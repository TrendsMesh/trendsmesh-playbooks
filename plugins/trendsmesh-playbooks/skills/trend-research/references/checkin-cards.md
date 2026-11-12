# Check-in cards

A check-in is a decision the user makes. Which ones the user sees depends on the level; the
engine decides that (`data/trend-research/checkins.yaml`) and says `ask`, `auto` or `stop` in
`tm next`. Trend research has five, and none spends anything: every card says "free".

## How a card looks

Use Claude Code's question cards (the AskUserQuestion tool): **one plain question at a time**,
options with a short label and a description, your recommendation first with "(recommended)" in
its label.

1. The header says what is decided and what happens after the answer.
2. **Restate every point in the message itself** (HANDOFF §4): the card's content, each rule and
   each option, in full. Never "see above", never only a link or a file.
3. Each number carries its source, and creator counts are "creators in TrendsMesh evidence" (R3).
   For trends: the position in the sample first (the band, "2.3× the new creators of a typical
   <category> trend"), the raw counts second.
4. In the user's language and plain words: no ids, commands, file names they don't need, or JSON.
   "Check-in", never the spec's other word for it.

The user can always answer something else ("drop the fan edits", "from now on, just the big
calls"). Redo the work as a new version and show the card again; record only the final answer. A
level change is `tm level <every_step|big_calls|hands_off> --run R`; a decision changed later
needs `tm decide <id> <choice> --change --run R`.

## The cards

**G0 · Confirm the seed phrases and market** (after A1). The seed phrases, each with its source;
the market, the working language and the market language (`references/languages.md`); the currency; the focus, if any; the outputs chosen. Choice: `accept`
(after any change the user asks for).

**G1 · Accept the category map** (after B4). The sub-categories, each with its count of trends;
what was kept; what was dropped and why (noise, contradicted, and your review's drops with their
reasons, so the user can restore any); the re-tags; the weak matches, if the map stayed thin
("weak match": its closest trends, never "no trends"); the shortlisted hooks in fit order, in two
lists: **used in your category** ("used in your category: N videos" of those checked) and
**transfers** (they fit, no category video uses them yet), each with its fit, its `why` and its Ad Library verdict ("competitor found: <advertiser>", "none
found in Ad Library titles" or "not checked"). In a weekly run, what is new since last week
(`tm research map-change`), and the review names carried over from last week that were removed
because their trends left the searches. Choices: `accept`, or `changed_a_lot` (only by rule in
Hands-off, when the map changed a lot: the run stops so the user sees the new map).

**Clearing `changed_a_lot`.** The stop is cleared by a new G1 decision, never by `tm resume`. Show
the new map as the G1 card above. Apply any drops or re-tags the user asks for (a new review
version, the map rebuilt). On the user's go-ahead, record `tm decide G1 accept --change --run R
--note "<their words, and what changed in the map>"`, then `tm next`.

**G2 · Accept the picks** (after D3). Per pick, in order: its stage (act now / still rising); its
band and the velocity index ("top 10% of <category> topics", "2.3× the new creators of a typical
<category> trend") first, then the raw counts ("7 new creators in TrendsMesh evidence in 14
days"); why now; the risk; the paid verdict ("none found in Ad Library titles", "a few advertisers:
…", "crowded in paid", "Not checkable without Foreplay", or "not checked"). Then every move with
its reason ("Moved by review"), and the lens lines when there is a focus. The card says what the
evidence shows plainly and words the rest as advice or a guess (`flow.md#d3`, R3): "try …", "may
suit …", never "works" or "fits" as a fact. Choice: `accept` (after any change the user asks for,
as a new picks version, checked again).

**G3 · Approve the page before it is published** (after E1). The local page's path (the
absolute path of `index.html`, so they can open it), the views it has (category report; the
weekly digest, or "it comes next week"; paid vs organic), and what publishing does: a first page
becomes a private link only they see until they share it; a weekly page goes to the same link
as before, so whoever has it sees this week's. Without a publishing tool in the session (neither
`Artifact` nor `publish_files`), say the page stays a local file, because this session can't
publish claude.ai artifacts. Choices:
`publish`, `keep_local`.

**GS · Set up the weekly report** (before F5, weekly digest only; on its own at Check every step
and at Just the big calls). Weekly on the config's `digest.schedule` day (Monday by default) at
09:00, their local time; what runs (a new run of
the same category and market that compares with this week, checks this week's calls and
republishes the page to the same link; nothing is sent to anyone); what it costs (nothing: no
per-run cost; it uses their TrendsMesh plan's calls); how to stop it (say "stop the weekly trend
report": `references/schedule.md`, "Stopping the schedule"). Without `create_scheduled_task` in the session, the card offers only "by hand"
and says what that means. Choices: `schedule`, `by_hand` (`references/schedule.md` at the plugin
root).

## A merged card (Just the big calls)

`tm next` gives `checkin.card` and the member `ids` still open. Show one card that covers them
all, then record each member.

| Card | Members | When | How to record |
|---|---|---|---|
| Approve the category map | G0, G1 | after B4 (the map and the hooks path) | one choice fits both: `tm decide approve_map accept --run R` |
| Approve the picks and the page | G2, G3 | after E1 (the page is built) | shown **once**, recorded **one by one**: `tm decide G2 accept --run R`, then `tm decide G3 publish --run R` or `tm decide G3 keep_local --run R` (their choices differ, so the card's id is refused) |

GS is never merged: a standing schedule needs its own yes.

## Decided by rule (`auto`)

`tm decide <id> <choice> --by rule --note "<the data behind it>" --run R`, with the rule `tm next`
names (FLOWS.md section G):

| Id | Rule | The note says |
|---|---|---|
| G0 | logged: the seed phrases and market from the intake; in a weekly run, the previous run's | the phrases, market and language |
| G1 | the review applied: `accept`; `changed_a_lot` when `tm research map-change` says the map changed a lot (V26); cleared only by `tm decide G1 accept --change` after the user saw the new map | kept, dropped, the share new and the new groups; the review names removed because their trends left the searches |
| G2 | the review applied; the top N by score (`picks.act_now`, `picks.still_rising`) | the picks with their weighted totals, the moves |
| G3 | `keep_local` when neither `Artifact` nor `publish_files` is in the session; otherwise `publish` (a first page private, a weekly page the same link) | whether the session can publish, the slug if any |
| GS | `by_hand`, unless the previous run's `schedule.how` is `desktop_task` (`tm status --run <previous run> --json` → `schedule`): then `schedule`, keeping its task | the previous schedule, or none |

Every decision by rule is listed in the final report with its rule and its data, and shown at the
next check-in the user sees.

## Stops the user must clear

`changed_a_lot` at G1 (in Hands-off; cleared as above), TrendsMesh not ready (signed out, no Agent plan, a limit
reached), answers missing fields the run needs (`tm trends check-fields`), a file of yours that a
check refused and that needs the user (rare: you fix your own files). Each stop says what
happened, what to do, and that the run continues from the same place. Then wait.
