"""Organic video's take QA rubric, the rubric picks and the A–Z log (OV9, OV10).

`tm tool take_qa` measures a generated take and writes `<take dir>/qa/<stem>_qa_vNN.json` (`qa_file` finds the
latest): {take, transcript, match, words, speech_seconds, wps, tail_silence, cuts, cut_offsets, lufs, peak,
contact_sheet, lines, heard_by}. Here:

- `match(script, words)`: the share of the script's words Whisper heard, in order (lower-case, punctuation
  dropped, Polish and other letters kept as they are): the longest common subsequence ÷ the script's word count.
  `script_lines` and `line_hits` split that alignment by line (issue #94): the share of each line heard, and where.
- `rubric_takes(qa, cfg, *, speech=True)`: the takes rubric (PLAYBOOK.md OV9) against the run's `qa.*` thresholds
  (defaults `organic_config.DEFAULTS`). `fails`: the transcript under `qa.transcript_min` (when local Whisper,
  even on the levelled take, did not hear a whole line, the fail says the line is not confirmed missing: check it
  with Scribe first; issue #94), the loudness outside
  `qa.lufs_usable`; `findings`: a cut more than `qa.cut_flag_s` off its bracket, a bracket with no cut, a line
  Scribe did not hear whole (missing from the take), a slow pace (each a sentence of the string table `organic.qa.*`: English here, `rubric_words` in a page's language);
  `speed`: what a slow take (under `qa.wps_min`) is sped up to in the edit, `min(qa.speed_max, 2.9 / wps)`,
  before any redo is suggested. The transcript and pace rules apply only to a take that carries the spoken lines
  (`speech`: the pack's route speaks in the model, `SPEECH_IN_TAKE`). A narrated or silent take gets its voice in
  the edit, so it is judged on its cuts and its loudness, and a take with no sound at all does not fail.
- `pick(run, stage, name, file, reason, by)` (`tm organic pick`): one row of the A–Z log, `03_wip/az_log.jsonl`
  (`organic_specs.AZ_FIELDS`), appended through `library.append_jsonl`, plus a manifest row for the file:

      {"stage": "images" | "takes", "name": <pack item>, "file": "03_wip/<file>", "rubric": {...},
       "reason": "<why this one>", "by": "rule" | "user", "at": "<ISO time>"}

  The file is an output of the item's latest Replicate record (`03_wip/<item stem>_vNN.run.json`); any other
  file, an earlier take's included, is refused. An images pick names an image item of the checked pack; its
  rubric is the criteria it was judged against (`IMAGE_RUBRIC`; the agent's judgement is the reason). A takes
  pick names a video item and a take with a QA file; its rubric is the take's latest QA, its measures and
  `rubric_takes`. A take that fails the rubric is never picked by rule: the video check-in's `fails_qa` holds the
  run for the user, and a user's pick of that take (`--by user`) needs a `video fails_qa` decision recorded after
  its latest QA.
- A pick counts (`current`) while it was made after the pack check that last changed its item
  (`organic_specs.item_checked_at`), it names an output of the item's
  latest record, and, for a take, it carries that take's latest QA. The latest row of an item, by time, is its pick.
  An image's picks are also the accepts on the images check-in page (`organic_specs.image_rows`); the generation
  guard (`organic_specs.picked`) reads the same picks by the same rule.
- An animation (`organic_pack.animated`: the pack's id, or an animation section's) has its storyboard check-in at
  F1 (OV9: style frame or storyboard -> full render). `tm organic storyboard` draws `03_wip/<item>/storyboard_vNN/`
  (`panel_NN.png`, `sheet.png`); its pick (stage `storyboard`, `name` the item, `file` the sheet) is an accept on the
  images check-in page (`organic_specs.page_image_rows(run, STORYBOARD)`) or `tm organic pick --stage storyboard`
  (by rule or the user's, against `STORYBOARD_RUBRIC`). It counts by the same rule: made after the pack check that
  last changed what the storyboard shows (`organic_pack.storyboard_key`: its scenes and on-screen text, its style, its
  section; never the spoken words alone, issue #90), naming the item's latest storyboard; a later
  drop or redo on the page ends it. `tm organic animate` draws the full animation only from a storyboard whose pick
  counts (`accepted_storyboard`), into `03_wip/<item>/renders/anim_vNN.mp4`, its manifest row naming that sheet and
  that pick (`pick_mark`): F2 takes the animation only while the item's current storyboard pick is that same pick, so
  a sheet picked again after a script change needs a new animation (Task 19 review I1).
- Stills with motion graphics (`organic_pack.stills`: the pack's id, or a stills section's) are drawn at F2 by a free
  `tm render video` of a motion-graphics composition (`render.MOTION_COMPS`; `motion_renders`): its pictures
  (QuizGrid's `options[].img`, a ranking's `items[].src`) show every generated item's current pick (the cards, or a
  ranking's takes), and nothing else the pack made; a picture the pack did not make only when it takes the user's own
  (an item with no model), and never one of the check-in pages' (`03_wip/gates/`, PR D review I1).
- An upscale (the pack's upscale-stage item, `organic_pack.UPSCALER`, issue #90) is an automatic step after the user
  accepted the take: `upscale_check` (`tm organic upscale`) finds the item's latest output and the accepted take it
  was made from (the current takes pick its record names as input), checks only what an upscale may change (the
  1080p size with the take's shape, the frame rate, and the sound: there as in the take, as long, as loud, within
  `UPSCALE_SLACK`), writes that technical QA as the output's QA file (`kind: "upscale"`) and, when it passes, logs the
  output's pick by rule. `tm organic pick` refuses an upscale item: it is never a take to judge.
- Step checks: `images_gap` (`images_picked`, F1: each image item's pick, and each animated item's storyboard) and
  `takes_gap` (`takes_checked`, F2: each take's pick, each animated item's animation drawn from its current
  storyboard, and the latest motion-graphics render from the current picks for stills). Both read only.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from tm import (audience, config, i18n, library, manifest, organic_config, organic_pack, organic_specs, render,
                state)
from tm.playbooks import ORGANIC_VIDEO
from tm.r2 import run_config
from tm.review import VIDEO_EXT
from tm.runfolder import RunFolder
from tm.stops import AGAIN, AGAIN_SENTENCE, Stop
from tm.tools import _common as c

AZ_LOG = organic_specs.AZ_LOG
WIP = organic_specs.WIP
IMAGES, TAKES, STORYBOARD = "images", "takes", "storyboard"
STAGES = (IMAGES, TAKES, STORYBOARD)
BY = ("rule", "user")
IMAGE_RUBRIC = ("realism", "consistency", "safe_zone", "no_text")   # PLAYBOOK.md OV9, the images rubric
# A storyboard is judged on the style kept (the topic's setting, the style's rendering), the same characters in every
# panel, text and key action above y 1260 in 9:16, and a panel per beat of the voiceover (references/animation-styles.md).
STORYBOARD_RUBRIC = ("style", "consistency", "safe_zone", "beats")
BOARD = re.compile(r"^storyboard_v(\d+)$")       # 03_wip/<item>/storyboard_vNN/
ANIM = "anim"                                     # 03_wip/<item>/renders/anim_vNN.mp4
ANIMATE = "tm organic animate"                    # the manifest source of an animation render
SPEECH_IN_TAKE = ("h3_native", "h3_narrator")   # the routes whose spoken lines are in the generated take
BRISK_WPS = 2.9   # the pace a slow take is sped up to (round 43): speed = 2.9 / wps, at most qa.speed_max
QA_TOOL = ("tm tool take_qa --run <run> <take> --lang <audio language> [--script <its lines, or the pack>] "
           "[--brackets <cuts>]")
UPSCALE_QA = "upscale"     # an upscale's technical QA (`upscale_check`), the `kind` of its QA file
UPSCALE_TOOL = "tm organic upscale --run <run> --name <the upscale item>"
UPSCALE_SLACK = {"size": 0.99, "shape": 0.01, "fps": 0.01, "seconds": 0.1, "lu": 1.0}   # what an upscale may move


# --- the measures --------------------------------------------------------------------------------------

def _plain(text: str) -> list[str]:
    """Words lower-cased, with punctuation dropped and every letter kept (composed, so ś is one letter)."""
    text = unicodedata.normalize("NFC", text).lower()
    return "".join("" if unicodedata.category(ch).startswith("P") else ch for ch in text).split()


def words_of(transcript: dict) -> list[str]:
    """The words of a `tm.tools.transcribe` transcript, in order."""
    return [w["word"] for s in transcript.get("segments") or [] for w in s.get("words") or []]


def match(script: str, words: list[str]) -> float:
    """The longest common subsequence of the script's words and the heard words ÷ the script's word count."""
    want, heard = _plain(script), _plain(" ".join(words))
    if not want:
        raise ValueError("The script has no words to match the take against.")
    row = [0] * (len(heard) + 1)
    for w in want:
        prev = 0   # the cell up and to the left
        for j, h in enumerate(heard, 1):
            prev, row[j] = row[j], prev + 1 if w == h else max(row[j], row[j - 1])
    return row[-1] / len(want)


_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def script_lines(script: str) -> list[str]:
    """The script's lines: each line of the text, split again after a sentence's end (. ! ? …); lines with no
    words are left out."""
    out = []
    for line in (script or "").splitlines():
        out += [part.strip() for part in _SENTENCE_END.split(line) if _plain(part)]
    return out


def line_hits(lines: list[str], words: list[dict]) -> list[dict]:
    """Which of each line's words were heard, from the same alignment as `match` (the longest common subsequence of
    the lines' words, in order, and the heard words). One {heard, first, last} per line: `heard` the share of its
    words heard (0 to 1), `first` and `last` the indexes in `words` of its first and last heard word (None when
    none was heard)."""
    want = [(tok, n) for n, line in enumerate(lines) for tok in _plain(line)]
    heard = [(tok, j) for j, w in enumerate(words) for tok in _plain(str(w.get("word", "")))]
    rows, cols = len(want), len(heard)
    table = [[0] * (cols + 1) for _ in range(rows + 1)]
    for i in range(rows - 1, -1, -1):
        for k in range(cols - 1, -1, -1):
            table[i][k] = (table[i + 1][k + 1] + 1 if want[i][0] == heard[k][0]
                           else max(table[i + 1][k], table[i][k + 1]))
    got: dict[int, list[int]] = {}
    i = k = 0
    while i < rows and k < cols:
        if want[i][0] == heard[k][0] and table[i][k] == table[i + 1][k + 1] + 1:
            got.setdefault(want[i][1], []).append(heard[k][1])
            i, k = i + 1, k + 1
        elif table[i + 1][k] >= table[i][k + 1]:
            i += 1
        else:
            k += 1
    out = []
    for n, line in enumerate(lines):
        found, total = got.get(n, []), len(_plain(line))
        out.append({"heard": round(len(found) / total, 3) if total else 1.0,
                    "first": found[0] if found else None, "last": found[-1] if found else None})
    return out


def _setting(cfg: dict | None, key: str):
    found = config.get(cfg, f"qa.{key}") if cfg else None
    return found if found is not None else organic_config.DEFAULTS["qa"][key]


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


_Q = "organic.qa."   # the rubric's sentences in the string table (issue #3): English here, a page's language there
LOCAL, SCRIBE = "whisper", "scribe"   # what heard a QA's words (`heard_by`): local Whisper, or ElevenLabs Scribe


def short_lines(qa: dict, heard_by: str) -> list[dict]:
    """The QA's lines not fully heard, when its words came from `heard_by` (a QA file without `lines`, written
    before issue #94, has none)."""
    if qa.get("heard_by") != heard_by:
        return []
    return [line for line in qa.get("lines") or [] if isinstance(line, dict) and _number(line.get("heard"))
            and line["heard"] < 1 and isinstance(line.get("line"), str)]


def _quoted(lines: list[dict]) -> str:
    return ", ".join(f"“{line['line']}”" for line in lines)


def _rubric(qa: dict, cfg: dict | None, speech: bool) -> tuple[list, list, float | None]:
    """The takes rubric as (fails, findings, speed), each fail and finding a key of the string table and its
    values. An upscale's QA (`upscale_check`) holds its own technical fails."""
    if qa.get("kind") == UPSCALE_QA:
        return [(f["key"], f.get("values") or {}) for f in qa.get("fails") or [] if isinstance(f, dict)], [], None
    fails, findings = [], []
    if speech:
        least = _setting(cfg, "transcript_min")
        score = qa.get("match")
        quiet = short_lines(qa, LOCAL)
        if not _number(score) or score < least:
            if quiet and _number(score):   # not missing yet: Whisper misses quiet lines (issue #94)
                fails.append((_Q + "fail_unconfirmed", {"score": f"{score:.0%}", "least": f"{least:.0%}",
                                                        "lines": _quoted(quiet)}))
            else:
                fails.append((_Q + "fail_transcript", {"score": f"{score:.0%}", "least": f"{least:.0%}"})
                             if _number(score) else (_Q + "fail_no_transcript", {"least": f"{least:.0%}"}))
        for line in short_lines(qa, SCRIBE):
            findings.append((_Q + "finding_line_missing", {"line": line["line"], "heard": f"{line['heard']:.0%}"}))
    low, high = _setting(cfg, "lufs_usable")
    lufs = qa.get("lufs")
    if _number(lufs) and not low <= lufs <= high:
        fails.append((_Q + "fail_loudness", {"lufs": f"{lufs:.1f}", "low": f"{low:g}", "high": f"{high:g}"}))
    elif not _number(lufs) and speech:
        fails.append((_Q + "fail_no_sound", {}))
    flag = _setting(cfg, "cut_flag_s")
    for o in qa.get("cut_offsets") or []:
        if o.get("cut") is None:
            findings.append((_Q + "finding_no_cut", {"at": f"{o['bracket']:g}"}))
        elif abs(o["offset"]) > flag:
            findings.append((_Q + "finding_cut_off", {"cut": f"{o['cut']:g}", "off": f"{abs(o['offset']):.2f}",
                                                       "bracket": f"{o['bracket']:g}", "flag": f"{flag:g}"}))
    speed = None
    wps = qa.get("wps")
    if speech and _number(wps) and 0 < wps < _setting(cfg, "wps_min"):
        speed = round(min(_setting(cfg, "speed_max"), BRISK_WPS / wps), 2)
        findings.append((_Q + "finding_slow", {"wps": f"{wps:g}", "least": f"{_setting(cfg, 'wps_min'):g}",
                                               "speed": f"{speed:g}"}))
    return fails, findings, speed


def rubric_takes(qa: dict, cfg: dict | None, *, speech: bool = True) -> dict:
    """{fails, findings, speed} of a take's QA (the module docstring), in English. `speech`: the take carries the
    spoken lines."""
    fails, findings, speed = _rubric(qa, cfg, speech)
    tr = i18n.translator(i18n.ENGLISH)
    return {"fails": [tr(k, **v) for k, v in fails], "findings": [tr(k, **v) for k, v in findings], "speed": speed}


def rubric_words(qa: dict, cfg: dict | None, lang: str | i18n.Translator, *, speech: bool = True) -> dict:
    """`rubric_takes` with its fails and findings in `lang` (a page's language), for the check-in pages."""
    fails, findings, speed = _rubric(qa, cfg, speech)
    tr = lang if isinstance(lang, i18n.Translator) else i18n.translator(lang)
    return {"fails": [tr(k, **v) for k, v in fails], "findings": [tr(k, **v) for k, v in findings], "speed": speed}


def speaks(pack: dict) -> bool:
    """The pack's takes carry the spoken lines (its route speaks in the model)."""
    return pack["speech"]["route"] in SPEECH_IN_TAKE


def qa_stage(run: RunFolder, take: Path) -> str:
    """The run-relative folder of a take's QA files: `<take dir>/qa`."""
    return f"{c.rel(run, Path(take).parent)}/qa"


def qa_file(run: RunFolder, take: Path) -> Path | None:
    """The latest QA file of a take, `<take dir>/qa/<stem>_qa_vNN.json`, or None."""
    take = Path(take)
    try:
        stage = qa_stage(run, take)
    except ValueError:   # outside the run
        return None
    return run.latest(stage, f"{take.stem}_qa", "json")


def read_qa(run: RunFolder, path: Path) -> dict:
    """A QA file's object; one that is not a JSON object is a Stop."""
    rel = c.rel(run, path)
    try:
        qa = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        qa = exc
    if not isinstance(qa, dict):
        why = qa if isinstance(qa, Exception) else "not a JSON object"
        raise Stop(f"{rel} cannot be read ({why}): run the take's QA again ({QA_TOOL}); nothing was logged; {AGAIN}.")
    return qa


# --- picks -----------------------------------------------------------------------------------------------

def _pack(run: RunFolder) -> dict:
    pack = organic_pack.checked_pack(run)
    if pack is None:
        raise Stop(f"{organic_specs.NO_PACK} {AGAIN_SENTENCE}")
    return pack


def _wanted(pack: dict, video: bool) -> list[dict]:
    """The items the pack generates (a model) of one kind: video, or images."""
    return [item for st in pack["stages"] for item in st["items"]
            if item.get("model") and organic_specs.is_video(pack, item) == video]


_when = organic_specs.when
_outputs = organic_specs.outputs
_checked_at = organic_specs.checked_at


def _modified(path: Path) -> datetime:
    """When a file was written, to the second (decisions are recorded to the second)."""
    return datetime.fromtimestamp(int(path.stat().st_mtime), timezone.utc)


def _fails_qa_after(run: RunFolder, since: datetime) -> bool:
    """A `video fails_qa` decision is recorded at or after `since`."""
    for d in state.load(run).decisions:
        when = _when(d.get("at"))
        if d.get("checkin") == "video" and d.get("choice") == "fails_qa" and when is not None and when >= since:
            return True
    return False


def current(run: RunFolder, row: dict, *, checked_at: datetime | None) -> str | None:
    """Why a pick no longer counts (the module docstring), or None while it does. Reads only."""
    if row.get("stage") == STORYBOARD:
        return _board_counts(run, row, checked_at)
    why = organic_specs.counts(run, row, checked=checked_at)
    if why:
        return why
    if row.get("stage") == TAKES:
        qa = qa_file(run, run.path / row["file"])
        if qa is None:
            return f"{row['file']} has no QA ({QA_TOOL})"
        if (row.get("rubric") or {}).get("qa") != c.rel(run, qa):
            return f"{row['file']} has a newer QA, {c.rel(run, qa)}: pick it again on that QA"
    return None


def picks(run: RunFolder, stage: str) -> dict[str, dict]:
    """The latest row of each item picked at `stage`, by the item's stem (counting or not: see `current`); an image's
    picks include the accepts on the images check-in page."""
    rows = (organic_specs.image_rows(run) if stage == IMAGES else storyboard_rows(run) if stage == STORYBOARD
            else [r for r in organic_specs.az_rows(run) if r.get("stage") == stage])
    return organic_specs.latest_picks(rows)


# --- the storyboard of an animation --------------------------------------------------------------------------

def animation_item(pack: dict, name: str) -> str:
    """The pack's animated item called `name` (in any case), in the pack's spelling; a Stop names the others."""
    items = organic_pack.animated(pack)
    found = next((i for i in items if i.lower() == str(name).strip().lower()), None)
    if found is None:
        raise Stop(f"{name} is not an animation of the checked pack (its animated items: {', '.join(items) or 'none'}): "
                   "a storyboard and an animation are made for the pack's id when the whole video is an animation, "
                   f"else for an animation section's id; nothing was done; {AGAIN}.")
    if why := organic_pack.id_gap(found):   # a pack checked before ids were held to it (PR D review I2)
        raise Stop(f"The animation {why}, and it would name the folder 03_wip/<item>/: nothing was written. Give it "
                   "such an id in a new version of the pack and check it again (tm organic pack check --stage recipe, "
                   f"then --stage pack); {AGAIN}.")
    return found


def storyboards(run: RunFolder, item: str) -> list[Path]:
    """The item's drawn storyboards, `03_wip/<item>/storyboard_vNN/` holding a `sheet.png`, oldest first."""
    folder = run.path / WIP / item
    if not folder.is_dir():
        return []
    found = sorted((int(m.group(1)), d) for d in folder.iterdir()
                   if d.is_dir() and (m := BOARD.match(d.name)) and (d / "sheet.png").is_file())
    return [d for _, d in found]


def latest_storyboard(run: RunFolder, item: str) -> str | None:
    """The run-relative sheet of the item's latest storyboard, or None."""
    found = storyboards(run, item)
    return c.rel(run, found[-1] / "sheet.png") if found else None


def storyboard_rows(run: RunFolder) -> list[dict]:
    """Every storyboard pick (the A–Z log's and the images page's accepts, drops and redos), oldest first."""
    rows = [r for r in organic_specs.az_rows(run) if r.get("stage") == STORYBOARD]
    rows += organic_specs.page_image_rows(run, STORYBOARD)
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(rows, key=lambda r: _when(r.get("read_at") or r.get("at")) or oldest)


def _board_counts(run: RunFolder, row: dict, checked_at: datetime | None) -> str | None:
    """Why a storyboard pick no longer counts, or None (the module docstring)."""
    file = str(row["file"]).replace("\\", "/")
    since = organic_specs.item_checked_at(run, organic_pack.storyboard_key(row["name"]), checked_at)
    made = _when(row.get("at"))
    if since is not None and (made is None or made < since):
        return (f"it was made before the pack was checked again with other scenes, on-screen text or style ({file}); "
                "a change to the spoken words alone keeps it")
    latest = latest_storyboard(run, row["name"])
    if file != latest:
        return f"{file} is not the item's latest storyboard ({latest or 'none drawn'})"
    return None


def pick_mark(row: dict) -> dict:
    """What names one pick (its file, when it was made, when it was read from a page): a render made from it records
    this mark, and counts only while the item's current pick has the same one (Task 19 review I1)."""
    return {"file": row.get("file"), "at": row.get("at"), "read_at": row.get("read_at")}


def _board_gap(run: RunFolder, item: str, done: dict[str, dict], checked_at: datetime | None) -> str | None:
    row = done.get(c.stem_of(item))
    return "its storyboard is not accepted" if row is None else current(run, row, checked_at=checked_at)


def accepted_storyboard(run: RunFolder, item: str) -> dict:
    """The item's storyboard pick that counts (`tm organic animate` draws only from it); else a Stop that says how
    the storyboard is accepted."""
    pack = _pack(run)
    item = animation_item(pack, item)
    why = _board_gap(run, item, picks(run, STORYBOARD), _checked_at(run))
    if why:
        sheet = latest_storyboard(run, item)
        raise Stop(f"The full animation of {item} is drawn only from an accepted storyboard, and {why}. "
                   + ("Draw it first (tm organic storyboard --run <run> --item <item> --page <its page>), then"
                      if sheet is None else f"Its latest is {sheet}:")
                   + " show it on the images check-in page (tm organic page gate --gate images) and read the user's "
                   "decisions, or, where the images check-in goes by rule, pick it against the storyboard rubric (tm "
                   "organic pick --stage storyboard --name <item> --file <its sheet.png> --reason \"<why>\"). Nothing "
                   f"was drawn; {AGAIN}.")
    return picks(run, STORYBOARD)[c.stem_of(item)]


def animation_of(run: RunFolder, item: str) -> tuple[str, dict] | None:
    """The item's latest animation render (`03_wip/<item>/renders/anim_vNN.mp4`) and its manifest params, or None."""
    latest = run.latest(f"{WIP}/{item}/renders", ANIM, "mp4")
    if latest is None:
        return None
    rel = c.rel(run, latest)
    for row in reversed(manifest.rows(run)):
        if row["source"] == ANIMATE and row["file"] == rel:
            try:
                params = json.loads(row["params"]) if row["params"] else {}
            except ValueError:
                params = {}
            return rel, params if isinstance(params, dict) else {}
    return rel, {}


RENDERED = "remotion render"                      # the manifest model of a `tm render video` output
CHECK_IN = f"{WIP}/gates/"                        # the check-in pages' data and thumbnails (organic_pages.gate.DATA)


def _iso(when: datetime | None) -> str | None:
    return when.isoformat(timespec="seconds") if when is not None else None


def made_under(run: RunFolder, comp: str, props: dict) -> dict:
    """What a `tm render` output of an organic run is made under, kept in its manifest row (`made_under`, PR D review
    M1): `at`, when it was made; `since`, each stills item's pick-currency time (`organic_specs.item_checked_at` of its
    `organic_pack.motion_key`); `picks`, the pick mark (`pick_mark`) of each picture or clip it shows that is an item's
    pick, by its case-folded path. A pack or log that cannot be read (a Stop) leaves `since` and `picks` empty, so the
    render is made and recorded, and F2 asks for it again once they are mended."""
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        pack = organic_pack.checked_pack(run)
        if pack is None:
            return {"at": at, "since": {}, "picks": {}}
        checked = _checked_at(run)
        since = {item: _iso(organic_specs.item_checked_at(run, organic_pack.motion_key(item), checked))
                 for item in organic_pack.stills(pack)}
        shown = {f.casefold() for f in motion_files(comp, props)} if comp in render.MOTION_COMPS else set()
        marks = {posix(row["file"]).casefold(): pick_mark(row) for stage in (IMAGES, TAKES)
                 for row in picks(run, stage).values() if posix(row["file"]).casefold() in shown}
    except Stop:
        return {"at": at, "since": {}, "picks": {}}
    return {"at": at, "since": since, "picks": marks}


def motion_renders(run: RunFolder) -> list[tuple[str, str, dict, dict]]:
    """Every motion-graphics render still in the run (`tm render video --comp QuizGrid|RankingList|RankingSplit`),
    oldest first: (its run-relative file, the composition, the props it was rendered from, and what it was made under
    (`made_under`), as its manifest row keeps them)."""
    out = []
    for row in manifest.rows(run):
        if row["model"] != RENDERED or not row["params"]:
            continue
        try:
            params = json.loads(row["params"])
        except ValueError:
            continue
        if (isinstance(params, dict) and params.get("composition") in render.MOTION_COMPS
                and (run.path / row["file"]).is_file()):
            props, under = params.get("props"), params.get("made_under")
            out.append((row["file"], params["composition"], props if isinstance(props, dict) else {},
                        under if isinstance(under, dict) else {}))
    return out


def posix(path: str) -> str:
    """A run-relative path as the engine writes it: '/' between parts, no '.' or empty part (`./03_wip//x`)."""
    text = str(path).replace("\\", "/")
    return PurePosixPath(text).as_posix() if text else ""


def motion_files(comp: str, props: dict) -> list[str]:
    """The pictures (QuizGrid) or clips (a ranking) a motion-graphics render shows, run-relative with '/'."""
    key, field = ("options", "img") if comp == "QuizGrid" else ("items", "src")
    group = props.get(key)
    return [posix(x[field]) for x in group if isinstance(x, dict) and isinstance(x.get(field), str)] \
        if isinstance(group, list) else []


MOTION, VIDEO_PAGE = "motion", "gate_video"        # a stills item's renders on the video check-in page (organic_gates)


def chosen_motion(run: RunFolder, item: str) -> tuple[str, str, dict, dict] | None:
    """The motion-graphics render (as `motion_renders` gives it) F2 and the edit take for the stills item (PR D review
    M5): the user's accept on the video check-in page, its choice, while that page was built (or the chat read) no
    earlier than the latest render was made (`made_under.at`), so the page showed it; else the latest render. A later
    drop or redo on the page ends the choice. None without a render."""
    renders = motion_renders(run)
    if not renders:
        return None
    latest = renders[-1]
    row = organic_specs.latest_picks(organic_specs.page_image_rows(run, MOTION, page=VIDEO_PAGE)).get(c.stem_of(item))
    if row is None:
        return latest
    chosen = next((r for r in reversed(renders) if r[0].casefold() == posix(row["file"]).casefold()), None)
    shown, made = _when(row.get("at")), _when(latest[3].get("at"))
    if chosen is None or shown is None or (made is not None and shown < made):
        return latest
    return chosen


def _own(pack: dict, video: bool) -> bool:
    """The pack takes the user's own pictures (an images item with no model) or, for a ranking, their own clips."""
    return any(not item.get("model") and (st["stage"] != organic_pack.IMAGES_STAGE) == video
               for st in pack["stages"] for item in st["items"])


def _are(files: list[str]) -> str:
    return f"{', '.join(files)} {'is' if len(files) == 1 else 'are'}"


def _motion_gap(run: RunFolder, pack: dict, item: str, checked_at: datetime | None) -> str | None:
    """Why the stills item is not drawn yet (PR D review I1), or None: no motion-graphics render; or the one it takes
    (`chosen_motion`: the user's choice on the video page, else the latest) does
    not show every generated item's current pick (a QuizGrid's cards, a ranking's takes), shows a generated file that
    is not its item's current pick, shows a file the pack did not make while it takes none of the user's own, or shows
    a check-in page's own picture (`CHECK_IN`, the evidence thumbnails); or it was made under an earlier pack check of
    the item, or before a pick it shows was made again (`made_under`, PR D review M1)."""
    chosen = chosen_motion(run, item)
    if chosen is None:
        return "it has no render"
    file, comp, props, under = chosen
    video = comp != "QuizGrid"
    shown = motion_files(comp, props)
    folded = {f.casefold() for f in shown}
    made: set[str] = set()
    for wanted in _wanted(pack, False) + _wanted(pack, True):
        made |= {f.casefold() for f in _outputs(run, c.stem_of(wanted["name"]))[1]}
    current_picks: dict[str, str] = {}   # item stem -> its current pick, case-folded
    rows: dict[str, dict] = {}
    for stage in (IMAGES, TAKES):
        for stem, row in picks(run, stage).items():
            if current(run, row, checked_at=checked_at) is None:
                current_picks[stem], rows[stem] = posix(row["file"]).casefold(), row
    gaps = []
    since = _iso(organic_specs.item_checked_at(run, organic_pack.motion_key(item), checked_at))
    if (under.get("since") or {}).get(item) != since:
        gaps.append("it was rendered before the pack was checked again: render it again")
    marks = under.get("picks") or {}
    again = [w["name"] for w in _wanted(pack, video) if (stem := c.stem_of(w["name"])) in rows
             and current_picks[stem] in folded and marks.get(current_picks[stem]) != pick_mark(rows[stem])]
    if again:
        gaps.append(f"it was rendered before {', '.join(again)} {'was' if len(again) == 1 else 'were'} picked again: "
                    "render it again")
    unshown = [w["name"] for w in _wanted(pack, video) if current_picks.get(c.stem_of(w["name"])) not in folded]
    if unshown:
        gaps.append(f"it does not show the current pick of {', '.join(unshown)}")
    gates = [f for f in shown if f.casefold().startswith(CHECK_IN.casefold())]
    if gates:
        gaps.append(f"{_are(gates)} the check-in pages' own (an evidence thumbnail), never the video's")
    stale = [f for f in shown if f.casefold() in made and f.casefold() not in current_picks.values()]
    if stale:
        gaps.append(f"{_are(stale)} not the current pick")
    foreign = [f for f in shown if f.casefold() not in made and f not in gates]
    if foreign and not _own(pack, video):
        what = "clips" if video else "pictures"
        gaps.append(f"{_are(foreign)} not made by the pack, and it takes none of the user's own {what} (an item with no "
                    "model)")
    return f"{file}: {'; '.join(gaps)}" if gaps else None


def pick(run: RunFolder, stage: str, name: str, file: str, reason: str, by: str = "rule") -> dict:
    """Log one pick (the module docstring). Returns {row, qa}; a pick the rules refuse is a Stop."""
    if state.load(run).playbook != ORGANIC_VIDEO:
        raise ValueError("Picks are for organic video runs.")
    if stage not in STAGES or by not in BY:
        raise ValueError(f"A pick's stage is one of {', '.join(STAGES)}, and its by one of {', '.join(BY)}.")
    if not reason.strip():
        raise ValueError("Give the reason for the pick in words (--reason): the A–Z log keeps why each was chosen.")
    path, rel = audience.inside(run, file)          # ValueError: not a file of this run
    pack = _pack(run)
    if stage == STORYBOARD:
        return _pick_storyboard(run, pack, name, rel, reason, by)
    if (up := upscale_item(pack, name)) is not None:
        raise Stop(f"{up['name']} is the upscale of the accepted take, an automatic step: it is checked for what an "
                   f"upscale may change and picked by rule with {UPSCALE_TOOL}, never picked as a take; nothing was "
                   f"logged; {AGAIN}.")
    video = stage == TAKES
    found = organic_specs.item_of(pack, c.stem_of(name))
    kinds = ", ".join(i["name"] for i in _wanted(pack, video)) or "none"
    if found is None or not found[1].get("model") or organic_specs.is_video(pack, found[1]) != video:
        raise Stop(f"{name} is not {'a video' if video else 'an image'} item of the checked pack (its "
                   f"{'video' if video else 'image'} items: {kinds}): pick each {'take' if video else 'image'} "
                   f"under the item that made it; nothing was logged; {AGAIN}.")
    item = found[1]
    suffixes = sorted(VIDEO_EXT) if video else organic_specs.IMAGE_SUFFIXES
    if path.suffix.lower() not in suffixes:
        raise Stop(f"{rel} is not {'a video' if video else 'an image'} ({', '.join(suffixes)}): pick the file "
                   f"{item['name']} made; nothing was logged; {AGAIN}.")
    latest, every = _outputs(run, c.stem_of(item["name"]))
    if rel not in latest:
        made = ", ".join(sorted(latest)) or "nothing yet"
        why = ("is from an earlier take of it, made again since" if rel in every
               else "is not a file it made (an output of its Replicate records)")
        raise Stop(f"{rel} {why}: pick among {item['name']}'s latest outputs ({made}); nothing was logged; "
                   f"{AGAIN}.")
    qa_rel = None
    if video:
        qa_path = qa_file(run, path)
        if qa_path is None:
            raise Stop(f"{rel} has no QA yet, and a take is picked on its QA: run {QA_TOOL} first; nothing was "
                       f"logged; {AGAIN}.")
        qa_rel = c.rel(run, qa_path)
        qa = read_qa(run, qa_path)
        found_rubric = rubric_takes(qa, run_config(run), speech=speaks(pack))
        if found_rubric["fails"]:
            shown = "; ".join(found_rubric["fails"] + found_rubric["findings"])
            if by == "rule":
                raise Stop(f"{rel} fails the takes rubric ({shown}), and a take that fails is never picked by rule: "
                           f"decide `video fails_qa` and show the findings to the user (tm decide video fails_qa "
                           f"--run <run>); if they keep it, log their pick with --by user. Nothing was logged; "
                           f"{AGAIN}.")
            if not _fails_qa_after(run, _modified(qa_path)):
                raise Stop(f"{rel} fails the takes rubric ({shown}). The user keeps a failing take only after "
                           f"`video fails_qa` is decided on its latest QA ({qa_rel}) and they have seen the "
                           f"findings: decide it first (tm decide video fails_qa --run <run>). Nothing was logged; "
                           f"{AGAIN}.")
        rubric = {"qa": qa_rel, **{k: qa.get(k) for k in ("match", "wps", "lufs", "peak", "cuts")}, **found_rubric}
    else:
        rubric = {"against": list(IMAGE_RUBRIC)}
    row = {"stage": stage, "name": item["name"], "file": rel, "rubric": rubric, "reason": reason.strip(), "by": by,
           "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    organic_specs.az_rows(run)   # a damaged log is mended first, so a pick never lands after an unreadable line
    library.append_jsonl(run.path / AZ_LOG, [row])
    manifest.record(run, rel, rel.split("/", 1)[0], f"{stage} pick ({by})", parent=qa_rel,
                    params={"item": item["name"], "reason": row["reason"]}, cost="0")
    return {"row": row, "qa": qa_rel}


def _pick_storyboard(run: RunFolder, pack: dict, name: str, rel: str, reason: str, by: str) -> dict:
    item = animation_item(pack, name)
    latest = latest_storyboard(run, item)
    if rel != latest:
        raise Stop(f"{rel} is not the latest storyboard of {item} ("
                   + (f"that is {latest}" if latest else "none is drawn yet: tm organic storyboard") + "): pick the "
                   f"sheet.png of its latest storyboard; nothing was logged; {AGAIN}.")
    row = {"stage": STORYBOARD, "name": item, "file": rel, "rubric": {"against": list(STORYBOARD_RUBRIC)},
           "reason": reason.strip(), "by": by, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    organic_specs.az_rows(run)   # a damaged log is mended first, so a pick never lands after an unreadable line
    library.append_jsonl(run.path / AZ_LOG, [row])
    manifest.record(run, rel, rel.split("/", 1)[0], f"{STORYBOARD} pick ({by})", params={"item": item,
                    "reason": row["reason"]}, cost="0")
    return {"row": row, "qa": None}


# --- the upscale of an accepted take (issue #90) ---------------------------------------------------------------

def upscale_item(pack: dict, name: str) -> dict | None:
    """The pack's upscale-stage item named `name` (any case, as its stem), or None."""
    stem = c.stem_of(name)
    return next((item for st in pack["stages"] if st["stage"] == organic_pack.UPSCALE_STAGE for item in st["items"]
                 if item.get("model") == organic_pack.UPSCALER and c.stem_of(item["name"]) == stem), None)


def _measure(path: Path) -> dict:
    from tm.tools import take_qa   # heavy imports inside

    found = c.probe(path)
    lufs, _ = take_qa.loudness(path) if found.get("has_audio") else (None, None)
    return {"width": found.get("width"), "height": found.get("height"), "fps": found.get("fps"),
            "seconds": found.get("duration"), "sound": bool(found.get("has_audio")), "lufs": lufs}


def _upscale_fails(out: dict, src: dict) -> list[dict]:
    """What the upscale changed that it may not (the module docstring), as string-table keys and values."""
    fails = []
    slack = UPSCALE_SLACK
    w, h, sw, sh = out["width"] or 0, out["height"] or 0, src["width"] or 0, src["height"] or 0
    if min(w, h) < 1080 * slack["size"] or not (sw and sh and abs(w / h - sw / sh) <= slack["shape"] * (sw / sh)):
        fails.append({"key": _Q + "upscale_size", "values": {"got": f"{w}×{h}", "take": f"{sw}×{sh}"}})
    if abs((out["fps"] or 0) - (src["fps"] or 0)) > slack["fps"]:
        fails.append({"key": _Q + "upscale_fps", "values": {"got": f"{out['fps']:g}", "take": f"{src['fps']:g}"}})
    if abs((out["seconds"] or 0) - (src["seconds"] or 0)) > slack["seconds"]:
        fails.append({"key": _Q + "upscale_length", "values": {"got": f"{out['seconds']:g}",
                                                               "take": f"{src['seconds']:g}"}})
    if src["sound"] and not out["sound"]:
        fails.append({"key": _Q + "upscale_no_sound", "values": {}})
    elif (src["sound"] and _number(out["lufs"]) and _number(src["lufs"])
          and abs(out["lufs"] - src["lufs"]) > slack["lu"]):
        fails.append({"key": _Q + "upscale_loudness", "values": {"got": f"{out['lufs']:.1f}",
                                                                 "take": f"{src['lufs']:.1f}",
                                                                 "slack": f"{slack['lu']:g}"}})
    return fails


def _upscaled_from(run: RunFolder, pack: dict, stem: str) -> str | None:
    """The accepted take the item's latest record was made from: the current takes pick whose file its inputs name."""
    names = set()
    for _, record in organic_specs.records(run, stem):
        if record.get("outputs"):
            names = {v.removeprefix("file:").casefold() for v in (record.get("input") or {}).values()
                     if isinstance(v, str) and v.startswith("file:")}
    checked = _checked_at(run)
    for row in picks(run, TAKES).values():
        if (upscale_item(pack, row["name"]) is None and Path(row["file"]).name.casefold() in names
                and current(run, row, checked_at=checked) is None):
            return posix(row["file"])
    return None


def upscale_check(run: RunFolder, name: str) -> dict:
    """The upscale's technical QA and its pick by rule (the module docstring). Returns {row, qa, source, measured}; a
    Stop when there is nothing to check, or the upscale changed what it may not (nothing is logged)."""
    if state.load(run).playbook != ORGANIC_VIDEO:
        raise ValueError("Upscales are checked in organic video runs.")
    pack = _pack(run)
    item = upscale_item(pack, name)
    if item is None:
        ups = [i["name"] for st in pack["stages"] if st["stage"] == organic_pack.UPSCALE_STAGE for i in st["items"]]
        raise Stop(f"{name} is not an upscale item of the checked pack (its upscale items: {', '.join(ups) or 'none'}); "
                   f"nothing was checked; {AGAIN}.")
    stem = c.stem_of(item["name"])
    latest, _ = _outputs(run, stem)
    made = sorted(f for f in latest if Path(f).suffix.lower() in VIDEO_EXT)
    if len(made) != 1:
        raise Stop(f"{item['name']} has {'no' if not made else 'more than one'} video from its latest run "
                   f"({', '.join(made) or 'nothing yet'}): upscale the accepted take once (tm tool replicate_run --name "
                   f"{item['name']}); nothing was checked; {AGAIN}.")
    rel = made[0]
    source = _upscaled_from(run, pack, stem)
    if source is None:
        raise Stop(f"{rel} is not made from an accepted take: {item['name']}'s spec takes the take the user accepted "
                   f"(its current pick, with its QA) as its input video. Nothing was checked; {AGAIN}.")
    out, src = _measure(run.path / rel), _measure(run.path / source)
    fails = _upscale_fails(out, src)
    target = run.next_version(qa_stage(run, run.path / rel), f"{Path(rel).stem}_qa", "json")
    run.assert_writable(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    qa = {"take": rel, "kind": UPSCALE_QA, "source": source, "measured": out, "source_measured": src, "fails": fails}
    target.write_text(json.dumps(qa, ensure_ascii=False, indent=1), encoding="utf-8")
    qa_rel = c.rel(run, target)
    manifest.record(run, qa_rel, qa_rel.split("/", 1)[0], "tm organic upscale", parent=rel, cost="0")
    if fails:
        tr = i18n.translator(i18n.ENGLISH)
        raise Stop(f"{rel} changed what an upscale may not ({'; '.join(tr(f['key'], **f['values']) for f in fails)}), "
                   f"so it is not picked (its QA: {qa_rel}). Show the user these findings; the take they accepted, "
                   f"{source}, stays accepted. They choose: deliver at the take's own resolution (the pack re-planned "
                   f"without the upscale), or the upscale made again, paid as a redo (tm organic redo); {AGAIN}.")
    row = {"stage": TAKES, "name": item["name"], "file": rel,
           "rubric": {"qa": qa_rel, "upscale_of": source, "fails": [], "findings": []},
           "reason": f"the upscale of the accepted take {source}: the size, the frame rate and the sound checked",
           "by": "rule", "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    organic_specs.az_rows(run)   # a damaged log is mended first, so a pick never lands after an unreadable line
    library.append_jsonl(run.path / AZ_LOG, [row])
    manifest.record(run, rel, rel.split("/", 1)[0], f"{TAKES} pick (rule)", parent=qa_rel,
                    params={"item": item["name"], "reason": row["reason"]}, cost="0")
    return {"row": row, "qa": qa_rel, "source": source, "measured": out}


# --- step checks -------------------------------------------------------------------------------------

NO_PACK_GAP = "the latest pack passed the pack check (tm organic pack check --stage pack)"


def _gap(run: RunFolder, stage: str, video: bool) -> str | None:
    pack = organic_pack.checked_pack(run)
    if pack is None:
        return NO_PACK_GAP
    checked_at = _checked_at(run)
    command = (f"tm organic pick --stage {stage} --name <item> --file <{'take' if video else 'image'}> "
               "--reason \"<why>\"")
    missing, drawn = [], []
    try:
        done = picks(run, stage)
        for item in _wanted(pack, video):
            row = done.get(c.stem_of(item["name"]))
            why = "it has no pick" if row is None else current(run, row, checked_at=checked_at)
            if why and video and upscale_item(pack, item["name"]) is not None:
                why += f": it is the upscale of the accepted take, checked and picked by rule with {UPSCALE_TOOL}"
            if why:
                missing.append(f"{item['name']}: {why}")
        boards = picks(run, STORYBOARD)
        for item in organic_pack.animated(pack):
            why = _board_gap(run, item, boards, checked_at)
            if not why and video:
                anim = animation_of(run, item)
                why = (None if anim and anim[1].get("storyboard_pick") == pick_mark(boards[c.stem_of(item)])
                       else "its animation is not drawn from its accepted storyboard (tm organic animate)")
            if why:
                drawn.append(f"{item}: {why}")
        motion = [f"{item}: {why}" for item in (organic_pack.stills(pack) if video else [])
                  if (why := _motion_gap(run, pack, item, checked_at))]
    except Stop as exc:   # a damaged log or record
        return f"the A–Z log and the Replicate records are readable ({exc})"
    if not missing and not drawn and not motion:
        return None
    gaps = []
    if missing:
        what = "each take is checked and picked" if video else "each image item has its pick logged"
        gaps.append(f"{what}, after the latest pack check, from the item's latest take ({'; '.join(missing)}): "
                    f"{command}")
    if drawn:
        what = ("each animation is drawn from its accepted storyboard" if video
                else "each animation's latest storyboard is accepted after the latest pack check")
        gaps.append(f"{what} ({'; '.join(drawn)}): accepted on the images check-in page or tm organic pick --stage "
                    "storyboard --name <item> --file <its sheet.png> --reason \"<why>\"" + (", then tm organic animate"
                                                                                           if video else ""))
    if motion:
        gaps.append(f"each stills item is rendered from its picked pictures ({'; '.join(motion)}): tm render video "
                    f"--run <run> --comp {'|'.join(render.MOTION_COMPS)} --props <its props, naming the picks>")
    return "; and ".join(gaps)


def images_gap(run: RunFolder) -> str | None:
    """The `images_picked` step check (F1): each image item of the checked pack has a pick that counts (`current`).
    Reads only."""
    return _gap(run, IMAGES, video=False)


def takes_gap(run: RunFolder) -> str | None:
    """The `takes_checked` step check (F2): each video item of the checked pack has a pick that counts (`current`):
    its latest take, with that take's latest QA. Reads only."""
    return _gap(run, TAKES, video=True)
