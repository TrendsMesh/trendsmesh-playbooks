"""The brief page's PDFs (issue #10): the full report and one per view, printed at build time.

    names(views)                  {"full" | view: "pdf/brief_pack-<key>.pdf"}, the paths the page serves them at
    browser()                     the browser that prints them (`atlas.find_browser`), or None
    stills(run, mp4, dest)        the animatic's stills as small JPEGs in `dest` (for the print page)
    print_pdf(browser, page, key, out)   one PDF of `page#print-<key>`, by headless Chrome
    text(path)                    the text a PDF shows (CB13 reads the creator PDF's)

The page is printed from its print mode (`brief_page.render(..., stills=...)`): `.print/print.html` in the
page folder, hidden, so `tm page files` publishes the PDFs and not their source. A PDF has no video: each
animatic is shown by the five stills its render wrote (`atlas.STILLS`), made smaller JPEGs here, so a PDF
stays small.

Printing drives the user's own browser as the animatic step does (`atlas.find_browser`: Chrome first, as
headless Edge was seen to write its files late and out of order): one process per PDF, each with a profile
folder of its own, and its file waited for. A computer without a browser builds the page without PDFs. The
names are the page's, not the folder's (`brief_pack-creator.pdf`), so publishing a new version to the same
link replaces each PDF.

`text` reads what Chrome (Skia) writes: uncompressed or Flate-compressed objects, fonts with a ToUnicode map,
text shown with Tj/TJ. It needs no PDF library. Its lines are the baselines the text objects (BT ... ET) sit
on, so words on two lines never run together; the objects on one line are joined by a space, or by nothing
(`joiner`), for a word whose letters change font.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
import zlib
from pathlib import Path

from tm import atlas
from tm.tools import _common as c

PAGE = "brief_pack"
DIR = "pdf"
PRINT_DIR = ".print"                 # hidden: `page.files` leaves it out of the publish
PRINT_PAGE = "print.html"
FULL = "full"
STILL_WIDTH = 360                    # px: a still is printed about 3 cm wide
TIMEOUT_S = 120
WAIT_S = 30                          # for the file after the browser exits (a browser may write it late)
VIRTUAL_TIME_MS = 8000               # the page's own script and images, before printing
MODEL = "Chrome print-to-pdf"        # the manifest's model of a PDF


def names(views: list[str]) -> dict[str, str]:
    """The PDFs a page with `views` gets, by key ("full", then each view): their served paths."""
    return {key: f"{DIR}/{PAGE}-{key}.pdf" for key in [FULL, *views]}


def browser() -> Path | None:
    return atlas.find_browser()


def stills(run_path: Path, mp4: Path, dest: Path) -> list[Path]:
    """The stills `atlas.render` wrote beside `mp4`, each as a JPEG STILL_WIDTH wide in `dest`; the ones
    missing or that ffmpeg cannot read are left out."""
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for png in atlas.still_paths(mp4):
        if not png.is_file():
            continue
        jpg = dest / f"{png.stem}.jpg"
        try:
            c.run_ffmpeg(["-i", str(png), "-vf", f"scale={STILL_WIDTH}:-2", "-q:v", "5", str(jpg)])
        except (subprocess.CalledProcessError, OSError):
            jpg.unlink(missing_ok=True)
            continue
        out.append(jpg)
    return out


def _argv(browser_path: Path, url: str, out: Path, profile: Path) -> list[str]:
    argv = [str(browser_path)]
    if not atlas.is_headless_shell(browser_path):
        argv.append("--headless=new")
    argv += ["--disable-gpu", "--no-first-run", "--no-default-browser-check", "--disable-extensions",
             f"--user-data-dir={profile}", f"--print-to-pdf={out}", "--no-pdf-header-footer",
             f"--virtual-time-budget={VIRTUAL_TIME_MS}"]
    if atlas.needs_no_sandbox(browser_path):
        argv.append("--no-sandbox")
    return argv + [url]


def print_pdf(browser_path: Path, page: Path, key: str, out: Path) -> None:
    """Print `page#print-<key>` to `out` with the browser, headless, in a profile folder of its own, and
    wait for the whole file. ValueError when no PDF came out. The browser is given absolute paths: it does not
    write a PDF to a relative one (issue #54, `--run` given as a relative path, on Windows)."""
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    url = f"{Path(page).resolve().as_uri()}#print-{key}"
    with tempfile.TemporaryDirectory(prefix="tm-pdf-") as profile:
        try:
            proc = subprocess.run(_argv(browser_path, url, out, Path(profile)), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            raise ValueError(f"the browser did not print {out.name} in {TIMEOUT_S} s") from None
        except OSError as exc:
            raise ValueError(f"the browser could not start ({exc})") from None
        deadline, size = time.monotonic() + WAIT_S, -1
        while time.monotonic() < deadline:            # written, and no longer growing
            if out.is_file() and out.stat().st_size == size and _complete(out):
                return
            size = out.stat().st_size if out.is_file() else -1
            time.sleep(0.5)
    tail = " | ".join((proc.stderr or "").strip().splitlines()[-2:])
    raise ValueError(f"the browser wrote no {out.name}" + (f" ({tail})" if tail else ""))


def _complete(path: Path) -> bool:
    data = path.read_bytes()
    return data.startswith(b"%PDF-") and b"%%EOF" in data[-1024:]


def write_print_page(folder: Path, html_text: str) -> Path:
    page = folder / PRINT_DIR / PRINT_PAGE
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(html_text, encoding="utf-8", newline="\n")
    return page


def remove(folder: Path) -> None:
    shutil.rmtree(folder / DIR, ignore_errors=True)


# --- reading a PDF's text ------------------------------------------------------------------------

_OBJ = re.compile(rb"(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj", re.S)
_REF = rb"(\d+)\s+\d+\s+R"
_TOKEN = re.compile(rb"<<|>>|\[|\]|<[0-9A-Fa-f\s]*>|\((?:\\.|[^\\)])*\)|/[^\s/<>\[\]()]+|[^\s/<>\[\]()]+", re.S)


def _stream(body: bytes) -> bytes:
    m = re.search(rb"stream\r?\n", body)
    if m is None:
        return b""
    data = body[m.end():body.rfind(b"endstream")].rstrip(b"\r\n")
    if b"/FlateDecode" in body[:m.start()]:
        try:
            return zlib.decompress(data)
        except zlib.error:
            return zlib.decompressobj().decompress(data)
    return data


def _literal(raw: bytes) -> bytes:
    """The bytes of a PDF literal string `(...)`."""
    out, i, raw = bytearray(), 0, raw[1:-1]
    escapes = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}
    while i < len(raw):
        ch = raw[i:i + 1]
        if ch == b"\\" and i + 1 < len(raw):
            nxt = raw[i + 1:i + 2]
            octal = re.match(rb"[0-7]{1,3}", raw[i + 1:i + 4])
            if octal:
                out.append(int(octal.group(0), 8) & 0xFF)
                i += 1 + len(octal.group(0))
                continue
            out += escapes.get(nxt, nxt)
            i += 2
            continue
        out += ch
        i += 1
    return bytes(out)


def _string(token: bytes) -> bytes:
    if token.startswith(b"<"):
        hexed = re.sub(rb"\s", b"", token[1:-1])
        return bytes.fromhex((hexed + b"0" * (len(hexed) % 2)).decode("ascii"))
    return _literal(token)


def _cmap(data: bytes) -> tuple[dict[bytes, str], int]:
    """A ToUnicode map: {code bytes: text} and the code length in bytes."""
    out: dict[bytes, str] = {}
    width = 2
    hexes = lambda s: bytes.fromhex(s.decode("ascii"))   # noqa: E731
    text = lambda s: hexes(s).decode("utf-16-be", "replace")   # noqa: E731
    for m in re.finditer(rb"begincodespacerange(.*?)endcodespacerange", data, re.S):
        first = re.search(rb"<([0-9A-Fa-f]+)>", m.group(1))
        if first:
            width = len(first.group(1)) // 2
    for block in re.finditer(rb"beginbfchar(.*?)endbfchar", data, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", block.group(1)):
            out[hexes(src)] = text(dst)
    for block in re.finditer(rb"beginbfrange(.*?)endbfrange", data, re.S):
        for lo, hi, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]*>|\[[^\]]*\])",
                                      block.group(1)):
            n, start, end = len(lo) // 2, int(lo, 16), int(hi, 16)
            if dst.startswith(b"["):
                targets = [text(t) for t in re.findall(rb"<([0-9A-Fa-f]*)>", dst)]
                for k, t in zip(range(start, end + 1), targets):
                    out[k.to_bytes(n, "big")] = t
                continue
            base = hexes(dst[1:-1])
            for k in range(start, min(end, start + 0xFFFF) + 1):
                code = (int.from_bytes(base, "big") + k - start).to_bytes(len(base), "big")
                out[k.to_bytes(n, "big")] = code.decode("utf-16-be", "replace")
    return out, width


class _Font:
    def __init__(self, cmap: dict[bytes, str] | None, width: int):
        self.cmap, self.width = cmap, width

    def decode(self, data: bytes) -> str:
        if self.cmap is None:
            return data.decode("latin-1")
        w = self.width
        return "".join(self.cmap.get(data[i:i + w], "") for i in range(0, len(data) - w + 1, w))


def _resolve(objs: dict[int, bytes], body: bytes, key: bytes) -> bytes | None:
    """The value of /key in a dictionary: an inline << >> dictionary, or the object a reference names."""
    m = re.search(rb"/" + key + rb"\s*(" + _REF + rb"|<<)", body)
    if m is None:
        return None
    if m.group(1) == b"<<":
        depth, i = 1, m.end()
        while i < len(body) and depth:
            if body.startswith(b"<<", i):
                depth, i = depth + 1, i + 2
            elif body.startswith(b">>", i):
                depth, i = depth - 1, i + 2
            else:
                i += 1
        return body[m.end():i - 2]
    return objs.get(int(m.group(2)))


def _fonts(objs: dict[int, bytes], page: bytes) -> dict[bytes, _Font]:
    resources = _resolve(objs, page, b"Resources") or b""
    fonts = _resolve(objs, resources, b"Font") or b""
    out = {}
    for name, ref in re.findall(rb"/([^\s/<>\[\]()]+)\s+" + _REF, fonts):
        font = objs.get(int(ref), b"")
        to_unicode = re.search(rb"/ToUnicode\s+" + _REF, font)
        if to_unicode and int(to_unicode.group(1)) in objs:
            out[name] = _Font(*_cmap(_stream(objs[int(to_unicode.group(1))])))
        else:
            out[name] = _Font(None, 1)
    return out


def _content(objs: dict[int, bytes], page: bytes) -> bytes:
    m = re.search(rb"/Contents\s*(\[[^\]]*\]|" + _REF + rb")", page)
    if m is None:
        return b""
    refs = re.findall(_REF, m.group(1)) if m.group(1).startswith(b"[") else [m.group(2)]
    return b"\n".join(_stream(objs.get(int(r), b"")) for r in refs)


def _actual(token: bytes) -> str:
    data = _string(token)
    if data.startswith(b"\xfe\xff"):
        return data[2:].decode("utf-16-be", "replace")
    return data.decode("latin-1")


def _number(tok: bytes) -> float:
    try:
        return float(tok)
    except ValueError:
        return 0.0


def _page_text(stream: bytes, fonts: dict[bytes, _Font]) -> list[tuple[float, str]]:
    """(baseline, text) of each text object (BT ... ET) of a content stream, in order."""
    objects: list[tuple[float, str]] = []
    line: list[str] = []
    font = _Font(None, 1)
    y = 0.0
    stack: list[bytes] = []
    actual: list[bool] = []             # inside a span with /ActualText: its text in place of the glyphs
    for m in _TOKEN.finditer(stream):
        tok = m.group(0)
        if tok in (b"<<", b">>", b"[", b"]") or tok.startswith((b"/", b"(", b"<")) or re.fullmatch(rb"[-+.\d]+", tok):
            stack.append(tok)
            continue
        op, args = tok, stack
        stack = []
        if op == b"BT":
            line = []
        elif op == b"ET":
            if line:
                objects.append((y, "".join(line)))
            line = []
        elif op == b"Tm" and len(args) >= 6:
            y = _number(args[5])
        elif op in (b"Td", b"TD") and len(args) >= 2:
            y += _number(args[1])
        elif op == b"Tf" and args:
            names = [a for a in args if a.startswith(b"/")]
            font = fonts.get(names[-1][1:], _Font(None, 1)) if names else font
        elif op in (b"Tj", b"TJ", b"'", b'"'):
            if actual and actual[-1]:
                continue
            for a in args:
                if a.startswith((b"(", b"<")) and not a.startswith(b"<<"):
                    line.append(font.decode(_string(a)))
        elif op == b"BDC":
            text = None
            for i, a in enumerate(args):
                if a == b"/ActualText" and i + 1 < len(args):
                    text = _actual(args[i + 1])
            actual.append(text is not None)
            if text is not None:
                line.append(text)
        elif op == b"BMC":
            actual.append(False)
        elif op == b"EMC" and actual:
            actual.pop()
    if line:
        objects.append((y, "".join(line)))
    return objects


def text(path: Path, joiner: str = " ") -> str:
    """The text the PDF at `path` shows, NFKC-normalised (a ligature is its letters): a line per baseline, the
    text objects on one baseline (a change of font, a table's cells) joined by `joiner`. ValueError for a file
    that is not a PDF."""
    data = Path(path).read_bytes()
    if not data.startswith(b"%PDF-"):
        raise ValueError(f"{Path(path).name} is not a PDF")
    objs = {int(m.group(1)): m.group(3) for m in _OBJ.finditer(data)}
    pages = [body for _, body in sorted(objs.items()) if re.search(rb"/Type\s*/Page(?![s\w])", body)]
    lines: list[str] = []
    for page in pages:
        last = None
        for y, shown in _page_text(_content(objs, page), _fonts(objs, page)):
            if last is not None and abs(y - last) < 0.5:
                lines[-1] += joiner + shown
            else:
                lines.append(shown)
            last = y
    return unicodedata.normalize("NFKC", "\n".join(lines))
