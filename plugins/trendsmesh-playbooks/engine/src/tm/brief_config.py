"""config.yaml of a creative brief run (playbook 02): its schema, written from the one intake card,
its validation, the `intake_written` step check, and a run started from a trend research pick.
`tm config` hands a creative brief run here.

The schema is PLAYBOOK.md "Config" with the numbers of CB1-CB13 named one by one. As in the other
playbooks, the config changes thresholds, never a rule: a key that is not in the schema fails
validation, and so does a changed fixed value (the saturation source, the voice tiers). CB11 and
CB12 are rules too (the plan's decision 4): every run makes the page, and briefs come with their
animatics. So a run is the review pack alone, or everything.

A run can start from a seed, a pick trend research handed on (`tm run new --seed <seed_id>`):
the whole `seed/1` row is kept as `00_raw/seed.json`, run.json `brief` names it, and the intake
pre-fills the category phrase and the market from it. An organic video run starts from a seed the
same way (`find_seed`, `start_from_seed`), named in run.json `organic` instead. An expired seed starts a run too; B3
re-checks it with a fresh trend card. Its `paid_level` is only a hint for the B4 card
(`SEED_PAID`); the Ad Library check of CB4 always runs.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from urllib.parse import urlparse

from tm import brand, config, flow, i18n, library, manifest, seeds, state, trend_spool
from tm.config import Problem
from tm.playbooks import CREATIVE_BRIEF, ORGANIC_VIDEO
from tm.runfolder import RunFolder

ISSUES = "https://github.com/TrendsMesh/trendsmesh-playbooks/issues"
CRITERIA = ("brand_fit", "persona_fit", "bridge", "lifecycle", "transfer", "sensitivity", "feasibility")  # CB3
RECIPIENTS = ("decision", "strategy", "creator", "editor", "media-buyer")  # CB13, the schema's spelling
TREND_KINDS = ("hook", "topic", "format", "sound")  # CB2
VOICE_TIERS = ["own_customers", "category", "brand"]  # CB5: tier C never counts
REVIEW_PACK, PAGE, BRIEFS, ANIMATICS = "review_pack", "page", "briefs", "animatics"
SEED_FILE = "00_raw/seed.json"
LANDING = "landing_*"  # the landing page the agent saved at A1, 00_raw/landing_<name>.<ext>
# a seed's Ad Library level -> the hint the B4 card shows beside the fresh check (never in its place)
SEED_PAID = {"none": "none_found", "found": "competitor_found", "crowded": "competitor_found",
             "not_checkable": None, "not_checked": None}
SEED_KINDS = tuple(f"{k}_trend" for k in TREND_KINDS)  # the seeds C1 can put in CB2's trend slot

DEFAULTS: dict = {
    "account": {"id": None, "market": None, "language": None, "currency": None},   # language: older configs
    "languages": {"working": None, "market": None},             # tm.i18n: BCP 47 tags (issue #3)
    "product": {"name": None, "landing_url": None, "category_phrase": None},
    "brand": {"profile": None, "guide": None},  # profile: library/brands/<slug>/brand_vNN.json
    "voice": {"links": [], "tiers": list(VOICE_TIERS), "sources": ["reddit_archive", "import"],
              "min_phrases_per_concept": 1, "bank_min": 20, "bank_max": 40},
    "music": {"require_ads_license": False},
    "trends": {"kinds": list(TREND_KINDS), "min_relevant": 5, "terms": [], "exclude_terms": []},
    "persona": {"min_results_per_segment": 10},
    "formats": {"placement_share_min": 0.25},
    "brief": {"valid_days_default": 14, "recipients": list(RECIPIENTS), "currency": "USD", "fx_rate": None},
    "scoring": {"weights": {c: 1 for c in CRITERIA}},
    "benchmark": {"source": "meta_ad_library"},
    "concepts": {"count": 3, "min_axes_diff": 2},
    "outputs": [REVIEW_PACK, BRIEFS, ANIMATICS, PAGE],
    "delivery": {"channel": "artifact"},
    "animatic": {"formats": None, "fps": 24},
    "intake": {"budget": None, "deadline": None, "approver": None, "rights": None, "fee": None},
    "seed": None,
}

FIXED = {  # rules, not thresholds: path -> (the fixed value, why another value is refused)
    "benchmark.source": ("meta_ad_library", "{value} is not supported yet: saturation uses the Meta Ad "
                                            "Library; it is tracked at " + ISSUES),
    "voice.tiers": (VOICE_TIERS, "tier C never counts as evidence (CB5)"),
}
FOREPLAY = ("Foreplay is not supported yet: saturation uses the Meta Ad Library (tracked at "
            f"{ISSUES}).")
CHOICES = {"delivery.channel": ("artifact", "html_file")}
_COUNT = (True, 1, None, True, True)  # a whole number from 1
NUMBERS = {  # path: (integer?, lowest, highest, lowest allowed?, highest allowed?), as in config
    "voice.min_phrases_per_concept": _COUNT,
    "voice.bank_min": _COUNT,
    "voice.bank_max": _COUNT,
    "trends.min_relevant": _COUNT,
    "persona.min_results_per_segment": _COUNT,
    "formats.placement_share_min": (False, 0, 1, False, True),
    "brief.valid_days_default": _COUNT,
    "brief.fx_rate": (False, 0, None, False, True),
    "concepts.count": _COUNT,
    "concepts.min_axes_diff": (True, 0, 5, True, True),  # of five axes (CB6)
    "animatic.fps": _COUNT,
    **{f"scoring.weights.{c}": (False, 0, None, True, True) for c in CRITERIA},
}
BOOLS = ("music.require_ads_license",)
TEXT_LISTS = ("voice.links", "trends.terms", "trends.exclude_terms")


def defaults() -> dict:
    return copy.deepcopy(DEFAULTS)


# --- writing ----------------------------------------------------------------------

def _intake_open(s: state.RunState) -> None:
    if s.step not in (None, "A0", "A1"):  # the intake card is A1's
        raise ValueError("The intake is already done, so the config is not rewritten.")


def _outputs(outputs: object) -> list[str]:
    """The chosen outputs in the playbook's order. CB11 and CB12 are `validate`'s."""
    known = flow.output_ids(CREATIVE_BRIEF)
    if not isinstance(outputs, list) or not set(outputs) <= set(known):
        raise ValueError(f"outputs must be some of: {', '.join(known)}.")
    return [o for o in known if o in outputs]


def _recipients(value: object) -> object:
    """`media_buyer` written the schema's way, `media-buyer`, each once (the plan's decision 14)."""
    if not isinstance(value, list):
        return value
    out = []
    for r in value:
        r = "media-buyer" if r == "media_buyer" else r
        if r not in out:
            out.append(r)
    return out


def _blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def seed_row(run: RunFolder) -> dict | None:
    """The seed this run was started from (00_raw/seed.json), else None. run.json names it in the run's
    own state: `brief.seed` for a creative brief, `organic.seed` for organic video."""
    s = state.load(run)
    if not ((s.brief or {}).get("seed") or (s.organic or {}).get("seed")):
        return None
    try:
        row = json.loads((run.path / SEED_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"run.json names a seed, but {SEED_FILE} cannot be read ({exc}).") from None
    if not isinstance(row, dict):
        raise ValueError(f"run.json names a seed, but {SEED_FILE} does not hold one JSON object.")
    return row


def write_from_intake(run: RunFolder, answers: dict) -> Path:
    """Write config.yaml from the intake card's answers and set the level and outputs in run.json.

    `answers` has the config's shape (`account`, `product`, `brand`, `outputs`, ...) plus the
    intake-only `level`. Anything it leaves out gets the default; a run started from a seed gets
    the seed's category phrase (its sub-category, else its category) and market. Problems are not
    raised here: `validate` lists them. Not allowed once the intake step (A1) is done.
    """
    s = state.load(run)
    _intake_open(s)
    answers = copy.deepcopy(answers)
    level = answers.pop("level", None) or s.level
    cfg = i18n.settle(config._merge(defaults(), answers))
    cfg["outputs"] = _outputs(cfg.get("outputs"))
    if isinstance(cfg.get("brief"), dict):
        cfg["brief"]["recipients"] = _recipients(cfg["brief"].get("recipients"))
    row = seed_row(run)
    cfg["seed"] = row.get("seed_id") if row is not None else None  # only run.json's seed, never the answers'
    if row is not None:
        fills = {("product", "category_phrase"): row.get("sub_category") or row.get("category"),
                 ("account", "market"): row.get("market")}
        for (group, key), value in fills.items():
            if isinstance(cfg.get(group), dict) and _blank(cfg[group].get(key)) and not _blank(value):
                cfg[group][key] = value
    if level is not None:
        flow.set_level(run, level)  # refuses an unknown level before anything is written
    s = state.load(run)
    s.outputs = list(cfg["outputs"])
    state.save(run, s)
    return config.save(run, cfg)


# --- validation -------------------------------------------------------------------

def _outputs_problems(outputs: object, out: list[Problem]) -> None:
    known = flow.output_ids(CREATIVE_BRIEF)
    if not (isinstance(outputs, list) and set(outputs) <= set(known)):
        out.append(Problem("outputs", f"outputs must be some of: {', '.join(known)}.",
                           "Choose which outputs this run produces."))
        return
    if PAGE not in outputs:
        out.append(Problem("outputs", "Every creative brief ends on the shared page (CB12), so outputs must "
                           "include page.", "Add page to outputs."))
    if (BRIEFS in outputs) != (ANIMATICS in outputs):
        out.append(Problem("outputs", "Briefs and animatics come together (CB11): every brief has its animatic, "
                           "and an animatic is made from a brief.",
                           "Choose both briefs and animatics, or neither (the review pack alone)."))
    if REVIEW_PACK not in outputs and BRIEFS not in outputs:
        out.append(Problem("outputs", "A creative brief makes the review pack, the briefs or both, so the page has "
                           "concepts to show; outputs without review_pack or briefs skip the concepts (C1, G2).",
                           "Add review_pack (the review pack alone: review_pack and page), or choose everything "
                           "(review_pack, briefs, animatics, page)."))


def _currency(value: object) -> bool:
    return isinstance(value, str) and len(value) == 3 and value.isalpha() and value.isupper()


def validate(run: RunFolder) -> list[Problem]:
    """Everything wrong or missing in config.yaml, each with what to do. Empty means ready."""
    try:
        cfg = config.load(run)
    except ValueError as exc:
        return [Problem(config.FILE, str(exc), "Answer the intake questions so the config can be written.")]
    out: list[Problem] = []
    config._unknown_keys(cfg, DEFAULTS, "", out)
    for path, (fixed, why) in FIXED.items():
        value = config._get(cfg, path)
        if path == "benchmark.source" and isinstance(value, str) and value.strip().lower() == "foreplay":
            out.append(Problem(path, FOREPLAY, f"Set {path} to {fixed}."))
        elif value is not None and value != fixed:
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
    bank_min, bank_max = config._get(cfg, "voice.bank_min"), config._get(cfg, "voice.bank_max")
    if (config.in_range(bank_min, _COUNT) and config.in_range(bank_max, _COUNT) and bank_min > bank_max):
        out.append(Problem("voice.bank_max", f"voice.bank_max ({bank_max}) is below voice.bank_min ({bank_min}).",
                           "Give the language bank a range whose top is at least its bottom."))
    weights = config._get(cfg, "scoring.weights")
    if isinstance(weights, dict) and weights and all(w == 0 for w in weights.values()):
        out.append(Problem("scoring.weights", "scoring.weights are all 0, so no candidate can be scored.",
                           "Give at least one criterion a weight above 0."))
    for path in BOOLS:
        value = config._get(cfg, path)
        if value is not None and not isinstance(value, bool):
            out.append(Problem(path, f"{path} must be true or false, not {value!r}.", f"Set {path} to true or false."))
    for path in TEXT_LISTS:
        value = config._get(cfg, path)
        if value is not None and not (isinstance(value, list)
                                      and all(isinstance(x, str) and x.strip() for x in value)):
            out.append(Problem(path, f"{path} must be a list of texts, not {value!r}.",
                               f"Give {path} as a list, or leave it empty."))

    _outputs_problems(cfg.get("outputs"), out)
    out += i18n.language_problems(cfg)    # unset: an older config's account.language, else English
    recipients = config._get(cfg, "brief.recipients")
    if not (isinstance(recipients, list) and recipients):
        out.append(Problem("brief.recipients", "The page needs at least one view (brief.recipients).",
                           f"Choose one or more of {', '.join(RECIPIENTS)}."))
    elif not set(recipients) <= set(RECIPIENTS):
        unknown = ", ".join(str(r) for r in recipients if r not in RECIPIENTS)
        out.append(Problem("brief.recipients", f"{unknown} is not a view of the page (CB13).",
                           f"Choose from {', '.join(RECIPIENTS)}."))
    kinds = config._get(cfg, "trends.kinds")
    if not (isinstance(kinds, list) and kinds and set(kinds) <= set(TREND_KINDS)):
        out.append(Problem("trends.kinds", f"trends.kinds must be one or more of {', '.join(TREND_KINDS)}, "
                           f"not {kinds!r}.", "Correct trends.kinds (a run without TrendsMesh is guess mode, "
                           "which the doctor decides, not the config)."))

    brief_currency = config._get(cfg, "brief.currency")
    if not _currency(brief_currency):
        out.append(Problem("brief.currency", f"brief.currency must be a three-letter code such as USD, not "
                           f"{brief_currency!r}.", "Set brief.currency to USD."))
    account_currency = config._get(cfg, "account.currency")
    if account_currency is not None and not _currency(account_currency):
        out.append(Problem("account.currency", f"account.currency must be a three-letter code such as PLN, not "
                           f"{account_currency!r}.", "Tell Claude the ad account's currency."))
    elif (_currency(account_currency) and _currency(brief_currency) and account_currency != brief_currency
          and config._get(cfg, "brief.fx_rate") is None):
        out.append(Problem("brief.fx_rate", f"The account spends in {account_currency} and the brief is in "
                           f"{brief_currency}, so the rate must be stated (CB13).",
                           f"Set brief.fx_rate: how many {account_currency} one {brief_currency} buys "
                           "(for example 3.70)."))

    url = config._get(cfg, "product.landing_url")
    link = urlparse(url.strip()) if isinstance(url, str) else None
    if not (link and link.scheme.lower() in ("http", "https") and link.netloc):
        what = "The landing page is missing." if _blank(url) else f"The landing page must be an http(s) link, not {url!r}."
        out.append(Problem("product.landing_url", what, "Tell Claude the product's landing page link."))
    if _blank(config._get(cfg, "product.category_phrase")):
        out.append(Problem("product.category_phrase", "The category phrase is missing.",
                           "Tell Claude the product's category in a few words (for example \"linen bedding\")."))
    return out


# --- the intake_written step check ------------------------------------------------

def _brand_gap(run: RunFolder, profile: object) -> str | None:
    """What is wrong with config.yaml `brand.profile`, else None."""
    want = f"brand.profile names a brand profile saved with tm brand save ({brand.DIR.as_posix()}/<brand>/brand_vNN.json)"
    if _blank(profile) or not isinstance(profile, str):
        return want
    workspace = trend_spool.workspace_of(run)
    path = (workspace / profile).resolve()
    try:
        path.relative_to((workspace / brand.DIR).resolve())
    except ValueError:
        return f"{want}; {profile} is not in {brand.DIR.as_posix()}/"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return f"{want}; {profile} does not exist"
    except OSError as exc:
        return f"{want}; {profile} cannot be read ({exc.strerror or exc})"
    except ValueError:
        return f"{want}; {profile} is not valid JSON"
    if not isinstance(data, dict) or data.get("kind") != "brand":
        kind = data.get("kind") if isinstance(data, dict) else None
        return f"{want}; {profile} is not a brand profile (its kind is {kind!r})"
    problems = brand.check(data, workspace=workspace)
    if problems:
        return f"the brand profile {profile} passes tm brand check ({'; '.join(p.field + ': ' + p.what for p in problems)})"
    return None


def intake_gap(run: RunFolder) -> str | None:
    """A1 is done once the config validates, it has the ad account's currency (so CB13's rate check
    cannot be skipped), its brand profile is a saved one that passes the brand check, and the
    landing page is saved in 00_raw. The gaps, or None."""
    gaps = []
    problems = validate(run)
    if problems:
        gaps.append(f"config.yaml passes tm config check ({'; '.join(p.field for p in problems)})")
    try:
        cfg = config.load(run)
    except ValueError:
        cfg = {}
    profile = config._get(cfg, "brand.profile")
    if _blank(config._get(cfg, "account.currency")):
        gaps.append("account.currency holds the ad account's currency (from ads_get_ad_accounts)")
    gap = _brand_gap(run, profile)
    if gap:
        gaps.append(gap)
    if not any(p.is_file() for p in (run.path / "00_raw").glob(LANDING)):
        gaps.append(f"the landing page is saved as 00_raw/{LANDING}")
    return ", and ".join(gaps) or None


# --- a run started from a trend research pick -------------------------------------

def _damaged_holding(workspace: Path, lines: list[int], seed_id: str) -> list[int]:
    """The damaged lines whose text names `seed_id`."""
    if not seed_id:
        return []
    text = (Path(workspace) / seeds.FILE).read_text(encoding="utf-8-sig").split("\n")
    return [n for n in lines if seed_id in text[n - 1]]


SEEDED_RUN = {CREATIVE_BRIEF: ("the brief", "a creative brief"),   # playbook -> (the run, what builds on a seed)
              ORGANIC_VIDEO: ("the organic video run", "an organic video")}


def find_seed(workspace: Path, seed_id: str, *, playbook: str = CREATIVE_BRIEF) -> dict:
    """The trend research seed `seed_id` from the library, expired or not (B3 re-checks it), for a run
    of `playbook` (creative brief or organic video: the refusals name its run).

    `tm run new --seed` calls this before any run exists, so every refusal is a bad argument
    (ValueError, exit 1) that names the fix, never a resume:
    - a found row that breaks seed/1, or whose kind is not one of PB02's four trend kinds;
    - the id on a damaged line (the line is named);
    - any other unknown id: the valid ones are listed, and any damaged lines named.
    """
    where = seeds.FILE.as_posix()
    run_name, builder = SEEDED_RUN[playbook]
    other = f"pick another seed (tm seeds list --source {seeds.PB4}) or start {run_name} without --seed"
    _, damaged = library.read_jsonl(Path(workspace) / seeds.FILE)
    found = seeds.rows(workspace, source=seeds.PB4)
    row = next((r for r in found if r.get("seed_id") == seed_id), None)
    if row is not None:
        try:
            seeds.check(row)
        except ValueError as exc:
            raise ValueError(f"The seed {seed_id} in {where} breaks seed/1: {exc} Run trend research's E3 again "
                             f"(tm research seeds), or {other}.") from None
        if row["kind"] not in SEED_KINDS:
            raise ValueError(f"The seed {seed_id} is a {row['kind']}; {builder} builds on a "
                             f"{', '.join(SEED_KINDS)} only. So {other}.")
        return row
    lines = ", ".join(map(str, damaged))
    holding = _damaged_holding(workspace, damaged, seed_id) if damaged else []
    if holding:
        raise ValueError(f"The seed {seed_id} is on a damaged line of {where} (line "
                         f"{', '.join(map(str, holding))}: not a JSON row), so it cannot be read. Fix or delete "
                         f"that line, then run tm run new again; or {other}.")
    valid = ", ".join(str(r.get("seed_id")) for r in found)
    listed = (f"The trend research seeds are: {valid}." if found
              else f"There are no readable trend research seeds in {where} yet.")
    broken = (f" Lines {lines} of {where} are damaged (not JSON rows) and are not listed; fix or delete "
              "them if the seed was there." if damaged else "")
    raise ValueError(f"No trend research seed {seed_id!r} in {where}. {listed}{broken} "
                     f"See them with tm seeds list --source {seeds.PB4}.")


def start_from_seed(run: RunFolder, row: dict) -> None:
    """Keep the whole seed row as 00_raw/seed.json (a manifest row names the run it came from) and
    name it in run.json: `brief`, with its Ad Library hint for the B4 card, or for organic video
    `organic` (no Ad Library step there)."""
    target = run.path / SEED_FILE
    with open(target, "x", encoding="utf-8") as fh:  # a new file in 00_raw, never an overwrite
        fh.write(json.dumps(row, ensure_ascii=False, indent=2) + "\n")
    manifest.record(run, SEED_FILE, "00_raw", f"seed from {row.get('run')}")
    s = state.load(run)
    if s.playbook == ORGANIC_VIDEO:
        s.organic = {**(s.organic or {}), "seed": row["seed_id"]}
    else:
        s.brief = {**(s.brief or {}), "seed": row["seed_id"], "seed_paid": SEED_PAID[row["paid_level"]]}
    state.save(run, s)
