"""The model review every two weeks (issue #115, section 5): public rankings and prices against the model registry.

    python3 .github/scripts/model_review.py [--today YYYY-MM-DD] [--dry-run] [--snapshot FILE] [--save FILE]

It reads only free, public pages (no paid key): Arena's leaderboard dataset on Hugging Face (text-to-image, image
edit, image-to-video, text-to-video), Artificial Analysis' leaderboard pages (images, video, speech, music), Replicate's
public model pages (prices from `billingConfig`, availability) and collections, and ElevenLabs' models page. It
matches what it read to the registry through the alias table (`data/models/aliases.yaml`); a name it can't match is
listed "to match". It then opens ONE issue for the owner (mentioning @piotr-lezon, so the owner gets an email), e.g.
"Model review 2026-11-17 – 2026-12-01", with the new models near the top of a ranking that are on Replicate (what they
do, price per unit, ranking places, a proposed test and its estimated cost), the changes of price, availability or
ranking of the registry's models, and the models gone from Replicate with the routes they are in.

**Nothing in the registry is changed**, not even a price: the owner tests locally and writes the decisions in the
issue; the maintainer applies exactly those and closes it. `compare` and `render` are pure (the tests give them a saved
snapshot); only `fetch_snapshot` touches the network.
"""

from __future__ import annotations

import argparse
import html as htmllib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "plugins" / "trendsmesh-playbooks" / "data" / "models"
OWNER = "piotr-lezon"                       # the owner's GitHub login (verified with `gh api users/piotr-lezon`)
TOP = 10                                    # a new model counts when it ranks this high
UA = {"User-Agent": "Mozilla/5.0 (trendsmesh-playbooks model review)"}
ARENA = ("https://datasets-server.huggingface.co/rows?dataset=lmarena-ai/leaderboard-dataset&config={config}"
         "&split=latest&offset=0&length=100")
# each ranking: (source, board) -> the registry tasks it ranks
BOARDS = {
    ("arena", "text_to_image"): ("photos", "illustrations"),
    ("arena", "image_edit"): ("image_edit",),
    ("arena", "image_to_video"): ("image_to_video",),
    ("arena", "text_to_video"): ("text_to_video",),
    ("artificial_analysis", "image/leaderboard/text-to-image"): ("photos", "illustrations"),
    ("artificial_analysis", "video/leaderboard/image-to-video"): ("image_to_video",),
    ("artificial_analysis", "video/leaderboard/text-to-video"): ("text_to_video",),
    ("artificial_analysis", "text-to-speech/leaderboard"): ("voiceover",),
    ("artificial_analysis", "music/leaderboard"): ("music",),
}
COLLECTIONS = ("text-to-image", "image-to-video", "text-to-video")   # Replicate's, where a new model is looked for
ELEVENLABS = "https://elevenlabs.io/docs/overview/models"
# what a proposed test makes, per task: (how many, the unit's quantity each) -> 3 images, or 3 takes of 15 s
TEST = {"image": (3, 1), "second": (3, 15), "character": (3, 300), "minute": (3, 1), "run": (3, 1)}
_AA_ROW = re.compile(r'"formatted":\{"rank":(\d+),.{0,600}?"values":\{"id":"[^"]*","name":"([^"]+)"', re.S)
_EL_ID = re.compile(r"\b(eleven_[a-z0-9_]+|scribe_v\d+[a-z0-9_]*|music_v[0-9_]+)\b")
_KEY = re.compile(r'"billingConfig"\s*:\s*(?=\{)')


# --- names -----------------------------------------------------------------------------------------------------

def norm(name: str) -> str:
    """A name as compared: lower case, without a bracketed variant ("(Medium)", "(720p)"), a maker's prefix
    ("Dreamina"), or punctuation; "v2" is "2"."""
    text = re.sub(r"\([^)]*\)", " ", str(name).lower())
    text = text.rsplit("/", 1)[-1] if "/" in text and " " not in text.strip() else text
    text = re.sub(r"\bdreamina\b", " ", text)
    text = re.sub(r"[^a-z0-9.]+", " ", text).replace(".", " ")
    text = re.sub(r"\bv(\d)", r"\1", text)
    return " ".join(text.split())


def name_index(registry: dict, aliases: dict) -> dict[str, str]:
    """Every name a registry model goes by (its aliases, its registry name, its id's name), normalised -> its id."""
    out: dict[str, str] = {}
    for m in [*(registry.get("models") or []), *(registry.get("left_out") or [])]:
        for n in (m["id"], m.get("name") or ""):
            if n:
                out.setdefault(norm(n), m["id"])
    for mid, names in (aliases or {}).items():
        for source in ("arena", "artificial_analysis"):
            for n in (names or {}).get(source) or []:
                out[norm(n)] = mid
    return out


def _replicate_match(name: str, ids: list[str]) -> str | None:
    """The Replicate id of a ranked name (a new model found in a collection): the one whose name is the same, else
    the shortest whose name holds every word of it; None when there is none."""
    want = norm(name)
    same = [i for i in ids if norm(i) == want]
    if same:
        return same[0]
    found = [i for i in ids if want and set(want.split()) <= set(norm(i).split())]
    return min(found, key=len) if found else None


# --- prices ----------------------------------------------------------------------------------------------------

def _usd(text: object) -> float | None:
    try:
        return float(str(text).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def live_usd(entry: dict, variant: dict) -> float | None:
    """A registry variant's price today in its own unit, from a Replicate price entry, or None."""
    live = variant.get("live") or {}
    tier = next((t for t in entry.get("tiers") or [] if t.get("criteria") == live.get("criteria")), None)
    price = _usd((tier or {}).get("price"))
    return None if price is None else round(price * float(live.get("factor", 1)), 6)


def _cheapest(entry: dict) -> str:
    tiers = [t for t in entry.get("tiers") or [] if _usd(t.get("price")) is not None]
    if not tiers:
        return "no price on its page"
    t = min(tiers, key=lambda x: _usd(x["price"]))
    return f"{t['price']} per {t.get('unit') or 'unit'} ({t.get('criteria')})"


# --- the comparison --------------------------------------------------------------------------------------------

def _routes_of(registry: dict, mid: str) -> list[str]:
    out = []
    routes = registry.get("routes") or {}
    for sit, r in ((routes.get("talking_person") or {}).get("situations") or {}).items():
        if mid in (r.get("model"), r.get("then"), r.get("plus"), *(r.get("also") or [])):
            out.append(f"talking person: {sit}")
    for r in routes.get("voice") or []:
        if mid in (r.get("model"), r.get("then"), r.get("budget")):
            out.append(f"voice: {r.get('route')}")
    if (routes.get("lipsync_fallback") or {}).get("model") == mid:
        out.append("lip-sync fallback")
    return out


def compare(registry: dict, aliases: dict, snapshot: dict, *, top: int = TOP) -> dict:
    """What the owner should look at: `{new, to_match, rankings, price_changes, gone, elevenlabs_new, errors}`."""
    index = name_index(registry, aliases)
    models = {m["id"]: m for m in registry.get("models") or []}
    active = {i for i, m in models.items() if m.get("status") == "active"}
    left = {e["id"] for e in registry.get("left_out") or []}
    collection_ids = sorted({i for ids in (snapshot.get("collections") or {}).values() for i in ids})
    replicate = snapshot.get("replicate") or {}
    new: dict[str, dict] = {}
    to_match: dict[str, dict] = {}
    places: dict[str, list[str]] = {}
    for key, rows in (snapshot.get("rankings") or {}).items():
        source, board = key.split(":", 1)
        tasks = BOARDS.get((source, board), ())
        for row in sorted((r for r in rows if isinstance(r.get("rank"), int) and r["rank"] <= top),
                          key=lambda r: r["rank"]):
            name, rank = row.get("name") or "", row.get("rank")
            where = f"#{rank} {source.replace('_', ' ').title()} {board.split('/')[-1]}"
            mid = index.get(norm(name))
            if mid is not None:
                if mid in models:
                    places.setdefault(mid, []).append(where)
                continue                                   # a registry model, or one left out after a test
            rid = _replicate_match(name, collection_ids)
            if rid is None:
                to_match.setdefault(norm(name), {"name": name, "places": []})["places"].append(where)
                continue
            if rid in models or rid in left:
                if rid in models:
                    places.setdefault(rid, []).append(where)
                continue
            got = new.setdefault(rid, {"model": rid, "name": name, "places": [], "tasks": []})
            got["places"].append(where)
            got["tasks"] += [t for t in tasks if t not in got["tasks"]]
    for got in new.values():
        entry = replicate.get(got["model"]) or {}
        got["price"] = _cheapest(entry) if "error" not in entry else f"no price ({entry['error']})"
        unit_tasks = [(registry.get("tasks") or {}).get(t, {}).get("unit", "run") for t in got["tasks"]] or ["run"]
        tiers = [_usd(t.get("price")) for t in entry.get("tiers") or [] if _usd(t.get("price")) is not None]
        each = min(tiers) if tiers else None
        n, qty = TEST.get(unit_tasks[0], (3, 1))
        got["test"] = (f"{n} {'takes of ' + str(qty) + ' s' if unit_tasks[0] == 'second' else 'runs'} for each of "
                       f"{', '.join(got['tasks']) or 'its task'}, against the task's selected model")
        got["test_usd"] = round(each * n * qty * max(1, len(got["tasks"])), 2) if each is not None else None
    price_changes, gone = [], []
    for mid in sorted(active):
        m = models[mid]
        if m.get("provider") != "replicate":
            continue
        entry = replicate.get(mid)
        if entry is None:
            continue                                   # not read this time (a fetch error is in errors)
        priced = any(v.get("live") for v in (m.get("variants") or {}).values())
        if "error" in entry and (priced or entry.get("available") is False):
            gone.append({"model": mid, "why": entry["error"], "tasks": sorted(m.get("tasks") or {}),
                         "routes": _routes_of(registry, mid)})
            continue
        if "error" in entry:
            continue                                   # billed by hardware time: its page is there, with no price
        for vname, var in (m.get("variants") or {}).items():
            if not var.get("live"):
                continue
            now, was = live_usd(entry, var), (var.get("price") or {}).get("usd")
            if now is None:
                price_changes.append({"model": mid, "variant": vname, "was": was, "now": None,
                                      "note": f"no tier {var['live'].get('criteria')!r} on the page today"})
            elif was is not None and abs(now - was) > max(0.0005, was * 0.01):
                price_changes.append({"model": mid, "variant": vname, "was": was, "now": now, "note": ""})
    el_page = snapshot.get("elevenlabs")
    el_new, el_gone = [], []
    if isinstance(el_page, list):
        known = {i for i, m in models.items() if m.get("provider") == "elevenlabs"}
        el_new = sorted(i for i in el_page if i not in known and i not in left)
        el_gone = sorted(i for i in active & known if _EL_ID.fullmatch(i) and i not in el_page)
    gone += [{"model": i, "why": "not on ElevenLabs' models page", "tasks": sorted(models[i].get("tasks") or {}),
              "routes": _routes_of(registry, i)} for i in el_gone]
    return {"new": sorted(new.values(), key=lambda g: g["places"][0]), "to_match": list(to_match.values()),
            "rankings": {mid: p for mid, p in sorted(places.items()) if mid in active},
            "price_changes": price_changes, "gone": gone, "elevenlabs_new": el_new,
            "errors": list(snapshot.get("errors") or [])}


def render(report: dict, start: date, end: date, *, registry_checked: str = "") -> tuple[str, str]:
    """The issue's title and body (Markdown)."""
    title = f"Model review {start.isoformat()} – {end.isoformat()}"
    out = [f"@{OWNER}: the two-weekly model review. Nothing in the registry was changed: test what you want locally, "
           "then write your decisions here (group, ★, removals), and the maintainer applies exactly those.",
           "", f"Registry prices last read: {registry_checked or 'unknown'}.", ""]
    out.append("## New models near the top of a ranking, on Replicate")
    if report["new"]:
        out += ["| Model | Ranked | Price per unit | Proposed test | Estimated cost |", "|---|---|---|---|---|"]
        for g in report["new"]:
            cost = f"${g['test_usd']:.2f}" if g.get("test_usd") is not None else "price it first"
            out.append(f"| `{g['model']}` ({g['name']}) | {'; '.join(g['places'])} | {g['price']} | {g['test']} | "
                       f"{cost} |")
    else:
        out.append("None this time.")
    out += ["", "## Changes for the registry's models", "", "**Prices**"]
    if report["price_changes"]:
        for c in report["price_changes"]:
            now = f"${c['now']:g}" if c["now"] is not None else "?"
            out.append(f"- `{c['model']}` {c['variant']}: ${c['was']:g} in the registry, {now} today"
                       + (f" ({c['note']})" if c["note"] else ""))
    else:
        out.append("- No price changed.")
    out += ["", "**Ranking places today**"]
    out += [f"- `{mid}`: {'; '.join(p)}" for mid, p in report["rankings"].items()] or ["- None in the top places."]
    out += ["", "## Gone from Replicate or ElevenLabs"]
    if report["gone"]:
        for g in report["gone"]:
            where = "; ".join(g["routes"]) or "no route"
            out.append(f"- `{g['model']}` ({g['why']}): tasks {', '.join(g['tasks']) or 'none'}; routes: {where}")
    else:
        out.append("None.")
    if report["elevenlabs_new"]:
        out += ["", "## On ElevenLabs' models page, not in the registry", ", ".join(f"`{i}`"
                                                                                for i in report["elevenlabs_new"])]
    out += ["", "## To match (names the alias table doesn't know)"]
    out += [f"- {t['name']}: {'; '.join(t['places'])}" for t in report["to_match"]] or ["None."]
    if report["errors"]:
        out += ["", "## Not read this time"] + [f"- {e}" for e in report["errors"]]
    out += ["", "_Opened by `.github/workflows/model-review.yml` (issue #115). It reads only public pages and never "
            "edits `data/models/registry.yaml`._"]
    return title, "\n".join(out) + "\n"


# --- reading the public pages (network) ------------------------------------------------------------------------

def _get(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:     # noqa: S310 (public https pages only)
        return resp.read().decode("utf-8", "replace")


def parse_arena(text: str) -> list[dict]:
    rows = [r.get("row") or {} for r in (json.loads(text).get("rows") or [])]
    return [{"name": r["model_name"], "rank": r.get("rank")} for r in rows
            if r.get("category") == "overall" and r.get("model_name")]


def parse_aa(text: str) -> list[dict]:
    seen: dict[str, int] = {}
    for rank, name in _AA_ROW.findall(text.replace('\\"', '"')):
        seen.setdefault(name, int(rank))
    return [{"name": n, "rank": r} for n, r in sorted(seen.items(), key=lambda x: x[1])]


def parse_billing(text: str) -> dict:
    """A Replicate page's prices, read as `tm tool replicate_price` reads them (the same criteria words, so the
    registry's `live.criteria` names the same tier): `{tiers}` or `{error}`."""
    plain = htmllib.unescape(text)
    config = None
    for page in (text, plain, plain.replace('\\"', '"')):
        for m in _KEY.finditer(page):
            try:
                found, _ = json.JSONDecoder().raw_decode(page, m.end())
            except ValueError:
                continue
            if isinstance(found, dict):
                config = found
                break
        if config is not None:
            break
    if config is None:
        return {"error": "billingConfig not found"}
    tiers = []
    for tier in config.get("current_tiers") or []:
        crit = ", ".join(f"{c.get('title')}={c.get('value')}" for c in tier.get("criteria") or []) or "all"
        for p in tier.get("prices") or []:
            tiers.append({"criteria": crit, "price": p.get("price"), "unit": p.get("metric_display") or p.get("title")})
    return {"tiers": tiers} if tiers else {"error": "billingConfig holds no prices"}


def parse_collection(text: str) -> list[str]:
    skip = {"collections", "explore", "docs", "pricing", "blog", "about", "signin", "account", "changelog", "terms",
            "privacy", "search"}
    return sorted({m for m in re.findall(r'href="/([a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9._-]*)"', htmllib.unescape(text))
                   if m.split("/", 1)[0] not in skip})


def fetch_snapshot(registry: dict) -> dict:
    snap: dict = {"rankings": {}, "replicate": {}, "collections": {}, "elevenlabs": None, "errors": []}
    for source, board in BOARDS:
        url = (ARENA.format(config=board) if source == "arena" else f"https://artificialanalysis.ai/{board}")
        try:
            text = _get(url)
            snap["rankings"][f"{source}:{board}"] = parse_arena(text) if source == "arena" else parse_aa(text)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            snap["errors"].append(f"{source} {board}: {exc}")
    for slug in COLLECTIONS:
        try:
            snap["collections"][slug] = parse_collection(_get(f"https://replicate.com/collections/{slug}"))
        except (urllib.error.URLError, OSError) as exc:
            snap["errors"].append(f"Replicate collection {slug}: {exc}")
    ids = [m["id"] for m in registry.get("models") or [] if m.get("provider") == "replicate"
           and m.get("status") == "active"]
    pending = compare(registry, {}, {**snap, "replicate": {}})["new"]      # the new ones to price too
    for mid in list(dict.fromkeys(ids + [g["model"] for g in pending])):
        try:
            snap["replicate"][mid] = parse_billing(_get(f"https://replicate.com/{mid}"))
        except urllib.error.HTTPError as exc:
            snap["replicate"][mid] = {"error": f"HTTP {exc.code}", "available": False} if exc.code == 404 else None
            if exc.code != 404:
                snap["errors"].append(f"Replicate {mid}: {exc}")
        except (urllib.error.URLError, OSError) as exc:
            snap["errors"].append(f"Replicate {mid}: {exc}")
    snap["replicate"] = {k: v for k, v in snap["replicate"].items() if v is not None}
    try:
        snap["elevenlabs"] = sorted(set(_EL_ID.findall(_get(ELEVENLABS))))
    except (urllib.error.URLError, OSError) as exc:
        snap["errors"].append(f"ElevenLabs models page: {exc}")
    return snap


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _open_issue(title: str, body: str) -> str:
    found = subprocess.run(["gh", "issue", "list", "--state", "open", "--search", f'"{title}" in:title',
                            "--json", "title", "--jq", ".[].title"], capture_output=True, text=True, check=True)
    if title in found.stdout.splitlines():
        return f"An open issue already has the title {title!r}: nothing opened."
    done = subprocess.run(["gh", "issue", "create", "--title", title, "--body-file", "-"], input=body,
                          capture_output=True, text=True, check=True)
    return done.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--today", type=date.fromisoformat, default=date.today())
    p.add_argument("--dry-run", action="store_true", help="print the issue instead of opening it")
    p.add_argument("--snapshot", type=Path, help="compare a saved snapshot (JSON) instead of reading the pages")
    p.add_argument("--save", type=Path, help="also save the snapshot read (JSON)")
    a = p.parse_args(argv)
    registry, aliases = load(DATA / "registry.yaml"), load(DATA / "aliases.yaml")
    snap = json.loads(a.snapshot.read_text(encoding="utf-8")) if a.snapshot else fetch_snapshot(registry)
    if a.save:
        a.save.write_text(json.dumps(snap, indent=1), encoding="utf-8")
    report = compare(registry, aliases, snap)
    title, body = render(report, a.today - timedelta(days=14), a.today, registry_checked=str(registry.get("checked")))
    if a.dry_run:
        print(title + "\n\n" + body)
        return 0
    print(_open_issue(title, body))
    return 0


if __name__ == "__main__":
    sys.exit(main())
