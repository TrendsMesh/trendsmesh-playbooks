"""Create an ad's stages on the run page (issue #17): one component per check-in, its materials read from the run's
own files, as `skills/create-ad/references/pages.md` lists them.

    materials(ctx, checkin)          the blocks (template._BLOCKS, template._LIVE_BLOCKS) a check-in's stage shows
    note_lines(run, checkin, got, lang)  what a choice saved on the page adds to its recorded note
    write_files(run, checkin, got)       the files it writes when recorded (the copy as edited:
                                         `03_wip/copy_decisions_vNN.json`, for tm ad copy accept)

The pages and where their data comes from (never typed into the page by hand):

    concept       03_wip/concepts_vNN.json (the checked one): the model ads (a clip of each, what to take from it),
                  the trends (a TrendsMesh trend's card from 02_research/trend_<id>.json, else "my guess"), and the
                  2 to 3 concepts with their beats, length and why, and cost range; the user picks one (`concept`)
    board         board_vNN.json: the scenes (time, name, picture, on-screen text, line, sound, source); a note per
                  scene (`scene_notes`)
    plan          production_plan_vNN.json: per line the model, its price with the check date, the alternative;
                  what the user's own files replace; the pre-video totals and the video estimate; a note per line;
                  with a talking person, CA5's rows (tm.create_presenter: the plan's situation first, each row's
                  model, needs, voice and today's Replicate price) and two picks, the situation (`presenter`) and the
                  model (`presenter_model`), written into the next plan version when they change it (issue #100)
    visual, audio the gate's batch, raw: each output of the plan's items (its latest Replicate record, as for the takes,
                  and its ElevenLabs takes `03_wip/audio/<item>_vNN.<ext>`); accept, redo or drop each (`items`)
    takes         create_qa.take_rows: each take of the storyboard's videos raw, with its transcript, QA numbers,
                  contact sheet, and the QA's fails and findings; accept, redo or drop each (`items`)
    storyboard    storyboard_vNN.json with the board's scenes: one scene at a time (frames, time, picture, on-screen
                  text, line, sound), the placeholder render, each paid video's exact prompt and price; a note per
                  scene
    review        the edit's versions (03_wip/edit_vNN.mp4, the latest 4) side by side; a pick (`version`) and notes
                  pinned at the playing version's time (`pins`); what was checked (create_qa.edit_report)
    copy          `tm ad copy check`'s page (create_copy.page_data): per ad its facts and each text editable with its
                  live count against its limit and a keep tick (`copy`)
    upload_offer  the files an upload would send, and the paused note
    upload        `tm ad upload check`'s card (create_upload.card): the PAUSED proposal in full, read-only

No decision is left empty (issue #97): the first concept (the agent's recommendation), each item's accept (redo
for a take that fails its QA) and the checked edit's version (else the latest) are selected in advance, and
`tm page decision` takes what the user left as it was (tm.run_page.detail.fill).

Nothing here spends, generates or uploads: a page records the user's choice, and the engine keeps every money
approval where it already guards it (tm budget approve, the paid-call guard, tm ad redo). The upload page never
activates anything (issue #46).

Fixed words are the `ad.page` (and `ad.copy`, `ad.upload`) keys of data/i18n/en.yaml, read with `_w`.
"""

from __future__ import annotations

import json
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from tm import (create_clips, create_config, create_copy, create_plan, create_presenter, create_qa, create_upload,
                i18n, manifest, organic_qa, organic_specs, state)
from tm.run_page import refresh_ad
from tm.run_page.context import MEDIA_EXT, Context
from tm.run_page.template import fmt
from tm.run_page.words import has_key, plural, tx
from tm.runfolder import RunFolder
from tm.tools import _common as tools_common

VISUAL_TYPES = ("presenter", "hook_scene", "product_shot", "still", "slide", "animation")
AUDIO_TYPES = ("music", "sfx", "voice")
ITEM_CHOICES = ("accept", "redo", "drop")
ACCEPT, REDO = ITEM_CHOICES[:2]          # an item's recommended choice, selected on the page in advance (issue #97)
REVIEW_VERSIONS = 4
WIP = create_config.WIP


def _w(where: Context | str, _key: str, **values: object) -> str:
    """`ad.page.<_key>` in the page's language (`where`: the Context, or the language)."""
    lang = where if isinstance(where, str) else where.lang
    return tx("ad.page." + _key, lang, **values)


def _wn(ctx: Context, _key: str, count: object, **values: object) -> str:
    """The count `ad.page.<_key>` (one / other in en.yaml) in the form `count` takes in the page's language."""
    return plural("ad.page." + _key, count, ctx.lang, **values)


def _word(ctx: Context, key: str, default: object) -> str:
    """The table's words for `ad.page.<key>` when it has them, else `default` as it is (a value no word names)."""
    return _w(ctx, key) if has_key("ad.page." + key) else str(default or "")


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _checked(ctx: Context, stem: str) -> tuple[dict | None, str | None]:
    """The checked version of `stem` (`tm ad check`), with its run-relative path; (None, None) before the check."""
    try:
        path = create_plan.checked_file(ctx.run, stem)
    except (OSError, ValueError):
        return None, None
    data = ctx.json(path)
    return (data, ctx.rel(path)) if isinstance(data, dict) else (None, None)


def _readable(name: object) -> str:
    return str(name).replace("_", " ").strip().capitalize()


def _secs(v) -> str:
    return f"{v:g}" if _num(v) else "—"


def _media(ctx: Context, files) -> list[dict]:
    out = []
    for f in files if isinstance(files, list) else [files] if files else []:
        rel = f.get("file") if isinstance(f, dict) else f
        served = ctx.put(rel) if isinstance(rel, str) else None
        if served:
            out.append({"src": served, "caption": (f.get("caption") if isinstance(f, dict) else "") or ""})
    return out


# --- concept --------------------------------------------------------------------------------------

def _model_ad_media(ctx: Context, ad: dict) -> list[dict]:
    """A model ad's clip with its thumbnail as the poster (issue #97): the concepts file's `clip` and `thumb`, else
    what `tm ad clips` saved for its id; its thumbnail alone without a clip."""
    def served(key: str, saved: Path) -> str | None:
        return (ctx.put(ad[key]) if isinstance(ad.get(key), str) else None) or \
            (ctx.put(ctx.rel(saved)) if saved.is_file() else None)
    clip = served("clip", create_clips.clip_path(ctx.run, ad.get("id")))
    thumb = served("thumb", create_clips.thumb_path(ctx.run, ad.get("id")))
    if clip:
        return [{"src": clip, "caption": "", **({"poster": thumb} if thumb else {})}]
    return [{"src": thumb, "caption": ""}] if thumb else []


def _concept(ctx: Context) -> list[dict]:
    data, src = _checked(ctx, create_plan.CONCEPTS)
    if data is None:
        return []
    guess = state.load(ctx.run).evidence == "guess"
    blocks = []
    ads = [a for a in data.get("model_ads") or [] if isinstance(a, dict)]
    names = {a.get("id"): a.get("name") or a.get("id") for a in ads}
    if ads:
        cards = []
        for a in ads:
            chips = [{"text": _w(ctx, "source." + str(a.get("source"))) if a.get("source") in create_plan.SOURCES_MODEL_AD
                      else str(a.get("source")), "style": "warn" if a.get("source") == "guess" else ""}]
            if _num(a.get("run_days")):
                chips.append({"text": _wn(ctx, "run_days", a["run_days"], n=fmt(a["run_days"]))})
            cards.append({"title": str(names[a.get("id")]), "chips": chips,
                          "lines": [_w(ctx, "take_from", why=a.get("why") or "")], "media": _model_ad_media(ctx, a)})
        blocks.append({"kind": "cards", "title": _w(ctx, "model_ads"), "items": cards})
    trends = [t for t in data.get("trends") or [] if isinstance(t, dict)]
    tnames = {t.get("id"): t.get("name") or t.get("id") for t in trends}
    plain = []
    for t in trends:
        card_file = ctx.run.path / "02_research" / f"trend_{t.get('id')}.json"
        trend_block = refresh_ad._trend_card(ctx, card_file) if t.get("source") == "trendsmesh" and card_file.is_file() \
            else None
        if trend_block:
            trend_block["chips"] = [{"text": _word(ctx, "type." + str(t.get("type")), t.get("type"))}] + \
                list(trend_block.get("chips") or [])
            blocks.append(trend_block)
            thumbs = _media(ctx, t.get("thumbs"))
            if thumbs:
                blocks.append({"kind": "media", "items": thumbs})
            continue
        chips = [{"text": _w(ctx, "type." + str(t.get("type"))) if t.get("type") in create_plan.TREND_TYPES
                  else str(t.get("type"))}]
        if t.get("source") == "guess" or guess:
            chips.append({"text": _w(ctx, "guess"), "style": "warn"})
        if t.get("licence"):
            chips.append({"text": _w(ctx, "licence." + str(t["licence"])) if t["licence"] in ("ads", "inspiration")
                          else str(t["licence"])})
        lines = [_w(ctx, "evidence", links=", ".join(map(str, t["evidence"])))] if t.get("evidence") else []
        plain.append({"title": str(tnames[t.get("id")]), "chips": chips, "lines": lines,
                      "media": _media(ctx, t.get("thumbs"))})
    if plain:
        blocks.append({"kind": "cards", "title": _w(ctx, "trends"), "items": plain})
    concepts = [c for c in data.get("concepts") or [] if isinstance(c, dict)]
    cards, keys = [], []
    best = str(concepts[0].get("key")) if concepts else None      # the recommended concept is listed first
    for c in concepts:
        key = str(c.get("key"))
        keys.append(key)
        cost = c.get("cost_usd") if isinstance(c.get("cost_usd"), list) and len(c["cost_usd"]) == 2 else None
        chips = [{"text": _w(ctx, "length", n=_secs(c.get("length_s"))), "style": "pink"}]
        if cost:
            chips.append({"text": _w(ctx, "cost_range", low=fmt(cost[0]), high=fmt(cost[1]))})
        beats = [{"t": b.get("t"), "picture": b.get("picture"), "line": b.get("line")}
                 for b in c.get("beats") or [] if isinstance(b, dict)]
        table = ctx.ds.add(f"{c.get('name')}: {_w(ctx, 'beats')}", src, [
            ("t", _w(ctx, "col.time"), "text"), ("picture", _w(ctx, "col.picture"), "text"),
            ("line", _w(ctx, "col.line"), "text")], beats)
        uses = _w(ctx, "uses", ad=names.get(c.get("model_ad"), c.get("model_ad")),
                  trends=", ".join(str(tnames.get(t, t)) for t in c.get("trends") or []))
        cards.append({"title": str(c.get("name") or key), "chips": chips,
                      "lines": [uses, _w(ctx, "combine", text=c.get("combine") or ""),
                                _w(ctx, "length_why", why=c.get("length_why") or "")],
                      "table": table,
                      "choose": {"path": ["concept"], "label": _w(ctx, "pick_concept"), "default": best,
                                 "options": [{"value": key, "label": _w(ctx, "pick_concept")}]}})
    if cards:
        blocks.append({"kind": "cards", "title": _w(ctx, "concepts"), "items": cards,
                       "offer": {"concept": {"type": "pick", "values": keys, "default": best}}})
    return blocks


# --- board and plan -------------------------------------------------------------------------------

def _source(ctx: Context, value: object) -> str:
    text = str(value or "")
    if text.startswith("asset:"):
        return _w(ctx, "source.asset", file=Path(text[len("asset:"):]).name)
    return _w(ctx, "source." + text) if text in ("generate", "site") else text


def _scenes(data: dict) -> list[dict]:
    return [s for s in data.get("scenes") or [] if isinstance(s, dict)]


def _scene_label(ctx: Context, n: int, sc: dict) -> str:
    return _w(ctx, "scene_named", n=n, name=sc["name"]) if sc.get("name") else _w(ctx, "scene", n=n)


def _board(ctx: Context) -> list[dict]:
    data, src = _checked(ctx, create_plan.BOARD)
    if data is None:
        return []
    scenes = _scenes(data)
    rows = [{"time": f"{_secs(sc.get('start'))}–{_secs(sc.get('end'))} s", "name": sc.get("name"),
             "picture": sc.get("picture"), "on_screen_text": sc.get("on_screen_text"), "line": sc.get("line"),
             "sound": sc.get("sound"), "source": _source(ctx, sc.get("source"))} for sc in scenes]
    words = sum(len(str(sc.get("line") or "").split()) for sc in scenes)
    length = scenes[-1].get("end") if scenes else None
    tiles = ctx.ds.add(_w(ctx, "board"), src, ctx.tile_columns(), [
        {"label": _w(ctx, "tile.length"), "value": length, "sticker": True},
        {"label": _w(ctx, "tile.scenes"), "value": len(scenes)},
        {"label": _w(ctx, "tile.words"), "value": words},
        {"label": _w(ctx, "tile.wpm"), "value": data.get("model_ad_wpm")}])
    table = ctx.ds.add(_w(ctx, "board"), src, [(k, _w(ctx, "col." + k), "text") for k in
                                              ("time", "name", "picture", "on_screen_text", "line", "sound", "source")],
                       rows)
    keys = [str(sc.get("n") or i) for i, sc in enumerate(scenes, 1)]
    notes = [{"path": ["scene_notes", k], "label": _scene_label(ctx, int(k) if k.isdigit() else i, sc)}
             for i, (k, sc) in enumerate(zip(keys, scenes), 1)]
    return [{"kind": "tiles", "data": tiles}, {"kind": "table", "title": _w(ctx, "board"), "data": table},
            {"kind": "notes", "summary": _w(ctx, "scene_notes"), "items": notes,
             "offer": {"scene_notes": {"type": "notes", "keys": keys}}}]


def _unit(ctx: Context, budget: object) -> str:
    return _w(ctx, "budget." + str(budget)) if budget in ("ai_usd", "voice_credits") else str(budget or "")


def _plan(ctx: Context) -> list[dict]:
    data, src = _checked(ctx, create_plan.PLAN)
    if data is None:
        return []
    lines = [ln for ln in data.get("lines") or [] if isinstance(ln, dict)]
    rows = [{"item": _readable(ln.get("item")), "type": _w(ctx, "type." + str(ln.get("type")))
             if str(ln.get("type")) in VISUAL_TYPES + AUDIO_TYPES + ("upscale", "transcription") else ln.get("type"),
             "stage": _w(ctx, "stage." + str(ln.get("stage"))) if ln.get("stage") in create_plan.STAGES else ln.get("stage"),
             "model": ln.get("model"), "cost": ln.get("cost"), "unit": _unit(ctx, ln.get("budget")),
             "checked": ln.get("checked"), "alternative": ln.get("alternative")} for ln in lines]

    def total(stage, budget):
        return round(sum(ln["cost"] for ln in lines if _num(ln.get("cost")) and (ln.get("stage") or "pre_video") == stage
                         and ln.get("budget") == budget), 4)
    tiles = [{"label": _w(ctx, "tile.pre_usd"), "value": total("pre_video", "ai_usd"), "sticker": True},
             {"label": _w(ctx, "tile.video_usd"), "value": total("video", "ai_usd")}]
    if any(ln.get("budget") == "voice_credits" for ln in lines):
        tiles.insert(1, {"label": _w(ctx, "tile.pre_credits"), "value": total("pre_video", "voice_credits")})
    route = data.get("voice_route")
    tiles.append({"label": _w(ctx, "tile.voice"), "value": _w(ctx, "route." + str(route))
                  if route in create_plan.VOICE_ROUTES else route})
    blocks = [{"kind": "tiles", "data": ctx.ds.add(_w(ctx, "plan"), src, ctx.tile_columns(), tiles)},
              {"kind": "table", "title": _w(ctx, "plan"), "data": ctx.ds.add(_w(ctx, "plan"), src, [
                  ("item", _w(ctx, "col.item"), "text"), ("type", _w(ctx, "col.type"), "text"),
                  ("stage", _w(ctx, "col.stage"), "text"), ("model", _w(ctx, "col.model"), "text"),
                  ("cost", _w(ctx, "col.cost"), "num"), ("unit", _w(ctx, "col.unit"), "text"),
                  ("checked", _w(ctx, "col.checked"), "text"), ("alternative", _w(ctx, "col.alternative"), "text")],
                  rows)}]
    inventory = ctx.latest(WIP, create_config.ASSETS_STEM, "json")
    assets = (ctx.json(inventory) or {}).get("assets") if inventory else None
    own = [_w(ctx, "replaces", file=Path(str(a.get("file"))).name, type=_w(ctx, "type." + str(a["replaces"]))
              if str(a["replaces"]) in VISUAL_TYPES + AUDIO_TYPES else _readable(a["replaces"]))
           for a in assets or [] if isinstance(a, dict) and a.get("usable") and a.get("replaces")]
    if own:
        blocks.append({"kind": "list", "title": _w(ctx, "own_files"), "items": own})
    blocks += _presenter(ctx, data, lines)
    keys = [str(ln.get("item")) for ln in lines if ln.get("item")]
    blocks.append({"kind": "notes", "summary": _w(ctx, "line_notes"),
                   "items": [{"path": ["line_notes", k], "label": _readable(k)} for k in keys],
                   "offer": {"line_notes": {"type": "notes", "keys": keys}}})
    return blocks


def _cents(usd: float) -> str:
    """A price in USD to the cent, rounded half up (1.575 is 1.58, as CA5's table writes it)."""
    return str(Decimal(str(usd)).quantize(Decimal("0.01"), ROUND_HALF_UP))


def _presenter(ctx: Context, data: dict, lines: list[dict]) -> list[dict]:
    """The talking person (issue #100): CA5's rows, the plan's situation first, each with its model, what it needs,
    its voice and today's price for a 15 s take (tm.create_presenter); a pick of the situation (`presenter`; the
    fallback only once the plan names it, after a review) and of the model (`presenter_model`: the row's own, or
    another of the table's). Nothing for a plan without a talking person."""
    if not any(ln.get("type") == "presenter" for ln in lines):
        return []
    rows = create_presenter.rows(ctx.run, data)
    current = create_presenter.situation_of(data)
    cards, values = [], []
    for row in rows:
        s, p = row["situation"], row["price"]
        chips = [{"text": _w(ctx, "presenter.plan_row"), "style": "pink"}] if row["plan"] else []
        chips.append({"text": _w(ctx, "presenter.usd", usd=_cents(p["usd"])) if p else _w(ctx, "presenter.no_price"),
                      "style": "" if p and not p["old_days"] else "warn"})
        out = [_w(ctx, "presenter.model", model=f"{create_presenter.MODELS[row['model']]} ({row['model']})"),
               _w(ctx, "presenter.needs_line", what=_w(ctx, f"presenter.needs.{s}")),
               _w(ctx, "presenter.voice_line", voice=_w(ctx, f"presenter.voice.{s}"))]
        if p:
            out.append(_w(ctx, "presenter.unit_price", price=f"{p['unit_price']:g}", unit=p["unit"], date=p["checked"]))
            if p["old_days"]:
                out.append(_wn(ctx, "presenter.old", p["old_days"], n=p["old_days"]))
        if row["plus"]:
            out.append(_w(ctx, "presenter.plus"))
        card = {"title": _w(ctx, f"presenter.situation.{s}"), "chips": chips, "lines": out}
        if s != create_presenter.FALLBACK or current == s:
            values.append(s)
            card["choose"] = {"path": ["presenter"], "label": _w(ctx, "presenter.pick"), "default": current,
                              "options": [{"value": s, "label": _w(ctx, "presenter.pick")}]}
        else:
            card["lines"].append(_w(ctx, "presenter.fallback_only"))
        cards.append(card)
    chosen = (data.get("presenter") or {}).get("model") if (data.get("presenter") or {}).get("user_choice") else None
    models = [create_presenter.ROW, *create_presenter.MODELS]
    pick_model = {"title": _w(ctx, "presenter.model_title"), "lines": [_w(ctx, "presenter.model_hint")],
                  "choose": {"path": ["presenter_model"], "label": _w(ctx, "presenter.model_title"),
                             "default": chosen if chosen in models else create_presenter.ROW,
                             "options": [{"value": m, "label": _w(ctx, "presenter.model_row") if m == create_presenter.ROW
                                          else create_presenter.MODELS[m]} for m in models]}}
    return [{"kind": "text", "title": _w(ctx, "presenter.title"), "text": _w(ctx, "presenter.hint")},
            {"kind": "cards", "items": cards,
             "offer": {"presenter": {"type": "pick", "values": values, "default": current}}},
            {"kind": "cards", "items": [pick_model],
             "offer": {"presenter_model": {"type": "pick", "values": models,
                                           "default": pick_model["choose"]["default"]}}}]


# --- the gates: visual, audio, takes --------------------------------------------------------------

def _outputs(ctx: Context, item: str) -> list[Path]:
    """A plan item's outputs: the media of its latest Replicate record (`03_wip/<item>_vNN.run.json`, the item's name
    as replicate_run's `--name` makes it), and its ElevenLabs takes `03_wip/audio/<item>_vNN.<ext>` (`--out`)."""
    stem = tools_common.stem_of(item)
    latest, _ = organic_specs.outputs(ctx.run, stem)
    found = [ctx.run.path / rel for rel in latest if Path(rel).suffix.lower() in MEDIA_EXT]
    audio = ctx.run.path / WIP / "audio"
    names = {re.escape(item), re.escape(stem)}
    pattern = re.compile(rf"^(?:{'|'.join(names)})_v\d+$")
    if audio.is_dir():
        found += [p for p in audio.iterdir() if p.is_file() and p.suffix.lower() in MEDIA_EXT and pattern.match(p.stem)]
    return sorted({p for p in found if p.is_file()}, key=lambda p: p.name)


def _transcript(ctx: Context, rel: object) -> str | None:
    data = ctx.json(ctx.inside(rel)) if isinstance(rel, str) else None
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("text"), str) and data["text"].strip():
        return data["text"].strip()
    text = " ".join(str(s.get("text", "")).strip() for s in data.get("segments") or [] if isinstance(s, dict))
    return text.strip() or None


def _qa(ctx: Context, rel: object) -> tuple[list[str], str | None, list[dict]]:
    """A take's QA file from tm tool take_qa (run-relative): its transcript line, its numbers as a dataset, and its
    contact sheet."""
    path = ctx.inside(rel) if isinstance(rel, str) else None
    qa = ctx.json(path)
    if not isinstance(qa, dict):
        return [], None, []
    lines = []
    said = _transcript(ctx, qa.get("transcript"))
    if said:
        lines.append(_w(ctx, "transcript", text=said))
    rows = [{"label": _w(ctx, "qa." + k), "value": qa.get(k)} for k in ("match", "wps", "lufs", "peak")
            if _num(qa.get(k))]
    if isinstance(qa.get("cuts"), list):
        rows.append({"label": _w(ctx, "qa.cuts"), "value": len(qa["cuts"])})
    did = ctx.ds.add(_w(ctx, "qa_title"), ctx.rel(path), ctx.tile_columns(), rows) if rows else None
    return lines, did, _media(ctx, qa.get("contact_sheet"))


def _qa_words(ctx: Context) -> i18n.Translator:
    """The translator create_qa writes the takes' fails and findings with: the page's language (its organic.qa words
    too), else English."""
    tr = i18n.translator(ctx.lang)
    return tr if not i18n.missing(ctx.lang, ("organic", "ad")) else i18n.translator(i18n.ENGLISH)


def _gate_items(ctx: Context, checkin: str) -> list[tuple[str, dict]]:
    """The items of the visual or audio gate, each with its plan line (the takes come from create_qa)."""
    data, _ = _checked(ctx, create_plan.PLAN)
    types = VISUAL_TYPES if checkin == "visual" else AUDIO_TYPES
    lines = [ln for ln in (data or {}).get("lines") or [] if isinstance(ln, dict) and ln.get("type") in types
             and (checkin == "audio" or (ln.get("stage") or "pre_video") == "pre_video")]
    return [(str(ln["item"]), ln) for ln in lines if ln.get("item")]


def _gate(checkin: str):
    def component(ctx: Context) -> list[dict]:
        cards, keys = [], []
        options = [{"value": c, "label": _w(ctx, "item." + c)} for c in ITEM_CHOICES]
        for item, line in _gate_items(ctx, checkin):
            outs = _outputs(ctx, item)
            for n, f in enumerate(outs, 1):
                key = f.stem
                served = ctx.put(ctx.rel(f))
                if not served:
                    continue
                keys.append(key)
                title = _w(ctx, "option", item=_readable(item), n=n) if len(outs) > 1 else _readable(item)
                chips = [{"text": line.get("model")}] if line.get("model") else []
                if _num(line.get("cost")):
                    chips.append({"text": f"{fmt(line['cost'])} {_unit(ctx, line.get('budget'))}"})
                lines, qa, sheet = _qa(ctx, ctx.rel(organic_qa.qa_file(ctx.run, f))) \
                    if organic_qa.qa_file(ctx.run, f) else ([], None, [])
                cards.append({"title": title, "chips": chips, "lines": lines,
                              "media": [{"src": served, "caption": f.name}] + sheet, "table": qa,
                              "choose": {"path": ["items", key], "label": title, "options": options,
                                         "default": ACCEPT}})
        if not cards:
            return [{"kind": "text", "text": _w(ctx, "nothing_yet")}]
        return [{"kind": "cards", "title": _w(ctx, "gate." + checkin), "items": cards,
                 "offer": {"items": {"type": "each", "keys": keys, "values": list(ITEM_CHOICES),
                                     "defaults": {k: ACCEPT for k in keys}}}}]
    return component


def _takes(ctx: Context) -> list[dict]:
    """The takes gate from create_qa.take_rows (the storyboard's videos, each take of its latest Replicate record):
    each take raw, its transcript, QA numbers and contact sheet, and the QA's fails and findings in the page's
    words."""
    lines_of = {str(v.get("item")): v for v in (_checked(ctx, create_plan.STORYBOARD)[0] or {}).get("videos") or []
                if isinstance(v, dict)}
    rows = [r for r in create_qa.take_rows(ctx.run, _qa_words(ctx)) if r.get("take")]
    per_item: dict[str, int] = {}
    for r in rows:
        per_item[r["item"]] = per_item.get(r["item"], 0) + 1
    cards, keys, seen, defaults = [], [], {}, {}
    options = [{"value": c, "label": _w(ctx, "item." + c)} for c in ITEM_CHOICES]
    for r in rows:
        served = ctx.put(r["take"])
        if not served:
            continue
        key = Path(r["take"]).stem
        keys.append(key)
        defaults[key] = REDO if r.get("fails") else ACCEPT      # a take that fails its QA: redo it
        seen[r["item"]] = seen.get(r["item"], 0) + 1
        title = _w(ctx, "option", item=_readable(r["item"]), n=seen[r["item"]]) if per_item[r["item"]] > 1 \
            else _readable(r["item"])
        line = lines_of.get(r["item"]) or {}
        chips = [{"text": line.get("model")}] if line.get("model") else []
        if _num(line.get("cost")):
            chips.append({"text": f"{fmt(line['cost'])} {_unit(ctx, line.get('budget'))}"})
        chips += [{"text": _w(ctx, "qa_fails"), "style": "warn"}] if r.get("fails") else []
        lines, qa, sheet = _qa(ctx, r.get("qa")) if r.get("qa") else ([_w(ctx, "qa_missing")], None, [])
        lines += [_w(ctx, "qa_fail", text=f) for f in r.get("fails") or []]
        lines += [_w(ctx, "qa_finding", text=f) for f in r.get("findings") or []]
        cards.append({"title": title, "chips": chips, "lines": lines,
                      "media": [{"src": served, "caption": Path(r["take"]).name}] + sheet, "table": qa,
                      "choose": {"path": ["items", key], "label": title, "options": options,
                                 "default": defaults[key]}})
    if not cards:
        return [{"kind": "text", "text": _w(ctx, "nothing_yet")}]
    return [{"kind": "cards", "title": _w(ctx, "gate.takes"), "items": cards,
             "offer": {"items": {"type": "each", "keys": keys, "values": list(ITEM_CHOICES), "defaults": defaults}}}]


# --- storyboard -----------------------------------------------------------------------------------

def _storyboard(ctx: Context) -> list[dict]:
    data, src = _checked(ctx, create_plan.STORYBOARD)
    if data is None:
        return []
    board, _ = _checked(ctx, create_plan.BOARD)
    scenes = _scenes(board or {})
    frames: dict[str, list] = {}
    for f in data.get("frames") or []:
        if isinstance(f, dict):
            frames.setdefault(str(f.get("scene")), []).append(f.get("file"))
    pages, keys = [], []
    for i, sc in enumerate(scenes, 1):
        key = str(sc.get("n") or i)
        keys.append(key)
        label = _scene_label(ctx, int(key) if key.isdigit() else i, sc)
        pages.append({"label": label, "media": _media(ctx, frames.get(key)), "rows": [
            (_w(ctx, "col.time"), f"{_secs(sc.get('start'))}–{_secs(sc.get('end'))} s"),
            (_w(ctx, "col.picture"), sc.get("picture")), (_w(ctx, "col.on_screen_text"), sc.get("on_screen_text")),
            (_w(ctx, "col.line"), sc.get("line")), (_w(ctx, "col.sound"), sc.get("sound")),
            (_w(ctx, "col.source"), _source(ctx, sc.get("source")))],
            "note": {"path": ["scene_notes", key], "label": _w(ctx, "scene_note")}})
    blocks = []
    if pages:
        blocks.append({"kind": "pager", "title": _w(ctx, "storyboard"), "scenes": pages, "label": _w(ctx, "storyboard"),
                       "prev": _w(ctx, "prev"), "next": _w(ctx, "next"), "keys": _w(ctx, "arrow_keys"),
                       "offer": {"scene_notes": {"type": "notes", "keys": keys}}})
    placeholder = _media(ctx, data.get("placeholder_render"))
    if placeholder:
        blocks.append({"kind": "media", "title": _w(ctx, "placeholder"), "items": placeholder})
    videos = [v for v in data.get("videos") or [] if isinstance(v, dict)]
    if videos:
        cards = []
        for v in videos:
            cards.append({"title": _readable(v.get("item")), "chips": [{"text": str(v.get("model") or "")}],
                          "lines": [_w(ctx, "price", cost=fmt(v.get("cost")), unit=_unit(ctx, v.get("budget")),
                                       date=v.get("checked") or "—"),
                                    *([_w(ctx, "prompt_rules", file=v["prompt_rules"])] if v.get("prompt_rules") else [])],
                          "pre": str(v.get("prompt") or "")})
        total = sum(v["cost"] for v in videos if _num(v.get("cost")) and v.get("budget") == "ai_usd")
        blocks.append({"kind": "tiles", "data": ctx.ds.add(_w(ctx, "videos"), src, ctx.tile_columns(), [
            {"label": _w(ctx, "tile.video_usd"), "value": round(total, 4), "sticker": True}])})
        blocks.append({"kind": "cards", "title": _w(ctx, "videos"), "items": cards, "wide": True})
    elif data.get("no_video_reason"):
        blocks.append({"kind": "text", "text": _w(ctx, "no_video", why=data["no_video_reason"])})
    return blocks


# --- review ---------------------------------------------------------------------------------------

def _versions(ctx: Context) -> list[Path]:
    folder = ctx.run.path / WIP
    found = [p for p in folder.glob("edit_v*.mp4") if re.fullmatch(r"edit_v\d+", p.stem)] if folder.is_dir() else []
    return sorted(found, key=lambda p: int(p.stem.split("_v")[1]))[-REVIEW_VERSIONS:]


def _review(ctx: Context) -> list[dict]:
    items, keys = [], []
    for f in _versions(ctx):
        served = ctx.put(ctx.rel(f))
        if not served:
            continue
        n = int(f.stem.split("_v")[1])
        label = _w(ctx, "version", n=n)
        keys.append(f.stem)
        items.append({"key": f.stem, "label": label, "src": served, "caption": ""})
    if not items:
        return [{"kind": "text", "text": _w(ctx, "no_version")}]
    report = create_qa.edit_report(ctx.run, i18n.translator(ctx.lang))
    checked = Path(str((report or {}).get("edit") or "")).stem
    best = checked if checked in keys else keys[-1]        # the checked edit, else the latest version
    blocks = [{"kind": "versions", "title": _w(ctx, "versions"), "items": items,
               "pick": {"path": ["version"], "label": _w(ctx, "pick_version"), "default": best},
               "pins": {"path": ["pins"], "label": _w(ctx, "pin_label"), "button": _w(ctx, "pin_button"),
                        "heading": _w(ctx, "pins"), "empty": _w(ctx, "no_pins")},
               "offer": {"version": {"type": "pick", "values": keys, "default": best},
                         "pins": {"type": "pins", "versions": keys}}}]
    return blocks + _checked_edit(ctx)


def _checked_edit(ctx: Context) -> list[dict]:
    """What was checked (S7), from create_qa.edit_report: the checked edit's loudness, true peak and transcript match,
    and each CA11 check with its result and note."""
    report = create_qa.edit_report(ctx.run, i18n.translator(ctx.lang))
    if not report:
        return []
    src = ctx.rel(create_plan.checked_file(ctx.run, create_plan.EDIT_QA))
    edit = str(report.get("edit") or "")
    version = _w(ctx, "version", n=int(Path(edit).stem.split("_v")[1])) if "_v" in edit else edit
    tiles = [{"label": _w(ctx, "qa." + k), "value": report.get(k)} for k in ("lufs", "peak", "match")
             if _num(report.get(k))]
    rows = [{"check": r["label"], "result": r["result_label"], "note": r.get("note")} for r in report["checked"]]
    blocks = [{"kind": "text", "text": f"**{report['title']}: {version}**"}]
    if tiles:
        blocks.append({"kind": "tiles", "data": ctx.ds.add(report["title"], report.get("qa") or src,
                                                           ctx.tile_columns(), tiles)})
    if rows:
        blocks.append({"kind": "table", "data": ctx.ds.add(report["title"], src, [
            ("check", _w(ctx, "col.check"), "text"), ("result", _w(ctx, "col.result"), "text"),
            ("note", _w(ctx, "col.note"), "text")], rows)})
    return blocks


# --- copy -----------------------------------------------------------------------------------------

FACTS = ("ad_name", "video_title", "cta", "display_link", "url")
LIST_WORDS = {"primary_texts": "ad.copy.primary", "headlines": "ad.copy.headline", "descriptions": "ad.copy.description"}


def _copy(ctx: Context) -> list[dict]:
    try:
        data = create_copy.page_data(ctx.run)
    except (OSError, ValueError):
        return []
    if not data.get("ads"):
        return []
    draft = ctx.latest(WIP, create_copy.DRAFT, "json")
    ads, offer = [], {}
    for ad in data["ads"]:
        key = str(ad["key"])
        lists = []
        for field, words in LIST_WORDS.items():
            got = ad.get(field) or {}
            items = [{"n": it["n"], "text": it["text"], "count": it["count"],
                      "path": ["copy", key, field, str(it["n"])]} for it in got.get("items") or []]
            limit = (got.get("items") or [{}])[0].get("limit") if got.get("items") else None
            if items:
                lists.append({"name": field, "label": tx(words, ctx.lang), "limit": limit, "items": items,
                              "count": plural("ad.copy.count", limit, ctx.lang),
                              "over": plural("ad.copy.over", limit, ctx.lang)})
                offer.setdefault(key, {})[field] = len(items)
        facts = [(_w(ctx, "fact." + k), (ad.get("facts") or {}).get(k)) for k in FACTS]
        ads.append({"key": key, "title": (ad.get("facts") or {}).get("ad_name") or key, "facts": facts, "lists": lists})
    return [{"kind": "copy", "title": tx("ad.copy.title", ctx.lang), "ads": ads, "keep": tx("ad.copy.keep", ctx.lang),
             "source": ctx.rel(draft) if draft else "", "offer": {"copy": {"type": "copy", "ads": offer}}}]


# --- upload ---------------------------------------------------------------------------------------

def _files(ctx: Context, ads) -> list[dict]:
    out = []
    for ad in ads or []:
        if not isinstance(ad, dict):
            continue
        out += _media(ctx, [{"file": ad.get("video"), "caption": str(ad.get("key") or "")},
                            {"file": ad.get("thumbnail"), "caption": str(ad.get("key") or "")}])
    return out


def _delivered(ctx: Context) -> list[dict]:
    """The final files of the accepted copy's ads (04_final/<key>_vNN.mp4 and its thumbnail)."""
    try:
        copy = create_copy.accepted(ctx.run)
    except (OSError, ValueError):
        copy = None
    ads = []
    for ad in (copy or {}).get("ads") or []:
        key = ad.get("key")
        video = ctx.latest("04_final", key, "mp4")
        thumb = next((p for p in (ctx.latest("04_final", f"{key}_thumb", e) for e in ("jpg", "png")) if p), None)
        ads.append({"key": key, "video": ctx.rel(video) if video else None, "thumbnail": ctx.rel(thumb) if thumb else None})
    return ads


def _upload_offer(ctx: Context) -> list[dict]:
    blocks = [{"kind": "text", "text": "**" + tx("ad.upload.paused_note", ctx.lang) + "**"}]
    files = _files(ctx, _delivered(ctx))
    if files:
        blocks.append({"kind": "media", "title": _w(ctx, "upload.files"), "items": files})
    return blocks


def _copy_lines(ctx: Context, copy: dict | None) -> list[dict]:
    cards = []
    for ad in (copy or {}).get("ads") or []:
        lines = []
        for field, words in LIST_WORDS.items():
            for it in ad.get(field) or []:
                if isinstance(it, dict) and it.get("text"):
                    lines.append(f"{tx(words, ctx.lang)}: {it['text']}")
        cards.append({"title": str(ad.get("ad_name") or ad.get("key")), "lines": lines})
    return [{"kind": "cards", "title": _w(ctx, "upload.copy"), "items": cards}] if cards else []


def _upload(ctx: Context) -> list[dict]:
    try:
        card = create_upload.card(ctx.run)
    except (OSError, ValueError):
        return []
    if not card.get("ad_account_id"):
        return _upload_offer(ctx)
    names = card.get("names") or {}
    budget = card.get("budget") or {}
    cadence = budget.get("cadence")
    said = lambda d: _w(ctx, "upload.said", said=d["said"]) if isinstance(d, dict) and d.get("said") else ""
    ai = (card.get("ai_disclosure") or {})
    rows = [(_w(ctx, "upload.account"), card.get("ad_account_id")), (_w(ctx, "upload.page"), card.get("page_id")),
            (_w(ctx, "upload.campaign"), names.get("campaign")), (_w(ctx, "upload.adset"), names.get("adset")),
            *((_w(ctx, "upload.ad", ad=k), v) for k, v in (names.get("ads") or {}).items()),
            (_w(ctx, "upload.objective"), card.get("objective")), (_w(ctx, "upload.event"), card.get("event")),
            (_w(ctx, "upload.why"), card.get("why")),
            (_w(ctx, "upload.budget"), " ".join(x for x in (
                _w(ctx, "upload.budget_value", amount=fmt(budget.get("amount")), currency=budget.get("currency") or "",
                   cadence=_w(ctx, "cadence." + cadence) if cadence in ("daily", "lifetime") else cadence or ""),
                said(budget)) if x)),
            (_w(ctx, "upload.countries"), ", ".join(map(str, card.get("country") or []))),
            (_w(ctx, "upload.audience"), card.get("audience")), (_w(ctx, "upload.placements"), card.get("placements")),
            (_w(ctx, "upload.ai"), " ".join(x for x in (_w(ctx, "ai." + ai["value"]) if ai.get("value") in
                                                         ("OPT_IN", "OPT_OUT") else ai.get("value") or "", said(ai)) if x)),
            (_w(ctx, "upload.status"), card.get("status"))]
    proposal = ctx.latest(create_upload.RESULTS, create_upload.PROPOSAL, "json")
    blocks = [{"kind": "text", "text": "**" + str(card.get("paused_note") or "") + "**"},
              {"kind": "facts", "title": card.get("title"), "rows": rows,
               "source": ctx.rel(proposal) if proposal else ""}]
    if card.get("pixel_notes"):
        blocks.append({"kind": "list", "items": card["pixel_notes"]})
    files = _files(ctx, card.get("ads"))
    if files:
        blocks.append({"kind": "media", "title": _w(ctx, "upload.files"), "items": files})
    blocks += _copy_lines(ctx, card.get("copy"))
    if card.get("facts"):
        blocks.append({"kind": "list", "title": _w(ctx, "upload.placement_facts"), "items": card["facts"]})
    return blocks


# --- the check-ins --------------------------------------------------------------------------------

COMPONENTS = {"concept": (_concept,), "board": (_board,), "plan": (_plan,), "visual": (_gate("visual"),),
              "audio": (_gate("audio"),), "takes": (_takes,), "storyboard": (_storyboard,),
              "review": (_review,), "copy": (_copy,), "upload_offer": (_upload_offer,), "upload": (_upload,)}


def materials(ctx: Context, checkin: str) -> list[dict]:
    """The blocks the check-in's stage shows from the run's files (none for a check-in without a component)."""
    out: list[dict] = []
    for part in COMPONENTS.get(checkin, ()):
        out += part(ctx)
    return out


def outcome(ctx: Context, checkin: str, choice: object) -> str | None:
    return None


# --- a choice saved on the page, recorded ---------------------------------------------------------

def _clock(t: float) -> str:
    m = int(t // 60)
    return f"{m}:{t - m * 60:04.1f}"


def _edited_copy(run: RunFolder, detail: dict) -> tuple[list[dict], int, int] | None:
    """The draft's texts with the page's edits and ticks (create_copy's choices format), how many were edited and
    how many dropped; None without a checked draft."""
    draft = create_copy.draft(run)
    if draft is None:
        return None
    edited = detail.get("copy") or {}
    out_ads, changed, dropped = [], 0, 0
    for ad in draft.get("ads") or []:
        mine = edited.get(str(ad["key"])) or {}
        row = {"key": ad["key"]}
        for field in LIST_WORDS:
            row[field] = []
            for n, it in enumerate(ad.get(field) or [], 1):
                saved = (mine.get(field) or {}).get(str(n)) or {}
                text = saved["text"] if isinstance(saved.get("text"), str) and saved["text"].strip() else it["text"]
                keep = saved.get("keep", True) is not False
                changed += text != it["text"]
                dropped += not keep
                row[field].append({"n": n, "text": text, "keep": keep})
        out_ads.append(row)
    return out_ads, changed, dropped


def note_lines(run: RunFolder, checkin: str, got: dict, lang: str) -> list[str]:
    """The lines a choice saved on the page adds to its recorded note (in the page's language): the concept picked,
    each item's choice, the notes per scene or line, the version picked and the pinned notes, the copy's edits."""
    detail = got.get("detail") or {}
    lines = []
    if detail.get("concept"):
        data = create_plan.checked(run, create_plan.CONCEPTS) or {}
        name = next((c.get("name") for c in data.get("concepts") or [] if isinstance(c, dict)
                     and str(c.get("key")) == detail["concept"]), detail["concept"])
        lines.append(_w(lang, "rec.concept", name=name))
    for key, choice in (detail.get("items") or {}).items():
        lines.append(_w(lang, "rec.item", item=key, choice=_w(lang, "item." + choice)))
    for key, text in (detail.get("scene_notes") or {}).items():
        lines.append(_w(lang, "rec.scene", n=key, text=text))
    for key, text in (detail.get("line_notes") or {}).items():
        lines.append(_w(lang, "rec.line", item=_readable(key), text=text))
    if detail.get("version"):
        lines.append(_w(lang, "rec.version", name=_w(lang, "version", n=int(detail["version"].split("_v")[1]))))
    for pin in detail.get("pins") or []:
        lines.append(_w(lang, "rec.pin", version=_w(lang, "version", n=int(pin["version"].split("_v")[1])),
                        time=_clock(pin["t"]), text=pin["text"]))
    if detail.get("presenter"):
        situation, model = detail["presenter"], detail.get("presenter_model")
        own = create_presenter.is_rows_model(situation, model)
        name = create_presenter.MODELS.get(create_presenter.ROWS[situation]["model"] if own else model, model)
        said = _w(lang, f"presenter.situation.{situation}")
        lines.append(_w(lang, "rec.presenter", situation=said, model=name) if own
                     else _w(lang, "rec.presenter_choice", situation=said, model=name))
    if checkin == "copy":
        edited = _edited_copy(run, detail)
        if edited and (edited[1] or edited[2]):
            lines.append(_w(lang, "rec.copy", edited=edited[1], dropped=edited[2]))
    return lines


def write_files(run: RunFolder, checkin: str, got: dict) -> dict:
    """The files a recorded choice writes: the copy as the user left it on the page, as
    `03_wip/copy_decisions_vNN.json` (create_copy's choices: per ad, per list, `{n, text, keep}`), for `tm ad copy
    accept`, which checks it again; and the plan's talking person picked on the page (not on a reject), as the next
    `production_plan_vNN.json` when it changes the plan (`files["plan"]`), for `tm ad check plan`. Nothing else is
    acted on."""
    if checkin in ("plan", "board_and_plan"):
        detail = got.get("detail") or {}
        if not detail.get("presenter") or got.get("choice") == "reject":
            return {}
        rel = create_presenter.record(run, detail["presenter"], detail.get("presenter_model"))
        return {"plan": rel} if rel else {}
    if checkin != "copy":
        return {}
    edited = _edited_copy(run, got.get("detail") or {})
    if edited is None:
        return {}
    target = run.next_version(WIP, create_copy.DECISIONS, "json")
    run.assert_writable(target)
    target.write_text(json.dumps({"ads": edited[0], "note": got.get("note") or None, "from": "the run page"},
                                 ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rel = target.relative_to(run.path).as_posix()
    manifest.record(run, rel, "03_wip", "tm page decision --record")
    return {"copy_decisions": rel}
