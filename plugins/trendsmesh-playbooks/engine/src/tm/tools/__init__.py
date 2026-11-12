"""`tm tool <name> [args]`: run one media tool in its tier's pixi environment.

The engine process only orchestrates: it checks the tier is installed, reads the keys the tool
needs with `secrets.get`, and starts

    pixi run --as-is --manifest-path <root>/env/pixi.toml -e <env> python -m tm.tools.<name> [args]

as an argv list (never a shell string), with the keys as child-process environment variables
(REPLICATE_API_TOKEN, ELEVENLABS_API_KEY). Keys never go on argv and are never printed. Keys
inherited from the shell are dropped, so a tool only ever sees the plugin's own key.

`--as-is` runs the installed environment without installing or updating anything, so nothing
downloads without a yes; a tier that is not installed stops here (exit 2), and one that is out
of date (a part missing) stops in the tool with the same todo.

A light action runs in the base tier instead of the tool's own (`Tool.light`): `elevenlabs credits`, one free read,
needs no voice tier (#54). SSL_CERT_DIR naming a folder with no certificates (what conda-forge's openssl activation
sets on Windows) is left out of the child's environment, so the nested pixi does not say "ignoring SSL_CERT_DIR"
(`paths.child_environ`).

Paid tools are guarded here, deterministically, before the child starts: they need `--run` and a
numeric `--cost` (the estimate the user approved: USD for Replicate, credits for ElevenLabs), and
`budget.spend(run, kind, cost, what)` records it or stops (exit 2, nothing runs). The child tells
the engine, through the file named in TM_COST_REPORT, whether money was spent and the actual cost
when known; the engine then reconciles the estimate with `budget.reconcile` (an overrun is
recorded and stops the run). With no report (the child crashed) the estimate stays spent. The child is also
told the approved estimate (TM_COST_ESTIMATE, never inherited from the shell): ElevenLabs compares what is left with
it before paying, and a refusal for no credit names it (#66).

The help (`-h` or `--help` anywhere in the arguments) is free for every tool, paid or not: it needs no run, no cost
and no key, and runs in the base tier, where every tool module imports (#88: `tm tool elevenlabs --help` used to say
it costs money). A voice call the approved budget no longer covers (a re-record) is refused with `budget.shortfall`'s
words, which ask the user for the difference; the run is not stopped (#88).

A playbook may hold a paid tool to its own rules first: `PRECHECK[playbook][tool]` names a function
`(run, args) -> str | None` that runs after the tier and key checks and before `budget.spend`; a message
back is a stop (exit 2), and nothing runs or is spent. Organic video's is `organic_specs.guard` (model
specs, never an automatic video redo, an unfinished paid take resumed); Create an ad's is `create_plan.guard`
(the plan's or the storyboard's line, the video after the storyboard's yes, never an automatic video redo).
Refresh-ad has none.

Everything the engine itself says is one JSON object on stdout when `--json` is in the arguments.

Each tool module is also runnable on its own (`python -m tm.tools.<name> --help`); heavy imports
(OpenCV, torch, faster-whisper, replicate) happen inside the functions that need them, so this
package imports in the light engine environment.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from tm import budget, cli, envtiers, flow, i18n, paths, secrets, state
from tm.playbooks import CREATE_AD, ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.stops import Stop


@dataclass(frozen=True)
class Tool:
    tier: str
    keys: tuple[str, ...] = ()
    summary: str = ""
    budget: dict[str, str | None] | None = None  # action (first argument, "*" = any) -> budget kind;
    # "--resume" or "<action>:--resume" -> the kind of a resumed call (None = free)
    light: tuple[str, ...] = ()  # actions that need only the base tier (elevenlabs credits: one free read, #54)

    def tier_for(self, args: list[str]) -> str:
        """The tier this call runs in: the tool's own, or base for a light action or the help (every tool module
        imports in the base tier, #88)."""
        if wants_help(args):
            return "base"
        return "base" if self.light and args and args[0] in self.light else self.tier

    def kind_for(self, args: list[str]) -> str | None:
        """The budget kind this call spends from, or None when it is free. Decided from the parsed
        value, as the tool parses it: only a non-empty --resume is the free path. The help is free (#88)."""
        if not self.budget or wants_help(args):
            return None
        if "--resume" in self.budget and (_parsed(args).resume or "").strip():
            return self.budget["--resume"]  # finishing a run that is already paid: free
        actions = {k: v for k, v in self.budget.items() if not k.startswith("-") and ":" not in k}
        action = args[0] if args and not args[0].startswith("-") else None
        if action and f"{action}:--resume" in self.budget and (_parsed(args).resume or "").strip():
            return self.budget[f"{action}:--resume"]  # only this action's resume is free (music-compose)
        if action in actions:
            return actions[action]
        if "*" in actions:
            return actions["*"]
        # an unknown or missing action is paid (the tool will refuse it, but the guard holds alone)
        return next((v for v in actions.values() if v), None)


def wants_help(args: list[str]) -> bool:
    """A bare -h or --help: the tool's parser prints its help and exits before anything is read, sent or spent."""
    return any(a in ("-h", "--help") for a in args)


TOOLS: dict[str, Tool] = {
    "teardown": Tool("breakdown", (), "scenes, frames, overlays and the material keys of the original"),
    "transcribe": Tool("breakdown", (), "faster-whisper transcript with word timestamps"),
    "inpaint_mode": Tool("breakdown", (), "budget (OpenCV) or pro (ProPainter) caption removal"),
    "inpaint": Tool("breakdown", (), "free caption removal (OpenCV Telea) from the teardown's overlay boxes and times"),
    "recut": Tool("breakdown", (), "render an edit list (picture, music or speech in sync)"),
    "recut_qa": Tool("breakdown", (), "QA of a re-cut: joints, flash, music, words, captions"),
    "segment_map": Tool("breakdown", (), "retention steps mapped to seconds, with cards, visual change, loudness and speech"),
    "reframe": Tool("base", (), "9:16 to 4:5, keeping every overlay inside"),
    "ffmpeg": Tool("base", (), "the plugin's ffmpeg in the run folder: frames, cuts, joins, mixes; never overwrites"),
    "speaker_sim": Tool("voice", (), "speaker similarity (ECAPA) for clone QA"),
    "vo_qa": Tool("voice", (), "R9 check of a processed voiceover line against the unprocessed one"),
    "elevenlabs": Tool("voice", ("elevenlabs_api_key",), "Voice Isolator, IVC clone, TTS (with word times), history search, voice previews, Music, credits",
                       {"isolate": "voice_credits", "clone-ivc": "voice_credits", "tts": "voice_credits",
                        "history-search": None, "music-upload": "voice_credits",
                        "music-compose": "voice_credits", "music-compose:--resume": None,
                        "credits": None, "voices": None}, light=("credits",)),
    "music_index": Tool("breakdown", (), "index a music folder: length, loudness, tempo estimate, mood"),
    "take_qa": Tool("breakdown", (), "QA of a generated take: cuts, transcript, pace, loudness, contact sheet"),
    "replicate_price": Tool("base", (), "live prices from Replicate's public model pages (billingConfig)"),
    "deliver": Tool("base", (), "finish, speed, upload copy, preview, cover, no-sound export, loudness"),
    "replicate_run": Tool("ai", ("replicate_api_token",), "run a Replicate model from a JSON spec (and ProPainter)",
                          {"*": "ai_usd", "--resume": None}),
}

# playbook -> tool -> "module:function" (run, args) -> str | None, imported when a paid call needs it
PRECHECK: dict[str, dict[str, str]] = {ORGANIC_VIDEO: {"replicate_run": "tm.organic_specs:guard"},
                                       CREATE_AD: {"replicate_run": "tm.create_plan:guard"}}

ENV_VARS = {"replicate_api_token": "REPLICATE_API_TOKEN", "elevenlabs_api_key": "ELEVENLABS_API_KEY"}
_KEY_NAMES = {"replicate_api_token": "Replicate token", "elevenlabs_api_key": "ElevenLabs key"}
_PROVIDERS = {"replicate_api_token": "replicate", "elevenlabs_api_key": "elevenlabs"}


def child_argv(name: str, args: list[str]) -> list[str]:
    tool = TOOLS[name]
    return [str(paths.pixi_bin()), "run", "--as-is", "--manifest-path",
            str(paths.plugin_root() / "env" / "pixi.toml"), "-e", envtiers.TIERS[tool.tier_for(args)].env,
            "python", "-m", f"tm.tools.{name}", *args]


def _say(as_json: bool, status: str, message: str, code: int) -> int:
    print(json.dumps({"status": status, "message": message}, ensure_ascii=False) if as_json else message)
    return code


def _parsed(args: list[str]) -> argparse.Namespace:
    """--run, --cost, --resume and replicate_run's spec and --name as the tools read them (no abbreviations, there
    or here); a pre-check reads the same (organic_specs.guard). `spec` is the first argument that is not an
    option's value (an action, for elevenlabs)."""
    p = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    p.add_argument("spec", nargs="?")
    for flag in ("--run", "--cost", "--resume", "--name"):
        p.add_argument(flag)
    try:
        return p.parse_known_args(args)[0]
    except SystemExit:  # e.g. --cost with no value: the call is refused below
        return argparse.Namespace(spec=None, run=None, cost=None, resume=None, name=None)


def _label(name: str, args: list[str]) -> str:
    """What a paid call is called in its spend and over-budget messages: the tool with its spec (the first argument
    that is no option's value; elevenlabs' action) or the record it resumes, and the item (--name) when given.
    A call written spec first (refresh-ad) reads as before; one written `--run R` first no longer reads "--run"
    (PR C review Minor 3)."""
    known = _parsed(args)
    target = known.spec or known.resume or next(iter(args), "")
    return " ".join(["tm tool", name, target, *([f"({known.name})"] if known.name else [])]).rstrip()


def _paid_args(args: list[str]) -> tuple[str | None, float | None]:
    known = _parsed(args)
    try:
        cost = float(known.cost) if known.cost is not None else None
    except ValueError:
        cost = None
    return known.run, cost if cost is not None and math.isfinite(cost) and cost > 0 else None


def _precheck(run: RunFolder, name: str, args: list[str]) -> str | None:
    """The run's own refusals and its playbook's pre-check of this paid call (PRECHECK), before anything is spent:
    None, or the stop's message. A run dropped from its week (organic video, run.json `organic.dropped`) spends
    nothing more, whatever the tool (Task 21 fix round 2, N1)."""
    s = state.load(run)
    dropped = (s.organic or {}).get("dropped") if isinstance(s.organic, dict) else None
    if dropped:
        return (f"{run.path.resolve().name} was dropped from its week ({dropped.get('at')}: “{dropped.get('note')}”), "
                f"so the run is finished and spends nothing more: {name} did not run and nothing was spent. To make "
                f"that day, start it again from the week run (tm organic start --run {dropped.get('week') or '<week run>'}) "
                "and make it in the new run.")
    target = PRECHECK.get(s.playbook, {}).get(name)
    if not target:
        return None
    flow.refuse_if_held(s, "nothing was spent")   # a stopped run: no pre-check runs, nothing is written
    module, function = target.split(":")
    return getattr(importlib.import_module(module), function)(run, args)


def _settle(run, kind: str, estimate: float, report: Path, what: str) -> str | None:
    """Replace the recorded estimate by what the child says was spent (see the module docstring).
    Returns the stop message when the actual cost went over the approved budget."""
    try:
        said = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None  # no word from the tool: the estimate stays spent
    if not isinstance(said, dict):
        return None
    if not said.get("spent"):
        actual = 0.0
    else:
        actual = said.get("actual")
        if actual is None:
            return None
        ok = isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual) \
            and actual >= 0
        if not ok:
            print(f"Note: {what} reported an unusable cost ({actual!r}), so the approved estimate of "
                  f"{estimate:g} stays counted.", file=sys.stderr)
            return None
    if budget.reconcile(run, kind, estimate, float(actual), what) == 2:
        return flow.open_stop(run, [f"over_budget_{kind}"]) or "Over budget."
    return None


def run_tool(name: str, args: list[str]) -> int:
    tool = TOOLS[name]
    as_json = "--json" in args
    tier = tool.tier_for(args)
    if not envtiers.installed(tier):
        return _say(as_json, "stop", f"The {name} tool needs the '{tier}' tools, which are not installed "
                    f"yet. Nothing was run. Install them with: tm env install {tier} (it asks before "
                    "downloading). The run continues from the same place.", 2)
    env = paths.child_environ({k: v for k, v in os.environ.items()
                               if k not in ENV_VARS.values() and k != "TM_COST_ESTIMATE"})
    env.update(paths.pixi_env())
    for key in () if wants_help(args) else tool.keys:   # the help needs no key (#88)
        value = secrets.get(key)  # type: ignore[arg-type]
        if not value:
            get = i18n.t(f"keys.{_PROVIDERS[key]}.get", permissions=i18n.t("keys.elevenlabs.permissions"))
            return _say(as_json, "stop", f"The {_KEY_NAMES[key]} is not set, so the {name} tool did not run "
                        f"and nothing was spent. {get} The run continues from the same place.", 2)
        env[ENV_VARS[key]] = value
    kind = tool.kind_for(args)
    run = estimate = None
    what = _label(name, args) if kind else ""
    if kind:
        run_path, estimate = _paid_args(args)
        if not run_path or estimate is None:
            unit = "USD" if kind == "ai_usd" else "ElevenLabs credits"
            return _say(as_json, "error", f"{what} costs money, so it needs --run <run folder> and --cost <the "
                        f"approved estimate in {unit}, above 0>. Nothing was run.", 1)
        try:
            run = RunFolder.open(Path(run_path))
            refused = _precheck(run, name, args) or budget.shortfall(run, kind, estimate, what)
            if refused:   # nothing spent; a voice shortfall asks the user and leaves the run going (#88)
                return _say(as_json, "stop", refused, 2)
            if budget.spend(run, kind, estimate, what):
                return _say(as_json, "stop", flow.open_stop(run, [f"over_budget_{kind}"]) or "Over budget.", 2)
        except (flow.Held, Stop) as exc:  # the run is stopped, or the pre-check stops: nothing runs or is spent
            return _say(as_json, "stop", str(exc), 2)
        except (OSError, ValueError) as exc:
            return _say(as_json, "error", str(exc), 1)
        env["TM_COST_ESTIMATE"] = f"{estimate:g}"   # the tool checks what is left against it, and names it (#66)
    fd, report_name = tempfile.mkstemp(prefix="tm-cost-", suffix=".json")
    os.close(fd)
    report = Path(report_name)
    report.unlink()
    env["TM_COST_REPORT"] = str(report)
    try:
        # a paid tool's answer is held back until the cost is settled, so one answer goes out
        proc = subprocess.run(child_argv(name, args), env=env,
                              **({"stdout": subprocess.PIPE, "text": True, "encoding": "utf-8"} if kind else {}))
    except OSError as exc:
        if kind:
            budget.reconcile(run, kind, estimate, 0.0, what)  # nothing started, nothing spent
        return _say(as_json, "error", f"Could not start the {name} tool: {exc}", 1)
    code = proc.returncode if proc.returncode in (0, 1, 2) else 1
    if not kind:
        report.unlink(missing_ok=True)
        return code
    try:
        stop = _settle(run, kind, estimate, report, what)
    finally:
        report.unlink(missing_ok=True)
    out = proc.stdout or ""
    if stop is None:
        sys.stdout.write(out)
        return code
    if as_json:
        lines = out.strip().splitlines()
        try:
            result = json.loads(lines[-1]) if lines else None
        except ValueError:
            result = {"output": out}
        print(json.dumps({"status": "stop", "message": stop, "result": result}, ensure_ascii=False))
    else:
        sys.stdout.write(out)
        print(stop)
    return 2


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name", choices=sorted(TOOLS), metavar="name",
                        help="one of: " + ", ".join(sorted(TOOLS)))
    parser.add_argument("args", nargs=argparse.REMAINDER, help="passed to the tool unchanged")


def _run(args: argparse.Namespace) -> int:
    return run_tool(args.name, list(args.args))


cli.register("tool", _setup, _run)
