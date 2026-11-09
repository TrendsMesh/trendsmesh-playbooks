"""The Agent plan offer and the user's TrendsMesh sign-in choice.

`tm offer` reads TrendsMesh's public plans (`GET https://trendsmesh.com/v1/plans`, no sign-in, the
same data as the pricing table) and gives the one sentence the agent says to a signed-in user
whose plan has no trend data: the free months while an offer covers Agent, otherwise the price.
Sales are always open, so there is no "not on sale" answer. When the plans can't be read, it falls
back to the plans page. The agent says it once, at the start of a run, never mid-run.

    {"plans": [{"code": "agent", "name": "Agent", "monthlyPriceUsd": 99}, ...],
     "offer": {"plans": ["agent", "swarm"], "freeMonths": 1} | null}

Fields it doesn't use are ignored, and a field missing or of the wrong type reads as unknown.

`tm signin skip|ask|status` keeps the user's "no" to signing in to TrendsMesh, per workspace
(`<workspace>/.trendsmesh/prefs.json`), so later runs mention it in one line instead of asking
again.
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


# --- the sign-in choice ----------------------------------------------------------------------

SIGNIN_CHOICES = ("skip", "ask")


def _prefs_file(workspace: Path) -> Path:
    return Path(workspace) / ".trendsmesh" / "prefs.json"


def signin_status(workspace: Path) -> dict:
    try:
        data = json.loads(_prefs_file(workspace).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    skipped = isinstance(data, dict) and data.get("trendsmesh_sign_in") == "skipped"
    return {"skipped": skipped, "at": data.get("at") if skipped else None}


def signin_set(workspace: Path, choice: str) -> dict:
    if choice not in SIGNIN_CHOICES:
        raise ValueError(f"Choose one of {', '.join(SIGNIN_CHOICES)}, not {choice!r}.")
    f = _prefs_file(workspace)
    f.parent.mkdir(parents=True, exist_ok=True)
    data = {"trendsmesh_sign_in": "skipped" if choice == "skip" else "ask",
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    f.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return signin_status(workspace)


# --- commands --------------------------------------------------------------------------------

def _setup_offer(p: argparse.ArgumentParser) -> None:
    p.add_argument("--plans-file", help="a saved plans answer, instead of reading it from TrendsMesh")
    p.add_argument("--upgrade-url", default=PLANS_PAGE,
                   help="the upgrade_url TrendsMesh gave (get_usage, or a not_in_plan refusal)")
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
    cli.emit(args, {"status": "done", **asdict(o)}, o.text)
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
    text = ("The user chose to go on without TrendsMesh in this workspace: say so in one line, "
            "don't ask again." if st["skipped"] else "Ask the user to sign in to TrendsMesh.")
    cli.emit(args, {"status": "done", **st}, text)
    return 0


cli.register("offer", _setup_offer, _run_offer)
cli.register("signin", _setup_signin, _run_signin)
