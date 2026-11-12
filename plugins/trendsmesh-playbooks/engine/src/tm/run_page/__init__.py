"""The run page (issue #19): one published page per run that grows at every check-in, built from the run state.

    tm page build --run R [--ask FILE] [--local] [--json]   04_final/run_page_vNN/ from run.json, the run's files and
                                                            the asks (FILE: this check-in's words, saved first)
    tm page decision --run R CHECKIN [--record] [--json]    the choice saved on the published page for CHECKIN;
                                                            --record records it (tm decide, "(from the page)")

An **ask** is the one thing the agent writes for a check-in, in the run's language: `{"checkin", "title",
"lede", "question", "context", "options": [{"choice", "label", "means", "recommended"}], "points", "media":
[{"file", "caption"}], "data": [{"file", "title"}]}` (only checkin, title, question and options are needed). It is
saved as `03_wip/page/ask_<checkin>_vNN.json` with its id (`<checkin>_vNN`) and the time it was saved. Everything
else on the page comes from the run: the stage materials (`refresh_ad.materials`, from the run's saved files), the
recorded decisions (run.json), and the files the ask names.

A check-in is **open** while its latest ask is newer than its latest recorded decision: it is in the "Now" block,
with the only active decision blocks on the page. Every decided check-in (asked on the page or not, by the user or by
rule) is a folded stage in "Already settled", its decision a read-only summary from run.json. So the page never
holds two versions of one question, and an earlier decision cannot be saved again by a click.

The page saves a choice in the artifact's db (`CAPABILITIES`: the owner reads and writes `decisions`) as the
document `decisions/<checkin>`, with the ask id it was made on and, for a stage that takes more than a choice (a
pick, a choice per item, notes per scene or pinned at a time, edited copy: tm.run_page.detail), its `detail`, taken
back only as far as the build offered it (`.build.json` `offer`). `decision` reads it only through tm.page's reader
(the newest whole ArtifactData list of `decisions`, saved after the page's latest publish), and refuses a choice made
on an earlier ask, a choice the ask does not offer, and a page published before the question was on it. A note is
data: it is returned whole, to quote to the user, and never acted on.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from tm import checkins, flow, i18n, manifest, page, playbooks, state
from tm.run_page import (create_ad, detail as details, organic_video, refresh_ad, template, trend_research,
                         words)
from tm.run_page.context import MEDIA_EXT, Context
from tm.run_page.words import t
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

PAGE = "run_page"
COLLECTION = "decisions"
ASKS = "03_wip/page"
SOURCE = "tm page build"
ASK_SOURCE = "tm page build --ask"
BUILD_FILE = ".build.json"          # in the page folder; hidden, so never published (page.files)
# The owner reads and writes the decisions; viewers the page is shared with read the page, not the choices, and
# are told to answer in chat. `user` tells the page whether this viewer is the owner; `downloads` saves the CSVs.
CAPABILITIES = {"db": {"rules": [{"path": COLLECTION, "read": "owner", "write": "owner"}]}, "user": {},
                "downloads": {}}
COMPONENTS = {playbooks.REFRESH_AD: refresh_ad.materials, playbooks.CREATE_AD: create_ad.materials,
              playbooks.TREND_RESEARCH: trend_research.materials, playbooks.ORGANIC_VIDEO: organic_video.materials}
OUTCOMES = {playbooks.REFRESH_AD: refresh_ad.outcome,     # a decided choice in words, when no ask labels it
            playbooks.CREATE_AD: create_ad.outcome, playbooks.TREND_RESEARCH: trend_research.outcome,
            playbooks.ORGANIC_VIDEO: organic_video.outcome}
# what a stage's detail adds when its choice is recorded: the lines of its note (a Stop there refuses the answer
# before anything is recorded), and the files it writes (with `then`, a line for the agent)
RECORDED = {playbooks.CREATE_AD: (create_ad.note_lines, create_ad.write_files),
            playbooks.ORGANIC_VIDEO: (organic_video.note_lines, organic_video.write_files)}
ANSWER_SOURCE = "tm page decision --record"

_ASK_KEYS = {"checkin", "title", "lede", "question", "context", "options", "points", "media", "data"}
_OPTION_KEYS = {"choice", "label", "means", "recommended"}
_CHOICE = re.compile(r"^[A-Za-z0-9_.:@+-]{1,120}$")
_ASK_FILE = re.compile(r"^ask_(.+)_v(\d+)$")
MAX_TEXT = 4000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _when(value: object) -> datetime | None:
    try:
        at = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
    return at.replace(tzinfo=timezone.utc) if at is not None and at.tzinfo is None else at


# --- asks -----------------------------------------------------------------------------------------

def _catalogue(run: RunFolder):
    return checkins.load(playbook=state.load(run).playbook)


def _members(run: RunFolder, checkin: str) -> list[str]:
    cat = _catalogue(run)
    if checkin in cat.checkins:
        return [checkin]
    return [cid for cid, c in cat.checkins.items() if c.card == checkin]


def check_ask(run: RunFolder, ask: object) -> list[str]:
    """What is wrong with an ask, in words; [] when it can be saved."""
    if not isinstance(ask, dict):
        return ["The ask must be a JSON object."]
    problems = [f"{k!r} is not a field of an ask (fields: {', '.join(sorted(_ASK_KEYS))})." for k in ask if k not in _ASK_KEYS]
    cat = _catalogue(run)
    cid = ask.get("checkin")
    if not (isinstance(cid, str) and (cid in cat.checkins or cid in cat.cards)):
        problems.append(f"checkin {cid!r} is not a check-in (or card) of this playbook.")
    for key in ("title", "question"):
        if not (isinstance(ask.get(key), str) and ask[key].strip()):
            problems.append(f"{key} is needed: one line in the run's language.")
    for key in ("title", "lede", "question", "context"):
        if isinstance(ask.get(key), str) and len(ask[key]) > MAX_TEXT:
            problems.append(f"{key} is longer than {MAX_TEXT} characters.")
        elif key in ask and ask[key] is not None and not isinstance(ask[key], str):
            problems.append(f"{key} must be text.")
    options = ask.get("options")
    if not (isinstance(options, list) and 1 <= len(options) <= 8):
        problems.append("options must list 1 to 8 options.")
        options = []
    allowed = cat.checkins[cid].choices if isinstance(cid, str) and cid in cat.checkins else None
    seen, recommended = set(), 0
    for n, o in enumerate(options, 1):
        if not isinstance(o, dict):
            problems.append(f"option {n} must be an object with choice and label.")
            continue
        problems += [f"option {n}: {k!r} is not a field of an option." for k in o if k not in _OPTION_KEYS]
        choice = o.get("choice")
        if not (isinstance(choice, str) and _CHOICE.match(choice)):
            problems.append(f"option {n}: choice must be the recorded choice id (letters, digits, _ - . : @ +).")
        elif allowed is not None and choice not in allowed:
            problems.append(f"option {n}: {choice!r} is not a choice of {cid} ({', '.join(allowed)}).")
        elif choice in seen:
            problems.append(f"option {n}: {choice!r} is listed twice.")
        seen.add(choice)
        if not (isinstance(o.get("label"), str) and o["label"].strip()):
            problems.append(f"option {n}: label is needed, in the run's language.")
        if "means" in o and not isinstance(o["means"], str):
            problems.append(f"option {n}: means must be text.")
        if "recommended" in o and not isinstance(o["recommended"], bool):
            problems.append(f"option {n}: recommended must be true or false.")
        recommended += o.get("recommended") is True
    if recommended > 1:
        problems.append("only one option can be recommended.")
    points = ask.get("points", [])
    if not (isinstance(points, list) and all(isinstance(p, str) and p.strip() for p in points)):
        problems.append("points must be a list of lines.")
    ctx = Context(run, None, "en")
    for key, ext in (("media", MEDIA_EXT), ("data", (".csv", ".json"))):
        items = ask.get(key, [])
        if not isinstance(items, list):
            problems.append(f"{key} must be a list of {{file, ...}}.")
            continue
        for n, item in enumerate(items, 1):
            rel = item.get("file") if isinstance(item, dict) else None
            path = ctx.inside(rel) if isinstance(rel, str) else None
            if path is None:
                problems.append(f"{key} {n}: {rel!r} is not a file inside the run folder (a run-relative path).")
            elif path.suffix.lower() not in ext:
                problems.append(f"{key} {n}: {rel} is not one of {', '.join(ext)}.")
    return problems


def save_ask(run: RunFolder, source: Path) -> dict:
    """Check the ask in `source` and save it as `03_wip/page/ask_<checkin>_vNN.json` (with `_id` and `_at`);
    a Stop with every problem when it cannot be saved."""
    try:
        ask = json.loads(Path(source).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise Stop(f"The ask {source} cannot be read ({exc}). Write it as JSON with the Write tool; {AGAIN}.") from None
    problems = check_ask(run, ask)
    if problems:
        raise Stop("The ask needs fixing:\n" + "\n".join(f"- {p}" for p in problems)
                   + f"\nFix the file and build the page again; {AGAIN}.")
    target = run.next_version(ASKS, f"ask_{ask['checkin']}", "json")
    run.assert_writable(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    saved = {"_id": target.stem.removeprefix("ask_"), "_at": _now(), **ask}
    target.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest.record(run, f"{ASKS}/{target.name}", "03_wip", ASK_SOURCE)
    return saved


def asks(run: RunFolder) -> dict[str, dict]:
    """The latest saved ask of each check-in (or card), with `_file`."""
    folder = run.path / ASKS
    found: dict[str, tuple[int, Path]] = {}
    for f in folder.glob("ask_*_v*.json") if folder.is_dir() else ():
        m = _ASK_FILE.match(f.stem)
        if m and (m.group(1) not in found or int(m.group(2)) > found[m.group(1)][0]):
            found[m.group(1)] = (int(m.group(2)), f)
    out = {}
    for cid, (_, f) in found.items():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise Stop(f"{ASKS}/{f.name} cannot be read. Restore it or move it out of {ASKS}; {AGAIN}.") from None
        if isinstance(data, dict) and isinstance(data.get("_id"), str):
            out[cid] = {**data, "_file": f"{ASKS}/{f.name}"}
    return out


# --- the page model -------------------------------------------------------------------------------

def _latest_decisions(run: RunFolder) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for d in state.load(run).decisions:
        if isinstance(d, dict) and isinstance(d.get("checkin"), str):
            out[d["checkin"]] = d
    return out


def is_open(run: RunFolder, ask: dict, decided: dict[str, dict] | None = None) -> bool:
    """An ask is open while some check-in it covers has no decision recorded after the ask was saved."""
    decided = _latest_decisions(run) if decided is None else decided
    asked = _when(ask.get("_at"))
    for cid in _members(run, ask["checkin"]):
        d = decided.get(cid)
        at = _when(d.get("at")) if d else None
        if d is None or at is None or (asked is not None and at < asked):
            return True
    return False


def _ask_blocks(ctx: Context, ask: dict) -> list[dict]:
    """What the ask itself adds: its points, its players, its tables (from the run files it names)."""
    out = []
    if ask.get("points"):
        out.append({"kind": "list", "items": ask["points"]})
    items = [{"src": served, "caption": m.get("caption") or ""} for m in ask.get("media") or []
             if (served := ctx.put(m["file"]))]
    if items:
        out.append({"kind": "media", "items": items})
    for d in ask.get("data") or []:
        path = ctx.inside(d["file"])
        rows = _rows(path) if path else None
        if rows:
            cols = list(dict.fromkeys(k for r in rows for k in r))
            kinds = {k: "num" if all(isinstance(r.get(k), (int, float)) and not isinstance(r.get(k), bool)
                                     for r in rows if r.get(k) is not None) else "text" for k in cols}
            did = ctx.ds.add(d.get("title") or path.name, ctx.rel(path), [(k, k, kinds[k]) for k in cols], rows)
            out.append({"kind": "table", "title": d.get("title") or "", "data": did})
    return out


def _rows(path: Path) -> list[dict] | None:
    """A table from a run file: a CSV's rows (numbers as numbers), or a JSON list of objects (or {"rows": [...]})."""
    import csv
    try:
        if path.suffix.lower() == ".csv":
            with open(path, encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
            return [{k: _number(v) for k, v in r.items() if k is not None} for r in rows]
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, csv.Error):
        return None
    data = data.get("rows") if isinstance(data, dict) else data
    if isinstance(data, list) and all(isinstance(r, dict) for r in data):
        return [{k: v if isinstance(v, (str, int, float, bool)) or v is None else json.dumps(v, ensure_ascii=False)
                 for k, v in r.items()} for r in data]
    return None


def _number(v: str):
    try:
        return int(v) if re.fullmatch(r"-?\d+", v.strip()) else float(v) if re.fullmatch(r"-?\d+\.\d+", v.strip()) else v
    except (AttributeError, ValueError):
        return v


def model(run: RunFolder, folder: Path | None, *, local: bool) -> tuple[dict, dict]:
    """The page's model (template.render) and the build record (`open`: check-in -> ask id)."""
    s = state.load(run)
    found = asks(run)
    words.reset()
    pl = words.page_lang(run)          # the run's working language, or English while its table is not translated
    lang = pl.lang
    ctx = Context(run, folder, lang)
    cat = _catalogue(run)
    decided = _latest_decisions(run)
    component = COMPONENTS.get(s.playbook, lambda c, cid: [])

    def stage_blocks(key: str, ask: dict | None) -> list[dict]:
        out = []
        for cid in _members(run, key) if key in cat.cards else [key]:
            out += component(ctx, cid)
        return out + (_ask_blocks(ctx, ask) if ask else [])

    own = playbooks.get(s.playbook).skill.replace("-", "_")     # a playbook's own stage names come first: G1 is
                                                                 # not the same check-in in every playbook
    def name(key: str) -> str:
        known = cat.cards[key].name if key in cat.cards else cat.checkins[key].name if key in cat.checkins else key
        mine = f"{own}.stage.{key}"
        return ctx.t(mine) if words.has(mine, lang) else ctx.t_or("stage." + key, known)

    def worded(cid: str, d: dict) -> str | None:
        return OUTCOMES.get(s.playbook, lambda c, i, x: None)(ctx, cid, d.get("choice"))

    stages = []                      # (when, key, ask or None, record or None)
    asked_members = set()
    for key, ask in found.items():
        members = _members(run, key)
        if is_open(run, ask, decided):
            stages.append((ask.get("_at") or "", key, ask, None))
        else:
            d = decided[members[-1]]
            stages.append((d.get("at") or "", key, ask, _record(ask, d, worded(members[-1], d))))
        asked_members.update(members)
    for cid, d in decided.items():
        if cid not in asked_members and cid in cat.checkins:
            stages.append((d.get("at") or "", cid, None, _record(None, d, worded(cid, d))))
    stages.sort(key=lambda x: (x[3] is None, x[0]))     # settled first by time, then the open ones
    now, settled = [], []
    for n, (_, key, ask, record) in enumerate(stages, 1):
        stage = {"key": key, "n": n, "name": name(key), "title": (ask or {}).get("title") or "",
                 "lede": (ask or {}).get("lede") or "", "blocks": stage_blocks(key, ask)}
        if record is None:
            stage["decision"] = {"checkin": key, "ask": ask["_id"], "question": ask["question"],
                                 "context": ask.get("context") or "", "options": ask["options"]}
            stage["offer"] = details.merge([b.get("offer") for b in stage["blocks"]])
            now.append(stage)
        else:
            stage["record"] = record
            settled.append(stage)
    settled.reverse()                                   # newest first
    pb = playbooks.get(s.playbook)
    updated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    named = "playbook." + pb.skill.replace("-", "_")     # the playbook's name in the page's language
    pb_name = t(named, lang) if words.has(named, lang) else pb.name
    m = {"lang": i18n.html_lang(lang), "warning": pl.warning, "title": t("top.title", lang, playbook=pb_name, run=run.path.name), "playbook": pb_name,
         "run": run.path.name, "updated": updated, "local": local, "build": folder.name if folder else "",
         "now": now, "settled": settled, "datasets": ctx.ds}
    built = {"page": PAGE, "local": local, "lang": lang, "built_at": _now(),
             "open": {st["key"]: st["decision"]["ask"] for st in now},
             "offer": {st["key"]: st["offer"] for st in now if st["offer"] and not local}}
    return m, built


def _record(ask: dict | None, d: dict, worded: str | None = None) -> dict:
    labels = {o["choice"]: o["label"] for o in (ask or {}).get("options") or []}
    label = labels.get(d.get("choice")) or worded or d.get("choice")
    return {"choice": d.get("choice"), "label": label, "note": d.get("note"),
            "at": d.get("at"), "by": d.get("by"), "rule": d.get("rule")}


# --- build ------------------------------------------------------------------------------------------

def build(run: RunFolder, ask_file: Path | None = None, *, local: bool = False) -> dict:
    """Save the ask (when given), then build `04_final/run_page_vNN/` from the run state. A build that would not
    publish (too big for the Artifact tool, or a mangled `/_blob/` reference) is removed and refused."""
    saved = save_ask(run, ask_file) if ask_file is not None else None
    folder = page.new_folder(run, PAGE)
    try:
        m, built = model(run, folder, local=local)
        text = template.render(m)
        bad = page.mangled_blob_refs(text)
        if bad:
            raise Stop(page.MANGLED.format(refs=", ".join(bad[:3])))
        (folder / "index.html").write_text(text, encoding="utf-8")
        (folder / BUILD_FILE).write_text(json.dumps(built, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        listed = page.files(folder)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    rel = folder.relative_to(run.path).as_posix()
    manifest.record(run, rel, "04_final", SOURCE, params={"open": ",".join(built["open"]) or None,
                                                          "local": local or None})
    return {"folder": rel, "index": str((folder / "index.html").resolve()), "open": list(built["open"]),
            "settled": len(m["settled"]), "ask": saved["_id"] if saved else None, "local": local,
            "lang": m["lang"], "title": m["title"], **({"language_warning": m["warning"]} if m["warning"] else {}), "artifact": page.artifact_args(listed),
            **({} if local else {"capabilities": CAPABILITIES}),
            "published": page.published(run, PAGE) if not local else None}


# --- the choice saved on the page --------------------------------------------------------------------

def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _chat(checkin: str) -> str:
    return f"Or ask in chat and record the answer with `tm decide {checkin} <choice>`. The run continues from the same place."


def decision(run: RunFolder, checkin: str) -> dict:
    """The choice saved on the published page for `checkin`: `{checkin, choice, label, note, saved_at, ask}`; a Stop
    when it cannot be taken as the user's answer to the question open now."""
    found = asks(run)
    ask = found.get(checkin)
    if ask is None:
        raise Stop(f"The page has never asked {checkin}: build it with an ask for {checkin} (tm page build --ask) and "
                   f"publish it first. {_chat(checkin)}")
    if not is_open(run, ask):
        raise Stop(f"{checkin} is already recorded, after its question was put on the page. Nothing to read. "
                   f"{_chat(checkin)}")
    record = (state.load(run).pages.get(PAGE) or {})
    if not record.get("slug"):
        raise Stop(f"The run page's publish is not recorded in this run, so its saved choices cannot be read: publish it "
                   f"and record it with `tm page published --run <run> --page {PAGE}`. {_chat(checkin)}")
    built = _read_json(run.path / str(record.get("folder") or "") / BUILD_FILE)
    if (built or {}).get("open", {}).get(checkin) != ask["_id"]:
        raise Stop(f"The published page does not show {checkin}'s latest question ({ask['_id']}): it was published "
                   f"before it. Publish the latest build (tm page files --page {PAGE}), record it, and let the user "
                   f"choose there. {_chat(checkin)}")
    source = page.saved_answer(run, PAGE, COLLECTION)
    if source is None:
        raise Stop(page.READ_AGAIN.format(collection=COLLECTION))
    saved = page.whole_answer(run, PAGE, source, COLLECTION)
    docs = dict(page.db_docs(saved, collection=COLLECTION, chat=_chat(checkin)))
    data = docs.get(checkin)
    if not isinstance(data, dict) or not data.get("choice"):
        raise Stop(f"No choice for {checkin} is saved on the page (in the read saved at {saved.get('_at')}). If the user "
                   f"says they chose, read the page again (one unfiltered ArtifactData list of {COLLECTION}). "
                   f"{_chat(checkin)}")
    if data.get("ask") != ask["_id"] or data.get("checkin") != checkin:
        raise Stop(f"The choice saved for {checkin} was made on an earlier version of its question ({data.get('ask')!r}, "
                   f"not {ask['_id']}), so it is not an answer to the one open now. Ask the user to choose again on the "
                   f"page. {_chat(checkin)}")
    labels = {o["choice"]: o["label"] for o in ask["options"]}
    if data["choice"] not in labels:
        raise Stop(f"The choice saved for {checkin} ({data['choice']!r}) is not one the question offers "
                   f"({', '.join(labels)}). {_chat(checkin)}")
    detail, problems = details.check(((built or {}).get("offer") or {}).get(checkin) or {}, data.get("detail"))
    if problems:
        raise Stop(f"The page saved for {checkin} what its question did not offer ({'; '.join(problems[:3])}), so it "
                   f"is not taken as the user's answer. Ask the user to choose again on the latest page. {_chat(checkin)}")
    note = data.get("note")
    return {"checkin": checkin, "ask": ask["_id"], "choice": data["choice"], "label": labels[data["choice"]],
            "note": note if isinstance(note, str) else "", "detail": detail, "saved_at": data.get("saved_at"),
            "read": source.relative_to(run.path).as_posix()}


def from_page_note(note: str, lang: str = "en") -> str:
    tag = t("from_page", lang)
    return f"{note.strip()} {tag}" if note and note.strip() else tag


def record(run: RunFolder, checkin: str) -> dict:
    """Record the choice saved on the page with `flow.decide`, as an answer from chat, the note marked "(from the
    page)". A check-in decided before this question was put on the page is changed (`--change`)."""
    got = decision(run, checkin)
    words.reset()
    lang = words.page_lang(run).lang
    lines_of, files_of = RECORDED.get(state.load(run).playbook, (None, None))
    lines = lines_of(run, checkin, got, lang) if lines_of else []
    note = from_page_note("\n".join(x for x in [got["note"].strip(), *lines] if x), lang)
    decided = _latest_decisions(run)
    change = any(cid in decided for cid in _members(run, checkin))
    flow.decide(run, checkin, got["choice"], by="user", note=note, change=change)
    files = {"answer": _save_answer(run, checkin, got)} if got["detail"] else {}
    if files_of:
        files.update(files_of(run, checkin, got))
    return {**got, "recorded_note": note, "change": change, "files": files}


def _save_answer(run: RunFolder, checkin: str, got: dict) -> str:
    """The whole answer read from the page (choice, note, detail), kept as `03_wip/page/answer_<checkin>_vNN.json`."""
    target = run.next_version(ASKS, f"answer_{checkin}", "json")
    run.assert_writable(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    keep = {k: got[k] for k in ("checkin", "ask", "choice", "label", "note", "detail", "saved_at", "read")}
    target.write_text(json.dumps(keep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rel = f"{ASKS}/{target.name}"
    manifest.record(run, rel, "03_wip", ANSWER_SOURCE)
    return rel
