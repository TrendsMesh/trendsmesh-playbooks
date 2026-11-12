"""Replicate and ElevenLabs keys (issue #66): where to make them, a free check, one message per refusal cause, and
what is left before a paid step.

    cause(provider, status, body)        "key", "permission", "credit", "plan", "rate", or None (not recognised)
    refusal(provider, cause, ...)        the message for that cause, with its fix and link (tm.i18n `keys.*`)
    check(provider)                      one free authenticated read -> Check(state, cause, fix, left, cloning)
    left(subscription)                   ElevenLabs credits left, counting usage-based billing; None = can't tell
    need(provider), estimate()           the approved estimate of this paid call (TM_COST_ESTIMATE, set by `tm tool`)

The free reads: Replicate `GET https://api.replicate.com/v1/account` (Authorization: Bearer; it returns who the
token belongs to), ElevenLabs `GET https://api.elevenlabs.io/v1/user/subscription` (xi-api-key; the plan and the
credits, the read `tm tool elevenlabs credits` makes). Neither docs page states a price for these reads; both are
plain reads that start no work. Replicate has no balance read: its docs show billing on the account page only, so
there is no balance check before a Replicate run (point 4 of #66), and "no credit" shows up as the run's refusal.

The key check states: works, unusable (set, but the provider refuses it or the account has nothing left: "connected
but unusable"), missing (not set; nothing is sent), unchecked (set, but the provider could not be reached or answered
in a form we don't know). The key is read from the plugin's secrets, goes only into the request header, and is never
printed, logged or written: a Check holds states and our own words only, never the provider's text.

Refusal answers, from the providers' docs as read on 2026-11-12 (the exact live bodies are NOT captured yet, #66):
- Replicate (https://replicate.com/docs/reference/http, .../topics/predictions/rate-limits, .../topics/billing):
  errors are {"detail": ...} (problem details, sometimes with "title"); 429 "Request was throttled" is documented,
  and an account with no payment method is held to 6 predictions a minute. 401 and 402 are not on any docs page:
  401 = a wrong or revoked token and 402 = no credit are the HTTP meanings, UNVERIFIED live.
- ElevenLabs (https://elevenlabs.io/docs/developers/resources/errors): {"detail": {"type", "code", "message",
  "status" (legacy)}}. 401 invalid_api_key / missing_api_key, 402 insufficient_credits, 403
  insufficient_permissions, feature_not_available and subscription_required, 429 rate_limit_exceeded,
  concurrent_limit_exceeded and system_busy are documented. The legacy statuses quota_exceeded (401) and
  missing_permissions (401) are what older answers sent: UNVERIFIED live.
An answer we don't recognise keeps today's message (`keys.<provider>.other`).

Making a key (checked against the docs on 2026-11-12): Replicate https://replicate.com/account/api-tokens; ElevenLabs
https://elevenlabs.io/app/settings/api-keys (Developers, API Keys). A restricted ElevenLabs key needs the permissions
this plugin's calls use: text_to_speech, voices_read and voices_write (the voice library and instant cloning),
audio_isolation, music_generation, speech_history_read and user_read (the subscription read; the docs don't name the
permission that read needs, user_read is our reading). The UI's labels for them are not in the docs.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Literal

from tm import i18n

Provider = Literal["replicate", "elevenlabs"]
State = Literal["works", "unusable", "missing", "unchecked"]

REPLICATE_TOKENS = "https://replicate.com/account/api-tokens"
REPLICATE_BILLING = "https://replicate.com/account/billing"
ELEVENLABS_KEYS = "https://elevenlabs.io/app/settings/api-keys"
ELEVENLABS_PLANS = "https://elevenlabs.io/app/subscription"

READS = {"replicate": "https://api.replicate.com/v1/account",
         "elevenlabs": "https://api.elevenlabs.io/v1/user/subscription"}
SECRETS = {"replicate": "replicate_api_token", "elevenlabs": "elevenlabs_api_key"}
_TIMEOUT = 10   # the doctor waits at most this long per provider

# ElevenLabs' codes (`code`, or the legacy `status`), from its errors page; the legacy ones are unverified live.
_EL_KEY = {"invalid_api_key", "missing_api_key", "api_key_expired", "authentication_error"}
_EL_PERMISSION = {"insufficient_permissions", "missing_permissions"}
_EL_CREDIT = {"insufficient_credits", "payment_required", "quota_exceeded"}
_EL_PLAN = {"feature_not_available", "subscription_required"}
_EL_RATE = {"rate_limit_exceeded", "concurrent_limit_exceeded", "system_busy", "too_many_concurrent_requests",
            "rate_limit_error"}


def _codes(body: object) -> set[str]:
    """The code words an answer carries: ElevenLabs' detail.code / detail.status / detail.type."""
    detail = body.get("detail", body) if isinstance(body, dict) else body
    if isinstance(detail, dict):
        return {str(detail[k]).lower() for k in ("code", "status", "type") if isinstance(detail.get(k), str)}
    return set()


def detail_text(body: object) -> str:
    """The provider's own short explanation, for the message (scrubbed by the caller)."""
    if isinstance(body, dict):
        detail = body.get("detail", body)
        if isinstance(detail, dict):
            text = " ".join(str(detail[k]) for k in ("code", "status", "message") if detail.get(k))
            return (text or json.dumps(detail))[:300]
        if detail is not None:
            title = body.get("title")
            return (f"{title}: {detail}" if title and title != detail else str(detail))[:300]
        return json.dumps(body)[:300]
    return str(body)[:300]


def cause(provider: Provider, status: int, body: object) -> str | None:
    """Why the provider refused: "key", "permission", "credit", "plan", "rate", or None for an answer we don't know."""
    if provider == "replicate":
        text = detail_text(body).lower()
        if status == 401:
            return "key"         # unverified live: HTTP's meaning, not on Replicate's docs pages
        if status == 402 or "insufficient credit" in text or "out of credit" in text:
            return "credit"      # unverified live: no docs page lists Replicate's no-credit answer
        if status == 429:
            return "rate"        # documented: "Request was throttled"
        return None
    codes = _codes(body)
    if status == 429 or codes & _EL_RATE:
        return "rate"
    if codes & _EL_PERMISSION:
        return "permission"
    if codes & _EL_CREDIT or status == 402:
        return "credit"
    if codes & _EL_PLAN:
        return "plan"
    if codes & _EL_KEY:
        return "key"
    if status == 403:
        return "plan"            # today's reading of a 403 without a code we know
    return None


_FEATURE = {"clone": "keys.elevenlabs.plan_clone", "music": "keys.elevenlabs.plan_music"}


def refusal(provider: Provider, cause_: str | None, *, status: int, detail: str | None, what: str,
            need: str | None = None, feature: str | None = None) -> str:
    """The message for one refusal: what happened, that nothing was spent, the fix with its link, and that the run
    continues from the same place. `detail` is the provider's own words (scrubbed by the caller; None leaves them
    out), `need` this step's approved estimate ("$0.40", "1200 credits")."""
    name = cause_ if cause_ in ("key", "permission", "credit", "plan", "rate") else "other"
    if provider == "replicate" and name in ("permission", "plan"):
        name = "other"
    values = {"said": f"({status}: {detail})" if detail else "", "what": what,
              "need": i18n.t("keys.need", need=need) if need else "",
              "which": i18n.t(_FEATURE[feature]) if name == "plan" and feature in _FEATURE else "",
              "permissions": i18n.t("keys.elevenlabs.permissions")}
    text = " ".join(i18n.t(f"keys.{provider}.{name}", **values).split())   # an empty part leaves no double space
    return text.replace(" .", ".").replace(" ,", ",").replace(" :", ":")


def estimate() -> float | None:
    """The approved estimate of this paid call, which `tm tool` passes the tool (TM_COST_ESTIMATE)."""
    try:
        value = float(os.environ.get("TM_COST_ESTIMATE", ""))
    except ValueError:
        return None
    return value if math.isfinite(value) and value > 0 else None


def need(provider: Provider) -> str | None:
    value = estimate()
    if value is None:
        return None
    return f"${value:.2f}" if provider == "replicate" else f"{value:g} credits"


def left(subscription: dict) -> int | None:
    """ElevenLabs credits left this period, with what usage-based billing may add; None when we can't tell (no counts,
    or overage with no cap). `max_credit_limit_extension` is the documented field ("unlimited", or 0 = off)."""
    try:
        base = int(subscription["character_limit"]) - int(subscription["character_count"])
    except (KeyError, TypeError, ValueError):
        return None
    if subscription.get("can_extend_character_limit") is True:
        extension = subscription.get("max_credit_limit_extension")
        if isinstance(extension, bool) or not isinstance(extension, int):
            return None          # "unlimited", or not said: the account may go on, we can't tell how far
        return max(base, 0) + extension
    return max(base, 0)


@dataclass(frozen=True)
class Check:
    provider: str
    state: State
    cause: str | None = None
    fix: str = ""                # our words (never the provider's text, never the key) for an unusable key
    left: int | None = None      # ElevenLabs: credits left, as `left()` reads them
    cloning: bool | None = None  # ElevenLabs: can_use_instant_voice_cloning, when the answer says so as a boolean


class _Answer:
    def __init__(self, status: int, body: object):
        self.status_code, self._body = status, body

    def json(self):
        if isinstance(self._body, str):
            raise ValueError("not JSON")
        return self._body


def _get(url: str, headers: dict | None = None, timeout: float | None = None):
    import requests

    return requests.get(url, headers=headers, timeout=timeout)


def _answer(provider: Provider, headers: dict):
    """The provider's answer to the free read. In the evals' sandbox (no network), TM_PROVIDER_ANSWERS names a JSON
    file of {provider: {"status", "body"}} that answers instead, as TM_PLANS_FILE does for the plans; a provider
    missing from it is unreachable."""
    fake = os.environ.get("TM_PROVIDER_ANSWERS")
    if fake:
        try:
            got = json.loads(open(fake, encoding="utf-8").read()).get(provider)
        except (OSError, ValueError, AttributeError):
            got = None
        if not isinstance(got, dict):
            raise ConnectionError("no answer")
        return _Answer(int(got.get("status", 200)), got.get("body"))
    return _get(READS[provider], headers=headers, timeout=_TIMEOUT)


def check(provider: Provider) -> Check:
    """One free authenticated read: does the key work? States only; nothing is printed or written."""
    from tm import secrets

    key = secrets.get(SECRETS[provider])  # type: ignore[arg-type]
    if not key:
        return Check(provider, "missing")
    headers = {"Authorization": f"Bearer {key}"} if provider == "replicate" else {"xi-api-key": key}
    try:
        resp = _answer(provider, headers)
    except Exception:  # noqa: BLE001 - any failure to reach the provider is "not checked", never a crash
        return Check(provider, "unchecked")
    finally:
        del key, headers
    try:
        body = resp.json()
    except ValueError:
        body = None
    if resp.status_code >= 400:
        why = cause(provider, resp.status_code, body)
        what = i18n.t("keys.what_check")
        # our words only: the provider's detail could quote the key back, so it stays out of the doctor's card
        return Check(provider, "unusable", why, refusal(provider, why, status=resp.status_code, detail=None, what=what))
    if provider == "replicate":
        return Check(provider, "works") if isinstance(body, dict) else Check(provider, "unchecked")
    if not isinstance(body, dict) or left(body) is None and "character_limit" not in body:
        return Check(provider, "unchecked")
    cloning = body.get("can_use_instant_voice_cloning")
    cloning = cloning if isinstance(cloning, bool) else None
    remaining = left(body)
    if remaining is not None and remaining <= 0:
        return Check(provider, "unusable", "credit", i18n.t("keys.elevenlabs.empty"), 0, cloning)
    return Check(provider, "works", None, "", remaining, cloning)
