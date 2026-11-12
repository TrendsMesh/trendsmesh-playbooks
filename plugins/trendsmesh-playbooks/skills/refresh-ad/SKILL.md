---
name: refresh-ad
description: Use when the user wants to refresh, fix or improve a Meta video ad that used to perform and is fading, or asks which ads are fading.
---

# Refresh an ad (TrendsMesh playbook 01)

Takes a Meta video ad that used to win and is fading, finds which part of the funnel is fading,
finds what is rising now (TrendsMesh), changes only that part, and tests the new version against
the old one. Outputs the user picks from: creative brief, edited real video, AI video, live test.

**The engine `tm` owns the flow, the rules' maths, the run state, the check-ins, budgets and
stops.** You do the work at each step and record it through `tm`. Never improvise the flow, never
compute R1, R2, R4 or R6 by hand, never skip a step or a check-in, whatever the reason given.
Call it as `tm ...` (the plugin puts it on PATH); add `--json` and read the one JSON object.
Pass JSON arguments as files in `03_wip/`, never inline (inline JSON breaks on Windows).
Exit codes: `0` done, `2` stop (the user must act), `1` error (read the message and fix the
cause; never work around it). Never run `python -m tm.tools.*` or the handoff's scripts.

**Language:** a run has two (`languages` in the config, `../../references/languages.md`): the
**working language**, for everything the user and their team read (cards, briefs, plans, reports;
by default the language the user writes in), and the **market language**, for everything the
audience sees or hears (ad copy, captions, voiceover, on-screen text; by default the working
language unless the account or landing page points elsewhere). `tm` messages are English: put
them in the user's words.

**Words:** say "check-in", never "gate". The levels are **Check every step**, **Just the big
calls** and **Hands-off**. The user never sees `tm` or any command, flag, check-in or step id
(G6, A2), file paths they don't need or JSON: you run those, they see plain words.

## 1. Readiness first (also `/trendsmesh-playbooks:doctor`)

1. **TrendsMesh: sign-in first, then the plan.** If the user has clearly said no to TrendsMesh
   (not a "not now"), run `tm signin skip --json` first (that keeps their no for this
   workspace), say in one line that you won't ask again, use the state `skipped`, and don't
   mention the plan. Otherwise follow
   `references/trendsmesh-sign-in.md`: ask
   the user to sign in (they skip only by saying so, and `tm signin` remembers it), read the plan
   with `get_usage`, and when the plan has no trend data make the offer once (`tm offer`). It
   gives the state: `ok`, `free`, `no_agents`, `inactive`, `skipped` or `missing`. None of them
   stops the run.
   **Meta Ads:** `ads_get_ad_entities` for one ad on the user's ad account (ask for the ad
   account first if you don't know it): `ok`, `missing` (not connected or not signed in) or
   `not_enabled` (Meta refuses this ad account).
2. `tm doctor --outputs <chosen or all four> --mcp trendsmesh=<s>,meta=<s> [--voice]
   [--caption-removal] [--fact elevenlabs_plan=cloning|no_cloning|unknown] --json`. The first
   `tm` call on a computer, and the first after a plugin update, installs the base tools first
   (about 0.5 GB; after an update mostly from the download cache): say so before it, and give it
   the Bash tool's longest timeout (10 minutes).
3. Show its `card` in plain words, without the flags in it. For each missing piece say what is
   missing, why it matters for the chosen output and the exact next step. Installs are yours,
   after one yes with the size and time: `tm env install <tier> --yes`. **Long commands:** say up
   front what they download and that they take minutes ("this downloads about 2.5 GB"), then run
   them with the 10-minute timeout or in the background (`run_in_background`) and wait for them:
   every `tm env install`, and the first `tm tool teardown`, which downloads the speech model
   (about 1.6 GB). Sign-ins, plans, keys and the Linux `sudo` line are the user's: say how, then
   **stop and wait**, except for the card's warnings.
   **TrendsMesh is a warning, never a stop.** The run can go on without it (no Agent plan, not
   signed in, or the user says no). Say the card's warning once in plain words: without TrendsMesh,
   the new hook is your best guess from their own winners and the Ad Library, not proof from what
   is rising now. The sign-in question and the offer were already made (step 1): don't repeat them.
   **An unknown voice-cloning plan is a warning too.** Pass `elevenlabs_plan=unknown` unless the user
   already said, and don't send them to look it up: a clone is needed only if V1c doesn't find the original
   voice, and V3 checks the plan then (`references/flow.md#v3`). **A plan known to have no cloning waits too.**
   Pass `no_cloning` and say in one line that cloning isn't available on their plan: V3 stops there with the
   choices, only if a clone is needed.
4. When the video tier is needed (edited or AI video), say once: Remotion is free for
   individuals and companies of up to 3 people; a company of 4 or more needs its own Remotion
   licence to render on its machines.

## 2. Intake (step A0), one batch of questions

`tm run new --name <product or short label> --json` gives the run folder (the ad is not
chosen yet; the name never needs to change). Then ask everything at once,
each with a default: ad account, market, the working and market languages, product and landing page, brand assets
folder (where the original video should be), outputs (default: the creative brief, the edited
video and the AI video), brand and compliance rules, budgets (AI in USD, ElevenLabs credits;
required in Hands-off for the outputs that spend; in Hands-off with the edited video, also how far
a re-cut may go and whether a segment weak by design may be re-cut, `flow.md#a0`), and **"How
involved do you want to be?"**:

- **Check every step**: every check-in, one by one.
- **Just the big calls**: only the big decisions (picking the ad, approving the changes, the
  spending, the launch, the results), plus the checks that need a person: listening to a voice or
  a re-cut.
- **Hands-off**: none but the launch of a live test (going live is always your call); budgets
  are set now, I run to the end and report. I still stop when I can't go on without you, at a
  red quality check, or before going over a budget.

**The live test is listed on its own, never a default.** It is the one output that spends ad
money and publishes ads. Say what it gives (a Meta A/B test of the new video against the original
ad, decided after 7 to 14 days) and that it needs its own budget; "go with the defaults" never
turns it on. Only when the user picks it by name, ask for the daily budget and the days (no
amount is suggested or assumed), and estimate it right away (`flow.md#a0`: R4 from the account's
numbers). Its launch is asked at every level, Hands-off too.

Voice rights, one confirmation: "You have the rights to the voice in this ad." Then write the
answers to `<run>/03_wip/intake_answers_v01.json` and run `tm config write --run R --answers F`,
`tm config check --run R --json` (ask about each problem it lists) and `tm done A0 --run R`.
Answers JSON and details: `references/flow.md#a0`.

## 3. The loop

**Start from the run's state.** When the user names a run (its folder, or the run they mean) or
plainly asks to continue it ("carry on", "continue my run"), run `tm next` on it **before you
answer**, and answer from what it says. When a run under `runs/01-refresh-ad/` is not done but the
request does not plainly continue it (it asks for something new, or does not say), **ask one short
question before anything else**, with enough to recognise the run: "You have an unfinished ad
refresh run <run folder name> from <created>, stopped at <step>. Continue it, or start a new one?"
(`tm status --run R --json` gives `created`, `step` and `trend_data`, and changes nothing). When `tm
status` gives `trend_data` with `expired` true, say so in the question, from its `message`: "Its
trend data expired on <valid_until>. Start a new run with fresh data, or continue this one on the
old data?" Then `tm next` on that run, or a new run (`tm run new`). Readiness and intake are for a
new run only. Before you do, plan or describe a step's work, read its section in
`references/flow.md` (the `ref`): never from memory.

`tm next --run R --json` → act on `action`, then `tm next` again. Always.

| action | what you do |
|---|---|
| `work` | Read the step's section in `references/flow.md` (`ref`). Do the work. Record every file you create yourself with `tm record` (tools record theirs; section 5). Then `tm done <step> --run R`. |
| `ask` | Put the check-in on the run page and show it as a question card (`references/checkin-cards.md`, "The run page"), wait for the answer, then `tm decide <id> <choice> --run R [--note ...]` (a choice clicked on the page: `tm page decision --run R <id> --record`). |
| `auto` | Decide by the rule in the message: `tm decide <id> <choice> --by rule --note "<the data behind it>" --run R`. List it in the final report. |
| `stop` | Tell the user what happened, what to do and that the run continues from the same place. **Then wait.** Do nothing else in the run until they say it is done. |
| `done` | Final report: outputs, every decision taken by rule with its data, spend against budgets. When the message offers the live test, end the report with that one question (`flow.md#e1`). When it offers the move of the winning ad, ask that one question; when the ad was moved, end the report with the user's part, step by step (`tm live-test move report`, `flow.md#e4`). |

- **`notice`:** whenever `tm next` gives a `notice` (a run without TrendsMesh data: the
  direction of changes and the launch when they are shown to the user, and the final report;
  Hands-off hears it at the launch, which is always asked, and in the final report), tell the
  user in plain words, in their language, with the card or report. It is a statement, not a question: never stop or ask for it.
- **What the changes rest on (guess mode).** At A5 the run records it: `tm evidence trendsmesh
  --run R --why "<reason>"` when TrendsMesh answers with trend data, `tm evidence guess --run R
  --why "<reason>"` when it does not. A guess run goes to the end like any other; its changes
  are labelled as guesses (the change register, `tm register check`), never as proof. If
  TrendsMesh stops answering mid-run (a limit, a lapsed plan, an expired sign-in), say so and
  wait for it, or switch to `guess` only after the user says yes. That switch is possible until
  the change register (A7) is done. After it the changes are decided and `tm evidence` refuses:
  tell the user, and write what you have (in the results library row, a trend status you can't
  fetch is `unknown`).
- **After a stop**, once the user has acted: a stop you recorded or a budget stop clears with
  `tm resume --run R`; an engine stop (a voice check, a red R8 item, a measurement not due, a
  test plan below R4's minimum events) clears with the decision, the new plan or the date that
  removes its cause; a test estimate below R4's minimum events, right after the diagnosis,
  clears with a new budget and estimate or with skipping the test (`tm live-test`). Then `tm
  next`. While a stop is open the engine refuses every spend, budget approval, paid tool and
  launch decision with exit 2: that is the stop holding, not an error to work around.
- **Hands-off with a missing budget** holds that output's paid step and every step after it
  (the steps are linear; except a re-cut's CR5a and CR5b: section 5). Say so plainly and offer
  to set the budget (`tm budget approve`).
- The user may change the level at any time: `tm level <every_step|big_calls|hands_off> --run R`.
- To change a decision already taken: `tm decide <id> <choice> --change --run R`.
- A run spans days and sessions: everything lives in the run folder. On a new session,
  `tm next` picks up exactly where it was. `tm due --json` lists measurements that are due.

## 4. Plan only supported changes

After `tm diagnose` and `tm structural` (A1a), and after `tm material`, always run `tm next`: if
it returns the "Accept the diagnosis" check-in with `do_not_refresh` (a landing page, account,
auction or unclear cause, or a stage that can't be refreshed for this material), relay its
message plainly and record `do_not_refresh` (by rule in Hands-off). The run ends there, before any
spend, with the diagnosis report.

Otherwise plan for **`diagnosis.target_stage`** (not `stage`) and only what
`tm changes --stage <target_stage> --material <material> --json` lists, plus the always-edits it
lists (a 4:5 version when `tm formats` says so, R6; the copy and thumbnail decision, R7).

**A middle target leads to path C-R, the re-cut** (`references/recut.md`, steps
`flow.md#cr1` to `#cr7`): flow R is on by itself. A segment weak by design (R2b,
`diagnosis.structural.structural` true) under another target is an improvement opportunity, never
a refresh trigger: offer it at the "Accept the diagnosis" check-in and, if the user takes it, turn
it on with `tm flow R --run R` then, and only then (it is refused after C1). In Hands-off run it
only when the config has `diagnosis.structural_recut: true`; otherwise report it as an
opportunity. Every cut is judged by `tm recut check` before anything renders.

Nothing else is considered. Still not supported, said plainly as "isn't supported yet": lip-sync
and any new speech on camera (a talking head gets the re-cuts only), static graphics, and a
reorder or cut inside one continuous shot at level 0 (offer the regenerated shot, level 4).

## 5. Assets, keys and costs (hard rules)

- **Run folder** `runs/01-refresh-ad/<date>_<name>/`: `00_raw 01_base 02_research 03_wip
  04_final 05_results showcase`, `manifest.md`. Never overwrite: new versions `_v01`, `_v02`.
  Never change a file in `00_raw` or `01_base`.
- **Every asset** gets a manifest row. Tools (`tm tool`, `tm render`, `tm r1`, `tm diagnose`,
  ...) record their own outputs; record the files you create yourself: `tm record --run R --file
  <path> --stage <stage> --source "<tool, MCP call and its parameters, or URL>" [--parent P]
  [--prompt T] [--params <JSON file>] [--model M] [--cost C] [--before-after "before: <path>"]
  [--raw-response-file F]`. Save raw MCP answers verbatim next to the assets they feed (as files
  in the run, recorded the same way).
- **Keys** (Replicate, ElevenLabs) are never searched for, read, printed, echoed, logged,
  committed or written into the workspace: not in part, not masked, not their length. The user
  sets them in `/plugin` → trendsmesh-playbooks → configure; `tm doctor` says whether each is
  set, without showing it.
- **Costs** (Replicate, ElevenLabs, Meta spend): before any paid call, show the prompts,
  parameters, model and the estimate (`tm budget estimate <ai_usd|voice_credits|test> <amount>
  --what "..." --json`). At Check every step and Just the big calls it needs the user's yes at
  the spending check-in; after a yes, `tm budget approve --run R <kind> <total>` (the engine
  refuses it before that check-in and after a `reject`). **A budget is one running total per
  kind in the run**, shared by every check-in that spends it (the re-cut's with the AI video's
  for `ai_usd`, the re-cut's with the voice budget for `voice_credits`): `<total>` is what is
  already approved for the kind plus this check-in's amount, never this amount alone (that would
  lower the total, and the engine refuses a total below what is spent). Read both first with `tm
  status --run R --json`: `budgets` is the approved total per kind, `spend` what is spent. When no check-in in the run asks for
  the kind (ProPainter caption removal without the AI video), ask with the estimate and pass the
  user's words: `--note "<their words>"`; with the AI video in the run, the caption removal is
  approved on its own at VC, `--for VC --note "<their words>"`, and the AI video's plan (G6) later
  approves its amount on top (`flow.md#vc`). In Hands-off the budget approved at intake decides; a
  new amount is approved only when the run stops for that budget. Then run the tool through the
  engine, which books the cost first: `tm tool <name> ... --run R --cost <amount>`. Meta spend is
  booked first too: at activation, `tm budget spend --run R test <total> --what "live test"`, and
  only on exit 0 is anything activated (`tm done E3` is refused until it is booked). Exit 2
  means nothing ran or went live: tell the user and wait. Replicate prices are confirmed by the
  user before the first run (lesson 7). **Re-cuts:** one check-in, "Approve the re-cut budget",
  approves both kinds (ProPainter and Veo in USD, ElevenLabs Music in credits). In Hands-off a
  re-cut never stops for a budget: `tm recut check` leaves an L3 to L5 variant without its budget
  `waiting` and the free L0 to L2 ones are rendered. The voice budget covers a hook's new line and
  a re-cut's new line alike.
- **Meta:** campaigns, ad sets and ads are always created **PAUSED**. Creating them changes the
  account, so it is part of the approved test plan. Nothing goes live before a green R8 check
  and the launch check-in. **We never host files publicly.**

## 6. The A1 fetch (fits the context)

Weekly totals first, for every ad: `ads_get_ad_entities` at ad level, `time_increment=7`, from
today−92 to **today−2** (13 weeks that line up with R1's windows), only the fields R1 needs **plus
the retention ladder R2 reads**: `video_play_actions`, `video_p50_watched_actions`,
`video_p75_watched_actions`, `video_p95_watched_actions`, `video_p100_watched_actions` and
`video_avg_time_watched_actions` (without them the diagnosis can't see which part of the middle
fades). Then account-level weekly totals the same way. Then daily rows (`time_increment=1`)
**only for the top 5 ads by spend, and for the chosen ad if it is not among them**, with R1's
fields only: they are the bulk of the fetch (91 rows per ad against 13), so the six ladder fields
(about 200 characters a row) go on the weekly rows alone and the fetch still fits. Save every
answer verbatim in `01_base/` and pass the weekly files to
`tm r1 --run R --ads <weekly files> --account <account files> --json`. The average watch time is
whole seconds per day from Meta: never present it as precise. Details, fields, the structural
check's fetch (R2b) and the "Pick the ad" card: `references/flow.md#a1` and `#a1a`,
`references/meta-mcp.md`.

## 7. Stops for files (A2 and E2), in these words

- **A2, no video file.** The Meta MCP never returns the video (`download_hd_url` is null). Look
  in the brand assets folder first. If it is not there, record the stop with `tm stop --run R
  --reason missing_video --what "<what>" --todo "<todo>"` and tell the user: "The video file of
  <ad name> isn't in your brand folder, and Meta doesn't hand it over through this connection.
  Open <https://adsmanager.facebook.com/adsmanager/manage/ads?act=ACCOUNT&selected_ad_ids=AD>,
  open the ad, and download its video from the ad's media (or ask whoever made the ad for the
  original file). Put it in <brand folder> and tell me: the run continues from the same place."
  Only if the user can't get it: the low-quality preview, marked as such in the manifest and in
  every output.
- **E2, upload.** First prepare every file the approved plan uses: each video in each format
  (9:16, 4:5) and the thumbnail when the plan changes or shares it (R7). Then
  `ads_creative_upload_media` with the local files, all of them in one call when the tool takes
  several. It ends one of three ways:
  - It works: save the ids.
  - **An upload window** (the Claude desktop app): the tool opens a window in the chat where the
    user picks the files from their disk. That is not a failure and not a stop: it is an upload
    the user finishes. Before the call, send the user the files with the file-sending tool
    (SendUserFile), then one short instruction: "Here are the <n> files for the test: <names>.
    In the upload window, choose all of them at once and send: the ids come back to me by
    themselves." Videos and thumbnail go in one round. Then find the files by name in the answer.
  - The file can't be sent at all: record the stop (`--reason upload_by_hand`) and tell the
    user: "I can't send the videos to Meta from here. Upload these files to your Ads Manager
    media library: <file names>. Tell me when they're there: I find them by name and continue
    from the same place."

  Save the ids in `05_results/meta_objects_v01.json`. Never upload to a public host instead.
  Every creative is then created with the AI disclosure (`self_ai_disclosure`) the approved plan
  names: it can't be set later (`references/flow.md#e1`, `#e2`).

## 8. Hard rules R1–R9

**Read `references/rules.md` before step A1**, and keep it in force to the end. In short: R1 the
ad comes from the ranking; R2 the change follows the fading stage, the middle read from its
retention steps (or no refresh); R2b a segment weakest in every ad that uses the same file is an
opportunity, reported, never a refresh trigger; R3 every
number has a source and a hypothesis is never a finding (a change without TrendsMesh data is a
guess, said as one); R4 the test plan and thresholds are
written before launch, with enough events; R5 a results-library row per variant closes the run
(`tm library add --run R --row <file>`); R6 formats follow placements; R7 a copy and thumbnail
decision every time; R8 the quality and policy check blocks a launch on any red item; R9 a new
voice line is regenerated to length first, and checked against the original.

## Red flags: stop and go back to `tm next`

| Thought | Reality |
|---|---|
| "The user is in a hurry, skip this step / check" | Steps and check-ins come from `tm`. Make the step quick; never skip it. Saturation is always the Meta Ad Library. |
| "Any ad will do" | The ad comes from the R1 ranking. |
| "The user remembers the number" | Use the number from the run's data with its source, or leave it out (R3). |
| "I'll cut here, it looks fine" | Run `tm recut check` first; it decides. Nothing renders around it. |
| "This music edit passes QA, use it" | A beat-cut edit is never the final music. `tm recut music` first: reuse a take, or method E (`references/recut.md`). |
| "They already looked at it, launch" | R8 check, then the launch check-in. Red blocks, at every level. |
| "Show the key (or part of it) so they can check it" | Never, not masked either. `tm doctor` says whether it is set; they see it in `/plugin`. |
| "Use the preview, downloads are a pain" | Stop with the Ads Manager link first. Preview only as the last resort, marked. |
| "Don't bother them with prices" | Estimate first; approval or an approved budget; then `tm tool ... --cost`. |
| "No TrendsMesh, so stop and wait for the plan" | Never. Say the warning once (the sign-in question and the offer were made at readiness) and go on in guess mode. |
| "This hook looks like a trend, call it proof" | Proof is a saved TrendsMesh answer of this run. Anything else is a guess, labelled as one. |
| "The overlay boxes are probably right" | Look at the teardown's frame sheets before planning covering cards. |

## References

`references/flow.md` (every step), `references/checkin-cards.md`, `references/rules.md`,
`references/lessons.md`, `references/variants.md`, `references/recut.md` (the re-cut methods,
the edit list, music, limits), `references/meta-mcp.md`, `references/trendsmesh-mcp.md`,
`references/trendsmesh-sign-in.md`; templates in `templates/` (the middle diagnosis:
`templates/middle_diagnosis_template.md`).
