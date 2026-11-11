"""config.yaml of a Create an ad run (playbook 05): its schema, written from S0's intake, its validation and the
`ad_intake_written` step check. `tm config` hands a Create an ad run here.

The schema is the spec's "Config" table (issue #17) plus the plugin's own settings. As in the other playbooks, the
config changes thresholds, never a rule: a key that is not in the schema fails validation, and so does a changed
fixed value (the generation provider).

The intake (S0, CA1) asks four questions, each with options pre-filled from the site, the config and earlier runs:
1. who the ad is for and what they make or do (`brand.persona.who`, `brand.persona.makes`);
2. what the ad sells (`intake.sells.kind`, one of SELLS, and `intake.sells.what`);
3. the length and the placements (`intake.length_s` [low, high], `intake.placements`);
4. existing materials: the asset inventory, `03_wip/assets_vNN.json` (`ASSETS_STEM`), checked by `intake_gap`.
`intake.live` says whether what is sold is live; when it is not (early access, a waitlist), `intake.not_live` says
what it is, and nothing that is not live may be promised (CA1, CA3).

The run's two languages are `languages: {working, market}` (tm.i18n, issue #3; references/languages.md), shown on
the intake card from their defaults: the cards and pages follow the working language, the ad's copy, voice-over,
captions and on-screen text the market language.

Intake-only answers, not kept in config.yaml: `level` (run.json; `mode` follows it: Hands-off is `auto`) and
`outputs` (always `video_ad`). Hands-off spends only inside the budgets the intake gives (CA7): they are approved
here, as Refresh an ad's are. The Meta ad budget (`budget.daily_ad_spend`) is never a default and never approved
here: the upload proposal takes the amount and the cadence from the user's own words (CA14).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from urllib.parse import urlparse

from tm import budget, config, flow, i18n, state
from tm.config import Problem
from tm.runfolder import RunFolder

ISSUES = "https://github.com/TrendsMesh/trendsmesh-playbooks/issues"
OUTPUT = "video_ad"
WIP = "03_wip"
ASSETS_STEM = "assets"
SELLS = ("product", "feature", "process", "offer")
PLACEMENTS = ("reels", "stories", "feed", "advantage_plus")
# The asset types of a production plan (S5) and of `models.<asset_type>` (CA5).
ASSET_TYPES = ("presenter", "hook_scene", "product_shot", "still", "slide", "animation", "music", "sfx",
               "voice", "upscale", "transcription")
ASSET_KINDS = ("music", "voiceover", "footage", "broll", "product_shot", "logo", "brand_guide", "past_ad",
               "earlier_run")
MODES = {"hands_off": "auto"}  # the level -> the spec's mode; any other level is hitl
BUDGETS = {"ai_usd": "generation_usd", "voice_credits": "voice_credits"}  # budget kind -> its budget.* key

DEFAULTS: dict = {
    "brand": {"product": None, "url": None, "persona": {"who": None, "makes": None}},
    "languages": {"working": None, "market": None},   # tm.i18n: BCP 47 tags (issue #3)
    "intake": {"sells": {"kind": None, "what": None}, "length_s": None, "placements": None, "live": None,
               "not_live": None},
    "meta": {"ad_account_id": None, "page_id": None, "dataset_id": None},
    "mode": "hitl",
    "budget": {"generation_usd": None, "voice_credits": None, "daily_ad_spend": None},
    "generation": {"provider": "replicate"},
    "models": {},  # asset type -> the model the user confirmed for it (ASSET_TYPES)
    "audio": {"music_source": None, "transition_sound": None},
    "currency": "USD",
    "fx_rate": None,
    "pricing": {"max_age_days": 7},
    "take": {"max_s": 15, "words_max": 45},
    "copy": {"count": 5, "primary_max": 125, "headline_max": 40, "description_max": 30},
    "qa": {"lufs_target": -14, "true_peak_max": -1.5},
}

FIXED = {"generation.provider": ("replicate", "{name} is not supported yet: generation uses Replicate (tracked at "
                                              + ISSUES + ")")}
CHOICES = {"mode": ("hitl", "auto")}
_COUNT = (True, 1, None, True, True)
_ABOVE0 = (False, 0, None, False, True)
NUMBERS = {
    "budget.generation_usd": _ABOVE0,
    "budget.voice_credits": _ABOVE0,
    "budget.daily_ad_spend": _ABOVE0,
    "fx_rate": _ABOVE0,
    "pricing.max_age_days": _COUNT,
    "take.max_s": _ABOVE0,
    "take.words_max": _COUNT,
    "copy.count": (True, 1, 5, True, True),
    "copy.primary_max": _COUNT,
    "copy.headline_max": _COUNT,
    "copy.description_max": _COUNT,
    "qa.lufs_target": (False, -70, 0, True, False),
    "qa.true_peak_max": (False, -20, 0, True, True),
}
LENGTH = (False, 3, 180, True, True)  # seconds, each end of intake.length_s


def defaults() -> dict:
    return copy.deepcopy(DEFAULTS)


# --- writing ----------------------------------------------------------------------

def write_from_intake(run: RunFolder, answers: dict) -> Path:
    """Write config.yaml from S0's intake answers; set the level and the output in run.json; in Hands-off approve
    the intake's budgets (CA7). Problems are not raised here: `validate` lists them. Not allowed once S0 is done."""
    s = state.load(run)
    if s.step not in (None, "S0"):
        raise ValueError("The intake is already done, so the config is not rewritten. Budgets change with "
                         "`tm budget approve`.")
    answers = copy.deepcopy(answers)
    level = answers.pop("level", None) or s.level
    outputs = answers.pop("outputs", [OUTPUT])
    if outputs != [OUTPUT]:
        raise ValueError(f"outputs must be [\"{OUTPUT}\"]: a Create an ad run makes one video ad.")
    cfg = i18n.settle(config._merge(defaults(), answers))
    if level is not None:
        cfg["mode"] = MODES.get(level, "hitl")
    if cfg["meta"].get("ad_account_id") is not None:
        cfg["meta"]["ad_account_id"] = str(cfg["meta"]["ad_account_id"])
    if level is not None:
        flow.set_level(run, level)  # refuses an unknown level before anything is written
    s = state.load(run)
    s.outputs = [OUTPUT]
    state.save(run, s)
    path = config.save(run, cfg)
    if level == "hands_off":
        for kind, key in BUDGETS.items():
            amount = cfg["budget"].get(key)
            if config.in_range(amount, _ABOVE0):
                budget.approve_from_intake(run, kind, amount, "the budget given at intake (Hands-off)")
    return path


# --- validation -------------------------------------------------------------------

def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _need(out: list[Problem], cfg: dict, path: str, what: str) -> None:
    if not _text(config.get(cfg, path)):
        out.append(Problem(path, f"{what} is missing.", "Ask the user (the intake's question, with options)."))


def _intake(out: list[Problem], cfg: dict) -> None:
    _need(out, cfg, "brand.product", "The product")
    url = config.get(cfg, "brand.url")
    if not (_text(url) and urlparse(url).scheme in ("http", "https") and urlparse(url).netloc):
        out.append(Problem("brand.url", f"brand.url must be the product site's address (https://...), not {url!r}.",
                           "Ask the user for the product's site."))
    _need(out, cfg, "brand.persona.who", "Who the ad is for (question 1)")
    _need(out, cfg, "brand.persona.makes", "What the people the ad is for make or do (question 1)")
    kind = config.get(cfg, "intake.sells.kind")
    if kind not in SELLS:
        out.append(Problem("intake.sells.kind", f"What the ad sells must be one of {', '.join(SELLS)}, not {kind!r} "
                           "(question 2).", "Ask the user what the ad sells."))
    _need(out, cfg, "intake.sells.what", "What exactly the ad sells (question 2)")
    length = config.get(cfg, "intake.length_s")
    if not (isinstance(length, list) and len(length) == 2 and all(config.in_range(v, LENGTH) for v in length)
            and length[0] <= length[1]):
        out.append(Problem("intake.length_s", f"The length must be [shortest, longest] in seconds, from 3 to 180, not "
                           f"{length!r} (question 3: a decision, not something that comes out of the script).",
                           "Ask the user for the length."))
    places = config.get(cfg, "intake.placements")
    if not (isinstance(places, list) and places and all(p in PLACEMENTS for p in places)
            and len(set(places)) == len(places)):
        out.append(Problem("intake.placements", f"The placements must be one or more of {', '.join(PLACEMENTS)}, "
                           f"each once, not {places!r} (question 3).", "Ask the user for the placements."))
    live = config.get(cfg, "intake.live")
    if not isinstance(live, bool):
        out.append(Problem("intake.live", "Whether what the ad sells is live yet is missing.",
                           "Check the site, and ask the user when it does not say."))
    elif not live and not _text(config.get(cfg, "intake.not_live")):
        out.append(Problem("intake.not_live", "What the ad sells is not live: say what it is (early access, a "
                           "waitlist), so nothing that is not live is promised.", "Ask the user and write it."))


def _models(out: list[Problem], cfg: dict) -> None:
    models = cfg.get("models")
    if not isinstance(models, dict):
        out.append(Problem("models", "models must map asset types to models.", "Put it back as a group."))
        return
    for key, value in models.items():
        if key not in ASSET_TYPES:
            out.append(Problem(f"models.{key}", f"{key} is not an asset type ({', '.join(ASSET_TYPES)}).",
                               f"Remove models.{key}."))
        elif not _text(value):
            out.append(Problem(f"models.{key}", f"models.{key} must name a model.", "Correct it."))


def validate(run: RunFolder) -> list[Problem]:
    """Everything wrong or missing in config.yaml, each with what to do. Empty means ready."""
    try:
        cfg = config.load(run)
    except ValueError as exc:
        return [Problem(config.FILE, str(exc), "Answer the intake questions so the config can be written.")]
    out: list[Problem] = []
    schema = {**DEFAULTS, "models": None}  # models' keys are checked by _models
    config._unknown_keys(cfg, schema, "", out)
    for path, (fixed, why) in FIXED.items():
        value = config.get(cfg, path)
        if value is not None and value != fixed:
            out.append(Problem(path, why.format(name=str(value).capitalize()) + ".", f"Set {path} to {fixed}."))
    for path, allowed in CHOICES.items():
        if config.get(cfg, path) not in allowed:
            out.append(Problem(path, f"{path} must be one of {', '.join(allowed)}.", "Correct it."))
    for path, spec in NUMBERS.items():
        value = config.get(cfg, path)
        if value is not None and not config.in_range(value, spec):
            out.append(config.range_problem(path, value, spec))
    _intake(out, cfg)
    _models(out, cfg)
    out += i18n.config_problems(cfg)    # both languages, as tags: the working one for the cards, the market one for the ad
    currency = cfg.get("currency")
    if not (isinstance(currency, str) and len(currency) == 3 and currency.isalpha() and currency.isupper()):
        out.append(Problem("currency", f"currency must be a three-letter code such as USD or PLN, not {currency!r}.",
                           "Ask the user the ad account's currency."))
    elif currency != "USD" and cfg.get("fx_rate") is None:
        out.append(Problem("fx_rate", f"Money is shown in USD with the rate for a {currency} account, and the rate "
                           "is missing.", f"Set fx_rate: how many {currency} one USD buys."))
    if state.load(run).level == "hands_off" and config.get(cfg, "budget.generation_usd") is None:
        out.append(Problem("budget.generation_usd", "Hands-off spends only inside the budget given at intake, and the "
                           "generation budget is missing.", "Ask the user for the generation budget in USD."))
    return out


def load(run: RunFolder) -> dict:
    """The run's config merged over the defaults (a key the file lacks reads as its default)."""
    return config._merge(defaults(), config.load(run))


# --- the asset inventory and the ad_intake_written step check ------------------------

def inventory_problems(path: Path) -> list[str]:
    """What is wrong with an asset inventory (question 4): {"earlier_runs_checked": true, "assets": [{"file",
    "kind", "usable", "replaces"}]}. `replaces` is the asset type a usable file removes from generation, or null."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{path.name} cannot be read as JSON ({exc})"]
    if not isinstance(data, dict):
        return [f"{path.name} must hold one JSON object"]
    out = []
    if data.get("earlier_runs_checked") is not True:
        out.append("earlier_runs_checked is true: the earlier runs of the brand were checked for reusable files")
    assets = data.get("assets")
    if not isinstance(assets, list):
        return out + ["assets lists the user's files (an empty list when there are none)"]
    for n, a in enumerate(assets, 1):
        if not (isinstance(a, dict) and _text(a.get("file")) and a.get("kind") in ASSET_KINDS
                and isinstance(a.get("usable"), bool)):
            out.append(f"asset {n} has a file, a kind ({', '.join(ASSET_KINDS)}) and usable true or false")
            continue
        replaces = a.get("replaces")
        if replaces is not None and (replaces not in ASSET_TYPES or not a["usable"]):
            out.append(f"asset {n} ({a['file']}) replaces an asset type ({', '.join(ASSET_TYPES)}) only when usable")
    return out


def intake_gap(run: RunFolder) -> str | None:
    """S0 is done once config.yaml validates and the asset inventory is written. Reads only. The gaps, or None."""
    gaps = []
    problems = validate(run)
    if problems:
        gaps.append(f"config.yaml passes tm config check ({'; '.join(p.field for p in problems)})")
    inventory = run.latest(WIP, ASSETS_STEM, "json")
    if inventory is None:
        gaps.append(f"the asset inventory is written ({WIP}/{ASSETS_STEM}_vNN.json, question 4)")
    else:
        gaps.extend(inventory_problems(inventory))
    return ", and ".join(gaps) or None


def page_words(run: RunFolder) -> tuple[i18n.Translator, i18n.PageLang]:
    """The words of Create an ad's cards and pages (the `ad` area of data/i18n/en.yaml) in the run's working language,
    or in English with the warning to show the user when that language has no translation of them yet."""
    built = i18n.page_lang(i18n.run_languages(run).working, "ad")
    return i18n.translator(built.lang), built
