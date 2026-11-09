"""config.yaml of an organic video run (playbook 03): its schema, written from A0's one batch of intake
answers, its validation and the `organic_intake_written` step check. `tm config` hands an organic video
run here.

The schema is PLAYBOOK.md §7 with the numbers of OV1-OV14 named one by one (the plan's Global
Constraints), plus the plugin's own settings. PLAYBOOK.md §7's `channel`, `context`, `catalog`, `voice`
and `music` are per channel: they live in the channel profile (`tm brand`, `channel/1`) and the
store's brand profile, and the config names the run's channels by slug (`channels`). As in the other
playbooks, the config changes thresholds, never a rule: a key that is not in the schema fails
validation, and so does a changed fixed value (the generation provider, the publishing tool).

The intake (A0, preflight P3-F2) also takes intake-only answers that are not kept in config.yaml:
- `level`, set with `flow.set_level`. The level wins: an answer's `level`, else the one already set
  with `tm level`, else `mode.variant`'s (gated is Check every step, az is Hands-off). `mode.variant`
  is then written from the level (az for Hands-off, else gated), the spec's word for the reference pages;
  a variant other than gated or az is refused. That write is lossy (Just the big calls is written as
  gated, which reads back as Check every step), so `mode.variant` is for display only: the level
  lives in run.json (`level`), and anything that needs it (the pages, Task 7) reads it there;
- `outputs`, the run kind, `proposals` (an idea run) or `weekly_plan` (a week run), kept in run.json;
  the config's `kind` follows it (`production` runs are started from an idea or a week slot);
- `chat_language` and `audience_language`, which decide `page_lang`: pages are built in the chat
  language when it is English or Polish, otherwise in English with `page_lang_note`.
"""

from __future__ import annotations

import copy
from pathlib import Path

from tm import brand, config, flow, state, trend_spool
from tm.config import Problem
from tm.runfolder import RunFolder

ISSUES = "https://github.com/TrendsMesh/trendsmesh-playbooks/issues"
OUTPUTS_READY: tuple[str, ...] = ("script", "ai_video", "weekly_pack")  # the plan's decision 18: all built (PR E)
OUTPUT_WORDS = {"script": "A script to film", "ai_video": "An AI video", "weekly_pack": "The weekly pack"}
RUN_KINDS = {"proposals": "proposals", "weekly_plan": "weekly_plan"}  # the intake's outputs -> config kind
NEEDS_OUTPUT = {"weekly_plan": "weekly_pack"}  # an intake run kind -> the output that must be ready for it
VARIANT_LEVEL = {"gated": "every_step", "az": "hands_off"}  # PLAYBOOK.md mode.variant -> the plugin's level
PAGE_LANGS = ("en", "pl")
LANGUAGE_NAMES = {"en": "English", "pl": "Polish", "de": "German", "fr": "French", "es": "Spanish",
                  "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "cs": "Czech", "uk": "Ukrainian"}
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
GATES = ("pack", "images", "video", "edit")

DEFAULTS: dict = {
    "channels": [],  # slugs of the channel profiles this run is for (library/channels/<slug>/)
    "platforms": None,  # a production run's platforms, from its proposal's decision (null: the channel profile's)
    "kind": "proposals",
    "output": "script",
    "weekly": {"contents": None, "per_week": 5, "days": ["mon", "wed", "fri", "sat", "sun"],
               "flexible_day": "sun", "run_day": "sun", "rhythm": "all_at_once"},
    "generation": {"provider": "replicate", "quality_tier": "default", "resolution": "768p", "upscale": "none"},
    "mode": {"variant": "gated", "gates": list(GATES)},
    "budget": {"per_run_usd": 5, "per_week_usd": 5},
    "publishing": {"tool": "none"},
    "page_lang": "en",
    "page_lang_note": None,
    "currency": "USD",
    "fx_rate": None,
    "pricing": {"max_age_days": 7},
    "qa": {"transcript_min": 0.9, "wps_min": 2.8, "wps_max": 3.0, "tail_s": 1.5, "speed_max": 1.25,
           "take_max_s": 15, "lufs_target": -14, "lufs_asmr": -16, "lufs_usable": [-30, -5],
           "cut_flag_s": 1.0, "upload_max_mb": 15, "preview_crf": 27, "upload_crf": [26, 28]},
    "safe_zone": {"x": [90, 880], "y": [260, 1540], "atlas_text_max_y": 1260},
    "proposals": {"min": 4, "max": 6},
    "research": {"cards": 12, "recent_days": 7},
    "animation": {"fps": 30},
}

FIXED = {  # rules, not thresholds: path -> (the fixed value, why another value is refused)
    "generation.provider": ("replicate", "{name} is not supported yet: generation uses Replicate (tracked at "
                                         + ISSUES + ")"),
    "publishing.tool": ("none", "Posting through a tool is not supported yet: you download from the page and "
                                "post (tracked at " + ISSUES + ")"),
}
CHOICES = {
    "kind": ("proposals", "weekly_plan", "production"),
    "output": tuple(OUTPUT_WORDS),
    "weekly.flexible_day": WEEKDAYS,
    "weekly.run_day": WEEKDAYS,
    "weekly.rhythm": ("all_at_once",),
    "generation.quality_tier": ("budget", "default", "top"),
    "generation.resolution": ("720p", "768p", "1080p"),  # OV8: 720p (768P on H3) or 1080p; upscale apart
    "generation.upscale": ("none", "pruna"),
    "mode.variant": tuple(VARIANT_LEVEL),
}
OPTIONAL_CHOICES = {"weekly.contents": ("scripts", "videos", "mix")}  # asked only for the weekly pack
SUBSETS = {"weekly.days": WEEKDAYS, "mode.gates": GATES, "platforms": brand.PLATFORMS}
_COUNT = (True, 1, None, True, True)  # a whole number from 1
_ABOVE0 = (False, 0, None, False, True)
_FROM0 = (False, 0, None, True, True)
_LUFS = (False, -70, 0, True, False)  # loudness, below 0
_CRF = (True, 0, 51, True, True)  # H.264
NUMBERS = {  # path: (integer?, lowest, highest, lowest allowed?, highest allowed?), as in config
    "weekly.per_week": (True, 1, 7, True, True),
    "budget.per_run_usd": _ABOVE0,
    "budget.per_week_usd": _ABOVE0,
    "fx_rate": _ABOVE0,
    "pricing.max_age_days": _COUNT,
    "qa.transcript_min": (False, 0, 1, False, True),
    "qa.wps_min": _ABOVE0,
    "qa.wps_max": _ABOVE0,
    "qa.tail_s": _FROM0,
    "qa.speed_max": (False, 1, None, True, True),
    "qa.take_max_s": _ABOVE0,
    "qa.lufs_target": _LUFS,
    "qa.lufs_asmr": _LUFS,
    "qa.cut_flag_s": _ABOVE0,
    "qa.upload_max_mb": _ABOVE0,
    "qa.preview_crf": _CRF,
    "safe_zone.atlas_text_max_y": (True, 0, 1920, True, True),
    "proposals.min": _COUNT,
    "proposals.max": _COUNT,
    "research.cards": _COUNT,
    "research.recent_days": _COUNT,
    "animation.fps": _COUNT,
}
RANGES = {  # path: the spec of both ends, [low, high] with low below high
    "qa.lufs_usable": (False, -70, 0, True, True),
    "qa.upload_crf": _CRF,
    "safe_zone.x": (True, 0, 1080, True, True),
    "safe_zone.y": (True, 0, 1920, True, True),
}
ORDERED = (("qa.wps_min", "qa.wps_max"), ("proposals.min", "proposals.max"))  # low at most high


def defaults() -> dict:
    return copy.deepcopy(DEFAULTS)


# --- writing ----------------------------------------------------------------------

def _intake_open(s: state.RunState) -> None:
    if s.step not in (None, "A0"):  # the intake is A0's (preflight P3-F2)
        raise ValueError("The intake is already done, so the config is not rewritten.")


def _outputs(outputs: object) -> list[str]:
    """The run kind the intake chose: one of proposals or weekly_plan, ready in this release."""
    if not (isinstance(outputs, list) and len(outputs) == 1 and outputs[0] in RUN_KINDS):
        raise ValueError(f"outputs must be one of: {', '.join(RUN_KINDS)} (an idea run or a week run; "
                         "a production run is started from an idea or a week slot).")
    needs = NEEDS_OUTPUT.get(outputs[0])
    if needs and needs not in OUTPUTS_READY:
        raise ValueError(f"{OUTPUT_WORDS[needs]} is not built yet: it arrives in a later version of the plugin. Start an "
                         f"idea run (outputs [\"proposals\"]) instead; each picked idea can become "
                         f"{OUTPUT_WORDS[OUTPUTS_READY[0]].lower()}.")
    return list(outputs)


def _language(value: object) -> str | None:
    """`pl`, `PL`, `pl-PL` -> `pl`; None when nothing is given."""
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().replace("_", "-").split("-")[0].lower()


def _audience_language(run: RunFolder, given: object, channels: object) -> str | None:
    """The answers' audience language, else the first channel's saved profile's."""
    if _language(given):
        return _language(given)
    workspace = trend_spool.workspace_of(run)
    for slug in channels if isinstance(channels, list) else []:
        try:
            profile = brand.latest(workspace, str(slug), kind="channel")
        except ValueError:  # a damaged library file: the note names no language
            return None
        if profile and _language(profile.get("audience_language")):
            return _language(profile.get("audience_language"))
    return None


def _page_lang(cfg: dict, chat: str | None, audience: str | None) -> None:
    if chat is None:
        return
    if chat in PAGE_LANGS:
        cfg["page_lang"], cfg["page_lang_note"] = chat, None
        return
    said = LANGUAGE_NAMES.get(audience, audience) if audience else "the audience's language"
    cfg["page_lang"] = "en"
    cfg["page_lang_note"] = f"Pages are built in English; post text stays in {said}."


def write_from_intake(run: RunFolder, answers: dict) -> Path:
    """Write config.yaml from A0's intake answers and set the level and outputs in run.json.

    `answers` has the config's shape (`channels`, `output`, `generation`, `budget`, ...) plus the
    intake-only `level`, `outputs`, `chat_language` and `audience_language` (module docstring).
    Anything it leaves out gets the default. Channel names are kept as slugs. Problems are not raised
    here: `validate` lists them. Not allowed once A0 is done.
    """
    s = state.load(run)
    _intake_open(s)
    answers = copy.deepcopy(answers)
    level = answers.pop("level", None)
    outputs = _outputs(answers.pop("outputs", ["proposals"]))
    chat = _language(answers.pop("chat_language", None))
    audience = answers.pop("audience_language", None)
    answers.pop("kind", None)  # the run kind follows the outputs
    cfg = config._merge(defaults(), answers)
    variant = config.get(answers, "mode.variant")
    if variant is not None and not (isinstance(variant, str) and variant in VARIANT_LEVEL):
        raise ValueError(f"mode.variant must be one of {', '.join(VARIANT_LEVEL)}, not {variant!r}.")
    level = level or s.level or VARIANT_LEVEL.get(variant)  # the level wins: a variant only sets a missing one
    if level is not None and isinstance(cfg.get("mode"), dict):
        cfg["mode"]["variant"] = "az" if level == "hands_off" else "gated"  # display only: read run.json level
    cfg["kind"] = RUN_KINDS[outputs[0]]
    if isinstance(cfg.get("channels"), list):
        cfg["channels"] = [brand.channel_key(c) if isinstance(c, str) and c.strip() else c for c in cfg["channels"]]
    _page_lang(cfg, chat, _audience_language(run, audience, cfg.get("channels")))
    if level is not None:
        flow.set_level(run, level)  # refuses an unknown level before anything is written
    s = state.load(run)
    s.outputs = outputs
    state.save(run, s)
    return config.save(run, cfg)


def write_from_previous(run: RunFolder) -> Path:
    """Next week's week run ("plan my week of videos", `tm run new --after <last week run>`): copy the config of the
    week run it follows, with its outputs (weekly_plan) and its level; ask no intake. The channel profile is then
    reused at `reuse_profile` (it is confirmed), and the channel's used trends carry the earlier weeks' videos."""
    s = state.load(run)
    _intake_open(s)
    if not s.previous_run:
        raise ValueError("This run follows no earlier run, so there is no config to copy. Answer the intake questions, "
                         "or start the run with `tm run new --after <last week run>`.")
    previous = RunFolder.open(run.path.resolve().parents[2] / s.previous_run)
    before = state.load(previous)
    if before.playbook != s.playbook or "weekly_plan" not in before.outputs:
        raise ValueError(f"The previous run ({s.previous_run}) is not a week run of organic video, so its config is not "
                         "this week's. Start the run after the last week run, or answer the intake questions.")
    try:
        cfg = config.load(previous)
    except ValueError as exc:
        raise ValueError(f"The previous run ({s.previous_run}) has no config to copy: {exc}") from None
    cfg["kind"] = RUN_KINDS["weekly_plan"]
    if before.level is not None:
        flow.set_level(run, before.level)
    s = state.load(run)
    s.outputs = ["weekly_plan"]
    state.save(run, s)
    return config.save(run, cfg)


# --- validation -------------------------------------------------------------------

def _fixed(out: list[Problem], cfg: dict) -> None:
    for path, (fixed, why) in FIXED.items():
        value = config.get(cfg, path)
        if value is not None and value != fixed:
            name = str(value).capitalize() if isinstance(value, str) else repr(value)
            out.append(Problem(path, why.format(name=name) + ".", f"Set {path} to {fixed}."))


def _present(cfg: dict, path: str) -> bool:
    """The dotted key is in cfg, even as null."""
    *parents, last = path.split(".")
    node = config.get(cfg, ".".join(parents)) if parents else cfg
    return isinstance(node, dict) and last in node


def _choice_problem(out: list[Problem], path: str, value: object, allowed: tuple) -> None:
    out.append(Problem(path, f"{path} must be one of {', '.join(allowed)}, not {value!r}.",
                       f"Pick one of {', '.join(allowed)}."))


def _choices(out: list[Problem], cfg: dict) -> None:
    for path, allowed in CHOICES.items():  # a written choice is never null
        if _present(cfg, path) and config.get(cfg, path) not in allowed:
            _choice_problem(out, path, config.get(cfg, path), allowed)
    for path, allowed in OPTIONAL_CHOICES.items():
        value = config.get(cfg, path)
        if value is not None and value not in allowed:
            _choice_problem(out, path, value, allowed)
    for path, allowed in SUBSETS.items():
        value = config.get(cfg, path)
        if value is not None and not (isinstance(value, list) and value and all(v in allowed for v in value)
                                      and len(set(value)) == len(value)):
            out.append(Problem(path, f"{path} must be one or more of {', '.join(allowed)}, each once, not {value!r}.",
                               f"Correct {path}."))


def _numbers(out: list[Problem], cfg: dict) -> None:
    for path, spec in NUMBERS.items():
        value = config.get(cfg, path)
        if value is not None and not config.in_range(value, spec):
            out.append(config.range_problem(path, value, spec))
    for path, spec in RANGES.items():
        value = config.get(cfg, path)
        if value is not None and not (isinstance(value, list) and len(value) == 2
                                      and all(config.in_range(v, spec) for v in value) and value[0] < value[1]):
            kind = "whole numbers" if spec[0] else "numbers"
            out.append(Problem(path, f"{path} must be [low, high], two {kind} from {spec[1]} to {spec[2]} with low "
                                     f"below high, not {value!r}.", f"Give {path} a valid range."))
    for low, high in ORDERED:
        a, b = config.get(cfg, low), config.get(cfg, high)
        if config.in_range(a, NUMBERS[low]) and config.in_range(b, NUMBERS[high]) and a > b:
            out.append(Problem(high, f"{high} ({b}) is below {low} ({a}).", f"Give {high} a value of at least {a}."))


def validate(run: RunFolder) -> list[Problem]:
    """Everything wrong or missing in config.yaml, each with what to do. Empty means ready."""
    try:
        cfg = config.load(run)
    except ValueError as exc:
        return [Problem(config.FILE, str(exc), "Answer the intake questions so the config can be written.")]
    out: list[Problem] = []
    config._unknown_keys(cfg, DEFAULTS, "", out)
    _fixed(out, cfg)
    _choices(out, cfg)
    _numbers(out, cfg)
    output = cfg.get("output")
    if output in OUTPUT_WORDS and output not in OUTPUTS_READY:
        ready = " or ".join(OUTPUTS_READY)
        out.append(Problem("output", f"{OUTPUT_WORDS[output]} is not built yet: it arrives in a later version of "
                           "the plugin.", f"Set output to {ready} ({OUTPUT_WORDS[OUTPUTS_READY[0]].lower()}) for now."))
    page_lang = cfg.get("page_lang")
    if page_lang not in PAGE_LANGS:
        out.append(Problem("page_lang", f"Pages in {page_lang!r} are not supported yet: pages are built in English or "
                           f"Polish (tracked at {ISSUES}).", "Set page_lang to en or pl."))
    note = cfg.get("page_lang_note")
    if note is not None and not (isinstance(note, str) and note.strip()):
        out.append(Problem("page_lang_note", "page_lang_note must be a sentence, or null.", "Correct it."))
    channels = cfg.get("channels")
    if not (isinstance(channels, list) and all(isinstance(c, str) and c and brand.channel_key(c) == c for c in channels)):
        out.append(Problem("channels", f"channels must list the channels' slugs (as in {brand.CHANNEL_DIR.as_posix()}/"
                           f"<slug>/), not {channels!r}.", "Write the channel names again with tm config write."))
    currency = cfg.get("currency")
    if not (isinstance(currency, str) and len(currency) == 3 and currency.isalpha() and currency.isupper()):
        out.append(Problem("currency", f"currency must be a three-letter code such as USD or PLN, not {currency!r}.",
                           "Tell Claude the currency the channel's money is in."))
    elif currency != "USD" and cfg.get("fx_rate") is None:
        out.append(Problem("fx_rate", f"Costs are shown in USD with the rate for a {currency} account, and the rate "
                           "is missing.", f"Set fx_rate: how many {currency} one USD buys (for example 3.70)."))
    return out


# --- the organic_intake_written step check ------------------------------------------

def intake_gap(run: RunFolder) -> str | None:
    """A0 is done once config.yaml validates and names the run's channels. Reads only. The gaps, or None."""
    gaps = []
    problems = validate(run)
    if problems:
        gaps.append(f"config.yaml passes tm config check ({'; '.join(p.field for p in problems)})")
    try:
        channels = config.load(run).get("channels")
    except ValueError:
        channels = None
    if not (isinstance(channels, list) and channels):
        gaps.append("config.yaml channels names the channel this run is for (tm config write)")
    return ", and ".join(gaps) or None

