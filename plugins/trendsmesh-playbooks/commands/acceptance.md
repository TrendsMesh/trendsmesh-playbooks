---
description: Run a TrendsMesh acceptance suite with the user (default "recuts", the re-cut acceptance) on their real data, case by case, with the playbook the suite names, and write the report into the suite's folder, for them to keep or send privately to the TrendsMesh team. Use it when the user wants to run or continue the acceptance.
---

Run the acceptance suite `$ARGUMENTS` (when empty: `recuts`) with the user. You are the
operator: you run every case on their real data with the suite's playbook, and they give you
what only they can: a file, a key, a budget, a connection, and their verdict after watching,
listening or reading. The suite's playbook is the `playbook` line of
`data/acceptance/<suite>.yaml` (none means Refresh an ad), and `tm acceptance start` answers it
too (`playbook`): `01-refresh-ad` runs with the "Refresh an ad" skill
(`skills/refresh-ad/SKILL.md`), `04-trend-research` with the "Trend research" skill
(`skills/trend-research/SKILL.md`), `02-creative-brief` with the "Creative brief" skill
(`skills/creative-brief/SKILL.md`), `03-organic-ai-video` with the "Organic video" skill
(`skills/organic-video/SKILL.md`). The engine `tm` keeps the cases,
the results and the spend in `acceptance.json`, so the acceptance continues in a new session from
the same place. Talk to the user in their language, in plain words: they never see `tm`, a flag,
a case's JSON or a check-in id.

**One plain question at a time.** Ask it, then wait for the answer before anything else.
**Keys are never pasted into the chat**, not even when the user offers: a missing key is set in
`/plugin` → trendsmesh-playbooks → configure (the doctor's card says how), and you check it with
the doctor again. Say "check-in", never "gate"; the levels are **Check every step**, **Just the
big calls** and **Hands-off**. Every stop you tell the user about says what happened, what to do,
and that the acceptance continues from the same place.

1. **Readiness.** Run the doctor's checks for the suite's playbook (`commands/doctor.md`: steps
   1 to 4 for Refresh an ad, its "Trend research" steps 1 to 3 for trend research, its "Creative brief" steps for creative brief, its "Organic video" steps for organic video) with two
   changes: TrendsMesh is checked without a question (its state if its tools answer, otherwise
   `missing`: for Refresh an ad a warning only, the playbook runs on as guesses; for trend
   research the case that needs it asks for it), and Meta Ads is `missing` when its tools are
   not in this session (a case's `meta` need asks for it); when they are, the doctor's Meta check
   may ask for the ad account, its one question here. Show the card
   in a few plain lines; it is a statement, not a question. What is missing is asked for when a
   case needs it.
2. **Start or resume.** `tm acceptance start --suite <suite> --json`. It creates the suite's
   folder in this workspace, or resumes the one already started (`resumed`); it never overwrites.
   Say in one line where the acceptance stands. When the suite has a budget (`budget` is not
   empty), state it in plain words (for `recuts`: at most 4 US dollars on Replicate and 3,000
   ElevenLabs credits for the whole suite, and nothing on Meta ads; for `organic`: at most 10 US
   dollars on Replicate and 5,000 ElevenLabs credits, spent on the person's own channel). Its
   approval is asked once, at the first case that needs a budget (step 4), before that case's
   first paid call. A suite without a budget spends nothing: say nothing about a budget.
   **For `trends`, `briefs` and `organic`, work from the suite's folder.** Its case runs belong to that folder (`path`,
   `acceptance/<date>_<suite>/`), not to this workspace: it holds their `runs/`, `library/` and
   `.trendsmesh/`. Right after `tm acceptance start`, `cd` into it and stay there for every `tm`
   call and every TrendsMesh and Ad Library call: the collector looks for its marker from Claude's
   folder, and `tm run new`, the weekly run's lookup and `tm seeds list` read the folder they run
   in. `tm acceptance` works from there too. In a new session, `tm acceptance start` from this
   workspace first (it resumes), then `cd` again. The one exception is `briefs`' B8: it is worked
   from the `trends` suite's folder, where the seeds are, and recorded back in the `briefs` folder,
   as its steps say.
3. **The loop.** `tm acceptance next --json`, then act on `status`:
   - `case`: work through the case below, record it, then `tm acceptance next` again.
   - `stop` (exit 2): tell the user its message in plain words and wait.
   - `done`: every case has a result (also when a new session resumes a finished suite that has
     no report yet): write the report, step 6.
4. **Each case.** Say which case it is (`position`), its title and what it proves, in one or
   two lines. When the case's first step says to ask something first (H9: whether the person has
   a Windows machine to run it on), ask that before its needs, and wait. Then, for each of its
   `needs` the session doesn't have yet, one plain question, and wait:
   - `meta`: when the Meta Ads tools (`ads_get_ad_entities`) are not in this session, ask the
     user to connect the Meta Ads connector in Claude Code with their Meta login and to tell you
     when it's done. When they are, ask for the ad account if you don't know it, and check it
     with one `ads_get_ad_entities` call (for trend research: one `ads_library_search` call,
     and no ad account is needed).
   - `trendsmesh`: when the TrendsMesh tools (`get_usage`) are not in this session, ask the user
     to sign in to TrendsMesh in Claude Code (`/mcp`, **trendsmesh**, **Authenticate**) and to
     tell you when it's done. When they are, check it with one `get_usage` call: a plan without
     trend data is said as the doctor says it (`commands/doctor.md`, "Trend research" step 4).
   - `artifacts`: when neither `Artifact` nor the older `publish_files` is in this session, say
     that this session can't publish claude.ai artifacts (the `Artifact` tool is built into Claude
     Code in the Claude desktop app, not added from `/mcp`) and ask whether they can run the case
     where it is; then see that `Artifact` (or `publish_files`) is among the tools.
   - `file`: ask for the path of the file the case's `steps` name (the original video as
     uploaded to Meta, a product clip, an earlier case's music take).
   - `key`: the doctor's card says whether the key is set. If it isn't, tell them where to set
     it (`/plugin` → trendsmesh-playbooks → configure), never in the chat, and run the doctor
     again once they say it's done.
   - `budget`: the first time in the suite (`budget.approved` false), ask for the suite budget's
     one yes and record their words: `tm acceptance approve --note "<their words>"`. In the case
     run, money is approved only at the playbook's spending check-in, with `tm budget approve
     --run <case run> <kind> <total>` for the case's `kinds`, and the case run's total for a kind
     never goes past its own spend so far plus `budget.left` for that kind. If the case costs more than is left, say
     so with both numbers and ask how to go on. In `organic`, a case's money is spent in the
     production run its steps start (`tm organic start`): approve it there (`--run <that
     production run>`), on the same terms; its spend counts in `budget.left`.
   - `human_verdict`: asked after the run (step 5).
   If the user says they can't provide something, record the case blocked with what was
   missing, in their words: `tm acceptance record <id> blocked --note "<what was missing>"`.
   That is the only way a case is left out: never skip one (a case that waits for a later day, like `trends` T6, stays to do and comes last), and never mark one blocked
   without their word.
5. **Run it.** Do the case's `steps` with the suite's playbook skill in the case's own run
   folder (`run`):
   use it instead of `tm run new` (one exception: `trends` T6 follows T2's run with `tm run new
   --after`, as its steps say), and from there `tm next --run <run>` as the skill says, at the
   level the steps name. For a later case on the same ad, offer the earlier case's intake
   answers ("the same answers as for H2?") as one question; the level and the budgets are never
   carried over: they come from this case's steps (H8 is Hands-off with no AI budget). When the engine refuses what a case
   expects (a diagnosis that allows no re-cut on today's data, a red QA check), tell the user
   what it said and what that means for the case, and ask how to go on.
   - A case with `judge` set is the user's to judge. Give them the review copy's path (the
     timecoded copy in the run's `showcase/review_tc/`) and say what to watch or listen for and
     at which seconds (the case's `judge`, with this run's own seconds where it points to them).
     Ask one question: does it pass? Record exactly what they say, with `--by person`:
     `tm acceptance record <id> pass|fail --by person --note "<their words, and the seconds>"
     --evidence <review copy> <QA file> ...`. The engine refuses a judged case without
     `--by person`: you never judge a video or a sound for them, and their fail is recorded as a
     fail.
   - A case with `judge: null` is proven by recorded numbers: compare them with its `pass`,
     record `pass` or `fail` yourself with the numbers in the note and their files as evidence,
     and tell the user the result in one line.
6. **The report.** After the last case: `tm acceptance report --json` writes `report_vNN.md`
   (results, notes, evidence, spend and the totals against the suite budget) in the suite's folder
   (`acceptance/<date>_<suite>/`), next to `acceptance.json` and the case runs. Give the user its
   path and its text. Say in plain words that the report holds their own numbers (their ads'
   results, their channel, their spend), so it stays with them: they keep it, or, if they want the
   TrendsMesh team to see it, they send the file to the team privately, by email to
   contact@trendsmesh.com. Never suggest posting it anywhere public (an issue, a forum, a social post), and never
   send it yourself. A case that waits for a later day (`trends` T6, seven days after T2) is left to
   do, and the report says it is not run yet.

**Resume.** In a new session the same command picks up from `acceptance.json`: step 1, then
`tm acceptance start` (it resumes; for `trends`, `cd` into the suite's folder after it), then
`tm acceptance next`. A case whose run folder already
has steps done goes on from its own state: `tm next --run <run>`.
