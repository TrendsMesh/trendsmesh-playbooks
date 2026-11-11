"""Readiness checks and the doctor. The checks are data (data/requirements.yaml).

The doctor cannot see MCP servers or the ElevenLabs plan. Claude checks each MCP with one cheap
call and passes the result in (`--mcp trendsmesh=ok,meta=not_enabled`); the ElevenLabs plan is a
reported fact (`--fact elevenlabs_plan=cloning|no_cloning|unknown`). Anything not passed is
"not checked yet", which counts as not ready. A check marked `warn` (TrendsMesh for refresh-ad;
TrendsMesh and the artifacts connector for creative brief; the Meta Ad Library and the artifacts
connector for trend research; the keys, the artifacts connector and the browser for organic video)
never makes the run not ready: the card shows it as a warning with
its own note (refresh-ad's guess-mode notice unless the check names another). The ElevenLabs
plan row is left out while the key is missing, since the key row already says what to do.

Each check names the playbooks it is for (`playbooks`, refresh-ad when absent), and `--playbook`
picks them: trend research has no guess mode, so there TrendsMesh and its Agent plan block;
Meta Ads blocks refresh-ad and creative brief. A playbook other than refresh-ad needs the tiers of
its env_tier rows whose `when` holds (creative brief's animatic tier only with animatics), and a
`browser` row asks `tm.atlas` for the user's own Chrome or Edge.

A reported fact marked `unknown_warns` (the ElevenLabs cloning plan) is a warning while unknown,
not a stop: it matters only if the run needs a clone, and the voice step (refresh-ad's V3) checks
it then. A value known to fall short still blocks.
"""

from __future__ import annotations

import argparse
import ctypes.util
import platform
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

from tm import __version__, atlas, cli, envtiers, evidence, flow, paths, playbooks, secrets
from tm.playbooks import REFRESH_AD

# ok, missing (not connected or not signed in), not_enabled (Meta refuses the ad account), no_plan
# and free (signed in, a plan without trend data: free is what get_usage's plan_code "human"
# gives), inactive (a suspended account), skipped (the user chose to go on without it).
# no_agents: the sign-in page said the plan doesn't include agents (until free accounts can
# connect), so nothing connected. artifacts: the claude.ai artifacts connector is in the
# session (`publish_files`) or not.
McpState = Literal["ok", "missing", "not_enabled", "no_plan", "free", "inactive", "skipped", "no_agents"]
MCP_STATES = ("ok", "missing", "not_enabled", "no_plan", "free", "inactive", "skipped", "no_agents")
MCP_STATES_OF = {"trendsmesh": ("ok", "missing", "no_plan", "free", "inactive", "skipped", "no_agents"),
                 "meta": ("ok", "missing", "not_enabled"),
                 "artifacts": ("ok", "missing")}
_CONNECTED = ("ok", "not_enabled", "no_plan", "free", "inactive")
_NOT_SIGNED_IN = ("skipped", "no_agents")  # the user's no, or a plan that connects no agent
FACT_VALUES = {"elevenlabs_plan": ("cloning", "no_cloning", "unknown")}
RESERVE_MB = 2048  # room for runs on top of the tiers
_LIBS = {"libnss3": "nss3", "libgbm": "gbm", "libasound2": "asound", "libcups2": "cups",
         "libpango": "pango-1.0", "libatk-bridge": "atk-bridge-2.0"}


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    ok: bool
    fixer: str  # "agent" or "user"
    fix: str  # empty when ok
    size_mb: int = 0  # download size for agent installs
    unchecked: bool = False
    warn: bool = False  # the run can go on without it (requirements.yaml `warn`)
    note: str = ""  # a warning's line on the card (`warn_note`, else the guess-mode notice)


@dataclass(frozen=True)
class Readiness:
    items: list[Item]
    ready: bool


def _read_catalogue(path: Path) -> list[dict]:
    """The checks in `path`, refused when one names a playbook that is not registered or an MCP
    state its MCP never has (`ok_states`): a typo would otherwise drop a check without a word."""
    checks = yaml.safe_load(path.read_text(encoding="utf-8"))["checks"]
    known = {pb.id for pb in playbooks.all_playbooks()}
    for e in checks:
        unknown = [p for p in e.get("playbooks", [REFRESH_AD]) if p not in known]
        if unknown:
            raise ValueError(f"{path.name}: check {e['id']} names playbook {', '.join(unknown)}, "
                             f"which data/playbooks.yaml does not list (it lists {', '.join(sorted(known))}).")
        if "ok_states" in e:
            states = MCP_STATES_OF.get(e.get("mcp"), ())
            bad = [s for s in e["ok_states"] if s not in states] if isinstance(e["ok_states"], list) else [e["ok_states"]]
            if bad or not e["ok_states"]:
                raise ValueError(f"{path.name}: check {e['id']} has ok_states {e['ok_states']!r}; the "
                                 f"states of MCP {e.get('mcp')!r} are {', '.join(states) or 'none'}.")
    return checks


@lru_cache(maxsize=1)
def _catalogue() -> list[dict]:
    return _read_catalogue(paths.bundled_data() / "requirements.yaml")


def _os_key() -> str:
    return {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}.get(platform.system(), "any")


def _missing_libs() -> list[str]:
    return [name for name, lib in _LIBS.items() if not ctypes.util.find_library(lib)]


def _os_release() -> dict[str, str]:
    """/etc/os-release as a dict; empty when it cannot be read."""
    try:
        text = Path("/etc/os-release").read_text(encoding="utf-8")
    except OSError:
        return {}
    pairs = (line.split("=", 1) for line in text.splitlines() if "=" in line)
    return {k.strip(): v.strip().strip('"') for k, v in pairs}


def _asound_package() -> str:
    """Ubuntu 24.04 and Debian 13 renamed libasound2 to libasound2t64 (the 64-bit time move);
    there apt-get aborts on the old name and installs nothing."""
    rel = _os_release()
    version = tuple(int(n) for n in re.findall(r"\d+", rel.get("VERSION_ID", ""))[:2])
    if rel.get("ID") == "ubuntu":
        return "libasound2t64" if version >= (24, 4) else "libasound2"
    if rel.get("UBUNTU_CODENAME") and "ubuntu" in rel.get("ID_LIKE", "").split():
        # Mint, Pop!_OS and the like follow their Ubuntu base
        return "libasound2" if rel["UBUNTU_CODENAME"] in _OLD_UBUNTU else "libasound2t64"
    if rel.get("ID") == "debian":
        return "libasound2t64" if version >= (13,) else "libasound2"
    return "libasound2"


_OLD_UBUNTU = {"focal", "jammy", "kinetic", "lunar", "mantic", "bionic"}  # before 24.04 (noble)


def _minutes(mb: int) -> int:
    return max(1, round(mb / 500))


def _size(mb: int) -> str:
    return f"{mb / 1000:.1f} GB" if mb >= 1000 else f"{mb} MB"


def _gb(mb: float) -> str:
    return f"{mb / 1024:.1f} GB"


def _fix_text(entry: dict, **vars: object) -> str:
    fixes = entry.get("fix", {})
    return fixes.get(_os_key(), fixes.get("any", "")).format(**vars)


def _applies(entry: dict, outputs: set[str], voice: bool, caption_removal: bool, tiers: list[str]) -> bool:
    if entry["kind"] == "env_tier":
        return entry["tier"] in tiers
    return _holds(entry.get("when"), outputs, voice, caption_removal, tiers)


def _holds(alts: list[dict] | None, outputs: set[str], voice: bool, caption_removal: bool,
           tiers: list[str]) -> bool:
    """True when the `when` alternatives are absent or one of them holds."""
    if not alts:
        return True
    for alt in alts:
        if "outputs" in alt and not set(alt["outputs"]) & outputs:
            continue
        if "voice" in alt and alt["voice"] != voice:
            continue
        if "caption_removal" in alt and alt["caption_removal"] != caption_removal:
            continue
        if "os" in alt and alt["os"] != _os_key():
            continue
        if "tier" in alt and alt["tier"] not in tiers:
            continue
        return True
    return False


def _tier_wanted(entry: dict, tier: str, outputs: set[str], voice: bool, caption_removal: bool) -> bool:
    """For a playbook other than refresh-ad: an env_tier row names a tier it needs, when its `when`
    is absent or holds for the run (a `tier` key in it is not looked at)."""
    return (entry["kind"] == "env_tier" and entry["tier"] == tier
            and _holds(entry.get("when"), outputs, voice, caption_removal, list(envtiers.TIERS)))


def _for_playbook(playbook: str) -> list[dict]:
    """The checks of this playbook (its id), in the catalogue's order."""
    return [e for e in _catalogue() if playbook in e.get("playbooks", [REFRESH_AD])]


def check(outputs: set[str], voice: bool, mcp: dict[str, McpState], *,
          caption_removal: bool = False, facts: dict[str, str] | None = None,
          playbook: str = REFRESH_AD) -> Readiness:
    """`playbook` is its id or skill name."""
    facts = facts or {}
    outputs = set(outputs)
    pb = playbooks.get(playbook).id
    entries = _for_playbook(pb)
    tiers = (envtiers.tiers_for(outputs, voice) if pb == REFRESH_AD
             else [t for t in envtiers.TIERS if any(_tier_wanted(e, t, outputs, voice, caption_removal)
                                                    for e in entries)])
    present = {t: envtiers.installed(t) for t in tiers}
    items: list[Item] = []
    skipped_key: set[str] = set()
    for e in entries:
        if not _applies(e, outputs, voice, caption_removal, tiers):
            continue
        kind, id_, name, fixer = e["kind"], e["id"], e["name"], e["fixer"]
        ok, unchecked, size, vars = False, False, 0, {}
        if kind == "env_tier":
            t = envtiers.TIERS[e["tier"]]
            ok, size = present[e["tier"]], t.approx_mb
            vars = {"tier": e["tier"], "size": _size(t.approx_mb), "minutes": _minutes(t.approx_mb)}
        elif kind == "secret":
            ok = bool(secrets.get(e["secret"]))
            if not ok:
                skipped_key.add(id_)
        elif kind == "disk_gb":
            need = sum(envtiers.TIERS[t].approx_mb for t in tiers if not present[t]) + RESERVE_MB
            free = shutil.disk_usage(paths.data_dir()).free / 1024**2
            ok = free >= need
            vars = {"need": _gb(need), "free": _gb(free)}
        elif kind == "browser":  # Linux: the headless shell brings none of the libraries Chrome's package does
            browser = atlas.find_browser()
            ok = browser is not None and not (_os_key() == "linux" and atlas.is_headless_shell(browser)
                                              and _missing_libs())
        elif kind == "linux_libs":
            missing = _missing_libs()
            ok, vars = not missing, {"missing": ", ".join(missing), "asound": _asound_package()}
        elif kind == "mcp":
            state = mcp.get(e["mcp"])
            ok, unchecked = state in e.get("ok_states", _CONNECTED), state is None
        elif kind == "plan" and "mcp" in e:
            state = mcp.get(e["mcp"])
            if state in _NOT_SIGNED_IN or (e.get("warn") and state == "missing"):
                continue  # the connection row already says what to do
            plan_of = e["plan_of"] if isinstance(e["plan_of"], list) else [e["plan_of"]]
            ok = state == "ok" or (state in _CONNECTED and state not in plan_of)
            unchecked = state is None or state == "missing"
            if state in plan_of:
                ok, unchecked = False, False
        elif kind == "plan":  # a reported fact
            if e.get("needs_key") in skipped_key:
                continue
            value = facts.get(e["fact"], "unknown")
            ok, unchecked = value == "cloning", value not in ("cloning", "no_cloning")
        by_state = (e.get("fix_by_state") or {}).get(mcp.get(e.get("mcp", ""))) if "mcp" in e else None
        fix = "" if ok else (e["unchecked"] if unchecked else by_state or _fix_text(e, **vars))
        warn = bool(e.get("warn")) or (unchecked and kind == "plan" and bool(e.get("unknown_warns")))
        items.append(Item(id_, name, ok, "agent" if unchecked and "mcp" in e else fixer, fix, size if not ok else 0,
                          unchecked, warn, (e.get("warn_note") or evidence.NOTICE_SHORT) if warn else ""))
    return Readiness(items, all(i.ok or i.warn for i in items))


def card(r: Readiness) -> str:
    # A warning Claude has not checked yet stays on Claude's list: it is checked, not skipped. One
    # the user would check (the cloning plan) is checked later, when it matters: a warning.
    warned = [i for i in r.items if not i.ok and i.warn and not (i.unchecked and i.fixer == "agent")]
    bad = [i for i in r.items if not i.ok and i not in warned]
    if r.ready and not any(i.warn and not i.ok for i in r.items):
        head = "**Ready to go.** Everything this run needs is in place."
    elif r.ready and all(i.unchecked for i in warned):  # only checks made later, if the run needs them
        head = "**Ready to go.** You can start now. One thing is checked later, only if the run needs it."
    elif r.ready:
        things = "One thing" if len(warned) < 2 else "A few things"
        head = f"**Ready to go.** You can start now. {things} would make the results better."
    else:
        head = "**Not ready yet.** Here is what is in place and what is not."
    lines = [head, ""]
    lines += [f"- ✅ {i.name}" for i in r.items if i.ok]
    lines += [f"- ⚠️ {i.name}" for i in warned]
    for i in bad:
        lines.append(f"- ❌ {i.name}" + (" (not checked yet)" if i.unchecked else ""))
    if warned:
        lines += ["", "**You can go on without these:**"]
        lines += [f"- {i.fix}" for i in warned]
        lines += [f"- {note}" for note in dict.fromkeys(i.note for i in warned)]
    todo = [i for i in bad if i.unchecked and i.fixer == "agent"]
    agent = [i for i in bad if i.fixer == "agent" and not i.unchecked]
    user = [i for i in bad if i.fixer == "user"]
    if agent:
        lines += ["", "**I can fix these for you, once you say yes:**"]
        lines += [f"- {i.fix}" for i in agent]
        total = sum(i.size_mb for i in agent)
        if total:
            lines.append(f"- Together: about {_size(total)}, about {_minutes(total)} min.")
    if todo:
        lines += ["", "**I still need to check these (nothing for you to do):**"]
        lines += [f"- {i.fix}" for i in todo]
    if user:
        lines += ["", "**You need to do these yourself:**"]
        lines += [f"{n}. {i.fix}" for n, i in enumerate(user, 1)]
    if bad:
        lines += ["", "When they are done, tell me and I check again. The run continues from the same place."]
    return "\n".join(lines)


def _secret_values() -> list[str]:
    values: list[str] = []
    try:
        text = (paths.data_dir() / "secrets.env").read_text(encoding="utf-8")
    except (OSError, RuntimeError):
        return values
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and value.strip():
            values.append(value.strip())
    return values


def scrub(text: str) -> str:
    for v in sorted(set(_secret_values()), key=len, reverse=True):
        text = text.replace(v, "[hidden]")
    return re.sub(r"\br8_[A-Za-z0-9]{8,}", "[hidden]", text)


def support_report(r: Readiness, log_tail: str) -> Path:
    rows = [f"| {i.id} | {'ok' if i.ok else ('not checked' if i.unchecked else 'missing')} | {i.fixer} | {i.fix} |"
            for i in r.items]
    body = "\n".join([
        "# TrendsMesh playbooks: support report", "",
        f"- Date: {date.today().isoformat()}",
        f"- System: {platform.system()} {platform.release()} ({platform.machine()})",
        f"- Python: {sys.version.split()[0]}",
        f"- tm engine: {__version__}",
        f"- Ready: {'yes' if r.ready else 'no'}", "",
        "## Checks", "", "| Check | Result | Who fixes | Next step |", "|---|---|---|---|", *rows, "",
        "## Log of the last failed step", "", "```", log_tail.rstrip(), "```", "",
        "This report holds no keys, but it can hold details of your runs: read it, then send it privately to "
        "contact@trendsmesh.com, not to a public issue.", "",
    ])
    ws = paths.workspace()
    ws.mkdir(parents=True, exist_ok=True)
    stem = f"trendsmesh-support-{date.today().isoformat()}"
    n = 1
    while True:
        target = ws / (f"{stem}.md" if n == 1 else f"{stem}_{n}.md")
        try:
            with open(target, "x", encoding="utf-8") as fh:
                fh.write(scrub(body))
            return target
        except FileExistsError:
            n += 1


def _pairs(text: str | None, allowed: dict[str, tuple[str, ...]] | None, what: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in filter(None, (text or "").split(",")):
        key, sep, value = part.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not key or (allowed is not None and key not in allowed) \
                or (allowed is not None and value not in allowed[key]) \
                or (allowed is None and value not in MCP_STATES):
            raise ValueError(f"Could not read '{part}' in --{what}.")
        out[key] = value
    return out


def _setup(p: argparse.ArgumentParser) -> None:
    p.add_argument("--playbook", default=REFRESH_AD,
                   help="the playbook to check for, its id or skill (default: refresh-ad)")
    p.add_argument("--outputs", required=True, help="comma list of the playbook's outputs; "
                   "refresh-ad: creative_brief,edited_video,ai_video,live_test; creative-brief: "
                   "review_pack,briefs,animatics,page; trend-research: "
                   "category_report,weekly_digest,paid_view; organic-video: proposals,weekly_plan "
                   "(an idea or week run's A0), script_to_film or organic_video (a production run's D1)")
    p.add_argument("--voice", action="store_true")
    p.add_argument("--caption-removal", action="store_true")
    p.add_argument("--mcp", help="trendsmesh=<ok|free|inactive|skipped|no_agents|missing|no_plan>,"
                                 "meta=<ok|not_enabled|missing>,artifacts=<ok|missing>")
    p.add_argument("--fact", help="elevenlabs_plan=cloning|no_cloning|unknown")
    p.add_argument("--report", action="store_true", help="also write the support report")
    p.add_argument("--log-file", help="file whose last lines go into the report")
    p.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    try:
        playbook = playbooks.offered(args.playbook).id
    except ValueError as exc:
        return cli.fail(args, str(exc))
    known = flow.output_ids(playbook)
    outputs = {o.strip() for o in args.outputs.split(",") if o.strip()}
    bad = outputs - set(known)
    if not outputs or bad:
        return cli.fail(args, f"Unknown output {', '.join(sorted(bad)) or '(none given)'}. Choose from: {', '.join(known)}.")
    try:
        mcp = _pairs(args.mcp, MCP_STATES_OF, "mcp")
        facts = _pairs(args.fact, FACT_VALUES, "fact")
        envtiers.clean_stale()  # free the disk an earlier plugin version's tiers still hold
        r = check(outputs, args.voice, mcp, caption_removal=args.caption_removal, facts=facts,
                  playbook=playbook)
    except (ValueError, RuntimeError) as exc:
        return cli.fail(args, str(exc))
    report = None
    if args.report:
        tail = ""
        if args.log_file:
            try:
                tail = "\n".join(Path(args.log_file).read_text(encoding="utf-8", errors="replace").splitlines()[-60:])
            except OSError:
                tail = "(the log could not be read)"
        report = support_report(r, tail)
    text = card(r) + (f"\n\nSupport report written to: {report}" if report else "")
    payload = {"status": "ready" if r.ready else "stop", "ready": r.ready,
               "items": [asdict(i) for i in r.items], "card": card(r),
               "warnings": [i.id for i in r.items if i.warn and not i.ok],
               "report": str(report) if report else None}
    cli.emit(args, payload, text)
    return 0 if r.ready else 2


cli.register("doctor", _setup, _run)
