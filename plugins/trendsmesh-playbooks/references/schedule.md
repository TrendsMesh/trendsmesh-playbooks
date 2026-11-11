# Weekly schedules (shared: trend research's weekly digest and organic video's weekly pack)

## What Claude Code offers (checked 2026-11-07, Claude Code 2.1.319)

- **Desktop scheduled tasks.** The Claude desktop app has a `scheduled-tasks` connector with
  `create_scheduled_task`, `list_scheduled_tasks`, `update_scheduled_task` (and
  `delete_scheduled_task`, `run_scheduled_task`, `list_task_runs`). `create_scheduled_task` takes
  `taskId` (kebab-case), `title`, `description`, `prompt` and `cronExpression` (five fields, the
  user's **local** time; `"0 9 * * 1"` is every Monday at 09:00), or `fireAt` for one run. The task
  is stored in the user's `~/.claude/scheduled-tasks/<taskId>/SKILL.md`.
  - It runs **only while the desktop app is open**; a run missed while the app was closed runs at
    the next launch.
  - It takes **no working folder**, and each run starts fresh, with no memory of the session that
    made it. So its prompt must name the workspace folder (the folder that holds `runs/`) and say
    everything the run needs.
  - It may run in the permission mode of the session that made it; a run that needs a permission
    the user has not given waits for them.
- **The CLI** (`claude --help`) has no schedule command. `/schedule` makes *cloud* routines: they
  run on Anthropic's machines, without the user's workspace, its run folders, or their TrendsMesh
  and Meta sign-ins, so they cannot run a trend report. `/loop` repeats a prompt inside one open
  session only. Neither is used.
- **A plugin cannot create a scheduled task by itself**: no plugin file or hook makes one. Only
  Claude, in a desktop app session where `create_scheduled_task` is among its tools, can, and only
  after the user's yes (a standing schedule is a standing rule).

So: offer the desktop scheduled task when `create_scheduled_task` is in the session; otherwise
say how to run the report by hand, and `tm due` reminds the user at session start.

## The schedule check-in (GS) and step F5

GS is asked on its own at Check every step and Just the big calls. Its card says, in plain words
and with every point restated:

- **when:** every week on the config's `digest.schedule` day (`weekly_monday` by default: every
  Monday) at 09:00, their local time (or the hour they prefer);
- **what runs:** a new weekly run of the same category and market, which copies this run's
  settings, compares with this week's snapshot, checks this week's calls, rebuilds the page and
  republishes it to the same link (the link only: nothing is sent to anyone);
- **what it costs:** nothing (TrendsMesh, the Ad Library and the page are free per run; it uses
  their plan's TrendsMesh calls);
- **how to stop it:** say "stop the weekly trend report" ("Stopping the schedule" below); a task
  turned off only in the desktop app leaves no weekly reminder, so say it to Claude then too
  (with the schedule by hand there is nothing to stop);
- **where it works:** only while the Claude desktop app is open; a missed Monday runs at the next
  launch.

Hands-off decides GS by its rule: `by_hand`, unless the previous run's `schedule.how` is
`desktop_task` (`tm status --run <previous run> --json` gives its `schedule`): then `schedule`,
keeping the same task. A previous `by_hand` stays `by_hand`.

### `schedule`, with `create_scheduled_task` in the session

1. **Never make a second task for a category.** Look for one first: in a weekly run, the previous
   run's `schedule.id`; otherwise `list_scheduled_tasks`, a task whose id or title names this
   category and market. When one exists, keep it: record it again (step 3, with its id and cron)
   and create nothing. If it is paused, say so and ask whether to turn it on
   (`update_scheduled_task` with `enabled: true` only after a yes).
2. `create_scheduled_task` with:
   - `taskId`: `trend-report-<category slug>-<market lower case>`, for example
     `trend-report-beauty-us` (if it is taken, the tool names a free one: use that);
   - `title`: "Trend report: <category> (<market>)", in the user's language;
   - `description`: "Weekly trend report for <category> (<market>), republished to the same link";
   - `cronExpression`: `"0 9 * * <day>"`, the day from the config's `digest.schedule`
     (`weekly_monday` 1, `weekly_tuesday` 2, `weekly_wednesday` 3, `weekly_thursday` 4,
     `weekly_friday` 5, `weekly_saturday` 6, `weekly_sunday` 0), or the user's hour;
   - `prompt`, with `<workspace>` the absolute path of the folder that holds `runs/`, in double
     quotes wherever a command uses it (it may hold spaces): "Update my trend report for
     <category> (<market>). The workspace is "<workspace>", the folder that holds `runs/`; this
     session does not start there. First run `cd "<workspace>"` on its own, then begin every `tm`
     command with `cd "<workspace>" &&`, for example `cd "<workspace>" && tm next --run <run>
     --json`. Find the last trend research run of this category in runs/04-trend-research/ and
     start the weekly run after it. If the Artifact tool refuses the page's files, keep the page
     local: give the path of its index.html, say plainly that the link was not updated this week,
     and record nothing as published."
3. `tm research schedule --run R --how desktop_task --id <taskId> --cron "<cron>" --json`
   (it writes `schedule = {how: "desktop_task", id, cron}` into `run.json`; GS reads it next week).
4. Tell the user it is set, when the first run is, that it runs while the desktop app is open, and
   how to stop it. Then `tm done F5 --run R`.

A scheduled run has not yet been run end to end: the acceptance (`trends` T6) starts the task
once with `run_scheduled_task` and checks where its run landed, whether the collector saved its
answers and whether the page was republished.

### `by_hand` (no `create_scheduled_task`, or the user says no)

Record it: `tm research schedule --run R --how by_hand --json` (F5 is then skipped). Say, in one
sentence in their language: "Each week, open Claude Code in this folder and say 'update my trend
report': I compare with this week and republish to the same link. When a week has passed, I'll
remind you at the start of a session." The reminder is `tm due`, which the plugin runs at session
start: it lists a finished trend research run with the weekly digest, the latest of its chain, a
week or more after it was made ("the weekly trend report is due"). It leaves out a run whose
schedule is a desktop task (the task starts the next run). A weekly run started and left
unfinished is listed from the next day as "this week's trend report … is not finished": the user
asks Claude to continue it, and once it is done the weekly reminder comes back a week after it.

When the session has no `create_scheduled_task` and the user wants a real schedule, say it once:
scheduled tasks come with the Claude desktop app; there it can be set up in one step.

## Stopping the schedule

When the user says "stop the weekly trend report" (or that they turned the task off themselves):

1. Find the task: the latest run's `schedule.id` (`tm status --run <latest run> --json`), else
   `list_scheduled_tasks`, a task whose id or title names this category and market.
2. Turn it off with `update_scheduled_task` and `enabled: false`. Delete it
   (`delete_scheduled_task`) only when the user asks to delete it, after a yes. When it is
   already off or gone, change nothing in the app.
3. `tm research schedule --run <latest run> --how by_hand --json`, so next week's run keeps it by
   hand and `tm due` reminds them again (a run left as `desktop_task` with no task behind it is
   never reminded).
4. Say the by-hand sentence above, once.

## The weekly pack (organic video)

The same pattern, with the weekly pack's words (`skills/organic-video/references/flow.md#i5`): its
check-in `schedule` ("Set up the weekly pack") before I5, a task per channel (`weekly-pack-<channel
slug>`) on the config's `weekly.run_day` whose prompt names the workspace, the organic-video skill,
the channel and "plan my week of videos", and nothing made before the user approves the week. It is
recorded with `tm schedule --run R --how desktop_task|by_hand` (the command `tm research schedule` is
the alias of, for trend research runs). `tm due` reminds a week after a done week run with no task
behind it ("next week's videos are due"), and the day before a week's flexible day and on that day, while its video is not started.
