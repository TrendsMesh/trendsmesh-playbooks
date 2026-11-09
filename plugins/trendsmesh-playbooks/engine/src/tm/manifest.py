"""manifest.md: one table row per asset; prompts and raw responses saved beside the asset."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path, PurePosixPath, PureWindowsPath

from tm.runfolder import RunFolder

COLUMNS = ("file", "stage", "source", "parent", "prompt", "params", "model", "date", "cost", "before/after")


def _cell(value: object) -> str:
    if value is None or value == "":
        return "-"
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _inside(value: str, what: str) -> str:
    """Normalise to posix separators and refuse anything that leaves the run folder."""
    text = value.replace("\\", "/")
    if (not text or PurePosixPath(text).is_absolute() or PureWindowsPath(value).is_absolute()
            or PureWindowsPath(value).drive or ".." in PurePosixPath(text).parts):
        raise ValueError(f"{what} must be a path inside the run folder, got {value!r}.")
    return text


def _sidecar(run: RunFolder, asset: Path, kind: str, ext: str) -> Path:
    """<filename>.<kind>.<ext>; an existing sidecar is never overwritten, a later one is <kind>_v02 and so on."""
    n = 1
    while True:
        tag = kind if n == 1 else f"{kind}_v{n:02d}"
        side = asset.parent / f"{asset.name}.{tag}.{ext}"
        if not side.exists():
            run.assert_writable(side)
            return side
        n += 1


def record(run: RunFolder, file: str, stage: str, source: str, parent: str | None = None,
           prompt: str | None = None, params: dict | None = None, model: str | None = None,
           cost: str | None = None, before_after: str | None = None,
           raw_response: str | None = None) -> None:
    file = _inside(file, "file")
    stage = _inside(stage, "stage")
    asset = run.path / file
    prompt_cell = prompt
    if prompt:
        side = _sidecar(run, asset, "prompt", "txt")
        side.parent.mkdir(parents=True, exist_ok=True)
        side.write_text(prompt, encoding="utf-8")
        prompt_cell = prompt if len(prompt) <= 120 else f"{prompt[:117]}... (full: {side.name})"
    if raw_response is not None:
        side = _sidecar(run, asset, "response", "json")
        side.parent.mkdir(parents=True, exist_ok=True)
        side.write_text(raw_response, encoding="utf-8")
    manifest = run.path / "manifest.md"
    text = manifest.read_text(encoding="utf-8") if manifest.exists() else ""
    if "| file |" not in text:
        if text and not text.endswith("\n"):
            text += "\n"
        text += "| " + " | ".join(COLUMNS) + " |\n|" + "---|" * len(COLUMNS) + "\n"
    row = [file, stage, source, parent, prompt_cell, params, model, f"{date.today():%Y-%m-%d}", cost, before_after]
    text += "| " + " | ".join(_cell(v) for v in row) + " |\n"
    manifest.write_text(text, encoding="utf-8")


def _split_row(line: str) -> list[str]:
    """Split one table line on unescaped pipes and undo `_cell`'s escaping."""
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") else body
    cells: list[str] = []
    cur: list[str] = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            cur.append(body[i + 1])
            i += 2
            continue
        if ch == "|":
            cells.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    cells.append("".join(cur))
    return [c.strip() for c in cells]


def rows(run: RunFolder) -> list[dict]:
    """The manifest table read back: one dict per row keyed by COLUMNS; the "-" placeholder becomes ''."""
    manifest = run.path / "manifest.md"
    if not manifest.is_file():
        return []
    out: list[dict] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = _split_row(line)
        if len(cells) != len(COLUMNS) or cells[0] == "file" or set(cells[0]) <= {"-", ":"}:
            continue
        out.append({col: ("" if val == "-" else val) for col, val in zip(COLUMNS, cells)})
    return out
