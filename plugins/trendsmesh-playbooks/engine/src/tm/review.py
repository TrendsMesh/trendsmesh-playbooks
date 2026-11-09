"""The local review page: `<run>/review/index.html`, a static read-only view for the browser.

It shows before/after video pairs with one shared play/seek control, frame grids and QA strips
(images under `03_wip/`, listed by folder), the strategy brief's change register (latest
`04_final/strategy_brief*.md`, shown as escaped preformatted text, not rendered markdown) and the
decision log from run.json. Decisions are still made in chat.

The page is a generated view, not an asset: it is regenerated each time and `review/index.html` is
overwritten on purpose (it never goes through versioning). Every path in it is relative to
`review/` and URL-encoded, so the run folder can move; everything inserted is HTML-escaped; no
external resources are loaded.

Pairing, from the manifest's before/after cell: `after (before: <path>)` pairs that row's file with
<path>; `before: <path> / after: <path>` names both.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from string import Template
from urllib.parse import quote

from tm import cli, manifest, state
from tm.runfolder import RunFolder

VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_AFTER_OF = re.compile(r"^after \(before: (.+)\)$")
_BOTH = re.compile(r"^before: (.+?) / after: (.+)$")


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _url(rel: str) -> str:
    return "../" + quote(rel.replace("\\", "/"), safe="/")


def pairs(run: RunFolder) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for row in manifest.rows(run):
        cell = row["before/after"].strip()
        if m := _AFTER_OF.match(cell):
            pair = (m.group(1).strip(), row["file"])
        elif m := _BOTH.match(cell):
            pair = (m.group(1).strip(), m.group(2).strip())
        else:
            continue
        if pair not in found:
            found.append(pair)
    return found


def _pairs_html(run: RunFolder) -> str:
    out = []
    for before, after in pairs(run):
        out.append(
            '<div class="pair"><div class="players">'
            f'<figure><video preload="metadata" muted src="{_e(_url(before))}"></video><figcaption>Before: {_e(before)}</figcaption></figure>'
            f'<figure><video preload="metadata" muted src="{_e(_url(after))}"></video><figcaption>After: {_e(after)}</figcaption></figure>'
            '</div><div class="controls"><button class="play" type="button">Play</button>'
            '<input class="seek" type="range" min="0" max="1000" value="0"></div></div>')
    return "\n".join(out) or '<p class="muted">No before/after pairs yet.</p>'


def _grids_html(run: RunFolder) -> str:
    wip = run.path / "03_wip"
    folders: dict[str, list[Path]] = {}
    if wip.is_dir():
        for p in sorted(wip.rglob("*")):
            if p.is_file() and p.suffix.lower() in IMAGE_EXT:
                folders.setdefault(p.parent.relative_to(run.path).as_posix(), []).append(p)
    out = []
    for folder, files in folders.items():
        figs = "".join(
            f'<figure><a href="{_e(_url(f.relative_to(run.path).as_posix()))}"><img loading="lazy" '
            f'src="{_e(_url(f.relative_to(run.path).as_posix()))}" alt="{_e(f.name)}"></a>'
            f'<figcaption>{_e(f.name)}</figcaption></figure>' for f in files)
        out.append(f"<h3>{_e(folder)}</h3><div class=\"grid\">{figs}</div>")
    return "\n".join(out) or '<p class="muted">No frame grids or QA strips yet.</p>'


def _register_html(run: RunFolder) -> str:
    final = run.path / "04_final"
    briefs = sorted(final.glob("strategy_brief*.md")) if final.is_dir() else []
    if not briefs:
        return '<p class="muted">No strategy brief yet.</p>'
    latest = briefs[-1]
    text = latest.read_text(encoding="utf-8", errors="replace")
    return f'<p class="muted">{_e(latest.name)}</p><pre>{_e(text)}</pre>'


def _decisions_html(run: RunFolder) -> str:
    decisions = state.load(run).decisions
    if not decisions:
        return '<p class="muted">No decisions yet.</p>'
    head = "".join(f"<th>{h}</th>" for h in ("When", "Check-in", "Choice", "By", "Rule", "Note", "Change"))
    body = "".join(
        "<tr>" + "".join(f"<td>{_e(d.get(k) or '')}</td>"
                         for k in ("at", "checkin", "choice", "by", "rule", "note", "change")) + "</tr>"
        for d in decisions)
    return f"<table><tr>{head}</tr>{body}</table>"


def build(run: RunFolder) -> Path:
    template = Template((Path(__file__).with_name("review_template.html")).read_text(encoding="utf-8"))
    page = template.substitute(
        run_id=_e(run.path.name), pairs=_pairs_html(run), grids=_grids_html(run),
        register=_register_html(run), decisions=_decisions_html(run))
    target = run.path / "review" / "index.html"
    target.parent.mkdir(exist_ok=True)
    target.write_text(page, encoding="utf-8")
    return target


def _setup_cli(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="kind", metavar="build")
    s = sub.add_parser("build")
    s.add_argument("--run", required=True)
    s.add_argument("--json", action="store_true")


def _run_cli(a: argparse.Namespace) -> int:
    if a.kind != "build":
        print("Use: tm review build --run RUN [--json]")
        return 1
    try:
        path = build(RunFolder.open(Path(a.run)))
    except (OSError, ValueError, KeyError) as exc:
        return cli.fail(a, f"Could not build the review page: {exc}")
    cli.emit(a, {"status": "done", "path": str(path)}, str(path))
    return 0


cli.register("review", _setup_cli, _run_cli)
