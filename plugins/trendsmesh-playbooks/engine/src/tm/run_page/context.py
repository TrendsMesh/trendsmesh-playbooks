"""What a stage component gets to build its materials: the run, the page's datasets, the page language, and a
way to put a run file on the page (copied into the page folder's `assets/media/`, never linked outside it)."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from tm import page
from tm.run_page.template import Datasets
from tm.run_page.words import has, label, t
from tm.runfolder import RunFolder

MEDIA_EXT = (".mp4", ".mov", ".webm", ".m4v", ".mp3", ".wav", ".m4a", ".aac", ".ogg",
             ".png", ".jpg", ".jpeg", ".webp", ".gif")
_VERSION = re.compile(r"_v(\d+)$")


class Context:
    def __init__(self, run: RunFolder, folder: Path | None, lang: str):
        self.run, self.folder, self.lang = run, folder, lang
        self.ds = Datasets()
        self._put: dict[str, str] = {}

    # words
    def t(self, key: str, **values: object) -> str:
        return t(key, self.lang, **values)

    def t_or(self, key: str, default: object) -> str:
        """The table's words for `key` when it has them (a stage name, a badge), else `default` as it is."""
        return t(key, self.lang) if has(key, self.lang) else str(default)

    def col(self, key: str) -> str:
        return label("col", key, self.lang)

    def label(self, group: str, key: str) -> str:
        return label(group, key, self.lang)

    def tile_columns(self) -> list[tuple[str, str, str]]:
        return [("label", self.col("metric"), "text"), ("value", self.col("value"), "num")]

    # files
    def rel(self, path: Path) -> str:
        return path.relative_to(self.run.path).as_posix()

    def inside(self, rel: str) -> Path | None:
        """The run file `rel` names, when it is a file inside the run folder; else None."""
        if not isinstance(rel, str) or not rel.strip():
            return None
        path = (self.run.path / rel.replace("\\", "/")).resolve()
        try:
            path.relative_to(self.run.path.resolve())
        except ValueError:
            return None
        return path if path.is_file() else None

    def latest(self, stage: str, stem: str, ext: str) -> Path | None:
        try:
            return self.run.latest(stage, stem, ext)
        except (OSError, ValueError):
            return None

    def newest(self, folder: str, pattern: str) -> Path | None:
        """The newest file matching `pattern` in the run's `folder`: the highest `_vNN`, then the name."""
        base = self.run.path / folder
        found = [p for p in base.glob(pattern) if p.is_file()] if base.is_dir() else []

        def key(p: Path):
            m = _VERSION.search(p.stem)
            return (int(m.group(1)) if m else 0, p.name)
        return max(found, key=key) if found else None

    def json(self, path: Path | None):
        if path is None:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def text(self, path: Path | None) -> str | None:
        try:
            return path.read_text(encoding="utf-8", errors="replace") if path is not None else None
        except OSError:
            return None

    def put(self, rel: str) -> str | None:
        """The run file `rel` copied onto the page (`assets/media/<name>`, Windows-safe and unique); its path on
        the page, or None when it is not a media file inside the run."""
        path = self.inside(rel)
        if path is None or path.suffix.lower() not in MEDIA_EXT:
            return None
        key = path.as_posix()
        if key in self._put:
            return self._put[key]
        served = f"assets/media/{len(self._put) + 1:02d}_{page.asset_name(path.name)}"
        if self.folder is not None:
            target = self.folder / served
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        self._put[key] = served
        return served
