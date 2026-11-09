"""Organic video's generation guard (OV5, OV6, OV8, OV9, OV10): the spec checks, "never regenerate",
`tm organic redo` and `tm organic dashboard-checked`.

`tm tool replicate_run` on an organic-video run calls `guard(run, args)` for a paid call, after the tier,
key and stopped-run checks and before `budget.spend` (`tools.PRECHECK`). A refusal is a stop (exit 2): nothing is run
and nothing is spent. Refresh-ad has no pre-check.

The guard reads only the latest *checked* pack (`organic_pack.checked_pack`: the version
`tm organic pack check --stage pack` marked, unchanged since, whose totals are in run.json `planned`). A
newer pack that is not checked stops it: run the pack check first.

A spec is run under a pack item's name: the stem is `_common.stem_of(--name or spec)`, as replicate_run
names it, and it must be one of the pack's `stages[].items[].name`, an item the pack makes with this very
model (an item with no model is never generated). Its records are `03_wip/<stem>_vNN.run.json`. An item
is a video when its model makes video anywhere in the pack (`_video_models`: a section's, an OV6 tier's,
the upscaler, or an item's outside the images stage), whatever stage it sits in; else it is an image.

`check(run, spec, spec_path)` gives the spec's problems:
- minimax/h3: no `first_frame_image` together with reference media (E006); reference mode needs
  `ratio: "9:16"`; each local audio reference is 2–15 s (ffprobe through `tm.tools._common.probe`);
  `duration` ≤ 15; `resolution` is the pack's choice (768p or 720p → "768P", 1080p → "2K");
- openai/gpt-image-2: `output_format: "png"`; `quality: "high"` for an item with `face: true`;
- bytedance/seedance-2.0 / 2.5: no input is the pack's `host.image`, the same file or the same name in any
  case (Seedance refuses photoreal faces, E005);
- any model: no input under `02_research/`, in any case (organic clips are evidence, never footage); every local
  input is a file of the run or a packshot the pack names (PR C review Minor 2); a voice reference
  (`VOICE_REFERENCES`) only when the pack's `speech.voice_reference` holds the user's request (OV7); the
  model is one of the pack's, and the item's own; a video item's input images are picked images or packshots;
  with a featured or hero product, an item names a packshot among its inputs (a video item may carry
  the product through a picked frame instead).

A picked image is the current pick of its image item (`picked`). The picks of an item are its images-stage rows
of `03_wip/az_log.jsonl` (the A–Z log), each one JSON object, `AZ_FIELDS`:

    {"stage": "images" | "takes", "name": <pack item>, "file": "03_wip/<file>",
     "rubric": {...}, "reason": "<why this one>", "by": "rule" | "user", "at": "<ISO time>"}

which `tm organic pick` (`tm.organic_qa.pick`, which says what each stage's rubric holds) writes, and each accept on
the images check-in page (`page_image_rows`: a row of `03_wip/decisions_gate_images_vNN.json`, which
`tm organic decisions --page gate_images` writes, dated by when that page was built; a carried accept only when
that read kept the carried rows). A drop or redo of the item on that page ends its pick. The latest of an item's
picks, by when it was made or read, is its pick, and it counts (`counts`)
while it was made after the pack check that last changed its item (`item_checked_at`: its stage entry, model or
resolution, or a redo line added for it; a re-check that only prices another item's redo keeps it) and names an
output of the item's latest Replicate record that made any (`outputs`): a pick made before a re-plan of its item,
or of a take made again since, is no pick.

Then the takes (records of the stem):
- the latest record holds a prediction that is not done and did not fail (it is paid and still on
  Replicate): finish it for free with `--resume`; it is never run again (Review Focus 1);
- the latest record has no prediction id and is `unknown` (the start lost Replicate's answer) or
  `not started` (the process stopped before the answer): Replicate may be running or charging for it, so
  nothing runs until the user has looked at the dashboard and `tm organic dashboard-checked` records what
  they saw for that record;
- a video item with a done record runs again only on an open user request (`tm organic redo`), once the checked
  pack prices it (PR C review I4: a `"redo": true` line per request, `organic_pack.redo_lines`, so the total rose
  and the user's yes was given again with `--change`);
- an image item with a done record: on an open, priced request, or once automatically when the images check-in
  goes by rule at the run's level. The automatic redo runs only while the approved budget still covers it and every
  other item's line still owed (`_owed`: items not made yet, open requests), recorded as `auto_redo`; otherwise it
  is recorded as a request by rule, which the pack prices like any request.

Then the money (PR C review I2), after the takes' rules and before `budget.spend`: the user's yes at the pack
check-in is current (flow's `approval_gap`: a re-plan at a higher total needs `tm decide pack approve --change`),
the planned `ai_usd` is approved in full (flow's `planned_gap`, as the spending steps wait), and `--cost` is the
item's own line in the checked pack (`priced_line`), within `organic_pack.TOL`.

run.json `organic.redos[<stem>]` lists the requests, the automatic redo and the dashboard checks:
`{kind: "request" | "auto_redo", note, by, at, after}`, `after` the stem's latest record when it was
made, and `{kind: "dashboard_checked", note, by, at, record}`. It is open until the stem has a newer record: replicate_run writes its record as the guarded
call starts, so a call refused after the guard (the budget) leaves the request open, and a call that
started uses it up.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from tm import checkins, flow, library, manifest, organic_pack, organic_proposals, state, tools, trend_spool
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.stops import AGAIN, AGAIN_SENTENCE, Stop
from tm.tools import _common as c
from tm.tools.replicate_run import FAILED

WIP = "03_wip"
AZ_LOG = f"{WIP}/az_log.jsonl"
AZ_FIELDS = ("stage", "name", "file", "rubric", "reason", "by", "at")
IMAGES = "images"                     # the pack stage of images (the images check-in)
IMAGES_DECISIONS = "decisions_gate_images"   # 03_wip/<this>_vNN.json: the images check-in page's decisions
IMAGES_BUILD = "tm organic page gate_images"   # the manifest source of an images page build (organic_pages.gate)
EVIDENCE = "02_research"
H3 = "minimax/h3"
H3_REFERENCES = ("reference_image_urls", "reference_video_urls", "reference_audio_urls")
VOICE_REFERENCES = ("reference_audio_urls", "reference_audios")   # H3's and Seedance's voice samples (OV7)
H3_AUDIO_S = (2.0, 15.0)              # OV10: an H3 audio reference is 2–15 s
H3_TAKE_MAX_S = 15
H3_RESOLUTION = {"720p": "768P", "768p": "768P", "1080p": "2K"}   # the pack's choice → H3's value
GPT_IMAGE = "openai/gpt-image-2"
SEEDANCE_NO_FACE = ("bytedance/seedance-2.0", "bytedance/seedance-2.5")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".bmp")
DONE = "done"
UNCERTAIN = ("unknown", "not started")   # no prediction id, and Replicate may have started it
REQUEST, AUTO_REDO, CHECKED = organic_pack.REDO_REQUEST, "auto_redo", "dashboard_checked"
PAID = "ai_usd"                        # the budget kind replicate_run spends (tools.TOOLS)
REDO_LINE = organic_pack.REDO_LINE     # a cost line `"redo": true` prices one requested redo of its item

E006 = "H3 refuses a first frame with reference media (E006)"
CLIPS = "organic clips are evidence, never footage"
NO_PACK = ("No checked pack is the latest in this run, so nothing is generated: run the pack check first "
           "(tm organic pack check --stage pack) and show the user its cost.")
RESUME = ("This take was paid for and is still on Replicate. Finish it for free with `--resume {record}`; it is "
          "never run again.")
NEVER = ("A video is never regenerated automatically. Ask the user; if they want a redo, record their words with "
         "`tm organic redo` and show its cost.")
DASHBOARD = ("{record} has no prediction id: the start lost Replicate's answer, or the process stopped before it came. "
             "Replicate may already be running or charging for it — check the Replicate dashboard first. If the take "
             "is there, it is paid: ask the user before anything is made again.")
CLEAR = ("Once the user has looked, record what they saw: tm organic dashboard-checked --run <run> --name {stem} "
         "--note \"<their words>\"; then {stem} may run again.")
IMAGE_ASKED = ("At this level the user picks the images, so an image is made again only when they ask. Ask the user; "
               "if they want a redo, record their words with `tm organic redo` and show its cost.")
PRICE_REDO = ("The redo of {item} is not priced yet ({asked} asked for, {lines} priced in the checked pack), and money "
              "is never taken from another item's line. Add one cost line for it to a new pack version, priced like "
              "{item}'s own and marked \"redo\": true; check it (tm organic pack check --stage pack), show the user the "
              "new total and record their yes with `tm decide pack approve --change`, then `tm budget approve ai_usd "
              "<the new total>`; then run it.")
AUTO_TOO_DEAR = ("The one automatic redo of {item} ({cost:g} USD) does not fit the approved budget with the other "
                 "items still to make ({owed:g} USD; {left:g} USD is left), so it is recorded as a request.")
IMAGE_ONCE = ("This image was already made again once automatically, the one redo the images check-in allows by rule. "
              "Ask the user; if they want another, record their words with `tm organic redo` and show its cost.")


def _stop(message: str) -> str:
    return f"{message} Nothing was run or spent; {AGAIN}."


def _model(spec: dict) -> str:
    """The spec's model without a pinned version."""
    return str(spec.get("model") or "").split(":", 1)[0]


def _item(pack: dict, stem: str) -> tuple[str, dict] | None:
    """(stage, item) of the pack item run under `stem`, or None."""
    for st in pack["stages"]:
        for item in st["items"]:
            if c.stem_of(item["name"]) == stem:
                return st["stage"], item
    return None


def _video_models(pack: dict) -> set[str]:
    """The models that make video in this pack: its sections', the OV6 tiers, the upscaler, and any item's outside
    the images stage."""
    made = {s["model"] for s in pack["sections"] if s.get("model")}
    made |= set(organic_pack.TIERS.values()) | {organic_pack.UPSCALER}
    return made | {item["model"] for st in pack["stages"] if st["stage"] != IMAGES for item in st["items"]
                   if item.get("model")}


def _is_video(pack: dict, item: dict) -> bool:
    return item.get("model") in _video_models(pack)


item_of, is_video = _item, _is_video   # public names for organic_qa (the picks)


def _evidence(rel: str) -> bool:
    """Under 02_research/, in any case (a case-blind disk keeps the case the spec wrote)."""
    return rel.split("/", 1)[0].casefold() == EVIDENCE


def _inside(run: RunFolder, path: Path) -> bool:
    """Under the run's folder, in any case (a case-blind disk keeps the case the spec wrote) and either slash."""
    root = run.path.resolve().as_posix().replace("\\", "/").casefold().rstrip("/") + "/"
    return path.as_posix().replace("\\", "/").casefold().startswith(root)


def _packshots(run: RunFolder, pack: dict) -> set[Path]:
    """The checked pack's product.packshots (workspace-relative), as resolved paths."""
    workspace = trend_spool.workspace_of(run)
    return {(workspace / shot).resolve() for shot in pack["product"]["packshots"]}


def _same_file(a: Path, b: Path) -> bool:
    if str(a).casefold() == str(b).casefold():
        return True
    try:
        return a.samefile(b)
    except OSError:   # one of them is not there (yet)
        return False


def _names(pack: dict) -> str:
    return ", ".join(item["name"] for st in pack["stages"] for item in st["items"])


def _inputs(spec: dict, base: Path) -> list[tuple[str, Path]]:
    """(input key, resolved path) of every local file the spec sends, lists included."""
    out = []
    for key, value in (spec.get("input") or {}).items():
        for v in value if isinstance(value, list) else [value]:
            p = c.local_file(v, base)
            if p is not None:
                out.append((key, p.resolve()))
    return out


def _rel(run: RunFolder, path: Path) -> str:
    """Run-relative with forward slashes; a file outside the run by its full path."""
    try:
        return path.resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        return str(path)


def az_rows(run: RunFolder) -> list[dict]:
    """The rows of the A–Z log (`AZ_LOG`), oldest first. A damaged line is a Stop that names it."""
    rows, damaged = library.read_jsonl(run.path / AZ_LOG)
    if damaged:
        raise Stop(f"{AZ_LOG} has damaged lines ({', '.join(map(str, damaged))}): each line is one JSON object "
                   f"{{{', '.join(AZ_FIELDS)}}}. Mend them by hand; {AGAIN}.")
    return rows


def when(text: object) -> datetime | None:
    """An ISO time as an aware datetime (a naive one is UTC), else None."""
    try:
        found = datetime.fromisoformat(str(text))
    except ValueError:
        return None
    return found if found.tzinfo else found.replace(tzinfo=timezone.utc)


def checked_at(run: RunFolder) -> datetime | None:
    """When the latest pack check passed (run.json `checked.pack.at`)."""
    return when((state.load(run).checked.get("pack") or {}).get("at"))


def item_checked_at(run: RunFolder, stem: str, checked: datetime | None) -> datetime | None:
    """Since when a pick of the item under `stem` must be made to count: the pack check that last changed that item
    (`organic_pack.item_marks`; run.json `checked.pack.since`, kept across re-checks that leave it as it was, such
    as one that only prices another item's redo), else `checked`, the latest pack check."""
    since = ((state.load(run).checked.get("pack") or {}).get("since") or {}).get(stem)
    return when(since) if since and checked is not None else checked


def outputs(run: RunFolder, stem: str) -> tuple[set[str], set[str]]:
    """(the outputs of the item's latest record that has any, every output of its records), run-relative.
    A damaged record is a Stop (`records`)."""
    latest: set[str] = set()
    every: set[str] = set()
    for _, record in _records(run, stem):
        made = {f"{WIP}/{name}" for name in record.get("outputs") or [] if isinstance(name, str)}
        if made:
            latest = made
            every |= made
    return latest, every


def _decisions_files(run: RunFolder, stem: str) -> list[Path]:
    """`03_wip/<stem>_vNN.json`, oldest first (by version)."""
    folder = run.path / WIP
    pattern = re.compile(rf"^{re.escape(stem)}_v(\d+)\.json$")
    found = sorted((int(m.group(1)), p) for p in folder.glob(f"{stem}_v*.json") if folder.is_dir()
                   for m in [pattern.match(p.name)] if m)
    return [p for _, p in found]


def _built(run: RunFolder, source: str = IMAGES_BUILD) -> dict[str, str | None]:
    """Each images page build (or, with `source`, another page's) -> when it was built (its row's `built_at`)."""
    out = {}
    for row in manifest.rows(run):
        if row["source"] == source:
            try:
                params = json.loads(row["params"]) if row["params"] else {}
            except ValueError:
                params = {}
            out[row["file"]] = params.get("built_at") if isinstance(params, dict) else None
    return out


def page_image_rows(run: RunFolder, kind: str = IMAGES, page: str = "gate_images") -> list[dict]:
    """Each decision on an images item (or, with `kind`, a storyboard item: `storyboard`; with `page` "gate_video"
    and `kind` "motion", a stills item's motion-graphics render) of the images check-in page, as a row of the picks
    (`AZ_FIELDS`, by "user", stage `kind`): the rows of `03_wip/decisions_<page>_vNN.json`. An accept with a file is
    a pick, dated by when its page was built (Task 17 I1: never by when the decisions were read, so a page built
    before a re-plan never makes a pick that counts); a drop or a redo is a row that ends the item's pick (`void`, I2). They are ordered by when they were
    read (`read_at`). A carried row counts only when that read kept the carried rows (`keep_carried`). A file that
    cannot be read is a Stop that names it."""
    out = []
    words = page.removeprefix("gate_")                    # the images (or video) check-in page
    built = _built(run, f"tm organic page {page}")
    for path in _decisions_files(run, f"decisions_{page}"):
        rel = f"{WIP}/{path.name}"
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            body = exc
        if not isinstance(body, dict) or not isinstance(body.get("decisions"), dict):
            why = body if isinstance(body, Exception) else "not its shape"
            raise Stop(f"{rel} cannot be read as the {page} page's decisions ({why}): read them again (tm organic "
                       f"decisions --page {page}), or move it out of {WIP}; {AGAIN}.")
        keep = body.get("keep_carried") is True
        at = built.get(body.get("folder")) if body.get("source") != "chat" else body.get("at")
        for row in body["decisions"].values():
            if not (isinstance(row, dict) and row.get("kind") == kind and isinstance(row.get("name"), str)
                    and (keep or not row.get("carried"))):
                continue
            base = {"stage": kind, "name": row["name"], "rubric": {"page": rel}, "by": "user", "at": at,
                    "read_at": body.get("at")}
            if row.get("action") == "accept" and isinstance(row.get("file"), str):
                out.append({**base, "file": row["file"], "reason": f"accepted on the {words} check-in page"})
            elif row.get("action") in ("drop", "redo"):
                out.append({**base, "file": None, "void": row["action"],
                            "reason": f"{row['action']} on the {words} check-in page"})
    return out


def image_rows(run: RunFolder) -> list[dict]:
    """Every pick of an image (the A–Z log's images rows and the images page's decisions), oldest first by when the
    engine learned of it."""
    rows = [r for r in az_rows(run) if r.get("stage") == IMAGES] + page_image_rows(run)
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(rows, key=lambda r: when(r.get("read_at") or r.get("at")) or oldest)


def counts(run: RunFolder, row: dict, *, checked: datetime | None) -> str | None:
    """Why a pick no longer counts (made before the pack check that last changed its item, `item_checked_at`, with
    `checked` the latest pack check; or not of the item's latest take), or None while it does. Reads only."""
    made = when(row.get("at"))
    file = str(row["file"]).replace("\\", "/")
    checked = item_checked_at(run, c.stem_of(row["name"]), checked)   # the one place (part 3's ruling)
    if checked is not None and (made is None or made < checked):
        return f"it was made before the pack was checked again ({file})"
    latest, _ = outputs(run, c.stem_of(row["name"]))
    if file not in latest:
        return f"{file} is not from the item's latest take ({', '.join(sorted(latest)) or 'none made'})"
    return None


def latest_picks(rows: list[dict]) -> dict[str, dict]:
    """The latest row of each item (by its stem), of rows oldest first; a later drop or redo (`void`) ends it."""
    out = {}
    for row in rows:
        if not isinstance(row.get("name"), str):
            continue
        if row.get("void"):
            out.pop(c.stem_of(row["name"]), None)
        elif isinstance(row.get("file"), str):
            out[c.stem_of(row["name"])] = row
    return out


def picked(run: RunFolder) -> set[str]:
    """The run-relative files that are the current pick of their image item (the module docstring). A damaged log
    line or decisions file is a Stop that names it."""
    checked = checked_at(run)
    return {str(row["file"]).replace("\\", "/") for row in latest_picks(image_rows(run)).values()
            if counts(run, row, checked=checked) is None}


def _level(pack: dict) -> str | None:
    return organic_proposals.PRODUCT_WORDS.get(str(pack["product"]["level"]).strip().lower())


def check(run: RunFolder, spec: dict, spec_path: Path, *, name: str | None = None) -> list[str]:
    """The spec's problems against the latest checked pack (the module docstring); empty means it may run.
    `name` is replicate_run's --name (the stem is that, or the spec's file name)."""
    pack = organic_pack.checked_pack(run)
    if pack is None:
        return [NO_PACK]
    spec_path = Path(spec_path)
    stem = c.stem_of(name or spec_path)
    if not isinstance(spec.get("input", {}), dict):
        return ["The spec's input must be one JSON object."]
    out: list[str] = []
    model = _model(spec)
    listed = sorted({m["model"] for m in pack["models"]})
    if model not in listed:
        out.append(f"{model or 'No model'} is not one of the pack's models ({', '.join(listed)}): generate only "
                   "with the models the user approved in the pack.")
    found = _item(pack, stem)
    if found is None:
        out.append(f"{stem} is not an item of the pack ({_names(pack)}): run each item under its own name "
                   "(--name <item>), so its takes are counted.")
    elif not found[1].get("model"):
        out.append(f"{found[1]['name']} has no model in the pack, so nothing is generated under its name: run each "
                   "take under the item the pack makes with its model.")
    elif found[1]["model"] != model:
        out.append(f"The pack makes {found[1]['name']} with {found[1]['model']}, and the spec runs {model or 'no model'}.")
    inp = spec.get("input") or {}
    inputs = _inputs(spec, spec_path.parent)
    shots = _packshots(run, pack)
    for key, path in inputs:
        rel = _rel(run, path)
        if _evidence(rel):
            out.append(f"{key} is {rel}, a saved trend video or image: {CLIPS}. Use the pack's own images, "
                       "picked frames or packshots.")
        elif not _inside(run, path) and not any(_same_file(path, shot) for shot in shots):
            out.append(f"{key} is {path.as_posix()}, outside this run and not a packshot the pack names: an item's "
                       "inputs are the run's own files (its images, picked frames, the host image, the voice lines) "
                       "or the packshots in the checked pack's product.packshots.")
    for key in VOICE_REFERENCES:
        if inp.get(key) and not isinstance(pack["speech"].get("voice_reference"), dict):
            out.append(f"{key} is a voice reference, and the checked pack has none: a voice reference is used only "
                       "when the user asks for it (OV7). Leave it out, or write their words in "
                       "speech.voice_reference and check the pack again.")
    if model == H3:
        _h3(pack, inp, spec_path.parent, out)
    elif model == GPT_IMAGE:
        if inp.get("output_format") != "png":
            out.append(f'gpt-image-2 needs output_format: "png" (got {inp.get("output_format")!r}).')
        if found and found[1].get("face") is True and inp.get("quality") != "high":
            out.append(f'{found[1]["name"]} is a face, so gpt-image-2 needs quality: "high" (got {inp.get("quality")!r}).')
    elif model in SEEDANCE_NO_FACE and pack["host"].get("image"):
        host = (run.path / pack["host"]["image"]).resolve()
        for key, path in inputs:
            if _same_file(path, host):
                out.append(f"{key} is the host image {pack['host']['image']}: Seedance refuses a photoreal face "
                           "(E005). Make a take with the host on minimax/h3.")
    if found:
        _frames(run, pack, found, inputs, out)
    return out


def _h3(pack: dict, inp: dict, base: Path, out: list[str]) -> None:
    references = [k for k in H3_REFERENCES if inp.get(k)]
    if inp.get("first_frame_image") and references:
        out.append(E006)
    if references and inp.get("ratio") != "9:16":
        out.append(f'H3 in reference mode needs ratio: "9:16" (got {inp.get("ratio")!r}).')
    audio = inp.get("reference_audio_urls") or []
    for value in audio if isinstance(audio, list) else [audio]:
        path = c.local_file(value, base)
        if path is None:
            continue
        try:
            seconds = float(c.probe(path)["duration"])
        except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError):
            out.append(f"The length of the audio reference {path.name} could not be read: give a 2–15 s sample.")
            continue
        low, high = H3_AUDIO_S
        if not low <= seconds <= high:
            out.append(f"The audio reference {path.name} is {seconds:g} s, and H3 takes 2–15 s: cut the sample "
                       "(the same text, at most 14 s for a voice reference).")
    duration = inp.get("duration")
    if duration is not None and not (isinstance(duration, (int, float)) and not isinstance(duration, bool)
                                     and math.isfinite(duration) and duration <= H3_TAKE_MAX_S):
        out.append(f"duration is {duration!r}, and an H3 take is at most {H3_TAKE_MAX_S} s.")
    choice = (pack.get("resolution") or {}).get("choice")
    if choice:
        want = H3_RESOLUTION.get(str(choice).split("_", 1)[0].lower())
        if want and str(inp.get("resolution", "")).upper() != want:
            out.append(f"resolution is {inp.get('resolution')!r}, and the pack's choice is {choice}: set resolution "
                       f'to "{want}".')


def _frames(run: RunFolder, pack: dict, found: tuple[str, dict], inputs: list[tuple[str, Path]],
            out: list[str]) -> None:
    """A video item's input images are picked; an item of a featured or hero product names a packshot."""
    _, item = found
    shots = _packshots(run, pack)
    images = [(k, p) for k, p in inputs if p.suffix.lower() in IMAGE_SUFFIXES and p not in shots]
    frames_picked = False
    if _is_video(pack, item) and images:
        try:
            chosen = picked(run)
        except Stop as exc:
            out.append(str(exc))
            return
        for key, path in images:
            rel = _rel(run, path)
            if rel in chosen:
                frames_picked = True
            elif not _evidence(rel):   # evidence is refused above already
                out.append(f"{key} is {rel}, which is not a picked image: a video's frames are images picked at "
                           f"the images check-in (a row of {AZ_LOG}).")
    level = _level(pack)
    if level in ("featured", "hero") and not frames_picked and not any(p in shots for _, p in inputs):
        out.append(f"The product is {level}, and {item['name']}'s inputs name no packshot: add the product's packshot "
                   f"({', '.join(pack['product']['packshots'])}) to its inputs (OV5).")


# --- the takes -------------------------------------------------------------------------------------

def _records(run: RunFolder, stem: str) -> list[tuple[Path, dict]]:
    """The stem's records, `03_wip/<stem>_vNN.run.json`, oldest first. A damaged one is a Stop."""
    pattern = re.compile(rf"^{re.escape(stem)}_v(\d+)\.run\.json$")
    folder = run.path / WIP
    found = sorted((int(m.group(1)), len(p.name), p) for p in folder.iterdir()
                   if (m := pattern.match(p.name)) and p.is_file()) if folder.is_dir() else []
    out = []
    for _, _, path in found:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            record = exc
        if not isinstance(record, dict):
            raise Stop(f"{WIP}/{path.name} cannot be read ({record}). Check that prediction on the Replicate dashboard "
                       f"before {stem} runs again; nothing was run or spent; {AGAIN}.")
        out.append((path, record))
    return out


records = _records   # public name for organic_qa (a pick names an output of the item's latest record)


def _redos(s: state.RunState, stem: str) -> list[dict]:
    rows = ((s.organic or {}).get("redos") or {}).get(stem) or []
    return [r for r in rows if isinstance(r, dict)]


def _uncertain(s: state.RunState, stem: str, records: list[tuple[Path, dict]]) -> Path | None:
    """The latest record when Replicate may have started it unseen (`UNCERTAIN`, no prediction id) and the user
    has not looked at the dashboard for it."""
    if records:
        path, record = records[-1]
        if not record.get("prediction_id") and record.get("status") in UNCERTAIN and not any(
                r.get("kind") == CHECKED and r.get("record") == path.name for r in _redos(s, stem)):
            return path
    return None


def _held(s: state.RunState, stem: str, records: list[tuple[Path, dict]]) -> str | None:
    """Why the stem's latest record holds every new run: paid and still on Replicate (resume it), or perhaps
    started unseen (check the dashboard). None when it holds nothing."""
    if records:
        path, record = records[-1]
        if record.get("prediction_id") and record.get("status") not in (DONE, *FAILED):
            return RESUME.format(record=f"{WIP}/{path.name}")
    unseen = _uncertain(s, stem, records)
    if unseen is not None:
        return f"{DASHBOARD.format(record=f'{WIP}/{unseen.name}')} {CLEAR.format(stem=stem)}"
    return None


def _add_redo(run: RunFolder, stem: str, entry: dict) -> None:
    s = state.load(run)
    redos = dict((s.organic or {}).get("redos") or {})
    redos[stem] = [*_redos(s, stem), entry]
    s.organic = {**(s.organic or {}), "redos": redos}
    state.save(run, s)


def priced_line(pack: dict, stem: str) -> dict | None:
    """The item's own ai_usd cost line in the pack (not a redo line), or None."""
    return next((line for line in pack["cost"]["lines"] if line.get("kind") == PAID and not line.get(REDO_LINE)
                 and isinstance(line.get("item"), str) and c.stem_of(line["item"]) == stem), None)


def _money_gap(s: state.RunState, pack: dict, stem: str, cost: str | None) -> str | None:
    """Why the paid call may not spend (PR C review I2), or None: the user's yes at the pack check-in is not
    current (flow's `approval_gap`: a re-plan after it needs `tm decide pack approve --change`), the planned amount
    is not approved in full (flow's `planned_gap`, as the spending steps wait), or `--cost` is not the item's priced
    line in the checked pack."""
    gap = flow.approval_gap(s, PAID, None)
    if gap:
        return gap
    if flow.planned_gap(s, (PAID,)):
        return " ".join(flow.planned_stop(PAID))
    line = priced_line(pack, stem)
    try:
        given = float(cost) if cost is not None else math.nan
    except ValueError:
        given = math.nan
    if line is None:
        return f"{stem} has no {PAID} cost line in the checked pack, so its cost is not approved."
    if not abs(given - float(line["cost"])) <= organic_pack.TOL:
        return (f"--cost {cost} is not {stem}'s line in the checked pack: {line['what']} costs {line['cost']:g} USD "
                f"({line['price_file']}, checked {line['checked']}). Run it with --cost {line['cost']:g}; another "
                "cost is a new pack, checked and shown to the user.")
    return None


def guard(run: RunFolder, args: list[str]) -> str | None:
    """`tools.PRECHECK[ORGANIC_VIDEO]["replicate_run"]`: None to let the paid call run, else the stop's message.
    It may record an automatic image redo in run.json (`organic.redos`)."""
    a = tools._parsed(args)
    if not a.spec:
        return _stop("Give the spec file to run (tm tool replicate_run --run R SPEC --name ITEM --cost USD).")
    spec_path = run.given(a.spec)   # from the working folder, else run-relative: replicate_run reads the same file
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return _stop(f"The spec {c.name_of(a.spec)} could not be read ({exc}): write it as one JSON object.")
    if not isinstance(spec, dict):
        return _stop(f"The spec {c.name_of(a.spec)} must hold one JSON object.")
    problems = check(run, spec, spec_path, name=a.name)
    if problems:
        return _stop(f"{c.name_of(a.spec)} is not run: " + " ".join(p if p.endswith(".") else p + "." for p in problems))
    stem = c.stem_of(a.name or a.spec)
    records = _records(run, stem)
    s = state.load(run)
    held = _held(s, stem, records)
    if held:
        return _stop(held)
    pack = organic_pack.checked_pack(run)
    refused, entry = _redo_rule(run, s, pack, stem, records)
    if refused:
        if entry:
            _add_redo(run, stem, entry)               # the automatic redo that did not fit: now a request to price
        return _stop(refused)
    unpaid = _money_gap(s, pack, stem, a.cost)
    if unpaid:
        return _stop(unpaid)
    if entry:
        _add_redo(run, stem, entry)
    return None


def _owed(run: RunFolder, s: state.RunState, pack: dict, stem: str) -> float:
    """What the approved budget still owes the other items: the priced line of each item not made yet (no done take),
    and of each open request of another item."""
    owed = 0.0
    for line in pack["cost"]["lines"]:
        if line.get("kind") != PAID or line.get(REDO_LINE) or not isinstance(line.get("item"), str):
            continue
        other = c.stem_of(line["item"])
        if other == stem:
            continue
        records = _records(run, other)
        if not any(r.get("status") == DONE for _, r in records):
            owed += float(line["cost"])
        elif any(r.get("kind") == REQUEST and r.get("after") == records[-1][0].name for r in _redos(s, other)):
            owed += float(line["cost"])
    return owed


def _redo_rule(run: RunFolder, s: state.RunState, pack: dict, stem: str,
               records: list[tuple[Path, dict]]) -> tuple[str | None, dict | None]:
    """(why the item may not run again, or None; the `organic.redos` entry to record, or None). The automatic image
    redo that fits the approved budget with everything still owed is recorded as `auto_redo`; one that does not fit is
    recorded as a request by rule, priced like any request. Reads only."""
    if not any(r.get("status") == DONE for _, r in records):
        return None, None                             # the item's first take (or one after a failure)
    after = records[-1][0].name
    redos = _redos(s, stem)
    name = _item(pack, stem)[1]["name"]
    if any(r.get("kind") == REQUEST and r.get("after") == after for r in redos):
        asked, lines = organic_pack.redos_asked(s, stem), organic_pack.redo_lines(pack, stem)
        if lines < asked:                             # the user's open request, not priced yet
            return PRICE_REDO.format(item=name, asked=asked, lines=lines), None
        return None, None                             # priced: the call's record uses the request up
    if _is_video(pack, _item(pack, stem)[1]):
        return NEVER, None
    autos = [r for r in redos if r.get("kind") == AUTO_REDO or (r.get("kind") == REQUEST and r.get("by") == "rule")]
    if any(r.get("after") != after for r in autos):
        return IMAGE_ONCE, None
    if autos:
        return None, None                             # recorded, and refused after the guard: still the one
    level = s.level if s.level in checkins.LEVEL_IDS else None
    if level is None or checkins.load(playbook=ORGANIC_VIDEO).route(IMAGES, level) != "rule":
        return IMAGE_ASKED, None
    line = priced_line(pack, stem)
    cost = float(line["cost"]) if line else 0.0
    left = s.budgets.get(PAID, 0.0) - s.spend.get(PAID, 0.0)
    owed = _owed(run, s, pack, stem)
    entry = {"note": "the images check-in goes by rule: one automatic redo", "by": "rule", "at": flow._now(),
             "after": after}
    if left + organic_pack.TOL >= cost + owed:
        return None, {"kind": AUTO_REDO, **entry}
    said = AUTO_TOO_DEAR.format(item=name, cost=cost, owed=owed, left=max(left, 0.0))
    return f"{said} {PRICE_REDO.format(item=name, asked=organic_pack.redos_asked(s, stem) + 1, lines=0)}", \
        {"kind": REQUEST, **entry}


def redo(run: RunFolder, name: str, note: str) -> dict:
    """Record the user's request to make an item again (`tm organic redo`). Returns {stem, item, stage, request}."""
    s = state.load(run)
    if s.playbook != ORGANIC_VIDEO:
        raise ValueError("tm organic redo is for organic video runs.")
    note = (note or "").strip()
    if not note:
        raise ValueError("--note holds the user's own words asking for the redo.")
    pack = organic_pack.checked_pack(run)
    if pack is None:
        raise Stop(f"{NO_PACK} {AGAIN_SENTENCE}")
    stem = c.stem_of(name)
    found = _item(pack, stem)
    if found is None:
        raise ValueError(f"{stem} is not an item of the pack ({_names(pack)}).")
    records = _records(run, stem)
    held = _held(s, stem, records)
    if held:
        raise Stop(f"{held} No redo is recorded for it; {AGAIN}.")
    if not any(r.get("status") == DONE for _, r in records):
        raise Stop(f"{found[1]['name']} has no finished take yet, so there is nothing to make again: its first run "
                   f"needs no request; {AGAIN}.")
    entry = {"kind": REQUEST, "note": note, "by": "user", "at": flow._now(), "after": records[-1][0].name}
    _add_redo(run, stem, entry)
    return {"stem": stem, "item": found[1]["name"], "stage": found[0], "request": entry}


def dashboard_checked(run: RunFolder, name: str, note: str) -> dict:
    """Record that the user looked at the Replicate dashboard for the stem's latest record, which may have started
    unseen (`tm organic dashboard-checked`), so the item may run again. Returns {stem, record, entry}."""
    s = state.load(run)
    if s.playbook != ORGANIC_VIDEO:
        raise ValueError("tm organic dashboard-checked is for organic video runs.")
    note = (note or "").strip()
    if not note:
        raise ValueError("--note holds what the user saw on the Replicate dashboard, in their words.")
    stem = c.stem_of(name)
    unseen = _uncertain(s, stem, _records(run, stem))
    if unseen is None:
        raise Stop(f"No take of {stem} waits for a look at the Replicate dashboard: its latest record has a prediction "
                   f"id or a known end, or is already checked; {AGAIN}.")
    entry = {"kind": CHECKED, "note": note, "by": "user", "at": flow._now(), "record": unseen.name}
    _add_redo(run, stem, entry)
    return {"stem": stem, "record": f"{WIP}/{unseen.name}", "entry": entry}
