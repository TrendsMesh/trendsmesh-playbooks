"""`tm schedule`: how the next weekly run starts, a desktop scheduled task or by hand (references/schedule.md).

    tm schedule --run RUN --how desktop_task|by_hand [--id ID --cron C] [--json]

It records run.json `schedule` (`{how: "desktop_task", id, cron}` or `{how: "by_hand"}`), which the next weekly run's
schedule check-in reads and `tm due` reads to leave out a run a desktop task starts. Two playbooks make weekly runs:
trend research with the weekly digest (its GS and F5; `tm research schedule` is kept as its alias) and organic video's
week run (its `schedule` check-in and I5). The desktop task's prompt is the skill's: for the weekly pack it names the
workspace, the skill, the channel and "plan my week of videos" (skills/organic-video/references/flow.md#i5).

Exit codes: 0 done, 1 error (no run, a run with no weekly schedule, or a wrong command line).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tm import cli, playbooks, research_checks, state
from tm.runfolder import ReadOnlyError, RunFolder

HOW = ("desktop_task", "by_hand")
WEEKLY_PLAN = "weekly_plan"
SAYS = {  # playbook -> what the user says each week
    playbooks.TREND_RESEARCH: "update the trend report",
    playbooks.ORGANIC_VIDEO: "plan my week of videos",
}


def _weekly(run: RunFolder, s: state.RunState) -> None:
    """A ValueError for a run that makes no weekly run."""
    if s.playbook == playbooks.TREND_RESEARCH:
        if research_checks.DIGEST not in s.outputs:
            raise ValueError(f"{run.path.resolve().name} does not make the weekly digest, so it has no weekly schedule.")
        return
    if s.playbook == playbooks.ORGANIC_VIDEO:
        if WEEKLY_PLAN not in s.outputs:
            raise ValueError(f"{run.path.resolve().name} is not a week run of organic video, so it has no weekly "
                             "schedule.")
        return
    name = next((p.name for p in playbooks.all_playbooks() if p.id == s.playbook), s.playbook)
    raise ValueError(f"{run.path.resolve().name} is a run of {name}, which has no weekly schedule.")


def record(run: RunFolder, how: str, task_id: str | None = None, cron: str | None = None) -> tuple[dict, str]:
    """Record how the next weekly run of `run` starts; (the schedule, the message). A ValueError for a run with no
    weekly schedule or a schedule that is not whole."""
    s = state.load(run)
    _weekly(run, s)
    if how == "desktop_task":
        if not (task_id and task_id.strip() and cron and len(cron.split()) == 5):
            raise ValueError("A desktop scheduled task is recorded with its --id (the taskId create_scheduled_task "
                             "used) and its --cron (five fields, local time, for example \"0 9 * * 1\").")
        s.schedule = {"how": "desktop_task", "id": task_id.strip(), "cron": " ".join(cron.split())}
        text = (f"Recorded the schedule: the desktop scheduled task {s.schedule['id']} ({s.schedule['cron']}, local "
                "time) starts the weekly run while the Claude desktop app is open.")
    elif how == "by_hand":
        if task_id or cron:
            raise ValueError("A schedule by hand has no task: leave out --id and --cron.")
        s.schedule = {"how": "by_hand"}
        text = (f"Recorded the schedule: by hand. The user asks Claude to {SAYS[s.playbook]} each week; tm due reminds "
                "them at session start once a week has passed.")
    else:
        raise ValueError(f"--how is one of {', '.join(HOW)}, not {how!r}.")
    state.save(run, s)
    return s.schedule, text


def add_arguments(sc: argparse.ArgumentParser) -> None:
    sc.add_argument("--run", required=True, help="the run folder")
    sc.add_argument("--how", required=True, choices=HOW)
    sc.add_argument("--id", help="the desktop scheduled task's taskId")
    sc.add_argument("--cron", help="its cron expression, five fields, local time")
    sc.add_argument("--json", action="store_true")


def run_command(args: argparse.Namespace, run: RunFolder | None = None) -> int:
    """Record the schedule and say so (`tm schedule`, `tm research schedule`)."""
    run = run or RunFolder.open(Path(args.run))
    schedule, text = record(run, args.how, args.id, args.cron)
    cli.emit(args, {"status": "done", "schedule": schedule, "message": text}, text)
    return 0


def _run(args: argparse.Namespace) -> int:
    try:
        return run_command(args)
    except (OSError, ValueError, ReadOnlyError) as exc:
        return cli.fail(args, str(exc))


cli.register("schedule", add_arguments, _run)
