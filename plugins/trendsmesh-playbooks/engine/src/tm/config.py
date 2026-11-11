"""config.yaml: the intake answers become the run's configuration.

The schema is PLAYBOOK.md "Config" plus `budget.voice_credits`, `intake.voice_rights_confirmed`,
`diagnosis.drop` and the `test.*` statistics. The config can change threshold values, never a
rule: a key that is not in the schema fails validation, and so does a fixed value (the
generation provider, the benchmark source, the test method) that is changed.

This is refresh-ad's config. `write_from_intake`, `validate` and `tm config` hand a trend research
run to `research_config`, a creative brief run to `brief_config`, an organic video run to
`organic_config` and a Create an ad run to `create_config`, each with its own schema.
"""

from __future__ import annotations

import argparse
import copy
import math
import os
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import yaml

from tm import budget, cli, flow, i18n, playbooks, state
from tm.playbooks import CREATE_AD, CREATIVE_BRIEF, ORGANIC_VIDEO, REFRESH_AD, TREND_RESEARCH
from tm.runfolder import RunFolder

FILE = "config.yaml"
INTAKE_ONLY = ("level", "flows")  # answers that go to run.json, not into config.yaml
MUSIC_SOURCES = ("original_file", "elevenlabs_continuation", "licensed_track", "generated")  # VARIANTS.md 3c

DEFAULTS: dict = {
    "mode": "hitl",  # derived from the level: Hands-off is "auto"
    "account": {"id": None, "market": None, "language": None},   # language: older configs (issue #3), see languages
    "languages": {"working": None, "market": None},             # tm.i18n: BCP 47 tags (issue #3)
    "product": {"name": None, "landing_url": None},
    "brand": {"assets_dir": None, "rules": None, "compliance": None},
    # the live test spends ad money and publishes ads: never a default, only when the user picks it
    # by name, with its daily budget and days (issue #22)
    "outputs": ["creative_brief", "edited_video", "ai_video"],
    "winner": {"event": None, "history_days": 90, "window_days": 7, "min_results": 30,
               "drop_recent_days": 2, "target_cpa": None, "fade_cost_increase": 0.30,
               "fade_p_value": 0.10, "detrend_by_account": True, "rank_by": "value_to_recover"},
    "diagnosis": {"table": "r2", "drop": 0.15, "frequency_rise": 0.20,
                  "middle_step_drop_pp": 3, "structural_recut": False},
    "formats": {"placement_share_min": 0.25},
    "generation": {"provider": "replicate",
                   "models": {"image": "gpt-image-2", "video": "veo-3.1-fast"},
                   "caption_removal": "telea"},
    "benchmark": {"source": "meta_ad_library"},
    "budget": {"ai_usd": None, "voice_credits": None, "test_per_day": None, "test_days": None},
    "test": {"decision_metric": None, "min_events_per_variant": None, "scale_threshold": None,
             "kill_threshold": None, "cost_guardrail": None, "method": "meta_ab_test",
             "min_effect": 0.20, "alpha": 0.10, "power": 0.80, "max_days": 14,
             # R4 (issue #23): the shortest run, and the results a variant needs before its cost
             # per result is checked against the guardrail
             "min_days": 4, "guardrail_min_results": 10},
    "library": {"path": "library/results.jsonl"},
    "vo": {"stretch_max": 1.12, "qa_tolerance": 0.10},
    "intake": {"voice_rights_confirmed": False},
    # re-cuts (path C-R): the highest level a variant may use (None: Hands-off stops at 2, the
    # other levels ask at G3r), the music source chain in order (VARIANTS.md 3c) and the
    # tools/recut_qa.py thresholds (PLAYBOOK.md "Config")
    "recut": {"max_level": None,
              "music_source": list(MUSIC_SOURCES),
              "qa": {"music_joint_db": 3, "beat_interval": 0.15, "tempo_drift": 0.04, "tail_db": -6,
                     "caption_flash_s": 0.2}},
}

FIXED = {  # rules, not thresholds
    "diagnosis.table": "r2",
    "generation.provider": "replicate",
    "benchmark.source": "meta_ad_library",
    "test.method": "meta_ab_test",
}
CHOICES = {
    "mode": ("hitl", "auto"),
    "winner.rank_by": ("value_to_recover", "peak_spend"),
    "generation.caption_removal": ("propainter", "telea"),
}
# path: (integer?, lowest, highest, lowest allowed?, highest allowed?)
NUMBERS = {
    "winner.history_days": (True, 7, None, True, True),
    "winner.window_days": (True, 7, None, True, True),
    "winner.min_results": (True, 1, None, True, True),
    "winner.drop_recent_days": (True, 0, None, True, True),
    "winner.target_cpa": (False, 0, None, False, True),
    "winner.fade_cost_increase": (False, 0, None, False, True),
    "winner.fade_p_value": (False, 0, 1, False, False),
    "diagnosis.drop": (False, 0, 1, False, False),
    "diagnosis.frequency_rise": (False, 0, None, False, False),
    "diagnosis.middle_step_drop_pp": (False, 0, 100, False, True),
    "formats.placement_share_min": (False, 0, 1, False, True),
    "test.min_effect": (False, 0, 1, False, False),
    "test.alpha": (False, 0, 1, False, False),
    "test.power": (False, 0, 1, False, False),
    "test.max_days": (True, 1, None, True, True),
    "test.min_days": (True, 1, None, True, True),
    "test.guardrail_min_results": (True, 1, None, True, True),
    "test.min_events_per_variant": (True, 1, None, True, True),
    "vo.stretch_max": (False, 1, None, True, True),
    "vo.qa_tolerance": (False, 0, 1, False, False),
    "budget.ai_usd": (False, 0, None, False, True),
    "budget.voice_credits": (False, 0, None, False, True),
    "budget.test_per_day": (False, 0, None, False, True),
    "budget.test_days": (True, 1, None, True, True),
    "recut.max_level": (True, 0, 5, True, True),
    "recut.qa.music_joint_db": (False, 0, None, False, True),
    "recut.qa.beat_interval": (False, 0, 1, False, False),
    "recut.qa.tempo_drift": (False, 0, 1, False, False),
    "recut.qa.caption_flash_s": (False, 0, None, False, True),
}
BOOLS = ("winner.detrend_by_account", "intake.voice_rights_confirmed",
         "diagnosis.structural_recut")


@dataclass(frozen=True)
class Problem:
    field: str
    what: str
    todo: str


# --- reading and writing --------------------------------------------------------

def defaults() -> dict:
    return copy.deepcopy(DEFAULTS)


def _merge(base: dict, over: dict) -> dict:
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def load(run: RunFolder) -> dict:
    path = run.path / FILE
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"{FILE} does not exist yet. It is written from the intake answers.") from None
    except yaml.YAMLError as exc:
        raise ValueError(f"{FILE} is not valid YAML: {exc}") from None
    if not isinstance(data, dict):
        raise ValueError(f"{FILE} is empty or not a mapping.")
    return data


def _for_playbook(run: RunFolder):
    """The config module of another playbook's run (`research_config`, `brief_config`,
    `organic_config`), or None for refresh-ad."""
    pb = state.load(run).playbook
    if pb == REFRESH_AD:
        return None
    if pb == TREND_RESEARCH:
        from tm import research_config  # it imports this module
        return research_config
    if pb == CREATIVE_BRIEF:
        from tm import brief_config  # it imports this module
        return brief_config
    if pb == ORGANIC_VIDEO:
        from tm import organic_config  # it imports this module
        return organic_config
    if pb == CREATE_AD:
        from tm import create_config  # it imports this module
        return create_config
    raise ValueError(f"{playbooks.get(pb).name} has no {FILE}.")


def save(run: RunFolder, cfg: dict) -> Path:
    """Write config.yaml in one step (a temporary file, then a rename)."""
    path = run.path / FILE
    tmp = run.path / (FILE + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, allow_unicode=True, sort_keys=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return path


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _positive(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def write_from_intake(run: RunFolder, answers: dict) -> Path:
    """Write config.yaml from the intake answers and set what `tm done A0` needs in run.json.

    `answers` has the config's shape (`account`, `product`, `budget`, `winner`, ...) plus the
    intake-only `level` and `flows`. Anything it leaves out gets the playbook's default.
    Hands-off approves the budgets the answers give. Problems are not raised here: `validate`
    lists them. Not allowed once the intake step is done. A trend research, creative brief or organic
    video run's answers go to its own module (`_for_playbook`).
    """
    other = _for_playbook(run)
    if other is not None:
        return other.write_from_intake(run, answers)
    s = state.load(run)
    if s.step not in (None, "A0"):
        raise ValueError("The intake is already done, so the config is not rewritten. "
                         "Budgets change with `tm budget approve`.")
    answers = copy.deepcopy(answers)
    level = answers.pop("level", None) or s.level
    flows = answers.pop("flows", None) or []
    cfg = i18n.settle(_merge(defaults(), answers))
    if "mode" not in answers:
        cfg["mode"] = "auto" if level == "hands_off" else "hitl"
    if cfg["account"].get("id") is not None:
        cfg["account"]["id"] = str(cfg["account"]["id"])
    outputs = cfg["outputs"]
    unknown = [o for o in outputs if o not in flow.output_ids()] if isinstance(outputs, list) else outputs
    if not isinstance(outputs, list) or unknown or not outputs:
        raise ValueError(f"outputs must be some of: {', '.join(flow.output_ids())}.")
    if level is not None:
        flow.set_level(run, level)  # refuses an unknown level before anything is written
    for f in flows:
        flow.use_flow(run, f)
    s = state.load(run)
    s.outputs = list(outputs)
    state.save(run, s)

    path = save(run, cfg)

    if cfg["intake"].get("voice_rights_confirmed") is True:
        manifest = run.path / "manifest.md"
        line = f"Voice rights: the user confirmed at intake on {date.today():%Y-%m-%d} that they hold the rights to the voice in this ad.\n"
        text = manifest.read_text(encoding="utf-8") if manifest.exists() else ""
        if "Voice rights:" not in text:
            manifest.write_text(text + ("" if text.endswith("\n") or not text else "\n") + line,
                                encoding="utf-8")
    if level == "hands_off":
        for kind in flow.BUDGET_KINDS:
            amount = budget.configured(cfg, kind)
            if amount:
                budget.approve_from_intake(run, kind, amount)
    return path


# --- validation -----------------------------------------------------------------

def value(cfg: dict | None, path: str):
    """A dotted key from a run config, falling back to the default when the file lacks it."""
    found = _get(cfg, path) if cfg else None
    return found if found is not None else _get(DEFAULTS, path)


def _get(cfg: dict, path: str):
    """The value at a dotted path (`brief.valid_days_default`), else None."""
    node = cfg
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


get = _get   # public name for the playbook modules


def _unknown_keys(cfg: object, schema: dict, prefix: str, out: list[Problem]) -> None:
    if not isinstance(cfg, dict):
        return
    for key, value in cfg.items():
        path = f"{prefix}{key}"
        if key not in schema:
            out.append(Problem(path, f"{path} is not a setting of this playbook. The config can only "
                                     "change the thresholds of the rules, not the rules.",
                               f"Remove {path} from {FILE}."))
        elif isinstance(schema[key], dict):
            if isinstance(value, dict):
                _unknown_keys(value, schema[key], path + ".", out)
            else:
                out.append(Problem(path, f"{path} must be a group of settings.",
                                   "Put it back as a group, as in the defaults."))


def in_range(value: object, spec: tuple) -> bool:
    """`value` is a finite number within `spec` = (integer?, lowest, highest, lowest allowed?,
    highest allowed?), as in NUMBERS."""
    integer, lo, hi, lo_ok, hi_ok = spec
    good = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    good = good and (not integer or float(value).is_integer())
    good = good and (value > lo or (lo_ok and value == lo))
    return good and (hi is None or value < hi or (hi_ok and value == hi))


def range_problem(path: str, value: object, spec: tuple, extra: str = "") -> Problem:
    integer, lo, hi = spec[:3]
    kind = "a whole number" if integer else "a number"
    bounds = f" from {lo}" + (f" to {hi}" if hi is not None else "")
    return Problem(path, f"{path} must be {kind}{extra}{bounds}, not {value!r}.",
                   f"Give {path} a valid value.")


def _blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def validate(run: RunFolder) -> list[Problem]:
    """Everything wrong or missing in config.yaml, each with what to do. Empty means ready."""
    other = _for_playbook(run)
    if other is not None:
        return other.validate(run)
    try:
        cfg = load(run)
    except ValueError as exc:
        return [Problem(FILE, str(exc), "Answer the intake questions so the config can be written.")]
    s = state.load(run)
    out: list[Problem] = []
    _unknown_keys(cfg, DEFAULTS, "", out)

    for path, fixed in FIXED.items():
        value = _get(cfg, path)
        if value is not None and value != fixed:
            out.append(Problem(path, f"{path} is fixed to {fixed} in v1; {value!r} is not supported.",
                               f"Set {path} to {fixed}."))
    for path, allowed in CHOICES.items():
        value = _get(cfg, path)
        if value is not None and value not in allowed:
            out.append(Problem(path, f"{path} must be one of {', '.join(allowed)}, not {value!r}.",
                               f"Pick one of {', '.join(allowed)}."))
    for path, spec in NUMBERS.items():
        value = _get(cfg, path)
        if value is None:
            continue
        good = in_range(value, spec)
        if path == "winner.window_days" and good and value % 7:
            good = False
        if not good:
            extra = " that is a multiple of 7 (a window is whole weeks)" if path == "winner.window_days" else ""
            out.append(range_problem(path, value, spec, extra))
    tail = _get(cfg, "recut.qa.tail_db")
    if tail is not None and not (_number(tail) and tail < 0):
        out.append(Problem("recut.qa.tail_db", f"recut.qa.tail_db must be a negative number of dB, not {tail!r}.",
                           "Give recut.qa.tail_db a valid value, e.g. -6."))
    chain = _get(cfg, "recut.music_source")
    if chain is not None and not (isinstance(chain, list) and chain and all(isinstance(x, str) for x in chain)
                                  and len(set(chain)) == len(chain) and set(chain) <= set(MUSIC_SOURCES)):
        out.append(Problem("recut.music_source", f"recut.music_source must be a list of some of "
                           f"{', '.join(MUSIC_SOURCES)}, each once and in the order to try them, not {chain!r}.",
                           "Give recut.music_source a valid list, or remove it for the default chain."))
    for path in BOOLS:
        value = _get(cfg, path)
        if value is not None and not isinstance(value, bool):
            out.append(Problem(path, f"{path} must be true or false, not {value!r}.",
                               f"Set {path} to true or false."))

    outputs = cfg.get("outputs")
    if not isinstance(outputs, list) or not outputs or not set(outputs) <= set(flow.output_ids()):
        out.append(Problem("outputs", f"outputs must be some of: {', '.join(flow.output_ids())}.",
                           "Choose which outputs this run produces."))
        outputs = []
    for path, label in (("account.id", "the ad account"), ("account.market", "the market"),
                        ("product.name", "the product")):
        if _blank(_get(cfg, path)):
            out.append(Problem(path, f"{label.capitalize()} is missing.", f"Tell Claude {label}."))
    out += i18n.config_problems(cfg)    # languages, or an older config's account.language
    if "live_test" in outputs and _blank(_get(cfg, "product.landing_url")):
        out.append(Problem("product.landing_url", "The live test needs the product's landing page link, "
                           "and it is missing.", "Give Claude the link the ads should point to."))

    flows = set(s.flows)
    if "V" in flows and _get(cfg, "intake.voice_rights_confirmed") is not True:
        out.append(Problem("intake.voice_rights_confirmed",
                           "A new voiceover line needs your confirmation that you have the rights to "
                           "the voice in this ad.", "Confirm it to Claude, or leave the new voice line out."))

    hands_off = s.level == "hands_off" or (s.level is None and cfg.get("mode") == "auto")
    if hands_off:
        def have(kind: str) -> bool:
            return bool(s.budgets.get(kind)) or budget.configured(cfg, kind) is not None
        if "ai_video" in outputs and not have("ai_usd"):
            out.append(Problem("budget.ai_usd", "Hands-off needs a budget before it generates AI video.",
                               "Tell Claude how much it may spend on AI generation, in US dollars."))
        elif ("edited_video" in outputs and not have("ai_usd")
              and _number(cap := _get(cfg, "recut.max_level")) and cap >= 3):
            # a re-cut at L3-L4 repairs (ProPainter) or generates (Veo) shots from ai_usd; at the
            # default (unset: level 2 in Hands-off) nothing it makes is paid. Asked at intake,
            # before the diagnosis says whether the run re-cuts (flow R)
            out.append(Problem("budget.ai_usd", "Hands-off needs an AI budget before it repairs or "
                               "generates shots for a re-cut.",
                               "Tell Claude how much it may spend on ProPainter and Veo, in US dollars, "
                               "or keep recut.max_level at 2."))
        if "edited_video" in outputs and "V" in flows and not have("voice_credits"):
            out.append(Problem("budget.voice_credits", "Hands-off needs a voice budget before it makes a "
                               "new voiceover line.", "Tell Claude how many ElevenLabs credits it may use."))
        if "live_test" in outputs and not have("test"):
            for key, ask in (("test_per_day", "how much to spend per day"), ("test_days", "for how many days")):
                if not _positive(_get(cfg, f"budget.{key}")):
                    out.append(Problem(f"budget.{key}", "Hands-off needs a live test budget before it "
                                       "launches a test.", f"Tell Claude {ask}."))
    elif "live_test" in outputs:
        # issue #22: a live test the user picked comes with their own daily budget and days, at every
        # level; no amount is assumed (R4 estimates it right away)
        for key, ask in (("test_per_day", "how much to spend per day"), ("test_days", "for how many days")):
            if not _positive(_get(cfg, f"budget.{key}")):
                out.append(Problem(f"budget.{key}", "The live test spends ad money, so it needs your daily "
                                   "budget and days; no amount is assumed.", f"Tell Claude {ask}."))
    return out


# --- command line ---------------------------------------------------------------

def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    w = sub.add_parser("write", help="write config.yaml from the intake answers")
    source = w.add_mutually_exclusive_group(required=True)
    source.add_argument("--answers", help="a JSON file with the intake answers (from here first, else in the run)")
    source.add_argument("--from-previous", action="store_true", dest="from_previous",
                        help="copy the config of the run this one follows (trend research; organic video's week run)")
    sub.add_parser("check", help="list what is missing or wrong in config.yaml")
    for sp in sub.choices.values():
        sp.add_argument("--run", required=True, help="the run folder")
        sp.add_argument("--json", action="store_true")


def _report(args: argparse.Namespace, problems: list[Problem], done: str) -> int:
    if not problems:
        cli.emit(args, {"status": "done", "problems": []}, done)
        return 0
    text = "\n".join(f"{p.field}: {p.what} {p.todo}" for p in problems)
    cli.emit(args, {"status": "stop", "problems": [asdict(p) for p in problems]},
             f"{text}\nThe run continues from the same place once this is settled.")
    return 2


def _run(args: argparse.Namespace) -> int:
    import json
    try:
        run = RunFolder.open(Path(args.run))
        if args.action == "write" and args.from_previous:
            other = _for_playbook(run)
            if not hasattr(other, "write_from_previous"):
                raise ValueError(f"--from-previous is for {playbooks.get(TREND_RESEARCH).name} runs and organic video's "
                                 "week runs; "
                                 f"a run of {playbooks.get(state.load(run).playbook).name} writes its "
                                 "config from the intake answers.")
            other.write_from_previous(run)
            return _report(args, validate(run), f"Copied {FILE} from the previous run.")
        if args.action == "write":
            data = json.loads(run.given(args.answers).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("The answers file must hold one JSON object.")
            write_from_intake(run, data)
            return _report(args, validate(run), f"Wrote {FILE}.")
        return _report(args, validate(run), f"{FILE} is ready.")
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))


cli.register("config", _setup, _run)
