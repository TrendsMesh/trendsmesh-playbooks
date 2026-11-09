"""replicate_price: live prices from Replicate's public model pages (free: no key, no budget).

    tm tool replicate_price --run RUN MODEL [MODEL ...] [--collection SLUG] [--json]

Every model page embeds a `billingConfig` JSON (the "Pricing" popover): tiers with criteria (a model
variant, a resolution) and prices per unit. The visible "$0.0001 per second" text is a placeholder;
only `billingConfig` is the price, and a page without it gives an `error` entry, never a price of 0
(lesson 11). Writes the next `02_research/models/prices_<YYYY-MM-DD>_vNN.json`, a list of
`{model, checked, tiers: [{criteria, price, unit}]}` or `{model, error}`, and a manifest row. Record
the price and its check date with every cost estimate.
"""

from __future__ import annotations

import json
import re
from datetime import date
from html import unescape

import requests

from tm.tools import _common as c

UA = {"User-Agent": "Mozilla/5.0 (playbooks price check)"}
SOURCE = "replicate.com model page billingConfig"
STAGE = "02_research/models"
_NOT_MODELS = {"collections", "explore", "docs", "pricing", "blog", "about", "signin", "account",
               "changelog", "terms", "privacy"}


def today() -> str:
    return date.today().isoformat()


def fetch(url: str) -> str:
    return requests.get(url, headers=UA, timeout=30).text


_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
_KEY = re.compile(r'"billingConfig"\s*:\s*(?=\{)')


def find_config(html: str) -> dict | None:
    """The object after the `billingConfig` key, whatever the key order, and also when the page has
    HTML entities (&quot;) or backslash-escaped JSON inside a script string."""
    plain = unescape(html)
    for text in (html, plain, plain.replace('\\"', '"')):
        for m in _KEY.finditer(text):
            try:
                cfg, _ = json.JSONDecoder().raw_decode(text, m.end())
            except ValueError:
                continue
            if isinstance(cfg, dict):
                return cfg
    return None


def billing(model: str, checked: str) -> dict:
    if not _MODEL.match(model):
        return {"model": model, "error": "not a model name (owner/name: letters, digits, - _ .)"}
    try:
        html = fetch(f"https://replicate.com/{model}")
    except requests.RequestException as exc:
        return {"model": model, "error": f"page could not be read: {type(exc).__name__}"}
    cfg = find_config(html)
    if cfg is None:
        return {"model": model, "error": "billingConfig not found"}
    tiers = []
    for t in cfg.get("current_tiers") or []:
        crit = ", ".join(f"{x.get('title')}={x.get('value')}" for x in t.get("criteria") or []) or "all"
        for p in t.get("prices") or []:
            tiers.append({"criteria": crit, "price": p.get("price"),
                          "unit": p.get("metric_display") or p.get("title")})
    if not tiers:
        return {"model": model, "error": "billingConfig holds no prices"}
    return {"model": model, "checked": checked, "tiers": tiers}


def collection(slug: str) -> list[str]:
    html = fetch(f"https://replicate.com/collections/{slug}")
    seen: list[str] = []
    for owner, name in re.findall(r'href="/([a-z0-9-]+)/([a-z0-9.\-_]+)"', html):
        key = f"{owner}/{name}"
        if owner not in _NOT_MODELS and key not in seen:
            seen.append(key)
    return seen


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("replicate_price", "Read the live prices of Replicate models from their public pages.")
    p.add_argument("models", nargs="*", help="owner/name of each model")
    p.add_argument("--collection", help="also every model of this Replicate collection (a slug)")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    models = list(a.models)
    if a.collection:
        try:
            models += [m for m in collection(a.collection) if m not in models]
        except requests.RequestException as exc:
            raise c.ToolError(f"The collection {a.collection} could not be read ({type(exc).__name__}).") from None
    if not models:
        raise c.ToolError("Name at least one model (owner/name) or a --collection.")
    day = today()
    results = [billing(m, day) for m in models]
    if all("error" in r for r in results):
        raise c.ToolStop("No price could be read: " + "; ".join(f"{r['model']}: {r['error']}" for r in results)
                         + ". Nothing was written; check the model names and the connection.")
    target = c.output(run, a.out, STAGE, f"prices_{day}", "json")
    c.write_json(target, results)
    c.record(run, target, SOURCE, params={"models": models})
    out = c.rel(run, target)
    lines = []
    for r in results:
        if "error" in r:
            lines.append(f"{r['model']}: {r['error']}")
        else:
            lines.append(f"{r['model']}: " + "; ".join(
                f"{t['price']} per {t['unit']} ({t['criteria']})" for t in r["tiers"]))
    return c.finish(a, {"tool": "replicate_price", "outputs": [out], "results": results},
                    "\n".join([*lines, f"Wrote {out}"]))


if __name__ == "__main__":
    raise SystemExit(main())
