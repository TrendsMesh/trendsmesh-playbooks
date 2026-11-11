---
name: trend-research
description: Use when the user wants trend research on a category or market, to know what is moving or what's trending in it, which trends to act on now, a weekly trend digest or weekly trend report, or paid vs organic for trends; also 'update my trend report'.
---

# Trend research (TrendsMesh playbook 04)

Maps one category in TrendsMesh, measures how fast each trend gains creators against the rest of
the category, sorts the trends into four stages (act now, still rising, too late, past its peak),
writes up the picks with their evidence videos, checks which rising trends are already in paid
ads, and ends with one read-only page with up to three views: the category report, the weekly
digest (what changed and whether last week's calls held) and paid vs organic. Every week the page
is republished under the same link. Nothing in it costs money per run.

**The engine `tm` owns the flow, the numbers, the stages, the run state, the check-ins and the
stops.** You do the judgement (the seed phrases and the split, the relevance review, the review of
the picks, the Ad Library reading, the text) and record it through `tm`. Never improvise the flow,
never compute a count, a growth number, a band or a stage by hand, never skip a step or a
check-in, whatever the reason given. Call it as `tm ...` (the plugin puts it on PATH); add
`--json` and read the one JSON object. Pass JSON as files in `03_wip/`, never inline (inline JSON
breaks on Windows). Exit codes: `0` done, `2` stop (something to fix or fetch first, or the user
must act: the message says what), `1` error (read the message and fix the cause; never work around
it). Never run the handoff's scripts or call a trend API directly.

**Language:** talk to the user, and write every output (picks, the digest text, cards), in the
run's language (`language` in the config). `tm` messages are English: put them in the user's words.

**Words:** say "check-in", never the spec's other word for it. The levels are **Check every
step**, **Just the big calls** and **Hands-off**. Ask **one plain question at a time**. The user
never sees `tm` or any command, flag, check-in or step id, file paths they don't need or JSON: you
run those, they see plain words. The words the spec fixes are used verbatim (`references/rules.md`):
"creators in TrendsMesh evidence", "none found in Ad Library titles", "Not checkable without
Foreplay", "weak match", "Moved by review".

**Where things are:** this skill's `references/` (`flow.md` every step, `checkin-cards.md`,
`rules.md`, `variants.md`, `lessons.md`) and `templates/picks_template.json`; the shared
references in the plugin's own `references/` folder, two folders up from this skill
(`../../references/`): `pages.md` (publishing the page), `trend-collection.md` (how answers are
saved), `schedule.md` (the weekly schedule).

## 1. Readiness first (also `/trendsmesh-playbooks:doctor`)

Follow the doctor's "Trend research" section (`commands/doctor.md` in the plugin):

1. **TrendsMesh**: sign-in first, then the plan (`../refresh-ad/references/trendsmesh-sign-in.md`,
   without its guess-mode lines): `ok`, `free`, `no_agents`, `inactive`, `skipped` or `missing`.
   **Meta Ads**: one `ads_library_search` call: `ok`, `missing` or `not_enabled`. **Artifacts**:
   `ok` when the `Artifact` tool (or the older `publish_files`) is among this session's tools,
   else `missing` (no call; never ask the user to add it through `/mcp`). Never guess a result.
2. `tm doctor --playbook trend-research --outputs <chosen, or all three> --mcp
   trendsmesh=<s>,meta=<s>,artifacts=<s> --json` (no `--report`: the support report is
   `/trendsmesh-playbooks:doctor`'s). The first `tm` call on a computer installs the
   base tools (about 0.5 GB): say so, and give it the Bash tool's longest timeout (10 minutes).
3. Show its `card` in plain words. **Without TrendsMesh, trend research stops**: it reads every
   number from TrendsMesh, so there is no guess mode. Never guess trends, never offer to run on
   guesses. Say what is missing, then the sign-in (once) or the Agent-plan offer (once, `tm offer`),
   and that the run continues from the same place once TrendsMesh is ready. **Meta Ads and shared
   page links are warnings**, never stops: without Meta the paid check says "not checked"; without
   a publishing tool the page is a local file instead of a link. Say each once.
4. **Keys never appear in chat.** Trend research needs none: TrendsMesh and Meta are signed in
   through `/mcp`. Never search for, read, print or ask for a key or token.

## 2. Intake (A0), one batch of questions

A new category: `tm run new --playbook trend-research --name <category> --json`, then the intake
in one batch with defaults: the level, the category phrase (a link, store, competitor or ad as the
input is "not supported yet": ask for a phrase), market and language, focus (optional), outputs
(the category report always; weekly digest; paid view; default all three), currency. Then `tm
config write`, `tm config check`, `tm done A0`. Details: `references/flow.md#a0`.

**The weekly run** ("update my trend report", a scheduled task, or the reminder at session
start): first `cd` into <workspace> (the folder that holds `runs/`), and stay there for every
`tm` call. Find the last trend research run of this category and market in
`runs/04-trend-research/` (the one no other run follows), then `tm run new --playbook trend-research --name <same name>
--after <that run> --json`, then `tm config write --run R --from-previous` (it copies the config
and sets Hands-off). Set another level only after the copy, and only if the user asked. No intake
questions. The order of the weekly run: `references/flow.md`, "The weekly run, in order".

## 3. The loop

**Start from the run's state.** When a run exists (the user names it, or one under
`runs/04-trend-research/` is not done), run `tm next` on it **before you answer**, and answer from
what it says. On every resume (a new session, after a stop), run `tm trends collect on --run R`
again before the next TrendsMesh or Ad Library call (`ads_library_search` is saved too). Before you do, plan or describe a step's work, read its
section in `references/flow.md` (the `ref`): never from memory.

`tm next --run R --json` → act on `action`, then `tm next` again. Always.

| action | what you do |
|---|---|
| `work` | Read the step's section in `references/flow.md` (`ref`). Do the work. Record each file you write yourself with `tm record`. Then `tm done <step> --run R`. |
| `ask` | Show the check-in as a card (`references/checkin-cards.md`), restating every point, wait for the answer, then `tm decide <id> <choice> --run R [--note ...]`. "Approve the picks and the page" is shown once and recorded as `tm decide G2 accept`, then `tm decide G3 publish` or `keep_local`. |
| `auto` | Decide by the rule in the message: `tm decide <id> <choice> --by rule --note "<the data behind it>" --run R`. List it in the final report. |
| `stop` | Tell the user what happened, what to do, and that the run continues from the same place. **Then wait.** A map that changed a lot is cleared by `tm decide G1 accept --change` after the user saw it, not by `tm resume` (`checkin-cards.md`). |
| `done` | Final report: the page's link (or the local `index.html`), the picks in short, the calls that held, the schedule, what was not checked, and every decision taken by rule with its data. |

- **Every stop** you report, from `tm` or your own (a TrendsMesh limit: `tm stop --run R --reason
  <id> --what ... --todo ...`, cleared with `tm resume --run R`), says what happened, what to do,
  and that the run continues from the same place.
- **Collection:** `tm trends collect on --run R` right before the first `search_trends` (B1), again
  at every resume right before the next TrendsMesh or Ad Library call (the 10-minute claim window runs only
  from `collect on` to that call), and `tm trends collect off --run R` at the end. An answer
  that comes with "This answer was not saved…" is saved with `tm trends ingest`, as it says
  (`trend-collection.md`).
- The user may change the level at any time: `tm level <every_step|big_calls|hands_off> --run R`.
- A run spans days and sessions: everything lives in the run folder; `tm next` picks it up.
  `tm due` (run at session start) reminds the user when a weekly report is due.

## 4. Pages and the schedule

- The page is built by `tm research report` into `04_final/report_vNN/`; publishing follows the
  plugin's `references/pages.md`: with the `Artifact` tool (or the older `publish_files`), the
  first page a new private artifact, every later one the same link (`tm page link`), recorded with
  `tm page published`; never republished while the user is deciding; without a publishing tool,
  or when it refuses the files, the local `index.html` path, with nothing recorded as published.
  A decision in chat counts.
- The weekly schedule follows the plugin's `references/schedule.md`: a desktop scheduled task when
  `create_scheduled_task` is in the session and the user says yes, else by hand. "Stop the weekly
  trend report": its "Stopping the schedule".

## 5. Hard rules TR1–TR10

**Read `references/rules.md` before step B1**, and keep it in force to the end. In short: TR1 the
map comes from searches split 5–8 ways to depth 2, reviewed for relevance, with hooks on their own
path; TR2 growth is counted from evidence videos (creators in TrendsMesh evidence); TR3 rule v3
decides the stage, and the review of the picks moves only with a written reason; TR4 contradicted
trends are out, language and sensitivity are risks; TR5 every pick is scored on seven criteria;
TR6 each pick says what, why now, how, the window and the risk; TR7 the Ad Library reads titles
only; TR8 the digest diffs this week's snapshot against last week's; TR9 last week's calls are
checked; TR10 one read-only page, relative numbers first. R3: every number has a source, and a
hypothesis is never a finding.

## Red flags: stop and go back to `tm next`

| Thought | Reality |
|---|---|
| "There are no trends in this category" | Never. A thin map shows its closest trends as a **"weak match"** (V7). |
| "Not in ads" | Say **"none found in Ad Library titles"**: the Ad Library returns titles only. Hooks are "Not checkable without Foreplay". |
| "I'll count creators myself" | `tm research growth` counts them, every time. Never a number by hand. |
| "I'll paste the videos into a file" | The collector saves every answer (`tm trends collect on`); a missed one goes through `tm trends ingest`. |
| "No TrendsMesh, I'll use what I know" | Trend research stops without TrendsMesh: the sign-in or the offer, never guesses. |
| "The user is in a hurry, skip the review" | The relevance review and the review of the picks run at every level, Hands-off included. |
| "This trend is obviously act now" | The stage comes from rule v3. Move it only from act now, with a reason the page shows ("Moved by review"). |
| "Republish now, they'll see the update" | Never while the user is deciding on the page. |
| "Make a fresh link this week" | A weekly page goes to the same slug, found with `tm page link`. |
| "Set the level, then copy last week's config" | The copy sets Hands-off over it: copy first, then the level. |
| "Ask everything at once to save time" | One plain question at a time (the intake batch is the one exception). |
| "Show the key so they can check it" | Never. Keys never appear in chat; trend research needs none. |

## References

`references/flow.md` (every step), `references/checkin-cards.md`, `references/rules.md`,
`references/variants.md`, `references/lessons.md`; `templates/picks_template.json`. In the
plugin's own `references/`: `pages.md`, `trend-collection.md`, `schedule.md`. The living spec is
`spec/04-trend-research/` in the repository.
