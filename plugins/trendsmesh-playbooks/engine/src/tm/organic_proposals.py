"""Proposals of an idea run (organic video, FLOWS.md C1 to C3): the check, the decisions taken on the
page, and one production run per idea marked produce.

C1. The agent writes `03_wip/proposals_vNN.json` in the handoff's schema (`schemas/pb3_proposals.schema.json`,
the handoff's, copied) with the plugin's block on each proposal:

    plugin = {"production": ai_footage|talking_character|animation|stills_motion|sections,
              "output": video|script, "risk_hits": [{"item": <one of RISK_ITEMS>, "mitigation": str}],
              "transfer": bool, "weak_link": str|null, "series": str|null, "seed": str|null}

`tm organic proposals check --run R --file F` runs `check` and marks the file it passed on
(`stepchecks.mark`, key `proposals`); C1's step check `proposals_checked` (`checked_gap`) asks that the
latest proposals file is that one, unchanged.

C2. The page saves one document per proposal (`decisions/<pid>`, with `updated_at`). Task 7 reads them
(`page.db_docs`) into `03_wip/decisions_proposals_vNN.json` through `decisions`:

    {"page": "proposals", "proposals": "03_wip/proposals_vNN.json" (the file the page was built from),
     "decisions": {pid: {decision, level, output, platforms, answers, note, carried}}}

A row equal to an earlier page version's is `carried` (PB02's rule, preflight P3-F4).

C3. `tm organic start --run R [--keep-carried]` (`start`) reads the latest decisions file and starts one
production run per idea marked produce: `<date>_<channel slug>-<pid lower>`, run.json
`organic = {parent, proposal, channel, key}`, its outputs, its level, the idea run's config with `kind:
production`, the output and the platforms, and `00_raw/proposal.json`. The channel's library gets the
used trends (`organic_research.record_used`) and one `decisions.jsonl` row per decided proposal. An idea
is its id plus a hash of what it is (`idea_key`), so a proposal rewritten under the same id is a new
idea. Everything a start writes is checked before any folder is made; a failure after that removes the
folder, or says it could not. The idea run records each start in run.json `organic.started` (by
`idea_key`); C3's step check `videos_started` (`started_gap`) asks for a start of every produce.
"""

from __future__ import annotations

import copy
import functools
import hashlib
import json
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

from tm import atlas, brand, brief_config, checkins, config, flow, json_schema, library, manifest, organic, \
    organic_config, organic_research, playbooks, runfolder, state, stepchecks, trend_spool
from tm.config import Problem
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

WIP = "03_wip"
STEM = "proposals"
KEY = "proposals"   # the stepchecks.mark key
NAME = re.compile(rf"^{WIP}/{STEM}_v\d+\.json$")
FILE_PATTERN = f"{WIP}/{STEM}_vNN.json"
DECISIONS_STEM = "decisions_proposals"
SCHEMA = Path(__file__).parent / "schemas" / "pb3_proposals.schema.json"
PROPOSAL_FILE = "00_raw/proposal.json"
SOURCE = "tm organic start"

PRODUCTIONS = ("ai_footage", "talking_character", "animation", "stills_motion", "sections")
PAGE_OUTPUTS = ("video", "script")                                  # the page's words
CONFIG_OUTPUT = {"video": "ai_video", "script": "script"}           # -> organic_config's `output`
RUN_OUTPUT = {"video": "organic_video", "script": "script_to_film"}  # -> the production run's outputs
RISK_ITEMS = ("hands_on_objects", "product_shape", "same_character", "fast_motion", "physics", "model_text",
              "speech", "long_takes", "several_characters")         # OV4's checklist
APPROACHES = {"recreate": "Recreate", "odtworzenie": "Recreate", "inspire": "Inspire", "inspiracja": "Inspire"}
PRODUCT_LEVELS = ("not shown", "incidental", "featured", "soft mention", "hero")   # OV5, verbatim
PRODUCT_WORDS = {**{w: w for w in PRODUCT_LEVELS}, "nie występuje": "not shown"}   # ExampleEdu's Polish word
DECISIONS = ("produce", "later", "skip")
_NOT_FOUND = re.compile(r"no trend found|nie znaleziono trendu", re.IGNORECASE)
_PERCENT = re.compile(r"\d+\s?%")
PRODUCTION_WORDS = {  # a production type in the user's words (flow.md C3), for the stops the agent relays
    "ai_footage": "AI footage", "talking_character": "a talking character", "animation": "an animation",
    "stills_motion": "stills with motion graphics (a quiz or a ranking)", "sections": "a video in sections",
}
NEEDS = {  # a production type the stack hides -> (the stack key, what it needs)
    "ai_footage": ("replicate", "a Replicate key (REPLICATE_API_TOKEN) for the video models"),
    "talking_character": ("replicate", "a Replicate key (REPLICATE_API_TOKEN) for the video models"),
    "animation": ("browser", "Chrome or Edge on this computer (the animation is drawn in it)"),
}
_TEXT_OR_NULL = {"type": ["string", "null"]}
PLUGIN: dict = {
    "type": "object",
    "required": ["production", "output", "risk_hits", "transfer", "weak_link", "series", "seed"],
    "properties": {
        "production": {"enum": list(PRODUCTIONS)},
        "output": {"enum": list(PAGE_OUTPUTS)},
        "risk_hits": {"type": "array", "items": {"type": "object", "required": ["item", "mitigation"],
                                                 "properties": {"item": {"enum": list(RISK_ITEMS)},
                                                                "mitigation": {"type": "string"}}}},
        "transfer": {"type": "boolean"},
        "weak_link": _TEXT_OR_NULL,
        "series": _TEXT_OR_NULL,
        "seed": _TEXT_OR_NULL,
    },
}
_SHAPE_TODO = (f"Write the proposals in the handoff's schema (schemas/{SCHEMA.name}) with the plugin block on each "
               "proposal, as a new version.")


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _plain(exc: Exception) -> str:
    """An exception's message without the resume tail: a check lists problems, it does not stop."""
    return str(exc).removesuffix(".").removesuffix(f"; {AGAIN}").removesuffix(f", then run this again")


def _name(p: dict) -> str:
    """A proposal as the user knows it: its title (never a bare code)."""
    return f"“{p.get('title') or p.get('id')}” ({p.get('id')})"


# --- C1: the check --------------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _schema() -> dict:
    """The handoff's schema with the plugin block required on each proposal."""
    schema = copy.deepcopy(json_schema.load(SCHEMA))
    item = schema["properties"]["proposals"]["items"]
    item["properties"]["plugin"] = PLUGIN
    item["required"] = [*item["required"], "plugin"]
    return schema


def shape(data: object) -> list[Problem]:
    """What breaks the schema, as problems; empty when the file is in its shape."""
    return [Problem(line.split(" ", 1)[0].removeprefix("proposals."), line, _SHAPE_TODO)
            for line in json_schema.problems(data, _schema(), name="proposals")]


def _id_gap(value: object) -> str | None:
    """Why an id cannot name a folder of the run (`organic_pack.id_gap`, the PR D rule for section ids), or None."""
    from tm import organic_pack   # it imports this module: imported where it is used

    return organic_pack.id_gap(value)


def run_channel(name: object, data: dict, channels: list) -> str | None:
    """The run's channel (its slug in config.yaml `channels`) a proposal's `channel` names: the file's
    `channels[]` entry with that id, matched by its id or name, or the name itself."""
    if not _text(name):
        return None
    entry = next((c for c in data.get("channels") or [] if isinstance(c, dict) and c.get("id") == name), {})
    for key in (name, entry.get("id"), entry.get("name")):
        slug = brand.channel_key(key) if _text(key) else ""
        if slug and slug in channels:
            return slug
    return None


def _trends(run: RunFolder, p: dict, pid: str, out: list[Problem]) -> dict[str, list[int]]:
    """Each trend of the proposal resolved to one saved card (its full id -> the picks), its picks
    checked against `tm organic videos`."""
    found: dict[str, list[int]] = {}
    for j, t in enumerate(p["trends"]):
        try:
            tid, _ = organic_research.resolve(run, t["id"])
        except ValueError as exc:  # a Stop too: no card (an error answer is none)
            out.append(Problem(f"{pid}.trends[{j}].id", f"{_name(p)}: {_plain(exc)}.",
                               "Give the id of a trend whose card is saved in this run (fetch it with get_trend)."))
            continue
        picks = t.get("pick") or []
        found[tid] = picks
        if not picks:
            continue
        try:
            n = len(organic_research.videos(run, tid)[2])
        except ValueError as exc:
            out.append(Problem(f"{pid}.trends[{j}].pick", f"{_name(p)}: {_plain(exc)}.",
                               "Fetch the trend's videos, or drop the picks."))
            continue
        bad = [i for i in picks if not 0 <= i < n]
        if bad:
            out.append(Problem(f"{pid}.trends[{j}].pick",
                               f"{_name(p)}: pick {', '.join(map(str, bad))} is not one of the {n} saved videos of "
                               f"{t['id']} (0 to {n - 1}).",
                               f"Pick by the index tm organic videos --trend {t['id']} shows."))
    return found


def _blank(p: dict, pid: str, out: list[Problem]) -> None:
    """The plugin block's texts are words or null, never blank (a blank series would be read as none)."""
    for key in ("weak_link", "series", "seed"):
        value = p["plugin"][key]
        if value is not None and not _text(value):
            out.append(Problem(f"{pid}.plugin.{key}", f"{_name(p)}: plugin.{key} is blank.",
                               f"Write the {key.replace('_', ' ')}, or null."))


def _approach(p: dict, pid: str, found: dict[str, list[int]], out: list[Problem]) -> None:
    approach = APPROACHES.get(str(p["approach"]).strip().lower())
    plugin = p["plugin"]
    if approach is None:
        out.append(Problem(f"{pid}.approach", f"{_name(p)}: the approach is {p['approach']!r}.",
                           "Write Recreate or Inspire (Odtworzenie or Inspiracja on a Polish page)."))
    if approach == "Recreate" and not any(len(set(picks)) >= 2 for picks in found.values()):
        out.append(Problem(f"{pid}.trends", f"{_name(p)} is a Recreate, which needs two evidence videos with the "
                                            "same structure, and no trend has two picks (OV3).",
                           "Pick two of one trend's videos (tm organic videos), or make it an Inspire."))
    if (approach == "Inspire" or plugin["transfer"]) and not _text(plugin["weak_link"]):
        why = "an Inspire" if approach == "Inspire" else "a transfer from another niche"
        out.append(Problem(f"{pid}.plugin.weak_link", f"{_name(p)} is {why}, and its weak link is not named.",
                           "Say in plugin.weak_link where the trend and the channel meet loosely."))


def _risk(p: dict, pid: str, out: list[Problem]) -> None:
    hits = p["plugin"]["risk_hits"]
    level = p["risk"]["level"]
    if (level == "low") != (len(hits) <= 1):
        out.append(Problem(f"{pid}.risk.level", f"{_name(p)}: the risk is {level} with {len(hits)} named "
                                                f"risk{'' if len(hits) == 1 else 's'} (OV4: low is at most one).",
                           "Set the level from the hits: low for none or one, medium or high for more."))
    texts = [(f"{pid}.risk.items[{k}]", x) for k, x in enumerate(p["risk"]["items"])]
    for k, hit in enumerate(hits):
        where = f"{pid}.plugin.risk_hits[{k}].mitigation"
        if not _text(hit["mitigation"]):
            out.append(Problem(where, f"{_name(p)}: the risk {hit['item']} has no mitigation.",
                               "Name how the risk is kept down (OV4)."))
        texts.append((where, hit["mitigation"]))
    for where, text in texts:
        if _PERCENT.search(text):
            out.append(Problem(where, f"{_name(p)}: the risk is given as a percentage ({text!r}).",
                               "Name the risk and its mitigation without percentages: there are not enough "
                               "videos of each type yet (OV4)."))


def _cost(p: dict, pid: str, out: list[Problem]) -> None:
    low, high = p["cost"]["low"], p["cost"]["high"]
    if low < 0 or high < 0 or low > high:
        out.append(Problem(f"{pid}.cost", f"{_name(p)}: the cost range is {low} to {high}.",
                           "Give the low and high cost in USD, both 0 or more, low at most high."))


def makeable(stack: dict | None) -> list[str]:
    """The production types this stack can make as one AI video, in the user's words (PR C re-review N2): the types
    it does not hide, an animation only where the Atlas renderer can draw, stills with motion graphics on the user's
    own pictures without Replicate (GPT Image 2 makes the cards on it); a video in sections is not one type."""
    hidden = organic.hidden_types(stack)
    out = []
    for kind in PRODUCTIONS:
        if kind in hidden or kind == "sections" or (kind == "animation" and atlas.missing() is not None):
            continue
        words = PRODUCTION_WORDS[kind]
        out.append(f"{words} on the user's own pictures" if kind == "stills_motion"
                   and (stack or {}).get("replicate") != "ok" else words)
    return out


def _production(p: dict, pid: str, stack: dict | None, out: list[Problem]) -> None:
    """The stack hides production types for an AI video only (PR B ruling I2): a script a person films
    may be any type."""
    production = p["plugin"]["production"]
    if p["plugin"]["output"] != "video" or stack is None or production not in organic.hidden_types(stack):
        return
    key, needs = NEEDS.get(production, (None, "a tool the stack check found missing"))
    others = [w for w in makeable(stack) if w != PRODUCTION_WORDS[production]]
    out.append(Problem(f"{pid}.plugin.production",
                       f"{_name(p)} is {PRODUCTION_WORDS[production]} as an AI video, which needs {needs}; the stack "
                       f"check found {key or 'it'} {stack.get(key, 'missing') if key else 'missing'}.",
                       "Propose it as a script to film (output script)"
                       + (f", or as an AI video of another kind this stack can make ({'; '.join(others)})" if others
                          else "")
                       + ", or set it up and record the stack again (tm organic stack)."))


def _product(p: dict, pid: str, profile: dict | None, out: list[Problem]) -> None:
    word = PRODUCT_WORDS.get(str(p["product"]["level"]).strip().lower())
    if word is None:
        out.append(Problem(f"{pid}.product.level", f"{_name(p)}: the product level is {p['product']['level']!r}, "
                                                   f"not one of {', '.join(PRODUCT_LEVELS)}.",
                           "Write one of the five levels (OV5)."))
    elif word != "not shown" and profile is not None and not profile.get("store"):
        out.append(Problem(f"{pid}.product.level", f"{_name(p)}: the product is {word}, and the channel has no "
                                                   "store, so its videos show no product: not shown.",
                           "Set the product level to not shown."))


def _used(p: dict, pid: str, found: dict, used: dict[str, dict], own: str | None, out: list[Problem]) -> None:
    """A trend the channel made a video from needs a series; the video this idea itself was started as
    (`own`, its run) is not another use."""
    if _text(p["plugin"]["series"]):
        return
    for tid in found:
        row = used.get(tid)
        if row and row.get("run") != own:
            out.append(Problem(f"{pid}.plugin.series",
                               f"{_name(p)} uses {row.get('name') or tid}, which the channel already made a video "
                               f"from ({row.get('run')}, {row.get('used')}).",
                               "Make it the next video of a series (plugin.series), or use another trend."))


def _seed(p: dict, pid: str, found: dict, seed: tuple[str | None, str | None, str | None], out: list[Problem]) -> None:
    seed_id, seed_trend, verdict = seed
    named = p["plugin"]["seed"]
    if named is not None and named != seed_id:
        was = f"started from {seed_id!r}" if seed_id else "not started from a seed"
        out.append(Problem(f"{pid}.plugin.seed", f"{_name(p)} names the seed {named!r}, and this run was {was}.",
                           "Name the run's own seed, or null."))
    elif (named is not None or seed_trend in found) and verdict != "keep":
        said = f"its re-check says {verdict}" if verdict else "it is not re-checked yet"
        out.append(Problem(f"{pid}.trends", f"{_name(p)} builds on the seeded trend, and {said}.",
                           "Re-check the seed (tm organic seed-check); propose it only when it is kept."))


def _not_found(node: object, where: str, out: list[Problem]) -> None:
    if isinstance(node, str):
        if _NOT_FOUND.search(node):
            out.append(Problem(where, f"{where} says no trend was found.",
                               "Never write that: show the best fit there is, with its numbers (OV2)."))
    elif isinstance(node, dict):
        for k, v in node.items():
            _not_found(v, f"{where}.{k}" if where else str(k), out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _not_found(v, f"{where}[{i}]", out)


def check(run: RunFolder, data: object, cfg: dict) -> list[Problem]:
    """Everything wrong in a proposals file (the module docstring and the plan's Task 6); empty when it
    holds. Reads only."""
    problems = shape(data)
    if problems:
        return problems
    out: list[Problem] = []
    workspace = trend_spool.workspace_of(run)
    s = state.load(run)
    organic_state = s.organic or {}
    proposals = data["proposals"]
    least = config.get(cfg, "proposals.min") or organic_config.DEFAULTS["proposals"]["min"]
    most = config.get(cfg, "proposals.max") or organic_config.DEFAULTS["proposals"]["max"]
    if not least <= len(proposals) <= most:
        out.append(Problem("proposals", f"The page holds {len(proposals)} proposals.",
                           f"Write {least} to {most} (C1), each with a different production type where possible."))
    seen: set[str] = set()
    for i, p in enumerate(proposals):
        if p["id"].casefold() in seen or not _text(p["id"]):
            out.append(Problem(f"proposals[{i}].id", f"The id {p['id']!r} is empty or used twice, in any case (one "
                                                     "folder on Windows and macOS).", "Give each proposal its own id."))
        elif why := _id_gap(p["id"]):
            out.append(Problem(f"proposals[{i}].id", f"The proposal's id {why} (it names the idea's production run "
                                                     "and its files).",
                               "Name it m1, m2, ... or another id of ASCII letters, digits, '_' and '-'."))
        seen.add(p["id"].casefold())
    page_lang = cfg.get("page_lang")
    if data.get("lang") != page_lang:
        out.append(Problem("lang", f"The proposals are in {data.get('lang')!r}, and this run's pages are in "
                                   f"{page_lang!r} (config.yaml page_lang).", f"Write them in {page_lang}, with lang "
                                                                              f"{page_lang}."))
    stack = organic_state.get("stack") if isinstance(organic_state.get("stack"), dict) else None
    if stack is None:
        out.append(Problem("stack", "The stack is not recorded in this run, so it is unknown which production "
                                    "types it hides.", "Record it (tm organic stack), then check again."))
    channels = cfg.get("channels") if isinstance(cfg.get("channels"), list) else []
    row = None
    try:
        row = brief_config.seed_row(run)  # only a seeded run has one
    except ValueError as exc:
        out.append(Problem("seed", str(exc), "Restore 00_raw/seed.json."))
    check_of = organic_state.get("seed_check") if isinstance(organic_state.get("seed_check"), dict) else {}
    seed = (organic_state.get("seed"), (row or {}).get("trend_id"), check_of.get("verdict"))
    profiles: dict[str, dict | None] = {}
    used: dict[str, dict[str, dict]] = {}
    started = organic_state.get("started") if isinstance(organic_state.get("started"), dict) else {}
    for p in proposals:
        pid = p["id"]
        slug = run_channel(p["channel"], data, channels)
        if slug is None:
            out.append(Problem(f"{pid}.channel", f"{_name(p)} is for {p['channel']!r}, which is not one of this run's "
                                                 f"channels ({', '.join(channels) or 'none'}).",
                               "Name the channel by its id in the file's channels, matching config.yaml channels."))
        elif slug not in profiles:
            try:
                profiles[slug] = brand.latest(workspace, slug, kind="channel")
                used[slug] = organic_research.used(workspace, slug)
            except ValueError as exc:
                profiles[slug], used[slug] = None, {}
                out.append(Problem(f"{pid}.channel", f"The channel {slug}'s library cannot be read: {_plain(exc)}.",
                                   "Fix the file it names, then check again."))
        found = _trends(run, p, pid, out)
        _blank(p, pid, out)
        _approach(p, pid, found, out)
        _risk(p, pid, out)
        _cost(p, pid, out)
        _production(p, pid, stack, out)
        _product(p, pid, profiles.get(slug) if slug else None, out)
        if slug:
            own = (started.get(idea_key(p)) or {}).get("run")
            _used(p, pid, found, used.get(slug) or {}, own, out)
        _seed(p, pid, found, seed, out)
    _not_found(data, "", out)
    return out


def checked_gap(run: RunFolder) -> str | None:
    """The `proposals_checked` step check: C1 is done once the latest 03_wip/proposals_vNN.json passed
    `tm organic proposals check` and is unchanged since. Reads only."""
    return stepchecks.fresh(run, KEY, WIP, STEM, "json")


# --- C2: the decisions on the page ----------------------------------------------------------------

def _level(doc: dict) -> str | None:
    """The plugin's page writes the level; the original's writes `mode` (auto: Hands-off) and `gates`
    (all four: Check every step; fewer: Just the big calls)."""
    if doc.get("level") in checkins.LEVEL_IDS:
        return doc["level"]
    if doc.get("mode") == "auto":
        return "hands_off"
    gates = doc.get("gates")
    if isinstance(gates, list):
        return "every_step" if set(organic_config.GATES) <= set(gates) else "big_calls"
    if doc.get("mode") == "gates":  # the original page's default ticks every check-in
        return "every_step"
    return None


def newest_docs(docs: list[tuple[str, dict]], data: dict) -> dict[str, dict]:
    """The page's document for each proposal of `data` (`page.db_docs`: (id, document); the id is the
    proposal's), the newest `updated_at` winning, as read."""
    ids = {p["id"] for p in data.get("proposals") or [] if isinstance(p, dict) and isinstance(p.get("id"), str)}
    newest: dict[str, dict] = {}
    for doc_id, doc in docs:
        if doc_id in ids and isinstance(doc, dict):
            before = newest.get(doc_id)
            if before is None or str(doc.get("updated_at") or "") >= str(before.get("updated_at") or ""):
                newest[doc_id] = doc
    return newest


def decisions(docs: list[tuple[str, dict]], data: dict, defaults: dict[str, dict] | None = None) -> dict[str, dict]:
    """Each proposal's decision from the page's documents (`newest_docs`): `{pid: {decision:
    produce|later|skip|None, level, output, platforms, answers, note, carried}}`. A value the document
    does not give comes from `defaults[<the proposal's channel>]` (`profile_defaults`), else None; the
    output first from the proposal's plugin.output, then the file's default_output (`_output`)."""
    proposals = [p for p in data.get("proposals") or [] if isinstance(p, dict) and isinstance(p.get("id"), str)]
    newest = newest_docs(docs, data)
    out: dict[str, dict] = {}
    for p in proposals:
        doc = newest.get(p["id"], {})
        base = (defaults or {}).get(p.get("channel")) or {}
        platforms = doc.get("platforms")
        platforms = [x for x in platforms if x in brand.PLATFORMS] if isinstance(platforms, list) else []
        answers = doc.get("answers") if isinstance(doc.get("answers"), dict) else {}
        out[p["id"]] = {
            "decision": doc.get("decision") if doc.get("decision") in DECISIONS else None,
            "level": _level(doc) or base.get("level"),
            "output": doc.get("output") if doc.get("output") in PAGE_OUTPUTS else _output(p, data, base),
            "platforms": list(dict.fromkeys(platforms)) or base.get("platforms"),
            "answers": {str(k): v for k, v in answers.items() if isinstance(v, str)},
            "note": doc.get("note") if isinstance(doc.get("note"), str) else "",
            "carried": doc.get("carried") is True,
        }
    return out


def profile_defaults(run: RunFolder, data: dict) -> dict[str, dict]:
    """What a proposal's decision takes when the page leaves it out, per channel named in the file:
    the run's level (run.json, never mode.variant), its config's output, the channel profile's
    platforms."""
    try:
        cfg = config.load(run)
    except ValueError:
        cfg = {}
    level = state.load(run).level
    output = "video" if cfg.get("output") == "ai_video" else "script"
    channels = cfg.get("channels") if isinstance(cfg.get("channels"), list) else []
    workspace = trend_spool.workspace_of(run)
    out: dict[str, dict] = {}
    for p in data.get("proposals") or []:
        name = p.get("channel") if isinstance(p, dict) else None
        if not isinstance(name, str) or name in out:
            continue
        slug = run_channel(name, data, channels)
        try:
            profile = brand.latest(workspace, slug, kind="channel") if slug else None
        except ValueError:
            profile = None
        platforms = (profile or {}).get("platforms")
        out[name] = {"level": level, "output": output,
                     "platforms": list(platforms) if isinstance(platforms, list) and platforms else None}
    return out


# --- C3: starting the picked videos ---------------------------------------------------------------

def _rel(run: RunFolder, path: Path) -> str:
    return path.relative_to(run.path).as_posix()


def _read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _checked_proposals(run: RunFolder) -> tuple[str, dict]:
    """The proposals file C1 passed (its run-relative path and data); a Stop while C1 is not done."""
    gap = checked_gap(run)
    if gap is not None:
        raise Stop(f"The picked videos start from checked proposals, and C1 is done once {gap} (tm organic "
                   f"proposals check --run <run> --file {FILE_PATTERN}). Check them, then start again; {AGAIN}.")
    rel = state.load(run).checked[KEY]["file"]
    return rel, _read(run.path / rel)


def _decisions_file(run: RunFolder) -> tuple[str, dict[str, dict], str | None]:
    """The latest decisions file: its path, its rows and the proposals file it was taken on. A Stop
    when there is none or it is not one."""
    path = run.latest(WIP, DECISIONS_STEM, "json")
    if path is None:
        raise Stop("No decisions have been read from the proposals page yet: read them (tm organic decisions), "
                   f"then start again; {AGAIN}.")
    rel = _rel(run, path)
    try:
        read = _read(path)
        rows = read["decisions"]
        ok = isinstance(rows, dict) and all(isinstance(r, dict) for r in rows.values())
    except (OSError, ValueError, TypeError, KeyError):
        ok = False
    if not ok:
        raise Stop(f"{rel} is not a decisions file of the proposals page. Read the decisions again (tm organic "
                   f"decisions); {AGAIN}.")
    on = read.get("proposals")
    return rel, rows, on if isinstance(on, str) else None


def _today() -> date:
    """Today (tests set it)."""
    return date.today()


def idea_key(p: dict) -> str:
    """An idea as a start knows it: its id and a hash of what makes it that idea (its channel, title,
    video type, approach and trends), so a proposal rewritten under the same id is a new idea, while a
    fixed typo in its risk or cost is not."""
    what = {"channel": p.get("channel"), "title": p.get("title"), "video_type": p.get("video_type"),
            "approach": p.get("approach"), "trends": [t.get("id") for t in p.get("trends") or [] if isinstance(t, dict)]}
    digest = hashlib.sha256(json.dumps(what, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return f"{p.get('id')}#{digest[:12]}"


def _output(p: dict, data: dict, base: dict) -> str | None:
    """A decision's output when the page gives none: the proposal's own (plugin.output), the file's
    default_output, then the run's config (`base`)."""
    for value in ((p.get("plugin") or {}).get("output") if isinstance(p.get("plugin"), dict) else None,
                  data.get("default_output"), base.get("output")):
        if value in PAGE_OUTPUTS:
            return value
    return None


def _row(row: dict, p: dict, data: dict, base: dict) -> dict:
    """A decision with the proposal's, the file's and the profile's values where the file has none."""
    out = {**row, **{k: base.get(k) for k in ("level", "platforms") if row.get(k) in (None, [])}}
    if out.get("output") not in PAGE_OUTPUTS:
        out["output"] = _output(p, data, base)
    return out


def _ws_rel(workspace: Path, path: Path) -> str:
    return path.relative_to(workspace).as_posix()


def _left_over(workspace: Path, parent: str, key: str) -> list[Path]:
    """Production runs this idea run made for `key` that it did not record as started (a start that
    stopped half way, or whose folder could not be removed). A run the user dropped from a week (`organic.dropped`)
    is not one: it stays, so its spend still counts, and a new start of the idea takes a free name."""
    folder = workspace / "runs" / playbooks.get(ORGANIC_VIDEO).id
    found = []
    for run_json in sorted(folder.glob("*/run.json")) if folder.is_dir() else ():
        try:
            mine = json.loads(run_json.read_text(encoding="utf-8")).get("organic") or {}
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(mine, dict) and mine.get("parent") == parent and mine.get("key") == key and not mine.get("dropped"):
            found.append(run_json.parent)
    return found


def _free_name(workspace: Path, slug: str, pid: str, today: date) -> str:
    """`<channel slug>-<pid lower>`, with -2, -3 ... when another idea's run already has that name today."""
    folder = workspace / "runs" / playbooks.get(ORGANIC_VIDEO).id
    base = f"{slug}-{pid.lower()}"
    name, n = base, 1
    while (folder / f"{today:%Y-%m-%d}_{runfolder.slug(name)}").exists():
        n += 1
        name = f"{base}-{n}"
    return name


def _plan(workspace: Path, run: RunFolder, data: dict, p: dict, row: dict, channels: list, parent: str,
          today: date) -> dict:
    """Everything one start needs, checked before any folder is made: the channel, the cards, the run
    name and the used-trend rows. A Stop names what is wrong."""
    slug = run_channel(p["channel"], data, channels)
    if slug is None:
        raise Stop(f"{_name(p)} is for {p['channel']!r}, which is not one of this run's channels. Check the "
                   f"proposals again (tm organic proposals check). Nothing was started; {AGAIN}.")
    key = idea_key(p)
    left = _left_over(workspace, parent, key)
    if left:
        where = ", ".join(_ws_rel(workspace, x) for x in left)
        raise Stop(f"A start of {_name(p)} stopped half way and left {where}, which is not recorded as started. "
                   f"Delete that folder, then start again. Nothing was started; {AGAIN}.")
    resolved = [organic_research.resolve(run, t["id"]) for t in p["trends"]]
    name = _free_name(workspace, slug, p["id"], today)
    run_id = f"{today:%Y-%m-%d}_{runfolder.slug(name)}"
    try:
        used = organic_research.used_rows([
            {"trend_id": tid, "name": card.get("name"), "kind": card.get("kind"), "run": run_id, "video": p["id"],
             "series": p["plugin"]["series"], "used": today.isoformat()} for tid, card in resolved])
    except ValueError as exc:
        raise Stop(f"{_name(p)} cannot be recorded in the channel's used trends ({exc}). Fetch its trend cards again "
                   f"(get_trend) or fix the proposal and check it again. Nothing was started; {AGAIN}.") from None
    return {"p": p, "row": row, "slug": slug, "key": key, "name": name, "ids": [tid for tid, _ in resolved],
            "used": used}


def _remove(workspace: Path, prod: RunFolder, p: dict, exc: Exception) -> ValueError:
    """The error for a start that failed after its folder was made, once the folder is removed; when it
    cannot be removed, the error says so and names it."""
    where = _ws_rel(workspace, prod.path)
    try:
        shutil.rmtree(prod.path)
    except OSError as err:
        return ValueError(f"The run for {_name(p)} could not be started ({exc}), and its folder {where} could not be "
                          f"removed ({err}). Delete that folder, then start again with the same command.")
    return ValueError(f"The run for {_name(p)} could not be started ({exc}), so {where} was not kept. Start again with "
                      "the same command.")


def _make(workspace: Path, run: RunFolder, cfg: dict, plan: dict, parent: str, proposals_rel: str, today: date,
          started: dict, *, organic_extra: dict | None = None) -> dict:
    """One production run from its checked plan: the folder, its state (run.json `organic`, plus `organic_extra`:
    a week's slot names its week), config and 00_raw/proposal.json, the start recorded in the idea run, then the
    used trends. Any failure once the folder exists removes it and the start again (`_remove`)."""
    p, row, slug = plan["p"], plan["row"], plan["slug"]
    try:
        prod = RunFolder.create(workspace, plan["name"], today, playbook=ORGANIC_VIDEO)
    except FileExistsError:
        raise Stop(f"Another start made a run named {plan['name']} for {_name(p)} just now. Start again; "
                   f"{AGAIN}.") from None
    try:
        s = state.load(prod)
        s.organic = {"parent": parent, "proposal": p["id"], "channel": slug, "key": plan["key"], **(organic_extra or {})}
        state.save(prod, s)  # first, so a run left half made is found again (`_left_over`)
        flow.set_level(prod, row["level"])
        s = state.load(prod)
        s.outputs = [RUN_OUTPUT[row["output"]]]
        state.save(prod, s)
        new = copy.deepcopy(cfg)
        new.update({"kind": "production", "output": CONFIG_OUTPUT[row["output"]], "channels": [slug],
                    "platforms": list(row["platforms"])})
        if isinstance(new.get("mode"), dict):
            new["mode"]["variant"] = "az" if row["level"] == "hands_off" else "gated"  # display only
        config.save(prod, new)
        kept = {"proposal": p, "decision": row, "trend_ids": plan["ids"], "channel": slug, "idea_run": parent,
                "proposals_file": proposals_rel, "key": plan["key"],
                "product_level": PRODUCT_WORDS.get(str(p["product"]["level"]).strip().lower())}
        with open(prod.path / PROPOSAL_FILE, "x", encoding="utf-8") as fh:  # a new file in 00_raw
            fh.write(json.dumps(kept, ensure_ascii=False, indent=2) + "\n")
        manifest.record(prod, PROPOSAL_FILE, "00_raw", SOURCE, parent=f"{parent}/{proposals_rel}",
                        params={"proposal": p["id"], "level": row["level"], "output": row["output"]})
        started[plan["key"]] = {"proposal": p["id"], "run": prod.path.name, "path": _ws_rel(workspace, prod.path),
                                "channel": slug, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "kept_carried": bool(row.get("carried"))}
        _save_started(run, started)
        organic_research.record_used(workspace, slug, plan["used"])
    except (OSError, ValueError) as exc:
        if started.pop(plan["key"], None) is not None:
            try:
                _save_started(run, started)
            except OSError:
                pass  # the folder goes below; a start recorded for a missing run is found by its path
        raise _remove(workspace, prod, p, exc) from None
    return {"proposal": p["id"], "title": p.get("title"), "run": prod.path.name,
            "path": started[plan["key"]]["path"], "level": row["level"], "output": row["output"]}


def _save_started(run: RunFolder, started: dict) -> None:
    s = state.load(run)
    s.organic = {**(s.organic or {}), "started": started}
    state.save(run, s)


def start(run: RunFolder, *, keep_carried: bool = False, today: date | None = None) -> dict:
    """Start one production run per idea marked produce in the latest decisions file (the module
    docstring). All or nothing for the refusals: an AI video of a production type the idea run's stack
    hides (the page may switch an idea checked as a script to a video), a produce carried over from an
    earlier page unless the user kept it in chat (`keep_carried`), or a start that cannot be recorded
    stops before any run is made. An idea already started (`idea_key`) is never started again."""
    today = today or _today()
    s = state.load(run)
    if s.playbook != ORGANIC_VIDEO or "proposals" not in s.outputs:
        raise ValueError(f"{run.path.name} is not an organic video idea run: tm organic start starts the ideas picked "
                         "on an idea run's proposals page.")
    proposals_rel, data = _checked_proposals(run)
    decisions_rel, rows, taken_on = _decisions_file(run)
    if taken_on is not None and taken_on != proposals_rel:
        raise Stop(f"The decisions in {decisions_rel} were taken on the page built from {taken_on}, and the checked "
                   f"proposals are now {proposals_rel}. Build the page again and publish it, let the user decide, "
                   f"and read the decisions again; {AGAIN}.")
    cfg = config.load(run)
    channels = cfg.get("channels") if isinstance(cfg.get("channels"), list) else []
    by_id = {p["id"]: p for p in data["proposals"]}
    unknown = [pid for pid, r in rows.items() if r.get("decision") == "produce" and pid not in by_id]
    if unknown:
        verb = "is" if len(unknown) == 1 else "are"
        raise Stop(f"{decisions_rel} marks {', '.join(unknown)} to produce, which {verb} not in {proposals_rel}."
                   f" Read the decisions again from the page built from it; {AGAIN}.")
    defaults = profile_defaults(run, data)
    started = dict((s.organic or {}).get("started") or {})
    hidden_types = organic.hidden_types(organic.stack_of(run))
    drawing = functools.cache(atlas.missing)   # an animation is drawn here, in the user's browser (PB02's words)
    new, again, hidden, undrawn, carried, unclear = [], [], [], [], [], []
    for p in data["proposals"]:
        row = _row(rows.get(p["id"]) or {}, p, data, defaults.get(p["channel"]) or {})
        if row.get("decision") != "produce":
            continue
        if idea_key(p) in started:
            again.append(p)
        elif row.get("output") == "video" and p["plugin"]["production"] in hidden_types:
            hidden.append(p)
        elif row.get("output") == "video" and p["plugin"]["production"] == "animation" and drawing() is not None:
            undrawn.append(p)
        elif row.get("carried") and not keep_carried:
            carried.append(p)
        elif row.get("level") not in checkins.LEVEL_IDS or not row.get("platforms"):
            unclear.append(p)
        else:
            new.append((p, row))
    if hidden or undrawn:
        stack = organic.stack_of(run) or {}
        why = []
        for p in hidden:
            key, needs = NEEDS[p["plugin"]["production"]]
            why.append(f"{_name(p)} is {PRODUCTION_WORDS[p['plugin']['production']]}, which needs {needs} (the stack "
                       f"check found {key} {stack.get(key, 'missing')})")
        for p in undrawn:
            why.append(f"{_name(p)} is {PRODUCTION_WORDS['animation']}, and it cannot be drawn here ({drawing()[1]})")
        todo = "it can be a script to film (switch the output on the page or in chat, then read the decisions again)"
        if hidden:
            todo += ", or set the tool up and record the stack again (tm organic stack), then start"
        if undrawn:
            todo += f", or for the animation: {drawing()[2]}, then start again"
        raise Stop(f"Marked to produce as an AI video, which this run cannot make: {'; '.join(why)}. Ask the user: "
                   f"{todo}. Nothing was started; {AGAIN}.")
    if carried:
        names = ", ".join(_name(p) for p in carried)
        raise Stop(f"{names} {'was' if len(carried) == 1 else 'were'} marked to produce on an earlier page and carried "
                   f"over to this one ({decisions_rel}): the page shows the earlier choice until the user saves "
                   "again. Ask the user once whether to make them; on a yes, start again with --keep-carried; on a "
                   f"no, let them change it on the page and read the decisions again. Nothing was started; {AGAIN}.")
    if unclear:
        names = ", ".join(_name(p) for p in unclear)
        raise Stop(f"{names}: the level or the platforms are not decided, and the run and channel profile give none. "
                   f"Ask the user, then read the decisions again; {AGAIN}.")
    workspace = trend_spool.workspace_of(run)
    if again and not new:
        _record_decisions(run, workspace, data, rows, defaults, started, channels, today)  # later and skip count
        names = ", ".join(f"{_name(p)} as {started[idea_key(p)]['run']}" for p in again)
        raise Stop(f"Every idea marked produce is already started ({names}); an idea is never started twice. Continue "
                   f"in its production run; {AGAIN}.")
    parent = _ws_rel(workspace, run.path.resolve())   # --run may be relative to where tm runs
    plans = [_plan(workspace, run, data, p, row, channels, parent, today) for p, row in new]
    made = [_make(workspace, run, cfg, plan, parent, proposals_rel, today, started) for plan in plans]
    recorded = _record_decisions(run, workspace, data, rows, defaults, started, channels, today)
    return {"started": made, "already_started": [{"proposal": p["id"], "title": p.get("title"),
                                                  "run": started[idea_key(p)]["run"]} for p in again],
            "kept_carried": [p["id"] for p, r in new if r.get("carried")],
            "decisions": decisions_rel, "proposals": proposals_rel, "decisions_recorded": recorded}


def _record_decisions(run: RunFolder, workspace: Path, data: dict, rows: dict, defaults: dict, started: dict,
                      channels: list, today: date) -> int:
    """One row per decided proposal in its channel's decisions.jsonl, once per decision of each idea
    (`idea_key`: a decision changed on a later page, or a rewritten idea, is recorded again); a produce
    once it is started. The number of rows written."""
    s = state.load(run)
    recorded = dict((s.organic or {}).get("decided") or {})
    by_channel: dict[str, list[dict]] = {}
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for p in data["proposals"]:
        row = _row(rows.get(p["id"]) or {}, p, data, defaults.get(p["channel"]) or {})
        decision, key = row.get("decision"), idea_key(p)
        slug = run_channel(p["channel"], data, channels)
        if decision is None or slug is None or recorded.get(key) == decision:
            continue
        if decision == "produce" and key not in started:
            continue
        by_channel.setdefault(slug, []).append({
            "at": at, "date": today.isoformat(), "run": run.path.name, "proposal": p["id"], "idea": key,
            "title": p.get("title"), "decision": decision, "production": p["plugin"]["production"],
            "approach": APPROACHES.get(str(p["approach"]).strip().lower()), "output": row.get("output"),
            "level": row.get("level"), "started": (started.get(key) or {}).get("run")})
        recorded[key] = decision
    for slug, out in by_channel.items():
        library.append_jsonl(workspace / organic_research.ORGANIC_DIR / slug / organic_research.DECISIONS, out)
    s.organic = {**(s.organic or {}), "decided": recorded}
    state.save(run, s)
    return sum(map(len, by_channel.values()))


def started_gap(run: RunFolder) -> str | None:
    """The `videos_started` step check: C3 is done once the latest decisions file was taken on the page
    built from the checked proposals, and a start is recorded (run.json `organic.started`) for every
    idea marked produce in it. Reads only."""
    try:
        rel, rows, taken_on = _decisions_file(run)
    except Stop:
        return ("the decisions on the proposals page are read (tm organic decisions) and each idea marked produce "
                "is started (tm organic start)")
    checked = (state.load(run).checked.get(KEY) or {}).get("file")
    if taken_on is not None and taken_on != checked:
        return (f"the decisions are read from the page built from the checked proposals ({checked or 'none checked'}; "
                f"{rel} was taken on {taken_on}), and each idea marked produce is started (tm organic start)")
    try:
        by_id = {p["id"]: p for p in _read(run.path / checked)["proposals"]}
    except (OSError, ValueError, TypeError, KeyError):
        return f"the checked proposals ({checked}) are readable, and each idea marked produce is started"
    started = (state.load(run).organic or {}).get("started") or {}
    missing = [pid for pid, r in rows.items() if r.get("decision") == "produce"
               and (pid not in by_id or idea_key(by_id[pid]) not in started)]
    if not missing:
        return None
    names = ", ".join(_name(by_id[pid]) if pid in by_id else pid for pid in missing)
    return f"every idea marked produce in {rel} is started (tm organic start): {names}"
