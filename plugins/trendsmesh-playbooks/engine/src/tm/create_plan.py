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

Costs (#93): a line may cover several calls (`"calls": N, "cost_per_call"`, N different prompts inside its approved
total); each call runs at the cost of one call, and no more than N run. A music line from ElevenLabs gives the seconds
of a take (`seconds`) and costs at least those seconds at the model's rate (`tm.music_models`, the dated table that
`tm ad prices` saves in the run as the line's price file). ElevenLabs' music takes and voice takes have their own
guard (`tools.PRECHECK[CREATE_AD]["elevenlabs"]`, `voice_guard`): the item is the line named by `--out
03_wip/audio/<item>_vNN.mp3`, the call runs at that line's cost, and a music plan whose seconds cost more than that at
the rate is refused before anything is sent. The spend on takes the user turned down is kept apart in run.json
(`ad.rejected`: per take, its item, budget kind and amount), booked by `tm ad redo` (the take it replaces) and `tm ad
reject` (a take not made again under its item, e.g. replaced by a new line); `tm ad costs` shows it on its own line.

Models (#98): a paid call runs only its line's model (Replicate's spec `model`, its owner optional and a pinned
version allowed; ElevenLabs' `--model`). A line made from the user's own words for a model keeps them in
`user_named`; when they do not name the line's model plainly (`names_model`: its words, in order), the call waits
for the user's answer to one short question ("Do you mean Seedance 2.0?"), kept in `model_confirmed`.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

from tm import config, create_config, flow, i18n, music_models, playbooks, state, stepchecks, tts_models
from tm.config import Problem
from tm.playbooks import CREATE_AD
from tm.runfolder import RunFolder, slug

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
AUDIO = f"{WIP}/audio"                         # ElevenLabs' takes: <item>_vNN.mp3 (or .wav), a music take's record beside
VOICE_HELD = ("music-compose", "tts")          # the ElevenLabs calls that make a plan line's take (voice_guard)
_AUDIO_TAKE = re.compile(r"^(?P<base>.+)_v(?P<n>\d+)\.(?:mp3|wav)(?P<record>\.json)?$")
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
        if tr["type"] == "sound" and tr.get("licence") not in ("ads", "inspiration"):
            out.append(Problem(f"trends[{n}]", "A sound trend is used in an ad only with a licence for ads.",
                               "Set licence: ads (licensed for ads) or inspiration (not used as the sound)."))
    concepts = data.get("concepts")
    concepts = concepts if isinstance(concepts, list) else []
    out.extend(_missing_cards(run, trends, concepts))
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


def _card_saved(run: RunFolder, tid: str) -> bool:
    """`02_research/trend_<id>.json`, or a later version of it (`tm trends ingest` never overwrites)."""
    folder = run.path / RESEARCH
    pattern = re.compile(rf"^trend_{re.escape(tid)}(?:_v\d+)?\.json$")
    return folder.is_dir() and any(pattern.match(p.name) for p in folder.iterdir() if p.is_file())


def _missing_cards(run: RunFolder, trends: list, concepts: list) -> list[Problem]:
    """#98 point 1: each TrendsMesh trend a concept uses has its card saved (S1), named when it is missing."""
    used = {t for cp in concepts if isinstance(cp, dict) and isinstance(cp.get("trends"), list) for t in cp["trends"]}
    out = []
    for n, tr in enumerate(trends, 1):
        if not (isinstance(tr, dict) and tr.get("source") == "trendsmesh" and _text(tr.get("id"))):
            continue
        if tr["id"] in used and not _card_saved(run, tr["id"]):
            out.append(Problem(f"trends[{n}]", f"Trend {tr['id']}'s trend card is not saved in the run: "
                               f"{RESEARCH}/trend_{tr['id']}.json is missing.",
                               "S1 saves the card of each trend a concept uses before this check: its get_trend "
                               f"answer, with tm trends ingest --run R --tool get_trend --input "
                               f"'{{\"trend_id\": \"{tr['id']}\"}}' --file <the answer> (flow.md S1, Trends)."))
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
    if "calls" in line:
        calls, each = line["calls"], line.get("cost_per_call")
        if not (isinstance(calls, int) and not isinstance(calls, bool) and calls >= 1):
            out.append(Problem(f"{where}[{n}].calls", f"{item}'s calls must be a whole number of paid calls, 1 or "
                               "more.", "Set calls, or leave it out for one call."))
        elif not (_number(each) and each > 0):
            out.append(Problem(f"{where}[{n}].cost_per_call", f"{item} covers {calls} calls but gives no cost a call.",
                               "Set cost_per_call: what one call costs."))
        elif _number(line.get("cost")) and calls * each > line["cost"] + TOL:
            out.append(Problem(f"{where}[{n}].cost", f"{item}'s {calls} calls at {each:g} cost "
                               f"{round(calls * each, 6):g}, more than the line's {line['cost']:g}.",
                               "Make the line's cost the calls' total."))
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
        out.extend(_music_problems(line, n))
    out.extend(presenter_problems(run, data, lines))
    return out


# --- the talking person: CA5's table, CA4's one take per speaker (issue #95) -------

PRESENTERS = {   # situation -> (a word of its take's model, what the casting gives it); rules.md CA5's table
    "described": ("seedance", "nothing: the face block"),
    "specific_person": ("h3", "the face"),
    "own_voice": ("h3", "the face"),
    "exact_wording": ("gemini-omni", "a reference"),
    "fallback": ("kling-avatar", "the face"),
}
NO_FACE = ("seedance",)   # refuses a photoreal face in its inputs (Replicate E005): no casting face can be used


def _names(lines: list[dict]) -> str:
    return ", ".join(str(ln.get("item")) for ln in lines)


def presenter_problems(run: RunFolder, data: dict, lines: list) -> list[Problem]:
    """The plan's talking person (lines of type presenter: the casting before the video, the takes at video): the
    situation of CA5's table named (`presenter.situation`) and its model used, unless the user picked another
    (`presenter.user_choice`); the fallback only with what the review showed (`presenter.why`); no paid casting for
    a model that cannot use the casting's face (Seedance); and one take per speaker whose lines fit one (CA4)."""
    talking = [ln for ln in lines if isinstance(ln, dict) and ln.get("type") == "presenter"]
    if not talking:
        return []
    takes = [ln for ln in talking if ln.get("stage") == "video"]
    casting = [ln for ln in talking if ln.get("stage") == "pre_video"]
    chosen = data.get("presenter") if isinstance(data.get("presenter"), dict) else {}
    situation, out = chosen.get("situation"), []
    if situation not in PRESENTERS:
        out.append(Problem("presenter.situation", "The plan makes a talking person, but names no situation of CA5's "
                           f"table ({', '.join(PRESENTERS)}).", "Ask the user which situation applies, before any "
                           "casting, and write presenter.situation (rules.md CA5)."))
    else:
        family = PRESENTERS[situation][0]
        for ln in takes:
            if family not in str(ln.get("model", "")).lower() and chosen.get("user_choice") is not True:
                out.append(Problem("presenter", f"CA5's table makes the presenter for {situation} with {family}, and "
                                   f"{ln.get('item')} uses {ln.get('model')}.", "Use the table's model, or write "
                                   "presenter.user_choice: true when the user picked another (suggest, never impose)."))
        if situation == "fallback" and not _text(chosen.get("why")):
            out.append(Problem("presenter.why", "The fallback (ElevenLabs + Kling Avatar v2) is only for a take the "
                               "review showed looks or sounds wrong.", "Write what the review showed (presenter.why), "
                               "or use the situation's own model."))
    faceless = [ln for ln in takes if any(m in str(ln.get("model", "")).lower() for m in NO_FACE)]
    if faceless and casting:
        out.append(Problem("lines", f"{_names(faceless)} is made with {faceless[0].get('model')}, which cannot use a "
                           "casting face (it refuses a photoreal face, E005), and the plan still pays for casting "
                           f"({_names(casting)}).", "Drop the casting: the person is cast from a description in the "
                           "prompt. Tell the user so before the casting (CA5)."))
    board = checked(run, BOARD) or {}
    said: dict[str, int] = {}
    for sc in board.get("scenes") or []:
        if isinstance(sc, dict) and _text(sc.get("line")):
            speaker = sc.get("speaker") or "voice"
            said[speaker] = said.get(speaker, 0) + _words(sc["line"])
    cfg = create_config.load(run)
    words_max, max_s = config.get(cfg, "take.words_max"), config.get(cfg, "take.max_s")
    for speaker, words in said.items():
        mine = [ln for ln in takes if ln.get("speaker") == speaker or (len(said) == 1 and not ln.get("speaker"))]
        if len(mine) > 1 and words <= words_max:
            out.append(Problem("lines", f"{speaker}'s lines ({words} words) fit one take (about {words_max} words, "
                               f"{max_s:g} s), and the plan makes {len(mine)} takes ({_names(mine)}): two generations "
                               "give two slightly different faces, voices and light.", "Make it one take, with the "
                               "cuts between places described in its prompt (\"selfie, then a hard cut to a whispered "
                               "close-up\"; CA4)."))
    return out


def _music_problems(line: dict, n: int) -> list[Problem]:
    """#93: an ElevenLabs music line gives a take's seconds and costs at least those seconds at the model's rate."""
    if line.get("type") != "music" or line.get("budget") != "voice_credits":
        return []
    item, model, seconds = line.get("item"), str(line.get("model")), line.get("seconds")
    if not (_number(seconds) and seconds > 0):
        return [Problem(f"lines[{n}].seconds", f"{item} gives no length: ElevenLabs prices music by the second.",
                        "Set seconds: how long one take is.")]
    need = music_models.credits(seconds, model)
    if _number(line.get("cost")) and _per_call(line) + TOL < need:
        return [Problem(f"lines[{n}].cost", f"{item} is priced at {_per_call(line):g} credits a take, but {seconds:g} s "
                        f"of {model} costs about {need} credits ({music_models.rate(model):g} a second, ElevenLabs' "
                        f"prices checked {music_models.CHECKED}).",
                        f"Price each take at {need} credits or more (tm ad prices saves the price file), and show the "
                        "user the new cost.")]
    return []


def _per_call(line: dict) -> float:
    """What one paid call of a line costs: its cost a call when it covers several (`calls`), else its cost."""
    each = line.get("cost_per_call")
    return float(each) if "calls" in line and _number(each) else float(line.get("cost") or 0)


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
    if abs(cost - _per_call(line)) > TOL:
        return _wrong_cost(a.name, cost, line, "USD")
    held = _model_held(a.name, _spec_model(run, a.spec), line)
    if held:
        return held
    s = state.load(run)
    made = [r for r in _records(run, stem) if r.get("status") not in FAILED]
    if stem not in videos and "calls" in line and len(made) >= line["calls"]:
        return i18n.t("ad.guard.calls_made", item=a.name, calls=line["calls"], made=len(made))
    if stem in videos:
        yes = _latest_decision(s, "storyboard")
        since = (s.checked.get(KEY[STORYBOARD]) or {}).get("at")
        if not (yes and yes.get("choice") == "approve" and _after(yes.get("at"), since)):
            return ("The paid video waits for the yes at \"Approve the filled storyboard and the paid video\", given "
                    "after the storyboard was last checked. Nothing was run or spent.")
        if made:
            asks = [r for r in ((s.ad or {}).get("redos") or []) if r.get("item") == stem]
            if len(made) >= (line.get("calls") if "calls" in line else 1) + len(asks):
                return NEVER.format(item=stem)
    return None


def _wrong_cost(name: str, cost: float, line: dict, unit: str) -> str:
    calls = f", {_per_call(line):g} a call for {line['calls']} calls" if "calls" in line else ""
    return (f"--cost {cost:g} is not {name}'s line ({_per_call(line):g} {unit}{calls}, price checked "
            f"{line.get('checked')}). Run it with its line's cost; another cost is a new version, checked and "
            "shown to the user.")


def _model_words(text: object) -> list[str]:
    return re.findall(r"[a-z]+|\d+", str(text or "").lower())


def _name(model: str) -> str:
    """A model id's own name: `owner/name:version` -> `name`."""
    return str(model).split(":", 1)[0].rsplit("/", 1)[-1]


def names_model(said: object, model: str) -> bool:
    """True when the user's words name `model` plainly: its name's words (or its whole id's), in order, among theirs
    ("Seedance 2.0 at 720p" names bytedance/seedance-2.0; "Gemini Sequence 2.0" does not)."""
    heard = _model_words(said)
    for want in (_model_words(_name(model)), _model_words(str(model).split(":", 1)[0])):
        if want and any(heard[i:i + len(want)] == want for i in range(len(heard) - len(want) + 1)):
            return True
    return False


def model_label(model: str) -> str:
    """How a model is named in the question to the user: `bytedance/seedance-2.0` -> `Seedance 2.0`; an id with
    underscores (ElevenLabs') as it is."""
    name = _name(model)
    if "_" in name:
        return name
    return " ".join(w[:1].upper() + w[1:] for w in name.split("-") if w)


def _spec_model(run: RunFolder, spec: str | None) -> str | None:
    """The model a Replicate spec runs, or None when it cannot be read (the tool then refuses it, spending nothing)."""
    if not _text(spec):
        return None
    try:
        data = json.loads(run.given(str(spec)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data.get("model") if isinstance(data, dict) and _text(data.get("model")) else None


def _same_model(given: str, line_model: str, owner: bool) -> bool:
    if given == line_model:
        return True
    if not owner:
        return False
    base = given.split(":", 1)[0]
    return line_model in (base, _name(given))


def _model_held(item: str, given: str | None, line: dict, owner: bool = True) -> str | None:
    """#98 point 2: the call runs the line's model, and a model the user named unplainly is confirmed first."""
    model = str(line.get("model"))
    if given is not None and not _same_model(str(given), model, owner):
        return i18n.t("ad.guard.model_differs", item=item, given=given, model=model)
    named = line.get("user_named")
    if _text(named) and not names_model(named, model) and not _text(line.get("model_confirmed")):
        return i18n.t("ad.guard.model_unclear", item=item, said=str(named).strip(), model=model,
                      label=model_label(model))
    return None


def _voice_args(args: list[str]):
    import argparse
    p = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    p.add_argument("action", nargs="?")
    for flag in ("--run", "--cost", "--out", "--model", "--plan"):
        p.add_argument(flag)
    try:
        return p.parse_known_args(args)[0]
    except SystemExit:
        return argparse.Namespace(action=None, run=None, cost=None, out=None, model=None, plan=None)


def _item_of_take(name: str) -> str:
    """The plan item a take's file is named after: `music_v02.mp3` -> `music`."""
    base = Path(name).name
    base = base[: -len(".json")] if base.endswith(".json") else base
    base = Path(base).stem
    m = re.match(r"^(.*)_v\d+$", base)
    return slug(m.group(1) if m else base)


def _music_plan(run: RunFolder, value: str | None) -> object:
    if not value:
        return None
    text = value.strip()
    try:
        if text[:1] in ("{", "["):
            return json.loads(text)
        return json.loads(run.given(text).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def voice_guard(run: RunFolder, args: list[str]) -> str | None:
    """`tools.PRECHECK[CREATE_AD]["elevenlabs"]` (#93): a music take or a voice take is a line of the checked production
    plan (named by `--out 03_wip/audio/<item>_vNN.mp3`), runs at that line's cost while its calls last, and a music
    plan whose seconds cost more than the line at the model's rate is refused before anything is sent. Other
    ElevenLabs calls (isolation, a clone, an upload) are not held here. None to let the call run, else the stop."""
    a = _voice_args(args)
    if a.action not in VOICE_HELD:
        return None
    if not _text(a.out):
        return i18n.t("ad.guard.voice_out")
    stem = _item_of_take(a.out)
    try:
        cost = float(a.cost)
    except (TypeError, ValueError):
        return "Give the line's cost with --cost."
    lines = {_stem(ln["item"]): ln for ln in plan_lines(checked(run, PLAN), "pre_video") if _text(ln.get("item"))}
    line = lines.get(stem)
    if line is None:
        return i18n.t("ad.guard.voice_not_line", item=stem)
    if line.get("budget") != "voice_credits":
        return f"{stem} spends {line.get('budget')}, not ElevenLabs credits: it is not an ElevenLabs call."
    if abs(cost - _per_call(line)) > TOL:
        return _wrong_cost(stem, cost, line, "credits")
    default = music_models.DEFAULT if a.action == "music-compose" else tts_models.DEFAULT
    held = _model_held(stem, a.model or default, line, owner=False)
    if held:
        return held
    made = _audio_takes(run, stem)
    if "calls" in line and len(made) >= line["calls"]:
        return i18n.t("ad.guard.calls_made", item=stem, calls=line["calls"], made=len(made))
    if a.action == "music-compose":
        model = a.model or music_models.DEFAULT
        plan = _music_plan(run, a.plan)
        if plan is None:
            return f"The music plan ({a.plan}) cannot be read, so nothing was sent or spent."
        shape = music_models.plan_problems(plan, model)
        if shape:
            return " ".join(shape) + " Nothing was sent or spent."
        seconds = music_models.plan_seconds(plan)
        need = music_models.credits(seconds, model)
        if need > cost + TOL:
            return i18n.t("ad.guard.music_rate", seconds=f"{seconds:g}", rate=f"{music_models.rate(model):g}",
                          model=model, checked=music_models.CHECKED, need=need, item=stem, cost=f"{cost:g}")
    return None


# --- takes, the spend on rejected ones, and the costs ------------------------------

def _audio_takes(run: RunFolder, stem: str) -> list[tuple[str, float | None]]:
    """The ElevenLabs takes of an item, oldest first: (the take, run-relative; what it cost when its record says)."""
    folder = run.path / AUDIO
    if not folder.is_dir():
        return []
    names = {p.name for p in folder.iterdir() if p.is_file()}
    found = []
    for name in names:
        m = _AUDIO_TAKE.match(name)
        if not m or slug(m.group("base")) != stem:
            continue
        if m.group("record"):    # a music take's record (pending or done): the take is paid
            try:
                data = json.loads((folder / name).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            used = data.get("credits_used") if isinstance(data, dict) else None
            found.append((int(m.group("n")), f"{AUDIO}/{name[: -len('.json')]}", float(used) if _number(used) else None))
        elif name + ".json" not in names:   # a voice take (it has no record)
            found.append((int(m.group("n")), f"{AUDIO}/{name}", None))
    return [(take, used) for _, take, used in sorted(found)]


def _runs(run: RunFolder, stem: str) -> list[tuple[str, float | None]]:
    """An item's Replicate runs that did not end without a result (each is paid), oldest first."""
    from tm import organic_specs   # the shared reader of 03_wip/<stem>_vNN.run.json
    return [(f"{WIP}/{path.name}", None) for path, r in organic_specs.records(run, stem) if r.get("status") not in FAILED]


def _takes(run: RunFolder, stem: str) -> list[tuple[str, float | None]]:
    """Every paid take of an item: its Replicate runs and its ElevenLabs takes."""
    return _runs(run, stem) + _audio_takes(run, stem)


def _line_for(run: RunFolder, stem: str) -> dict | None:
    """The item's line: in the checked storyboard or plan, else in the newest earlier version that has it (a line a
    new plan dropped keeps its price)."""
    for data in (checked(run, STORYBOARD), checked(run, PLAN)):
        for ln in [*((data or {}).get("videos") or []), *((data or {}).get("lines") or [])]:
            if isinstance(ln, dict) and _text(ln.get("item")) and _stem(ln["item"]) == stem:
                return ln
    folder, versions = run.path / WIP, []
    for path in folder.glob("*.json") if folder.is_dir() else []:
        m = re.match(rf"^({STORYBOARD}|{PLAN})_v(\d+)\.json$", path.name)
        if m:
            versions.append((m.group(1) == STORYBOARD, int(m.group(2)), path))
    for _, _, path in sorted(versions, reverse=True):   # the storyboards, then the plans, newest first
        data = _read(path)[0] or {}
        for ln in [*(data.get("videos") or []), *(data.get("lines") or [])]:
            if isinstance(ln, dict) and _text(ln.get("item")) and _stem(ln["item"]) == stem:
                return ln
    return None


def _book(s: state.RunState, stem: str, takes: list[tuple[str, float | None]], line: dict, note: str) -> list[dict]:
    """Book each take not booked yet as rejected spend, at what it cost (its record) or its line's cost a call."""
    rejected = list((s.ad or {}).get("rejected") or [])
    booked = {r.get("take") for r in rejected}
    new = [{"item": stem, "take": take, "kind": line.get("budget"),
            "amount": round(used if used is not None else _per_call(line), 6), "note": note.strip(), "by": "user",
            "at": flow._now()} for take, used in takes if take not in booked]
    s.ad = {**(s.ad or {}), "rejected": [*rejected, *new]}
    return new


def reject(run: RunFolder, item: str, note: str) -> list[dict]:
    """`tm ad reject`: the user turned down an item's takes (and it is not made again under that item, e.g. a new line
    replaces it). Each paid take not booked yet goes to the rejected spend; returns what was booked."""
    s = state.load(run)
    if s.playbook != CREATE_AD:
        raise ValueError("tm ad reject is for Create an ad runs.")
    if not _text(note):
        raise ValueError("--note holds the user's own words turning the take down.")
    stem = _stem(item)
    takes = _takes(run, stem)
    if not takes:
        raise ValueError(f"{item} has no paid take, so nothing is booked.")
    line = _line_for(run, stem)
    if line is None:
        raise ValueError(f"{item} is not a line of any production plan or storyboard of the run, so its cost is unknown.")
    new = _book(s, stem, takes, line, note)
    state.save(run, s)
    return new


def rejected_totals(s: state.RunState) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in (s.ad or {}).get("rejected") or []:
        if isinstance(r, dict) and _number(r.get("amount")) and r.get("kind"):
            out[r["kind"]] = round(out.get(r["kind"], 0.0) + float(r["amount"]), 6)
    return out


def costs(run: RunFolder) -> dict:
    """What each budget kind has approved, planned and spent, and the part of the spend that went to rejected takes."""
    s = state.load(run)
    rejected = rejected_totals(s)
    kinds = {k: {"approved": float(s.budgets.get(k, 0.0)), "planned": float(s.planned.get(k, 0.0)),
                 "spent": float(s.spend.get(k, 0.0)), "rejected": rejected.get(k, 0.0)}
             for k in playbooks.get(CREATE_AD).budgets}
    return {"kinds": kinds, "rejected": list((s.ad or {}).get("rejected") or [])}


def costs_text(data: dict) -> str:
    out = []
    for kind, v in data["kinds"].items():
        out.append(i18n.t("ad.costs.kind", service=i18n.t(f"ad.costs.service.{kind}"), spent=f"{v['spent']:g}",
                          approved=f"{v['approved']:g}", planned=f"{v['planned']:g}"))
        takes = [r for r in data["rejected"] if r.get("kind") == kind]
        out.append(i18n.t("ad.costs.rejected", amount=f"{v['rejected']:g}", n=len(takes),
                          items=", ".join(sorted({str(r.get("item")) for r in takes})) or "-"))
    return "\n".join(out)


def prices(run: RunFolder, today: date | None = None) -> tuple[str, str]:
    """`tm ad prices`: save ElevenLabs' dated price table (music by the second, voice by the character) as
    02_research/elevenlabs_prices_vNN.json, the price file of a plan's ElevenLabs lines. (its path, today)."""
    from tm import manifest
    when = (today or date.today()).isoformat()
    target = run.next_version(RESEARCH, "elevenlabs_prices", "json")
    data = {"checked": when, "music": music_models.table(),
            "tts": {"checked": tts_models.CHECKED, "unit": "credits a character", "default": tts_models.DEFAULT,
                    "models": {m: {"credits_per_char": v.credits_per_char, "source": v.source}
                               for m, v in tts_models.MODELS.items()},
                    "other_models": tts_models.GENERAL_RATE}}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rel = target.relative_to(run.path).as_posix()
    manifest.record(run, rel, "research", "ElevenLabs prices (the plugin's dated table)", cost="free")
    return rel, when


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
    made = _runs(run, stem)
    if not made:
        raise ValueError(f"{item} has no take yet, so its first run needs no request.")
    entry = {"item": stem, "note": note.strip(), "by": "user", "at": flow._now()}
    s.ad = {**(s.ad or {}), "redos": [*((s.ad or {}).get("redos") or []), entry]}
    booked = _book(s, stem, made[-1:], _line_for(run, stem) or {}, note)   # the take this one replaces (#93)
    state.save(run, s)
    return {**entry, "rejected": sum(b["amount"] for b in booked)}
