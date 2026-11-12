"""Create an ad (playbook 05), G4 and S7: the takes' QA and their acceptance (CA7, CA8, CA11), and the edit's QA before
every showing (CA11).

The measures are organic video's take QA: `tm tool take_qa --run R <video> --lang <market language> [--script <its
lines>]` writes `<video dir>/qa/<stem>_qa_vNN.json` (cuts, the transcript and its match with the lines, pace,
loudness, a contact sheet; `organic_qa`), for a take and for an edit alike. Here they are judged.

**The takes (G4).** A take is a video output of its storyboard item's latest Replicate record
(`03_wip/<item>_vNN.run.json`; a failed or cancelled run made nothing, so the take before it stays the one). A take
*speaks* when it carries the spoken lines: the storyboard video's `speaks`, else the plan's voice route (`native` and
`clone_take` speak in the model; the user's VO and an ElevenLabs voice come in the edit). Its rubric:

- `fails`: organic video's takes rubric (`organic_qa.rubric_words`: the transcript under `qa.transcript_min`, the
  loudness outside `qa.lufs_usable`, no sound in a take that speaks), plus **a word heard twice in a row that the
  lines say once** (a stutter: the transcript's match cannot see it, since the longest common subsequence skips an
  extra word);
- `findings`: the rubric's (cut offsets, a slow pace), **a word lasting about 2× its expected length** (a possible
  hidden repeat, CA11: its letters × the take's median seconds a letter), and **internal cuts** (CA10: keep each
  line's picture inside its own shot).

Step check `ad_takes_checked` (G4, `takes_gap`): every video of the checked storyboard has a take, and that take
its latest QA, with a transcript when it speaks. Check-in choice `takes accept` requires `ad_takes_accepted`
(`accepted_gap`): besides, each take passes its rubric, or the user saw its failure: a `takes fails_qa` decision
recorded at or after its latest QA (the check-in's stop: a video is never regenerated automatically). `take_rows`
is the takes check-in page's data, in the page's language.

**The edit (S7).** Each version is `03_wip/edit_vNN.mp4` (S6), measured with `tm tool take_qa` like a take (with
`--script` holding the board's lines when it has any). The agent writes what it checked, `03_wip/edit_qa_vNN.json`:

    {"edit": "03_wip/edit_vNN.mp4", "qa": "<its latest take_qa file>",
     "checked": [{"check": <one of EDIT_CHECKS>, "result": "ok" | "not_applicable" | "problem", "note": "<what>"}]}

`tm ad check edit` (`check_edit`) refuses it unless it names the latest edit and that edit's latest QA, the QA
measures the run's `qa.lufs_target` within 1 LU and a true peak at most `qa.true_peak_max`, an edit with spoken
lines has a transcript at `qa.transcript_min` or above and no stutter, and every CA11 check is written with a note,
none of them a problem (a problem is fixed in a new version, S6, and QA'd again). Step check `ad_edit_checked` (S7,
`edit_gap`), also required by `review accept`: the latest edit QA is the checked one, unchanged, and still names the
latest edit and its latest QA. `edit_report` is the review page's "what was checked". All read only but the check.
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from tm import config, create_config, create_plan, i18n, organic_qa, organic_specs, state, stepchecks
from tm.config import Problem
from tm.review import VIDEO_EXT
from tm.runfolder import RunFolder
from tm.stops import Stop
from tm.tools import _common as c

WIP = create_config.WIP
EDIT, EDIT_QA = "edit", create_plan.EDIT_QA
KEY_EDIT = create_plan.KEY[EDIT_QA]
SPEAKING_ROUTES = ("native", "clone_take")   # the voice routes whose lines are in the generated take (CA6)
# CA11, each written by the agent with what it saw; the loudness and the transcript are measured (take_qa)
EDIT_CHECKS = ("cuts", "take_scenes", "stills", "captions", "speech", "joins", "overlay_ends", "text")
RESULTS = ("ok", "not_applicable", "problem")
LONG_WORD = 2.0      # a word lasting about 2× its expected length is a possible hidden repeat (CA11)
LUFS_SLACK = 1.0     # LU around qa.lufs_target, as organic video's final
QA_TOOL = "tm tool take_qa --run R {video} --lang <the market language>"


def _english() -> i18n.Translator:
    return i18n.translator(i18n.ENGLISH)


def _cfg(run: RunFolder) -> dict:
    return create_config.load(run)


def _rel(run: RunFolder, path: Path) -> str:
    return c.rel(run, path)


# --- the measures -------------------------------------------------------------------------------

def _heard(words: list[dict]) -> list[tuple[str, dict]]:
    return [(" ".join(organic_qa._plain(str(w.get("word", "")))), w) for w in words if isinstance(w, dict)]


def repeats(words: list[dict], script: str) -> list[tuple[str, dict]]:
    """A word heard twice in a row that the script does not say twice in a row: (string key, values) each."""
    said = organic_qa._plain(script or "")
    doubled = {a for a, b in zip(said, said[1:]) if a == b}
    heard = _heard(words)
    out = []
    for (prev, _), (word, w) in zip(heard, heard[1:]):
        if word and word == prev and word not in doubled:
            out.append(("ad.qa.fail_repeat", {"word": str(w.get("word", "")).strip(), "at": f"{_num(w.get('start')):.2f}"}))
    return out


def _num(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def long_words(words: list[dict]) -> list[tuple[str, dict]]:
    """A word lasting more than LONG_WORD × its expected length (its letters × the median seconds a letter of the
    take's words): a possible hidden repeat."""
    timed = []
    for word, w in _heard(words):
        letters = len(word.replace(" ", ""))
        length = _num(w.get("end")) - _num(w.get("start"))
        if letters and length > 0:
            timed.append((w, letters, length))
    if len(timed) < 3:
        return []
    per_letter = statistics.median(length / letters for _, letters, length in timed)
    out = []
    for w, letters, length in timed:
        expected = letters * per_letter
        if length > LONG_WORD * expected:
            out.append(("ad.qa.finding_long", {"word": str(w.get("word", "")).strip(), "at": f"{_num(w['start']):.2f}",
                                              "seconds": f"{length:.2f}", "times": f"{length / expected:.1f}"}))
    return out


def _transcript(run: RunFolder, qa: dict) -> list[dict]:
    rel = qa.get("transcript")
    if not isinstance(rel, str):
        return []
    try:
        data = json.loads((run.path / rel).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise Stop(f"{rel} cannot be read: run the QA again ({QA_TOOL.format(video=qa.get('take'))}).") from None
    return [w for s in data.get("segments") or [] if isinstance(s, dict) for w in s.get("words") or []]


def board_lines(run: RunFolder) -> str:
    """The spoken lines of the checked script-board, in order."""
    board = create_plan.checked(run, create_plan.BOARD) or {}
    return " ".join(str(sc["line"]) for sc in board.get("scenes") or []
                    if isinstance(sc, dict) and isinstance(sc.get("line"), str) and sc["line"].strip())


# --- G4 the takes --------------------------------------------------------------------------------

def speaks(run: RunFolder, video: dict) -> bool:
    if isinstance(video.get("speaks"), bool):
        return video["speaks"]
    plan = create_plan.checked(run, create_plan.PLAN) or {}
    return plan.get("voice_route") in SPEAKING_ROUTES


def _takes_of(run: RunFolder, item: str) -> list[Path]:
    latest, _ = organic_specs.outputs(run, c.stem_of(item))
    return [run.path / rel for rel in sorted(latest) if Path(rel).suffix.lower() in VIDEO_EXT]


def _rows(run: RunFolder, tr: i18n.Translator) -> list[dict] | None:
    """One row per take of the checked storyboard's videos (an item with no take yet has a row with `take` None),
    or None when the storyboard is not checked. A damaged record or QA file is a Stop."""
    board = create_plan.checked(run, create_plan.STORYBOARD)
    if board is None:
        return None
    cfg, script = _cfg(run), board_lines(run)
    rows = []
    for video in board.get("videos") or []:
        if not (isinstance(video, dict) and isinstance(video.get("item"), str)):
            continue
        talk = speaks(run, video)
        takes = _takes_of(run, video["item"])
        if not takes:
            rows.append({"item": video["item"], "take": None, "speaks": talk, "missing": "it has no take yet"})
        for take in takes:
            rows.append(_row(run, cfg, tr, video["item"], take, talk, script))
    return rows


def _row(run: RunFolder, cfg: dict, tr: i18n.Translator, item: str, take: Path, talk: bool, script: str) -> dict:
    rel = _rel(run, take)
    row = {"item": item, "take": rel, "speaks": talk, "qa": None, "qa_at": None, "transcript": None,
           "contact_sheet": None, "fails": [], "findings": [], "missing": None}
    path = organic_qa.qa_file(run, take)
    if path is None:
        row["missing"] = f"it has no take QA ({QA_TOOL.format(video=rel)}{' --script <its lines>' if talk else ''})"
        return row
    qa = organic_qa.read_qa(run, path)
    row.update(qa=_rel(run, path), qa_at=datetime.fromtimestamp(int(path.stat().st_mtime), timezone.utc),
               transcript=qa.get("transcript"), contact_sheet=qa.get("contact_sheet"))
    if qa.get("take") != rel:
        row["missing"] = f"its latest QA, {row['qa']}, names {qa.get('take')!r}: run the QA on the take"
        return row
    if talk and qa.get("transcript") is None:
        row["missing"] = (f"it carries the spoken lines, and its QA has no transcript: run it again with --script "
                          f"<its lines> ({QA_TOOL.format(video=rel)} --script <its lines>)")
        return row
    rubric = organic_qa.rubric_words(qa, cfg, tr, speech=talk)
    words = _transcript(run, qa) if talk else []
    fails = repeats(words, script)
    findings = long_words(words)
    cuts = [t for t in qa.get("cuts") or [] if isinstance(t, (int, float))]
    row["fails"] = rubric["fails"] + [tr(k, **v) for k, v in fails]
    row["findings"] = rubric["findings"] + [tr(k, **v) for k, v in findings]
    if cuts:
        row["findings"].append(tr.plural("ad.qa.finding_cuts", len(cuts), n=len(cuts),
                                         at=", ".join(f"{t:g}" for t in cuts)))
    return row


def take_rows(run: RunFolder, tr: i18n.Translator | None = None) -> list[dict]:
    """The takes check-in page's data (pages.md "Gate"): per take its item, file, whether it speaks, its QA, transcript
    and contact sheet, and its fails and findings in the page's language (`tr`; English by default). Empty before
    the storyboard is checked."""
    rows = _rows(run, tr or _english()) or []
    return [{k: v for k, v in r.items() if k != "qa_at"} for r in rows]


def takes_gap(run: RunFolder) -> str | None:
    """`ad_takes_checked` (G4): every video of the checked storyboard has its take and that take its latest QA (with a
    transcript when it speaks). Reads only."""
    try:
        rows = _rows(run, _english())
    except Stop as exc:
        return f"the takes' records and QA files are readable ({exc})"
    if rows is None:
        return "the filled storyboard passes tm ad check storyboard"
    missing = [f"{r['take'] or r['item']}: {r['missing']}" for r in rows if r["missing"]]
    return f"each take is made and has its QA ({'; '.join(missing)})" if missing else None


def _fails_qa_since(run: RunFolder, since: datetime) -> bool:
    for d in state.load(run).decisions:
        when = organic_specs.when(d.get("at"))
        if d.get("checkin") == "takes" and d.get("choice") == "fails_qa" and when is not None and when >= since:
            return True
    return False


def accepted_gap(run: RunFolder) -> str | None:
    """`ad_takes_accepted` (the takes check-in's accept): `takes_gap`, and each take passes its rubric or the user
    saw it fail (a `takes fails_qa` decision at or after its latest QA). Reads only."""
    gap = takes_gap(run)
    if gap:
        return gap
    failing = [f"{r['take']}: {'; '.join(r['fails'])}" for r in _rows(run, _english()) or []
               if r["fails"] and not _fails_qa_since(run, r["qa_at"])]
    if failing:
        return (f"no take fails its QA ({' | '.join(failing)}), or the user has seen it: record `tm decide takes "
                "fails_qa` (a video is never regenerated automatically), show the take with its QA notes, and accept "
                "only on their word")
    return None


# --- S7 the edit ---------------------------------------------------------------------------------

def _measured(run: RunFolder, cfg: dict, edit: Path, qa_path: Path) -> list[Problem]:
    out: list[Problem] = []
    try:
        qa = organic_qa.read_qa(run, qa_path)
    except Stop as exc:
        return [Problem("qa", str(exc), "Run the edit's QA again.")]
    if qa.get("take") != _rel(run, edit):
        return [Problem("qa", f"{_rel(run, qa_path)} is the QA of {qa.get('take')!r}, not of the edit.",
                        f"Run it on the edit: {QA_TOOL.format(video=_rel(run, edit))}.")]
    target, peak_max = config.get(cfg, "qa.lufs_target"), config.get(cfg, "qa.true_peak_max")
    target = target if target is not None else create_config.DEFAULTS["qa"]["lufs_target"]
    peak_max = peak_max if peak_max is not None else create_config.DEFAULTS["qa"]["true_peak_max"]
    lufs, peak = qa.get("lufs"), qa.get("peak")
    louder = "Run the loudness pass again (S6, tm tool deliver), write a new version and QA it."
    if not isinstance(lufs, (int, float)):
        out.append(Problem("qa.lufs", "The edit has no measurable sound.", "Render it with its sound (S6)."))
    elif abs(lufs - target) > LUFS_SLACK:
        out.append(Problem("qa.lufs", f"The edit measures {lufs:.1f} LUFS, more than {LUFS_SLACK:g} LU from "
                           f"{target:g} LUFS (CA11).", louder))
    if isinstance(peak, (int, float)) and peak > peak_max:
        out.append(Problem("qa.peak", f"The edit's true peak is {peak:.1f} dBFS, above {peak_max:g} dBFS (CA11).", louder))
    script = board_lines(run)
    if script:
        least = organic_qa._setting(cfg, "transcript_min")
        match = qa.get("match")
        if not isinstance(match, (int, float)):
            out.append(Problem("qa.transcript", "The edit has spoken lines and its QA has no transcript.",
                               f"Run {QA_TOOL.format(video=_rel(run, edit))} --script <the board's lines>."))
        else:
            if match < least:
                out.append(Problem("qa.transcript", f"The edit's transcript matches {match:.0%} of the board's lines, "
                                   f"under {least:.0%}.", "Listen for the missing words, fix the edit (S6), QA it again."))
            tr = _english()
            try:
                found = repeats(_transcript(run, qa), script)
            except Stop as exc:
                found = []
                out.append(Problem("qa.transcript", str(exc), "Run the edit's QA again."))
            out.extend(Problem("qa.transcript", f"In the edit, {tr(k, **v)}.",
                               "Compare the edit's audio with the take: an edit bug is fixed in the edit (S6), a model "
                               "stutter is cut by its word times (CA6, CA12).") for k, v in found)
    return out


def check_edit(run: RunFolder, data: dict) -> list[Problem]:
    """`tm ad check edit`: the edit QA file (the module docstring)."""
    cfg = _cfg(run)
    latest = run.latest(WIP, EDIT, "mp4")
    if latest is None:
        return [Problem("edit", f"There is no edit yet ({WIP}/{EDIT}_vNN.mp4).", "Render the edit first (S6).")]
    want = _rel(run, latest)
    if data.get("edit") != want:
        return [Problem("edit", f"The edit QA names {data.get('edit')!r}, not the latest edit, {want}.",
                        "QA the latest version.")]
    out: list[Problem] = []
    qa_path = organic_qa.qa_file(run, latest)
    if qa_path is None:
        out.append(Problem("qa", f"{want} has no QA yet.", f"Run {QA_TOOL.format(video=want)} (with --script <the "
                           "board's lines> when it has spoken lines)."))
    elif data.get("qa") != _rel(run, qa_path):
        out.append(Problem("qa", f"The edit QA names {data.get('qa')!r}, not {want}'s latest QA, "
                           f"{_rel(run, qa_path)}.", "Name its latest QA."))
    else:
        out.extend(_measured(run, cfg, latest, qa_path))
    checked = data.get("checked") if isinstance(data.get("checked"), list) else []
    seen: dict[str, dict] = {}
    for n, row in enumerate(checked, 1):
        if not (isinstance(row, dict) and row.get("check") in EDIT_CHECKS and row.get("result") in RESULTS
                and isinstance(row.get("note"), str) and row["note"].strip()):
            out.append(Problem(f"checked[{n}]", f"Check {n} needs check (one of {', '.join(EDIT_CHECKS)}), result "
                               f"({', '.join(RESULTS)}) and a note saying what was looked at.", "Complete it."))
            continue
        seen[row["check"]] = row
        if row["result"] == "problem":
            out.append(Problem(f"checked[{n}]", f"The {row['check']} check found a problem: {row['note'].strip()}",
                               "Fix it in a new version of the edit (S6), then QA that version (CA11: QA before "
                               "every showing)."))
    missing = [k for k in EDIT_CHECKS if k not in seen]
    if missing:
        out.append(Problem("checked", f"The edit QA does not say what was checked for {', '.join(missing)} (CA11).",
                           "Check each one and write it (not_applicable, with why, when the ad has none)."))
    return out


def _checked_edit(run: RunFolder) -> dict | None:
    return create_plan.checked(run, EDIT_QA)


def edit_gap(run: RunFolder) -> str | None:
    """`ad_edit_checked` (S7, and the review's accept): the latest edit QA passed `tm ad check edit`, unchanged, and
    still names the latest edit and that edit's latest QA. Reads only."""
    gap = stepchecks.fresh(run, KEY_EDIT, WIP, EDIT_QA, "json")
    if gap:
        return f"the edit's QA is written and passes tm ad check edit ({gap})"
    data = _checked_edit(run) or {}
    latest = run.latest(WIP, EDIT, "mp4")
    want = _rel(run, latest) if latest else None
    if data.get("edit") != want:
        return f"the latest edit, {want}, has its own QA checked (tm tool take_qa, then tm ad check edit)"
    qa = organic_qa.qa_file(run, latest)
    if qa is None or data.get("qa") != _rel(run, qa):
        return f"the edit QA names {want}'s latest QA, {_rel(run, qa) if qa else 'none yet'} (tm ad check edit)"
    return None


def edit_report(run: RunFolder, tr: i18n.Translator | None = None) -> dict | None:
    """The review page's "what was checked" (pages.md "Review"): the checked edit QA's edit, its loudness and true
    peak, and each CA11 check with its label, result and note, in the page's language. None before it is checked."""
    data = _checked_edit(run)
    if data is None:
        return None
    tr = tr or _english()
    try:
        qa = json.loads((run.path / data["qa"]).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, KeyError, TypeError):
        qa = {}
    return {"edit": data.get("edit"), "qa": data.get("qa"), "lufs": qa.get("lufs"), "peak": qa.get("peak"),
            "match": qa.get("match"), "title": tr("ad.qa.checked_title"),
            "checked": [{"check": r["check"], "label": tr(f"ad.qa.check_{r['check']}"), "result": r["result"],
                         "result_label": tr(f"ad.qa.result_{r['result']}"), "note": r["note"]}
                        for r in data.get("checked") or [] if isinstance(r, dict) and r.get("check") in EDIT_CHECKS]}
