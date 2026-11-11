"""config.yaml of a trend research run (playbook 04): its schema, written from the intake answers
or copied from the previous run, and its validation. `tm config` hands a trend research run here.

The schema is PLAYBOOK.md "Config" with the numbers of TR1-TR8 named one by one. As in refresh-ad,
the config changes thresholds, never a rule: a key that is not in the schema fails validation,
and so does a changed fixed value (the benchmark source, the digest channel). `trends.exclude_terms`
defaults to empty: TR1 ("seasonal is a tag, not noise") wins over the config table's "holidays".
The noise list (news, sport, politics, possessive names) is built into the map tool, so
`exclude_terms: []` is safe.
Inputs other than a phrase (VARIANTS.md V3-V6) are refused as not supported yet.
"""

from __future__ import annotations

import copy
from pathlib import Path

from tm import config, flow, i18n, state
from tm.config import Problem
from tm.playbooks import TREND_RESEARCH
from tm.runfolder import RunFolder

ISSUES = "https://github.com/TrendsMesh/trendsmesh-playbooks/issues"
REPORT = "category_report"  # always made (PLAYBOOK.md "Inputs")
# The picks file and report.json keep the original's output words; the config and run.json use the
# step ids. One table, read by `research_checks.check_picks` and `research_report` (ruling F7c).
PICK_OUTPUTS = {"category_report": "report", "weekly_digest": "digest", "paid_view": "paid"}
CRITERIA = ("growth", "earliness", "spread", "confidence", "fit", "transfer", "feasibility")  # TR5

DEFAULTS: dict = {
    "mode": "hitl",  # derived from the level: Hands-off is "auto"
    "category": {"inputs": [], "phrase": None, "seeds": []},
    "market": None,
    "language": None,       # older configs (issue #3): see languages
    "market_lang": None,    # older configs (issue #3): see languages
    "languages": {"working": None, "market": None},   # tm.i18n: BCP 47 tags (issue #3)
    "currency": "USD",
    "fx_rate": None,
    "focus": None,
    "outputs": [REPORT],
    "trends": {"min_match": 40, "min_relevant": 10, "max_split_depth": 2, "exclude_terms": []},
    "growth": {"window_days": 14, "baseline_days": 28, "lag_days": 2},
    "buckets": {"act_index": 1.3, "act_min_new": 3, "act_last_days": 5, "act_median_views": 5000,
                "concentrated": 0.6, "rise_index": 0.6, "rise_min_new": 2, "rise_last_days": 7,
                "crowded_creators": 100, "crowded_age_days": 90, "active_days": 14,
                "season_after_days": 60},
    "confidence": {"low_creators": 8, "low_top_share": 0.6, "high_creators": 15, "high_top_share": 0.4},
    "hooks": {"shortlist": 8, "min_fit": 3},
    "picks": {"act_now": 5, "still_rising": 5, "valid_days": 14},
    "paid": {"too_late_min_creators": 30},
    "scoring": {"weights": {c: 1 for c in CRITERIA}},
    "benchmark": {"source": "meta_ad_library"},
    "digest": {"map_change_share": 0.25, "schedule": "weekly_monday", "channel": "link"},
    "delivery": {"channel": "artifact"},
}

# The hooks path's gate before issue #8 (a hook kept only when enough of its videos named the category).
# A config written then still holds these keys: accepted, never read.
OLD_KEYS = {"hooks": {"min_share": None, "min_hits": None, "min_share_hits": None}}

FIXED = {  # rules, not thresholds: path -> (the fixed value, why another value is refused)
    "benchmark.source": ("meta_ad_library", "{value} is not supported yet; it is tracked at " + ISSUES),
    "digest.channel": ("link", "the digest is a link only; nothing is sent"),
}
CHOICES = {
    "mode": ("hitl", "auto"),
    "delivery.channel": ("artifact", "html_file"),
    "digest.schedule": tuple(f"weekly_{d}" for d in ("monday", "tuesday", "wednesday", "thursday",
                                                       "friday", "saturday", "sunday")),
}
_COUNT = (True, 1, None, True, True)  # a whole number from 1
_FROM0 = (True, 0, None, True, True)  # a whole number from 0
_SHARE = (False, 0, 1, False, True)  # above 0, at most 1
_ABOVE0 = (False, 0, None, False, True)
NUMBERS = {  # path: (integer?, lowest, highest, lowest allowed?, highest allowed?), as in config
    "trends.min_match": (False, 0, 100, True, True),
    "trends.min_relevant": _COUNT,
    "trends.max_split_depth": _FROM0,
    "growth.window_days": _COUNT,
    "growth.baseline_days": _COUNT,
    "growth.lag_days": _FROM0,
    "buckets.act_index": _ABOVE0,
    "buckets.act_min_new": _COUNT,
    "buckets.act_last_days": _FROM0,
    "buckets.act_median_views": (False, 0, None, True, True),
    "buckets.concentrated": _SHARE,
    "buckets.rise_index": _ABOVE0,
    "buckets.rise_min_new": _COUNT,
    "buckets.rise_last_days": _FROM0,
    "buckets.crowded_creators": _COUNT,
    "buckets.crowded_age_days": _COUNT,
    "buckets.active_days": _COUNT,
    "buckets.season_after_days": _COUNT,
    "confidence.low_creators": _COUNT,
    "confidence.low_top_share": _SHARE,
    "confidence.high_creators": _COUNT,
    "confidence.high_top_share": _SHARE,
    "hooks.shortlist": (True, 1, 20, True, True),
    "hooks.min_fit": (False, 1, 5, True, True),
    "picks.act_now": _FROM0,
    "picks.still_rising": _FROM0,
    "picks.valid_days": _COUNT,
    "paid.too_late_min_creators": _COUNT,
    "digest.map_change_share": _SHARE,
    "fx_rate": _ABOVE0,
    **{f"scoring.weights.{c}": (False, 0, None, True, True) for c in CRITERIA},
}
TEXT_LISTS = ("category.seeds", "trends.exclude_terms")
REQUIRED = (("category.phrase", "the category phrase"), ("market", "the market"))   # and the languages
# category.inputs: a phrase, a link (a product or landing page), or {kind, value}
UNSUPPORTED_INPUTS = {  # kind: (VARIANTS.md case, what it is)
    "product": ("V3", "A product or landing-page link"),
    "store": ("V4", "A store or brand"),
    "competitor": ("V5", "A competitor"),
    "ad": ("V6", "An existing ad or video"),
}
INPUT_KINDS = ("phrase", *UNSUPPORTED_INPUTS)


def defaults() -> dict:
    return copy.deepcopy(DEFAULTS)


# --- writing ----------------------------------------------------------------------

def _intake_open(s: state.RunState) -> None:
    if s.step not in (None, "A0"):
        raise ValueError("The intake is already done, so the config is not rewritten.")


def _outputs(outputs: object) -> list[str]:
    """The chosen outputs in the playbook's order, with the category report always among them."""
    known = flow.output_ids(TREND_RESEARCH)
    if not isinstance(outputs, list) or not set(outputs) <= set(known):
        raise ValueError(f"outputs must be some of: {', '.join(known)}.")
    return [o for o in known if o == REPORT or o in outputs]


def _write(run: RunFolder, cfg: dict, level: str | None) -> Path:
    cfg["outputs"] = _outputs(cfg.get("outputs"))
    if level is not None:
        flow.set_level(run, level)  # refuses an unknown level before anything is written
    s = state.load(run)
    s.outputs = list(cfg["outputs"])
    state.save(run, s)
    return config.save(run, cfg)


def _mode(level: str | None) -> str:
    return "auto" if level == "hands_off" else "hitl"


def write_from_intake(run: RunFolder, answers: dict) -> Path:
    """Write config.yaml from the intake answers and set the level and outputs in run.json.

    `answers` has the config's shape (`category`, `market`, `language`, `outputs`, ...) plus the
    intake-only `level`. Anything it leaves out gets the default. Problems are not raised here:
    `validate` lists them. Not allowed once the intake step is done.
    """
    s = state.load(run)
    _intake_open(s)
    answers = copy.deepcopy(answers)
    level = answers.pop("level", None) or s.level
    cfg = i18n.settle(config._merge(defaults(), answers))
    if "mode" not in answers:
        cfg["mode"] = _mode(level)
    return _write(run, cfg, level)


def write_from_previous(run: RunFolder, answers: dict | None = None) -> Path:
    """A weekly run: copy the config of the run it follows (`tm run new --after`). The level is
    `answers["level"]` if given, else Hands-off (the plan's decision 9), and the mode follows it.
    """
    s = state.load(run)
    _intake_open(s)
    if not s.previous_run:
        raise ValueError("This run follows no earlier run, so there is no config to copy. Answer "
                         "the intake questions, or start the run with `tm run new --after <last run>`.")
    previous = RunFolder.open(run.path.resolve().parents[2] / s.previous_run)
    try:
        cfg = config.load(previous)
    except ValueError as exc:
        raise ValueError(f"The previous run ({s.previous_run}) has no config to copy: {exc}") from None
    level = (answers or {}).get("level") or "hands_off"
    cfg["mode"] = _mode(level)
    return _write(run, cfg, level)


# --- validation -------------------------------------------------------------------

def _input_kind(item: object) -> object:
    if isinstance(item, str):
        return "product" if item.strip().lower().startswith(("http://", "https://")) else "phrase"
    if isinstance(item, dict):
        return item.get("kind")
    return None


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _inputs(inputs: object, out: list[Problem]) -> None:
    if not isinstance(inputs, list):
        out.append(Problem("category.inputs", f"category.inputs must be a list, not {inputs!r}.",
                           "Give category.inputs as a list, or leave it empty."))
        return
    for item in inputs:
        kind = _input_kind(item)
        if kind == "phrase" and (isinstance(item, str) or _text(item.get("value"))):
            continue
        if kind in UNSUPPORTED_INPUTS:
            case, what = UNSUPPORTED_INPUTS[kind]
            out.append(Problem("category.inputs",
                               f"{what} as a category input ({case}) is not supported yet; it is "
                               f"tracked at {ISSUES}.",
                               "Give Claude a category phrase instead (for example the product "
                               "type); the run goes on with the phrase."))
        else:  # an unknown kind, or {kind: phrase} without a value
            out.append(Problem("category.inputs",
                               f"{item!r} is not a category input. Each is a phrase, a link, or "
                               f"{{kind, value}} with kind one of {', '.join(INPUT_KINDS)}.",
                               "Correct category.inputs."))


def validate(run: RunFolder) -> list[Problem]:
    """Everything wrong or missing in config.yaml, each with what to do. Empty means ready."""
    try:
        cfg = config.load(run)
    except ValueError as exc:
        return [Problem(config.FILE, str(exc), "Answer the intake questions so the config can be written.")]
    out: list[Problem] = []
    config._unknown_keys(cfg, config._merge(defaults(), OLD_KEYS), "", out)
    for path, (fixed, why) in FIXED.items():
        value = config._get(cfg, path)
        if value is not None and value != fixed:
            out.append(Problem(path, f"{path} is fixed to {fixed}: {why.format(value=repr(value))}.",
                               f"Set {path} to {fixed}."))
    for path, allowed in CHOICES.items():
        value = config._get(cfg, path)
        if value is not None and value not in allowed:
            out.append(Problem(path, f"{path} must be one of {', '.join(allowed)}, not {value!r}.",
                               f"Pick one of {', '.join(allowed)}."))
    for path, spec in NUMBERS.items():
        value = config._get(cfg, path)
        if value is not None and not config.in_range(value, spec):
            out.append(config.range_problem(path, value, spec))
    weights = config._get(cfg, "scoring.weights")
    if isinstance(weights, dict) and weights and all(w == 0 for w in weights.values()):
        out.append(Problem("scoring.weights", "scoring.weights are all 0, so no pick can be scored.",
                           "Give at least one criterion a weight above 0."))
    for path in TEXT_LISTS:
        value = config._get(cfg, path)
        if value is not None and not (isinstance(value, list)
                                      and all(isinstance(x, str) and x.strip() for x in value)):
            out.append(Problem(path, f"{path} must be a list of words or phrases, not {value!r}.",
                               f"Give {path} as a list, or leave it empty."))
    currency = cfg.get("currency")
    if not (isinstance(currency, str) and len(currency) == 3 and currency.isalpha()
            and currency.isupper()):
        out.append(Problem("currency", f"currency must be a three-letter code such as USD or PLN, "
                           f"not {currency!r}.", "Tell Claude the currency for the page."))

    known = flow.output_ids(TREND_RESEARCH)
    outputs = cfg.get("outputs")
    if not (isinstance(outputs, list) and REPORT in outputs and set(outputs) <= set(known)):
        out.append(Problem("outputs", f"outputs must be {REPORT} and any of the others: "
                           f"{', '.join(known)}.", "Choose which outputs this run produces."))
    _inputs(config._get(cfg, "category.inputs") or [], out)
    for path, label in REQUIRED:
        if config._blank(config._get(cfg, path)):
            out.append(Problem(path, f"{label.capitalize()} is missing.", f"Tell Claude {label}."))
    out += i18n.config_problems(cfg)    # languages, or an older config's language and market_lang
    return out
