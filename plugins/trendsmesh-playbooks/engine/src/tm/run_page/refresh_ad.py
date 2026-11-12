"""Refresh an ad's stages on the run page: one component per check-in, its materials read from the run's own files.

    materials(ctx, checkin)   the blocks (template._BLOCKS) a check-in's stage shows

Each component reads what the run saved (never what the agent retypes): the ranking (01_base/winner_ranking),
the diagnosis (04_final/diagnosis), the audience (02_research/audience), the TrendsMesh answers (02_research/
trend_*.json and the trend's video pages), the change register, the strategy and creative briefs, the voice
files, the before/after pairs of the manifest, the budgets and the test plan in run.json, the pre-launch check.
Every number is in a dataset whose source is that file. A file the run does not have yet is left out, so a stage
shows what exists. The agent adds what no file holds (players, an extra table) through its ask's `media` and
`data` (tm.run_page.ask_blocks).
"""

from __future__ import annotations

from tm import review, state, trends
from tm.run_page.context import Context

RATES = {"hook_rate", "middle_rate", "ctr", "conversion"}
LADDER = ("p50/p25", "p75/p50", "p95/p75")


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _join(v) -> str | None:
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v if x not in (None, "")) or None
    return None if v in (None, "") else str(v)


# --- G1: pick the ad ------------------------------------------------------------------------------

def _ranking(ctx: Context) -> list[dict]:
    path = ctx.latest("01_base", "winner_ranking", "json")
    data = ctx.json(path)
    if not isinstance(data, dict) or not isinstance(data.get("candidates"), list):
        return []
    src = ctx.rel(path)
    order = {aid: n for n, aid in enumerate(data.get("ranking") or [], 1)}
    rows = []
    for c in data["candidates"]:
        if not isinstance(c, dict):
            continue
        peak, latest = c.get("peak") or {}, c.get("latest") or {}
        rows.append({"rank": order.get(c.get("ad_id")), "ad": c.get("name") or c.get("ad_id"),
                     "verdict": c.get("verdict"), "cpr_then": peak.get("cpr"), "cpr_now": latest.get("cpr"),
                     "cost_increase": c.get("cost_increase"), "value_to_recover": c.get("value_to_recover"),
                     "note": c.get("note")})
    rows.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0))
    tiles = ctx.ds.add(ctx.t("g1.title"), src, ctx.tile_columns(),
                       [{"label": ctx.t("g1.checked"), "value": len(rows)},
                        {"label": ctx.t("g1.fading"), "value": len(order), "sticker": True}])
    table = ctx.ds.add(ctx.t("g1.title"), src, [(k, ctx.col(k), kind) for k, kind in (
        ("rank", "num"), ("ad", "text"), ("verdict", "text"), ("cpr_then", "num"), ("cpr_now", "num"),
        ("cost_increase", "pct"), ("value_to_recover", "num"), ("note", "text"))], rows)
    return [{"kind": "tiles", "data": tiles}, {"kind": "table", "title": ctx.t("g1.title"), "data": table}]


# --- G1a: the diagnosis ---------------------------------------------------------------------------

def _chosen_ad(ctx: Context) -> dict | None:
    """The ranking's candidate the run picked at G1, with the ranking file."""
    picked = [d for d in state.load(ctx.run).decisions if d.get("checkin") == "G1"]
    path = ctx.latest("01_base", "winner_ranking", "json")
    data = ctx.json(path)
    if not picked or not isinstance(data, dict):
        return None
    for c in data.get("candidates") or []:
        if isinstance(c, dict) and c.get("ad_id") == picked[-1].get("choice"):
            return {**c, "_source": ctx.rel(path)}
    return None


def _diagnosis(ctx: Context) -> list[dict]:
    path = ctx.latest("04_final", "diagnosis", "json")
    d = ctx.json(path)
    src = ctx.rel(path) if isinstance(d, dict) else "run.json"
    if not isinstance(d, dict):
        d = state.load(ctx.run).diagnosis
    if not isinstance(d, dict):
        return []
    blocks = []
    ad = _chosen_ad(ctx)
    tiles = [{"label": ctx.t("g1a.stage"), "value": ctx.t_or("stage_name." + str(d.get("stage")), d.get("stage")),
              "sticker": True}]
    if d.get("target_stage"):
        tiles.append({"label": ctx.t("g1a.target"), "value": ctx.t_or("stage_name." + str(d["target_stage"]),
                                                                       d["target_stage"])})
    tile_src = src
    if ad and _num((ad.get("peak") or {}).get("cpr")) and _num((ad.get("latest") or {}).get("cpr")):
        then, now = ad["peak"]["cpr"], ad["latest"]["cpr"]
        tiles += [{"label": ctx.t("g1a.cpr_then"), "value": then}, {"label": ctx.t("g1a.cpr_now"), "value": now},
                  {"label": ctx.t("g1a.cpr_change"), "value": (now - then) / then if then else None, "kind": "pct"}]
        tile_src = f"{src}, {ad['_source']}"
    blocks.append({"kind": "tiles", "data": ctx.ds.add(ctx.t("g1a.title"), tile_src,
                                                       ctx.tile_columns(), tiles)})
    rows = [{"metric": ctx.label("metric", k), "best": v[0], "latest": v[1], "kind": "pct" if k in RATES else "num"}
            for k, v in (d.get("evidence") or {}).items() if isinstance(v, (list, tuple)) and len(v) == 2]
    if rows:
        did = ctx.ds.add(ctx.t("g1a.funnel"), src, [("metric", ctx.col("metric"), "text"), ("best", ctx.col("best"), "num"),
                                                    ("latest", ctx.col("latest"), "num")], rows)
        blocks.append({"kind": "compare", "title": ctx.t("g1a.funnel"), "data": did, "label": "metric", "a": "best",
                       "b": "latest", "a_name": ctx.col("best"), "b_name": ctx.col("latest")})
    lad = d.get("ladder") or {}
    if isinstance(lad.get("peak"), dict) and isinstance(lad.get("latest"), dict):
        dropped = set(lad.get("dropped") or [])
        steps = [{"step": s + (f" · {ctx.t('g1a.dropped')}" if s in dropped else ""), "best": lad["peak"].get(s),
                  "latest": lad["latest"].get(s), "kind": "pct"} for s in LADDER if s in lad["peak"]]
        did = ctx.ds.add(ctx.t("g1a.ladder"), src, [("step", ctx.col("step"), "text"), ("best", ctx.col("best"), "pct"),
                                                    ("latest", ctx.col("latest"), "pct")], steps)
        blocks.append({"kind": "compare", "title": ctx.t("g1a.ladder"), "data": did, "label": "step", "a": "best",
                       "b": "latest", "a_name": ctx.col("best"), "b_name": ctx.col("latest")})
    seen = [ctx.t_or("stage_name." + str(s), s) for s in d.get("also_seen") or []]
    if seen:
        blocks.append({"kind": "list", "title": ctx.t("g1a.also_seen"), "items": seen})
    return blocks


# --- G1b: the audience ----------------------------------------------------------------------------

def _audience(ctx: Context) -> list[dict]:
    a = state.load(ctx.run).audience or {}
    blocks = []
    hyp = (a.get("hypothesis") or {}).get("file")
    text = ctx.text(ctx.inside(hyp)) if hyp else None
    if text:
        blocks.append({"kind": "text", "title": ctx.t("g1b.hypothesis"), "text": text, "pre": True,
                       "summary": ctx.t("g1b.hypothesis_open"), "source": hyp})
    path = ctx.inside(a.get("file")) if a.get("file") else ctx.newest("02_research/audience", "audience_v*.json")
    doc = ctx.json(path)
    if isinstance(doc, dict):
        src = ctx.rel(path)
        segs = [s for s in doc.get("segments") or [] if isinstance(s, dict)]
        if segs:
            did = ctx.ds.add(ctx.t("g1b.segments"), src, [(k, ctx.col(k), kind) for k, kind in (
                ("name", "text"), ("age", "text"), ("gender", "text"), ("results", "num"), ("spend", "num"),
                ("cost_per_result", "num"))], segs)
            blocks.append({"kind": "table", "title": ctx.t("g1b.segments"), "data": did})
        pick = doc.get("pick") if isinstance(doc.get("pick"), dict) else None
        if pick:
            did = ctx.ds.add(ctx.t("g1b.pick"), src, ctx.tile_columns(), [
                {"label": ctx.t("g1b.segment"), "value": pick.get("segment"), "sticker": True},
                {"label": ctx.col("results"), "value": pick.get("results")},
                {"label": ctx.col("cost_per_result"), "value": pick.get("cost_per_result")},
                {"label": ctx.t("g1b.formats"), "value": _join(doc.get("formats"))}])
            blocks.insert(0 if not blocks else 1, {"kind": "tiles", "data": did})
    return blocks


# --- G2: trends -----------------------------------------------------------------------------------

_NUMBERS = (("videos", ("videos_count", "video_count", "videos_known", "videos")),
            ("creators", ("creators", "distinct_creators", "creators_count")),
            ("views", ("views_total", "total_views", "reach", "views")),
            ("reach_per_follower", ("median_reach_per_follower", "median_view_lift", "reach_per_follower")),
            ("new_creators_week", ("new_creators_per_week", "new_creators_week", "velocity")),
            ("hook_texts", ("distinct_hook_texts", "hook_texts")),
            ("first_video", ("first_video", "first_seen", "first_video_at")),
            ("latest_video", ("latest_video", "last_seen", "latest_video_at", "updated_at")),
            ("trend_since", ("since", "trend_since", "became_trend_at")),
            ("active_days", ("active_for_days", "days_active")),
            ("platforms", ("platforms",)), ("languages", ("languages",)))


def _first(card: dict, keys: tuple[str, ...]):
    for where in (card, card.get("growth") if isinstance(card.get("growth"), dict) else {},
                  card.get("reach") if isinstance(card.get("reach"), dict) else {}):
        for k in keys:
            v = where.get(k)
            if isinstance(v, list) and k != "videos":
                return _join(v)
            if v not in (None, "", []) and not isinstance(v, (dict, list)):
                return v
    return None


def _trend_card(ctx: Context, path) -> dict | None:
    answer = trends.unwrap(ctx.json(path))
    card = answer if isinstance(answer, dict) and ("name" in answer or "id" in answer) else None
    if card is None:
        found = trends.items(answer) if answer is not None else []
        card = found[0] if found and isinstance(found[0], dict) else None
    if card is None:
        return None
    src = ctx.rel(path)
    tid = str(card.get("id") or card.get("trend_id") or "")
    rel = card.get("relative") if isinstance(card.get("relative"), dict) else {}
    chips = [{"text": f"{ctx.t('trend.' + k)}: {v}"} for k, v in (
        ("status", card.get("status")), ("confidence", card.get("confidence")),
        ("momentum", card.get("momentum") if not isinstance(card.get("momentum"), dict) else card["momentum"].get("band")),
        ("rank", card.get("rank") or rel.get("position") or rel.get("band"))) if v not in (None, "")]
    if str(card.get("status", "")).lower() == "confirmed":
        chips[0]["style"] = "pink"
    numbers = [{"label": ctx.t("trend.n." + key), "value": v} for key, keys in _NUMBERS
               if (v := _first(card, keys)) is not None]
    out = {"kind": "trend", "name": card.get("name") or tid, "chips": chips,
           "meaning": " · ".join(str(card[k]) for k in ("formula", "what_it_is", "original_phrase")
                                 if isinstance(card.get(k), str) and card[k].strip()) or None}
    if numbers:
        out["numbers"] = ctx.ds.add(f"{out['name']}", src, [("label", ctx.col("metric"), "text"),
                                                           ("value", ctx.col("value"), "num")], numbers)
    flags = [f for f in (card.get("badges") or card.get("flags") or []) if isinstance(f, str) and f.strip()]
    if flags:
        out["badges"] = [{"text": ctx.t_or("badge." + f, f.replace("_", " ")),
                          "style": "warn" if "one_video" in f or "top_share" in f or "single" in f else ""} for f in flags]
    proof = card.get("proof") or card.get("confirmations") or []
    rows = []
    for p in proof if isinstance(proof, list) else []:
        if isinstance(p, dict):
            links = p.get("links") or p.get("urls") or []
            rows.append({"source": p.get("source") or p.get("kind"), "stands": p.get("stands") or p.get("verdict"),
                         "says": p.get("says") or p.get("text") or p.get("why"),
                         "url": p.get("url") or (links[0] if isinstance(links, list) and links else None),
                         "links": len(links) if isinstance(links, list) else None})
        elif isinstance(p, str) and p.strip():
            rows.append({"says": p})
    if rows:
        out["confirmations"] = ctx.ds.add(ctx.t("trend.confirmations"), src, [
            ("source", ctx.col("source"), "text"), ("stands", ctx.col("stands"), "text"),
            ("says", ctx.col("says"), "text"), ("url", ctx.col("example"), "link"), ("links", ctx.col("links"), "num")],
            rows)
    vids = trends.load_videos(ctx.run, tid) if tid else []
    if vids:
        vsrc = ", ".join(ctx.rel(f) for f in trends.video_files(ctx.run, tid)) or src
        places: dict[str, int] = {}
        for v in vids:
            where = v.get("hook_source") or v.get("hook_location")
            if isinstance(where, str) and where:
                places[where] = places.get(where, 0) + 1
        if places:
            out["placement"] = {"title": ctx.plural("trend.placement", len(vids), n=len(vids)),
                                "parts": [{"label": ctx.t_or("hook_source." + k, k), "value": n} for k, n in places.items()]}
        top = sorted((v for v in vids if isinstance(v, dict)), key=lambda v: -(v.get("views") or 0))[:8]
        out["videos"] = ctx.ds.add(ctx.t("trend.videos"), vsrc, [
            ("hook_text", ctx.col("hook_text"), "text"), ("hook_source", ctx.col("hook_source"), "text"),
            ("appears_at_s", ctx.col("appears_at_s"), "num"), ("views", ctx.col("views"), "num"),
            ("creator", ctx.col("creator"), "text"), ("url", ctx.col("video"), "link")],
            [{**v, "creator": v.get("creator") or trends.creator_of(v)} for v in top])
    return out


def _trends(ctx: Context) -> list[dict]:
    base = ctx.run.path / trends.RESEARCH
    files = sorted(p for p in base.glob("trend_*.json") if p.is_file()) if base.is_dir() else []
    cards = [c for c in (_trend_card(ctx, p) for p in files) if c]
    return cards


# --- G3, G4: hooks, the change register, the briefs -----------------------------------------------

def _register(ctx: Context) -> list[dict]:
    reg = state.load(ctx.run).register or {}
    path = ctx.inside(reg.get("file")) if reg.get("file") else ctx.latest("04_final", "change_register", "json")
    data = ctx.json(path)
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    rows = [{"change": i.get("change"), "basis": ctx.t_or("basis." + str(i.get("basis")), i.get("basis")),
             "evidence": _join(i.get("sources")), "because": i.get("because")} for i in items if isinstance(i, dict)]
    did = ctx.ds.add(ctx.t("g3.register"), ctx.rel(path), [(k, ctx.col(k), "text") for k in
                                                         ("change", "basis", "evidence", "because")], rows)
    return [{"kind": "table", "title": ctx.t("g3.register"), "data": did}]


def _doc(ctx: Context, stem: str, title_key: str) -> list[dict]:
    path = ctx.latest("04_final", stem, "md")
    text = ctx.text(path)
    return [{"kind": "text", "title": ctx.t(title_key), "text": text, "pre": True, "summary": ctx.t("data.show_text"),
             "source": ctx.rel(path)}] if text else []


# --- money, voice, video, test --------------------------------------------------------------------

def _budgets(ctx: Context) -> list[dict]:
    s = state.load(ctx.run)
    kinds = sorted(set(s.budgets) | set(s.spend) | set(s.planned))
    if not kinds:
        return []
    rows = [{"budget": ctx.t_or("budget." + k, k), "planned": s.planned.get(k), "approved": s.budgets.get(k),
             "spent": s.spend.get(k)} for k in kinds]
    did = ctx.ds.add(ctx.t("money.title"), "run.json", [("budget", ctx.col("budget"), "text"), ("planned", ctx.col("planned"), "num"),
                                                        ("approved", ctx.col("approved"), "num"), ("spent", ctx.col("spent"), "num")], rows)
    return [{"kind": "table", "title": ctx.t("money.title"), "data": did}]


def _voice(ctx: Context) -> list[dict]:
    base = ctx.run.path / "02_research" / "voice"
    files = sorted((p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in (".mp3", ".wav", ".m4a")),
                   key=lambda p: p.stat().st_mtime)[-6:] if base.is_dir() else []
    items = [{"src": served, "caption": ctx.rel(p)} for p in files if (served := ctx.put(ctx.rel(p)))]
    return [{"kind": "media", "title": ctx.t("voice.title"), "items": items}] if items else []


def _video(ctx: Context) -> list[dict]:
    out = []
    for before, after in review.pairs(ctx.run)[-4:]:
        b, a = ctx.put(before), ctx.put(after)
        if b and a:
            out.append({"kind": "pair", "title": ctx.t("video.pair"), "before": {"src": b, "caption": f"{ctx.t('video.before')}: {before}"},
                        "after": {"src": a, "caption": f"{ctx.t('video.after')}: {after}"}})
    return out


def _qa(ctx: Context) -> list[dict]:
    """The latest QA strips and frame sheets (`03_wip/qa/`), as the old review page showed them."""
    base = ctx.run.path / "03_wip" / "qa"
    files = sorted((p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")),
                   key=lambda p: p.stat().st_mtime)[-8:] if base.is_dir() else []
    items = [{"src": served, "caption": ctx.rel(p)} for p in files if (served := ctx.put(ctx.rel(p)))]
    return [{"kind": "media", "title": ctx.t("video.qa"), "items": items}] if items else []


def _test_plan(ctx: Context) -> list[dict]:
    plan = state.load(ctx.run).test_plan
    if not isinstance(plan, dict):
        return []
    calc = ctx.latest("04_final", "test_plan_calc", "json")
    src = f"run.json{', ' + ctx.rel(calc) if calc else ''}"
    tiles = [{"label": ctx.col(k), "value": plan.get(k)} for k in
             ("budget_total", "per_day", "days", "min_events_per_variant", "variants") if plan.get(k) is not None]
    blocks = []
    if tiles:
        tiles[0]["sticker"] = True
        did = ctx.ds.add(ctx.t("test.title"), src, ctx.tile_columns(), tiles)
        blocks.append({"kind": "tiles", "data": did})
    rules = [{"rule": ctx.label("threshold", k), "value": v} for k, v in (plan.get("thresholds") or {}).items()
             if not isinstance(v, (dict, list))]
    if rules:
        blocks.append({"kind": "table", "title": ctx.t("test.rules"), "data": ctx.ds.add(
            ctx.t("test.rules"), src, [("rule", ctx.col("rule"), "text"), ("value", ctx.col("value"), "num")], rules)})
    if isinstance(plan.get("calculation"), str) and plan["calculation"].strip():
        blocks.append({"kind": "text", "title": ctx.t("test.calculation"), "text": plan["calculation"], "source": src})
    return blocks


# --- the check-ins --------------------------------------------------------------------------------

COMPONENTS = {
    "G1": (_ranking,), "G1a": (_diagnosis,), "G1b": (_audience,), "G2": (_trends,),
    "G3": (_register, lambda c: _doc(c, "strategy_brief", "g3.strategy")),
    "G4": (lambda c: _doc(c, "creative_brief", "g4.brief"), _register),
    "G3r": (_register,), "VB": (_budgets,), "RB": (_budgets,), "G6": (_budgets,),
    "V1c": (_voice,), "GV": (_voice,), "G5": (_video, _qa), "G5r": (_video, _qa), "G9": (_video, _qa),
    "G10": (_test_plan, _budgets), "E2b": (lambda c: _doc(c, "prelaunch_check", "e2b.check"),),
    "G11": (lambda c: _doc(c, "prelaunch_check", "e2b.check"), _test_plan),
}


def outcome(ctx: Context, checkin: str, choice: object) -> str | None:
    """A decided choice in words the run's files give it (G1: the ad's name in the ranking), else None."""
    if checkin == "G1":
        data = ctx.json(ctx.latest("01_base", "winner_ranking", "json"))
        for c in (data.get("candidates") or []) if isinstance(data, dict) else []:
            if isinstance(c, dict) and c.get("ad_id") == choice and c.get("name"):
                return str(c["name"])
    return None


def materials(ctx: Context, checkin: str) -> list[dict]:
    """The blocks the check-in's stage shows from the run's files (none for a check-in without a component)."""
    out: list[dict] = []
    for part in COMPONENTS.get(checkin, ()):
        out += part(ctx)
    return out
