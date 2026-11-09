"""The trend shortlist: the handoff's tools/pb2/trend_shortlist.py, ported for every playbook.

    tm trends shortlist --run RUN --terms T [T ...] [--inputs GLOB ...] [--market-language en]
                        [--exclude-terms T ...] [--top 10] [--min-topics 3] [--today YYYY-MM-DD]
                        [--sounds-commercial-only] [--anchor-terms T ...] [--sound-relevance]
                        [--recent-days N] [--json]

It ranks saved TrendsMesh answers into four lists (hooks, topics, formats, sounds) and writes
`03_wip/trend_shortlist_vNN.json` and `.md`. Inputs default to the run's saved answers:
`02_research/search/*.json`, `lists/*.json`, `trend_*.json` and `videos/*.json`; `--inputs` takes
other files or globs, such as the handoff's legacy `search_*.json`, `rising_*.json`, `trend_<id>.json`
and `videos_<id>.json`. Shared by PB02 (creative brief), PB03 (organic video) and PB04.

The scoring is the original's, every constant verbatim (its module docstring explains it):

- HOOKS (hook_trend), and formats and sounds scored like them: usability, 0-100,
  `100 * signals * status_mult * language_mult * sensitivity_mult + fit_bonus`, where signals =
  .10 momentum + .32 creators + .22 lift + .22 recency + .14 adoption.
- TOPICS (everything else): relevance to the terms first (whole words with light suffixes; name 3,
  what_it_is 2, examples 1 by share; each term weighted by its rarity in the pool), minus noise
  penalties (excluded terms 6, `trends.DEFAULT_NOISE` 4, a possessive proper name 3, a one-off
  spike 3), then the same signals. Zero relevance or noise outweighing it drops the topic.
- A `contradicted` trend is excluded. The output never says "no category trend": with fewer than
  `--min-topics` topics, the best-signal topics with no noise flag fill the list, marked
  "weak fit (no term match)".

Query labels (each trend's `found_by`): a file the plugin saved (`trends.save_answer`'s envelope)
is labelled from its `_input`: a search by `about`, a trend by `detail:<id[:8]>`, a list by
`<sort>:<trend_type>`, and video pages join their trend by `_input.trend_id`. A legacy file keeps
the original's `query_label` verbatim.

The plugin's filters for organic video (`--anchor-terms`, `--sound-relevance`, `--recent-days`; see
`apply_filters`) add a `plugin` block to the rows they touch, `meta.plugin`, `anchor_dropped` and a
"Plugin filters" section. Without them the output equals the original's.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from tm import cli, manifest, trends
from tm.runfolder import ReadOnlyError, RunFolder

# ---------------------------------------------------------------------------- weights (verbatim)

HOOK_WEIGHTS = {"momentum": 0.10, "creators": 0.32, "lift": 0.22, "recency": 0.22, "adoption": 0.14}
STATUS_MULT = {"confirmed": 1.0, "unconfirmed": 0.8}
MOMENTUM_SCORE = {"rising": 1.0, "holding": 0.75, None: 0.3}
MOMENTUM_OTHER = 0.15
SENSITIVITY_MULT = {None: 1.0, "none": 1.0, "low": 0.85, "medium": 0.55, "high": 0.25}
LANG_MATCH, LANG_INFERRED, LANG_UNKNOWN, LANG_FOREIGN = 1.0, 0.9, 0.7, 0.45
CREATORS_CAP = 50
LIFT_UNKNOWN = 0.35
ADOPTION_FULL_PCT, ADOPTION_UNKNOWN = 50.0, 0.3
CONTRADICTION_STATUS_COST = 0.1
RECENCY_FULL_DAYS, RECENCY_ZERO_DAYS = 7, 60
HOOK_FIT_BONUS_MAX = 10.0

FIELD_WEIGHTS = {"name": 3.0, "what_it_is": 2.0, "examples": 1.0}
TOPIC_REL_SHARE = 0.6
TOPIC_REL_SCALE = 6.0
PENALTY_EXCLUDE, PENALTY_NOISE, PENALTY_PROPER_NAME, PENALTY_SPIKE = 6.0, 4.0, 3.0, 3.0
SPIKE_MAX_DAYS = 3

STOPWORDS = {
    "en": "the and you to of is it that this my i in for with what your me are be so on was just".split(),
    "es": "el la los las de que y en un una es por con para mi tu lo se como pero".split(),
    "pt": "o a os as de que e em um uma é por com para meu não você isso".split(),
    "pl": "i w na nie się to że jest z do jak co ale tak mi ja ten".split(),
    "de": "der die das und ist nicht ich du mit ein eine zu auf für wie".split(),
    "fr": "le la les de et est un une je tu pas que pour avec sur ce".split(),
    "it": "il la di che e è un una non per con mi ti questo sono".split(),
}
SCRIPTS = [("ru", r"[\u0400-\u04FF]"), ("ar", r"[\u0600-\u06FF]"), ("hi", r"[\u0900-\u097F]"),
           ("th", r"[\u0E00-\u0E7F]"), ("ko", r"[\uAC00-\uD7AF]"), ("ja", r"[\u3040-\u30FF]"),
           ("zh", r"[\u4E00-\u9FFF]")]

LICENCE_KEYS = ("license", "licence", "license_type", "licence_type", "music_license", "commercial_use", "commercial",
                "ads_allowed", "usage", "usage_rights", "rights")

STEM = "trend_shortlist"
DEFAULT_INPUTS = ("search/*.json", "lists/*.json", "trend_*.json", "videos/*.json")   # under 02_research


# ---------------------------------------------------------------------------- helpers

def parse_dt(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def split_terms(raw: str | None) -> list[str]:
    return [t.strip().lower() for t in (raw or "").split(",") if t.strip()]


def term_regex(term: str) -> re.Pattern:
    """Whole-word, case-insensitive, light suffixes on every word of the term."""
    parts = []
    for word in term.split():
        w = re.escape(word)
        if word.isalpha():
            if word.endswith("e"):
                w = re.escape(word[:-1]) + r"(?:e|es|ed|ing|er|ers)"
            else:
                w = w + r"(?:s|es|ed|ing|er|ers|y)?"
        parts.append(w)
    return re.compile(r"(?<![\w])" + r"[\s\-]+".join(parts) + r"(?![\w])", re.IGNORECASE)


def normalize_text(text: str) -> str:
    # "4:30am" -> "4am 4:30am" so an hour term matches clock times.
    return re.sub(r"\b(\d{1,2}):\d{2}\s?(am|pm)\b", r"\1\2 \g<0>", text or "", flags=re.IGNORECASE)


def detect_language(texts: list[str]) -> list[str]:
    """Very small script + stopword detector, used only when the API gives no languages."""
    votes: dict[str, int] = {}
    for text in texts:
        if not text or not text.strip():
            continue
        lang = None
        for code, pattern in SCRIPTS:
            if len(re.findall(pattern, text)) >= 3:
                lang = code
                break
        if lang is None:
            words = re.findall(r"[^\W\d_]+", text.lower())
            best, best_n = None, 0
            for code, sw in STOPWORDS.items():
                n = sum(1 for w in words if w in sw)
                if n > best_n:
                    best, best_n = code, n
            lang = best if best_n >= 1 else None
        if lang:
            votes[lang] = votes.get(lang, 0) + 1
    return sorted(votes, key=lambda k: -votes[k])


# ---------------------------------------------------------------------------- loading

def query_label(path: Path) -> str:
    """The original's label of a legacy file, from its name (verbatim)."""
    stem = path.stem
    for prefix, label in (("search_", ""), ("rising_", "rising:"), ("trend_", "detail:"),
                          ("videos_", "videos:")):
        if stem.startswith(prefix):
            rest = stem[len(prefix):]
            return label + (rest[:8] if label in ("detail:", "videos:") else rest.replace("_", " "))
    return stem.replace("_", " ")


def _saved(data: Any) -> bool:
    """A file the plugin saved: `trends.save_answer`'s envelope."""
    return isinstance(data, dict) and "_tool" in data and "answer" in data


def _read_file(path: Path) -> tuple[str, str, list] | None:
    """(`videos` and the trend id, or `trends` and the query label; the items). None for a saved
    answer that holds no trends (usage, Ad Library, an answer that is not JSON or an error)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if _saved(data):
        tool = data["_tool"]
        given = data.get("_input") if isinstance(data.get("_input"), dict) else {}
        answer = data["answer"]
        if trends.holds_no_cards(answer):
            return None
        if tool == "get_trend_videos":
            return "videos", str(given.get("trend_id") or ""), trends.videos(answer)[0]
        if tool == "search_trends":
            label = str(given.get("about") or "") or query_label(path)
        elif tool == "get_trend":       # no trend_id (a hand-written file): the card's id, else the name
            tid = given.get("trend_id") or next(
                (c["id"] for c in trends.items(answer) if isinstance(c, dict) and c.get("id")), None)
            label = f"detail:{str(tid)[:8]}" if tid else query_label(path)
        elif tool == "list_trends":
            label = f"{given.get('sort') or 'default'}:{given.get('trend_type') or 'all'}"
        else:
            return None
        return "trends", label, trends.items(answer)
    items = trends.items(data)
    if path.stem.startswith("videos_") or (items and isinstance(items[0], dict) and "kind" not in items[0]
                                           and "asset_id" in items[0]):
        return "videos", (path.stem.split("_", 1)[1] if "_" in path.stem else path.stem), items
    return "trends", query_label(path), items


def load_pool(paths: list[Path], skipped: list[Path] | None = None) -> tuple[dict, dict]:
    """Trends by id (merged: a detail answer wins, others fill gaps; examples de-duplicated) and the
    labels of the queries that found each. A file that cannot be read is skipped (added to
    `skipped` when given), as the reference tool did."""
    pool: dict[str, dict] = {}
    found_by: dict[str, list[str]] = {}
    extra_videos: dict[str, list[dict]] = {}
    for f in dict.fromkeys(Path(p) for p in paths):
        try:
            read = _read_file(f)
        except (OSError, ValueError):
            if skipped is not None:
                skipped.append(f)
            continue
        if read is None:
            continue
        what, label, items = read
        if what == "videos":
            if label:                     # an empty id would prefix-match every trend
                extra_videos.setdefault(label, []).extend(v for v in items if isinstance(v, dict))
            continue
        for t in items:
            if not isinstance(t, dict) or not t.get("id"):
                continue
            tid = t["id"]
            if tid in pool:  # keep the richer record, fill gaps from the other
                old = pool[tid]
                for k, v in t.items():
                    if v not in (None, "", [], {}) and (old.get(k) in (None, "", [], {}) or label.startswith("detail:")):
                        old[k] = v
            else:
                pool[tid] = dict(t)
            found_by.setdefault(tid, [])
            if label not in found_by[tid]:
                found_by[tid].append(label)
    for tid, vids in extra_videos.items():
        target = pool.get(tid) or next((t for k, t in pool.items() if k.startswith(tid)), None)
        if target is not None:
            target.setdefault("examples", [])
            target["examples"] = list(target["examples"]) + vids
    for t in pool.values():  # de-duplicate examples by asset id / url
        seen, uniq = set(), []
        for e in t.get("examples") or []:
            key = e.get("asset_id") or e.get("url")
            if key in seen:
                continue
            seen.add(key)
            uniq.append(e)
        t["examples"] = uniq
    return pool, found_by


# ---------------------------------------------------------------------------- scoring (verbatim)

def last_seen(t: dict) -> date | None:
    proof = t.get("proof") or {}
    d = parse_dt(proof.get("last_seen_at"))
    if d:
        return d
    pubs = [parse_dt(e.get("published")) for e in t.get("examples") or []]
    pubs = [p for p in pubs if p]
    since = parse_dt(t.get("since"))
    by_age = since + timedelta(days=int(t["active_for_days"])) if since and t.get("active_for_days") is not None else None
    cands = pubs + ([by_age] if by_age else [])
    return max(cands) if cands else None


def language_info(t: dict, market: str):
    langs = list((t.get("proof") or {}).get("languages") or t.get("languages") or [])
    inferred = False
    if not langs:
        texts = [(e.get("hook_text") or "") + " " + (e.get("excerpt") or "") for e in t.get("examples") or []]
        langs = detect_language(texts)
        inferred = bool(langs)
    if not langs:
        return [], False, LANG_UNKNOWN, False
    if market in langs:
        return langs, inferred, (LANG_INFERRED if inferred else LANG_MATCH), False
    return langs, inferred, LANG_FOREIGN, True


def signal_components(t: dict, today: date) -> dict:
    status = t.get("status")
    momentum = t.get("momentum")
    proof = t.get("proof") or {}
    creators = proof.get("distinct_creators") or (t.get("reach") or {}).get("creators") or 0
    lift = proof.get("median_view_lift")
    seen = last_seen(t)
    days_ago = (today - seen).days if seen else None
    if days_ago is None:
        recency = 0.3
    elif days_ago <= RECENCY_FULL_DAYS:
        recency = 1.0
    else:
        recency = clamp(1 - (days_ago - RECENCY_FULL_DAYS) / (RECENCY_ZERO_DAYS - RECENCY_FULL_DAYS))
    confs = t.get("confirmations") or []
    pcts = [float(x) for cf in confs if cf.get("source") == "youtube_scale" and cf.get("stands") == "supports"
            for x in re.findall(r"\((\d+(?:\.\d+)?)%\)", cf.get("says") or "")]
    adoption_pct = sorted(pcts)[len(pcts) // 2] if pcts else None
    contradictions = sum(1 for cf in confs if cf.get("stands") == "contradicts")
    return {
        "status_mult": clamp(STATUS_MULT.get(status, 0.0) - CONTRADICTION_STATUS_COST * contradictions),
        "adoption": ADOPTION_UNKNOWN if adoption_pct is None else clamp(adoption_pct / ADOPTION_FULL_PCT),
        "_adoption_pct": adoption_pct, "_contradictions": contradictions,
        "momentum": MOMENTUM_SCORE.get(momentum, MOMENTUM_OTHER),
        "creators": clamp(math.log10(1 + creators) / math.log10(1 + CREATORS_CAP)),
        "lift": LIFT_UNKNOWN if lift is None else clamp(0.5 + 0.5 * math.log10(max(lift, 1e-3))),
        "recency": recency,
        "_creators": creators, "_lift": lift, "_last_seen": seen.isoformat() if seen else None,
        "_days_ago": days_ago,
    }


def weighted_signals(c: dict) -> float:
    return sum(HOOK_WEIGHTS[k] * c[k] for k in HOOK_WEIGHTS)


def trend_fields(t: dict) -> dict[str, list[str]]:
    ex = t.get("examples") or []
    return {
        "name": [normalize_text(t.get("name") or "")],
        "what_it_is": [normalize_text(t.get("what_it_is") or "")],
        "examples": [normalize_text(" ".join(filter(None, [e.get("hook_text"), e.get("excerpt"), e.get("slot_fill")])))
                     for e in ex],
    }


def term_matches(fields: dict[str, list[str]], regexes: dict[str, re.Pattern]) -> dict[str, dict]:
    """term -> {field: share of texts matched}."""
    out = {}
    for term, rx in regexes.items():
        hit = {}
        for field, texts in fields.items():
            texts = [x for x in texts if x.strip()]
            if not texts:
                continue
            n = sum(1 for x in texts if rx.search(x))
            if n:
                hit[field] = n / len(texts)
        if hit:
            out[term] = hit
    return out


def relevance(matches: dict[str, dict], idf: dict[str, float]) -> float:
    total = 0.0
    for term, hit in matches.items():
        best = 0.0
        for field, share in hit.items():
            w = FIELD_WEIGHTS[field] * ((0.5 + 0.5 * share) if field == "examples" else 1.0)
            best = max(best, w)
        total += best * idf[term]
    return total


def noise_hits(t: dict, exclude_rx: dict, noise_rx: dict) -> list[dict]:
    text_main = normalize_text((t.get("name") or "") + " \n " + (t.get("what_it_is") or ""))
    hits = []
    for term, rx in exclude_rx.items():
        if rx.search(text_main):
            hits.append({"type": "exclude-term", "match": term, "penalty": PENALTY_EXCLUDE})
    for (group, term), rx in noise_rx.items():
        if rx.search(text_main):
            hits.append({"type": f"noise:{group}", "match": term, "penalty": PENALTY_NOISE})
    name = t.get("name") or ""
    m = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)(?:'s|’s|'|’)(?=\s|$)", name)
    if m:
        hits.append({"type": "proper-name", "match": m.group(0), "penalty": PENALTY_PROPER_NAME})
    afd = t.get("active_for_days")
    if afd is not None and afd <= SPIKE_MAX_DAYS:
        hits.append({"type": "one-off spike", "match": f"active {afd}d", "penalty": PENALTY_SPIKE})
    return hits


def top_examples(t: dict, n: int = 3) -> list[dict]:
    ex = sorted(t.get("examples") or [], key=lambda e: -(e.get("views") or 0))[:n]
    return [{k: e.get(k) for k in ("url", "views", "hook_text", "hook_source", "appears_at_s", "creator", "published")}
            for e in ex]


def sound_licence(t: dict) -> str:
    """'commercial' (usable in paid ads), 'organic' (organic posts only) or 'unknown', from whatever field TrendsMesh uses."""
    for k in LICENCE_KEYS:
        if k not in t or t[k] is None:
            continue
        v = t[k]
        if isinstance(v, bool):
            return "commercial" if v else "organic"
        sv = str(v).strip().lower()
        if any(w in sv for w in ("commercial", "ads", "paid", "business", "licensed for ads")):
            return "commercial"
        if any(w in sv for w in ("organic", "personal", "non-commercial", "noncommercial", "not for ads")):
            return "organic"
    return "unknown"


def base_record(t: dict, found_by: list[str], c: dict, langs, inferred) -> dict:
    reach = t.get("reach") or {}
    return {
        "id": t.get("id"), "short_id": (t.get("id") or "")[:8], "name": t.get("name"),
        "kind": t.get("kind"),
        "label": {"hook_trend": "hook", "format_trend": "format", "topic_trend": "topic", "sound_trend": "sound"}.get(t.get("kind"), t.get("kind")),
        "status": t.get("status"), "momentum": t.get("momentum"), "confidence": t.get("confidence"),
        "creators": c["_creators"], "views": reach.get("views"), "videos": reach.get("videos"),
        "median_view_lift": c["_lift"], "youtube_hook_rate_pct": c["_adoption_pct"],
        "contradicting_checks": c["_contradictions"], "since": (t.get("since") or "")[:10] or None,
        "last_seen": c["_last_seen"], "days_since_last_seen": c["_days_ago"],
        "active_for_days": t.get("active_for_days"), "visible_until": t.get("visible_until"),
        "languages": langs, "languages_inferred": inferred,
        "sensitivity_level": t.get("sensitivity_level"), "what_it_is": t.get("what_it_is"),
        "found_by": found_by, "top_examples": top_examples(t),
    }


def fmt_num(n) -> str:
    if n is None:
        return "n/a"
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{n / 1e3:.0f}k"
    return str(n)


def hook_reason(r: dict) -> str:
    bits = [f"{r['status']}, {r['momentum'] or 'momentum n/a'}",
            f"{r['creators']} creators",
            f"{r['median_view_lift']:.1f}x lift" if r["median_view_lift"] is not None else "lift n/a",
            f"last seen {r['days_since_last_seen']}d ago" if r["days_since_last_seen"] is not None else "last seen n/a"]
    if r["youtube_hook_rate_pct"] is not None:
        bits.append(f"YouTube hook rate {r['youtube_hook_rate_pct']:.0f}%")
    lang = "/".join(r["languages"]) or "lang n/a"
    bits.append(lang + (" (inferred)" if r["languages_inferred"] else ""))
    if r["matched_terms"]:
        bits.append("terms: " + ", ".join(r["matched_terms"]))
    if r["flags"]:
        bits.append("FLAG: " + "; ".join(r["flags"]))
    return "; ".join(bits)


def topic_reason(r: dict) -> str:
    if r["matched_terms"]:
        where = [f"{t} ({'/'.join(f for f in r['term_fields'][t])})" for t in r["matched_terms"]]
        bits = ["matches " + ", ".join(where)]
    else:
        bits = ["weak fit (no term match), shown as best available signal"]
    bits.append(f"{r['status']}, {r['creators']} creators, {fmt_num(r['views'])} views")
    if r["days_since_last_seen"] is not None:
        bits.append(f"last seen {r['days_since_last_seen']}d ago")
    if r["noise"]:
        bits.append("penalised: " + ", ".join(f"{h['match']}" for h in r["noise"]))
    if r["flags"]:
        bits.append("FLAG: " + "; ".join(r["flags"]))
    return "; ".join(bits)


def score_all(trends: dict, found_by: dict, terms: list[str], exclude: list[str], market: str, today: date,
              noise_groups: dict, min_topics: int, sounds_commercial_only: bool = False,
              anchors: list[str] = ()) -> dict:
    """The original's score_all: `hooks`, `topics`, `formats`, `sounds` (ranked records), `dropped`
    (counts) and `pool` (`pool_size`, `term_doc_freq`, `term_idf`).

    The plugin's `anchors` (organic video) drop topics and formats without a niche anchor
    (`anchor_filter`) before the weak fill, so `min_topics` still holds with anchored weak fits; the
    rows dropped are in `anchor_dropped`. Without anchors this is the original's, unchanged."""
    regexes = {t: term_regex(t) for t in terms}
    exclude_rx = {t: term_regex(t) for t in exclude}
    noise_rx = {(g, w): term_regex(w) for g, words in noise_groups.items() for w in words}
    pool_fields = {tid: trend_fields(t) for tid, t in trends.items()}
    n = len(trends)
    df = {term: sum(1 for f in pool_fields.values()
                    if any(rx.search(x) for texts in f.values() for x in texts)) for term, rx in regexes.items()}
    idf = {term: math.log(1 + n / (1 + df[term])) for term in terms}

    hooks, topics, formats, sounds, weak = [], [], [], [], []
    dropped = {"contradicted": 0, "no_term_relevance": 0, "noise_outweighs_relevance": 0, "sound_not_commercial": 0}
    for tid, t in trends.items():
        if t.get("status") == "contradicted":
            dropped["contradicted"] += 1
            continue
        c = signal_components(t, today)
        langs, inferred, lang_mult, foreign = language_info(t, market)
        sens_mult = SENSITIVITY_MULT.get(t.get("sensitivity_level"), 0.55)
        matches = term_matches(pool_fields[tid], regexes)
        rel = relevance(matches, idf)
        flags = []
        if foreign:
            flags.append(f"transferability risk: evidence only in {'/'.join(langs)}, not {market}")
        if sens_mult < 1:
            flags.append(f"sensitivity: {t.get('sensitivity_level')}")
        rec = base_record(t, found_by.get(tid, []), c, langs, inferred)
        rec["matched_terms"] = sorted(matches, key=lambda k: -idf[k])
        rec["term_fields"] = {k: sorted(v) for k, v in matches.items()}
        rec["flags"] = flags
        comps = {k: round(c[k], 3) for k in HOOK_WEIGHTS}
        signals = weighted_signals(c)
        kind = t.get("kind")
        if kind in ("hook_trend", "format_trend", "sound_trend"):
            if kind == "sound_trend":
                lic = sound_licence(t)
                rec["licence"] = lic
                if sounds_commercial_only and lic != "commercial":
                    dropped["sound_not_commercial"] += 1
                    continue
                if lic != "commercial":
                    flags.append("organic only: in ads use a licensed equivalent (CB9)" if lic == "organic" else "licence unknown: treat as organic only (CB9)")
            fit_bonus = HOOK_FIT_BONUS_MAX * (1 - math.exp(-rel / TOPIC_REL_SCALE))
            score = 100 * signals * c["status_mult"] * lang_mult * sens_mult + fit_bonus
            rec["score"] = round(score, 1)
            rec["components"] = {**comps, "signals": round(signals, 3), "status_mult": c["status_mult"], "language_mult": lang_mult,
                                 "sensitivity_mult": sens_mult, "term_relevance": round(rel, 2),
                                 "fit_bonus": round(fit_bonus, 2)}
            rec["reason"] = hook_reason(rec)
            {"hook_trend": hooks, "format_trend": formats, "sound_trend": sounds}[kind].append(rec)
        else:
            noise = noise_hits(t, exclude_rx, noise_rx)
            penalty = sum(h["penalty"] for h in noise)
            net = rel - penalty
            rec["noise"] = noise
            rel_norm = 1 - math.exp(-max(net, 0) / TOPIC_REL_SCALE)
            score = 100 * rel_norm * (TOPIC_REL_SHARE + (1 - TOPIC_REL_SHARE) * signals) * c["status_mult"] * lang_mult * sens_mult
            rec["score"] = round(score, 1)
            rec["components"] = {**comps, "signals": round(signals, 3), "term_relevance": round(rel, 2),
                                 "noise_penalty": penalty, "net_relevance": round(net, 2),
                                 "relevance_norm": round(rel_norm, 3), "status_mult": c["status_mult"], "language_mult": lang_mult,
                                 "sensitivity_mult": sens_mult}
            if rel <= 0:
                dropped["no_term_relevance"] += 1
                if not noise:
                    weak.append(rec)
                continue
            if net <= 0:
                dropped["noise_outweighs_relevance"] += 1
                continue
            rec["reason"] = topic_reason(rec)
            topics.append(rec)

    def tie(r):
        return -r["score"], -(r["creators"] or 0), -(r["views"] or 0)
    hooks.sort(key=tie)
    topics.sort(key=tie)
    formats.sort(key=tie)
    sounds.sort(key=tie)
    anchor_dropped: list[dict] = []
    if anchors:
        topics, anchor_dropped = anchor_filter(topics, trends, anchors)
        formats, dropped_formats = anchor_filter(formats, trends, anchors)
        anchor_dropped += dropped_formats
        weak = anchor_filter(weak, trends, anchors)[0]
    if len(topics) < min_topics:
        weak.sort(key=lambda r: -r["components"]["signals"])
        for r in weak[: min_topics - len(topics)]:
            r["flags"].append("weak fit (no term match)")
            r["reason"] = topic_reason(r)
            topics.append(r)
    out = {"hooks": hooks, "topics": topics, "formats": formats, "sounds": sounds, "dropped": dropped,
           "pool": {"pool_size": n, "term_doc_freq": df, "term_idf": {k: round(v, 3) for k, v in idf.items()}}}
    if anchors:
        out["anchor_dropped"] = anchor_dropped
    return out


# ---------------------------------------------------------------------------- the plugin's filters (PB03)
#
# Organic video (ANALYSIS.md lessons 1 and 2, PLAYBOOK.md B1): a topic or format must carry a niche
# anchor, sounds are ranked by how much their description and evidence name the niche, and a weekly
# run marks rows whose newest evidence is older than its window. None of it runs without its flag, so
# PB04's and PB02's shortlists stay the original's.

ANCHOR_DROP = "no niche anchor next to the activity term"
WEAK_SOUND = "weak fit (no niche relevance)"
ANCHOR_EXEMPT = ("hook_trend", "sound_trend")  # hooks are subject-agnostic (OV2); sounds get a relevance score


def anchor_regex(term: str) -> re.Pattern:
    """A whole-word, case-insensitive match of the term or its plain plural (the last word + s or es:
    "dog" finds "dogs"). A hyphen joins a compound, so "hot-dog" is not "dog" (lesson 2's noise), and
    "petals" is not "pet"."""
    words = r"\s+".join(re.escape(w) for w in term.split())
    return re.compile(rf"(?<![\w-]){words}(?:s|es)?(?![\w-])", re.IGNORECASE)


def _evidence_texts(videos: list) -> list[str]:
    return [v.get(k) for v in videos if isinstance(v, dict) for k in ("hook_text", "excerpt")
            if isinstance(v.get(k), str)]


def anchor_filter(rows: list[dict], cards: dict, anchors: list[str]) -> tuple[list[dict], list[dict]]:
    """(the rows kept, the rows dropped). A topic or format row is kept only when an anchor term is in its
    name, `what_it_is`, or a saved evidence text (`hook_text`, `excerpt` of its card's examples in
    `cards`, by id). Hooks and sounds are exempt. A dropped row is a copy whose `reason` says why."""
    if not anchors:
        return list(rows), []
    regexes = [anchor_regex(a) for a in anchors]
    kept, dropped = [], []
    for row in rows:
        if row.get("kind") in ANCHOR_EXEMPT:
            kept.append(row)
            continue
        card = cards.get(row.get("id")) or {}
        texts = [x for x in (row.get("name"), row.get("what_it_is"), card.get("name"), card.get("what_it_is"))
                 if isinstance(x, str)] + _evidence_texts(card.get("examples") or [])
        if any(rx.search(text) for rx in regexes for text in texts):
            kept.append(row)
        else:
            dropped.append({**row, "reason": ANCHOR_DROP})
    return kept, dropped


def sound_relevance(card: dict, videos: list[dict], terms: list[str]) -> dict:
    """`{"score", "matched"}`: the share of `terms` found (whole words) in the card's `what_it_is` and the
    evidence texts of `videos`, 0 to 1, and the terms found."""
    terms = [t for t in terms if t.strip()]
    texts = ([card["what_it_is"]] if isinstance(card.get("what_it_is"), str) else []) + _evidence_texts(videos)
    matched = [t for t in terms if any(anchor_regex(t).search(x) for x in texts)]
    return {"score": round(len(matched) / len(terms), 3) if terms else 0.0, "matched": matched}


def newest_evidence(card: dict) -> date | None:
    """The newest `published` day of a trend's evidence (its examples and saved video pages)."""
    days = [parse_dt(e.get("published")) for e in card.get("examples") or [] if isinstance(e, dict)]
    days = [d for d in days if d]
    return max(days) if days else None


def apply_filters(scored: dict, pool: dict, terms: list[str], *, anchors: list[str], sound_fit: bool,
                  recent_days: int | None, today: date) -> None:
    """Apply the sound relevance and the recency mark to `score_all`'s lists in place (before the cut;
    the anchors are applied in `score_all`). Each row's additions go in its `plugin` block."""
    if sound_fit:
        for r in scored["sounds"]:
            card = pool.get(r["id"]) or {}
            rel = sound_relevance(card, card.get("examples") or [], anchors or terms)
            r.setdefault("plugin", {})["relevance"] = rel
            if rel["score"] == 0:
                r["flags"].append(WEAK_SOUND)
                r["reason"] = hook_reason(r)
        scored["sounds"].sort(key=lambda r: (-r["plugin"]["relevance"]["score"], -r["score"], -(r["creators"] or 0),
                                             -(r["views"] or 0)))
    if recent_days is not None:
        for key in ("hooks", "topics", "formats", "sounds"):
            for r in scored[key]:
                newest = newest_evidence(pool.get(r["id"]) or {})
                r.setdefault("plugin", {}).update(
                    stale=newest is None or (today - newest).days > recent_days,
                    newest_evidence=newest.isoformat() if newest else None)


def filters_md(payload: dict, dropped: list[dict], *, anchors: list[str], sound_terms: list[str] | None,
               recent_days: int | None) -> str:
    """The Markdown the plugin's filters add below the original page: one line per filter given."""
    lines = ["## Plugin filters", ""]
    if anchors:
        lines.append(f"Niche anchors: {', '.join(anchors)}. Dropped ({ANCHOR_DROP}): " + ("; ".join(
            f"`{r['short_id']}` {md_escape(r['name'])} ({r['label']})" for r in dropped) or "none") + ".")
    if sound_terms is not None:
        lines.append(f"Sounds ranked by their niche relevance to: {', '.join(sound_terms)}.")
    stale = [r for key in ("hooks", "topics", "formats", "sounds") for r in payload[key]
             if (r.get("plugin") or {}).get("stale")]
    if recent_days is not None:
        lines.append(f"No evidence in the last {recent_days} days: " + ("; ".join(
            f"`{r['short_id']}` {md_escape(r['name'])}" for r in stale) or "none") + ".")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------- output (verbatim)

def md_escape(s) -> str:
    return str(s if s is not None else "").replace("|", "\\|").replace("\n", " ")


def render_md(hooks, topics, meta, hooks_rest=(), formats=(), sounds=()) -> str:
    lines = [f"# Trend shortlist ({meta['today']})", "",
             f"Generated by `tm trends shortlist`. Market language: `{meta['market_language']}`. "
             f"Terms: {', '.join(meta['terms'])}.",
             f"Pool: {meta['pool_size']} unique trends from {len(meta['inputs'])} files "
             f"({meta['hooks_scored']} hooks scored, {meta['topics_kept']} topics kept; dropped: "
             + ", ".join(f"{k} {v}" for k, v in meta["dropped"].items()) + ").", "",
             "## Best-fitting hooks", "",
             "Hooks (`hook_trend`) are opening structures usable for any subject; ranked by usability "
             "(status, momentum, creators, view lift, recency, language, sensitivity) with a small term-fit bonus.", "",
             "| # | Hook | Score | Status | Creators | Views | Lift | Last seen | Lang | Example | Reason |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(hooks, 1):
        ex = r["top_examples"][0] if r["top_examples"] else {}
        exs = f"[{md_escape((ex.get('hook_text') or '')[:60])}]({ex.get('url')})" if ex.get("url") else ""
        lift = f"{r['median_view_lift']:.1f}x" if r["median_view_lift"] is not None else "n/a"
        lines.append(f"| {i} | `{r['short_id']}` {md_escape(r['name'])} | {r['score']} | {r['status']}, "
                     f"{r['momentum'] or 'n/a'} | {r['creators']} | {fmt_num(r['views'])} | {lift} | "
                     f"{r['last_seen'] or 'n/a'} | {'/'.join(r['languages']) or 'n/a'} | {exs} | {md_escape(r['reason'])} |")
    flagged = [(i, r) for i, r in enumerate(hooks_rest, len(hooks) + 1) if r["flags"]]
    if flagged:
        lines += ["", "Flagged hooks below the cut (a hypothesis for this market, not evidence): " + "; ".join(
            f"#{i} `{r['short_id']}` {md_escape(r['name'])} ({r['score']}, {'; '.join(r['flags'])})" for i, r in flagged) + "."]
    lines += ["", "## Best-fitting topics", "",
              "Topics and formats ranked by relevance to the terms (name, description, evidence texts; "
              "rare terms weigh more), minus noise penalties, plus the same signals.", "",
              "| # | Trend | Type | Score | Status | Creators | Views | Last seen | Example | Reason |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(topics, 1):
        ex = r["top_examples"][0] if r["top_examples"] else {}
        exs = f"[{md_escape((ex.get('hook_text') or ex.get('creator') or 'clip')[:60])}]({ex.get('url')})" if ex.get("url") else ""
        lines.append(f"| {i} | `{r['short_id']}` {md_escape(r['name'])} | {r['label']} | {r['score']} | "
                     f"{r['status']} | {r['creators']} | {fmt_num(r['views'])} | {r['last_seen'] or 'n/a'} | "
                     f"{exs} | {md_escape(r['reason'])} |")

    def struct_table(title, intro, rows, licence=False):
        out = ["", f"## {title}", "", intro, ""]
        if not rows:
            out.append("None in the pool yet (the trend source returned no trends of this type for these queries).")
            return out
        out += ["| # | Trend | Score | Status | Creators | Views | Lift | Last seen |" + (" Licence |" if licence else "") + " Example | Reason |",
                "|---|---|---|---|---|---|---|---|" + ("---|" if licence else "") + "---|---|"]
        for i, r in enumerate(rows, 1):
            ex = r["top_examples"][0] if r["top_examples"] else {}
            exs = f"[{md_escape((ex.get('hook_text') or ex.get('creator') or 'clip')[:60])}]({ex.get('url')})" if ex.get("url") else ""
            lift = f"{r['median_view_lift']:.1f}x" if r["median_view_lift"] is not None else "n/a"
            out.append(f"| {i} | `{r['short_id']}` {md_escape(r['name'])} | {r['score']} | {r['status']}, {r['momentum'] or 'n/a'} | "
                       f"{r['creators']} | {fmt_num(r['views'])} | {lift} | {r['last_seen'] or 'n/a'} |"
                       + (f" {r.get('licence', 'unknown')} |" if licence else "") + f" {exs} | {md_escape(r['reason'])} |")
        return out
    lines += struct_table("Best-fitting formats", "Formats (`format_trend`): how a video is told (e.g. a story over clips, before and after); scored like hooks. "
                          "A format is used only if the ad can be made honestly (no invented posts or testimonials).", formats)
    lines += struct_table("Best-fitting sounds", "Sounds (`sound_trend`): scored like hooks, with the licence from the trend data. Only `commercial` "
                          "sounds may go into ads; `organic` or `unknown` ones get a licensed equivalent in the ad brief (CB9).", sounds, licence=True)
    lines += ["", "Scores are 0-100; every component is in the JSON output. Flags: a hook with evidence only in "
              "another language is a hypothesis for this market (CB2 transferability).", ""]
    return "\n".join(lines)


def build(scored: dict, meta: dict, top: int) -> tuple[dict, str]:
    """The JSON payload and the Markdown page, cut to `top` per list (the original's main)."""
    hooks, topics, formats, sounds = scored["hooks"], scored["topics"], scored["formats"], scored["sounds"]
    hooks_top, topics_top, formats_top, sounds_top = hooks[:top], topics[:top], formats[:top], sounds[:top]
    for rows in (formats_top, sounds_top, hooks_top, topics_top):
        for i, r in enumerate(rows, 1):
            r["rank"] = i

    def rest(rows, start):
        return [{"rank": i, "id": r["id"], "name": r["name"], "score": r["score"], "flags": r["flags"],
                 "languages": r["languages"]} for i, r in enumerate(rows, start)]
    payload = {"meta": meta, "hooks": hooks_top, "topics": topics_top, "formats": formats_top, "sounds": sounds_top,
               "hooks_beyond_top": rest(hooks[top:], top + 1),
               "topics_beyond_top": rest(topics[top:], top + 1)}
    return payload, render_md(hooks_top, topics_top, meta, hooks[top:], formats_top, sounds_top)


def write(run: RunFolder, inputs: list[Path], terms: list[str], *, exclude: list[str] = (), market: str = "en",
              today: date | None = None, top: int = 10, min_topics: int = 3,
              sounds_commercial_only: bool = False, anchors: list[str] = (), sound_fit: bool = False,
              recent_days: int | None = None) -> dict:
    """Score `inputs` and write 03_wip/trend_shortlist_vNN.json and .md (the same NN, never over an
    earlier one). Returns the counts, the two files (run-relative) and the files skipped.

    The plugin's filters (`score_all`'s anchors, `apply_filters`): `anchors` (niche anchor terms), `sound_fit` (sounds ranked
    by relevance to the anchors, else the terms) and `recent_days`. With none of them, the output is
    the original's."""
    today = today or date.today()
    market = market.lower()
    anchors = list(anchors)
    filtered = bool(anchors or sound_fit or recent_days is not None)
    skipped: list[Path] = []
    pool, found_by = load_pool(inputs, skipped)
    scored = score_all(pool, found_by, terms, list(exclude), market, today, trends.DEFAULT_NOISE, min_topics,
                       sounds_commercial_only, anchors)
    dropped = scored.get("anchor_dropped", [])
    if filtered:
        apply_filters(scored, pool, terms, anchors=anchors, sound_fit=sound_fit, recent_days=recent_days, today=today)
    meta = {"today": today.isoformat(), "market_language": market, "terms": terms,
            "exclude_terms": list(exclude), "inputs": [_shown(run, f) for f in dict.fromkeys(inputs)],
            "pool_size": scored["pool"]["pool_size"], "term_doc_freq": scored["pool"]["term_doc_freq"],
            "term_idf": scored["pool"]["term_idf"],
            "hooks_scored": len(scored["hooks"]), "topics_kept": len(scored["topics"]),
            "formats_scored": len(scored["formats"]), "sounds_scored": len(scored["sounds"]),
            "sounds_commercial_only": sounds_commercial_only, "dropped": scored["dropped"],
            "weights": {"hook_signals": HOOK_WEIGHTS, "field_weights": FIELD_WEIGHTS,
                        "topic_relevance_share": TOPIC_REL_SHARE,
                        "penalties": {"exclude": PENALTY_EXCLUDE, "noise": PENALTY_NOISE,
                                      "proper_name": PENALTY_PROPER_NAME, "spike": PENALTY_SPIKE}}}
    if filtered:
        meta["plugin"] = {"anchor_terms": anchors, "sound_relevance": sound_fit, "recent_days": recent_days}
    payload, md = build(scored, meta, top)
    if anchors:
        payload["anchor_dropped"] = [{"id": r["id"], "name": r["name"], "label": r["label"], "reason": r["reason"]}
                                     for r in dropped]
    if filtered:
        md += "\n" + filters_md(payload, dropped, anchors=anchors, sound_terms=(anchors or terms) if sound_fit else None,
                                recent_days=recent_days)
    target = max(run.next_version("03_wip", STEM, "json"), run.next_version("03_wip", STEM, "md").with_suffix(".json"),
                 key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
    page = target.with_suffix(".md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    page.write_text(md, encoding="utf-8")
    params = {"terms": terms, "exclude_terms": list(exclude), "market_language": market, "today": meta["today"],
              "top": top, "min_topics": min_topics, "inputs": len(meta["inputs"]), **meta.get("plugin", {})}
    for f in (target, page):
        manifest.record(run, f"03_wip/{f.name}", "03_wip", "tm trends shortlist", params=params)
    return {"json": f"03_wip/{target.name}", "md": f"03_wip/{page.name}", "pool_size": meta["pool_size"],
            "hooks": len(scored["hooks"]), "topics": len(scored["topics"]), "formats": len(scored["formats"]),
            "sounds": len(scored["sounds"]), "dropped": scored["dropped"],
            "skipped": [_shown(run, f) for f in skipped],
            **({"anchor_dropped": len(dropped)} if anchors else {})}


def _shown(run: RunFolder, path: Path) -> str:
    """A path as the output shows it: run-relative when inside the run."""
    try:
        return Path(path).resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        return str(path)


def input_files(run: RunFolder, patterns: list[str] | None) -> list[Path]:
    """The files `--inputs` names (each glob sorted, as the reference tool did), else the run's saved
    answers in DEFAULT_INPUTS order."""
    if not patterns:
        research = run.path / trends.RESEARCH
        return [f for pat in DEFAULT_INPUTS for f in sorted(research.glob(pat)) if f.is_file()]
    files: list[Path] = []
    for pat in patterns:
        matched = sorted(glob.glob(pat)) or ([pat] if Path(pat).exists() else [])
        files += [Path(p) for p in matched]
    return files


# ---------------------------------------------------------------------------- command line

def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("shortlist", help="rank the saved trends into hooks, topics, formats and sounds")
    p.add_argument("--run", required=True, help="the run folder")
    p.add_argument("--terms", required=True, nargs="+",
                   help="category, persona and angle terms (comma-separated or one per argument)")
    p.add_argument("--inputs", nargs="+", help="trend answer files or globs (default: the run's saved answers)")
    p.add_argument("--market-language", default="en", help="ISO code of the market language (default en)")
    p.add_argument("--exclude-terms", nargs="+", default=[], help="noise words (a topic penalty)")
    p.add_argument("--top", type=int, default=10, help="entries per list (default 10)")
    p.add_argument("--min-topics", type=int, default=3, help="fill the topic list up to this many with weak fits")
    p.add_argument("--today", help="reference date YYYY-MM-DD for recency (default: today)")
    p.add_argument("--sounds-commercial-only", action="store_true", help="keep only sounds marked commercial")
    p.add_argument("--anchor-terms", nargs="+", default=[],
                   help="niche anchor terms: a topic or format without one is dropped (organic video)")
    p.add_argument("--sound-relevance", action="store_true",
                   help="rank sounds by their niche relevance (the anchor terms, else the terms)")
    p.add_argument("--recent-days", type=int,
                   help="mark rows whose newest saved evidence is older than this many days")
    p.add_argument("--json", action="store_true")


def _terms(values: list[str]) -> list[str]:
    return [t for v in values for t in split_terms(v)]


def run_shortlist(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        terms = _terms(args.terms)
        if not terms:
            raise ValueError("--terms is empty: give the category, persona and angle words to rank trends by, "
                             "for example --terms \"lucid dream,sleep,journal\".")
        if args.top < 1 or args.min_topics < 0:
            raise ValueError("--top must be at least 1 and --min-topics at least 0.")
        if args.recent_days is not None and args.recent_days < 1:
            raise ValueError("--recent-days must be at least 1 (the weekly run's window is 7).")
        today = date.fromisoformat(args.today) if args.today else None
        inputs = input_files(run, args.inputs)
        if not inputs:
            where = ", ".join(args.inputs) if args.inputs else f"{run.path.name}/{trends.RESEARCH}"
            raise ValueError(f"No saved TrendsMesh answers matched ({where}), so there is nothing to rank. Search "
                             "TrendsMesh with collection on (or give --inputs), then run the shortlist again; the "
                             "run continues from the same place.")
        out = write(run, inputs, terms, exclude=_terms(args.exclude_terms), market=args.market_language,
                        today=today, top=args.top, min_topics=args.min_topics,
                        sounds_commercial_only=args.sounds_commercial_only, anchors=_terms(args.anchor_terms),
                        sound_fit=args.sound_relevance, recent_days=args.recent_days)
    except (OSError, ValueError, ReadOnlyError) as exc:
        return cli.fail(args, str(exc))
    skipped = f" Skipped (not readable JSON): {', '.join(out['skipped'])}." if out["skipped"] else ""
    cli.emit(args, {"status": "done", **out},
             f"Wrote {out['json']} and {out['md']}: {out['pool_size']} trends, {out['hooks']} hooks, "
             f"{out['topics']} topics, {out['formats']} formats, {out['sounds']} sounds.{skipped}")
    return 0
