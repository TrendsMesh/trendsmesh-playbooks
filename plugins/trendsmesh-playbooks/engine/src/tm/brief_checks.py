"""`04_final/brief_pack_vNN.json` (brief.json) of a creative brief run against CB1-CB13, and the
pick of the top concepts by score that stay distinct (`tm brief pick` was Hands-off's G2 before issue #145: Hands-off
keeps every concept now).

    check(run, brief, stage, cfg)   the problems at a stage: concepts (C1), brief (D), production (E1)
    pick(brief, totals, count, min_axes)   the top concepts by score that stay distinct (CB6)
    rule_pick(run, brief)           that pick on the run's latest scores and config, and why it is short
    concepts_gap / brief_gap / production_gap   the step checks `concepts_checked` ...
    landing_quotes(run, brief)      R3 for the landing page: a quote given as its is on the saved page
                                    text (`tm page fetch`), never from a WebFetch summary (stage brief)
    media_rows(concept)             its media-buyer rows by label, as the production check reads them
    account_figures(run), advertisers_seen(run, brief)   CB13's data: what the creator view never shows

Every stage refuses a trend id, a run file or a theme id in a field the page shows (issue #132, `plain_words`): the
page says its sources in words (`source`), and the MCP call, the run file or the trend id go in `source_ref`, which
the page folds into "Technical details".

CB13's check of the creator view (issue #146) reads data, never words: the creator view is built from the creator
fields only (brief_page), and the check refuses a view, or its PDF, that shows one of the run's own account figures
(spend, cost per result, results, from the saved Meta reads) or an advertiser of the run's Ad Library answers, with
the field and the value. Hooks and ad copy are shown as written, in every language alike.

The stages are cumulative: `brief` runs the concepts checks too, and `production` runs both, so the
brief Task 13 rewrites with the animatic paths is checked in full at E1. `tm brief check` marks the
file it passed on as `brief_<stage>` (`stepchecks.mark`); each step check asks that the latest
brief_pack is that file, unchanged. The mark covers the brief alone: a newer saturation file, voice
bank or audience pick after a pass leaves the earlier stages' marks standing, and the cumulative
production check at E1 reads them all again.

The shape is the handoff's schema (`schemas/pb2_brief.schema.json`, checked with `json_schema`),
with the plugin blocks of the plan's Decision 3 (their schemas below) and, at stage `concepts`, only
the concept fields the review pack's page shows (key message, hypothesis and beats among them). A
brief not in its shape gets its shape problems alone.

The texts of the rules are matched the way the voice check matches a quote: case, runs of spaces,
curly quotes and the ellipsis aside (`voice_themes._norm`), on whole words. The words the spec
forbids ("unused", "no category trend", "rising" in a guess run) are looked for in the agent's own
prose only: never in what it copied (the product, links, quotes, customer phrases, queries, trend
names), which it may not change.
"""

from __future__ import annotations

import copy
import functools
import itertools
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from tm import animatic, brief_research, brand, i18n, json_schema, page_text, plain_words, research_checks, state
from tm import stepchecks
from tm import trends, voice
from tm import voice_themes
from tm.brief_config import SEED_KINDS
from tm.config import Problem
from tm.evidence import GUESS, TRENDSMESH
from tm.mcp_saves import META
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

Stage = Literal["concepts", "brief", "production", "organic_concepts", "organic_views"]
AD_STAGES = ("concepts", "brief", "production")
# the organic video brief's (issue #136): its concepts (O5), then its creator, editor and publisher views and the
# posting plan (O7, cumulative). No customer phrases (CB5), Ad Library (CB4) or media-buyer rows: nothing is spent.
ORGANIC_STAGES = ("organic_concepts", "organic_views")
STAGES = (*AD_STAGES, *ORGANIC_STAGES)
FINAL, STEM = "04_final", "brief_pack"
NAME = re.compile(rf"^{FINAL}/{STEM}_v\d+\.json$")
SCHEMA = Path(__file__).parent / "schemas" / "pb2_brief.schema.json"
AXES = ("angle", "hook_type", "format", "persona", "awareness")   # CB6
# The awareness stage (PLAYBOOK CB6) is Schwartz's scale, whose names the LD review pack uses
# ("problem-aware", "unaware"): a fixed set, so it cannot differ by spelling.
AWARENESS = ("unaware", "problem_aware", "solution_aware", "product_aware", "most_aware")
MIN_PHRASE_WORDS = 3     # CB5: a customer phrase is a whole bank phrase, or this many of its words in a row
RELATIONS = ("consistent", "setup_payoff", "contradiction")       # CB7
LICENCES = ("commercial", "organic", "unknown")                   # CB9, as the shortlist reads them
GUESS_LABEL = "Hook (agent's guess)"
GLANCE_KEYS = ("trend", "guess", "customers", "account", "competition")   # a glance row's name in any language
# an organic video brief's rows beside the trend's (issue #136): the channel (O2) and the persona (O3); the schema's
# glance `key` enum takes them too (`_schema`)
ORGANIC_GLANCE_KEYS = ("channel", "persona")
COMPETITOR_FOUND = "competitor found"
# The review pack's: what its page shows of a concept, with the plugin block.
CONCEPT_FIELDS = ["id", "brief_id", "title", "one_liner", "key_message", "hypothesis", "glance", "hook", "beats", "plugin"]
NEAR_DUPLICATE = 0.6                       # word-set Jaccard of a concept's text and a running ad's
AD_TEXTS = ("body", "title", "primary_text", "headline", "message")   # a creative's copy, by key
AD_TEXT_LISTS = ("bodies", "titles")       # asset_feed_spec: [{"text": ...}]
AD_TEXT_UNDER = {"link_data": "name"}      # object_story_spec.link_data.name: the headline
# What the agent copied, so the forbidden-word scan never reads it (it may not change it).
COPIED_KEYS = ("url", "landing_url", "thumb", "quote", "phrase", "adapted_from", "query", "name", "trend_id",
               "candidate")
MEDIA_ROWS = ("Decision metric", "Baseline", "Target", "Minimum before a decision", "Setup", "Placements",
              "Audience")
EDITOR_ROWS = ("Length", "Captions", "Formats", "Versions", "Files")
# the areas of the string table the brief's page is built from (its own, and the shared run page's: issue #60)
PAGE_AREAS = ("brief", "run_page")
# CB13's data check (issue #146): the creator view never shows the run's own account figures. The fields of the
# saved Meta reads (01_base/meta/) that hold them, and what each is called in the problem.
FIGURE_KEYS = {"spend": "spend", "amount_spent": "spend", "cost_per_result": "cost per result", "cpa": "cost per result",
               "cost_per_action": "cost per result", "cost_per_purchase": "cost per result", "results": "results",
               "purchases": "results", "conversions": "results"}
FIGURE_DIGITS = 3            # a figure is looked for once it has this many digits: "7" or "12" alone says nothing
INTAKE_FIELDS = (("decision_facts", "budget", "budget"), ("decision_facts", "deadline", "deadline"),
                 ("decision_facts", "approver", "approver"), ("creator", "deadline", "deadline"))
BANNED = {
    "no category trend": ("the best-fitting trends", "show the closest hooks and topics, never this line (CB2)"),
    "unused": (research_checks.NONE_FOUND, "an Ad Library search reads titles, so it tells what it found, never "
                                           "that no one uses an idea (CB4)"),
}
RISING = {"rising": (GUESS_LABEL, "a guess run has no trend data, so nothing in it is called rising (CB2)")}
_SHAPE_TODO = ("Write brief.json in the shape of the reference playbook's brief.schema.json with its plugin blocks, then check "
               "it again.")

_TEXT = {"type": "string"}
META_PLUGIN: dict = {
    "type": "object", "required": ["evidence", "account_currency"],
    "properties": {"evidence": {"enum": [TRENDSMESH, GUESS]}, "account_currency": {"type": "string",
                                                                                  "pattern": "^[A-Z]{3}$"}},
}
CONCEPT_PLUGIN: dict = {
    "type": "object",
    "required": ["candidate", "trend", "axes", "saturation", "hook_image", "sound", "directional"],
    "properties": {
        "candidate": _TEXT,
        "trend": {"type": ["object", "null"], "required": ["trend_id", "kind", "name"],
                  "properties": {"trend_id": _TEXT, "kind": {"enum": list(SEED_KINDS)}, "name": _TEXT}},
        "axes": {"type": "object", "required": list(AXES),
                 "properties": {**{a: _TEXT for a in AXES}, "awareness": {"enum": list(AWARENESS)}}},
        "saturation": {"type": "object", "required": ["verdict", "query"],
                       "properties": {"verdict": {"enum": list(brief_research.VERDICTS)}, "query": _TEXT}},
        "hook_image": {"type": "object", "required": ["relation"],
                       "properties": {"relation": {"enum": list(RELATIONS)}, "why": {"type": ["string", "null"]}}},
        "sound": {"type": ["object", "null"], "required": ["licence", "organic_only", "licensed_equivalent"],
                  "properties": {"licence": {"enum": list(LICENCES)}, "organic_only": {"type": "boolean"},
                                 "licensed_equivalent": {"type": ["string", "null"]}}},
        "thumbnail": _TEXT,
        "directional": {"type": "boolean"},
    },
}
CLIP_PLUGIN: dict = {"type": "object", "required": ["as_of"],
                     "properties": {"as_of": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}}}


@functools.lru_cache(maxsize=None)
def _schema(stage: str) -> dict:
    """The handoff's schema with the plugin blocks, its concept fields the stage's."""
    schema = copy.deepcopy(json_schema.load(SCHEMA))
    meta = schema["properties"]["meta"]
    meta["properties"]["plugin"] = META_PLUGIN
    meta["required"] = [*meta["required"], "plugin"]
    concept = schema["$defs"]["concept"]
    props = concept["properties"]
    props["plugin"] = CONCEPT_PLUGIN
    props["copy_from_hook"]["properties"]["evidence"]["items"]["properties"]["plugin"] = CLIP_PLUGIN
    props["customer_phrases"]["items"]["properties"]["adapted_from"] = _TEXT
    props["customer_phrases"]["items"]["properties"]["translated"] = {"type": "boolean"}   # CB5, issue #3
    props["glance"]["items"]["properties"]["key"]["enum"] = [*GLANCE_KEYS, *ORGANIC_GLANCE_KEYS]
    if stage in ORGANIC_STAGES:
        return _organic_schema(schema, stage)
    meta["properties"]["kind"] = {"enum": ["ad"]}           # an organic brief is checked at its own stages
    concept["required"] = list(CONCEPT_FIELDS) if stage == "concepts" else [*concept["required"], "plugin"]
    return schema


def _organic_schema(schema: dict, stage: str) -> dict:
    """The organic video brief's shape (issue #136): `meta.kind` organic and its `meta.channel`, no landing page
    needed, no media-buyer view; each concept with its `organic` block, no saturation check (no Ad Library); the
    posting plan at `organic_views`."""
    meta = schema["properties"]["meta"]
    meta["required"] = [*meta["required"], "kind", "channel"]
    meta["properties"]["kind"] = {"enum": ["organic"]}
    meta["properties"]["product"]["required"] = ["name"]
    meta["properties"]["recipients"]["items"]["enum"] = ["decision", "strategy", "creator", "editor", "publisher"]
    meta["properties"]["plugin"] = {**META_PLUGIN, "required": ["evidence"]}
    concept = schema["$defs"]["concept"]
    plugin = copy.deepcopy(CONCEPT_PLUGIN)
    plugin["required"] = [k for k in plugin["required"] if k != "saturation"]
    plugin["properties"]["saturation"] = {"type": "null"}
    concept["properties"]["plugin"] = plugin
    concept["required"] = [*CONCEPT_FIELDS, "organic"]
    if stage == "organic_views":
        schema["required"] = [*schema["required"], "plan"]
    return schema


def shape(brief: object, stage: str) -> list[Problem]:
    """What breaks the stage's schema, as problems; empty when the brief is in its shape."""
    if stage not in STAGES:
        raise ValueError(f"The stage is one of {', '.join(STAGES)}, not {stage!r}.")
    return [Problem(line.split(" ", 1)[0].removeprefix("brief."), line, _SHAPE_TODO)
            for line in json_schema.problems(brief, _schema(stage), name="brief")]


# --- what the run holds ------------------------------------------------------------------------

def _filled(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _norm(text: object) -> str:
    return voice_themes._norm(text if isinstance(text, str) else "")


def media_rows(concept: dict) -> dict[str, object]:
    """The concept's media-buyer rows by their `MEDIA_ROWS` label (matched as the production check
    matches them, case and spaces aside): {label: text}, the first row of a label kept."""
    out: dict[str, object] = {}
    wanted = {_norm(label): label for label in MEDIA_ROWS}
    for row in concept.get("media") or []:
        label = wanted.get(_norm(row.get("label"))) if isinstance(row, dict) else None
        if label is not None and label not in out:
            out[label] = row.get("text")
    return out


def _says(text: object, phrase: str) -> bool:
    """The phrase is in the text as whole words (case and curly quotes aside)."""
    return voice_themes._found(phrase, [text if isinstance(text, str) else ""])


def _rel(run: RunFolder, path: Path) -> str:
    return path.relative_to(run.path).as_posix()


def _saturation(run: RunFolder) -> tuple[list[dict] | None, str, Problem | None]:
    """The checks of the latest saturation file, its name, or the problem that there are none."""
    path = run.latest(trends.RESEARCH, brief_research.SATURATION, "json")
    where = f"{trends.RESEARCH}/{brief_research.SATURATION}_vNN.json"
    if path is None:
        return None, where, Problem("saturation", f"This run has no saturation checks ({where}), so the concepts' "
                                                  "verdicts cannot be compared (CB4).",
                                    "Check every candidate in the Ad Library and run tm brief saturation first.")
    try:
        checks = trends.read(path).get("checks")
    except (OSError, ValueError, AttributeError):
        checks = None
    if not isinstance(checks, list):
        return None, _rel(run, path), Problem("saturation", f"{_rel(run, path)} holds no saturation checks.",
                                              "Write it again and run tm brief saturation, then check the brief.")
    return [c for c in checks if isinstance(c, dict)], _rel(run, path), None


def _bank(run: RunFolder) -> tuple[list[str] | None, str, Problem | None]:
    """The phrases of the latest voice themes' language bank, its file, or the problem."""
    path = run.latest(voice.STAGE, voice_themes.STEM, "json")
    where = f"{voice.STAGE}/{voice_themes.STEM}_vNN.json"
    if path is None:
        return None, where, Problem("customer_phrases", f"This run has no language bank yet ({where}), so the "
                                                        "concepts' customer phrases cannot be checked (CB5).",
                                    "Code the voice themes and run tm voice check first.")
    try:
        rows = trends.read(path).get("language_bank")
    except (OSError, ValueError, AttributeError):
        rows = None
    if not isinstance(rows, list):
        return None, _rel(run, path), Problem("customer_phrases", f"{_rel(run, path)} holds no language bank.",
                                              "Write it again and run tm voice check, then check the brief.")
    return [r["phrase"] for r in rows if isinstance(r, dict) and _filled(r.get("phrase"))], _rel(run, path), None


def running_ads(run: RunFolder) -> tuple[list[tuple[str, str]], int]:
    """(file, text) of every running ad's copy in the saved `ads_get_creatives` reads, wherever it
    sits (the Meta MCP may send a list as a JSON text), and how many reads gave them. A read that is
    an error (a non-empty `error`) or not JSON holds no ads. The Meta field names are not verified
    (as P-F2), so `tm brief check` says how many texts it compared: 0 from a read stands out."""
    out: list[tuple[str, str]] = []

    def walk(node: object, rel: str) -> None:
        if isinstance(node, str) and node.lstrip().startswith(("[", "{")):
            try:
                node = json.loads(node)
            except ValueError:
                return
        if isinstance(node, dict):
            for k, v in node.items():
                if k in AD_TEXTS and _filled(v):
                    out.append((rel, v))
                elif k in AD_TEXT_LISTS and isinstance(v, list):
                    out.extend((rel, x["text"]) for x in v if isinstance(x, dict) and _filled(x.get("text")))
                else:
                    if k in AD_TEXT_UNDER and isinstance(v, dict) and _filled(v.get(AD_TEXT_UNDER[k])):
                        out.append((rel, v[AD_TEXT_UNDER[k]]))
                    walk(v, rel)
        elif isinstance(node, list):
            for v in node:
                walk(v, rel)

    reads = 0
    for f in sorted((run.path / META).glob("ads_get_creatives_*.json")):
        try:
            answer = trends.answer_of(f)
        except (OSError, ValueError):
            continue
        if isinstance(answer, dict) and answer.get("error"):
            continue
        reads += 1
        walk(answer, _rel(run, f))
    return out, reads


def _words(text: str) -> set[str]:
    return set(re.findall(r"\w+(?:'\w+)*", _norm(text)))


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def _card(run: RunFolder, trend_id: str) -> tuple[dict | None, str]:
    """(the latest saved card of the trend, its file), or (None, why there is none)."""
    path = brief_research.card_file(run, trend_id)
    if path is None:
        return None, f"no saved trend card in {trends.RESEARCH}/ (get_trend of {trend_id})"
    card, wrong = brief_research.card_of(path)
    return (card, f"{trends.RESEARCH}/{path.name}") if card is not None else (None, wrong)


def _row(concept: dict, label: str) -> tuple[int | None, dict | None]:
    """The glance row with this English label and its index, else (None, None). A row's `key` (GLANCE_KEYS) names
    it in any language: a brief in another language labels its rows in that language (issue #3)."""
    return next(((k, r) for k, r in enumerate(concept["glance"])
                 if r.get("key") == label.lower() or _norm(r["label"]) == _norm(label)), (None, None))


def _list(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# --- every stage ---------------------------------------------------------------------------------

def _meta(run: RunFolder, brief: dict, evidence: str | None, cfg: dict) -> list[Problem]:
    out = []
    plugin = brief["meta"]["plugin"]
    if evidence is None:
        out.append(Problem("evidence", "This run has not recorded its evidence, so the trend rows cannot be checked.",
                           "Record it (tm evidence trendsmesh|guess --run R --why <reason>), then check again."))
    elif plugin["evidence"] != evidence:
        out.append(Problem("meta.plugin.evidence", f"meta.plugin.evidence is {plugin['evidence']}, but this run's "
                                                   f"evidence is {evidence}.", f"Set it to {evidence}."))
    account = brief_research._setting(cfg, "account.currency")
    if account is not None and plugin.get("account_currency") != account:
        out.append(Problem("meta.plugin.account_currency", f"meta.plugin.account_currency is "
                                                           f"{plugin.get('account_currency')}, but the ad account spends "
                                                           f"in {account} (account.currency).", f"Set it to {account}."))
    return out


def _ids(concepts: list[dict]) -> list[Problem]:
    out = []
    for key in ("id", "brief_id"):
        seen: dict[str, list[str]] = {}
        for c in concepts:
            seen.setdefault(c[key], []).append(c["id"])
        out += [Problem(f"concepts.{key}", f"{key} {value} is used by {_list(ids)}.",
                        f"Give each concept its own {key}.") for value, ids in seen.items() if len(ids) > 1]
    return out


def _axis(value: str) -> str:
    """An axis as it is compared: case, punctuation and runs of spaces aside."""
    return " ".join(re.sub(r"[\W_]+", " ", value.casefold()).split())


def apart(a: dict, b: dict) -> list[str]:
    """The axes on which two concepts differ (CB6)."""
    return [x for x in AXES if _axis(a["plugin"]["axes"][x]) != _axis(b["plugin"]["axes"][x])]


def _axes(concepts: list[dict], least: int) -> list[Problem]:
    """CB6: every pair of concepts differs on at least `least` of the five axes."""
    out = []
    for (_, a), (j, b) in itertools.combinations(enumerate(concepts), 2):
        differ = apart(a, b)
        if len(differ) < least:
            n = len(differ)
            same = [f"plugin.axes.{x}" for x in AXES if x not in differ]
            out.append(Problem(f"concepts[{j}].plugin.axes",
                               f"{a['id']} and {b['id']} differ on {n} axis{'' if n == 1 else 'es'} "
                               f"({', '.join(differ) or 'none'}), fewer than concepts.min_axes_diff {least} (CB6).",
                               f"Change {b['id']} on one of {', '.join(same)}, or drop it."))
    return out


def _near_duplicates(concepts: list[dict], ads: list[tuple[str, str]]) -> list[Problem]:
    """A concept's hook or primary text that repeats a running ad's copy (word sets, Jaccard >= 0.6)."""
    out = []
    for i, c in enumerate(concepts):
        for what, field, text in (("hook", "hook.text", c["hook"]["text"]),
                                  ("primary text", "ad_copy.primary", (c.get("ad_copy") or {}).get("primary"))):
            words = _words(text) if _filled(text) else set()
            overlaps = ((rel, ad, _jaccard(words, _words(ad))) for rel, ad in ads) if words else ()
            hit = next((o for o in overlaps if o[2] >= NEAR_DUPLICATE), None)
            if hit:
                rel, ad, j = hit
                out.append(Problem(f"concepts[{i}].{field}", f"{c['id']}'s {what} is a near-duplicate of a running ad "
                                                             f"in {rel}: {ad[:80]!r} (words in common {j:.2f}, below "
                                                             f"{NEAR_DUPLICATE} passes).",
                                   "A new concept says something the account's ads do not: rewrite it."))
    return out


def _trend_row(run: RunFolder, i: int, c: dict, evidence: str | None) -> list[Problem]:
    """CB2 and R3: the first glance row names the trend by its kind (or the guess), and its source
    the trend id of a saved card."""
    cid, field, trend = c["id"], f"concepts[{i}]", c["plugin"]["trend"]
    rows = c["glance"]
    out = [Problem(f"{field}.glance[{k}].source", f"{cid}'s glance row {r['label']} has no source (R3).",
                   "Say where its numbers come from.") for k, r in enumerate(rows) if not _filled(r["source"])]
    if not rows:
        return out + [Problem(f"{field}.glance", f"{cid} has no glance rows.",
                              "Give it the evidence at a glance: the trend, Customers, Account, Competition.")]
    first = rows[0]
    if evidence == GUESS:
        if trend is not None:
            out.append(Problem(f"{field}.plugin.trend", f"{cid} names a trend, but a guess run has no trend data.",
                               "Set plugin.trend to null."))
        if first.get("key") != "guess" and _norm(first["label"]) != _norm(GUESS_LABEL):
            out.append(Problem(f"{field}.glance[0].label", f"The first glance row of {cid} is {first['label']!r}; in "
                                                           f"a guess run it is \"{GUESS_LABEL}\" (CB2, R3).",
                               f"Label it \"{GUESS_LABEL}\" (in another language: key it guess, with the "
                               "label in that language)."))
    elif evidence == TRENDSMESH:
        if trend is None:
            return out + [Problem(f"{field}.plugin.trend", f"{cid} has no trend, and this run rests on TrendsMesh "
                                                           "data (CB2).", "Name the trend it builds on in plugin.trend.")]
        tid, kind = trend["trend_id"], trend["kind"]
        want = f"Rising {kind.removesuffix('_trend')}"
        if tid != c["plugin"]["candidate"]:
            out.append(Problem(f"{field}.plugin.trend.trend_id", f"{cid}'s trend is {tid}, but its candidate is "
                                                                 f"{c['plugin']['candidate']}: a concept builds on the "
                                                                 "trend it was scored and checked as (CB3, CB4).",
                               "Name the same trend in plugin.trend and plugin.candidate."))
        if first.get("key") != "trend" and first["label"].strip() != want:
            out.append(Problem(f"{field}.glance[0].label", f"The first glance row of {cid} is {first['label']!r}; its "
                                                           f"trend is a {kind}, so the row is \"{want}\" (CB2: a "
                                                           "hook_trend is never called a format).",
                               f"Label it \"{want}\" (in another language: key it trend, with \"{want}\" said "
                               "in that language)."))
        card, where = _card(run, tid)
        if card is None:
            out.append(Problem(f"{field}.plugin.trend.trend_id", f"{cid}'s trend {tid}: {where}.",
                               "Name a trend whose card this run saved, or fetch its card first."))
        elif card.get("kind") and card["kind"] != kind:
            out.append(Problem(f"{field}.plugin.trend.kind", f"{cid}'s plugin.trend.kind is {kind}, but its saved "
                                                             f"card {where} says {card['kind']}.",
                               f"Set it to {card['kind']} and label the row \"Rising "
                               f"{str(card['kind']).removesuffix('_trend')}\"."))
        ref = first.get("source_ref") if isinstance(first.get("source_ref"), str) else ""
        named = _norm(trend["name"]) in _norm(first["source"]) if _filled(trend.get("name")) else True
        if tid[:8].casefold() not in ref.casefold() or not named:
            out.append(Problem(f"{field}.glance[0].source_ref" if named else f"{field}.glance[0].source",
                               f"The {want} row of {cid} does not name its trend: its source names the trend "
                               f"(\"{trend.get('name')}\") and its source_ref holds the trend id's first characters, "
                               f"{tid[:8]} (R3).",
                               "Name the trend in source (its name, in the page's language) and its id in source_ref, "
                               f"like \"TrendsMesh trend {tid[:8]}, pulled <date>\"."))
    return out


# What the page shows of a brief (issue #132): never a trend id, a run file or a theme id. `source_ref` holds those.
_SHOWN_CONCEPT = ("title", "one_liner", "key_message", "hypothesis")
_SHOWN_BEAT = ("see", "hear", "ost", "why")


def _shown_fields(brief: dict):
    """(field path, text) of every brief field the page shows that `_visible` reads."""
    meta = brief.get("meta") or {}
    yield "meta.title", meta.get("title")
    for k, text in (meta.get("lede") or {}).items() if isinstance(meta.get("lede"), dict) else ():
        yield f"meta.lede.{k}", text
    findings = brief.get("findings") or {}
    for j, item in enumerate(findings.get("items") or []):
        for k in ("title", "text"):
            yield f"findings.items[{j}].{k}", (item or {}).get(k)
    yield "findings.caveat", findings.get("caveat")
    au = brief.get("audience") or {}
    yield "audience.text", au.get("text")
    yield "audience.source", au.get("source")
    for j, fact in enumerate(au.get("facts") or []):
        for k in ("value", "label"):
            yield f"audience.facts[{j}].{k}", (fact or {}).get(k)
    for i, c in enumerate(brief.get("concepts") or []):
        at = f"concepts[{i}]"
        for k in _SHOWN_CONCEPT:
            yield f"{at}.{k}", c.get(k)
        for j, row in enumerate(c.get("glance") or []):
            for k in ("label", "text", "source"):
                yield f"{at}.glance[{j}].{k}", (row or {}).get(k)
        for k in ("text", "description"):
            yield f"{at}.hook.{k}", (c.get("hook") or {}).get(k)
        for j, beat in enumerate(c.get("beats") or []):
            for k in _SHOWN_BEAT:
                yield f"{at}.beats[{j}].{k}", (beat or {}).get(k)
        note = c.get("note") if isinstance(c.get("note"), dict) else {}
        for k in ("title", "text"):
            yield f"{at}.note.{k}", note.get(k)
        for j, why in enumerate(c.get("why") or []):
            yield f"{at}.why[{j}].source_label", (why or {}).get("source_label")
        for j, p in enumerate(c.get("customer_phrases") or []):
            yield f"{at}.customer_phrases[{j}].used_in", (p or {}).get("used_in")


def _visible(run: RunFolder, brief: dict) -> list[Problem]:
    """Issue #132: a field the page shows holds no trend id, run file or theme id (`plain_words`); `source_ref` is
    where they go, in the folded "Technical details"."""
    have, out = plain_words.codes(run), []
    for field, text in _shown_fields(brief):
        hit = plain_words.found(text, have)
        if hit is None:
            continue
        what, value = hit
        if field.endswith(".source"):
            thing = {plain_words.RUN_FILE: "file", plain_words.TREND_ID: "trend id"}.get(what, "theme id")
            todo = f"Say the source in words in source, and put the {thing} in source_ref."
        elif what == plain_words.THEME_ID:
            todo = "Name the theme by its title, as the voice themes give it; its id goes in a source_ref."
        else:
            todo = "Say it in plain words (a trend by its name, a read by what it is); ids and files go in a source_ref."
        out.append(Problem(field, f"{field} shows {what} ({value}).", todo))
    return out


def _competition(i: int, c: dict, checks: list[dict] | None, where: str) -> list[Problem]:
    """CB4: the concept's verdict is the saturation file's, and its Competition row says it."""
    cid, field, sat = c["id"], f"concepts[{i}]", c["plugin"]["saturation"]
    out = []
    if checks is not None:
        row = next((r for r in checks if r.get("candidate") == c["plugin"]["candidate"]
                    and research_checks.key(str(r.get("query") or "")) == research_checks.key(sat["query"])), None)
        if row is None:
            out.append(Problem(f"{field}.plugin.saturation", f"{where} has no saturation check of "
                                                             f"{c['plugin']['candidate']} with the query "
                                                             f"{sat['query']!r} ({cid}, CB4).",
                               "Use the candidate and query of its check, or check it and run tm brief saturation."))
        elif row.get("verdict") != sat["verdict"]:
            out.append(Problem(f"{field}.plugin.saturation.verdict", f"{cid}'s plugin.saturation.verdict is "
                                                                     f"{sat['verdict']}, but the saturation file says "
                                                                     f"{row.get('verdict')} for {sat['query']!r} (CB4).",
                               "Copy the verdict of its check."))
        else:   # another query of the same candidate that found a competitor counts too
            found = next((r for r in checks if r.get("candidate") == c["plugin"]["candidate"]
                          and r.get("verdict") == "competitor_found"), None)
            if found is not None and sat["verdict"] != "competitor_found":
                out.append(Problem(f"{field}.plugin.saturation", f"{cid} cites the check {sat['query']!r} "
                                                                 f"(none_found), but the check {found.get('query')!r} "
                                                                 f"of the same candidate found a competitor (CB4).",
                                   "Cite the check that found a competitor, with its verdict competitor_found."))
    k, competition = _row(c, "Competition")
    if competition is None:
        return out + [Problem(f"{field}.glance", f"{cid} has no Competition row (CB4).",
                              "Add it with the Ad Library verdict.")]
    text = _norm(competition["text"])
    if sat["verdict"] == "competitor_found":
        ok, words = _says(text, COMPETITOR_FOUND), COMPETITOR_FOUND
    else:   # "none found" ... "in Ad Library titles": what was looked for may come between
        ok, words = bool(re.search(r"(?<!\w)none found(?!\w).*(?<!\w)in ad library titles(?!\w)", text)), \
            research_checks.NONE_FOUND
    if not ok:
        out.append(Problem(f"{field}.glance[{k}].text", f"The Competition row of {cid} does not say \"{words}\", its verdict "
                                              f"{sat['verdict']} (CB4).", f"Say \"{words}\" in it."))
    return out


def _texts(c: dict) -> list[str]:
    """Where a customer phrase counts as used: the hook, the beats' sound and on-screen text, the
    hooks to test, the ad copy and the creator's lines."""
    hook, ad_copy, creator = c["hook"], c.get("ad_copy") or {}, c.get("creator") or {}
    texts = [hook.get("text"), hook.get("description"), *(c.get("hooks_to_test") or [])]
    texts += [b.get(k) for b in c.get("beats") or [] for k in ("hear", "ost")]
    texts += [ad_copy.get(k) for k in ("primary", "headline", "button")]
    texts += [s.get("line") for s in creator.get("say") or [] if isinstance(s, dict)]
    return [t for t in texts if _filled(t)]


def _phrases(i: int, c: dict, bank: list[str] | None, where: str, least: int) -> list[Problem]:
    """CB5: enough phrases, each from the bank (or adapted from a bank phrase it names), each used."""
    cid, field, phrases = c["id"], f"concepts[{i}].customer_phrases", c.get("customer_phrases") or []
    out = []
    if len(phrases) < least:
        out.append(Problem(field, f"{cid} uses {len(phrases)} customer phrases, fewer than "
                                  f"voice.min_phrases_per_concept {least} (CB5).",
                           "Use the customers' own words from the language bank in its hook, lines or copy."))
    texts = _texts(c)
    for j, p in enumerate(phrases):
        phrase, adapted = p.get("phrase"), p.get("adapted_from")
        if not _filled(phrase):
            out.append(Problem(f"{field}[{j}]", f"{cid}'s customer phrase {j + 1} is empty.", "Give the phrase."))
            continue
        if p.get("translated") is True and adapted is None:      # issue #3: the original stays the source
            out.append(Problem(f"{field}[{j}].adapted_from", f"{cid}'s phrase {phrase!r} is marked translated, but "
                                                             "does not name the bank phrase it translates (CB5).",
                               "Put the original phrase, as the bank has it, in adapted_from."))
            continue
        if bank is not None:
            whole = {_norm(b) for b in bank}
            if adapted is not None and _norm(adapted) not in whole:
                out.append(Problem(f"{field}[{j}].adapted_from", f"{cid}'s phrase {phrase!r} is adapted_from "
                                                                 f"{adapted!r}, which is not a phrase of the language "
                                                                 f"bank ({where}).",
                                   "Name the whole bank phrase it was adapted from, as the bank has it."))
            elif adapted is None and _norm(phrase) not in whole and not (
                    len(_words(phrase)) >= MIN_PHRASE_WORDS and voice_themes._found(phrase, bank)):
                out.append(Problem(f"{field}[{j}].phrase", f"{cid}'s phrase {phrase!r} is not in the language bank "
                                                           f"({where}): it is a whole bank phrase, or at least "
                                                           f"{MIN_PHRASE_WORDS} words of one in a row (CB5).",
                                   "Use a bank phrase as customers wrote it, or name the bank phrase it was adapted "
                                   "from in adapted_from."))
        if not voice_themes._found(phrase, texts):
            out.append(Problem(f"{field}[{j}].phrase", f"{cid}'s phrase {phrase!r} is not used in the concept: not in "
                                                       "its hook, beats, hooks to test, ad copy or creator lines (CB5).",
                               "Use it there, or list the phrases the concept uses."))
    return out


def _fidelity_sound_persona(i: int, c: dict, directional: bool | None, audience_says: bool,
                            cfg: dict, row: str = "Account") -> list[Problem]:
    """CB7 (the hook-to-image relation), CB9 (the sound's licence) and CB1 (directional: in the
    Account row, or in the brief's audience text, where the dry run says it; an organic video brief's Persona
    row, `row`)."""
    cid, field, plugin = c["id"], f"concepts[{i}].plugin", c["plugin"]
    out = []
    image = plugin["hook_image"]
    if image["relation"] == "contradiction" and not _filled(image.get("why")):
        out.append(Problem(f"{field}.hook_image.why", f"{cid}'s hook and image contradict: a contradiction needs its "
                                                      "why (CB7).", "Say why the image contradicts the hook, or "
                                                                    "change the relation."))
    sound = plugin["sound"]
    if sound is None and (plugin["trend"] or {}).get("kind") == "sound_trend":
        out.append(Problem(f"{field}.sound", f"{cid} builds on a sound trend but names no sound (CB9).",
                           "Give plugin.sound with its licence."))
    if sound is not None:
        licence = sound["licence"]
        if brief_research._setting(cfg, "music.require_ads_license") and licence != "commercial":
            out.append(Problem(f"{field}.sound", f"{cid}'s sound has the licence {licence!r}; with "
                                                 "music.require_ads_license only commercial sounds are used (CB9).",
                               "Pick a sound licensed for ads, or none."))
        elif licence != "commercial" and not (sound["organic_only"] or _filled(sound["licensed_equivalent"])):
            out.append(Problem(f"{field}.sound", f"{cid}'s sound has the licence {licence!r}, and it is neither organic "
                                                 "only nor given a licensed equivalent for the ads (CB9).",
                               "Mark it organic_only, or name a licensed_equivalent."))
    if directional is not None:
        if plugin["directional"] is not directional:
            out.append(Problem(f"{field}.directional", f"{cid}'s plugin.directional is {plugin['directional']}, but "
                                                       f"the audience pick is "
                                                       f"{'directional' if directional else 'not directional'} (CB1).",
                               f"Set it to {str(directional).lower()}."))
        k, account = _row(c, row)
        if directional and not audience_says and not (account and _says(account["text"], "directional")):
            where = f"concepts[{i}].glance[{k}].text" if account else f"concepts[{i}].glance"
            what = "the account numbers are" if row == "Account" else "the persona is"
            out.append(Problem(where, f"Neither the {row} row of {cid} nor audience.text says \"directional\", and "
                                      "the audience pick is (CB1: thin data).",
                               f"Say in the audience text or the {row} row that {what} directional."))
    return out


def _concept_checks(run: RunFolder, brief: dict, evidence: str | None, cfg: dict) -> list[Problem]:
    concepts = brief["concepts"]
    out = _meta(run, brief, evidence, cfg) + _ids(concepts)
    out += _axes(concepts, brief_research._setting(cfg, "concepts.min_axes_diff"))
    out += _near_duplicates(concepts, running_ads(run)[0])
    checks, sat_where, sat_missing = _saturation(run)
    bank, bank_where, bank_missing = _bank(run)
    out += [p for p in (sat_missing, bank_missing) if p]
    pick = (state.load(run).audience or {}).get("pick")
    directional = pick.get("directional") if isinstance(pick, dict) else None
    if not isinstance(directional, bool):
        directional = None
        out.append(Problem("audience", "The audience is not picked yet, so CB1's directional mark cannot be checked.",
                           "Pick it first (tm audience pick), then check the brief."))
    least = brief_research._setting(cfg, "voice.min_phrases_per_concept")
    audience_says = _says((brief.get("audience") or {}).get("text"), "directional")
    for i, c in enumerate(concepts):
        out += _trend_row(run, i, c, evidence)
        out += _competition(i, c, checks, sat_where)
        out += _phrases(i, c, bank, bank_where, least)
        out += _fidelity_sound_persona(i, c, directional, audience_says, cfg)
    prose = _prose(brief, bank or [])
    out += research_checks.wording(prose, BANNED)
    if evidence == GUESS:
        out += research_checks.wording(prose, RISING)
    return out


def _prose(brief: dict, bank: list[str]) -> object:
    """The brief as the agent's own words: the copied fields (`COPIED_KEYS`) left out, and the copied
    texts (the product's name and link, quotes, customer and bank phrases, queries, trend names) cut
    out of the rest, normalised. Paths stay the brief's."""
    meta = brief["meta"]
    copied = [meta["product"].get("name"), meta["product"].get("landing_url"), *bank]
    for c in brief["concepts"]:
        copied += [p.get(k) for p in c.get("customer_phrases") or [] if isinstance(p, dict)
                   for k in ("phrase", "adapted_from")]
        copied += [w.get("quote") for w in c.get("why") or [] if isinstance(w, dict)]
        copied += [(c["plugin"].get("saturation") or {}).get("query"), (c["plugin"]["trend"] or {}).get("name")]
    texts = sorted({_norm(t) for t in copied if _filled(t)}, key=len, reverse=True)
    cut = re.compile("|".join(map(re.escape, texts))) if texts else None

    def scrub(node: object) -> object:
        if isinstance(node, dict):
            return {k: scrub(v) for k, v in node.items() if k not in COPIED_KEYS}
        if isinstance(node, list):
            return [scrub(v) for v in node]
        if isinstance(node, str):
            text = _norm(node)
            return cut.sub(" ", text) if cut else text
        return node
    return scrub(brief)


# --- stage brief ---------------------------------------------------------------------------------

def _valid_until(run: RunFolder, brief: dict, cfg: dict) -> list[Problem]:
    """CB8: the earliest `visible_until` of the concepts' trend cards, else prepared + the default."""
    meta = brief["meta"]
    prepared, created = brief_research._date(meta["prepared"]), date.fromisoformat(state.load(run).created)
    if prepared is None:
        return [Problem("meta.prepared", f"meta.prepared is {meta['prepared']!r}, not a date (YYYY-MM-DD).",
                        "Give the day the brief was prepared.")]
    if prepared < created:
        return [Problem("meta.prepared", f"meta.prepared is {prepared}, before the run began on {created} (CB8: the "
                                         "brief is valid from the run's date).", f"Set it to {created} or later.")]
    seen = []
    for c in brief["concepts"]:
        trend = c["plugin"]["trend"]
        card = _card(run, trend["trend_id"])[0] if trend else None
        until = brief_research._date(card.get("visible_until")) if card else None
        if until:
            seen.append(until)
    if seen:
        want, why = min(seen), "the earliest visible_until of the concepts' trends"
    else:
        days = brief_research._setting(cfg, "brief.valid_days_default")
        want, why = prepared + timedelta(days=days), f"prepared {prepared} + brief.valid_days_default {days} days"
    if meta["valid_until"] != want.isoformat():
        return [Problem("meta.valid_until", f"meta.valid_until is {meta['valid_until']!r}; it is {want} ({why}) (CB8).",
                        f"Set it to {want}.")]
    return []


def _currency(brief: dict, cfg: dict) -> list[Problem]:
    """CB13: the brief's money is in brief.currency, with the rate stated when the account differs."""
    meta, out = brief["meta"], []
    currency = brief_research._setting(cfg, "brief.currency")
    if meta.get("currency") != currency:
        out.append(Problem("meta.currency", f"meta.currency is {meta.get('currency')!r}; the brief is in "
                                            f"brief.currency {currency} (CB13).", f"Set it to {currency}."))
    account = brief_research._setting(cfg, "account.currency") or meta["plugin"]["account_currency"]
    if account == currency:
        return out
    rate = brief_research._setting(cfg, "brief.fx_rate")
    example = f"1 {currency} = {rate:.2f} {account}" if isinstance(rate, (int, float)) else f"1 {currency} = 3.70 {account}"
    note = meta.get("fx_note")
    fx_note = re.compile(rf"1 {re.escape(currency)} = (\d+(?:\.\d+)?) ([A-Z]{{3}})")   # "1 USD = 3.70 PLN"
    m = fx_note.fullmatch(note) if isinstance(note, str) else None
    if m is None:
        out.append(Problem("meta.fx_note", f"meta.fx_note is {note!r}; the account spends in {account}, so it states the "
                                           f"rate like \"{example}\" (CB13).", f"Write it as \"{example}\"."))
    elif m.group(2) != account:
        out.append(Problem("meta.fx_note", f"meta.fx_note converts to {m.group(2)}, but the account spends in "
                                           f"{account} (CB13).", f"Write it as \"{example}\"."))
    elif isinstance(rate, (int, float)) and float(m.group(1)) != float(rate):
        out.append(Problem("meta.fx_note", f"meta.fx_note says {m.group(1)}, but brief.fx_rate is {rate} (CB13).",
                           f"Write it as \"{example}\"."))
    return out


def _intake(i: int, c: dict, cfg: dict) -> list[Problem]:
    """CB13: budget, deadline, approver and usage are the intake's, or null ("to set"); never invented."""
    cid, out = c["id"], []
    todo = 'Leave it null, so the page shows "to set", or ask the user and set intake.{key}.'
    for group, key, intake in INTAKE_FIELDS:
        value = (c.get(group) or {}).get(key)
        given = brief_research._setting(cfg, f"intake.{intake}")
        if value is not None and _norm(str(value)) != _norm("" if given is None else str(given)):
            had = f"the intake has none (intake.{intake} is null)" if given is None else f"intake.{intake} is {given!r}"
            out.append(Problem(f"concepts[{i}].{group}.{key}", f"{cid}'s {group}.{key} is {value!r}, but {had}.",
                               todo.format(key=intake)))
    usage = (c.get("creator") or {}).get("usage")
    given = [str(v) for v in (brief_research._setting(cfg, f"intake.{k}") for k in ("rights", "fee")) if v is not None]
    if usage is not None and not (given and all(_norm(v) in _norm(str(usage)) for v in given)):
        had = (f"the intake gives {_list([repr(v) for v in given])}" if given
               else "the intake has none (intake.rights and intake.fee are null)")
        out.append(Problem(f"concepts[{i}].creator.usage", f"{cid}'s creator.usage is {usage!r}, but {had}.",
                           'Leave it null, so the page shows "to set", or state the intake\'s rights and fee.'))
    return out


def _page(url: object) -> tuple[str, str] | None:
    """(host without www., path without its trailing /) of an http(s) link: the same page however
    it is written (scheme, case, query and fragment aside); None for anything else."""
    if not _filled(url):
        return None
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower().removeprefix("www.")
    if parts.scheme.lower() not in ("http", "https") or not host:
        return None
    return host, parts.path.rstrip("/")


def landing_quotes(run: RunFolder, brief: dict) -> list[Problem]:
    """R3 for the landing page (issue #14): a concept's `why` quote given as the landing page's (its
    link is the product's landing page or another page saved as `00_raw/landing_*`, or its link or
    label names such a file) must be in that page's saved text, verbatim as the voice check matches
    a quote. A WebFetch summary is not the page's words: nothing may be quoted from it. A run with no
    landing page saved leaves this to A1, which requires one."""
    literal, summaries = page_text.landing_texts(run)
    if not literal and not summaries:
        return []
    pages = {p for p in [_page(brief["meta"]["product"].get("landing_url"))] + [_page(u) for _, _, u in literal] if p}
    files = [rel for rel, _, _ in literal]
    out = []
    for i, c in enumerate(brief["concepts"]):
        for j, why in enumerate(c.get("why") or []):
            if not isinstance(why, dict) or not _filled(why.get("quote")):
                continue
            named = " ".join(str(why.get(k) or "") for k in ("url", "source_label"))
            if _page(why.get("url")) not in pages and f"{page_text.RAW}/landing_" not in named:
                continue
            quote, field = why["quote"], f"concepts[{i}].why[{j}]"
            if not literal:
                out.append(Problem(field, f"{c['id']} quotes the landing page ({quote!r}), but the page is saved only "
                                          f"as a WebFetch summary ({_list(summaries)}): a summary is not the page's "
                                          "words, so no quote may come from it (R3).",
                                   "Save the page's own text with tm page fetch and copy the quote from it, or "
                                   "drop the quote."))
            elif not any(_says(t, quote) for _, t, _ in literal):
                where = voice_themes._where_it_parts(quote, [t for _, t, _ in literal]).replace("the item",
                                                                                                "the page text")
                out.append(Problem(field, f"{c['id']}'s quote {quote!r}, given as the landing page's, is not in its "
                                          f"saved text ({_list(files)}): {where} (R3).",
                                   "Copy the quote word for word from the saved page text, or drop it."))
    return out


def _brief_checks(run: RunFolder, brief: dict, cfg: dict) -> list[Problem]:
    out = []
    scenes = animatic.scene_names()
    for i, c in enumerate(brief["concepts"]):
        cid, field = c["id"], f"concepts[{i}]"
        if not _filled(c["key_message"]):
            out.append(Problem(f"{field}.key_message", f"{cid} has no key message (CB10).", "Write its key message."))
        if not (_filled(c["hypothesis"]) and brand._one_sentence(c["hypothesis"])):
            out.append(Problem(f"{field}.hypothesis", f"{cid}'s hypothesis is to be one sentence (CB10).",
                               "Write what the test shows in one sentence."))
        hooks = [h for h in c.get("hooks_to_test") or [] if _filled(h)]
        if not 2 <= len(hooks) <= 3:
            out.append(Problem(f"{field}.hooks_to_test", f"{cid} has {len(hooks)} hooks to test; a brief tests 2-3 hooks "
                                                         "(CB10).", "Give two or three hook variants."))
        ad_copy = c.get("ad_copy") or {}
        for key in ("primary", "headline"):
            if not _filled(ad_copy.get(key)):
                out.append(Problem(f"{field}.ad_copy.{key}", f"{cid} lacks ad_copy.{key} (R7: the decision is on the "
                                                             "primary text, headline and thumbnail).",
                                   f"Write its {key}."))
        if not _filled(c["plugin"].get("thumbnail")):
            out.append(Problem(f"{field}.plugin.thumbnail", f"{cid} lacks plugin.thumbnail (R7).",
                               "Describe the thumbnail: the first frame and its text."))
        for k, beat in enumerate(c["beats"]):
            scene = (beat.get("animatic") or {}).get("scene")
            if scene not in scenes:
                out.append(Problem(f"{field}.beats[{k}].animatic.scene", f"{cid}'s beat {k + 1} has the scene "
                                                                          f"{scene!r}, which scenes.js does not draw.",
                                   f"Use one of {', '.join(sorted(scenes))}."))
        out += _intake(i, c, cfg)
    return out + _valid_until(run, brief, cfg) + _currency(brief, cfg) + landing_quotes(run, brief)


PRODUCT_SCENES = ("product_phone", "morning_then_product")   # they draw params.product (scenes.js)


def warnings(brief: dict) -> list[Problem]:
    """What `tm brief check` says without failing (follow-up to issue 12): a product scene with no `product`
    param draws a plain placeholder (with `fixture: "book"`, the dry run's book) instead of the brief's product."""
    concepts = brief.get("concepts") if isinstance(brief, dict) else None
    meta = brief.get("meta") if isinstance(brief, dict) else None
    product = ((meta or {}).get("product") or {}) if isinstance(meta, dict) else {}
    name = product.get("name") if isinstance(product, dict) and _filled(product.get("name")) else None
    out = []
    for i, c in enumerate(concepts if isinstance(concepts, list) else []):
        for k, beat in enumerate((c.get("beats") if isinstance(c, dict) else None) or []):
            anim = beat.get("animatic") if isinstance(beat, dict) else None
            if not isinstance(anim, dict) or anim.get("scene") not in PRODUCT_SCENES:
                continue
            params = anim.get("params") if isinstance(anim.get("params"), dict) else {}
            if _filled(params.get("product")):
                continue
            drawn = "the dry run's book" if params.get("fixture") == "book" else "a plain placeholder"
            out.append(Problem(f"concepts[{i}].beats[{k}].animatic.params.product",
                               f"{c.get('id', f'Concept {i + 1}')}'s beat {k + 1} ({anim['scene']}) has no product "
                               f"name, so its animatic shows {drawn} instead of the product.",
                               "Give it params.product: the product's name" + (f" ({name})" if name else "")
                               + ", as meta.product.name says it; and params.screen, what is on its screen."))
    return out


# --- stage production ----------------------------------------------------------------------------

def _number_forms(raw: object) -> list[str]:
    """The ways a figure read as `raw` (93.2, "1234.56", {"value": "93.22"}) may be written in a text: as read, with
    two decimals (a whole count: none) and, from 100 on, rounded to a whole number; with "." or "," before the decimals and no, ",", "."
    or " " between thousands. Forms with fewer than `FIGURE_DIGITS` digits, and zero, are left out."""
    value = raw.get("value") if isinstance(raw, dict) else raw
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, str):
        text = value.strip().rstrip("%").strip()
        try:
            number = float(text)
        except ValueError:
            return []
    elif isinstance(value, (int, float)):
        number, text = float(value), None
    else:
        return []
    if not number or number != number or abs(number) in (float("inf"),):
        return []
    number = abs(number)
    bases = {f"{number:.2f}"} if number != int(number) or (text is not None and "." in text) else set()
    if text is not None and re.fullmatch(r"\d+(?:\.\d+)?", text.lstrip("-")):
        bases.add(text.lstrip("-"))
    if number == int(number) or number >= 100:
        bases.add(str(round(number)))
    out = set()
    for base in bases:
        whole, _, cents = base.partition(".")
        groups = [whole[max(0, k - 3):k] for k in range(len(whole), 0, -3)][::-1]
        for sep in ("", ",", ".", " "):
            for point in (".", ","):
                if sep == point:
                    continue
                form = sep.join(groups) + (point + cents if cents else "")
                if sum(ch.isdigit() for ch in form) >= FIGURE_DIGITS:
                    out.add(form)
    return sorted(out, key=lambda f: (-len(f), f))


def _figure_pattern(forms: list[str]) -> re.Pattern:
    """`forms` where they stand on their own: no digit, or digit and separator, on either side."""
    return re.compile(r"(?<!\d)(?<!\d[.,])(?:" + "|".join(re.escape(f) for f in forms) + r")(?!\d)(?![.,]\d)")


def account_figures(run: RunFolder) -> list[tuple[str, str, str, re.Pattern]]:
    """The run's own account figures (CB13, issue #146): each spend, cost per result and results value in the saved
    Meta reads of `01_base/meta/` (a list sent as a JSON text included), as (the value as read, what it is, the file,
    its pattern). Each value once; never a generic word, so it reads the same in every language."""
    found: dict[str, tuple[str, str, str, re.Pattern]] = {}

    def add(raw: object, what: str, rel: str) -> None:
        forms = _number_forms(raw)
        if forms:
            shown = str(raw.get("value") if isinstance(raw, dict) else raw)
            found.setdefault(forms[0], (shown, what, rel, _figure_pattern(forms)))

    def walk(node: object, rel: str) -> None:
        if isinstance(node, str) and node.lstrip().startswith(("[", "{")):
            try:
                node = json.loads(node)
            except ValueError:
                return
        if isinstance(node, dict):
            for k, v in node.items():
                what = FIGURE_KEYS.get(k) if isinstance(k, str) else None
                if what is None:
                    walk(v, rel)
                    continue
                if isinstance(v, dict) and isinstance(v.get("values"), list):   # Meta's results
                    v = v["values"]
                for x in v if isinstance(v, list) else [v]:
                    if isinstance(x, dict) and "value" not in x:
                        walk(x, rel)
                    elif not isinstance(x, list):
                        add(x, what, rel)
        elif isinstance(node, list):
            for v in node:
                walk(v, rel)

    folder = run.path / META
    for f in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = json.loads(f.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        answer = data.get("answer", data) if isinstance(data, dict) and "_input" in data else data
        walk(answer, f.relative_to(run.path).as_posix())
    return list(found.values())


def advertisers_seen(run: RunFolder, brief: dict) -> list[str]:
    """The advertisers the run's saturation answers name (CB4's file), the product itself aside: the creator view
    never names them (CB13, issue #146)."""
    checks = _saturation(run)[0] or []
    product = _norm(((brief.get("meta") or {}).get("product") or {}).get("name"))
    names = {a.strip() for r in checks for a in r.get("advertisers") or [] if isinstance(a, str) and a.strip()}
    return sorted(a for a in names if _norm(a) != product)


def _creator_data(run: RunFolder, brief: dict) -> list[tuple[str, str, re.Pattern]]:
    """What the creator view never shows, as (the value, what it is, its pattern on normalised text): the run's own
    account figures and the advertisers it saw in the Ad Library."""
    out = [(shown, f"the account's {what} in {rel}", pattern) for shown, what, rel, pattern in account_figures(run)]
    out += [(name, "an advertiser in the run's Ad Library answers", _whole(_norm(name)))
            for name in advertisers_seen(run, brief)]
    return out


def _production_checks(run: RunFolder, brief: dict, cfg: dict) -> list[Problem]:
    meta, out = brief["meta"], []
    for view, label, rows in (("media-buyer", "media", MEDIA_ROWS), ("editor", "editor", EDITOR_ROWS)):
        if view not in meta["recipients"]:
            continue
        for i, c in enumerate(brief["concepts"]):
            have = {_norm(r["label"]) for r in c.get(label) or []}
            out += [Problem(f"concepts[{i}].{label}", f"{c['id']} lacks the {label} row {row} (CB13, the {view} "
                                                      "view).", f"Add the row {row!r}.")
                    for row in rows if _norm(row) not in have]
    if "creator" in meta["recipients"]:
        data = _creator_data(run, brief)            # the PDF is read even with no data: never sent unread
        if data:
            out += _creator_view_data(brief, data,
                                      i18n.page_lang(i18n.languages_of(cfg).working, *PAGE_AREAS).lang)   # as built
        out += _creator_pdf_data(run, brief, data, out)
    return out


def _shown(whose: str, field: str, value: str, what: str) -> Problem:
    """A value of the run's data in the creator view: the field it is in, and the value."""
    m = _CONCEPT_FIELD.match(field)
    return Problem(field, f"{whose} creator view shows \"{value}\" in {m.group(2) if m else field}: {what} (CB13: the "
                          "creator view holds no account figures, results or competitors).",
                   "Say it the way a creator needs it, without that value.")


_CONCEPT_FIELD = re.compile(r"^concepts\[(\d+)\]\.(.+)$")


def _whole(low: str) -> re.Pattern:
    """`low` where it stands on its own: not the middle of a longer word."""
    start = r"(?<!\w)" if re.match(r"\w", low[0]) else ""
    end = r"(?!\w)" if re.match(r"\w", low[-1]) else ""
    return re.compile(start + re.escape(low) + end)


def _creator_view_data(brief: dict, data: list[tuple[str, str, re.Pattern]], lang: str = "en") -> list[Problem]:
    """CB13's data check on the creator view as the page builds it (`brief_page.view_text`): each of the brief's
    texts the view shows that holds a value of `data`, named by its field, then any such value in the rest of the
    view (the page's own text, a cut text). The usage line may name the creator's fee. A brief the page cannot be
    built from is left to the page's own check."""
    from tm import brief_page              # brief_page imports this module
    try:
        rest = "\n".join(_norm(t) for t in brief_page.view_text(brief, "creator", lang))
    except Stop:
        return []
    out = []
    texts = sorted(((where, _norm(text)) for where, text in research_checks.strings(brief)),
                   key=lambda wt: -len(wt[1]))
    for where, low in texts:
        whole = _whole(low) if low else None
        if whole is None or not whole.search(rest):     # longest first: a text inside a longer one is not shown
            continue
        rest = whole.sub(" ", rest)
        if where.endswith(".creator.usage"):
            continue
        m = _CONCEPT_FIELD.match(where)
        whose = f"{brief['concepts'][int(m.group(1))].get('id')}'s" if m else "The brief's"
        out += [_shown(whose, where, value, what) for value, what, pattern in data if pattern.search(low)]
    out += [_shown("The page", "creator view", value, what) for value, what, pattern in data if pattern.search(rest)]
    return out


def _creator_pdf_data(run: RunFolder, brief: dict, data: list[tuple[str, str, re.Pattern]],
                      said: list[Problem]) -> list[Problem]:
    """CB13 on the creator PDF (issue #10): the text of the creator PDF the latest page built from this brief
    printed (`brief_page.creator_pdf`), each value of `data` in it that no problem in `said` names already. The
    usage line may name the fee, as in the view. A PDF that is gone or has no text to read is a problem too: it is
    never sent unread. No page printed from this brief yet: nothing to read."""
    from tm import brief_page, brief_pdf          # brief_page imports this module
    found = brief_page.creator_pdf(run, brief)
    if found is None:
        return []
    rel, path = found
    try:
        shown = [brief_pdf.text(path, joiner) for joiner in (" ", "")]   # a word whose letters change font: ""
    except (OSError, ValueError) as exc:
        shown, why = [], f"cannot be read ({exc})"
    else:
        why = "has no text the check can read"
    if not shown or not _filled(shown[0]):
        return [Problem("creator PDF", f"The creator PDF {rel} {why}, so CB13 cannot be checked on it.",
                        "Build the page again (tm brief page), then check again.")]
    lows = [_norm(t) for t in shown]
    for c in brief["concepts"]:
        usage = (c.get("creator") or {}).get("usage") if isinstance(c, dict) else None
        if _filled(usage):
            lows = [low.replace(_norm(usage), " ") for low in lows]
    named = " ".join(x.what for x in said)
    return [Problem("creator PDF", f"The creator PDF {rel} shows \"{value}\": {what} (CB13: the creator view holds no "
                                   "account figures, results or competitors).",
                    "Find it in the creator view, say it without that value, then build the page again (tm brief page).")
            for value, what, pattern in data if any(pattern.search(low) for low in lows) and f'"{value}"' not in named]


# --- the organic video brief (issue #136) --------------------------------------------------------

def _organic_rows(i: int, c: dict) -> list[Problem]:
    """The rows an organic concept's glance has beside the trend's: Channel (O2) and Persona (O3)."""
    out = []
    for label in ("Channel", "Persona"):
        if _row(c, label)[1] is None:
            out.append(Problem(f"concepts[{i}].glance", f"{c['id']} has no {label} row (an organic video brief's "
                                                        "glance: the trend, Channel and Persona).",
                               f"Add the {label} row, keyed {label.lower()}, with its source."))
    return out


def _organic_block(i: int, c: dict, business: bool) -> list[Problem]:
    """The concept's topic, format, length and sound; a business account's sound is licensed for business use
    (the owner's decision on issue #136: a personal account may take a trending sound, its licence shown)."""
    cid, field, block = c["id"], f"concepts[{i}].organic", c["organic"]
    out = [Problem(f"{field}.{k}", f"{cid} has no {k}.", f"Give its {k}.")
           for k in ("topic", "format") if not _filled(block.get(k))]
    if not (isinstance(block.get("length_s"), (int, float)) and block["length_s"] > 0):
        out.append(Problem(f"{field}.length_s", f"{cid}'s length is {block.get('length_s')!r}, not seconds.",
                           "Give its length in seconds."))
    sound = block["sound"]
    if not _filled(sound.get("name")):
        out.append(Problem(f"{field}.sound.name", f"{cid}'s sound has no name.", "Name the sound, or the track."))
    if business and sound["licence"] != "commercial":
        out.append(Problem(f"{field}.sound", f"{cid}'s sound has the licence {sound['licence']!r}, and the channel is a "
                                             "business account: it may use only sounds licensed for business use.",
                           "Pick a sound licensed for business use (a commercial library track), or ask whether the "
                           "channel is a personal account."))
    return out


def _organic_concept_checks(run: RunFolder, brief: dict, evidence: str | None, cfg: dict) -> list[Problem]:
    """O5: CB2 (the trend row), CB6 (two axes apart), CB7, CB9 and CB1's directional mark, the Channel and Persona
    rows and each concept's organic block. No customer phrases (CB5) and no Ad Library check (CB4)."""
    concepts = brief["concepts"]
    out = _meta(run, brief, evidence, cfg) + _ids(concepts)
    out += _axes(concepts, brief_research._setting(cfg, "concepts.min_axes_diff"))
    pick = (state.load(run).audience or {}).get("pick")
    directional = pick.get("directional") if isinstance(pick, dict) else None
    if not isinstance(directional, bool):
        directional = None
        out.append(Problem("audience", "The persona is not picked yet, so CB1's directional mark cannot be checked.",
                           "Pick it first (tm audience pick --no-data), then check the brief."))
    channel = brief["meta"]["channel"]
    said = brief_research._setting(cfg, "channel.business")
    if isinstance(said, bool) and channel["business"] is not said:
        out.append(Problem("meta.channel.business", f"meta.channel.business is {channel['business']}, but the start card "
                                                    f"says {said} (channel.business).", f"Set it to {str(said).lower()}."))
    business = said if isinstance(said, bool) else channel["business"]
    audience_says = _says((brief.get("audience") or {}).get("text"), "directional")
    for i, c in enumerate(concepts):
        out += _trend_row(run, i, c, evidence)
        out += _fidelity_sound_persona(i, c, directional, audience_says, cfg, row="Persona")
        out += _organic_rows(i, c)
        out += _organic_block(i, c, business)
    prose = _prose(brief, [])
    out += research_checks.wording(prose, BANNED)
    if evidence == GUESS:
        out += research_checks.wording(prose, RISING)
    return out


def _organic_view_checks(run: RunFolder, brief: dict, cfg: dict) -> list[Problem]:
    """O7: each concept's key message and one-sentence hypothesis (CB10), its beats' scenes, the intake's values
    never invented, CB8's valid-until, the landing page's quotes (R3); the creator view (what to film and say), the
    editor rows, the publisher view against the platform rules, and the posting plan."""
    from tm import brief_organic             # it reads tm.kit, which a creative brief's other stages never need
    meta, out = brief["meta"], []
    scenes = animatic.scene_names()
    for i, c in enumerate(brief["concepts"]):
        cid, field = c["id"], f"concepts[{i}]"
        if not _filled(c["key_message"]):
            out.append(Problem(f"{field}.key_message", f"{cid} has no key message (CB10).", "Write its key message."))
        if not (_filled(c["hypothesis"]) and brand._one_sentence(c["hypothesis"])):
            out.append(Problem(f"{field}.hypothesis", f"{cid}'s hypothesis is to be one sentence (CB10).",
                               "Write what the video tests in one sentence."))
        for k, beat in enumerate(c["beats"]):
            scene = (beat.get("animatic") or {}).get("scene")
            if scene not in scenes:
                out.append(Problem(f"{field}.beats[{k}].animatic.scene", f"{cid}'s beat {k + 1} has the scene "
                                                                          f"{scene!r}, which scenes.js does not draw.",
                                   f"Use one of {', '.join(sorted(scenes))}."))
        if "creator" in meta["recipients"]:
            creator = c.get("creator") or {}
            out += [Problem(f"{field}.creator.{k}", f"{cid}'s creator view has no {what} (the creator view).",
                            f"Write {what}.") for k, what in (("say", "what to say"), ("shots", "shots to record"))
                    if not creator.get(k)]
        if "editor" in meta["recipients"]:
            have = {_norm(r["label"]) for r in c.get("editor") or []}
            out += [Problem(f"{field}.editor", f"{cid} lacks the editor row {row} (the editor view).",
                            f"Add the row {row!r}.") for row in EDITOR_ROWS if _norm(row) not in have]
        out += _intake(i, c, cfg)
    if "publisher" in meta["recipients"]:
        out += brief_organic.posting_problems(brief)
    out += brief_organic.plan_problems(brief)
    return out + _valid_until(run, brief, cfg) + landing_quotes(run, brief)


# --- the check -----------------------------------------------------------------------------------

def check(run: RunFolder, brief: dict, stage: Stage, cfg: dict) -> list[Problem]:
    """Everything wrong in brief.json at the stage, cumulative (see the module docstring); empty
    when it holds. `cfg` is the run's config ({} for the defaults). An organic video brief is checked at its
    own stages (`ORGANIC_STAGES`, issue #136)."""
    problems = shape(brief, stage)
    if problems:
        return problems
    evidence = state.load(run).evidence
    if stage in ORGANIC_STAGES:
        out = _organic_concept_checks(run, brief, evidence, cfg or {}) + _visible(run, brief)
        if stage == "organic_views":
            out += _organic_view_checks(run, brief, cfg or {})
        return out
    out = _concept_checks(run, brief, evidence, cfg or {}) + _visible(run, brief)
    if stage in ("brief", "production"):
        out += _brief_checks(run, brief, cfg or {})
    if stage == "production":
        out += _production_checks(run, brief, cfg or {})
    return out


def _id_order(cid: str) -> list:
    """C2 before C10."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", cid)]


def _greedy(brief: dict, totals: dict[str, float], count: int, min_axes: int) -> tuple[list[str], dict]:
    """The pick, and each concept passed over as too close: {id: (the picked concept nearest to it,
    the axes they differ on)}."""
    scored = [c for c in brief["concepts"] if c["plugin"]["candidate"] in totals]
    ranked = sorted(scored, key=lambda c: (-totals[c["plugin"]["candidate"]], _id_order(c["id"])))
    kept: list[dict] = []
    close: dict[str, tuple[str, list[str]]] = {}
    for c in ranked:
        if len(kept) == count:
            break
        near = min(((k["id"], apart(c, k)) for k in kept), key=lambda kv: len(kv[1]), default=None)
        if near is not None and len(near[1]) < min_axes:
            close[c["id"]] = near
        else:
            kept.append(c)
    return [c["id"] for c in kept], close


def pick(brief: dict, totals: dict[str, float], count: int, min_axes: int) -> list[str]:
    """The top concepts by their candidate's total (ties by concept id), each kept only
    when it differs from every one kept on at least `min_axes` axes (CB6), up to `count`. It may
    return fewer. A concept whose candidate has no total is not picked."""
    return _greedy(brief, totals, count, min_axes)[0]


def rule_pick(run: RunFolder, brief: dict) -> dict:
    """`pick` on the run's latest scores (weighted) and its `concepts.count` and
    `concepts.min_axes_diff`: {picked, count, min_axes, close, unscored, message}, the message
    saying why it returns fewer. Stop for a brief not in its shape or a run without scores; the
    one rule `tm brief pick` and `tm brief choose --source rule` share."""
    shape_problems = shape(brief, "concepts")
    if shape_problems:
        lines = "; ".join(p.what for p in shape_problems)
        raise Stop(f"The brief is not in its shape ({lines}), so the rule cannot pick. Fix it and check it with tm "
                   f"brief check; nothing was picked; {AGAIN}.")
    scores, missing = brief_research._latest_scores(run)
    if scores is None:
        raise Stop(f"{missing} Score the candidates and check them (tm brief scores) before picking; nothing was "
                   f"picked; {AGAIN}.")
    cfg = brief_research.run_config(run)
    totals = brief_research.totals(scores, brief_research.weights(cfg))
    count = brief_research._setting(cfg, "concepts.count")
    least = brief_research._setting(cfg, "concepts.min_axes_diff")
    picked, close = _greedy(brief, totals, count, least)
    concepts = brief["concepts"]
    unscored = [c["id"] for c in concepts if c["plugin"]["candidate"] not in totals]
    message = f"Picked {len(picked)} of the {count} concepts asked (concepts.count): {', '.join(picked) or 'none'}."
    if len(picked) < count:
        why = [f"{cid} is {len(axes)} axis{'' if len(axes) == 1 else 'es'} from {near} "
               f"({', '.join(axes) or 'no axis differs'}), fewer than concepts.min_axes_diff {least}"
               for cid, (near, axes) in close.items()]
        if unscored:
            why.append(f"{', '.join(unscored)} {'has' if len(unscored) == 1 else 'have'} no score")
        if len(concepts) < count:
            why.append(f"the brief has {len(concepts)} concept{'' if len(concepts) == 1 else 's'}")
        message += f" It returns fewer: {'; '.join(why)}."
    return {"picked": picked, "count": count, "min_axes": least, "close": list(close), "unscored": unscored,
            "message": message}


# --- the step checks -----------------------------------------------------------------------------

def key(stage: str) -> str:
    """The run.json `checked` key of a stage's pass."""
    return f"brief_{stage}"


def concepts_gap(run: RunFolder) -> str | None:
    return stepchecks.fresh(run, key("concepts"), FINAL, STEM, "json")


def brief_gap(run: RunFolder) -> str | None:
    return stepchecks.fresh(run, key("brief"), FINAL, STEM, "json")


def production_gap(run: RunFolder) -> str | None:
    return stepchecks.fresh(run, key("production"), FINAL, STEM, "json")


def organic_concepts_gap(run: RunFolder) -> str | None:
    return stepchecks.fresh(run, key("organic_concepts"), FINAL, STEM, "json")


def organic_views_gap(run: RunFolder) -> str | None:
    return stepchecks.fresh(run, key("organic_views"), FINAL, STEM, "json")
