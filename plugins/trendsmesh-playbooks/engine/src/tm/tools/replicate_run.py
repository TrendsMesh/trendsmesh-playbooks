"""Run any Replicate model from a JSON spec; save outputs, the record and manifest rows (paid).

    tm tool replicate_run --run RUN SPEC.json --cost USD [--name NAME] [--json]
    tm tool replicate_run --run RUN --resume 03_wip/<NAME>_vNN.run.json [--json]     (free)

spec.json: {"model": "owner/name" or "owner/name:version", "input": {...},
            "file_encoding": "url" (default) or "base64"}.
Input values that are paths to existing local files (or lists of them; relative paths are read
from the spec's folder) are sent as files: with "url" through Replicate's Files API, which keeps
them private to the user's account; with "base64" as data URIs, which keep the file extension
(ProPainter checks it, VARIANTS 4a). Nothing is ever hosted publicly.
Any input key works: Veo's first frame and last frame (`"image"` and `"last_frame"`, method E's
bridge clip) are two local paths in `input`, and both are sent as files. Note: for an official
model name ("owner/name") the replicate library ignores `file_encoding` and always uses its Files
API; "base64" takes effect only with a pinned "owner/name:version".

Paying never loses its result. Before the API call the version is reserved by writing
03_wip/<NAME>_vNN.run.json (status "not started") and the output names are checked. The
prediction id goes into that record as soon as Replicate accepts the run, and the status, metrics
and output URLs right after it finishes; downloads then fill in `outputs`. If a download (or the
wait) fails, the record keeps the paid prediction, and `--resume <record>` fetches the same
prediction (free) and downloads what is missing, never paying again. Outputs that are not file
URLs (text) are kept in the record and refused.

A prediction that ends failed or canceled with no output reports $0 spent, and its record gets a
`cost_note` to confirm that on the Replicate dashboard; so does a run Replicate refuses at creation
(which already reports nothing spent). A connection failure while starting keeps the estimate spent.
For organic video, `tm tool` runs `organic_specs.guard` before this (tools.PRECHECK).

Outputs: 03_wip/<NAME>_vNN_<i>.<ext>. Each output and the record get a manifest row (prompt,
parameters, model, the approved `--cost` estimate in USD: Replicate's prices must be confirmed
before a run, lesson 7), with the raw request and response beside it. The engine checks and
records `--cost` against the ai_usd budget before this runs (`tm tool`).

The key is read from REPLICATE_API_TOKEN, which the engine sets from the plugin's secrets (no
.env files). It is never printed, logged or written. Ported from
handoff/refresh-ad_v02/tools/replicate_run.py without python-dotenv.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from tm.tools import _common as c


# A prediction that failed before any output, and a run refused at creation, cost nothing (HANDOFF §4).
COST_NOTE = "failed before any output: $0 expected; confirm on the Replicate dashboard"
FAILED = ("failed", "canceled")   # Replicate's ends without a result


def _token() -> str:
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise c.ToolStop("The Replicate token is not set, so nothing was sent and nothing was spent. Open "
                         "/plugin, choose trendsmesh-playbooks, set the Replicate token, then start a new "
                         "session. The run continues from the same place.")
    return token


def _resolve(value, base: Path, opened: list):
    if isinstance(value, list):
        return [_resolve(v, base, opened) for v in value]
    p = c.local_file(value, base)
    if p is None:
        return value
    fh = p.open("rb")
    opened.append(fh)
    return fh


def _described(value, base: Path):
    """The input as recorded: local files by name, never their bytes."""
    if isinstance(value, list):
        return [_described(v, base) for v in value]
    p = c.local_file(value, base)
    return f"file:{p.name}" if p else value


def _prediction(pred) -> dict:
    keep = ("id", "model", "version", "status", "error", "metrics", "output", "created_at", "started_at",
            "completed_at")
    return {k: getattr(pred, k, None) for k in keep}


def _save(path: Path, record: dict) -> None:
    c.write_json(path, record)


def _client():
    import replicate

    return replicate.Client(api_token=_token())


def _resume_hint(record_path: Path) -> str:
    return (f" The prediction is paid and saved in {record_path.name}: run again with --resume "
            f"03_wip/{record_path.name} to finish it without paying again.")


def _finish(client, pred, record: dict, record_path: Path, out: Path, name: str) -> dict:
    """Wait for the prediction, record it, then download what is missing."""
    import httpx
    from replicate.exceptions import ReplicateError

    try:
        pred.wait()
    except (httpx.HTTPError, ReplicateError) as exc:
        raise c.ToolError(c.scrub(f"Waiting for {record['model']} failed: {exc}.") + _resume_hint(record_path)) \
            from None
    record.update({"status": pred.status, "metrics": pred.metrics, "error": pred.error,
                   "output": pred.output, "prediction": _prediction(pred)})
    if pred.status in FAILED and not pred.output:
        c.report_cost(True, 0.0)
        record["cost_note"] = COST_NOTE
    _save(record_path, record)
    if pred.status != "succeeded":
        note = f" ({COST_NOTE})" if record.get("cost_note") else ""
        raise c.ToolError(c.scrub(f"{record['model']} {pred.status}: {pred.error}") + note)
    urls = pred.output if isinstance(pred.output, list) else [pred.output]
    if not urls or not all(isinstance(u, str) and u.startswith(("https://", "http://")) for u in urls):
        raise c.ToolError(f"{record['model']} answered with something other than files (kept in "
                          f"{record_path.name}); this tool only saves file outputs.")
    for i, url in enumerate(urls):
        ext = Path(url.split("?")[0]).suffix or ".bin"
        dst = out / f"{name}_{i}{ext}"
        if dst.name in record["outputs"] and dst.is_file():
            continue
        part = dst.with_name(dst.name + ".part")
        try:
            with httpx.stream("GET", url, timeout=300, follow_redirects=True) as resp:
                resp.raise_for_status()
                with part.open("wb") as fh:
                    for chunk in resp.iter_bytes():
                        fh.write(chunk)
        except httpx.HTTPError as exc:
            part.unlink(missing_ok=True)
            raise c.ToolError(f"Downloading output {i} of {record['model']} failed: {exc}."
                              + _resume_hint(record_path)) from None
        part.replace(dst)
        record["outputs"].append(dst.name)
        _save(record_path, record)
    record["status"] = "done"
    _save(record_path, record)
    return record


def run(spec_path: Path | str, out_dir: Path | str, name: str) -> dict:
    """Run the spec (paid); outputs go to out_dir as <name>_<i>.<ext>, the record to <name>.run.json."""
    import httpx
    from replicate.exceptions import ReplicateError

    _token()
    spec_path, out = Path(spec_path), Path(out_dir)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    model, inputs = spec["model"], spec.get("input", {})
    encoding = spec.get("file_encoding", "url")
    if encoding not in ("url", "base64"):
        raise ValueError(f'file_encoding must be "url" or "base64", got {encoding!r}.')
    out.mkdir(parents=True, exist_ok=True)
    record_path = out / f"{name}.run.json"
    taken = [p.name for p in out.glob(f"{name}_*")]
    if record_path.exists() or taken:
        raise c.ToolError(f"{name} is already used in 03_wip ({', '.join(taken) or record_path.name}), and "
                          "files are never overwritten. Nothing was sent.")
    record = {"model": model, "input": {k: _described(v, spec_path.parent) for k, v in inputs.items()},
              "file_encoding": encoding, "status": "not started", "prediction_id": None, "outputs": [],
              "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _save(record_path, record)  # the version is reserved before anything is paid
    opened: list = []
    client = _client()
    started = time.time()
    try:
        inp = {k: _resolve(v, spec_path.parent, opened) for k, v in inputs.items()}
        # Official models run by name; community models need a pinned version ("owner/name:version").
        if ":" in model:
            pred = client.predictions.create(version=model.split(":", 1)[1], input=inp,
                                             file_encoding_strategy=encoding)
        else:
            pred = client.predictions.create(model=model, input=inp, file_encoding_strategy=encoding)
    except ReplicateError as exc:
        record.update({"status": "refused", "cost_note": COST_NOTE})   # report_cost(False) already said so
        _save(record_path, record)
        message = c.scrub(f"Replicate refused the run of {model} ({exc.status}): {exc.detail or exc.title}")
        if exc.status in (401, 402, 403):
            raise c.ToolStop(f"{message}. Check the token and the account's credit. Nothing was spent; the "
                             "run continues from the same place.") from None
        raise c.ToolError(message + ". Nothing was spent.") from None
    except httpx.HTTPError as exc:
        c.report_cost(True)  # unknown whether Replicate started it: keep the estimate spent
        record["status"] = "unknown"
        _save(record_path, record)
        raise c.ToolError(f"The connection to Replicate failed while starting {model}: {exc}. Check the "
                          "Replicate dashboard before trying again.") from None
    finally:
        for fh in opened:
            fh.close()
    c.report_cost(True)
    record.update({"prediction_id": pred.id, "status": pred.status})
    _save(record_path, record)
    record = _finish(client, pred, record, record_path, out, name)
    record["wall_seconds"] = round(time.time() - started, 1)
    _save(record_path, record)
    return record


def resume(record_path: Path | str) -> dict:
    """Finish a paid run from its record: fetch the same prediction (free), download what is missing."""
    record_path = Path(record_path)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if not record.get("prediction_id"):
        raise c.ToolError(f"{record_path.name} has no prediction id: that run never started, so there is "
                          "nothing to resume (run the spec again).")
    client = _client()
    pred = client.predictions.get(record["prediction_id"])
    name = record_path.name[: -len(".run.json")]
    return _finish(client, pred, record, record_path, record_path.parent, name)


def _inside_run(run_folder, value: str) -> Path:
    """A --resume record: a non-empty path relative to the run folder, never outside it."""
    from pathlib import PurePosixPath, PureWindowsPath

    text = value.strip()
    if not text:
        raise c.ToolError("--resume needs the run record to finish (03_wip/<NAME>_vNN.run.json). Nothing was run.")
    if (Path(text).is_absolute() or PureWindowsPath(text).is_absolute() or PureWindowsPath(text).drive
            or ".." in PurePosixPath(text.replace("\\", "/")).parts):
        raise c.ToolError(f"--resume must be a path inside the run folder, got {value!r}. Nothing was run.")
    path = run_folder.path / text
    try:
        path.resolve().relative_to(run_folder.path.resolve())
    except ValueError:
        raise c.ToolError(f"--resume must be a path inside the run folder, got {value!r}. Nothing was run.") from None
    if not path.name.endswith(".run.json") or not path.is_file():
        raise c.ToolError(f"{text} is not a run record of this run. Nothing was run.")
    return path


def _rows(run_folder, record: dict, record_path: Path, before: list[str], spec_ref: str, cost: str) -> list[str]:
    prompt = record["input"].get("prompt")
    params = {k: v for k, v in record["input"].items() if k != "prompt"}
    request = {"model": record["model"], "input": record["input"], "file_encoding": record["file_encoding"]}
    outputs = []
    for name in record["outputs"]:
        path = record_path.parent / name
        if name not in before:
            c.record(run_folder, path, "Replicate", spec_ref, prompt=prompt if isinstance(prompt, str) else None,
                     params=params, model=record["model"], cost=cost, request=request,
                     response=record.get("prediction"))
        outputs.append(c.rel(run_folder, path))
    return outputs


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tm tool replicate_run", description="Run a Replicate model (paid).",
                                allow_abbrev=False)
    p.add_argument("--run", required=True, help="the run folder")
    p.add_argument("spec", nargs="?", help='JSON: {"model": "owner/name", "input": {...}}')
    p.add_argument("--name", default=None, help="output name (default: the spec's file name)")
    p.add_argument("--cost", type=float, default=None, help="the approved estimate in USD")
    p.add_argument("--resume", default=None, help="a run record (relative to the run folder) to finish")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    run_folder = c.open_run(a.run)
    c.report_cost(False)
    _token()  # stop before anything is written when the key is missing
    out_dir = run_folder.path / "03_wip"
    if a.resume is not None:
        record_path = _inside_run(run_folder, a.resume)
        before = list(json.loads(record_path.read_text(encoding="utf-8")).get("outputs", []))
        record = resume(record_path)
        cost = "paid before (resumed)"
    else:
        if not a.spec:
            raise c.ToolError("Give the spec file (or --resume <record>).")
        a.spec = str(run_folder.given(a.spec))   # as given from here, else run-relative (the organic guard reads the same)
        base = c.stem_of(a.name or a.spec)
        stem = run_folder.next_version("wip", base, "run.json").name[: -len(".run.json")]
        record_path = out_dir / f"{stem}.run.json"
        before = []
        cost = f"{a.cost:g} USD (approved estimate)" if a.cost else "not given"
        try:
            record = run(a.spec, out_dir, stem)
        finally:
            if record_path.exists():
                c.record(run_folder, record_path, "Replicate run record", c.parent_ref(run_folder, a.spec),
                         model=json.loads(record_path.read_text(encoding="utf-8")).get("model"), cost=cost)
    spec_ref = c.parent_ref(run_folder, a.spec) if a.spec else c.rel(run_folder, record_path)
    outputs = _rows(run_folder, record, record_path, before, spec_ref, cost)
    summary = {k: record.get(k) for k in ("model", "prediction_id", "status", "metrics", "wall_seconds")}
    rel_record = c.rel(run_folder, record_path)
    return c.finish(a, {"tool": "replicate_run", "outputs": outputs, "record": rel_record, **summary},
                    f"{record['model']} done: {', '.join(outputs)} (record {rel_record}).")


if __name__ == "__main__":
    raise SystemExit(main())
