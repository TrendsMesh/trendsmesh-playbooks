"""Create an ad (playbook 05), S1 to G3: the checks of the concepts, the claims, the script-board, the production plan
and the filled storyboard; the money they plan; and the guard of every paid Replicate call.

Each file is written by the agent as a new version in 03_wip and checked with `tm ad check <what> --run R --file F`.
A clean check marks the file (`stepchecks.mark`), and the step's check (`*_gap`) asks that the latest version is
that file, unchanged. The formats are in skills/create-ad/references/flow.md.

Money (CA7, the owner's decision 2): a checked production plan sets run.json `planned` to its pre-video lines per
budget kind (stills, audio, transcription), and a checked storyboard to those plus its videos; each sets
`planned_at`, so the yes at `plan`, then at `storyboard`, is asked again after a re-plan (flow.planned_gap,
budget.approve). Hands-off's yes is the budget approved at intake.

The guard (`tools.PRECHECK[CREATE_AD]["replicate_run"]`) runs before `budget.spend` for every paid call: the item
(`--name`) is a line of the checked plan (a pre-video item) or of the checked storyboard (a video) at that line's cost;
a video waits for the storyboard's yes recorded after the storyboard was checked; and a video item that already has a
take runs again only after the user asked for it (`tm ad redo`): **a video is never regenerated automatically**.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

from tm import config, create_config, flow, playbooks, state, stepchecks
from tm.config import Problem
from tm.playbooks import CREATE_AD
from tm.runfolder import RunFolder

WIP = create_config.WIP
RESEARCH = "02_research"
CONCEPTS, CLAIMS, BOARD, PLAN, STORYBOARD = "concepts", "claims", "board", "production_plan", "storyboard"
EDIT_QA = "edit_qa"   # S7's file, checked by tm.create_qa (`tm ad check edit`)
WHAT = {CONCEPTS: "the concepts", CLAIMS: "the claims", BOARD: "the script-board", PLAN: "the production plan",
        STORYBOARD: "the filled storyboard", EDIT_QA: "the edit QA"}
KEY = {stem: f"ad_{stem}" for stem in WHAT}   # run.json `checked` keys
SOURCES_MODEL_AD = ("trendsmesh", "ad_library", "user", "guess")
SOURCES_TREND = ("trendsmesh", "guess")
TREND_TYPES = ("hook", "format", "topic", "sound", "hashtag", "visual")
CLAIM_SOURCES = ("site", "user", "trend")
STAGES = ("pre_video", "video")
VOICE_ROUTES = ("native", "elevenlabs_voice", "user_vo", "clone_take")
FAILED = ("failed", "canceled", "refused")    # a take that ended without a result costs nothing and may run again
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
TOL = 1e-6
NEVER = ("A video is never regenerated automatically. Show the user the take and its QA notes; if they want it made "
         "again, record their words with `tm ad redo --run R --item {item} --note \"<their words>\"` (its cost is the "
         "storyboard's line), then run it.")


# --- reading --------------------------------------------------------------------

def _read(path: Path) -> tuple[dict | None, list[Problem]]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, [Problem(Path(path).name, f"{Path(path).name} cannot be read as JSON ({exc}).", "Write it again.")]
    if not isinstance(data, dict):
        return None, [Problem(Path(path).name, f"{Path(path).name} must hold one JSON object.", "Write it again.")]
    return data, []


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _number(value: object, low: float = 0.0) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= low


def checked_file(run: RunFolder, stem: str) -> Path | None:
    """The latest version of `stem`, when it is the checked one and unchanged; else None."""
    if stepchecks.fresh(run, KEY[stem], WIP, stem, "json") is not None:
        return None
    return run.latest(WIP, stem, "json")


def checked(run: RunFolder, stem: str) -> dict | None:
    path = checked_file(run, stem)
    return _read(path)[0] if path else None


def numbers(text: str) -> set[str]:
    """The numbers written in a text, as written ("3", "1,500", "2.5"): a claim's numbers are the only ones copy may use."""
    return {m.group(0).replace(",", "").replace(".", "") for m in NUMBER.finditer(text or "")}


def _in_run(run: RunFolder, rel: object) -> bool:
    if not _text(rel):
        return False
    target = (run.path / str(rel)).resolve()
    try:
        target.relative_to(run.path.resolve())
    except ValueError:
        return False
    return target.is_file()


# --- S1 the concepts (CA2) ------------------------------------------------------

def check_concepts(run: RunFolder, data: dict) -> list[Problem]:
    out: list[Problem] = []
    s = state.load(run)
    cfg = create_config.load(run)
    if s.evidence is None:
        out.append(Problem("evidence", "What the concepts rest on is not recorded.",
                           "Run tm evidence trendsmesh --why <reason> when TrendsMesh answers, or tm evidence guess "
                           "--why <reason> without it."))
    guess = s.evidence == "guess"
    ads = data.get("model_ads")
    ads = ads if isinstance(ads, list) else []
    if not ads:
        out.append(Problem("model_ads", "No model ad is listed (about 5).", "List the model ads found."))
    ad_ids = set()
    for n, ad in enumerate(ads, 1):
        if not (isinstance(ad, dict) and _text(ad.get("id")) and ad.get("source") in SOURCES_MODEL_AD
                and _text(ad.get("why"))):
            out.append(Problem(f"model_ads[{n}]", f"Model ad {n} needs an id, a source ({', '.join(SOURCES_MODEL_AD)}) "
                               "and what to take from it (why).", "Complete it."))
            continue
        ad_ids.add(ad["id"])
        if guess and ad["source"] == "trendsmesh":
            out.append(Problem(f"model_ads[{n}]", "This run has no TrendsMesh data, so no model ad comes from it.",
                               "Mark it with its real source: the Ad Library, the user, or your guess."))
        if ad["source"] in ("trendsmesh", "ad_library") and not _in_run(run, ad.get("saved")):
            out.append(Problem(f"model_ads[{n}]", f"Model ad {ad['id']} has no saved answer in the run.",
                               f"Save the MCP answer in {RESEARCH}/ and name it in saved."))
    trends = data.get("trends")
    trends = trends if isinstance(trends, list) else []
    trend_ids = set()
    for n, tr in enumerate(trends, 1):
        if not (isinstance(tr, dict) and _text(tr.get("id")) and tr.get("type") in TREND_TYPES
                and tr.get("source") in SOURCES_TREND):
            out.append(Problem(f"trends[{n}]", f"Trend {n} needs an id, a type ({', '.join(TREND_TYPES)}) and a source "
                               f"({', '.join(SOURCES_TREND)}).", "Complete it."))
            continue
        trend_ids.add(tr["id"])
        if guess and tr["source"] == "trendsmesh":
            out.append(Problem(f"trends[{n}]", "This run has no TrendsMesh data, so this trend is a guess.",
                               "Mark its source as guess."))
        if tr["source"] == "trendsmesh":
            evidence = tr.get("evidence")
            if not (isinstance(evidence, list) and len(evidence) >= 2 and all(_text(e) for e in evidence)):
                out.append(Problem(f"trends[{n}]", f"Trend {tr['id']} needs 2 evidence videos.",
                                   "Name two of its videos."))
            if not any((run.path / RESEARCH).glob("trend_*.json")):
                out.append(Problem(f"trends[{n}]", "The trend cards are not saved in the run.",
                                   f"Save each get_trend answer as {RESEARCH}/trend_<id>.json."))
        if tr["type"] == "sound" and tr.get("licence") not in ("ads", "inspiration"):
            out.append(Problem(f"trends[{n}]", "A sound trend is used in an ad only with a licence for ads.",
                               "Set licence: ads (licensed for ads) or inspiration (not used as the sound)."))
    concepts = data.get("concepts")
    concepts = concepts if isinstance(concepts, list) else []
    if not 2 <= len(concepts) <= 3:
        out.append(Problem("concepts", f"There are {len(concepts)} concepts; the page shows 2 to 3.",
                           "Write 2 or 3 concepts."))
    length = config.get(cfg, "intake.length_s")
    low, high = length if isinstance(length, list) and len(length) == 2 else (0, 0)
    for n, cp in enumerate(concepts, 1):
        if not isinstance(cp, dict):
            out.append(Problem(f"concepts[{n}]", f"Concept {n} must be an object.", "Write it again."))
            continue
        name = cp.get("name") or n
        for key in ("key", "name", "combine", "length_why"):
            if not _text(cp.get(key)):
                out.append(Problem(f"concepts[{n}].{key}", f"Concept {name} has no {key}.", "Write it."))
        if cp.get("model_ad") not in ad_ids:
            out.append(Problem(f"concepts[{n}].model_ad", f"Concept {name} names no listed model ad.",
                               "Name one of the model ads."))
        used = cp.get("trends")
        if not (isinstance(used, list) and used and set(used) <= trend_ids):
            out.append(Problem(f"concepts[{n}].trends", f"Concept {name} names no listed trend.",
                               "Name the trends it combines."))
        beats = cp.get("beats")
        if not (isinstance(beats, list) and beats and all(isinstance(b, dict) and _text(b.get("picture"))
                                                          for b in beats)):
            out.append(Problem(f"concepts[{n}].beats", f"Concept {name} has no beats (time, picture, line).",
                               "Write its beats."))
        length = cp.get("length_s")
        if not (_number(length, 1) and low <= length <= high):
            out.append(Problem(f"concepts[{n}].length_s", f"Concept {name}'s length ({length!r}) is not inside the "
                               f"length the user chose ({low} to {high} s).", "Fit it to the chosen length."))
        cost = cp.get("cost_usd")
        if not (isinstance(cost, list) and len(cost) == 2 and all(_number(v) for v in cost) and cost[0] <= cost[1]):
            out.append(Problem(f"concepts[{n}].cost_usd", f"Concept {name} needs a cost range [low, high] in USD.",
                               "Give the range."))
    return out


# --- S3 the claims (CA3) --------------------------------------------------------

def check_claims(run: RunFolder, data: dict) -> list[Problem]:
    out: list[Problem] = []
    cfg = create_config.load(run)
    claims = data.get("claims")
    if not (isinstance(claims, list) and claims):
        return [Problem("claims", "No claim is listed.", "List what the ad may say, each with its source.")]
    seen = set()
    for n, cl in enumerate(claims, 1):
        if not (isinstance(cl, dict) and _text(cl.get("id")) and _text(cl.get("text"))
                and cl.get("source") in CLAIM_SOURCES and _text(cl.get("ref"))):
            out.append(Problem(f"claims[{n}]", f"Claim {n} needs an id, its text, a source ({', '.join(CLAIM_SOURCES)}) "
                               "and where it comes from (ref: the page, the user's words, the trend).", "Complete it."))
            continue
        if cl["id"] in seen:
            out.append(Problem(f"claims[{n}]", f"The claim id {cl['id']} is used twice.", "Give each claim its own id."))
        seen.add(cl["id"])
    if config.get(cfg, "intake.live") is False and not _text(data.get("not_live_said")):
        out.append(Problem("not_live_said", f"What the ad sells is not live ({config.get(cfg, 'intake.not_live')}).",
                           "Write how the ad says so (not_live_said): nothing that is not live is promised."))
    return out


def claim_ids(run: RunFolder) -> set[str]:
    data = checked(run, CLAIMS) or {}
    return {c["id"] for c in data.get("claims") or [] if isinstance(c, dict) and _text(c.get("id"))}


def claim_numbers(run: RunFolder) -> set[str]:
    data = checked(run, CLAIMS) or {}
    out: set[str] = set()
    for c in data.get("claims") or []:
        if isinstance(c, dict):
            out |= numbers(str(c.get("text", "")))
    return out


# --- S4 the script-board (CA4) --------------------------------------------------

def _words(text: object) -> int:
    return len(str(text).split()) if _text(text) else 0


def check_board(run: RunFolder, data: dict) -> list[Problem]:
    out: list[Problem] = []
    cfg = create_config.load(run)
    if checked_file(run, CLAIMS) is None:
        out.append(Problem("claims", "The claims are not checked yet.", "Check them first (tm ad check claims)."))
    known = claim_ids(run)
    wpm = data.get("model_ad_wpm")
    if not _number(wpm, 1):
        out.append(Problem("model_ad_wpm", "The model ad's words per minute is missing.", "Measure it and write it."))
    scenes = data.get("scenes")
    if not (isinstance(scenes, list) and scenes):
        return out + [Problem("scenes", "The board has no scenes.", "Write it scene by scene.")]
    at, speech = 0.0, {}
    for n, sc in enumerate(scenes, 1):
        if not (isinstance(sc, dict) and _number(sc.get("start")) and _number(sc.get("end"))
                and sc["end"] > sc["start"] and _text(sc.get("picture")) and _text(sc.get("source"))):
            out.append(Problem(f"scenes[{n}]", f"Scene {n} needs start and end (seconds), the picture and where it comes "
                               "from (source).", "Complete it."))
            continue
        if abs(sc["start"] - at) > 0.05:
            out.append(Problem(f"scenes[{n}].start", f"Scene {n} starts at {sc['start']} s, not where the scene before "
                               f"ends ({at:g} s).", "Make the scenes follow each other."))
        at = sc["end"]
        if _text(sc.get("line")):
            speaker = sc.get("speaker") or "voice"
            speech[speaker] = speech.get(speaker, 0) + _words(sc["line"])
        unknown = [c for c in sc.get("claims") or [] if c not in known]
        if unknown:
            out.append(Problem(f"scenes[{n}].claims", f"Scene {n} names claims that are not in the checked claims: "
                               f"{', '.join(map(str, unknown))}.", "Use only checked claims (CA3)."))
    first = scenes[0] if isinstance(scenes[0], dict) else {}
    if not (_text(first.get("on_screen_text")) and first.get("start") == 0):
        out.append(Problem("scenes[1].on_screen_text", "The hook has no on-screen text in the first second.",
                           "Put the hook's text on screen from 0 s (CA10)."))
    length = config.get(cfg, "intake.length_s") or [0, 0]
    if isinstance(length, list) and len(length) == 2 and not length[0] <= at <= length[1]:
        out.append(Problem("scenes", f"The board runs {at:g} s, outside the length the user chose ({length[0]} to "
                           f"{length[1]} s).", "Fit it, or ask the user to change the length."))
    total = sum(speech.values())
    if _number(wpm, 1) and total > at * wpm / 60 + 0.5:
        out.append(Problem("scenes", f"The lines have {total} words, over the word budget of {at * wpm / 60:.0f} "
                           f"({at:g} s at the model ad's {wpm:g} words a minute).", "Cut words (CA4)."))
    words_max, max_s = config.get(cfg, "take.words_max"), config.get(cfg, "take.max_s")
    if len(speech) == 1:   # one speaker: one take carries all speech
        (speaker, words), = speech.items()
        if words > words_max:
            out.append(Problem("scenes", f"{speaker}'s lines have {words} words: one take carries all speech, and a "
                               f"take holds about {words_max} words ({max_s:g} s).", "Fit the lines to one take."))
    return out


# --- S5 the production plan (CA5 to CA7) ----------------------------------------

def _fresh_price(line: dict, cfg: dict, today: date) -> bool:
    try:
        when = date.fromisoformat(str(line.get("checked")))
    except ValueError:
        return False
    return 0 <= (today - when).days <= config.get(cfg, "pricing.max_age_days")


def _line_problems(run: RunFolder, cfg: dict, line: object, n: int, where: str, today: date,
                   kinds: tuple[str, ...]) -> list[Problem]:
    if not (isinstance(line, dict) and _text(line.get("item")) and _text(line.get("model"))):
        return [Problem(f"{where}[{n}]", f"Line {n} needs an item name and a model.", "Complete it.")]
    out, item = [], line["item"]
    if not _number(line.get("cost")):
        out.append(Problem(f"{where}[{n}].cost", f"{item} has no cost in USD (or credits).", "Price it."))
    if line.get("budget") not in kinds:
        out.append(Problem(f"{where}[{n}].budget", f"{item} must say which budget it spends ({', '.join(kinds)}).",
                           "Set budget."))
    if not _fresh_price(line, cfg, today) or not _in_run(run, line.get("price_file")):
        out.append(Problem(f"{where}[{n}].checked", f"{item}'s price has no saved price file checked in the last "
                           f"{config.get(cfg, 'pricing.max_age_days')} days.",
                           "Read the live price (tm tool replicate_price), save it, and give its file and date."))
    return out


def check_plan(run: RunFolder, data: dict, *, today: date | None = None) -> list[Problem]:
    today = today or date.today()
    out: list[Problem] = []
    cfg = create_config.load(run)
    kinds = playbooks.get(CREATE_AD).budgets
    if checked_file(run, BOARD) is None:
        out.append(Problem("board", "The script-board is not checked yet.", "Check it first (tm ad check board)."))
    route = data.get("voice_route")
    if route not in VOICE_ROUTES:
        out.append(Problem("voice_route", f"The voice route must be one of {', '.join(VOICE_ROUTES)} (CA6).",
                           "Decide it with the user's materials in mind."))
    inventory = run.latest(WIP, create_config.ASSETS_STEM, "json")
    assets = (_read(inventory)[0] or {}).get("assets") or [] if inventory else []
    replaced = {a.get("replaces") for a in assets if isinstance(a, dict) and a.get("usable") and a.get("replaces")}
    if any(isinstance(a, dict) and a.get("usable") and a.get("kind") == "voiceover" for a in assets) \
            and route != "user_vo":
        out.append(Problem("voice_route", "The user has a usable voice-over recording, which fixes the voice route.",
                           "Set voice_route to user_vo (the recording, or its 1:1 clone)."))
    lines = data.get("lines")
    if not (isinstance(lines, list) and lines):
        return out + [Problem("lines", "The plan has no lines.", "List each asset type with its model and price.")]
    for n, line in enumerate(lines, 1):
        out.extend(_line_problems(run, cfg, line, n, "lines", today, kinds))
        if not isinstance(line, dict):
            continue
        item = line.get("item")
        if line.get("type") not in create_config.ASSET_TYPES:
            out.append(Problem(f"lines[{n}].type", f"{item}'s asset type must be one of "
                               f"{', '.join(create_config.ASSET_TYPES)}.", "Set type."))
        if line.get("stage") not in STAGES:
            out.append(Problem(f"lines[{n}].stage", f"{item} must say whether it is made before the video "
                               "(pre_video) or is the video (video).", "Set stage."))
        alt = line.get("alternative")
        if not _text(alt) or alt == line.get("model"):
            out.append(Problem(f"lines[{n}].alternative", f"{item} needs one alternative model (CA5: suggest, never "
                               "impose).", "Name an alternative."))
        if line.get("type") in replaced:
            out.append(Problem(f"lines[{n}]", f"The user's own file replaces {line.get('type')}, so {item} is not "
                               "generated.", "Drop the line, and say in the plan what the file replaces."))
    return out


def plan_lines(data: dict | None, stage: str) -> list[dict]:
    return [ln for ln in (data or {}).get("lines") or [] if isinstance(ln, dict) and ln.get("stage") == stage]


def _totals(lines: list[dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for ln in lines:
        if _number(ln.get("cost")) and ln.get("budget"):
            out[ln["budget"]] = round(out.get(ln["budget"], 0.0) + float(ln["cost"]), 6)
    return out


# --- G3 the filled storyboard (CA7, CA8) ----------------------------------------

def check_storyboard(run: RunFolder, data: dict, *, today: date | None = None) -> list[Problem]:
    today = today or date.today()
    out: list[Problem] = []
    cfg = create_config.load(run)
    kinds = playbooks.get(CREATE_AD).budgets
    board = checked(run, BOARD)
    if checked(run, PLAN) is None or board is None:
        out.append(Problem("plan", "The script-board and the production plan are not both checked.",
                           "Check them first."))
    scenes = len((board or {}).get("scenes") or [])
    frames = data.get("frames")
    frames = frames if isinstance(frames, list) else []
    have = {f.get("scene") for f in frames if isinstance(f, dict) and _in_run(run, f.get("file"))}
    missing = [n for n in range(1, scenes + 1) if n not in have]
    if missing:
        out.append(Problem("frames", f"Scenes {', '.join(map(str, missing))} have no real frame in the run.",
                           "Put a frame (a still, a slide, a placeholder) for every scene (CA8)."))
    if not _in_run(run, data.get("placeholder_render")):
        out.append(Problem("placeholder_render", "The whole edit is not rendered with the placeholder take yet.",
                           "Render the edit with the placeholder take (the still with a slow zoom) before any paid "
                           "video."))
    videos = data.get("videos")
    if not isinstance(videos, list):
        return out + [Problem("videos", "videos lists the paid takes (an empty list for an ad without video).",
                              "Write the list.")]
    if not videos and not _text(data.get("no_video_reason")):
        out.append(Problem("videos", "No paid video is listed.", "List the takes, or say why the ad has none "
                           "(no_video_reason: slides that become animations)."))
    for n, v in enumerate(videos, 1):
        out.extend(_line_problems(run, cfg, v, n, "videos", today, kinds))
        if isinstance(v, dict) and not _text(v.get("prompt")):
            out.append(Problem(f"videos[{n}].prompt", f"{v.get('item')} has no exact prompt: the page shows the prompt "
                               "and the price the user says yes to.", "Write the prompt."))
        if isinstance(v, dict) and not _in_run(run, v.get("prompt_rules")) and not _text(v.get("prompt_rules")):
            out.append(Problem(f"videos[{n}].prompt_rules", f"{v.get('item')} names no prompting guide.",
                               "Read the model's prompting guide and name it (CA5)."))
        if isinstance(v, dict) and "speaks" in v and not isinstance(v["speaks"], bool):
            out.append(Problem(f"videos[{n}].speaks", f"{v.get('item')}'s speaks must be true (the take says the "
                               "lines) or false (its voice comes in the edit).", "Set it, or leave it out to follow "
                               "the voice route."))
    return out


# --- recording a check ----------------------------------------------------------

def _check_edit_qa(run: RunFolder, data: dict) -> list[Problem]:
    from tm import create_qa   # it reads this module's checked files
    return create_qa.check_edit(run, data)


CHECKS = {CONCEPTS: check_concepts, CLAIMS: check_claims, BOARD: check_board, PLAN: check_plan,
          STORYBOARD: check_storyboard, EDIT_QA: _check_edit_qa}


def check(run: RunFolder, stem: str, file: str | Path) -> tuple[str, list[Problem]]:
    """Check `file` as `stem`; a clean one is marked (and the plan or storyboard plans its money). Returns (its
    run-relative path, the problems)."""
    if stem not in CHECKS:
        raise ValueError(f"{stem!r} is not something tm ad check knows ({', '.join(CHECKS)}).")
    s = state.load(run)
    if s.playbook != CREATE_AD:
        raise ValueError("tm ad check is for Create an ad runs.")
    path = run.given(str(file))
    try:
        rel = path.resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        raise ValueError(f"{file} is not inside the run folder.") from None
    latest = run.latest(WIP, stem, "json")
    if latest is None or latest.resolve() != path.resolve():
        raise ValueError(f"{rel} is not the latest {WIP}/{stem}_vNN.json: check the latest version.")
    data, problems = _read(path)
    if data is None:
        return rel, problems
    problems = CHECKS[stem](run, data)
    if problems:
        return rel, problems
    stepchecks.mark(run, KEY[stem], path)
    if stem in (PLAN, STORYBOARD):
        plan = data if stem == PLAN else checked(run, PLAN)
        lines = plan_lines(plan, "pre_video") + (data.get("videos") or [] if stem == STORYBOARD else [])
        s = state.load(run)
        s.planned, s.planned_at = _totals(lines), flow._now()
        state.save(run, s)
    return rel, []


def _gap(run: RunFolder, stem: str) -> str | None:
    gap = stepchecks.fresh(run, KEY[stem], WIP, stem, "json")
    return f"{WHAT[stem]} pass tm ad check {stem.split('_')[-1] if stem == PLAN else stem} ({gap})" if gap else None


def concepts_gap(run: RunFolder) -> str | None:
    if state.load(run).evidence is None:
        return ("the evidence is recorded: tm evidence trendsmesh --run R --why <reason> when TrendsMesh answers, or "
                "tm evidence guess --run R --why <reason> without it")
    return _gap(run, CONCEPTS)


def claims_gap(run: RunFolder) -> str | None:
    return _gap(run, CLAIMS)


def board_gap(run: RunFolder) -> str | None:
    return _gap(run, BOARD)


def plan_gap(run: RunFolder) -> str | None:
    return _gap(run, PLAN)


def storyboard_gap(run: RunFolder) -> str | None:
    return _gap(run, STORYBOARD)


# --- the paid guard and the user's redo -----------------------------------------

def _stem(name: str) -> str:
    from tm.tools import _common as c
    return c.stem_of(name)


def _records(run: RunFolder, stem: str) -> list[dict]:
    from tm import organic_specs   # the shared reader of 03_wip/<stem>_vNN.run.json
    return [r for _, r in organic_specs.records(run, stem)]


def _latest_decision(s: state.RunState, cid: str) -> dict | None:
    return next((d for d in reversed(s.decisions) if d.get("checkin") == cid), None)


def _after(when: object, since: object) -> bool:
    try:
        return datetime.fromisoformat(str(when)) >= datetime.fromisoformat(str(since))
    except ValueError:
        return False


def guard(run: RunFolder, args: list[str]) -> str | None:
    """`tools.PRECHECK[CREATE_AD]["replicate_run"]`: None to let the paid call run, else the stop's message."""
    from tm import tools
    a = tools._parsed(args)
    if not a.name:
        return "Name the item with --name: it must be a line of the checked production plan or storyboard."
    stem = _stem(a.name)
    try:
        cost = float(a.cost)
    except (TypeError, ValueError):
        return "Give the line's cost with --cost."
    plan, board = checked(run, PLAN), checked(run, STORYBOARD)
    pre = {_stem(ln["item"]): ln for ln in plan_lines(plan, "pre_video") if _text(ln.get("item"))}
    videos = {_stem(v["item"]): v for v in (board or {}).get("videos") or [] if isinstance(v, dict)
              and _text(v.get("item"))}
    video_plan = {_stem(ln["item"]) for ln in plan_lines(plan, "video") if _text(ln.get("item"))}
    line = videos.get(stem) or pre.get(stem)
    if line is None:
        if stem in video_plan:
            return (f"{a.name} is a video: it runs only from the checked filled storyboard, with its exact prompt and "
                    "price, after the user's yes there. Nothing was run or spent.")
        return (f"{a.name} is not a line of the checked production plan or storyboard, so it is not run: a new item is "
                "a new plan version, checked and shown to the user. Nothing was spent.")
    if line.get("budget") != "ai_usd":
        return f"{a.name} spends {line.get('budget')}, not Replicate's USD: it is not a Replicate call."
    if abs(cost - float(line["cost"])) > TOL:
        return (f"--cost {cost:g} is not {a.name}'s line ({float(line['cost']):g} USD, price checked "
                f"{line.get('checked')}). Run it with its line's cost; another cost is a new version, checked and "
                "shown to the user.")
    s = state.load(run)
    if stem in videos:
        yes = _latest_decision(s, "storyboard")
        since = (s.checked.get(KEY[STORYBOARD]) or {}).get("at")
        if not (yes and yes.get("choice") == "approve" and _after(yes.get("at"), since)):
            return ("The paid video waits for the yes at \"Approve the filled storyboard and the paid video\", given "
                    "after the storyboard was last checked. Nothing was run or spent.")
        made = [r for r in _records(run, stem) if r.get("status") not in FAILED]
        if made:
            asks = [r for r in ((s.ad or {}).get("redos") or []) if r.get("item") == stem]
            if len(asks) < len(made):
                return NEVER.format(item=stem)
    return None


def redo(run: RunFolder, item: str, note: str) -> dict:
    """Record the user's request to make a video item again (`tm ad redo`): the guard then lets one more take run."""
    s = state.load(run)
    if s.playbook != CREATE_AD:
        raise ValueError("tm ad redo is for Create an ad runs.")
    if not _text(note):
        raise ValueError("--note holds the user's own words asking for the new take.")
    stem = _stem(item)
    videos = {_stem(v["item"]) for v in (checked(run, STORYBOARD) or {}).get("videos") or []
              if isinstance(v, dict) and _text(v.get("item"))}
    if stem not in videos:
        raise ValueError(f"{item} is not a video of the checked storyboard.")
    if not [r for r in _records(run, stem) if r.get("status") not in FAILED]:
        raise ValueError(f"{item} has no take yet, so its first run needs no request.")
    entry = {"item": stem, "note": note.strip(), "by": "user", "at": flow._now()}
    s.ad = {**(s.ad or {}), "redos": [*((s.ad or {}).get("redos") or []), entry]}
    state.save(run, s)
    return entry
