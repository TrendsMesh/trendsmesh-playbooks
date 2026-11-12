"""Subcommands `tm run new` and `tm record`."""

from __future__ import annotations

import argparse
import re
import shutil
from datetime import date
from pathlib import Path

import yaml

from tm import cli, manifest, paths, playbooks, state, trend_spool
from tm.runfolder import ReadOnlyError, RunExists, RunFolder, slug


_emit = cli.emit
_fail = cli.fail


def _setup_run(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="run_command", metavar="action")
    new = sub.add_parser("new")
    new.add_argument("--name", required=True)
    new.add_argument("--playbook", default=playbooks.REFRESH_AD, help="a playbook id or skill name")
    new.add_argument("--after", help="the run folder this run follows (same playbook and workspace)")
    new.add_argument("--seed", help="creative brief or organic video: start from a trend research pick, its "
                                    "seed_id (tm seeds list --source pb4)")
    new.add_argument("--json", action="store_true")


def _previous(workspace: Path, after: str, pb: playbooks.Playbook) -> str:
    """The `--after` run, relative to the workspace, once it is a run of `pb` in this workspace.
    A relative `--after` is read from the workspace."""
    prev = RunFolder.open(workspace / after)
    try:
        rel = prev.path.resolve().relative_to(workspace.resolve())
    except ValueError:
        raise ValueError(f"{prev.path} is not a run in this workspace ({workspace}).") from None
    theirs = state.load(prev).playbook
    if theirs != pb.id:
        other = next((p.name for p in playbooks.all_playbooks() if p.id == theirs), theirs)
        raise ValueError(f"{prev.path.name} is a run of {other}, not of {pb.name}: a run follows "
                         "another run of the same playbook.")
    return rel.as_posix()


SEEDED = (playbooks.CREATIVE_BRIEF, playbooks.ORGANIC_VIDEO)  # the playbooks a trend research pick can start


def _seed(workspace: Path, seed_id: str, pb: playbooks.Playbook) -> dict:
    """The seed row a creative brief or organic video run starts from; found before the run folder is
    made (`brief_config.find_seed`, the same seeds and kinds for both)."""
    if pb.id not in SEEDED:
        names = " or ".join(playbooks.get(p).name for p in SEEDED)
        raise ValueError(f"--seed starts a {names} run from a trend pick; {pb.name} does not take one.")
    from tm import brief_config  # only a seeded run needs it
    return brief_config.find_seed(workspace, seed_id, playbook=pb.id)


def _finish(run: RunFolder, previous: str | None, seed: dict | None) -> None:
    """What the new run records beyond its folder: the run it follows and the seed it starts from
    (`brief_config.start_from_seed` names it in the playbook's own state). On a failure the new folder
    is removed, so no run is left that resumes without them."""
    try:
        if previous:
            s = state.load(run)
            s.previous_run = previous
            state.save(run, s)
        if seed is not None:
            from tm import brief_config
            brief_config.start_from_seed(run, seed)
    except (OSError, ValueError) as exc:
        shutil.rmtree(run.path, ignore_errors=True)
        what = "from the seed" if seed is not None else "after the earlier run"
        if run.path.exists():  # e.g. a file held open on Windows
            raise ValueError(f"The run could not be started {what} ({exc}), and its folder {run.path} could not "
                             "be removed. Delete that folder, then start the run again with the same "
                             "command.") from None
        raise ValueError(f"The run could not be started {what} ({exc}), so it was not kept. Start it "
                         "again with the same command.") from None


def _channels(path: Path) -> set[str]:
    """The channels a run's config names (organic video's `channels`), as run names spell them; none without."""
    try:
        cfg = yaml.safe_load((path / "config.yaml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return set()
    found = cfg.get("channels") if isinstance(cfg, dict) else None
    return {slug(str(c)).casefold() for c in found} if isinstance(found, list) else set()


def _started(s: state.RunState, path: Path) -> bool:
    """Anything was done in the run: a step reached, a level or a decision, or its config written. A run folder made
    and never used (a new run the user then did not want) is not one to continue."""
    return bool(s.step or s.level or s.decisions or (path / "config.yaml").is_file())


def unfinished_runs(workspace: Path, playbook: str, name: str, *, but: Path | None = None) -> list[dict]:
    """The runs of `playbook` in the workspace that are not done and were started, under the same name (as its folder
    spells it, or that name's `-2`, `-3` … of a later run the same day) or for the same channel (organic video's
    config `channels`): {folder (workspace-relative), created, step, status}, the newest first. `but` is left out.
    Issue #90: `tm run new` returns them, so an unfinished run is never missed."""
    base = slug(name).casefold()
    same = re.compile(rf"^\d{{4}}-\d{{2}}-\d{{2}}_{re.escape(base)}(-\d+)?$")
    folder = Path(workspace) / "runs" / playbooks.get(playbook).id
    found = []
    for path in folder.iterdir() if folder.is_dir() else ():
        if (but is not None and path.resolve() == Path(but).resolve()) or not (path / "manifest.md").is_file():
            continue
        if not (same.match(path.name.casefold()) or base in _channels(path)):
            continue
        try:
            s = state.load(RunFolder.open(path))
        except (OSError, ValueError):
            continue                          # a folder whose state cannot be read: `tm status` says why
        if s.status == "done" or not _started(s, path):
            continue
        found.append({"folder": path.relative_to(workspace).as_posix(), "created": s.created, "step": s.step,
                      "status": s.status})
    return sorted(found, key=lambda r: (r["created"], r["folder"]), reverse=True)


def _taken(args: argparse.Namespace, exc: RunExists) -> int:
    """A run of that name exists today: say which (its status and step, so the user can be asked whether
    to continue it) and a free name for a new one. Nothing is made."""
    payload = {"status": "error", "message": str(exc), "existing": str(exc.path), "suggested_name": exc.suggested}
    try:
        s = state.load(RunFolder.open(exc.path))
        payload.update(existing_status=s.status, existing_step=s.step)
    except (OSError, ValueError):
        pass                                  # a folder without a readable state: the message still says it
    cli.emit(args, payload, str(exc))
    return 1


def _run_run(args: argparse.Namespace) -> int:
    if args.run_command != "new":
        return _fail(args, "Use: tm run new --name <name> [--playbook <id|skill>] [--after <run folder>] "
                           "[--seed <seed_id>]")
    try:
        workspace = paths.workspace()
        pb = playbooks.offered(args.playbook)
        previous = _previous(workspace, args.after, pb) if args.after else None
        seed = _seed(workspace, args.seed, pb) if args.seed is not None else None
        run = RunFolder.create(workspace, args.name, date.today(), playbook=pb.id)
        _finish(run, previous, seed)
    except RunExists as exc:
        return _taken(args, exc)
    except (OSError, ValueError) as exc:
        return _fail(args, str(exc))
    if pb.id in trend_spool.COLLECTING:
        try:
            # A new run collects only once its skill turns it on: this session's marker goes, another
            # session's (its own run) stays.
            trend_spool.turn_off(workspace, trend_spool.this_session())
        except OSError:
            pass                              # the run exists; the marker stays tied to its own run
    try:
        unfinished = unfinished_runs(workspace, pb.id, args.name, but=run.path)
    except OSError:
        unfinished = []
    text = str(run.path)
    if unfinished:
        listed = "; ".join(f"{r['folder']} (from {r['created']}, at {r['step']}"
                           + (", stopped" if r["status"] == "stopped" else "") + ")" for r in unfinished)
        text += (f"\nUnfinished runs of this {pb.name} name or channel: {listed}. Ask the user first whether to "
                 "continue one (then `tm next` on it; this new folder stays unused) or start this new one.")
    _emit(args, {"status": "done", "path": str(run.path), "run_id": run.path.name, "unfinished_runs": unfinished,
                 "message": text}, text)
    return 0


def _setup_record(p: argparse.ArgumentParser) -> None:
    p.add_argument("--run", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--stage", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--parent")
    p.add_argument("--prompt")
    p.add_argument("--params", help="a JSON object, or the path of a JSON file holding one")
    p.add_argument("--model")
    p.add_argument("--cost")
    p.add_argument("--before-after", dest="before_after")
    p.add_argument("--raw-response-file", dest="raw_response_file")
    p.add_argument("--json", action="store_true")


def _run_record(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        params = cli.json_arg(args.params, run) if args.params else None
        if params is not None and not isinstance(params, dict):
            raise ValueError("--params must be a JSON object, for example '{\"seconds\": 8}'.")
        raw = run.given(args.raw_response_file).read_text(encoding="utf-8") if args.raw_response_file else None
        manifest.record(run, args.file, args.stage, args.source, args.parent, args.prompt, params,
                        args.model, args.cost, args.before_after, raw_response=raw)
    except (OSError, ValueError, ReadOnlyError) as exc:
        return _fail(args, str(exc))
    _emit(args, {"status": "done", "file": args.file}, f"Recorded {args.file}")
    return 0


cli.register("run", _setup_run, _run_run)
cli.register("record", _setup_record, _run_record)
