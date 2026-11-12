"""A playbook run lives in <workspace>/runs/<playbook id>/<YYYY-MM-DD>_<name>/, e.g.
runs/01-refresh-ad/2026-11-05_Ad-3/."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from tm import playbooks
from tm.playbooks import REFRESH_AD

PLAYBOOK = REFRESH_AD
STAGES = ("00_raw", "01_base", "02_research", "03_wip", "04_final", "05_results", "showcase")
READ_ONLY_STAGES = ("00_raw", "01_base")
_SHORT = {s.split("_", 1)[-1]: s for s in STAGES}


class ReadOnlyError(Exception):
    pass


class RunExists(FileExistsError):
    """A run of that name already exists that day (issue #7): its folder and a free name to use instead."""

    def __init__(self, path: Path, suggested: str):
        self.path, self.suggested = path, suggested
        super().__init__(f"A run folder already exists at {path}. To continue that run, use it: tm next --run "
                         f"{path}. To start a new one, run tm run new again with --name {suggested}.")


def slug(name: str) -> str:
    out: list[str] = []
    for ch in name.strip():
        out.append(ch if ch.isalnum() or ch == "-" else "-")
    text = "".join(out)
    while "--" in text:
        text = text.replace("--", "-")
    return text.strip("-") or "run"


def stage_dir(stage: str) -> str:
    return _SHORT.get(stage, stage)


@dataclass
class RunFolder:
    path: Path

    @staticmethod
    def _path(workspace: Path, name: str, today: date, pb: playbooks.Playbook) -> Path:
        return Path(workspace) / "runs" / pb.id / f"{today:%Y-%m-%d}_{name}"

    @classmethod
    def free_name(cls, workspace: Path, name: str, today: date, playbook: str = REFRESH_AD) -> str:
        """The run name as its folder spells it, while no run of `playbook` has it that day; else the
        first free <name>-2, <name>-3 ..."""
        pb, base = playbooks.get(playbook), slug(name)
        candidate, n = base, 1
        while cls._path(workspace, candidate, today, pb).exists():
            n += 1
            candidate = f"{base}-{n}"
        return candidate

    @classmethod
    def create(cls, workspace: Path, name: str, today: date, playbook: str = REFRESH_AD) -> "RunFolder":
        """A new run of `playbook` (its id or skill name). Raises ValueError for an unknown one, and
        RunExists (a FileExistsError naming a free name) when a run of that name exists that day."""
        pb = playbooks.get(playbook)
        path = cls._path(workspace, slug(name), today, pb)
        if path.exists():
            raise RunExists(path, cls.free_name(workspace, name, today, pb.id))
        for s in STAGES:
            (path / s).mkdir(parents=True)
        (path / "manifest.md").write_text(
            f"# Manifest: {pb.id} {path.name}\n\n", encoding="utf-8")
        run = cls(path)
        from tm import state
        state.save(run, state.RunState(
            run_id=path.name, playbook=pb.id, created=f"{today:%Y-%m-%d}"))
        return run

    @classmethod
    def open(cls, path: Path) -> "RunFolder":
        path = Path(path)
        if not (path / "manifest.md").is_file():
            raise FileNotFoundError(f"{path} is not a run folder (no manifest.md).")
        return cls(path)

    def _versions(self, stage: str, stem: str, ext: str) -> tuple[Path, str, int, Path | None]:
        """The stage folder, the bare extension, the highest NN of any <stem>_vNN.<ext> entry (0
        when there is none), and the highest such file. Of two files with the same NN (x_v3,
        x_v03) the longer, zero-padded name wins, so the answer never depends on listing order.
        Names match in any case (M5_final_v01 is m5_final's v01): on a case-blind disk (macOS,
        Windows) they are one name, so a version number is never given twice."""
        folder = self.path / stage_dir(stage)
        ext = ext.lstrip(".")
        pattern = re.compile(rf"^{re.escape(stem)}_v(\d+)\.{re.escape(ext)}$", re.IGNORECASE)
        highest, found, best = 0, None, None
        if folder.is_dir():
            for entry in folder.iterdir():
                m = pattern.match(entry.name)
                if not m:
                    continue
                highest = max(highest, int(m.group(1)))
                key = (int(m.group(1)), len(entry.name), entry.name)
                if entry.is_file() and (best is None or key > best):
                    best, found = key, entry
        return folder, ext, highest, found

    def next_version(self, stage: str, stem: str, ext: str) -> Path:
        """Return <stage>/<stem>_vNN.<ext> with NN = highest existing + 1 (gaps are never filled).

        The path is not reserved: callers must write to it straight away.
        """
        folder, ext, highest, _ = self._versions(stage, stem, ext)
        return folder / f"{stem}_v{highest + 1:02d}.{ext}"

    def latest(self, stage: str, stem: str, ext: str) -> Path | None:
        """The highest <stage>/<stem>_vNN.<ext>, else <stem>.<ext> if it exists, else None."""
        folder, ext, _, found = self._versions(stage, stem, ext)
        if found is not None:
            return found
        plain = folder / f"{stem}.{ext}"
        return plain if plain.is_file() else None

    def given(self, path: Path | str) -> Path:
        """A file or folder named on the command line of a command with `--run`: an absolute path as it is; a
        relative one inside the run when it is there (a run-relative name such as 03_wip/edit_v01.props.json,
        whatever the working folder, issue #90); else from the current folder when it is there (a path written
        from the workspace, runs/.../03_wip/x.json); else inside the run, so a message names where it was looked
        for. Every `tm` command that takes a run resolves its input paths here."""
        path = Path(path)
        if path.is_absolute():
            return path
        inside = self.path / path
        return inside if inside.exists() or not path.exists() else path

    def unique_path(self, path: Path | str) -> Path:
        """Never overwrite (the handoff's trend_shortlist.py): x.json while it is free, else x_v02.json,
        x_v03.json ...; x_v02.json counts on from 02. A relative path is inside the run folder.
        Saved MCP answers use it; tool outputs use `next_version` (`_v01` first). Like
        `next_version`, the path is not reserved: write to it straight away."""
        path = Path(path)
        path = path if path.is_absolute() else self.path / path
        if not path.exists():
            return path
        m = re.match(r"^(.*)_v(\d+)$", path.stem)
        base, n = (m.group(1), int(m.group(2))) if m else (path.stem, 1)
        while True:
            n += 1
            candidate = path.with_name(f"{base}_v{n:02d}{path.suffix}")
            if not candidate.exists():
                return candidate

    def assert_writable(self, path: Path) -> None:
        path = Path(path)
        try:
            rel = path.resolve().relative_to(self.path.resolve())
        except ValueError:
            return
        if rel.parts and rel.parts[0] in READ_ONLY_STAGES and path.exists():
            raise ReadOnlyError(
                f"{rel.as_posix()} is a saved original and is never changed. "
                "Write a new file under 03_wip instead; the run continues from the same place.")
