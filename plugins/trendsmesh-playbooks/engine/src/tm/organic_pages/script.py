"""The script to film (E3), as a page with a Markdown download: a port of the handoff's `tools/pb3/script_page.py`.

    check    `tm organic script check`: the script file `03_wip/script_<id>_<lang>_vNN.json` against the handoff's schema
             (`schemas/pb3_script.schema.json`, copied) and the plugin's rules; marks it `script`
    build    `tm organic page script`: `04_final/<id>_script_<lang>_vNN/index.html` and `<id>_script_<version>.md`

The page and the Markdown are the original's `render` and `to_md` as they are, except that the backslash in an
f-string expression (Python 3.12 only) is a variable (`md_js`). Proof: the ExampleEdu walkthrough's
`script_M5_en_v01.json` gives the handoff's packaged `04_final/M5_script_en_v01/index.html` and `M5_script_v01.md`
(tests/test_organic_script.py); the reference tool under Python 3.12 gives the same two files, so no golden is made.

The check holds, besides the schema (OV14 and the plan's Task 9):
- `lang` is the run's `page_lang`, unless the file's `plugin.lang_request` holds the user's words
  (an "English version" of a Polish channel's script);
- every fact has a `source` and a `url` (OV14);
- the lines said, in words, divided by the end of the last shot (`time`, "12–16 s" ends at 16) is at most
  `qa.wps_max` words a second (the voice-over rule, applied to the person who films);
- `hook.on_screen` is not empty;
- the posting kit passes `kit.check` as a kit filmed by a person (`filmed_by_person`, no AI label);
  the script has no kit file of its own, so the check builds one from the script's `kit` blocks
  (`language` = the script's, `plugin` = the script's `plugin` block, its trending sound and business
  alternative; `platforms` = the blocks it has);
- `generate_instead.cost`, when given, names `price_file` and `price_date` (an ISO date) with the amount `usd`.
"""

from __future__ import annotations

import dataclasses
import functools
import html
import json
import os
import re
import shutil
from datetime import date
from pathlib import Path

from tm import config, json_schema, kit, manifest, organic_proposals, page, state, stepchecks
from tm.config import Problem
from tm.organic_pages import lang_of
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

KEY = "script"                       # the stepchecks.mark key
WIP = "03_wip"
NAME = re.compile(rf"^{WIP}/script_(?P<id>[A-Za-z0-9][A-Za-z0-9_-]*)_(?P<lang>en|pl)_v(?P<n>\d{{2,}})\.json$")
FILE_PATTERN = f"{WIP}/script_<id>_<lang>_vNN.json"
SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "pb3_script.schema.json"
SOURCE = "tm organic page script"
_PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
_NUMBER = re.compile(r"(\d+):([0-5]\d(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)")   # m:ss, or seconds
_URL = re.compile(r"https?://\S+", re.IGNORECASE)


UI = {
 "en": {"eyebrow": "Organic AI video · script to film", "download": "⬇ Download script (.md)", "copy": "Copy", "copied": "Copied", "saved": "✓ Saved", "fail": "✕ Download failed",
        "length": "Length", "format": "Format", "goal": "Goal", "trends": "Built on", "hook": "Hook (first 2 seconds)", "on_screen": "On screen", "why": "Why it works",
        "shots": "Shot list", "time": "Time", "framing": "Framing", "action": "Action", "line": "Line", "filming": "Filming", "edit": "Edit", "sound": "Sound",
        "kit": "Posting kit", "facts": "Fact check (for you, not for the caption)", "gen": "Generate instead of filming (optional)", "host": "Host image prompt (GPT Image 2)",
        "video": "Video prompt (MiniMax H3)", "words": "words", "all_lines": "All lines (teleprompter)", "title": "Title", "caption": "Caption", "description": "Description",
        "hashtags": "Hashtags", "ai_label": "AI label", "pf": {"tiktok": "TikTok", "instagram": "Instagram Reels", "youtube": "YouTube Shorts", "facebook": "Facebook Reels"}},
 "pl": {"eyebrow": "Organiczne wideo AI · skrypt do nagrania", "download": "⬇ Pobierz skrypt (.md)", "copy": "Kopiuj", "copied": "Skopiowane", "saved": "✓ Zapisano", "fail": "✕ Nie udało się pobrać",
        "length": "Długość", "format": "Format", "goal": "Cel", "trends": "Na podstawie", "hook": "Hook (pierwsze 2 sekundy)", "on_screen": "Na ekranie", "why": "Dlaczego działa",
        "shots": "Lista ujęć", "time": "Czas", "framing": "Kadr", "action": "Akcja", "line": "Kwestia", "filming": "Nagrywanie", "edit": "Montaż", "sound": "Dźwięk",
        "kit": "Zestaw do publikacji", "facts": "Sprawdzenie faktów (dla Ciebie, nie do opisu)", "gen": "Wygeneruj zamiast nagrywać (opcjonalnie)", "host": "Prompt obrazu prowadzącej (GPT Image 2)",
        "video": "Prompt wideo (MiniMax H3)", "words": "słów", "all_lines": "Wszystkie kwestie (prompter)", "title": "Tytuł", "caption": "Opis", "description": "Opis",
        "hashtags": "Hashtagi", "ai_label": "Etykieta AI", "pf": {"tiktok": "TikTok", "instagram": "Instagram Reels", "youtube": "YouTube Shorts", "facebook": "Facebook Reels"}},
}


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def to_md(s: dict, t: dict) -> str:
    out = [f"# {s['title']}", "", f"{s['channel']} · {t['format']}: {s['format']} · {t['length']}: {s['length']}", "", f"**{t['goal']}:** {s['goal']}", "",
           f"## {t['hook']}", f"> {s['hook']['line']}", f"{t['on_screen']}: {s['hook']['on_screen']}", "", f"## {t['shots']}",
           f"| # | {t['time']} | {t['framing']} | {t['action']} | {t['line']} | {t['on_screen']} |", "|---|---|---|---|---|---|"]
    for sh in s["shots"]:
        out.append(f"| {sh['n']} | {sh['time']} | {sh['framing']} | {sh['action']} | {sh['line']} | {sh['on_screen']} |")
    out += ["", f"## {t['all_lines']}", " ".join(sh["line"] for sh in s["shots"] if sh["line"]), "", f"## {t['filming']}"] + [f"- {x}" for x in s["filming"]]
    out += ["", f"## {t['edit']}"] + [f"- {x}" for x in s["edit"]] + ["", f"## {t['kit']}"]
    for k, v in s["kit"].items():
        out.append(f"### {t['pf'][k]}")
        for f in ("title", "caption", "description", "hashtags", "ai_label", "sound"):
            if v.get(f):
                val = " ".join(v[f]) if isinstance(v[f], list) else v[f]
                out.append(f"**{t.get(f, f)}:**\n```\n{val}\n```" if f in ("title", "caption", "description", "hashtags") else f"**{t.get(f, f)}:** {val}")
    out += ["", f"## {t['facts']}"] + [f"- {f['claim']} ({f['source']}: {f['url']}). {f.get('note', '')}" for f in s.get("facts", [])]
    g = s.get("generate_instead")
    if g:
        out += ["", f"## {t['gen']}", g["note"], "", f"**{t['host']}:**", "```", g["host_image_prompt"], "```", f"**{t['video']}:**", "```", g["video_prompt"], "```"]
    return "\n".join(out) + "\n"


CSS = """:root{--bg:#F2F4F6;--surface:#fff;--ink:#13202A;--muted:#5A6977;--line:#D9DFE5;--accent:#B7791F;--accent-soft:#F6EBD9;
--display:"Bricolage Grotesque","Segoe UI",system-ui,sans-serif;--body:"Source Sans 3","Segoe UI",system-ui,sans-serif;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0E151B;--surface:#16212A;--ink:#E6ECF1;--muted:#97A6B3;--line:#283642;--accent:#E3A94B;--accent-soft:#2E2618;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0E151B;--surface:#16212A;--ink:#E6ECF1;--muted:#97A6B3;--line:#283642;--accent:#E3A94B;--accent-soft:#2E2618;color-scheme:dark}
*{box-sizing:border-box}html,body{overflow-x:hidden}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 var(--body)}
.wrap{max-width:980px;margin:0 auto;padding:28px 16px 64px;display:grid;gap:18px}
.eyebrow{font:600 13px/1 var(--body);letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
h1{font:700 clamp(26px,4vw,38px)/1.12 var(--display);margin:0}h2{font:700 20px/1.2 var(--display);margin:0}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px;display:grid;gap:10px;min-width:0}
.meta{color:var(--muted);margin:0}.hook{font:700 22px/1.3 var(--display);border-left:4px solid var(--accent);padding:6px 12px;background:var(--accent-soft);border-radius:0 8px 8px 0;margin:0}
.btn,.copy{font:600 14px/1 var(--body);padding:9px 14px;border-radius:8px;border:1px solid var(--line);background:var(--surface);color:var(--ink);cursor:pointer}
.btn.primary{background:var(--ink);color:var(--surface);border-color:var(--ink)}.copy{font-size:12px;padding:5px 8px}
.btn[hidden]{display:none}.btn:focus-visible,.copy:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.shots{display:grid;gap:10px}.shot{display:grid;grid-template-columns:72px 1fr;gap:4px 14px;border-top:1px solid var(--line);padding-top:10px}
.shot .t{font:700 15px/1.2 var(--display);color:var(--accent)}.shot .line{font-weight:600}.shot .k{color:var(--muted);font-size:14px}
@media (max-width:600px){.shot{grid-template-columns:1fr}}
ul{margin:0;padding-left:20px;display:grid;gap:4px}
.kit{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(260px,100%),1fr));gap:10px}
.pf{border:1px solid var(--line);border-radius:10px;padding:12px;display:grid;gap:8px;align-content:start;background:var(--bg)}
.fld{display:grid;gap:3px}.fld .k{font-size:12px;color:var(--muted);font-weight:600;letter-spacing:.04em;text-transform:uppercase;display:flex;justify-content:space-between;gap:6px;align-items:center}
pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.45 var(--body);background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:8px}
.status{font-size:13px;color:var(--muted)}"""


def field(fid: str, label: str, value: str, t: dict) -> str:
    return f'<div class="fld"><span class="k">{esc(label)} <button class="copy" type="button" data-src="{fid}">{t["copy"]}</button></span><pre id="{fid}">{esc(value)}</pre></div>'


_SCRIPT_BREAK = re.compile(r"</|<!--|<script", re.IGNORECASE)


def _js(value) -> str:
    """JSON for a <script> element. `</`, `<!--` and `<script` (any case) get a backslash after the `<`
    (`<\\/`: the original's own escape; `<\\!--`, `<\\script`: the same string in JavaScript), so no text can close the
    element or put the HTML parser in its double-escaped state."""
    return _SCRIPT_BREAK.sub(lambda m: "<\\" + m.group()[1:], json.dumps(value, ensure_ascii=False))


def render(s: dict, md_name: str, md: str) -> str:
    t = UI.get(s.get("lang", "en"), UI["en"])
    md_js = _js(md)   # a backslash cannot sit in an f-string expression before Python 3.12
    shots = "".join(f'<div class="shot"><span class="t">{esc(sh["time"])}</span><div><p class="line" style="margin:0">{esc(sh["line"]) or "—"}</p>'
                    f'<p class="k" style="margin:2px 0 0">{t["framing"]}: {esc(sh["framing"])}<br>{t["action"]}: {esc(sh["action"])}'
                    f'{"<br>" + t["on_screen"] + ": " + esc(sh["on_screen"]) if sh["on_screen"] else ""}</p></div></div>' for sh in s["shots"])
    lines = " ".join(sh["line"] for sh in s["shots"] if sh["line"])
    kit = ""
    for k, v in s["kit"].items():
        rows = "".join(field(f"k-{k}-{f}", t.get(f, f), " ".join(v[f]) if isinstance(v[f], list) else v[f], t) for f in ("title", "caption", "description", "hashtags") if v.get(f))
        rows += "".join(f'<p class="meta" style="font-size:14px">{t.get(f, f)}: {esc(v[f])}</p>' for f in ("ai_label", "sound") if v.get(f))
        kit += f'<div class="pf"><h2 style="font-size:16px">{t["pf"][k]}</h2>{rows}</div>'
    facts = "".join(f'<li>{esc(f["claim"])} <a href="{esc(f["url"])}" target="_blank" rel="noopener">{esc(f["source"])}</a>. {esc(f.get("note",""))}</li>' for f in s.get("facts", []))
    g = s.get("generate_instead")
    gen = (f'<section class="card"><h2>{t["gen"]}</h2><p class="meta">{esc(g["note"])}</p>{field("g-host", t["host"], g["host_image_prompt"], t)}{field("g-video", t["video"], g["video_prompt"], t)}</section>' if g else "")
    return f"""<!DOCTYPE html><html lang="{esc(s.get('lang','en'))}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(s['title'])}</title><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700&family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<header style="display:grid;gap:8px"><div class="eyebrow">{t['eyebrow']} · {esc(s['id'])} · {esc(s['date'])}</div><h1>{esc(s['title'])}</h1>
<p class="meta">{esc(s['channel'])} · {t['format']}: {esc(s['format'])} · {t['length']}: {esc(s['length'])} · {esc(s.get('word_count',''))} {t['words']}</p>
<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><button class="btn primary" id="dl" type="button" hidden>{t['download']}</button><span class="status" id="st" aria-live="polite"></span></div></header>
<section class="card"><p style="margin:0"><b>{t['goal']}:</b> {esc(s['goal'])}</p><p class="meta" style="margin:0">{t['trends']}: {esc('; '.join(s.get('trends', [])))}</p></section>
<section class="card"><h2>{t['hook']}</h2><p class="hook">{esc(s['hook']['line'])}</p><p class="meta" style="margin:0">{t['on_screen']}: {esc(s['hook']['on_screen'])} · {t['why']}: {esc(s['hook']['why'])}</p></section>
<section class="card"><h2>{t['shots']}</h2><div class="shots">{shots}</div>{field('all-lines', t['all_lines'], lines, t)}</section>
<section class="card"><h2>{t['filming']}</h2><ul>{''.join(f'<li>{esc(x)}</li>' for x in s['filming'])}</ul></section>
<section class="card"><h2>{t['edit']}</h2><ul>{''.join(f'<li>{esc(x)}</li>' for x in s['edit'])}</ul><p class="meta" style="margin:0">{t['sound']}: {esc(s['sound'])}</p></section>
<section class="card"><h2>{t['kit']}</h2><div class="kit">{kit}</div></section>
<section class="card"><h2>{t['facts']}</h2><ul>{facts}</ul></section>
{gen}
</div>
<script>window.__MD__ = {md_js}; window.__MDNAME__ = {_js(md_name)}; window.__T__ = {_js({k: t[k] for k in ('copy', 'copied', 'saved', 'fail')})};</script>
<script>
(function(){{
  const T = window.__T__;
  document.querySelectorAll('button.copy').forEach(b => b.addEventListener('click', async () => {{
    try {{ await navigator.clipboard.writeText(document.getElementById(b.dataset.src).innerText); b.textContent = T.copied; setTimeout(() => b.textContent = T.copy, 1200); }} catch (e) {{}}
  }}));
  (async () => {{
    for (let i = 0; i < 50 && !(window.claude && window.claude.use); i++) await new Promise(r => setTimeout(r, 200));
    let dls = null; try {{ dls = window.claude && window.claude.use ? await window.claude.use('downloads') : null; }} catch (e) {{ dls = null; }}
    if (!dls) return;
    const b = document.getElementById('dl'); const st = document.getElementById('st'); b.hidden = false;
    b.addEventListener('click', async () => {{
      try {{ await dls.save({{filename: window.__MDNAME__, data: window.__MD__}}); st.textContent = T.saved; }}
      catch (e) {{ st.textContent = (e && e.code === 'declined') ? '' : T.fail; }}
    }});
  }})();
}})();
</script></body></html>"""


# --- E3: the check -----------------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _schema() -> dict:
    return json_schema.load(SCHEMA)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def words_per_second(s: dict) -> tuple[int, float | None]:
    """The words of all the lines said, and the end time of the last shot in seconds (its `time`,
    "12–16 s": the last number; "1:02–1:10" ends at 70 s); None when that time holds no number."""
    said = sum(len(sh["line"].split()) for sh in s["shots"] if _text(sh.get("line")))
    ends = list(_NUMBER.finditer(str(s["shots"][-1].get("time")))) if s["shots"] else []
    if not ends:
        return said, None
    m = ends[-1]
    return said, (int(m[1]) * 60 + float(m[2].replace(",", ".")) if m[1] is not None else float(m[3].replace(",", ".")))


def _kit_of(s: dict) -> dict:
    """The posting kit the script's `kit` blocks make: the handoff's kit shape with the plugin block."""
    given = s.get("plugin") if isinstance(s.get("plugin"), dict) else {}
    return {"id": s["id"], "version": s["version"], "date": s["date"], "channel": s["channel"], "language": s["lang"],
            "video": f"{s['id']}_script", "platforms": s["kit"],
            "plugin": {"ai_label": False, "trending_sound": given.get("trending_sound"),
                       "business_alternative": given.get("business_alternative"), "platforms": list(s["kit"]),
                       "youtube_thumbnail": False}}


def _kit_context(run: RunFolder, s: dict) -> kit.KitContext:
    proposed = (run.path / organic_proposals.PROPOSAL_FILE).is_file()
    ctx = kit.context_of(run, language=s["lang"], ai_label="not_required",
                         product_level=None if proposed else "not shown")
    return dataclasses.replace(ctx, filmed_by_person=True)


def _lang_problem(s: dict, cfg: dict) -> Problem | None:
    """The script is in the run's page language, unless the user asked for the other one."""
    page_lang = cfg.get("page_lang")
    request = (s.get("plugin") or {}).get("lang_request") if isinstance(s.get("plugin"), dict) else None
    if s["lang"] == page_lang or _text(request):
        return None
    return Problem("lang", f"The script is in {s['lang']!r}, and this run's pages are in {page_lang!r} (config.yaml "
                           "page_lang).", f"Write it in {page_lang}, or, when the user asked for the other language, put "
                                          "their words in plugin.lang_request.")


def check(run: RunFolder, s: dict, cfg: dict) -> list[Problem]:
    """Everything wrong in a script file (the module docstring); empty when it holds. Reads only."""
    out: list[Problem] = []
    for line in json_schema.problems(s, _schema(), name="script"):
        field = line.split(" ", 1)[0].removeprefix("script.")
        todo = ("Name the source and its link for every fact (OV14); a fact without one is left out."
                if field.startswith("facts") else "Write the script in the shape of the script schema.")
        out.append(Problem(field, line, todo))
    if out:
        return out

    def bad(field: str, what: str, todo: str) -> None:
        out.append(Problem(field, what, todo))

    for key in ("id", "version"):
        if not _PART.fullmatch(s[key]):
            bad(key, f"The {key} {s[key]!r} is not letters, digits, _ and -.", f"Give the script a plain {key}.")
    wrong = _lang_problem(s, cfg)
    if wrong:
        out.append(wrong)
    for i, fact in enumerate(s.get("facts", [])):
        for field in ("source", "url"):
            if not _text(fact.get(field)):
                bad(f"facts[{i}].{field}", f"Fact {i + 1} has no {field}.", "Name the source and its link for every fact (OV14).")
        if _text(fact.get("url")) and not _URL.match(fact["url"].strip()):
            bad(f"facts[{i}].url", f"The link of fact {i + 1} is not a web address.", "Give the source's https link.")
    if not _text(s["hook"]["on_screen"]):
        bad("hook.on_screen", "The hook has no on-screen text.", "Write the hook's on-screen text: sound-off viewers read it.")
    if not s["shots"]:
        bad("shots", "The script has no shots.", "List the shots.")
    else:
        said, end = words_per_second(s)
        most = config.get(cfg, "qa.wps_max")
        if end is None or end <= 0:
            bad("shots", f"The last shot's time {s['shots'][-1]['time']!r} holds no end time.",
                "Write each shot's time as 12–16 s.")
        elif most is not None and said / end > most:
            bad("shots", f"The lines are {said} words in {end:g} s: {said / end:.1f} words a second, and at most {most:g} "
                "can be said.", "Cut words or lengthen the shots; a person filming it cannot say more.")
    gen = s.get("generate_instead")
    cost = gen.get("cost") if isinstance(gen, dict) else None
    if cost is not None:
        named = isinstance(cost, dict) and _text(cost.get("price_file")) and _text(cost.get("price_date"))
        try:
            named = named and bool(date.fromisoformat(str(cost["price_date"])))
        except (ValueError, TypeError):
            named = False
        if not named:
            bad("generate_instead.cost", "The cost names no price file and its date.",
                "Give cost: {usd, price_file, price_date}, from a saved price file (tm tool replicate_price), or leave the cost out.")
    try:
        ctx = _kit_context(run, s)
    except Stop as exc:
        bad("kit", str(exc).removesuffix(f" {AGAIN}").removesuffix(f"; {AGAIN}."), "Complete the channel profile, then check again.")
    else:
        for p in kit.check(_kit_of(s), ctx):
            bad(f"kit.{p.field}", p.what, p.todo)
    return out


def check_named(run: RunFolder, rel: str, s: object, cfg: dict) -> list[Problem]:
    """`check`, for the file `rel`: its name must be script_<id>_<lang>_vNN.json and say what it holds."""
    found = NAME.fullmatch(rel)
    if not found:
        return [Problem("file", f"The script is written as {FILE_PATTERN}; {rel} is not.", f"Write it as {FILE_PATTERN}.")]
    if not isinstance(s, dict):
        return [Problem("script", "The script is not one JSON object.", "Write one JSON object.")]
    out = check(run, s, cfg)
    for key, name in (("id", found["id"]), ("lang", found["lang"]), ("version", f"v{int(found['n']):02d}")):
        if s.get(key) != name:
            out.append(Problem(key, f"The file name says {name!r} and the script's {key} is {s.get(key)!r}.",
                               "Make the name and the script agree."))
    proposal = (state.load(run).organic or {}).get("proposal")
    if isinstance(proposal, str) and str(s.get("id")).lower() != proposal.lower():
        out.append(Problem("id", f"This production run was started for {proposal}, and the script is for "
                                 f"{s.get('id')!r}.",
                           f"Write the script for {proposal} in this run; another idea's script goes in its own run."))
    return out


def checked_gap(run: RunFolder) -> str | None:
    """The `script_checked` step check: the script's latest 03_wip/script_<id>_<lang>_vNN.json passed
    `tm organic script check` and is unchanged since. Reads only."""
    entry = state.load(run).checked.get(KEY)
    found = NAME.fullmatch(str((entry or {}).get("file") or ""))
    if found is None:
        return f"a script ({FILE_PATTERN}) is written and checked (tm organic script check)"
    gap = stepchecks.fresh(run, KEY, WIP, f"script_{found['id']}_{found['lang']}", "json")
    if gap is not None:
        return gap
    try:   # the language rule depends on the config, which may have changed since the check
        data = json.loads((run.path / entry["file"]).read_text(encoding="utf-8-sig"))
        wrong = _lang_problem(data, config.load(run))
    except (OSError, ValueError, KeyError, TypeError):
        return "the checked script can be read (tm organic script check)"
    return f"the script is in the run's page language again ({wrong.what}) and checked (tm organic script check)" if wrong else None


def built_gap(run: RunFolder) -> str | None:
    """The `script_page_built` step check: a page folder is built from the checked script, unchanged
    since. Reads only."""
    if checked_gap(run) is not None:
        return "the script is checked (tm organic script check) and the page is built from it (tm organic page script)"
    checked = state.load(run).checked[KEY]["file"]
    sha = stepchecks.sha256(run.path / checked)
    for row in reversed(manifest.rows(run)):
        if row["source"] != SOURCE or row["parent"] != checked:
            continue
        try:
            params = json.loads(row["params"]) if row["params"] else {}
        except ValueError:
            continue
        if isinstance(params, dict) and params.get("script_sha256") == sha and (run.path / row["file"]).is_dir():
            return None
    return f"the script page is built from the checked script, {checked} (tm organic page script)"


# --- E3: the page ------------------------------------------------------------------------------------

def _rel(run: RunFolder, path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        raise ValueError(f"{path} is not inside the run folder {run.path}.") from None


def build(run: RunFolder, file: Path) -> dict:
    """Build the page and its Markdown from the checked script `file` into a new
    `04_final/<id>_script_<lang>_vNN/`. A Stop before the script is checked, when `file` is not the
    checked script, when the script is not in the page's shape, and when the files would be over
    the Artifact tool's limits (nothing is written then)."""
    rel = _rel(run, file)
    gap = checked_gap(run)
    if gap is not None:
        raise Stop(f"The page is built from a checked script, and E3 is done once {gap}. Check it, then build again; {AGAIN}.")
    checked = state.load(run).checked[KEY]["file"]
    if rel != checked:
        raise Stop(f"{rel} is not the checked script ({checked}): check it first (tm organic script check), then build "
                   f"the page from it; {AGAIN}.")
    path = run.path / rel
    try:
        s = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise Stop(f"{rel} cannot be read ({exc}); check it again; {AGAIN}.") from None
    lang = lang_of(s)
    t = UI[lang]
    md_name = f"{page.asset_name(s['id'])}_script_{page.asset_name(s['version'])}.md"
    try:
        md = to_md(s, t)
        text = render(s, md_name, md)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        raise Stop(f"{rel} is not in the page's shape ({type(exc).__name__}: {exc}); check it again; {AGAIN}.") from None
    over = page.over_limits({"index.html": len(text.encode("utf-8")), md_name: len(md.encode("utf-8"))})
    if over:
        raise Stop(f"The page would be too big to publish as one artifact: {over}. Nothing was written. Shorten the script, "
                   f"check it again and build again; {AGAIN}.")
    out = page.new_folder(run, f"{s['id']}_script_{lang}")
    try:   # both files or neither: written under hidden temporary names, then moved into place
        for name, body in (("index.html", text), (md_name, md)):
            with open(out / f".{name}.tmp", "x", encoding="utf-8", newline="\n") as fh:
                fh.write(body)
        for name in ("index.html", md_name):
            os.replace(out / f".{name}.tmp", out / name)
    except OSError:
        shutil.rmtree(out, ignore_errors=True)
        raise
    out_rel = out.relative_to(run.path).as_posix()
    manifest.record(run, out_rel, page.FINAL, SOURCE, parent=rel, params={"script_sha256": stepchecks.sha256(path), "lang": lang})
    return {"folder": out_rel, "files": page.files(out), "script": rel, "lang": lang, "markdown": md_name}
