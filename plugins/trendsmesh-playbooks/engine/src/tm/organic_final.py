"""Organic video's final files (PLAYBOOK.md "Output format", FLOWS.md G1 and G2): the `final_checked` step check.

`tm tool deliver` makes the files (its docstring); here they are read. A production run's idea is `idea_id(run)`:
the proposal it was started for (run.json `organic.proposal`, from `tm organic start`, as the proposals file writes it),
else the checked pack's id. That spelling is canonical: an id given in another case (`--id M5` for `m5`) is the same
idea (`idea_named`), every file is written with it, and every lookup matches names in any case (`RunFolder.latest`).
Its final is the latest `04_final/<id>_final_vNN.mp4`, and `final_gap` (G1) passes when that final:

- probes as 1080×1920, H.264, AAC at 48 kHz;
- measures within ±1 LU of its loudness target: the one `tm tool deliver finish` recorded beside it
  (`<final>.response.json`, `request.lufs_target`), else the run's `qa.lufs_target`;
- has its upload copy `<final stem>_upload.mp4` under `qa.upload_max_mb` (10^6 bytes a MB), or the over-limit stop
  recorded for this very final (run.json `checked.upload_over`, its path and sha256: the video stays a local file);
- has its cover JPG, the latest `04_final/kits/cover_<id>_vNN.jpg` when it was made for this final (`cover_of`: the
  final its `tm tool deliver cover` record names; a cover made by hand counts when it is not older than the final).

A video in sections (FLOWS.md F5, `organic_pack`'s sections) has a second G1 check, `sections_covered`
(`sections_gap`, preflight P3-F7): the edit the latest final was made from (up the manifest's parents to its `tm render
video` row, whose props it keeps) cuts the sections in their order, every segment's `src` from its own section's
outputs, or made from one (a sped-up take): a footage or talking section's are the takes of its model (and their
upscales), an animation's its `03_wip/<id>/renders/anim_vNN.mp4`, a stills section's the motion-graphics renders. The
times are the edit's own: the cuts are judged on the takes, not on the plan's seconds. A pack with one section passes.

The posting kit's check, `kit_checked` (G2), is `tm.kit.kit_gap`. All read only.
"""

from __future__ import annotations

import functools
import json
import re
import subprocess
from pathlib import Path

from tm import config, manifest, organic_config, organic_pack, organic_qa, organic_specs, render, state, stepchecks
from tm.runfolder import RunFolder
from tm.tools import _common as c

FINAL = "04_final"
KITS = "04_final/kits"
UPLOAD_OVER = "upload_over"          # run.json checked[upload_over]: the final whose upload copy stayed over the limit
SIZE = (1080, 1920)
SAMPLE_RATE = 48000
LUFS_SLACK = 1.0
MB = 1_000_000
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
NO_ID = ("the run names its idea: it is started from the proposals page with tm organic start, which writes "
         "00_raw/proposal.json and the proposal in run.json")
FINISH = "tm tool deliver finish --run <run> <the edit's render> --id {id}"


def setting(run: RunFolder, key: str):
    """The run's `qa.<key>` (config.yaml), else organic video's default."""
    cfg = config.load(run) if (run.path / config.FILE).is_file() else None
    found = config.get(cfg, f"qa.{key}") if cfg else None
    return found if found is not None else organic_config.DEFAULTS["qa"][key]


def idea_id(run: RunFolder) -> str | None:
    """The idea this production run makes: its proposal, else the checked pack's id; None without either."""
    found = (state.load(run).organic or {}).get("proposal")
    if not (isinstance(found, str) and ID.fullmatch(found)):
        found = (organic_pack.checked_pack(run) or {}).get("id")
    return found if isinstance(found, str) and ID.fullmatch(found) else None


def idea_named(run: RunFolder, given: str) -> str:
    """The run's idea id, as `tm organic start` wrote it from the proposals file, for an `--id` given in any case
    (`m5` and `M5` are one idea, and one name on a case-blind disk): every file is written with that spelling. A
    ValueError for a name that is not plain, or another idea's. Without an idea of its own, the run takes `given`."""
    if not ID.fullmatch(given):
        raise ValueError(f"--id {given!r} must be the idea's id, letters, digits, '-' and '_' only (e.g. M5).")
    pid = idea_id(run)
    if pid is None:
        return given
    if given.casefold() != pid.casefold():
        raise ValueError(f"--id {given} is not this run's idea, {pid} (00_raw/proposal.json): give --id {pid}.")
    return pid


def final_of(run: RunFolder, pid: str) -> Path | None:
    return run.latest(FINAL, f"{pid}_final", "mp4")


def cover_of(run: RunFolder, pid: str, final: Path) -> Path | None:
    """The latest cover JPG of the idea when it was made for `final` (Task 16 review M3: a cover of an older final
    never passes a newer one): its `tm tool deliver cover` record (`<cover>.response.json`, `request.final`) names
    that final, in any case; a cover with no such record (made by hand) counts when it is not older than the final."""
    cover = run.latest(KITS, f"cover_{pid}", "jpg")
    if cover is None:
        return None
    made_for = made_for_final(cover)
    if made_for is not None:
        return cover if made_for.replace("\\", "/").casefold() == c.rel(run, final).casefold() else None
    try:
        return cover if cover.stat().st_mtime >= final.stat().st_mtime else None
    except OSError:
        return None


def made_for_final(cover: Path) -> str | None:
    """The final a cover's `tm tool deliver cover` record names (run-relative), else None."""
    try:
        said = json.loads((cover.parent / f"{cover.name}.response.json").read_text(encoding="utf-8"))
        final = said["request"]["final"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return final if isinstance(final, str) else None


def upload_of(final: Path) -> Path:
    return final.with_name(f"{final.stem}_upload.mp4")


def target_of(run: RunFolder, final: Path) -> float:
    """The loudness target `tm tool deliver finish` made this final for, else the run's `qa.lufs_target`."""
    try:
        said = json.loads((final.parent / f"{final.name}.response.json").read_text(encoding="utf-8"))
        target = said["request"]["lufs_target"]
        if isinstance(target, (int, float)) and not isinstance(target, bool):
            return float(target)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return float(setting(run, "lufs_target"))


def _probe(path: Path) -> dict:
    """{width, height, vcodec, acodec, sample_rate, lufs} of a video (ffprobe, then ffmpeg's ebur128)."""
    from tm.tools.take_qa import loudness

    out = subprocess.run([c.ffprobe_bin(), "-v", "error", "-show_streams", "-of", "json", c.media(path)],
                         capture_output=True, check=True).stdout
    streams = json.loads(out.decode("utf-8", "replace")).get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
    return {"width": video.get("width"), "height": video.get("height"), "vcodec": video.get("codec_name"),
            "acodec": audio.get("codec_name"), "sample_rate": int(audio.get("sample_rate") or 0),
            "lufs": loudness(path)[0] if audio else None}


def _size(path: Path) -> int:
    return path.stat().st_size


def _minus(value: float) -> str:
    return f"{value:g}".replace("-", "−")


def final_gap(run: RunFolder) -> str | None:
    """The `final_checked` step check (G1): the module docstring. Reads only."""
    pid = idea_id(run)
    if pid is None:
        return NO_ID
    final = final_of(run, pid)
    if final is None:
        return f"{FINAL}/{pid}_final_vNN.mp4 is made ({FINISH.format(id=pid)})"
    rel = c.rel(run, final)
    try:
        found = _probe(final)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        return f"{rel} can be read by ffprobe ({exc}): make it again ({FINISH.format(id=pid)})"
    missing = []
    if (found["width"], found["height"]) != SIZE:
        missing.append(f"it is 1080×1920 (it is {found['width']}×{found['height']})")
    if found["vcodec"] != "h264":
        missing.append(f"its picture is H.264 (it is {found['vcodec']})")
    if found["acodec"] != "aac" or found["sample_rate"] != SAMPLE_RATE:
        heard = f"{found['acodec']} {found['sample_rate']} Hz" if found["acodec"] else "no sound"
        missing.append(f"its sound is AAC 48 kHz (it is {heard})")
    target, lufs = target_of(run, final), found["lufs"]
    if lufs is None or abs(lufs - target) > LUFS_SLACK:
        heard = _minus(round(lufs, 1)) if lufs is not None else "not measurable"
        missing.append(f"its loudness is {_minus(target)} LUFS ±1 (it is {heard}): make it again "
                       f"({FINISH.format(id=pid)}{' --asmr' if target != setting(run, 'lufs_target') else ''})")
    limit = setting(run, "upload_max_mb")
    upload = upload_of(final)
    if upload.is_file():
        if _size(upload) >= limit * MB:
            missing.append(f"its upload copy is under {limit:g} MB (it is {_size(upload) / MB:.1f} MB)")
    elif stepchecks.fresh(run, UPLOAD_OVER, FINAL, f"{pid}_final", "mp4") is not None:
        missing.append(f"it has an upload copy under {limit:g} MB (tm tool deliver upload --run <run> {rel})")
    if cover_of(run, pid, final) is None:
        latest = run.latest(KITS, f"cover_{pid}", "jpg")
        made_for = made_for_final(latest) if latest is not None else None
        stale = (f": the latest, {latest.name} was made for {made_for}" if made_for
                 else f": the latest, {latest.name} is older than it" if latest is not None else "")
        missing.append(f"it has its own cover JPG ({KITS}/cover_{pid}_vNN.jpg, from tm tool deliver cover --run <run> "
                       f"{KITS}/cover_{pid}_vNN.png after the final{stale})")
    return f"{rel} is ready: {'; '.join(missing)}" if missing else None


# --- a video in sections (G1) ------------------------------------------------------------------------

EDIT = "tm render video --run <run> --comp OrganicCaptions --props 03_wip/edit_vNN.props.json, then {finish}"
PARENTS_MAX = 8   # how far up the manifest's parents the edit's render is looked for (render, speed, finish, ...)


def _key(rel: str) -> str:
    """A run-relative path in any spelling ('\\', './', '//', any case) as one key (PR D review M2)."""
    return organic_qa.posix(rel).casefold()


def _rows(run: RunFolder) -> dict[str, dict]:
    """Each file's latest manifest row, by its path in any spelling (`_key`)."""
    return {_key(r["file"]): r for r in manifest.rows(run)}


def _lineage(rows: dict[str, dict], rel: str) -> list[str]:
    """`rel` and the files it was made from, up the manifest's parent column, as `_key`s."""
    out, key = [], _key(rel)
    while key and key not in out and len(out) <= PARENTS_MAX:
        out.append(key)
        key = _key((rows.get(key) or {}).get("parent", ""))
    return out


def edit_of(run: RunFolder, final: Path) -> tuple[str, dict] | None:
    """(the render, the props it was made from) of the edit a final was made from, or None."""
    rows = _rows(run)
    for key in _lineage(rows, c.rel(run, final)):
        row = rows.get(key)
        if row and row["model"] == organic_qa.RENDERED:
            try:
                params = json.loads(row["params"]) if row["params"] else {}
            except ValueError:
                return None
            props = params.get("props") if isinstance(params, dict) else None
            return (row["file"], props) if isinstance(props, dict) else None
    return None


def _section_outputs(run: RunFolder, pack: dict, sec: dict) -> tuple[set[str], str]:
    """(the files a section's segments may come from, case-folded; those files in words)."""
    sid, kind = str(sec["id"]), sec["type"]
    if kind in organic_pack.VIDEO_TYPES:
        made: set[str] = set()
        for st in pack["stages"]:
            for item in st["items"]:
                if st["stage"] != organic_pack.IMAGES_STAGE and item.get("model") in (sec["model"], organic_pack.UPSCALER):
                    made |= organic_specs.outputs(run, c.stem_of(item["name"]))[1]
        return {f.casefold() for f in made}, f"{sid}: a take of {sec['model']}"
    if kind == "animation":
        folder = run.path / organic_qa.WIP / sid / "renders"
        files = {c.rel(run, f).casefold() for f in folder.glob(f"{organic_qa.ANIM}_v*.mp4")} if folder.is_dir() else set()
        return files, f"{sid}: {organic_qa.WIP}/{sid}/renders/{organic_qa.ANIM}_vNN.mp4"
    if kind == "stills_motion":               # the render F2 took: the user's choice, else the latest (PR D M5)
        chosen = organic_qa.chosen_motion(run, sid)
        return ({chosen[0].casefold()} if chosen else set(),
                f"{sid}: its {' or '.join(render.MOTION_COMPS)} render ({chosen[0] if chosen else 'none made'})")
    return set(), f"{sid}: nothing"


def sections_gap(run: RunFolder) -> str | None:
    """The `sections_covered` step check (G1): the module docstring. Reads only."""
    pack = organic_pack.checked_pack(run)
    if pack is None or len(pack["sections"]) <= 1:
        return None
    pid = idea_id(run)
    if pid is None:
        return NO_ID
    final = final_of(run, pid)
    if final is None:
        return f"{FINAL}/{pid}_final_vNN.mp4 is made from the edit's render ({EDIT.format(finish=FINISH.format(id=pid))})"
    edit = edit_of(run, final)
    if edit is None:
        return (f"{c.rel(run, final)} is made from a render of the edit ({EDIT.format(finish=FINISH.format(id=pid))}): no "
                "tm render video is among the files it was made from")
    render_rel, props = edit
    secs = pack["sections"]
    outputs = [_section_outputs(run, pack, sec) for sec in secs]
    rows = _rows(run)
    segments = props.get("segments") if isinstance(props.get("segments"), list) else []
    fits_in = []
    for n, seg in enumerate(segments, 1):
        src = seg.get("src") if isinstance(seg, dict) else None
        made = set(_lineage(rows, src)) if isinstance(src, str) else set()
        fits_in.append({i for i, (files, _) in enumerate(outputs) if made & files})
        if not fits_in[-1]:
            return (f"the edit the final was made from ({render_rel}) cuts every segment from a section's outputs "
                    f"({'; '.join(words for _, words in outputs)}): segment {n} ({src}) is from no section")

    @functools.cache
    def fits(j: int, i: int) -> bool:   # segments[j:] cover sections[i:], segment j in section i
        if i not in fits_in[j]:
            return False
        if j == len(fits_in) - 1:
            return i == len(secs) - 1
        return fits(j + 1, i) or (i + 1 < len(secs) and fits(j + 1, i + 1))

    if fits_in and fits(0, 0):
        return None
    said = ", ".join("/".join(str(secs[i]["id"]) for i in sorted(f)) for f in fits_in) or "none"
    return (f"the edit the final was made from ({render_rel}) cuts the sections in order, "
            f"{' → '.join(str(s['id']) for s in secs)}, each from its own outputs "
            f"({'; '.join(words for _, words in outputs)}): its segments are from {said}")
