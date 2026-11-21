"""Readiness checks and the doctor. The checks are data (data/requirements.yaml).

The doctor cannot see MCP servers. Claude checks each MCP with one cheap
call and passes the result in (`--mcp trendsmesh=ok,meta=not_enabled`); the ElevenLabs plan is a
reported fact (`--fact elevenlabs_plan=cloning|no_cloning|unknown`). An MCP not passed is "not checked yet":
Claude checks it itself a moment later, so the row is `pending` (⏳ "checking in a moment" on the card, `pending` in
the JSON) and counts as ready (issue #124); exit 2 is only for a row that is really missing. A check marked `warn` (TrendsMesh for refresh-ad;
TrendsMesh and the artifacts connector for creative brief; the Meta Ad Library and the artifacts
connector for trend research; the keys, the artifacts connector and the browser for organic video)
never makes the run not ready: the card shows it as a warning with
its own note (a TrendsMesh row while no mode is saved: `evidence.CHOOSE_NOTE`, the choice being the user's; else the
row's `warn_note`). The ElevenLabs
plan row is left out while the key is missing, since the key row already says what to do.

Each check names the playbooks it is for (`playbooks`, refresh-ad when absent), and `--playbook`
picks them: trend research is Paid only, so there TrendsMesh and its Agent plan block; organic video's block until
the user chooses Free or Paid (issue #106), and on Free (`--mode free`, else the workspace's `tm mode`) a playbook with
a Free mode shows TrendsMesh as one line, "Free mode, your choice", with what Free misses (`evidence.NOTICES` short);
Meta Ads blocks refresh-ad and creative brief. A playbook other than refresh-ad needs the tiers of
its env_tier rows whose `when` holds (creative brief's animatic tier only with the briefs: animatics are made on
request at D2, issue #145; `animatics`, an output before then, is read and left out), and a
`browser` row asks `tm.atlas` for the user's own Chrome or Edge.

A key row with `check` (the Replicate token, the ElevenLabs key) asks the provider with one free call
(`tm.providers.check`, #66) and shows three states: works, connected but unusable (refused, or no credits left: the
fix for that cause), missing (where to make the key, with the link). A provider that can't be reached leaves a key
that is set as "set, not checked", which blocks nothing. The ElevenLabs answer also says whether the plan includes
voice cloning: that fills the cloning fact when Claude passed none (`unknown`).

A reported fact marked `unknown_warns` (the ElevenLabs cloning plan) is a warning while unknown,
not a stop: it matters only if the run needs a clone, and the voice step (refresh-ad's V3) checks
it then. One also marked `short_warns` waits the same way when it is known to fall short (its
`short_note` on the card): V3 stops there, only if a clone is needed. Both are `later` warnings.
"""

from __future__ import annotations

import argparse
import ctypes.util
import difflib
import json
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

from tm import __version__, atlas, cli, envtiers, evidence, flow, i18n, offer, paths, playbooks, providers, secrets
from tm.playbooks import REFRESH_AD

# ok, missing (not connected or not signed in), not_enabled (Meta refuses the ad account), no_plan
# and free (signed in, a plan without trend data: free is what get_usage's plan_code "human"
# gives), inactive (a suspended account), skipped (the user chose to go on without it).
# no_agents: the sign-in page said the plan doesn't include agents (until free accounts can
# connect), so nothing connected. artifacts: the session can publish claude.ai artifacts (the
# built-in `Artifact` tool, or the older `publish_files`) or not; denied: a publish in this session was refused by
# Claude Code's permissions (issue #125, references/permissions.md), recorded once Claude saw the refusal.
McpState = Literal["ok", "missing", "not_enabled", "no_plan", "free", "inactive", "skipped", "no_agents", "denied"]
MCP_STATES = ("ok", "missing", "not_enabled", "no_plan", "free", "inactive", "skipped", "no_agents", "denied")
MCP_STATES_OF = {"trendsmesh": ("ok", "missing", "no_plan", "free", "inactive", "skipped", "no_agents"),
                 "meta": ("ok", "missing", "not_enabled"),
                 "artifacts": ("ok", "missing", "denied")}
_CONNECTED = ("ok", "not_enabled", "no_plan", "free", "inactive")
_NOT_SIGNED_IN = ("skipped", "no_agents")  # the user's no, or a plan that connects no agent
FACT_VALUES = {"elevenlabs_plan": ("cloning", "no_cloning", "unknown")}
RESERVE_MB = 2048  # room for runs on top of the tiers
# The general check (issue 76): no playbook chosen. Its rows (`playbooks: [general]` in requirements.yaml) are the
# base tools, the disk, the two keys and the TrendsMesh sign-in; Meta Ads is left to each playbook's own check.
GENERAL = "general"
WINDOWS_11_BUILD = 22000  # Windows 11 still says release "10"; its build number starts here
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
    note: str = ""  # a warning's line on the card (`warn_note`; TrendsMesh: CHOOSE_NOTE), or what Free misses
    later: bool = False  # a warning that matters only at a later step, if the run gets there (the cloning plan)
    state: str = ""  # a key row: works, unusable (connected but unusable), missing, unchecked (#66)
    free: bool = False  # the TrendsMesh row of a run on Free, the user's choice (issue #106): shown, not a warning
    pending: bool = False  # not checked yet, and Claude checks it itself in a moment (issue #124): not a blocker


@dataclass(frozen=True)
class Readiness:
    items: list[Item]
    ready: bool


def _read_catalogue(path: Path) -> list[dict]:
    """The checks in `path`, refused when one names a playbook that is not registered or an MCP
    state its MCP never has (`ok_states`): a typo would otherwise drop a check without a word."""
    checks = yaml.safe_load(path.read_text(encoding="utf-8-sig"))["checks"]
    known = {pb.id for pb in playbooks.all_playbooks()} | {GENERAL}
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


def _applies(entry: dict, outputs: set[str], voice: bool, caption_removal: bool, tiers: list[str],
             production: str | None = None) -> bool:
    if entry["kind"] == "env_tier":
        return entry["tier"] in tiers
    return _holds(entry.get("when"), outputs, voice, caption_removal, tiers, production)


def _holds(alts: list[dict] | None, outputs: set[str], voice: bool, caption_removal: bool,
           tiers: list[str], production: str | None = None) -> bool:
    """True when the `when` alternatives are absent or one of them holds. `production` is organic video's
    production type (`--production`): an alternative with `production` holds only for one of its types, one with
    `not_production` for any other (or none given)."""
    if not alts:
        return True
    for alt in alts:
        if "outputs" in alt and not set(alt["outputs"]) & outputs:
            continue
        if "production" in alt and production not in alt["production"]:
            continue
        if "not_production" in alt and production in alt["not_production"]:
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


def _tier_wanted(entry: dict, tier: str, outputs: set[str], voice: bool, caption_removal: bool,
                 production: str | None = None) -> bool:
    """For a playbook other than refresh-ad: an env_tier row names a tier it needs, when its `when`
    is absent or holds for the run (a `tier` key in it is not looked at)."""
    return (entry["kind"] == "env_tier" and entry["tier"] == tier
            and _holds(entry.get("when"), outputs, voice, caption_removal, list(envtiers.TIERS), production))


def _tiers(pb: str, entries: list[dict], outputs: set[str], voice: bool, caption_removal: bool,
           production: str | None) -> list[str]:
    if pb == REFRESH_AD:
        return envtiers.tiers_for(outputs, voice)
    return [t for t in envtiers.TIERS if any(_tier_wanted(e, t, outputs, voice, caption_removal, production)
                                             for e in entries)]


def route_tiers(playbook: str, outputs: set[str], *, voice: bool = False, production: str | None = None) -> list[str]:
    """The tiers the doctor asks for on this route (in install order), installed or not: what `check` would show
    as its tier rows. Organic video's C3 asks for the missing ones once, before D1's check."""
    pb = playbooks.get(playbook).id
    return _tiers(pb, _for_playbook(pb), set(outputs), voice, False, production)


def _for_playbook(playbook: str) -> list[dict]:
    """The checks of this playbook (its id), in the catalogue's order."""
    return [e for e in _catalogue() if playbook in e.get("playbooks", [REFRESH_AD])]


PROBE_FAILED = ("The video editing tools are installed but a test render failed: {tail}. I set them up again with "
                "`tm env install video --yes` (after your yes).")
PROBE_PASSED = " (a test render passed: a one-time check of about a minute)"


def _video_probe() -> tuple[str, str]:
    """The video tier's test render (`render.probe`, issue #124): ("cached", "") when one passed before for this lock
    file and headless shell, ("passed", "") when it passed now (about a minute), ("failed", <what failed>)."""
    from tm import render
    from tm.tools import _common

    if render.probe_ok():
        return "cached", ""
    try:
        render.probe()
    except (_common.ToolError, OSError, RuntimeError) as exc:
        return "failed", str(exc)
    return "passed", ""


FREE_ROW = "TrendsMesh: Free mode, your choice (say \"connect TrendsMesh\" any time)"
_FREE_GENERAL = ("Free mode: I guess trends from what I can see, each labelled a guess. TrendsMesh would show which "
                 "hooks, topics, sounds and formats are repeating across creators right now, and how early.")


def account_words(meta_account: dict | None) -> str:
    """The Meta account the check read, as its currency and the number of accounts (issue #124): never a name or an
    id, which `--meta-account` cannot carry."""
    if not meta_account:
        return ""
    n, currency = meta_account["accounts"], meta_account["currency"]
    return f"{currency}; your only ad account" if n == 1 else f"{currency}; 1 of {n} accounts checked"


def check(outputs: set[str], voice: bool, mcp: dict[str, McpState], *,
          caption_removal: bool = False, facts: dict[str, str] | None = None,
          playbook: str = REFRESH_AD, production: str | None = None, mode: str | None = None,
          meta_account: dict | None = None) -> Readiness:
    """`playbook` is its id or skill name, or GENERAL for the general check. `production`: organic video's
    production type for a production run (an animation needs the animatic tools, and no breakdown or AI video
    tools). `mode`: the user's choice, free or paid (None: not chosen). On Free, in a playbook that has it, the
    TrendsMesh rows are one line, "Free mode, your choice", and TrendsMesh is not checked (issue #106); not
    chosen, a TrendsMesh row that is not ok says the choice is the user's (`evidence.CHOOSE_NOTE`); on Paid it keeps
    its own note and step (issue #124)."""
    facts = facts or {}
    outputs = set(outputs)
    pb = GENERAL if playbook == GENERAL else playbooks.get(playbook).id
    on_free = mode == "free" and (pb == GENERAL or playbooks.get(pb).guess) and mcp.get("trendsmesh") != "ok"
    free_shown = False
    entries = _for_playbook(pb)
    tiers = _tiers(pb, entries, outputs, voice, caption_removal, production)
    present = {t: envtiers.installed(t) for t in tiers}
    items: list[Item] = []
    skipped_key: set[str] = set()
    checked: dict[str, providers.Check] = {}   # one free call per provider, however many rows name it
    for e in entries:
        if not _applies(e, outputs, voice, caption_removal, tiers, production):
            continue
        kind, id_, name, fixer = e["kind"], e["id"], e["name"], e["fixer"]
        if on_free and e.get("mcp") == "trendsmesh":
            if not free_shown:
                said = evidence.NOTICES.get(pb)
                items.append(Item(id_, FREE_ROW, True, fixer, "", free=True,
                                  note=said.short if said else _FREE_GENERAL))
                free_shown = True
            continue
        ok, unchecked, size, vars, key_state, key_fix = False, False, 0, {}, "", ""
        probe_fix = ""
        if kind == "env_tier":
            t = envtiers.TIERS[e["tier"]]
            ok, size = present[e["tier"]], t.approx_mb
            vars = {"tier": e["tier"], "size": _size(t.approx_mb), "minutes": _minutes(t.approx_mb)}
            if ok and e["tier"] == "video":   # the files are in place: does a render work? (issue #124)
                result, tail = _video_probe()
                if result == "failed":
                    ok, fixer, probe_fix = False, "agent", PROBE_FAILED.format(tail=tail.rstrip("."))
                elif result == "passed":
                    name += PROBE_PASSED
        elif kind == "secret" and e.get("check"):
            provider = e["check"]
            if provider not in checked:
                checked[provider] = providers.check(provider)
            got = checked[provider]
            key_state, ok = got.state, got.state in ("works", "unchecked")
            name = f"{name}: {i18n.t('keys.states.' + key_state)}"
            key_fix = got.fix if key_state == "unusable" else i18n.t(f"keys.{provider}.get",
                                                                     permissions=i18n.t("keys.elevenlabs.permissions"))
            if key_state == "missing":
                skipped_key.add(id_)
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
            said = checked.get("elevenlabs")
            if value == "unknown" and e["fact"] == "elevenlabs_plan" and said and said.cloning is not None:
                value = "cloning" if said.cloning else "no_cloning"   # the key check's own answer (#66)
            ok, unchecked = value == "cloning", value not in ("cloning", "no_cloning")
        if e.get("names_account") and meta_account:
            name = f"{name} ({account_words(meta_account)})"
        by_state = (e.get("fix_by_state") or {}).get(mcp.get(e.get("mcp", ""))) if "mcp" in e else None
        fix = "" if ok else (e["unchecked"] if unchecked else by_state or key_fix or probe_fix or _fix_text(e, **vars))
        fact = kind == "plan" and "mcp" not in e
        later = fact and not ok and bool(e.get("unknown_warns") if unchecked else e.get("short_warns"))
        warn = bool(e.get("warn")) or later
        note = e.get("short_note") if later and not unchecked else e.get("warn_note") or ""
        if e.get("mcp") == "trendsmesh" and mode is None and not ok:
            note = evidence.CHOOSE_NOTE   # not chosen yet: the choice is the user's (on Paid, the row's own note)
        who = "agent" if unchecked and "mcp" in e else fixer
        items.append(Item(id_, name, ok, who, fix, size if not ok else 0, unchecked, warn, note if warn else "",
                          later, key_state, pending=not ok and unchecked and who == "agent"))
    return Readiness(items, all(i.ok or i.warn or i.pending for i in items))


def card(r: Readiness, *, general: bool = False) -> str:
    """The readiness card. `general`: the general check's card (no playbook chosen), which speaks of the plugin, not
    of a run, and ends with how to check one playbook."""
    # A row Claude has not checked yet is pending: Claude checks it in a moment, nothing for the user to do (issue
    # #124). One the user would check (the cloning plan) is checked later, when it matters: a warning.
    pending = [i for i in r.items if i.pending]
    warned = [i for i in r.items if not i.ok and i.warn and not i.pending]
    bad = [i for i in r.items if not i.ok and i not in warned and not i.pending]
    if general:
        head = i18n.t("doctor.general.ready" if r.ready else "doctor.general.not_ready")
    elif r.ready and not warned:
        head = "**Ready to go.** Everything this run needs is in place."
    elif r.ready and all(i.later and i.unchecked for i in warned):  # checked later, if needed
        head = "**Ready to go.** You can start now. One thing is checked later, only if the run needs it."
    elif r.ready and all(i.later for i in warned):  # known now, matters only at a later step
        head = "**Ready to go.** You can start now. One thing matters later, only if the run needs it."
    elif r.ready:
        things = "One thing" if len(warned) < 2 else "A few things"
        head = f"**Ready to go.** You can start now. {things} would make the results better."
    else:
        head = "**Not ready yet.** Here is what is in place and what is not."
    if pending and r.ready and not general:
        still = f"I'm still checking {_and([i.name for i in pending])}."
        head = (f"**Ready to go.** {still}" if not warned
                else head.replace("**Ready to go.**", f"**Ready to go.** {still}", 1))
    lines = [head, ""]
    lines += [f"- ✅ {i.name}" for i in r.items if i.ok and not i.free]
    lines += [f"- ℹ️ {i.name}. {i.note}" for i in r.items if i.free]
    lines += [f"- ⏳ {i.name}: checking in a moment" for i in pending]
    lines += [f"- ⚠️ {i.name}" for i in warned]
    lines += [f"- ❌ {i.name}" for i in bad]
    if warned:
        lines += ["", "**You can go on without these:**"]
        lines += [f"- {i.fix}" for i in warned]
        lines += [f"- {note}" for note in dict.fromkeys(i.note for i in warned) if note]
    agent = [i for i in bad if i.fixer == "agent"]
    user = [i for i in bad if i.fixer == "user"]
    if agent:
        lines += ["", "**I can fix these for you, once you say yes:**"]
        lines += [f"- {i.fix}" for i in agent]
        total = sum(i.size_mb for i in agent)
        if total:
            lines.append(f"- Together: about {_size(total)}, about {_minutes(total)} min.")
    if user:
        lines += ["", "**You need to do these yourself:**"]
        lines += [f"{n}. {i.fix}" for n, i in enumerate(user, 1)]
    if bad:
        lines += ["", i18n.t("doctor.general.again") if general else
                  "When they are done, tell me and I check again. The run continues from the same place."]
    if general:
        names = ", ".join(pb.name for pb in playbooks.all_playbooks() if playbooks.bundled(pb))
        lines += ["", i18n.t("doctor.general.one_playbook", playbooks=names)]
    return "\n".join(lines)


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def system_name() -> str:
    """The system for a report: Windows 11 by its build number, since its `platform.release()` still says 10."""
    system, release, machine = platform.system(), platform.release(), platform.machine()
    if system != "Windows":
        return f"{system} {release} ({machine})"
    parts = platform.version().split(".")
    build = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else None
    if build is None:
        return f"Windows {release} ({machine})"
    return f"Windows {'11' if build >= WINDOWS_11_BUILD else release} (build {build}, {machine})"


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


REPORT_NAME = "trendsmesh-support.md"   # one file, overwritten by each report (issue #124)


def plugin_version() -> str:
    """The plugin's version from its manifest (`.claude-plugin/plugin.json`), or "(version unknown)"."""
    try:
        version = json.loads((paths.plugin_root() / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    except (OSError, RuntimeError, ValueError, KeyError, TypeError):
        return "(version unknown)"
    return str(version)


def support_report(r: Readiness, log_tail: str, *, meta_account: dict | None = None) -> Path:
    """The support report, `<workspace>/trendsmesh-support.md`: written again by each report, so it is always the
    current one. A row that names the Meta account says which one was checked, as `account_words`."""
    words = account_words(meta_account)

    def check_name(i: Item) -> str:
        return f"{i.id} ({words})" if words and i.name.endswith(f"({words})") else i.id
    rows = [f"| {check_name(i)} | {'ok' if i.ok else ('not checked' if i.unchecked else 'missing')} | {i.fixer} | "
            f"{i.fix} |" for i in r.items]
    body = "\n".join([
        "# TrendsMesh playbooks: support report", "",
        f"- Date: {date.today().isoformat()}",
        f"- System: {system_name()}",
        f"- Python: {sys.version.split()[0]}",
        f"- Plugin: trendsmesh-playbooks {plugin_version()}",
        f"- tm engine: {__version__}",
        *([f"- Meta ad account: {words}"] if words else []),
        f"- Ready: {'yes' if r.ready else 'no'}", "",
        "## Checks", "", "| Check | Result | Who fixes | Next step |", "|---|---|---|---|", *rows, "",
        "## Log of the last failed step", "", "```", log_tail.rstrip(), "```", "",
        i18n.t("doctor.report.send"), "",
    ])
    ws = paths.workspace()
    ws.mkdir(parents=True, exist_ok=True)
    target = ws / REPORT_NAME
    target.write_text(scrub(body), encoding="utf-8")
    return target


_ACCOUNT_HELP = "currency=<ISO 4217 code>,accounts=<n>"


def _meta_account(text: str | None) -> dict | None:
    """`--meta-account currency=EUR,accounts=2`: the checked account's currency and how many accounts the user has.
    Nothing else is taken, so no account name or id reaches the card or the report."""
    if text is None:
        return None
    pairs = dict(part.partition("=")[::2] for part in text.split(",") if part.strip())
    pairs = {k.strip(): v.strip() for k, v in pairs.items()}
    currency, accounts = pairs.get("currency", "").upper(), pairs.get("accounts", "")
    if set(pairs) != {"currency", "accounts"} or not re.fullmatch(r"[A-Z]{3}", currency) \
            or not accounts.isdigit() or int(accounts) < 1:
        raise ValueError(f"Could not read --meta-account '{text}': give {_ACCOUNT_HELP} (the currency of the ad "
                         "account checked and the number of ad accounts), never an account name or id.")
    return {"currency": currency, "accounts": int(accounts)}


def _closest(given: str, known: list[str]) -> str | None:
    """The output id a wrong name most likely meant (issue #124): one that contains it, else the closest spelling."""
    within = [k for k in known if given.lower() in k]
    if within:
        return within[0]
    close = difflib.get_close_matches(given.lower(), known, n=1, cutoff=0.5)
    return close[0] if close else None


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
    p.add_argument("--general", action="store_true",
                   help="the general check, when no playbook is chosen: the base tools, the keys and the TrendsMesh "
                        "sign-in (--mcp trendsmesh=<state> only; no --playbook, no --outputs)")
    p.add_argument("--playbook", help="the playbook to check for, its id or skill (default: refresh-ad)")
    p.add_argument("--outputs", help="comma list of the playbook's outputs (needed unless --general); "
                   "refresh-ad: creative_brief,edited_video,ai_video,live_test; creative-brief: "
                   "review_pack,briefs,page; trend-research: "
                   "category_report,weekly_digest,paid_view; organic-video: proposals,weekly_plan "
                   "(an idea or week run's A0), script_to_film or organic_video (a production run's D1)")
    p.add_argument("--voice", action="store_true")
    p.add_argument("--caption-removal", action="store_true")
    p.add_argument("--production", metavar="TYPE", help="organic-video's production type at a production run's D1 (00_raw/proposal.json "
                                        "plugin.production): an animation asks for the animatic tools, not the video "
                                        "breakdown or AI video tools")
    p.add_argument("--mcp", help="trendsmesh=<ok|free|inactive|skipped|no_agents|missing|no_plan>,"
                                 "meta=<ok|not_enabled|missing>,artifacts=<ok|missing|denied>")
    p.add_argument("--fact", help="elevenlabs_plan=cloning|no_cloning|unknown")
    p.add_argument("--meta-account", metavar="SPEC",
                   help=f"{_ACCOUNT_HELP}: the Meta ad account checked, from ads_get_ad_accounts: its currency and "
                        "the number of ad accounts (never a name or an id); shown on the card and in the report")
    p.add_argument("--mode", choices=offer.MODES, help="the user's choice, Free or Paid (default: the workspace's, "
                                                       "`tm mode status`; a run's own choice is passed here)")
    p.add_argument("--report", action="store_true", help="also write the support report")
    p.add_argument("--log-file", help="file whose last lines go into the report")
    p.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    general = args.general
    if general:
        if args.playbook or args.outputs:
            return cli.fail(args, "--general is the check with no playbook chosen: give it no --playbook and no "
                                  "--outputs (a playbook's own check takes them without --general).")
        playbook, outputs = GENERAL, set()
    else:
        try:
            playbook = playbooks.offered(args.playbook or REFRESH_AD).id
        except ValueError as exc:
            return cli.fail(args, str(exc))
        known = flow.output_ids(playbook)
        if args.outputs is None:
            return cli.fail(args, f"Give --outputs (choose from: {', '.join(known)}), or --general for the check "
                                  "with no playbook chosen.")
        outputs = {o.strip() for o in args.outputs.split(",") if o.strip()}
        if playbook == playbooks.CREATIVE_BRIEF:            # an output before issue #145 (brief_config.LEGACY_OUTPUTS)
            outputs.discard("animatics")
        bad = outputs - set(known)
        if not outputs or bad:
            hints = [h for b in sorted(bad) if (h := _closest(b, known))]
            hint = f" Did you mean {', '.join(dict.fromkeys(hints))}?" if hints else ""
            return cli.fail(args, f"Unknown output {', '.join(sorted(bad)) or '(none given)'}.{hint} "
                                  f"Choose from: {', '.join(known)}.")
    try:
        mcp = _pairs(args.mcp, MCP_STATES_OF, "mcp")
        if general and set(mcp) - {"trendsmesh"}:
            raise ValueError("The general check takes TrendsMesh only (--mcp trendsmesh=<state>): each playbook's own "
                             "check looks at Meta Ads and shared page links.")
        facts = _pairs(args.fact, FACT_VALUES, "fact")
        meta_account = _meta_account(args.meta_account)
        if general and meta_account:
            raise ValueError("The general check never looks at Meta Ads: give --meta-account to a playbook's check.")
        production = args.production
        if production is not None:
            from tm import organic_proposals   # it imports the doctor's neighbours: imported where it is used

            if general or playbook != playbooks.get("organic-video").id or production not in organic_proposals.PRODUCTIONS:
                raise ValueError(f"--production is organic video's production type, one of "
                                 f"{', '.join(organic_proposals.PRODUCTIONS)}.")
        envtiers.clean_stale()  # free the disk an earlier plugin version's tiers still hold
        mode = args.mode or offer.mode_status(paths.workspace())["mode"]
        r = check(outputs, args.voice, mcp, caption_removal=args.caption_removal, facts=facts,
                  playbook=playbook, production=production, mode=mode, meta_account=meta_account)
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
        report = support_report(r, tail, meta_account=meta_account)
    shown = card(r, general=general)
    text = shown + (f"\n\nSupport report written to: {report}\n{i18n.t('doctor.report.send')}" if report else "")
    payload = {"status": "ready" if r.ready else "stop", "ready": r.ready,
               "playbook": None if general else playbook, "mode": mode,
               "items": [asdict(i) for i in r.items], "card": shown,
               "warnings": [i.id for i in r.items if i.warn and not i.ok and not i.pending],
               "pending": [i.id for i in r.items if i.pending], "meta_account": meta_account,
               "report": str(report) if report else None}
    cli.emit(args, payload, text)
    return 0 if r.ready else 2   # ready allows pending rows; 2 only for a row that is really missing


cli.register("doctor", _setup, _run)
