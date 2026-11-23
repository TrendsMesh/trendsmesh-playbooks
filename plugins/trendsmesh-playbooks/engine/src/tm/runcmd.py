"""Subcommands `tm run new` and `tm record`."""

from __future__ import annotations

import argparse
import re
import shutil
from datetime import date
from pathlib import Path

import yaml

from tm import cli, manifest, paths, playbooks, state, trend_spool
from tm.runfolder import ReadOnlyError, RunExists, RunFolder, slug


_emit = cli.emit
_fail = cli.fail


def _setup_run(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="run_command", metavar="action")
    new = sub.add_parser("new")
    new.add_argument("--name", required=True)
    new.add_argument("--playbook", default=playbooks.REFRESH_AD, help="a playbook id or skill name")
    new.add_argument("--after", help="the run folder this run follows (same playbook and workspace)")
    new.add_argument("--seed", help="creative brief or organic video: start from a trend research pick, its "
                                    "seed_id (tm seeds list --source pb4)")
    new.add_argument("--json", action="store_true")


def _previous(workspace: Path, after: str, pb: playbooks.Playbook) -> str:
    """The `--after` run, relative to the workspace, once it is a run of `pb` in this workspace.
    A relative `--after` is read from the workspace."""
    prev = RunFolder.open(workspace / after)
    try:
        rel = prev.path.resolve().relative_to(workspace.resolve())
    except ValueError:
        raise ValueError(f"{prev.path} is not a run in this workspace ({workspace}).") from None
    theirs = state.load(prev).playbook
    if theirs != pb.id:
        other = next((p.name for p in playbooks.all_playbooks() if p.id == theirs), theirs)
        raise ValueError(f"{prev.path.name} is a run of {other}, not of {pb.name}: a run follows "
                         "another run of the same playbook.")
    return rel.as_posix()


SEEDED = (playbooks.CREATIVE_BRIEF, playbooks.ORGANIC_VIDEO)  # the playbooks a trend research pick can start


def _seed(workspace: Path, seed_id: str, pb: playbooks.Playbook) -> dict:
    """The seed row a creative brief or organic video run starts from; found before the run folder is
    made (`brief_config.find_seed`, the same seeds and kinds for both)."""
    if pb.id not in SEEDED:
        names = " or ".join(playbooks.get(p).name for p in SEEDED)
        raise ValueError(f"--seed starts a {names} run from a trend pick; {pb.name} does not take one.")
    from tm import brief_config  # only a seeded run needs it
    return brief_config.find_seed(workspace, seed_id, playbook=pb.id)


def _finish(run: RunFolder, previous: str | None, seed: dict | None) -> None:
    """What the new run records beyond its folder: the run it follows and the seed it starts from
    (`brief_config.start_from_seed` names it in the playbook's own state). On a failure the new folder
    is removed, so no run is left that resumes without them."""
    try:
        if previous:
            s = state.load(run)
            s.previous_run = previous
            state.save(run, s)
        if seed is not None:
            from tm import brief_config
            brief_config.start_from_seed(run, seed)
    except (OSError, ValueError) as exc:
        shutil.rmtree(run.path, ignore_errors=True)
        what = "from the seed" if seed is not None else "after the earlier run"
        if run.path.exists():  # e.g. a file held open on Windows
            raise ValueError(f"The run could not be started {what} ({exc}), and its folder {run.path} could not "
                             "be removed. Delete that folder, then start the run again with the same "
                             "command.") from None
        raise ValueError(f"The run could not be started {what} ({exc}), so it was not kept. Start it "
                         "again with the same command.") from None


def _channels(path: Path) -> set[str]:
    """The channels a run's config names (organic video's `channels`), as run names spell them; none without."""
    try:
        cfg = yaml.safe_load((path / "config.yaml").read_text(encoding="utf-8-sig")) or {}
    except (OSError, yaml.YAMLError):
        return set()
    found = cfg.get("channels") if isinstance(cfg, dict) else None
    return {slug(str(c)).casefold() for c in found} if isinstance(found, list) else set()


def _started(s: state.RunState, path: Path) -> bool:
    """Anything was done in the run: a step reached, a level or a decision, or its config written. A run folder made
    and never used (a new run the user then did not want) is not one to continue."""
    return bool(s.step or s.level or s.decisions or (path / "config.yaml").is_file())


def unfinished_runs(workspace: Path, playbook: str, name: str, *, but: Path | None = None) -> list[dict]:
    """The runs of `playbook` in the workspace that are not done and were started, under the same name (as its folder
    spells it, or that name's `-2`, `-3` … of a later run the same day) or for the same channel (organic video's
    config `channels`): {folder (workspace-relative), created, step, status}, the newest first. `but` is left out.
    Issue #90: `tm run new` returns them, so an unfinished run is never missed."""
    base = slug(name).casefold()
    same = re.compile(rf"^\d{{4}}-\d{{2}}-\d{{2}}_{re.escape(base)}(-\d+)?$")
    folder = Path(workspace) / "runs" / playbooks.get(playbook).id
    found = []
    for path in folder.iterdir() if folder.is_dir() else ():
        if (but is not None and path.resolve() == Path(but).resolve()) or not (path / "manifest.md").is_file():
            continue
        if not (same.match(path.name.casefold()) or base in _channels(path)):
            continue
        try:
            s = state.load(RunFolder.open(path))
        except (OSError, ValueError):
            continue                          # a folder whose state cannot be read: `tm status` says why
        if s.status == "done" or not _started(s, path):
            continue
        found.append({"folder": path.relative_to(workspace).as_posix(), "created": s.created, "step": s.step,
                      "status": s.status})
    return sorted(found, key=lambda r: (r["created"], r["folder"]), reverse=True)


def _taken(args: argparse.Namespace, exc: RunExists) -> int:
    """A run of that name exists today: say which (its status and step, so the user can be asked whether
    to continue it) and a free name for a new one. Nothing is made."""
    payload = {"status": "error", "message": str(exc), "existing": str(exc.path), "suggested_name": exc.suggested}
    try:
        s = state.load(RunFolder.open(exc.path))
        payload.update(existing_status=s.status, existing_step=s.step)
    except (OSError, ValueError):
        pass                                  # a folder without a readable state: the message still says it
    cli.emit(args, payload, str(exc))
    return 1


def _run_run(args: argparse.Namespace) -> int:
    if args.run_command != "new":
        return _fail(args, "Use: tm run new --name <name> [--playbook <id|skill>] [--after <run folder>] "
                           "[--seed <seed_id>]")
    try:
        workspace = paths.workspace()
        pb = playbooks.offered(args.playbook)
        previous = _previous(workspace, args.after, pb) if args.after else None
        seed = _seed(workspace, args.seed, pb) if args.seed is not None else None
        run = RunFolder.create(workspace, args.name, date.today(), playbook=pb.id)
        _finish(run, previous, seed)
    except RunExists as exc:
        return _taken(args, exc)
    except (OSError, ValueError) as exc:
        return _fail(args, str(exc))
    if pb.id in trend_spool.COLLECTING:
        try:
            # A new run collects only once its skill turns it on: this session's marker goes, another
            # session's (its own run) stays.
            trend_spool.turn_off(workspace, trend_spool.this_session())
        except OSError:
            pass                              # the run exists; the marker stays tied to its own run
    try:
        unfinished = unfinished_runs(workspace, pb.id, args.name, but=run.path)
    except OSError:
        unfinished = []
    text = str(run.path)
    if unfinished:
        listed = "; ".join(f"{r['folder']} (from {r['created']}, at {r['step']}"
                           + (", stopped" if r["status"] == "stopped" else "") + ")" for r in unfinished)
        text += (f"\nUnfinished runs of this {pb.name} name or channel: {listed}. Ask the user first whether to "
                 "continue one (then `tm next` on it; this new folder stays unused) or start this new one.")
    _emit(args, {"status": "done", "path": str(run.path), "run_id": run.path.name, "unfinished_runs": unfinished,
                 "message": text}, text)
    return 0


def _setup_record(p: argparse.ArgumentParser) -> None:
    p.add_argument("--run", required=True)
    p.add_argument("--file", required=True, help="relative to the run folder")
    p.add_argument("--stage", required=True)
    p.add_argument("--source", help="where the file came from (needed unless --copy-from gives it)")
    p.add_argument("--copy-from", dest="copy_from", metavar="PATH",
                   help="copy this file (any path: the brand folder, Downloads, a file dropped in the chat) to --file "
                        "first; its full path is the source (refresh-ad A2, issue #143). Never overwrites")
    p.add_argument("--length-s", dest="length_s", type=float, metavar="SECONDS",
                   help="the ad's video length (from ads_get_ad_videos): an original (01_base/*_original.*) whose own "
                        "length is more than 1 s or 5 %% off it is refused, and nothing is copied (issue #171)")
    p.add_argument("--parent")
    p.add_argument("--prompt")
    p.add_argument("--params", help="a JSON object, or the path of a JSON file holding one")
    p.add_argument("--model")
    p.add_argument("--cost")
    p.add_argument("--before-after", dest="before_after")
    p.add_argument("--raw-response-file", dest="raw_response_file")
    p.add_argument("--json", action="store_true")


def _copy_in(run: RunFolder, given: str, rel: str) -> str:
    """Copy a file from anywhere to `rel` in the run (never over a file already there); its full path, the source."""
    import shutil

    src = Path(given).expanduser()
    if not src.is_file():
        raise ValueError(f"{src} is not a file: ask the user for the file's full path, or to drop it into the chat.")
    target = run.given(rel, missing_ok=True)
    if target.exists():
        if target.resolve() == src.resolve():
            return str(src.resolve())
        raise ValueError(f"{rel} is already in the run; give a new name (a new version) for this file.")
    run.assert_writable(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    return str(src.resolve())


ORIGINAL = re.compile(r"^01_base/[^/]+_original\.[^/]+$")   # refresh-ad A2: the ad's own video file
LENGTH_SLACK_S, LENGTH_SLACK = 1.0, 0.05                     # an original may be off the ad by max(1 s, 5 %)


def check_length(path: Path, rel: str, length_s: float) -> None:
    """Refuse an original (`ORIGINAL`) whose length (ffprobe) is off the ad's `length_s` by more than
    max(LENGTH_SLACK_S, LENGTH_SLACK of it): it is another video, or another cut of it (issue #171)."""
    import subprocess

    from tm.tools import _common as tools_common

    if length_s <= 0:
        raise ValueError(f"--length-s must be the ad's length in seconds, above 0 (not {length_s:g}).")
    try:
        found = float(tools_common.probe(path).get("duration") or 0)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"The length of {path} can't be read with ffprobe ({exc.__class__.__name__}): check it is "
                         f"the ad's video. Nothing was copied or recorded.") from None
    slack = max(LENGTH_SLACK_S, LENGTH_SLACK * length_s)
    if found <= 0 or abs(found - length_s) > slack:
        raise ValueError(f"{path.name} runs {found:.1f} s and the ad's video {length_s:.1f} s (more than "
                         f"{slack:.1f} s apart), so it is not this ad's video, or another cut of it. Nothing was copied "
                         f"or recorded as {rel}: ask the user for the file of this ad (ads_get_ad_videos names its "
                         "length and thumbnail).")


def _run_record(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        params = cli.json_arg(args.params, run) if args.params else None
        if params is not None and not isinstance(params, dict):
            raise ValueError("--params must be a JSON object, for example '{\"seconds\": 8}'.")
        raw = run.given(args.raw_response_file).read_text(encoding="utf-8") if args.raw_response_file else None
        source = args.source
        rel = str(args.file).replace("\\", "/")
        if args.length_s is not None and ORIGINAL.match(rel):
            given = Path(args.copy_from).expanduser() if args.copy_from else run.given(args.file, missing_ok=True)
            if given.is_file():   # a missing file is _copy_in's (or the manifest's) to name
                check_length(given, rel, args.length_s)
        if args.copy_from:
            copied = _copy_in(run, args.copy_from, args.file)
            source = source or copied
        if not (source and source.strip()):
            raise ValueError("Say where the file came from with --source, or copy it in with --copy-from <path>.")
        manifest.record(run, args.file, args.stage, source, args.parent, args.prompt, params,
                        args.model, args.cost, args.before_after, raw_response=raw)
    except (OSError, ValueError, ReadOnlyError) as exc:
        return _fail(args, str(exc))
    _emit(args, {"status": "done", "file": args.file}, f"Recorded {args.file}")
    return 0


cli.register("run", _setup_run, _run_run)
cli.register("record", _setup_record, _run_record)
