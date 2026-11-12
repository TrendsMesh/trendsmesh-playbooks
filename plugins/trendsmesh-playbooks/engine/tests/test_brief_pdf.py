"""The brief page's PDFs (issue #10): printed at build time, the print mode they are printed from, the buttons that
download them, and CB13 on the creator PDF's text.

A made-up brief, public (`test_brief_creator_view._brief`). The browser is faked (conftest finds none outside the
`video` tests): a fake printer writes a small PDF per key, so the build is tested without Chrome. The real print is
the `video` test at the end.
"""

import copy
import json
import re
import struct
import subprocess
import time
import types
import zlib
from pathlib import Path

import pytest

from conftest import video_asked_for
from test_brief_creator_view import _brief
from tm import atlas, brief_checks, brief_page, brief_pdf, manifest, page
from tm.cli import main
from tm.playbooks import CREATIVE_BRIEF
from tm.runfolder import RunFolder


# --- a PDF the way Skia writes one: Type0 fonts with a ToUnicode map, Flate streams -----------------------------

def _cmap(chars: str) -> bytes:
    """A ToUnicode map: glyph i+1 -> chars[i], half by bfchar, half by bfrange."""
    pairs = [(i + 1, ch) for i, ch in enumerate(chars)]
    half = len(pairs) // 2
    bfchar = "".join(f"<{g:04X}> <{ord(ch):04X}>\n" for g, ch in pairs[:half])
    bfrange = "".join(f"<{g:04X}> <{g:04X}> <{ord(ch):04X}>\n" for g, ch in pairs[half:])
    return ("/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n1 begincodespacerange\n<0000> <FFFF>\n"
            f"endcodespacerange\n{half} beginbfchar\n{bfchar}endbfchar\n{len(pairs) - half} beginbfrange\n{bfrange}"
            "endbfrange\nendcmap\nend\nend\n").encode()


def _obj(n: int, body: bytes, stream: bytes | None = None, flate: bool = True) -> bytes:
    if stream is None:
        return b"%d 0 obj\n%s\nendobj\n" % (n, body)
    data = zlib.compress(stream) if flate else stream
    head = body[:-2] + (b" /Filter /FlateDecode" if flate else b"") + b" /Length %d>>" % len(data)
    return b"%d 0 obj\n%s stream\n%s\nendstream\nendobj\n" % (n, head, data)


def make_pdf(pages: list[list[str]], *, flate: bool = True) -> bytes:
    """A PDF whose pages show these lines, each line one text object at its own baseline (a line holding a tab
    is two text objects on one baseline, the second in a bold font)."""
    chars = sorted({ch for lines in pages for line in lines for ch in line if ch != "\t"})
    glyph = {ch: i + 1 for i, ch in enumerate(chars)}
    hexed = lambda t: "<" + "".join(f"{glyph[ch]:04X}" for ch in t) + ">"   # noqa: E731
    out = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n", _obj(1, b"<</Type /Catalog /Pages 2 0 R>>"),
           _obj(3, b"<</Type /Font /Subtype /Type0 /BaseFont /AAAAAA+Sans /Encoding /Identity-H /ToUnicode 4 0 R>>"),
           _obj(4, b"<<>>", _cmap("".join(chars)), flate),
           _obj(5, b"<</Type /Font /Subtype /Type0 /BaseFont /BAAAAA+Sans-Bold /Encoding /Identity-H /ToUnicode 4 0 R>>")]
    kids = []
    for p, lines in enumerate(pages):
        page_n, content_n = 10 + 2 * p, 11 + 2 * p
        kids.append(b"%d 0 R" % page_n)
        ops = []
        for i, line in enumerate(lines):
            y = 50 + 20 * i
            parts = line.split("\t")
            ops.append(f"BT\n/F1 12 Tf\n1 0 0 -1 8 {y} Tm\n[{hexed(parts[0])}] TJ\nET")
            for k, extra in enumerate(parts[1:], 1):
                ops.append(f"BT\n/F2 12 Tf\n1 0 0 -1 {100 * k} {y} Tm\n{hexed(extra)} Tj\nET")
        out.append(_obj(page_n, b"<</Type /Page /Parent 2 0 R /Resources <</Font <</F1 3 0 R /F2 5 0 R>>>> "
                                b"/Contents %d 0 R>>" % content_n))
        out.append(_obj(content_n, b"<<>>", "\n".join(ops).encode(), flate))
    out.insert(2, _obj(2, b"<</Type /Pages /Count %d /Kids [%s]>>" % (len(kids), b" ".join(kids))))
    return b"".join(out) + b"trailer\n<</Root 1 0 R>>\n%%EOF\n"


def test_pdf_text_reads_skia_fonts_pages_and_lines(tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(make_pdf([["View: Creator", "Zażółć gęślą jaźń: cost"], ["per day", "Lumen\t. A lamp"]]))
    assert brief_pdf.text(f) == "View: Creator\nZażółć gęślą jaźń: cost\nper day\nLumen . A lamp"
    assert brief_pdf.text(f, "").splitlines()[-1] == "Lumen. A lamp"     # one baseline: the fonts' objects joined
    f.write_bytes(make_pdf([["plain streams too"]], flate=False))
    assert brief_pdf.text(f) == "plain streams too"
    f.write_bytes(b"<html>not a pdf</html>")
    with pytest.raises(ValueError):
        brief_pdf.text(f)


def test_pdf_text_takes_a_ligature_and_actual_text(tmp_path):
    f = tmp_path / "a.pdf"
    stream = (b"BT\n/F1 12 Tf\n1 0 0 -1 8 50 Tm\n(of) Tj\n/Span<</ActualText (fi) >> BDC\n<0001> Tj\nEMC\n(ce) Tj\nET")
    pdf = (b"%PDF-1.4\n" + _obj(1, b"<</Type /Page /Resources <</Font <</F1 2 0 R>>>> /Contents 3 0 R>>")
           + _obj(2, b"<</Type /Font /Subtype /Type1 /BaseFont /Helvetica>>") + _obj(3, b"<<>>", stream) + b"%%EOF\n")
    f.write_bytes(pdf)
    assert brief_pdf.text(f) == "office"                                  # the span's text, not its glyph
    f.write_bytes(make_pdf([["ﬁve"]]))                               # the ligature glyph: its letters
    assert brief_pdf.text(f) == "five"


# --- the build ------------------------------------------------------------------------------------------------------

@pytest.fixture
def run(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    from datetime import date
    return RunFolder.create(ws, "lumen", date(2026, 11, 1), playbook=CREATIVE_BRIEF)


def _png(width: int = 4, height: int = 7) -> bytes:
    row = b"\x00" + b"\x30\x60\x90" * width
    chunk = lambda kind, data: (struct.pack(">I", len(data)) + kind + data   # noqa: E731
                                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(row * height)) + chunk(b"IEND", b""))


def _with_animatics(run: RunFolder, brief: dict, *, stills: bool = True) -> dict:
    """The brief with two concepts, each naming a 9:16 animatic rendered into the run, with its five stills."""
    brief = copy.deepcopy(brief)
    second = copy.deepcopy(brief["concepts"][0])
    second.update(id="C2", title="Second concept")
    brief["concepts"].append(second)
    for c in brief["concepts"]:
        name = f"{c['id']}_animatic_9x16_v01.mp4"
        c["animatic"] = {"9x16": f"animatic/{name}", "default": "9x16"}
        mp4 = run.path / brief_page.RENDERS / name
        mp4.parent.mkdir(parents=True, exist_ok=True)
        mp4.write_bytes(b"mp4")
        for still in atlas.still_paths(mp4) if stills else []:
            still.write_bytes(_png())
    return brief


def _write_brief(run: RunFolder, brief: dict, n: int = 1) -> Path:
    path = run.path / "04_final" / f"brief_pack_v{n:02d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
    return path


class FakePrinter:
    """`brief_pdf.print_pdf` without a browser: a PDF per key showing `texts[key]` (default "View: <key>"),
    each call recorded with the print page and its key."""

    def __init__(self, texts: dict[str, str] | None = None, fail_on: str | None = None, size: int = 0):
        self.texts, self.fail_on, self.size, self.calls = texts or {}, fail_on, size, []

    def __call__(self, browser, page_path, key, out):
        self.calls.append((Path(page_path), key, Path(out)))
        if key == self.fail_on:
            raise ValueError(f"the browser wrote no {Path(out).name}")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(make_pdf([self.texts.get(key, f"View: {key}").splitlines()]) + b"%" * self.size)


@pytest.fixture
def printer(monkeypatch):
    fake = FakePrinter()
    monkeypatch.setattr(brief_pdf, "browser", lambda: Path("/Applications/Chrome"))
    monkeypatch.setattr(brief_pdf, "print_pdf", fake)
    return fake


VIEWS = ["decision", "strategy", "creator"]
PDFS = ["pdf/brief_pack-full.pdf", "pdf/brief_pack-decision.pdf", "pdf/brief_pack-strategy.pdf",
        "pdf/brief_pack-creator.pdf"]


def test_page_prints_the_full_report_and_one_pdf_per_view(run, printer, capsys):
    _write_brief(run, _with_animatics(run, _brief()))
    assert main(["brief", "page", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    folder = run.path / out["folder"]
    assert out["pdfs"] == [f"{out['folder']}/{p}" for p in PDFS] and out["pdf_note"] is None
    assert [key for _, key, _ in printer.calls] == ["full", *VIEWS]
    assert {p for p, _, _ in printer.calls} == {folder / ".print" / "print.html"}   # one print page, a key each
    assert "Printed 4 PDFs" in out["message"] and "downloads" in out["message"]
    # published with the page; the print page and its stills are not
    served = [f["as"] for f in page.files(folder)]
    assert served[0] == "index.html" and set(PDFS) <= set(served)
    assert not any(s.startswith(".print") for s in served)
    # a manifest row per PDF, and the page's row (still the last: decided_page reads it) lists them
    rows = manifest.rows(run)
    assert [r["file"] for r in rows if r["source"] == brief_page.PDF_SOURCE] == [f"{out['folder']}/{p}" for p in PDFS]
    assert rows[-1]["source"] == brief_page.SOURCE
    assert json.loads(rows[-1]["params"])["pdfs"] == dict(zip(["full", *VIEWS], PDFS))
    assert brief_page.built_gap(run) is None and brief_page.decided_page(run)["page"] == out["folder"]


def test_print_page_shows_stills_a_banner_and_no_forms(run, printer, capsys):
    _write_brief(run, _with_animatics(run, _brief()))
    assert main(["brief", "page", "--run", str(run.path), "--json"]) == 0
    folder = run.path / json.loads(capsys.readouterr().out)["folder"]
    text = (folder / ".print" / "print.html").read_text(encoding="utf-8")
    assert "<video" not in text and 'class="toggle"' not in text           # stills, not the animatics
    shots = re.findall(r'<img[^>]* src="(stills/[^"]+)"', text)
    stills = sorted(p.name for p in (folder / ".print" / "stills").iterdir())
    assert len(stills) == 10 and all(s.endswith(".jpg") for s in stills)  # five per animatic, as JPEGs
    assert set(shots) == {f"stills/{s}" for s in stills}
    assert (folder / ".print" / "stills" / stills[0]).read_bytes()[:2] == b"\xff\xd8"
    assert text.count(brief_page.PDF_WORDS["stills"]) == 2                # the caption under each concept's stills
    assert 'src="../animatic/' not in text                                # no video left to point at
    for key, label in (("full", "Full report"), ("creator", "View: Creator"), ("decision", "View: Decision maker")):
        assert f'<div class="print-banner" data-print="{key}" hidden>{label}</div>' in text
    assert "@page{size:A4" in text and "print-color-adjust:exact" in text and "break-inside:avoid" in text
    for hidden in (".viewbar", "aside", ".decide", ".decisions"):
        assert f"body.print {hidden}" in text
    assert "location.hash.match(/^#print-" in text and "vb-dl" not in text


def test_print_mode_shows_one_view_or_every_view():
    """What each print shows is what showView shows; the full report shows every element of a ticked view."""
    brief = _brief()
    text, views = brief_page.render(brief, stills={})
    script = text[text.index("// print mode"):]
    assert "showView(key)" in script and "RECIPIENTS.includes(x)" in script
    creator = " ".join(brief_page.view_text(brief, "creator"))
    assert "Your part" in creator and "Your decision on C1" not in creator


def test_buttons_download_on_claude_ai_and_open_the_file_elsewhere(run, printer, capsys):
    _write_brief(run, _with_animatics(run, _brief()))
    assert main(["brief", "page", "--run", str(run.path), "--json"]) == 0
    folder = run.path / json.loads(capsys.readouterr().out)["folder"]
    text = (folder / "index.html").read_text(encoding="utf-8")
    assert '<button type="button" class="vb-dl" data-file="pdf/brief_pack-full.pdf">Download full report (PDF)</button>' in text
    for view in VIEWS:          # one button per view, shown with its view (the page hides the others)
        label = brief_page.VIEW_LABEL[view]
        assert (f'<button type="button" class="vb-dl" data-v="{view}" data-file="pdf/brief_pack-{view}.pdf">'
                f'Download {label} view (PDF)</button>') in text
    assert brief_page.E(brief_page.PDF_WORDS["hint"]) in text and "Share, then Copy link" not in text
    script = text[text.index("// the PDFs (issue #10)"):]
    assert "window.claude.use('downloads')" in script and "dls.save({ filename:" in script
    assert "location.protocol === 'file:'" in script and "window.open(b.dataset.file" in script
    assert "say(note.dataset.unavailable)" in script and "e.code === 'declined'" in script
    note = re.search(r'<span class="vb-hint vb-dl-note"[^>]*>', text).group(0)
    assert brief_page.E(brief_page.PDF_WORDS["unavailable"]) in note and " hidden" in note
    # the buttons sit outside .vb-buttons, whose buttons without a view the page's script removes
    bar = re.search(r'<div class="vb-buttons">(.*?)</div>', text).group(1)
    assert "vb-dl" not in bar
    for view in VIEWS:
        parser = brief_page._ViewText(view)
        parser.feed(text)
        shown = " ".join(parser.texts)
        assert ("Download Creator view (PDF)" in shown) == (view == "creator") and "Download full report" in shown


def test_no_browser_builds_the_page_without_pdfs(run, capsys):
    _write_brief(run, _with_animatics(run, _brief()))
    assert main(["brief", "page", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    folder = run.path / out["folder"]
    assert out["pdfs"] == [] and "no Chrome or Edge" in out["pdf_note"] and "No PDFs" in out["message"]
    assert not (folder / "pdf").exists() and not (folder / ".print").exists()
    text = (folder / "index.html").read_text(encoding="utf-8")
    assert "vb-dl" not in text and "// the PDFs" not in text
    assert brief_page.E(brief_page.PDF_WORDS["hint_no_pdf"]) in text and "Share, then Copy link" not in text
    assert json.loads(manifest.rows(run)[-1]["params"])["pdfs"] == {}


def test_a_failed_print_or_pdfs_over_the_limits_leave_them_out(run, monkeypatch, capsys):
    monkeypatch.setattr(brief_pdf, "browser", lambda: Path("/Applications/Chrome"))
    _write_brief(run, _with_animatics(run, _brief()))
    monkeypatch.setattr(brief_pdf, "print_pdf", FakePrinter(fail_on="creator"))
    assert main(["brief", "page", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["pdfs"] == [] and "printing them failed" in out["pdf_note"] and "brief_pack-creator.pdf" in out["pdf_note"]
    assert not (run.path / out["folder"] / "pdf").exists()                # never a part of the set

    def broken(*args):
        raise PermissionError("the folder is read-only")
    monkeypatch.setattr(brief_pdf, "print_pdf", broken)
    assert main(["brief", "page", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["pdfs"] == [] and "read-only" in out["pdf_note"]
    assert (run.path / out["folder"] / "index.html").is_file()           # the page all the same
    monkeypatch.setattr(brief_pdf, "print_pdf", FakePrinter(size=10**6))
    monkeypatch.setattr(page, "MAX_TOTAL_BYTES", 2 * 10**6)
    assert main(["brief", "page", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["pdfs"] == [] and "too big to publish" in out["pdf_note"]
    assert not (run.path / out["folder"] / "pdf").exists() and page.files(run.path / out["folder"])


def test_a_rebuild_prints_the_pdfs_again_under_the_same_names(run, printer, capsys):
    _write_brief(run, _with_animatics(run, _brief()))
    assert main(["brief", "page", "--run", str(run.path), "--json"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert main(["brief", "page", "--run", str(run.path), "--json"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["folder"] != first["folder"]
    # served at the same paths, so a publish to the same link replaces each PDF
    assert [p.split("/", 2)[2] for p in second["pdfs"]] == [p.split("/", 2)[2] for p in first["pdfs"]] == PDFS


def test_a_page_with_one_view_gets_the_download_bar_alone(run, printer, capsys):
    brief = _with_animatics(run, _brief())
    brief["meta"]["recipients"] = ["creator"]
    _write_brief(run, brief)
    assert main(["brief", "page", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [Path(p).name for p in out["pdfs"]] == ["brief_pack-full.pdf", "brief_pack-creator.pdf"]
    text = (run.path / out["folder"] / "index.html").read_text(encoding="utf-8")
    assert 'class="viewbar"' in text and 'class="vb-buttons"' not in text and "vb-dl" in text
    assert 'class="viewbar"' not in brief_page.render(brief)[0]           # no PDFs, one view: no bar, as before


def test_stills_missing_print_without_them(run, printer, capsys):
    _write_brief(run, _with_animatics(run, _brief(), stills=False))
    assert main(["brief", "page", "--run", str(run.path), "--json"]) == 0
    folder = run.path / json.loads(capsys.readouterr().out)["folder"]
    text = (folder / ".print" / "print.html").read_text(encoding="utf-8")
    assert "<video" not in text and 'class="stills"' not in text and len(printer.calls) == 4


def _absolute_only_browser(monkeypatch) -> list[list[str]]:
    """The real `print_pdf` with a fake browser that, like Chrome on Windows, writes no PDF to a relative
    `--print-to-pdf` path (issue #54): the argv of each call is kept."""
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        out = Path(next(a for a in argv if a.startswith("--print-to-pdf=")).split("=", 1)[1])
        if out.is_absolute():
            out.write_bytes(make_pdf([["View"]]))
        return types.SimpleNamespace(returncode=0, stdout="", stderr="" if out.is_absolute() else
                                     f"Failed to write file {out}: The system cannot find the path specified.")
    monkeypatch.setattr(brief_pdf, "browser", lambda: Path("/Applications/Chrome"))
    monkeypatch.setattr(brief_pdf, "subprocess", types.SimpleNamespace(
        run=run, TimeoutExpired=subprocess.TimeoutExpired, CalledProcessError=subprocess.CalledProcessError))
    monkeypatch.setattr(brief_pdf, "WAIT_S", 2)
    monkeypatch.setattr(brief_pdf, "time", types.SimpleNamespace(monotonic=time.monotonic, sleep=lambda s: None))
    return calls


def test_a_relative_run_path_prints_every_pdf(run, monkeypatch, capsys):
    """`tm brief page --run <relative path>`: the browser is given absolute paths, so all four PDFs print."""
    calls = _absolute_only_browser(monkeypatch)
    _write_brief(run, _with_animatics(run, _brief(), stills=False))
    monkeypatch.chdir(run.path.parent)
    assert main(["brief", "page", "--run", run.path.name, "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["pdf_note"] is None and [p.split("/", 2)[2] for p in out["pdfs"]] == PDFS
    assert len(calls) == 4
    for argv in calls:
        out_arg = next(a for a in argv if a.startswith("--print-to-pdf=")).split("=", 1)[1]
        assert Path(out_arg).is_absolute() and argv[-1].startswith("file:")
    assert "vb-dl" in (run.path / out["folder"] / "index.html").read_text(encoding="utf-8")


def test_no_pdfs_tells_the_user_the_page_has_no_download_buttons(run, monkeypatch, capsys):
    """A print that fails is never silent: the answer says to tell the user the page has no download buttons,
    and why."""
    monkeypatch.setattr(brief_pdf, "browser", lambda: Path("/Applications/Chrome"))
    monkeypatch.setattr(brief_pdf, "print_pdf", FakePrinter(fail_on="full"))
    _write_brief(run, _with_animatics(run, _brief()))
    assert main(["brief", "page", "--run", str(run.path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["pdfs"] == []
    assert "Tell the user" in out["message"] and "no download buttons" in out["message"]
    assert "brief_pack-full.pdf" in out["message"]                       # why: the print's own error


def test_capabilities_declare_the_downloads(capsys):
    assert main(["brief", "capabilities", "--json"]) == 0
    caps = json.loads(capsys.readouterr().out)["capabilities"]
    assert caps["downloads"] is True and set(caps) == {"db", "user", "downloads"}


# --- CB13 on the creator PDF ----------------------------------------------------------------------------------------

def _said(problems) -> str:
    return "\n".join(f"{p.field}: {p.what}" for p in problems)


def _built_with(run, monkeypatch, creator_text: str) -> dict:
    monkeypatch.setattr(brief_pdf, "browser", lambda: Path("/Applications/Chrome"))
    monkeypatch.setattr(brief_pdf, "print_pdf", FakePrinter({"creator": creator_text}))
    brief = _with_animatics(run, _brief())
    _write_brief(run, brief)
    brief_page.build(run)
    return brief


def test_production_check_reads_the_creator_pdf(run, monkeypatch):
    brief = _built_with(run, monkeypatch, "View: Creator\nYour part\nKeep the spend low")
    said = _said(brief_checks._production_checks(run, brief, {}))
    assert "creator PDF" in said and '"spend"' in said and "pdf/brief_pack-creator.pdf" in said
    # a word whose letters change font: the text objects on one baseline, joined
    brief = _built_with(run, monkeypatch, "View: Creator\nOur CT\tR doubled")
    assert '"ctr"' in _said(brief_checks._production_checks(run, brief, {}))


def test_production_check_passes_a_clean_creator_pdf_and_keeps_the_usage_exception(run, monkeypatch):
    brief = _built_with(run, monkeypatch, "View: Creator\nYour part\nDay one.")
    assert brief_checks._production_checks(run, brief, {}) == []
    usage = "12 months of paid use, 1,100 PLN"
    brief = _with_animatics(run, _brief())
    brief["concepts"][0]["creator"]["usage"] = usage
    brief["concepts"][1]["creator"]["usage"] = usage
    monkeypatch.setattr(brief_pdf, "print_pdf", FakePrinter({"creator": f"Deadline: to set. Usage: {usage}."}))
    _write_brief(run, brief, 2)
    brief_page.build(run)
    assert brief_checks._production_checks(run, brief, {}) == []


def test_production_check_names_a_word_once_and_refuses_an_unreadable_pdf(run, monkeypatch):
    brief = _built_with(run, monkeypatch, "View: Creator\nLower cost per checkout")
    changed = copy.deepcopy(brief)
    changed["concepts"][0]["key_message"] = "Lower cost per checkout"
    path = _write_brief(run, changed, 2)
    brief_page.build(run, path)
    problems = brief_checks._production_checks(run, changed, {})
    assert [p.field for p in problems if '"checkout"' in p.what] == ["concepts[0].key_message"]   # not again as PDF
    pdf = brief_page.creator_pdf(run, changed)[1]
    pdf.write_bytes(b"not a pdf")
    said = _said(brief_checks._production_checks(run, changed, {}))
    assert "creator PDF" in said and "cannot be read" in said
    pdf.unlink()
    assert "cannot be read" in _said(brief_checks._production_checks(run, changed, {}))


def test_production_check_reads_only_the_pdf_of_this_brief(run, monkeypatch):
    brief = _built_with(run, monkeypatch, "View: Creator\nThe spend")
    newer = copy.deepcopy(brief)
    newer["concepts"][0]["one_liner"] = "A new one-liner."
    assert brief_page.creator_pdf(run, newer) is None                     # no page built from it yet
    assert brief_checks._production_checks(run, newer, {}) == []
    assert brief_page.creator_pdf(run, brief)[0].endswith("pdf/brief_pack-creator.pdf")


# --- the real print ---------------------------------------------------------------------------------------------------

@pytest.mark.video
def test_chrome_prints_each_view(run, request):
    """The real print (`-m video`): each PDF holds its view's text, the creator PDF passes CB13, and with JPEG
    stills each stays small."""
    if not video_asked_for(request.config):
        pytest.skip("drives a real browser: run with -m video")
    if atlas.find_browser() is None:
        pytest.skip("no Chrome or Edge on this computer")
    brief = _with_animatics(run, _brief())
    _write_brief(run, brief)
    got = brief_page.build(run)
    assert got["pdf_note"] is None and len(got["pdfs"]) == 4
    texts = {Path(p).stem.split("-", 1)[1]: brief_pdf.text(run.path / p) for p in got["pdfs"]}
    assert texts["creator"].startswith("View: Creator") and texts["full"].startswith("Full report")
    assert "Your part" in texts["creator"] and "Your decision on" not in texts["creator"]
    assert "Someone in their thirties" not in texts["creator"] and "Someone in their thirties" in texts["full"]
    assert "Your part" in texts["full"] and "Your part" not in texts["decision"]
    assert brief_page.PDF_WORDS["stills"] in texts["creator"]
    assert all((run.path / p).stat().st_size < 2 * 10**6 for p in got["pdfs"])
    assert brief_checks._production_checks(run, brief, {}) == []
