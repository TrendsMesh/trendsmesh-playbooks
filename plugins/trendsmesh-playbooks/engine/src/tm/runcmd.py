"""Subcommands `tm run new` and `tm record`."""

from __future__ import annotations

import argparse
import shutil
from datetime import date
from pathlib import Path

from tm import cli, manifest, paths, playbooks, state, trend_spool
from tm.runfolder import ReadOnlyError, RunFolder


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
    except (OSError, ValueError) as exc:
        return _fail(args, str(exc))
    if pb.id in trend_spool.COLLECTING:
        try:
            # A new run collects only once its skill turns it on: this session's marker goes, another
            # session's (its own run) stays.
            trend_spool.turn_off(workspace, trend_spool.this_session())
        except OSError:
            pass                              # the run exists; the marker stays tied to its own run
    _emit(args, {"status": "done", "path": str(run.path), "run_id": run.path.name}, str(run.path))
    return 0


def _setup_record(p: argparse.ArgumentParser) -> None:
    p.add_argument("--run", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--stage", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--parent")
    p.add_argument("--prompt")
    p.add_argument("--params", help="a JSON object, or the path of a JSON file holding one")
    p.add_argument("--model")
    p.add_argument("--cost")
    p.add_argument("--before-after", dest="before_after")
    p.add_argument("--raw-response-file", dest="raw_response_file")
    p.add_argument("--json", action="store_true")


def _run_record(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        params = cli.json_arg(args.params) if args.params else None
        if params is not None and not isinstance(params, dict):
            raise ValueError("--params must be a JSON object, for example '{\"seconds\": 8}'.")
        raw = Path(args.raw_response_file).read_text(encoding="utf-8") if args.raw_response_file else None
        manifest.record(run, args.file, args.stage, args.source, args.parent, args.prompt, params,
                        args.model, args.cost, args.before_after, raw_response=raw)
    except (OSError, ValueError, ReadOnlyError) as exc:
        return _fail(args, str(exc))
    _emit(args, {"status": "done", "file": args.file}, f"Recorded {args.file}")
    return 0


cli.register("run", _setup_run, _run_run)
cli.register("record", _setup_record, _run_record)
