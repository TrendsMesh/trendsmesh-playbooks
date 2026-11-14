"""The Agent plan offer and the user's TrendsMesh sign-in choice.

`tm offer` reads TrendsMesh's public plans (`GET https://trendsmesh.com/v1/plans`, no sign-in, the
same data as the pricing table) and gives the one sentence the agent says to a signed-in user
whose plan has no trend data: the free months while an offer covers Agent, otherwise the price.
Sales are always open, so there is no "not on sale" answer. When the plans can't be read, it falls
back to the plans page. The agent says it at the start of a run, never mid-run: with the Free/Paid
question, then on Free at most once every OFFER_EVERY_DAYS days (`tm offer` notes when, issue #106).

    {"plans": [{"code": "agent", "name": "Agent", "monthlyPriceUsd": 99}, ...],
     "offer": {"plans": ["agent", "swarm"], "freeMonths": 1} | null}

Fields it doesn't use are ignored, and a field missing or of the wrong type reads as unknown.

`tm mode free|paid|ask|status [--run R]` keeps the user's choice, Free (the AI guesses) or Paid
(TrendsMesh), per workspace (`<workspace>/.trendsmesh/prefs.json`) or for one run, so later runs say it
in one line instead of asking again. Free is never a default: the engine refuses a guess run without
the choice (`flow.set_evidence`). `tm signin skip|ask|status` (0.13 and earlier) is kept: a skip is
the Free choice.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import urllib.parse
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from tm import __version__, cli, paths

PLANS_URL = "https://trendsmesh.com/v1/plans"
PLANS_PAGE = "https://trendsmesh.com/plans"
TIMEOUT_S = 5  # per connection step and read; a resolver that hangs is the OS's own timeout
PLAN = "agent"
MAX_FREE_MONTHS = 12  # more than this is not an offer we make: read it as a broken answer
_HOST = "trendsmesh.com"


@dataclass(frozen=True)
class Offer:
    known: bool  # the plans were read
    price_usd: float | None
    free_months: int | None  # an offer covering the Agent plan, while it is on
    upgrade_url: str
    text: str  # what the agent says, in English (the skill puts it in the user's words)


def _price(value: float) -> str:
    return f"${value:,.0f}" if float(value).is_integer() else f"${value:,.2f}"


def from_plans(data: object, upgrade_url: str = PLANS_PAGE) -> Offer:
    """The offer for the Agent plan, from the public plans answer (or None when unread)."""
    fallback = Offer(False, None, None, upgrade_url,
                     f"Trend data needs the TrendsMesh Agent plan: {upgrade_url}")
    if not isinstance(data, dict):
        return fallback
    plans = data.get("plans") if isinstance(data.get("plans"), list) else []
    agent = next((p for p in plans if isinstance(p, dict) and p.get("code") == PLAN), None)
    price = agent.get("monthlyPriceUsd") if agent else None
    ok_price = (isinstance(price, (int, float)) and not isinstance(price, bool)
                and math.isfinite(price) and price >= 0)
    price = float(price) if ok_price else None
    offer = data.get("offer") if isinstance(data.get("offer"), dict) else None
    covered = offer.get("plans") if offer else None
    months = offer.get("freeMonths") if isinstance(covered, list) and PLAN in covered else None
    months = (months if isinstance(months, int) and not isinstance(months, bool)
              and 0 < months <= MAX_FREE_MONTHS else None)
    if price is None:
        return fallback
    then = f"{_price(price)} a month (tax, where it applies, is shown at checkout)"
    if months:
        first = "first month" if months == 1 else f"first {months} months"
        return Offer(True, price, months, upgrade_url,
                     f"Trend data needs the TrendsMesh Agent plan. Right now the {first} "
                     f"{'is' if months == 1 else 'are'} $0 for new subscribers: you add a card, "
                     f"nothing is charged for the {first}, and after that it is {then}. "
                     "Want to try it?")
    return Offer(True, price, None, upgrade_url,
                 f"Trend data needs the TrendsMesh Agent plan, {then}. Want to try it?")


def safe_upgrade_url(url: str | None) -> str:
    """The upgrade link TrendsMesh gave, only if it is an https link on trendsmesh.com (tool
    answers can carry text others wrote); otherwise the plans page."""
    # A browser reads "\\" as "/", so a backslash could hide another host: refuse it, with
    # whitespace and control characters.
    if not isinstance(url, str) or any(c.isspace() or c == "\\" or ord(c) < 32 or ord(c) == 127 for c in url):
        return PLANS_PAGE
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port  # raises on a port that isn't a number in range
    except ValueError:
        return PLANS_PAGE
    host = (parts.hostname or "").lower()
    if (parts.scheme != "https" or parts.username or parts.password or port not in (None, 443)
            or not (host == _HOST or host.endswith("." + _HOST))):
        return PLANS_PAGE
    return url


def fetch(url: str = PLANS_URL, timeout: float = TIMEOUT_S) -> object | None:
    """The public plans answer, or None when it can't be read (offline, a proxy, an error).
    TM_PLANS_FILE (tests and the evals' sandbox only) reads a saved answer instead."""
    saved = os.environ.get("TM_PLANS_FILE")
    if saved:
        try:
            return json.loads(Path(saved).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": f"trendsmesh-playbooks/{__version__}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https URL
            body = json.loads(resp.read(256 * 1024).decode("utf-8"))
    except Exception:  # noqa: BLE001 - any failure (network, HTTP, a broken or hostile body) is "unread"
        return None
    # The api answers {"ok": true, "data": {...}}; accept the bare object too.
    if isinstance(body, dict) and isinstance(body.get("data"), dict) and body.get("ok") is True:
        return body["data"]
    return body


# --- the user's choice: Free (the AI guesses) or Paid (TrendsMesh), issue #106 -----------------
#
# `<workspace>/.trendsmesh/prefs.json` keeps it per workspace:
#     {"trendsmesh_mode": "free" | "paid", "at": <when chosen>, "offered_at": <the last plan offer>,
#      "trendsmesh_sign_in": "skipped" | "ask"}   (the last key: 0.13 and earlier, read only)
# A run can carry its own choice instead (run.json `trendsmesh_mode`, `tm mode free --run R`): Free for
# this run only, when the user who chose Paid says no to the offer and yes to going on with guesses.
# Nothing is ever Free by default: no choice reads as None, and a skipped sign-in from 0.13 or earlier
# is reported (`legacy_skip`) but is not a choice, so the next run asks once.

MODES = ("free", "paid")
MODE_CHOICES = (*MODES, "ask")   # ask: forget the choice, so the next run asks again
OFFER_EVERY_DAYS = 30            # after a Free choice, the plan offer comes back at most this often
SIGNIN_CHOICES = ("skip", "ask")


def _prefs_file(workspace: Path) -> Path:
    return Path(workspace) / ".trendsmesh" / "prefs.json"


def _prefs(workspace: Path) -> dict:
    try:
        data = json.loads(_prefs_file(workspace).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_prefs(workspace: Path, data: dict) -> None:
    f = _prefs_file(workspace)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _when(value: object) -> datetime | None:
    try:
        when = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
    return when.replace(tzinfo=when.tzinfo or timezone.utc) if when else None


def mode_status(workspace: Path, *, now: datetime | None = None) -> dict:
    """The workspace's choice: `mode` free, paid or None (not chosen); `offer_due` whether the plan offer may be
    made now (no choice yet, Paid, or Free with no offer in the last OFFER_EVERY_DAYS days)."""
    data = _prefs(workspace)
    mode = data.get("trendsmesh_mode") if data.get("trendsmesh_mode") in MODES else None
    offered = _when(data.get("offered_at"))
    due = mode != "free" or offered is None or ((now or _now()) - offered).days >= OFFER_EVERY_DAYS
    return {"mode": mode, "at": data.get("at") if mode else None,
            "legacy_skip": mode is None and data.get("trendsmesh_sign_in") == "skipped",
            "offered_at": data.get("offered_at"), "offer_due": due}


def mode_set(workspace: Path, choice: str) -> dict:
    if choice not in MODE_CHOICES:
        raise ValueError(f"Choose one of {', '.join(MODE_CHOICES)}, not {choice!r}.")
    data = {k: v for k, v in _prefs(workspace).items() if k in ("offered_at",)}
    if choice in MODES:
        data.update({"trendsmesh_mode": choice, "at": _now().isoformat(timespec="seconds")})
    _write_prefs(workspace, data)
    return mode_status(workspace)


def record_offer(workspace: Path) -> None:
    """The plan offer was made now (`tm offer`), so a Free workspace hears it again only after OFFER_EVERY_DAYS."""
    data = _prefs(workspace)
    data["offered_at"] = _now().isoformat(timespec="seconds")
    _write_prefs(workspace, data)


def run_mode(run_path: Path) -> str | None:
    """A run's own choice (run.json `trendsmesh_mode`), else None."""
    try:
        data = json.loads((Path(run_path) / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get("trendsmesh_mode") if isinstance(data, dict) else None
    return value if value in MODES else None


def chosen_free(run_path: Path, workspace: Path) -> bool:
    """Whether the user chose Free for this run: its own choice, else the workspace's."""
    own = run_mode(run_path)
    return own == "free" if own else mode_status(workspace)["mode"] == "free"


# `tm signin` (0.13 and earlier): a "no" to TrendsMesh is now the Free choice.
def signin_status(workspace: Path) -> dict:
    st = mode_status(workspace)
    skipped = st["mode"] == "free"
    return {"skipped": skipped, "at": st["at"] if skipped else None, "legacy_skip": st["legacy_skip"]}


def signin_set(workspace: Path, choice: str) -> dict:
    if choice not in SIGNIN_CHOICES:
        raise ValueError(f"Choose one of {', '.join(SIGNIN_CHOICES)}, not {choice!r}.")
    mode_set(workspace, "free" if choice == "skip" else "ask")
    return signin_status(workspace)


# --- commands --------------------------------------------------------------------------------

def _setup_offer(p: argparse.ArgumentParser) -> None:
    p.add_argument("--plans-file", help="a saved plans answer, instead of reading it from TrendsMesh")
    p.add_argument("--upgrade-url", default=PLANS_PAGE,
                   help="the upgrade_url TrendsMesh gave (get_usage, or a not_in_plan refusal)")
    p.add_argument("--workspace", help="where the offer is noted (default: the current folder)")
    p.add_argument("--json", action="store_true")


def _run_offer(args: argparse.Namespace) -> int:
    if args.plans_file:
        try:
            data = json.loads(Path(args.plans_file).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return cli.fail(args, f"The plans file can't be read: {exc}")
    else:
        data = fetch()
    o = from_plans(data, safe_upgrade_url(args.upgrade_url))
    try:  # noted, so a Free workspace hears it again only after OFFER_EVERY_DAYS; a note that fails changes nothing
        record_offer(Path(args.workspace) if args.workspace else paths.workspace())
    except OSError:
        pass
    cli.emit(args, {"status": "done", **asdict(o)}, o.text)
    return 0


def _setup_mode(p: argparse.ArgumentParser) -> None:
    p.add_argument("choice", choices=(*MODE_CHOICES, "status"))
    p.add_argument("--run", help="this run only (run.json), not the workspace: Free for one run")
    p.add_argument("--workspace")
    p.add_argument("--json", action="store_true")


_MODE_TEXT = {
    "free": ("The user chose Free: the AI guesses trends, each labelled a guess. Open each run with one line saying so, "
             "and what TrendsMesh would add to this run; they can say 'connect TrendsMesh' any time."),
    "paid": "The user chose Paid: the run reads TrendsMesh. If TrendsMesh isn't ready, ask Free or Paid again.",
    None: "No choice yet: when TrendsMesh isn't ready, ask Free or Paid (trendsmesh-sign-in.md). Never start guessing on your own.",
}


def _run_mode(args: argparse.Namespace) -> int:
    ws = Path(args.workspace) if args.workspace else paths.workspace()
    try:
        if args.run:
            from tm import state   # the run's own choice
            from tm.runfolder import RunFolder
            run = RunFolder.open(Path(args.run))
            s = state.load(run)
            if args.choice != "status":
                s.trendsmesh_mode = args.choice if args.choice in MODES else None
                state.save(run, s)
            st = {**mode_status(ws), "mode": s.trendsmesh_mode, "run": str(args.run), "this_run_only": True}
        else:
            st = mode_status(ws) if args.choice == "status" else mode_set(ws, args.choice)
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))
    text = _MODE_TEXT[st["mode"]]
    if st.get("legacy_skip"):
        text += (" This workspace skipped the TrendsMesh sign-in in an earlier version: that was not a choice of Free, so "
                 "ask Free or Paid once.")
    cli.emit(args, {"status": "done", **st}, text)
    return 0


def _setup_signin(p: argparse.ArgumentParser) -> None:
    p.add_argument("choice", choices=(*SIGNIN_CHOICES, "status"))
    p.add_argument("--workspace")
    p.add_argument("--json", action="store_true")


def _run_signin(args: argparse.Namespace) -> int:
    ws = Path(args.workspace) if args.workspace else paths.workspace()
    try:
        st = signin_status(ws) if args.choice == "status" else signin_set(ws, args.choice)
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))
    text = _MODE_TEXT["free" if st["skipped"] else None]
    cli.emit(args, {"status": "done", **st}, text)
    return 0


cli.register("offer", _setup_offer, _run_offer)
cli.register("mode", _setup_mode, _run_mode)
cli.register("signin", _setup_signin, _run_signin)
