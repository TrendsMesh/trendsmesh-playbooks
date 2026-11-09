"""The week's delivery (organic video I4, the plan's Decision 14): one delivery page for the week and the posting plan.

    deliver(run)        `tm organic deliver-week`: 04_final/week_delivery_vNN/ and 05_results/posting_plan_vNN.json, .md
    delivered_gap(run)  the step check `week_delivered`

The page is `week_delivery` (`organic_pages.gate`, gate `edit`; the plan page is `04_final/week_vNN/`), one item per
started slot run (`organic_week.slot_runs`) in date order: its final video (the first item of
`organic_gates.delivery_json`, its files made absolute) with its kit, or its checked script to film (its page's
Markdown) with the kit its blocks make. The data's `plugin.items` ties each item to its slot run (`run`, `kind`
final or script, `stem`, `files`, the video's `kit`), so `tm organic decisions --page week_delivery`
(`organic_gates.take_decisions`) reads its decisions like a single delivery page's and acts on them in that run: a
redo becomes the user's request there, unticked platforms a new kit version there. `plugin.slots` records each slot's
file and sha256 for `delivered_gap`.

The posting plan is `[{day, channel, title, file, caption, sound}]`, one row per slot and ticked platform: `day` the
ISO date, `channel` the platform, `file` the file to post as the page names its download (the video's upload copy, the
script's Markdown).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from tm import brand, manifest, organic_week, runfolder, state, stepchecks, trend_spool
from tm.organic_week import DELIVERY, PLAN_STEM, RESULTS, _text, day_date
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

SOURCE = "tm organic deliver-week"


def _deliverable(prod: RunFolder) -> tuple[str, Path]:
    """("video", its latest final) or ("script", its checked script) of a slot run; a Stop when it has none yet."""
    from tm import organic_final

    s = state.load(prod)
    if "organic_video" in s.outputs:
        pid = organic_final.idea_id(prod)
        final = organic_final.final_of(prod, pid) if pid else None
        if final is None:
            raise Stop(f"{prod.path.name} has no final video yet: finish it in its own run (G1 to G4), then deliver the "
                       f"week; {AGAIN}.")
        return "video", final
    entry = s.checked.get("script")
    if not entry or not (prod.path / entry["file"]).is_file():
        raise Stop(f"{prod.path.name} has no checked script yet: finish it in its own run (E3), then deliver the week; "
                   f"{AGAIN}.")
    return "script", prod.path / entry["file"]


def _script_md(prod: RunFolder, script: dict) -> Path:
    """The Markdown of a slot run's latest script page (`organic_pages.script.build` names it); a Stop without one."""
    from tm import page

    folder = page.latest_folder(prod, f"{script['id']}_script_{script['lang']}")
    md = folder / f"{page.asset_name(script['id'])}_script_{page.asset_name(script['version'])}.md" if folder else None
    if md is None or not md.is_file():
        raise Stop(f"{prod.path.name}'s script page is not built: build it (tm organic page script), then deliver the "
                   f"week; {AGAIN}.")
    return md


WORDS = {
    "en": {"title": "{title}: the week's videos, scripts and posting kits",
           "lede": ("Every video and script of the week, each with its posting kit, in posting order. Download each video "
                    "and cover, or the script to film, with the Download buttons; the posting plan says when and where "
                    "to post each one."),
           "eyebrow": "{day} {date} · {time}", "label": "“{title}”", "q_video": "Watch the video and check the texts.",
           "q_script": "Read the script you film, and check the texts.", "cap_script": "Script to film",
           "dl_script": "script (.md)", "plan": "Posting plan", "none": "nothing to post"},
    "pl": {"title": "{title}: filmy, skrypty i zestawy do publikacji z tego tygodnia",
           "lede": ("Każdy film i skrypt tygodnia z zestawem do publikacji, w kolejności publikacji. Film i okładkę albo "
                    "skrypt do nagrania pobierzesz przyciskami „Pobierz”; plan publikacji mówi, kiedy i gdzie wrzucić "
                    "każdy z nich."),
           "eyebrow": "{day} {date} · {time}", "label": "„{title}”", "q_video": "Obejrzyj film i sprawdź opisy.",
           "q_script": "Przeczytaj skrypt do nagrania i sprawdź opisy.", "cap_script": "Skrypt do nagrania",
           "dl_script": "skrypt (.md)", "plan": "Plan publikacji", "none": "nic do publikacji"},
}


def _caption(platform: str, block: dict) -> str:
    if platform == "youtube":
        return "\n\n".join(x for x in (block.get("title"), block.get("description")) if _text(x))
    text = str(block.get("caption") or "").rstrip()
    tags = " ".join(t for t in block.get("hashtags") or [] if isinstance(t, str))
    return f"{text}\n{tags}".strip() if tags and tags not in text else text


def deliver(run: RunFolder) -> dict:
    """Build the week's delivery page and write the posting plan (the module docstring). A Stop while a started slot
    has no final or checked script, or while nothing is started."""
    from tm import organic_gates, organic_pack
    from tm.organic_pages import gate as gate_page, lang_of, script as script_page, week as week_page

    _, week_rel, week = organic_week.checked_week(run)
    lang = lang_of(week)
    t = WORDS[lang]
    days = dict(zip(organic_week.WEEKDAYS, week_page.T[lang]["days"]))
    slot_of = {organic_week.DAY[str(s["day"])]: s for s in week["slots"]}
    slots = organic_week.slot_runs(run)
    if not slots:
        raise Stop(f"No slot of the week is started yet: start them (tm organic start), make each, then deliver the "
                   f"week; {AGAIN}.")
    workspace = trend_spool.workspace_of(run)
    items, slots_of, entries, rows, taken = [], {}, {}, [], set()
    for day, prod, entry in slots:
        kind, file = _deliverable(prod)
        slot = slot_of.get(day) or {}
        when = day_date(week, day)
        title = organic_pack.idea_of(prod).get("title") or slot.get("title") or prod.path.name
        if kind == "video":
            single = organic_gates.delivery_json(prod)
            item = copy.deepcopy(single["items"][0])
            ties = {**single["plugin"]["items"]["final"], "kit": single["plugin"]["kit"]}
            for shown in [*item.get("options", []), *item.get("refs", [])]:   # the slot run's files, as they are
                shown["src"] = str((prod.path / shown["src"]).resolve())
                if shown.get("download"):
                    shown["download"]["src"] = str((prod.path / shown["download"]["src"]).resolve())
            option = item["options"][0]
            post = (option.get("download") or {}).get("filename") or Path(option["src"]).name
            item["question"] = t["q_video"]
        else:
            data = json.loads(file.read_text(encoding="utf-8-sig"))
            md = str(_script_md(prod, data).resolve())
            post = f"{runfolder.slug(str(week['channel']))}_{data['id']}_{runfolder.slug(data['title'])}.md"
            item = {"question": t["q_script"], "refs": [], "kit": script_page._kit_of(data),
                    "options": [{"id": data["version"], "src": md, "caption": t["cap_script"], "pick": True,
                                 "download": {"src": md, "filename": post, "label": t["dl_script"]}}]}
            ties = {"kind": "script", "name": None, "stem": f"script_{data['id']}",
                    "files": {data["version"]: file.relative_to(prod.path).as_posix()}}
        item["id"] = organic_gates.item_id(f"{day}-{entry.get('proposal') or prod.path.name}", taken)
        taken.add(item["id"])
        item["proposal"] = t["eyebrow"].format(day=days[day], date=when.isoformat() if when else "",
                                               time=slot.get("time", ""))
        item["label"] = t["label"].format(title=title)
        items.append(item)
        entries[item["id"]] = {**ties, "run": entry["path"]}   # where a decision on the item is acted on
        slots_of[item["id"]] = {"day": day, "run": entry["path"], "kind": kind,
                                "file": file.resolve().relative_to(workspace.resolve()).as_posix(),
                                "sha256": stepchecks.sha256(file)}
        kit_data = item.get("kit") or {}
        ticked = (kit_data.get("plugin") or {}).get("platforms") or list((kit_data.get("platforms") or {}))
        for platform in [p for p in brand.PLATFORMS if p in ticked]:
            block = (kit_data.get("platforms") or {}).get(platform) or {}
            rows.append({"day": when.isoformat() if when else day, "channel": platform,
                         "title": title, "file": post, "caption": _caption(platform, block),
                         "sound": str(block.get("sound") or "")})
    data = {"lang": lang, "title": t["title"].format(title=week["title"]), "run": organic_week.week_ref(run),
            "gate": "edit", "date": organic_week._today().isoformat(), "lede": t["lede"], "items": items,
            "plugin": {"page": DELIVERY, "week": week_rel, "items": entries, "slots": slots_of}}
    got = gate_page.build(run, data, page=DELIVERY)
    plan = run.next_version(RESULTS, PLAN_STEM, "json")
    plan.parent.mkdir(parents=True, exist_ok=True)
    with open(plan, "x", encoding="utf-8", newline="\n") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
    md_path = plan.with_suffix(".md")
    with open(md_path, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(_plan_md(week, rows, t))
    plan_rel, md_rel = (p.relative_to(run.path).as_posix() for p in (plan, md_path))
    for rel in (plan_rel, md_rel):
        manifest.record(run, rel, RESULTS, SOURCE, parent=got["folder"], cost="0",
                        params={"slots": len(items)})
    return {**got, "page": DELIVERY, "items": len(items), "posting_plan": plan_rel, "posting_plan_md": md_rel,
            "rows": len(rows)}


def _plan_md(week: dict, rows: list[dict], t: dict) -> str:
    out = [f"# {t['plan']}: {week['title']}", ""]
    if not rows:
        out.append(t["none"])
    for r in rows:
        out += [f"## {r['day']} · {r['channel']} · {r['title']}", "", f"- file: {r['file']}", f"- sound: {r['sound']}",
                "", "```", r["caption"], "```", ""]
    return "\n".join(out).rstrip() + "\n"


def delivered_gap(run: RunFolder) -> str | None:
    """The `week_delivered` step check: I4 is done once the latest week delivery page was built from every started
    slot's current final or checked script, with its posting plan. Reads only."""
    from tm.organic_pages import gate as gate_page

    try:
        slots = organic_week.slot_runs(run)
        current = {entry["path"]: _deliverable(prod)[1] for _, prod, entry in slots}
    except Stop as exc:
        return f"every started slot has its final video or checked script ({str(exc).split(':')[0]})"
    if not current:
        return "the week's slots are started and made (tm organic start), then delivered (tm organic deliver-week)"
    workspace = trend_spool.workspace_of(run)
    rows = [r for r in manifest.rows(run) if r["source"] == f"{gate_page.SOURCE} {DELIVERY}"]
    plan_rows = [r for r in manifest.rows(run) if r["source"] == SOURCE]
    if rows and plan_rows and plan_rows[-1]["parent"] == rows[-1]["file"]:
        try:
            data = json.loads((run.path / rows[-1]["parent"]).read_text(encoding="utf-8"))
            built = {v["run"]: v for v in data["plugin"]["slots"].values()}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            built = {}
        if set(built) == set(current) and all(
                built[k].get("sha256") == stepchecks.sha256(f)
                and built[k].get("file") == f.resolve().relative_to(workspace.resolve()).as_posix()
                for k, f in current.items()):
            return None
    return "the week's delivery page and posting plan are built from every started slot's latest file (tm organic deliver-week)"
