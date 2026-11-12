"""Organic video's check-in pages (F1 images, F2 takes) and its delivery page with every step (G4, OV9 and OV12):
their data, the decisions taken on them, and the `final_page_built` step check.

    gate_json(run, gate)        the images or video check-in page's data (`tm organic page gate --gate …`)
    delivery_json(run)          the delivery page's data, gate `edit` (`tm organic page delivery`)
    take_decisions(run, page, *, file, text, keep_carried)   03_wip/decisions_<page>_vNN.json
    delivery_gap(run)           the step check `final_page_built` (G4)

The week's delivery page (`week_delivery`, `tm.organic_week_delivery`) is read by the same `take_decisions`: each of
its items names its slot run (`plugin.items[id].run`), so a redo becomes the user's request in that run (keyed as its
own delivery page's, `delivery:<stem>`), and a video's ticks a new kit version there.

The pages are `gate_images`, `gate_video` and `delivery` (drift check 26); `tm.organic_pages.gate` builds them from
this data (the handoff's `gate.schema.json`) and their db collections are `gate_images`, `gate_video` and `gate_edit`.
Every label is in the language the page is built in (`organic_pages.gate_words`, of `organic_pages.lang_of` the
pack: its `lang` when that language's table is translated, else English); the data's `lang` is the pack's. The data's `plugin`
block (not shown) ties each item to the run: `{page, pack, final, kit, items: {item id: {kind, name, stem, files:
{option id: run-relative file}}}, missing_thumbnails}`.

The check-in pages: one item per item of the checked pack the stage makes (`organic_qa`'s image or video items),
id `images-<stem>` or `takes-<stem>` (`item_id`: ASCII letters, digits, '_' and '-' only). Its options are every output of the item's done Replicate records (an image),
or each take, shown by its 720p preview (`showcase/<take stem>_720p.mp4`, `tm tool deliver preview`) when there is
one, captioned with its QA findings (`organic_qa.rubric_takes` on its latest QA). An output whose file is gone is
left out. The item's current pick (`organic_qa.picks` and `current`) is marked. Its refs are the product's
packshots, the host image (beside the items that did not make it) and the thumbnails of the style spec's evidence
videos (named by their URLs, found among the saved videos of the idea's trends, fetched once into
`03_wip/gates/thumbs/`; one that cannot be had is listed in `missing_thumbnails`), followed on the images page by the
latest still of the pack's composition (`tm render still`, in 03_wip, after the latest pack check; `compositions`),
so the copied look is judged beside its evidence before the render (OV3, lesson 21); a take's item also shows the QA contact sheet of its picked (else latest) take.
An animation's storyboard check-in is on the images page: each animated item's latest storyboard sheet (its accept
is the storyboard's pick, `organic_qa`), with the voiceover beside it to listen to; the video page shows each animated
item's animation renders (`03_wip/<item>/renders/anim_vNN.mp4`), the latest marked, and each stills item's
motion-graphics renders (`organic_qa.motion_renders`), the one F2 and the edit take marked: the user's accept there is
that choice (`organic_qa.chosen_motion`).

The delivery page: first the final (`final`): the latest `04_final/<id>_final_vNN.mp4` shown by its preview, with
its upload copy to download; the cover JPG to download; the latest posting kit, with the platform ticks and the
YouTube-thumbnail tick. Then every step that made it: the images (the pick marked, the others beside it), the raw
takes with their QA findings, each stills item's motion-graphics renders (the one F2 took marked, OV9), the voiceover
(ElevenLabs takes in the manifest), the storyboard (the latest
`03_wip/<item>/storyboard_vNN/sheet.png` of each item). Each item has Accept / Redo with a note / Drop.

Decisions. `take_decisions` reads the page's newest saved db answer, whole and fresh (`page.saved_answer`,
`page.whole_answer`, `page.db_docs`, the page's collection), or the user's words in chat (`--text`, one line per
item: `<item id>: accept|redo|drop|not decided[; choice: <option id>][; platforms: tiktok, youtube][; thumbnail:
yes|no][; note: <their words>]`), into

    03_wip/decisions_<page>_vNN.json = {page, collection, folder, data, from, slug, at, source, keep_carried,
        decisions: {item id: {kind, name, stem, action, choice, file, note[, platforms, thumbnail][, carried]}},
        read: {item id: document}, carried: [item id, ...], redos: [stem, ...], kit}

Everything is checked first; then the decisions file is written, then the requests and the new kit (so a file named
in the decisions file is never a request or kit that was not made because of a later Stop).

A row equal to the one the latest decisions file of another page build read is `carried` (`page.mark_carried`);
a row from chat never is. A carried redo or accept is not acted on unless `keep_carried` (the user said so in chat):
- each redo that is acted on becomes a request in run.json `organic.redos[<stem>]` (`{kind: "request", note, by:
  "user", at, after, page}`, `after` the item's latest Replicate record, else its file), once per note and take; a
  redo of what the pack does not generate (the final, the voiceover, a storyboard, an animation, a motion-graphics
  render) under `<page>:<stem>` (`delivery:`, `gate_video:`, ...), a key no pack item has, so the generation guard
  never reads it as an item's request, and the message names it by its label on that page (Task 19 review M5):
  what the generation guard (`tm.organic_specs`) lets run once. Its note is the user's words, kept as data: it
  is never read as an instruction to the engine;
- an accept on the images page is that image's pick (`organic_specs.page_image_rows`);
- on the delivery page, the final's unticked platforms (and its YouTube-thumbnail tick) are written into a new
  version of the posting kit: its platform blocks and `plugin.platforms`. The new kit is checked with `tm kit check`
  before it is posted.
"""

from __future__ import annotations

import copy
import json
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

from tm import (flow, i18n, kit, manifest, organic_final, organic_pack, organic_qa, organic_specs, page, render,
                runfolder, state, stepchecks, trend_spool, trends)
from tm.organic_pages import gate_words, lang_of
from tm.organic_pages import gate as gate_page
from tm.r2 import run_config
from tm.review import VIDEO_EXT
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop
from tm.tools import _common as c

WIP = "03_wip"
SHOWCASE = "showcase"
THUMBS = f"{gate_page.DATA}/thumbs"
GATES = {"images": "gate_images", "video": "gate_video"}           # the original gate -> the check-in page
TTS = "ElevenLabs text to speech"                                  # the manifest source of a voiceover take
STORYBOARD = organic_qa.BOARD                                     # 03_wip/<item>/storyboard_vNN/
ACTIONS = ("accept", "redo", "drop")
DECISIONS_SOURCE = "tm organic decisions"
DELIVERY = "delivery"
READ_WITH = gate_page.READ_WITH


def _ui(lang: str) -> dict:
    return gate_words(lang)


def _rel(run: RunFolder, path: Path) -> str:
    return c.rel(run, path)


def _run_ref(run: RunFolder) -> str:
    """The run as the reference pages name it: `runs/<playbook>/<run>`, from the workspace."""
    try:
        return run.path.resolve().relative_to(trend_spool.workspace_of(run).resolve()).as_posix()
    except ValueError:
        return run.path.name


def _pack(run: RunFolder) -> dict:
    return organic_qa._pack(run)


def _option_id(file: str, taken: dict) -> str:
    """The option's id: the file's stem, made unique within its item."""
    base = Path(file).stem
    oid, n = base, 1
    while oid in taken:
        n += 1
        oid = f"{base}_{n}"
    return oid


def item_id(text: str, taken: set[str]) -> str:
    """A page item's id from `text`: ASCII letters, digits, '_' and '-' only (accents and other non-ASCII letters
    dropped, anything else '-'), since the page's script puts it into CSS selectors and element ids (Task 17 M7);
    made unique among `taken`, which it joins. The plugin block ties the id to its item, so the id is never read back as a name."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^A-Za-z0-9_-]", "-", plain) or "item"
    iid, n = base, 1
    while iid in taken:
        n += 1
        iid = f"{base}-{n}"
    taken.add(iid)
    return iid


def _made(run: RunFolder, stem: str, suffixes) -> list[str]:
    """Every output of the item's done records that is still there, run-relative, oldest first."""
    out = []
    for _, record in organic_specs.records(run, stem):
        if record.get("status") != organic_specs.DONE:
            continue
        for name in record.get("outputs") or []:
            rel = f"{WIP}/{name}"
            if (isinstance(name, str) and Path(name).suffix.lower() in suffixes and (run.path / rel).is_file()
                    and rel not in out):
                out.append(rel)
    return out


def _preview(run: RunFolder, file: str) -> str:
    """The 720p preview of a video (`showcase/<stem>_720p.mp4`) when it is made, else the video."""
    preview = f"{SHOWCASE}/{Path(file).stem}_720p.mp4"
    return preview if (run.path / preview).is_file() else file


def _current(run: RunFolder, stage: str) -> dict[str, str]:
    """Each item's current pick at `stage` (stem -> file), the picks that count only."""
    checked = organic_specs.checked_at(run)
    return {stem: row["file"] for stem, row in organic_qa.picks(run, stage).items()
            if organic_qa.current(run, row, checked_at=checked) is None}


def _qa(run: RunFolder, take: str, pack: dict, t: dict) -> tuple[str, str | None]:
    """(the take's QA findings in words, its contact sheet when it is there)."""
    path = organic_qa.qa_file(run, run.path / take)
    if path is None:
        return t["qa_none"], None
    qa = organic_qa.read_qa(run, path)
    found = organic_qa.rubric_words(qa, run_config(run), lang_of(pack), speech=organic_qa.speaks(pack))
    words = [t["qa_fails"].format(fails="; ".join(found["fails"])) if found["fails"] else t["qa_pass"]]
    if found["findings"]:
        words.append(t["qa_findings"].format(findings="; ".join(found["findings"])))
    sheet = qa.get("contact_sheet")
    sheet = sheet.replace("\\", "/") if isinstance(sheet, str) else None
    return " · ".join(words), sheet if sheet and (run.path / sheet).is_file() else None


def _evidence(run: RunFolder, pack: dict, t: dict) -> tuple[list[dict], list[str]]:
    """The style spec's evidence videos as refs (their thumbnails), and the ones that could not be had."""
    refs, missing = [], []
    spec = pack.get("style_spec") or {}
    urls = [u.strip() for u in spec.get("evidence") or [] if isinstance(u, str) and u.strip()]
    if not urls:
        return refs, missing
    saved, _ = organic_pack.evidence_videos(run, organic_pack.idea_of(run))
    for url in dict.fromkeys(urls):
        video = saved.get(url)
        aid = video.get("asset_id") if video else None
        if not (isinstance(aid, str) and aid):
            missing.append(url)
            continue
        dest = run.path / THUMBS / page.asset_name(f"{aid}.jpg")
        if page.fetch_image(video.get("thumbnail_url"), dest):
            refs.append({"src": _rel(run, dest), "caption": t["cap_evidence"].format(
                creator=trends.creator_of(video) or "?")})
        else:
            missing.append(aid)
    return refs, missing


def _refs(run: RunFolder, pack: dict, t: dict) -> tuple[list[dict], list[str]]:
    """The refs beside every item: the packshots, the host image, the evidence thumbnails."""
    workspace = trend_spool.workspace_of(run)
    refs = [{"src": str((workspace / shot).resolve()), "caption": t["cap_packshot"]}
            for shot in pack["product"]["packshots"] if (workspace / shot).is_file()]
    host = pack["host"].get("image")
    if isinstance(host, str) and (run.path / host).is_file():
        refs.append({"src": host.replace("\\", "/"), "caption": t["cap_host"]})
    shown, missing = _evidence(run, pack, t)
    return refs + shown, missing


def compositions(pack: dict) -> tuple[str, ...]:
    """The compositions the pack's video is drawn with: the motion graphics of its stills, OrganicCaptions' edit for
    the rest."""
    return ((render.MOTION_COMPS if organic_pack.stills(pack) else ())
            + (("OrganicCaptions",) if pack["production"] != "stills_motion" else ()))


def _still(run: RunFolder, pack: dict, t: dict) -> dict | None:
    """The latest still of one of the pack's `compositions`, made in 03_wip (`tm render still`; a cover is made in
    04_final) after the latest pack check (its `made_under.at`, PR D review M4), as a ref."""
    checked = organic_specs.checked_at(run)
    for row in reversed(manifest.rows(run)):
        if (row["model"] != "remotion still" or not row["file"].startswith(f"{WIP}/")
                or not (run.path / row["file"]).is_file()):
            continue
        try:
            params = json.loads(row["params"]) if row["params"] else {}
        except ValueError:
            params = {}
        params = params if isinstance(params, dict) else {}
        under = params.get("made_under") if isinstance(params.get("made_under"), dict) else {}
        made = organic_specs.when(under.get("at"))
        if (params.get("composition") not in compositions(pack) or made is None
                or (checked is not None and made < checked)):
            continue
        return {"src": row["file"], "caption": t["cap_still"].format(comp=params["composition"],
                                                                     frame=params.get("frame", "?"))}
    return None


def _stage_items(run: RunFolder, pack: dict, t: dict, *, video: bool, refs: list[dict]) -> tuple[list, dict]:
    """The items of one stage (the images or the takes): (page items, their plugin entries). An item with nothing
    made is left out."""
    stage = organic_qa.TAKES if video else organic_qa.IMAGES
    kind = "takes" if video else "images"
    picks = _current(run, stage)
    items, plugin = [], {}
    taken: set[str] = set()
    for item in organic_qa._wanted(pack, video):
        stem = c.stem_of(item["name"])
        files = _made(run, stem, VIDEO_EXT if video else organic_specs.IMAGE_SUFFIXES)
        if not files:
            continue
        ids: dict[str, str] = {}
        options, sheets = [], {}
        for f in files:
            oid = _option_id(f, ids)
            ids[oid] = f
            option = {"id": oid, "src": f, "caption": Path(f).stem}
            if video:
                words, sheets[f] = _qa(run, f, pack, t)
                option = {**option, "src": _preview(run, f), "caption": f"{Path(f).stem} · {words}"}
            if picks.get(stem) == f:
                option["pick"] = True
            options.append(option)
        shown = [r for r in refs if r["src"] not in files]
        if video:
            take = picks.get(stem) or files[-1]
            if sheets.get(take):
                shown.append({"src": sheets[take], "caption": t["cap_contact"].format(take=Path(take).stem)})
        iid = item_id(f"{kind}-{stem}", taken)
        items.append({"id": iid, "proposal": t["proposal"].format(id=pack["id"], channel=pack["channel"]),
                      "label": t[f"label_{kind}"].format(name=item["name"]),
                      "question": t[f"q_{kind}"].format(name=item["name"]), "options": options, "refs": shown})
        plugin[iid] = {"kind": kind, "name": item["name"], "stem": stem, "files": ids}
    return items, plugin


def _data(run: RunFolder, pack: dict, gate: str, items: list, plugin: dict) -> dict:
    t = _ui(lang_of(pack))
    # the data's lang is the run's working language (the pack's): the page build says when its table is missing
    lang = i18n.tag(pack.get("lang")) or i18n.ENGLISH
    return {"lang": lang, "title": t[f"title_{gate}"].format(title=pack["title"]), "run": _run_ref(run),
            "gate": gate, "date": date.today().isoformat(), "lede": t[f"lede_{gate}"], "items": items,
            "plugin": plugin}


def _animations(run: RunFolder, pack: dict, t: dict) -> tuple[list, dict]:
    """Each animated item's renders, `03_wip/<item>/renders/anim_vNN.mp4`, the latest marked."""
    items, plugin = [], {}
    taken: set[str] = set()
    for item in organic_pack.animated(pack):
        stage = f"{WIP}/{item}/renders"
        latest = run.latest(stage, organic_qa.ANIM, "mp4")
        if latest is None:
            continue
        version = re.compile(rf"{organic_qa.ANIM}_v(\d+)\.mp4", re.IGNORECASE)   # any case, on every system (M6)
        found = ((version.fullmatch(p.name), p) for p in latest.parent.iterdir() if p.is_file())
        files = [p for _, p in sorted((int(m.group(1)), p) for m, p in found if m)]
        ids: dict[str, str] = {}
        options = []
        for f in files:
            rel = _rel(run, f)
            oid = _option_id(rel, ids)
            ids[oid] = rel
            options.append({"id": oid, "src": _preview(run, rel), "caption": f"{item}/{f.stem}",
                            **({"pick": True} if f == latest else {})})
        iid = item_id(f"animation-{item}", taken)
        items.append({"id": iid, "proposal": t["proposal"].format(id=pack["id"], channel=pack["channel"]),
                      "label": t["label_animation"].format(name=item), "question": t["q_animation"],
                      "options": options})
        plugin[iid] = {"kind": "animation", "name": item, "stem": f"{item}_animation", "files": ids}
    return items, plugin


def _motions(run: RunFolder, pack: dict, t: dict) -> tuple[list, dict]:
    """The stills' motion-graphics renders (one item per stills item of the pack), the one F2 and the edit take
    marked (`organic_qa.chosen_motion`: the user's choice, else the latest)."""
    files = [f for f, *_ in organic_qa.motion_renders(run)]
    items, plugin = [], {}
    if not files:
        return items, plugin
    taken: set[str] = set()
    for item in organic_pack.stills(pack):
        ids: dict[str, str] = {}
        options = []
        marked = organic_qa.chosen_motion(run, item)[0]
        for f in files:
            oid = _option_id(f, ids)
            ids[oid] = f
            options.append({"id": oid, "src": _preview(run, f), "caption": Path(f).stem,
                            **({"pick": True} if f == marked else {})})
        iid = item_id(f"motion-{item}", taken)
        items.append({"id": iid, "proposal": t["proposal"].format(id=pack["id"], channel=pack["channel"]),
                      "label": t["label_motion"].format(name=item), "question": t["q_motion"], "options": options})
        plugin[iid] = {"kind": "motion", "name": item, "stem": f"{item}_motion", "files": ids}
    return items, plugin


def gate_json(run: RunFolder, gate: str) -> dict:
    """The data of the images or video check-in page (the module docstring). A Stop without a checked pack or with
    nothing made at that stage yet."""
    if gate not in GATES:
        raise ValueError(f"The check-in pages are {', '.join(GATES)}, not {gate!r}.")
    pack = _pack(run)
    t = _ui(lang_of(pack))
    refs, missing = _refs(run, pack, t)
    still = _still(run, pack, t) if gate == "images" and pack.get("style_spec") else None
    items, plugin = _stage_items(run, pack, t, video=gate == "video", refs=refs + ([still] if still else []))
    if gate == "video" and organic_pack.stills(pack):
        extra, entries = _motions(run, pack, t)
        items += extra
        plugin.update(entries)
    animated = organic_pack.animated(pack)
    if animated:
        if gate == "video":
            more = [_animations(run, pack, t)]
        else:
            more = [_storyboards(run, pack, t, only=animated)]
            if more[0][0]:
                more.append(_voiceover(run, pack, t))
        for extra, entries in more:
            items += extra
            plugin.update(entries)
    if not items:
        what = "take" if gate == "video" else "image"
        raise Stop(f"No {what} of the pack is made yet, so there is nothing to show on the {GATES[gate]} page. Make "
                   f"them first (tm tool replicate_run --name <item>), then build the page; {AGAIN}.")
    entry = state.load(run).checked.get("pack") or {}
    return _data(run, pack, gate, items, {"page": GATES[gate], "pack": entry.get("file"), "items": plugin,
                                          "missing_thumbnails": missing})


def _voiceover(run: RunFolder, pack: dict, t: dict) -> tuple[list, dict]:
    files = list(dict.fromkeys(r["file"] for r in manifest.rows(run)
                               if r["source"] == TTS and (run.path / r["file"]).is_file()))
    if not files:
        return [], {}
    ids: dict[str, str] = {}
    options = []
    for f in files:
        oid = _option_id(f, ids)
        ids[oid] = f
        options.append({"id": oid, "src": f, "caption": Path(f).name})
    item = {"id": "voiceover", "proposal": t["proposal"].format(id=pack["id"], channel=pack["channel"]),
            "label": t["label_voiceover"], "question": t["q_voiceover"], "options": options}
    return [item], {"voiceover": {"kind": "voiceover", "name": None, "stem": "voiceover", "files": ids}}


def _storyboards(run: RunFolder, pack: dict, t: dict, only: list[str] | None = None) -> tuple[list, dict]:
    """The latest storyboard sheet of each item folder, `03_wip/<item>/storyboard_vNN/sheet.png` (with `only`, of
    those items' folders alone)."""
    items, plugin = [], {}
    taken: set[str] = set()
    wip = run.path / WIP
    folders = (sorted(p for p in wip.iterdir() if p.is_dir()) if wip.is_dir() else []) if only is None else \
        [wip / item for item in only if (wip / item).is_dir()]
    for folder in folders:
        found = sorted((int(m.group(1)), d) for d in folder.iterdir()
                       if d.is_dir() and (m := STORYBOARD.match(d.name)) and (d / "sheet.png").is_file())
        if not found:
            continue
        latest = found[-1][1]
        sheet = _rel(run, latest / "sheet.png")
        iid = item_id(f"storyboard-{folder.name}", taken)
        items.append({"id": iid, "proposal": t["proposal"].format(id=pack["id"], channel=pack["channel"]),
                      "label": t["label_storyboard"].format(name=folder.name), "question": t["q_storyboard"],
                      "options": [{"id": latest.name, "src": sheet, "caption": f"{folder.name}/{latest.name}"}]})
        plugin[iid] = {"kind": "storyboard", "name": folder.name, "stem": f"{folder.name}_storyboard",
                       "files": {latest.name: sheet}}
    return items, plugin


def delivery_json(run: RunFolder) -> dict:
    """The data of the delivery page (the module docstring). A Stop without a checked pack, a final or its kit."""
    pack = _pack(run)
    lang = lang_of(pack)
    t = _ui(lang)
    pid = organic_final.idea_id(run)
    if pid is None:
        raise Stop(f"The delivery page shows this idea's final, and {organic_final.NO_ID}; {AGAIN}.")
    final = organic_final.final_of(run, pid)
    if final is None:
        raise Stop(f"The delivery page shows the final video, and none is made: {organic_final.FINAL}/"
                   f"{pid}_final_vNN.mp4 ({organic_final.FINISH.format(id=pid)}, G1). Make it, then build the page; "
                   f"{AGAIN}.")
    kit_path = run.latest(organic_final.KITS, f"{pid}_kit", "json")
    if kit_path is None:
        raise Stop(f"The delivery page shows the posting kit, and none is written: {organic_final.KITS}/"
                   f"{pid}_kit_vNN.json (tm kit check, G2). Write and check it, then build the page; {AGAIN}.")
    try:
        kit_data = json.loads(kit_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise Stop(f"{_rel(run, kit_path)} cannot be read ({exc}): write the kit again and check it (tm kit check); "
                   f"{AGAIN}.") from None
    final_rel, kit_rel = _rel(run, final), _rel(run, kit_path)
    version = final.stem.rsplit("_", 1)[-1]
    channel = runfolder.slug(str(pack.get("channel") or "")) or pid
    option = {"id": version, "src": _preview(run, final_rel), "caption": t["cap_final"].format(version=version),
              "pick": True}
    upload = organic_final.upload_of(final)
    if upload.is_file():
        name = f"{channel}_{pid}_{runfolder.slug(pack['title'])}.mp4"
        option["download"] = {"src": _rel(run, upload), "filename": name, "label": t["dl_video"]}
    refs = []
    cover = organic_final.cover_of(run, pid, final)   # only the cover made for this final (Task 16 review M3)
    if cover is not None:
        refs.append({"src": _rel(run, cover), "caption": t["cap_cover"],
                     "download": {"src": _rel(run, cover), "filename": f"{channel}_{pid}_{t['cover_file']}.jpg",
                                  "label": t["dl_cover"]}})
    items = [{"id": "final", "proposal": t["proposal"].format(id=pid, channel=pack["channel"]),
              "label": t["label_final"].format(id=pid, title=pack["title"]), "question": t["q_final"],
              "options": [option], "refs": refs, "kit": kit_data}]
    plugin = {"final": {"kind": "final", "name": None, "stem": f"{pid}_final", "files": {version: final_rel}}}
    shared, missing = _refs(run, pack, t)
    for video in (False, True):
        more, entries = _stage_items(run, pack, t, video=video, refs=shared)
        items += more
        plugin |= entries
    for more, entries in (_motions(run, pack, t), _voiceover(run, pack, t), _storyboards(run, pack, t)):
        items += more
        plugin |= entries
    return _data(run, pack, "edit", items, {"page": DELIVERY, "final": final_rel, "kit": kit_rel, "items": plugin,
                                            "missing_thumbnails": missing})


def build(run: RunFolder, page_name: str) -> dict:
    """Make the page's data and build it (`organic_pages.gate.build`). Returns its result and the data."""
    gate_page.check_page(page_name)
    if page.awaiting(run, page_name) is not None:   # before the data is made (thumbnails are fetched)
        raise page.Deciding(page_name, read=READ_WITH.format(page=page_name))
    data = delivery_json(run) if page_name == DELIVERY else gate_json(run, gate_page.PAGES[page_name])
    got = gate_page.build(run, data, page=page_name)
    return {**got, "page": page_name, "items": len(data["items"]),
            "missing_thumbnails": data["plugin"].get("missing_thumbnails") or []}


# --- the step check ---------------------------------------------------------------------------------

def delivery_gap(run: RunFolder) -> str | None:
    """The `final_page_built` step check (G4): a delivery page folder is built from the latest final, unchanged
    since. Reads only."""
    pid = organic_final.idea_id(run)
    if pid is None:
        return organic_final.NO_ID
    final = organic_final.final_of(run, pid)
    if final is None:
        return (f"the delivery page is built from the final, {organic_final.FINAL}/{pid}_final_vNN.mp4, which is made "
                f"first ({organic_final.FINISH.format(id=pid)})")
    rel, sha = _rel(run, final), stepchecks.sha256(final)
    for row in reversed(manifest.rows(run)):
        if row["source"] != f"{gate_page.SOURCE} {DELIVERY}":
            continue
        try:
            params = json.loads(row["params"]) if row["params"] else {}
        except ValueError:
            continue
        if (isinstance(params, dict) and params.get("final") == rel and params.get("final_sha256") == sha
                and (run.path / row["file"] / "index.html").is_file()):
            return None
    return f"the delivery page is built from the latest final, {rel} (tm organic page delivery --run <run>)"


# --- decisions ----------------------------------------------------------------------------------------

def decided_page(run: RunFolder, page_name: str) -> dict:
    """The build people decide on: the published folder (`state.pages[page]`), else the latest build; its data file,
    unchanged since. `{folder, data_file, data}`; a Stop when there is none or its data changed."""
    target = (state.load(run).pages.get(page_name) or {}).get("folder")
    rows = [r for r in manifest.rows(run) if r["source"] == f"{gate_page.SOURCE} {page_name}"
            and (target is None or r["file"] == target)]
    if not rows:
        where = f"the published folder {target}" if target else "this run"
        raise Stop(f"No {page_name} page build of {where} is recorded (tm organic page), so it is unknown what people "
                   f"decided on. Build the page and publish it, then read the decisions; {AGAIN}.")
    row = rows[-1]
    try:
        params = json.loads(row["params"]) if row["params"] else {}
    except ValueError:
        params = {}
    path = run.path / row["parent"]
    if not path.is_file() or params.get("data_sha256") != stepchecks.sha256(path):
        raise Stop(f"The page {row['file']} was built from {row['parent']}, which is gone or changed since, so it is "
                   f"unknown what people decided on. Build the page again, publish it and let the user decide on it; "
                   f"{AGAIN}.")
    return {"folder": row["file"], "data_file": row["parent"], "data": json.loads(path.read_text(encoding="utf-8"))}


_ACTION_WORDS = {"accept": "accept", "redo": "redo", "drop": "drop", "not decided": None,
                 "akceptuj": "accept", "popraw": "redo", "odrzuć": "drop", "bez decyzji": None}
_FIELDS = {"choice": "choice", "wybór": "choice", "platforms": "platforms", "platformy": "platforms",
           "thumbnail": "thumbnail", "miniatura": "thumbnail", "note": "note", "uwaga": "note"}
_YES = {"yes": True, "tak": True, "no": False, "nie": False}


def parse_chat(text: str, data: dict) -> list[tuple[str, dict]]:
    """The user's words in chat as page documents `(item id, document)`: one line per item, the module docstring's
    shape, in English or Polish. Two lines for one item, a word it cannot read, or a text with no line of this page
    is a Stop."""
    ids = [it["id"] for it in data["items"]]
    docs: dict[str, dict] = {}
    for line in text.splitlines():
        line = line.strip()
        iid = next((i for i in sorted(ids, key=len, reverse=True) if line.startswith(f"{i}: ")), None)
        if iid is None:
            continue
        if iid in docs:
            raise Stop(f"The text has two lines for {iid}, so it is unclear what the user decided. Ask them once and "
                       f"write one line; {AGAIN}.")
        parts = line[len(iid) + 2:].split("; ")
        word = parts[0].strip().lower()
        if word not in _ACTION_WORDS:
            raise Stop(f"The line {line!r} starts with {parts[0]!r}, which is not accept, redo, drop or not decided. "
                       f"Ask the user and write the line again; {AGAIN}.")
        doc: dict = {"action": _ACTION_WORDS[word]}
        for i, part in enumerate(parts[1:], 1):
            head, sep, value = part.partition(": ")
            field = _FIELDS.get(head.strip().lower()) if sep else None
            if field is None:
                raise Stop(f"The line {line!r} has a part it cannot read ({part!r}). Write it as `<item>: <decision>"
                           f"[; choice: <option>][; platforms: …][; thumbnail: yes|no][; note: …]`; {AGAIN}.")
            if field == "note":                     # the last part: a note may hold "; "
                doc["note"] = "; ".join([value, *parts[i + 1:]])
                break
            if field == "platforms":
                doc["platforms"] = [p.strip().lower() for p in value.split(",") if p.strip()]
            elif field == "thumbnail":
                if value.strip().lower() not in _YES:
                    raise Stop(f"The line {line!r} says thumbnail {value!r}: write yes or no; {AGAIN}.")
                doc["thumbnail"] = _YES[value.strip().lower()]
            else:
                doc["choice"] = value.strip()
        docs[iid] = doc
    if not docs:
        raise Stop("The text holds no line of this page (each starts with an item's id, e.g. `final: accept; "
                   f"platforms: tiktok, youtube`; the ids are {', '.join(ids)}). Write the user's answer in that form; "
                   f"{AGAIN}.")
    return list(docs.items())


def _newest(docs: list[tuple[str, dict]], ids: set[str]) -> dict[str, dict]:
    """Each item's document, the newest by `updated_at` when one is saved twice (else the later one)."""
    out: dict[str, dict] = {}
    for iid, doc in docs:
        if iid in ids and (iid not in out or str(doc.get("updated_at") or "") >= str(out[iid].get("updated_at") or "")):
            out[iid] = doc
    return out


def _platforms_said(iid: str, said: object) -> None:
    """Task 17 I3: a choice of platforms is never dropped quietly. An unknown name, or every platform unticked, is a
    Stop that asks the user, naming the four."""
    if said is None:
        return
    four = ", ".join(kit.PLATFORMS)
    names = said if isinstance(said, list) else [said]
    unknown = [str(p) for p in names if p not in kit.PLATFORMS]
    if unknown:
        raise Stop(f"The decision on {iid} names {', '.join(map(repr, unknown))}, which is not a platform; the four are "
                   f"{four}. Ask the user which of them to post to, write their answer in chat form (`{iid}: accept; "
                   f"platforms: tiktok, youtube`) and read it with --text; {AGAIN}.")
    if not names:
        raise Stop(f"The decision on {iid} unticks every platform, so the video would be posted nowhere. Ask the user "
                   f"which of the four ({four}) to post to, or whether not to post it; write their answer in chat form "
                   f"and read it with --text; {AGAIN}.")


def _rows(data: dict, docs: dict[str, dict]) -> dict[str, dict]:
    """A row per item of the page, from its document (an item nobody decided on: action None)."""
    entries = (data.get("plugin") or {}).get("items") or {}
    rows = {}
    for it in data["items"]:
        iid = it["id"]
        doc = docs.get(iid) or {}
        entry = entries.get(iid) or {}
        action = doc.get("action")
        if action not in (*ACTIONS, None):
            raise Stop(f"The decision on {iid} is {action!r}, which is not accept, redo or drop: ask the user what "
                       f"they meant, write it in chat form and read it with --text; {AGAIN}.")
        files = entry.get("files") or {}
        options = it.get("options") or []
        marked = next((o["id"] for o in options if o.get("pick")), None)
        if "choice" in doc:
            choice = doc.get("choice")
        elif marked is not None or len(options) < 2:
            choice = marked if marked is not None else (options[0]["id"] if options else None)
        elif action == "accept":   # M4: never the oldest option: ask which one
            raise Stop(f"The user accepted {iid} without saying which option ({', '.join(o['id'] for o in options)}), "
                       f"and none is picked yet. Ask them which one and write it as `{iid}: accept; choice: <option>`; "
                       f"{AGAIN}.")
        else:
            choice = None
        note = doc.get("note")
        row = {"kind": entry.get("kind"), "name": entry.get("name"), "stem": entry.get("stem"), "action": action,
               "choice": choice if choice in files else None, "file": files.get(choice),
               "note": note.strip() if isinstance(note, str) else ""}
        if it.get("kit"):
            said = doc.get("platforms")
            _platforms_said(iid, said)
            ticked = said if isinstance(said, list) else list(kit.PLATFORMS)
            row["platforms"] = [p for p in kit.PLATFORMS if p in ticked]
            row["thumbnail"] = doc.get("thumbnail") is True
        rows[iid] = row
    return rows


def _decisions_files(run: RunFolder, page_name: str) -> list[Path]:
    return organic_specs._decisions_files(run, f"decisions_{page_name}")


def _item_run(run: RunFolder, data: dict, iid: str, out_rel: str, page_name: str) -> tuple[RunFolder, str, str]:
    """Where a decision on an item is acted on: (the run, the page its request is keyed by, the decisions file as that
    run names it). An item of the week's delivery page (its `plugin.items[iid].run`) is its slot run's, as that run's
    own delivery page would key it; any other item is this run's and this page's."""
    entry = ((data.get("plugin") or {}).get("items") or {}).get(iid) or {}
    if not isinstance(entry.get("run"), str):
        return run, page_name, out_rel
    workspace = trend_spool.workspace_of(run)
    target = RunFolder(workspace / entry["run"])
    if not (target.path / "run.json").is_file():
        raise Stop(f"{iid} belongs to the run {entry['run']}, which is gone, so its decision cannot be acted on there. "
                   f"Restore it, or build the page again; {AGAIN}.")
    return target, DELIVERY, f"{_run_ref(run)}/{out_rel}"


def _redo_entry(run: RunFolder, row: dict, source: str, page_name: str) -> tuple[str, dict] | None:
    """The redo of the row's item as the user's request (the module docstring): (its key in run.json
    `organic.redos`, the entry), or None when the same request (note and take) is already recorded. Reads only."""
    stem = row["stem"]
    records = organic_specs.records(run, stem) if row["kind"] in ("images", "takes") else []
    key = stem if row["kind"] in ("images", "takes") else f"{page_name}:{stem}"   # never a pack item's (Task 17 M5)
    after = records[-1][0].name if records else (Path(row["file"]).name if row["file"] else None)
    s = state.load(run)
    if any(r.get("kind") == organic_specs.REQUEST and r.get("after") == after and r.get("note") == row["note"]
           for r in organic_specs._redos(s, key)):
        return None
    return key, {"kind": organic_specs.REQUEST, "note": row["note"], "by": "user", "at": flow._now(), "after": after,
                 "page": source}


def _kit_plan(run: RunFolder, data: dict, row: dict) -> tuple[Path | None, dict | None, list[str]]:
    """The final's ticks as a new kit version (the module docstring): (its path, its content, the ticked platforms),
    or (None, None, …) when nothing changed. A kit that is gone or cannot be read is a Stop. Reads only."""
    kit_rel = (data.get("plugin") or {}).get("kit")
    path = run.path / kit_rel if isinstance(kit_rel, str) else None
    if path is None or not path.is_file():
        raise Stop(f"The posting kit the page showed ({kit_rel}) is gone, so the platform ticks cannot be written into "
                   f"it. Restore it, or write the kit again with only the ticked platforms; {AGAIN}.")
    try:
        current = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        current = exc
    if not isinstance(current, dict):
        why = current if isinstance(current, Exception) else "not one JSON object"
        raise Stop(f"The posting kit the page showed ({kit_rel}) cannot be read ({why}), so the platform ticks cannot "
                   f"be written into it. Write the kit again and check it (tm kit check); nothing was written; {AGAIN}.")
    blocks = current.get("platforms") if isinstance(current.get("platforms"), dict) else {}
    plugin = current.get("plugin") if isinstance(current.get("plugin"), dict) else {}
    had = [p for p in kit.PLATFORMS if p in (plugin.get("platforms") or blocks)]
    ticked = [p for p in row["platforms"] if p in blocks]
    if not ticked:
        raise Stop(f"The user ticked {', '.join(row['platforms'])}, and the posting kit {kit_rel} has no block for "
                   f"{'it' if len(row['platforms']) == 1 else 'them'} (it holds {', '.join(blocks) or 'none'}). Write a "
                   f"kit with those platforms and check it (tm kit check), or ask the user again; {AGAIN}.")
    if ticked == had and (plugin.get("youtube_thumbnail") is True) == row["thumbnail"]:
        return None, None, ticked
    m = re.match(r"^(?P<stem>.+)_v\d+\.json$", path.name)
    pid = organic_final.idea_id(run)
    stem = f"{pid}_kit" if pid else (m.group("stem") if m else path.stem)   # the run's spelling of the idea
    out = run.next_version(Path(kit_rel).parent.as_posix(), stem, "json")
    new = copy.deepcopy(current)
    new["platforms"] = {p: blocks[p] for p in ticked}
    new["plugin"] = {**plugin, "platforms": ticked, "youtube_thumbnail": row["thumbnail"]}
    vm = re.search(r"_v(\d+)\.json$", out.name)
    if vm:
        new["version"] = f"v{vm.group(1)}"
    return out, new, ticked


def _write_kit(run: RunFolder, data: dict, row: dict, out: Path, new: dict) -> str:
    with open(out, "x", encoding="utf-8", newline="\n") as fh:
        json.dump(new, fh, ensure_ascii=False, indent=1)
    out_rel = _rel(run, out)
    manifest.record(run, out_rel, out_rel.split("/", 1)[0], DECISIONS_SOURCE,
                    parent=(data.get("plugin") or {}).get("kit"), params={"platforms": new["plugin"]["platforms"], "youtube_thumbnail": row["thumbnail"]})
    return out_rel


def take_decisions(run: RunFolder, page_name: str, *, file: Path | None = None, text: Path | None = None,
                   keep_carried: bool = False) -> dict:
    """Read the decisions taken on a check-in or delivery page into `03_wip/decisions_<page>_vNN.json` and act on
    them (the module docstring), then stop waiting for them."""
    gate_page.check_page(page_name)
    collection = gate_page.COLLECTIONS[page_name]
    slug = (state.load(run).pages.get(page_name) or {}).get("slug")
    if text is None and not slug:
        raise Stop(f"The page's publish is not recorded (tm page published --page {page_name}), so it is unknown which "
                   "artifact's decisions to read. Record it, read the decisions with an ArtifactData list first, or write the "
                   f"user's answer in chat form and read it with --text; {AGAIN}.")
    decided = decided_page(run, page_name)
    data = decided["data"]
    ids = {it["id"] for it in data["items"]}
    if text is not None:
        source = Path(text)
        docs = parse_chat(source.read_text(encoding="utf-8-sig"), data)
    else:
        source = Path(file) if file is not None else page.saved_answer(run, page_name, collection)
        if source is None:
            raise Stop(f"No saved answer holds the decisions of this page ({slug}): read them with an ArtifactData list "
                       f"first (the page's url, collection {collection}, query.limit 1000; with the older "
                       f"tools, db_list on slug {slug}), then run this again; {AGAIN}.")
        docs = page.db_docs(page.whole_answer(run, page_name, source, collection), collection=collection)
        if not docs:
            raise Stop("Nothing was saved on the page. Ask the user in chat; a decision written in chat counts. Write "
                       "their answer one line per item (for example `final: accept; platforms: tiktok, youtube` or "
                       "`takes-take: redo; note: <their words>`) to a file in the run and read it with --text; "
                       f"{AGAIN}.")
    newest = _newest(docs, ids)
    rows = _rows(data, newest)
    read = {iid: {k: v for k, v in doc.items() if k != "updated_at"} for iid, doc in newest.items()}
    carried: list[str] = []
    if text is None:
        earlier = page.earlier_decisions(run, _decisions_files(run, page_name), decided["folder"], built="folder",
                                         rows="read", command=DECISIONS_SOURCE, shape=dict) or {}
        carried = page.mark_carried(copy.deepcopy(read), earlier)
        for iid in carried:
            rows[iid]["carried"] = True
    rel = _rel(run, source)
    out = run.next_version(WIP, f"decisions_{page_name}", "json")
    out_rel = out.relative_to(run.path).as_posix()
    acted = [iid for iid, row in rows.items() if keep_carried or not row.get("carried")]
    requests = []
    for iid in acted:
        if rows[iid]["action"] == "redo" and rows[iid]["stem"]:
            target, at_page, source_ref = _item_run(run, data, iid, out_rel, page_name)
            if (found := _redo_entry(target, rows[iid], source_ref, at_page)):
                requests.append((iid, target, *found))
    redos = [key for _, _, key, _ in requests]
    labels = {it["id"]: it.get("label") or it["id"] for it in data["items"]}
    redo_labels = [labels[iid] for iid, _, _, _ in requests]        # the items in the page's words (Task 19 M5)
    kit_out, kit_body, ticked = None, None, None
    if page_name == DELIVERY and "final" in acted and "final" in read:   # the ticks the user saved, or said
        kit_out, kit_body, ticked = _kit_plan(run, data, rows["final"])
    new_kit = _rel(run, kit_out) if kit_out is not None else None
    slot_kits = []      # the week's delivery: each slot video's ticks, as a new kit version in its own run
    for iid in acted if page_name != DELIVERY else ():
        entry = ((data.get("plugin") or {}).get("items") or {}).get(iid) or {}
        if entry.get("kind") == "final" and entry.get("kit") and iid in read:
            target, _, _ = _item_run(run, data, iid, out_rel, page_name)
            mini = {"plugin": {"kit": entry["kit"]}}
            found_out, found_body, found_ticked = _kit_plan(target, mini, rows[iid])
            if found_out is not None:
                slot_kits.append({"item": iid, "run": entry["run"], "target": target, "data": mini, "out": found_out,
                                  "body": found_body, "ticked": found_ticked})
    out.parent.mkdir(parents=True, exist_ok=True)
    body = {"page": page_name, "collection": collection, "folder": decided["folder"], "data": decided["data_file"],
            "from": rel, "slug": slug or None, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "chat" if text is not None else "page", "keep_carried": bool(keep_carried), "decisions": rows,
            "read": read, "carried": carried, "redos": redos, "kit": new_kit,
            "kits": [{"item": k["item"], "run": k["run"], "kit": _rel(k["target"], k["out"])} for k in slot_kits]}
    with open(out, "x", encoding="utf-8", newline="\n") as fh:
        json.dump(body, fh, ensure_ascii=False, indent=2)
    manifest.record(run, out_rel, WIP, DECISIONS_SOURCE, parent=rel,
                    params={"page": page_name, "folder": decided["folder"]})
    for _, target, key, entry in requests:            # acted on after the decisions file says what was decided (M3)
        organic_specs._add_redo(target, key, entry)
    if kit_out is not None:
        _write_kit(run, data, rows["final"], kit_out, kit_body)
    for k in slot_kits:
        _write_kit(k["target"], k["data"], rows[k["item"]], k["out"], k["body"])
    page.clear_await(run, page_name)
    return {"file": out_rel, "from": rel, "page": page_name, "folder": decided["folder"], "source": body["source"],
            "decisions": rows, "carried": carried, "redos": redos, "redo_labels": redo_labels, "kit": new_kit,
            "ticked": ticked, "kits": body["kits"], "docs": len(docs)}
