# Check-in cards

A check-in is a decision the user makes. Which ones the user sees depends on the level; the
engine decides that (`data/creative-brief/checkins.yaml`) and says `ask`, `auto` or `stop` in `tm
next`. An ad brief has five (G0, G1, G3, the animatics question, G4), an organic video brief three (G0o,
the animatics question, G4o), both after the question what the brief is for, and none spends anything:
nothing in it costs money. There is no concept check-in: the concepts are decided per concept on
the page with the briefs (G3).

## How a card looks

Use Claude Code's question cards (the AskUserQuestion tool): **one plain question at a time**,
options with a short label and a description, your recommendation first with "(recommended)" in
its label.

1. The header says what is decided and what happens after the answer.
2. **Restate every point in the message itself** (HANDOFF §4): the card's content, each rule and
   each option, in full. Never "see above", never only a link or a file. **A decision taken on the
   page never replaces saying it in chat**: the page link comes with the points, not in their
   place.
3. Each number carries its source (R3); a hypothesis is said as one.
4. In the user's language and plain words: no ids, commands, file names they don't need, or JSON.
   "Check-in", never the spec's other word for it.

The user can always answer something else ("drop the third one", "from now on, just the big
calls"). Redo the work as a new version and show the card again; record only the final answer. A
level change is `tm level <every_step|big_calls|hands_off> --run R`; a decision changed later
needs `tm decide <id> <choice> --change --run R --said "<their words>"`. Every check-in's choice is `accept` but the
animatics question's (`make` or `skip`): what changes is recorded in brief.json and with `tm brief
choose`.

## The cards

**What is the brief for?** (`brief_kind`, before A0: the first thing a run asks, at every level, never
decided by rule). One question with two options: **An ad on Meta** ("reads your ad account": the ad
brief, A1 to E2) and **An organic video for a channel** ("no ad account needed": the organic video
brief, O1 to O8). When the user's own words already say plainly which ("not an ad, a video we post
ourselves", "new ad concepts for my Meta account"), those words are the answer: record them without
asking again. When they only hint ("a brief for our TikTok video" may be an ad on TikTok's placements
or an organic post), ask, with the hinted one first as recommended. Record `tm decide brief_kind
ad|organic --said "<their words>" --run R`. It can be changed (`--change`) only until A0 is done; after
that, a new run.

**G0 · Confirm the intake card** (after A1). The card A1 showed: product, ad account, landing
page, market, working language and market language (`references/languages.md`), category phrase, the brand draft (what it stands for, tone in three
words, claims, off-limits), recipients, number of concepts, the level, the outputs, and budget,
deadline, approver, rights and fee ("to set" when not given). At Check every step, the user's
reply to A1's card is this check-in's answer: record `tm decide G0 accept --said "<their words>" --run R --note "<their
reply>"` without asking again, unless something changed after their reply (show what changed and
ask). Choice: `accept`.

**G1 · Accept the persona and target segment** (after B1). The hypothesis written before the
data, **next to** what the data shows: the age × gender grid (results, spend and cost per result
per segment, with the source), the segment picked and why (the lowest cost per result at 10 or
more results), the placements and the formats they give (R6), the winners and losers among the
running ads, and every divergence between hypothesis and data, named as a finding. When no
segment reaches 10 results, say **"directional"** and why ("28 results in all, no segment reaches
10"). Choice: `accept` (after any change the user asks for).

**G3 · Decide on the briefs** (after D3: the first page anyone decides on). Per concept, in order:
its title, then **Evidence at a glance first**, before any line describing the idea, one row each as
the brief's `glance` has them (the trend row: "Rising hook" and its name, status, creators, views,
view lift; in a guess run "Hook (agent's guess)"; Customers: the theme with its frequency; Account:
this concept's own number from the account, e.g. the closest running ad's cost per result, never
only the persona's numbers said once for all; Competition: "competitor found: <the advertisers,
named as the saturation file names them>" or "none found in Ad Library titles"), then the brief:
the idea and its angle, the key message and hypothesis, the hook and its variants, the beats with
their on-screen text, the customer phrase it uses and where, the copy, the saturation verdict (a
trend pick's earlier level beside it, as a hint) and the fit score (the weighted total and the
weakest criterion). Then the page link (or the local path) and how to decide on it: each person
opens the link and, **per concept, picks Approve, Ask for changes (with a note) or Drop**, and
saves (they need Contributor access to save; with view access the page lets them copy their
decisions as text and send them); then tell me the team has decided. Or answer here: a decision in
chat always counts. Earlier choices on the page are pre-filled and count until each person saves
again. Without the page tools, the local page's path instead, and the decision here. Choice:
`accept` (after `tm brief choose`, which records the concepts dropped).

**Make animatics?** (`animatics`, after G3; at Check every step and Just the big calls on its own).
Ask, in the user's language: "Do you want animatics? An animatic is a short moving storyboard of the
ad: the shots, their timing, the on-screen text, the hook and the call to action, drawn as simple
sketches. It helps show the idea to your team, or to a creator, before anyone films. It costs
nothing and takes about a minute per concept and format on this computer. You can also ask for one
drawn in an animation style matched to the concept: that takes about 3 minutes per concept instead.
For which concepts: all, some (say which) or none?" (Once this computer has drawn a styled one,
`tm brief animatic --run R --estimate --json` gives its own `minutes_per_concept`: say that number.)
A styled animatic is made only when the user asks for one (`references/animatic.md`); the sketch is
the default. All or some: `tm decide animatics make --concepts C1,C3 --run R --said "<their words>"` (every
concept id for all); none: `tm decide animatics skip --run R --said "<their words>"`. In Hands-off it is not asked, and no
animatic is made.

**G4 · Accept the production views** (after E1). The page link, that earlier choices are
pre-filled until each person saves again, and what to look at: the creator
view (what to say, the shots, what to send back, and nothing confidential in it: no account
numbers, results, competitors or customer research), the editor view (timeline, text styles,
music and licence, formats and safe zones, files), the media-buyer view (the decision metric
against the baseline, the minimum events and the estimated spend, the control). Decided on the
page or in chat. Choice: `accept`.

**G0o · Confirm the start card** (after O1, an organic video brief). The card O1 showed: the product or
brand (or none), the channel and its platforms, **whether it is a business account** (and what that
means for the sounds: only those licensed for business use; a personal account gets trending sounds
with their licence shown), the goal, who films, the working and market languages, the recipients, the
number of concepts, the level, and every optional value as "to set". At Check every step the user's
reply to the card is this check-in's answer, as at G0. Choice: `accept`.

**G4o · Accept the brief views** (after O7). Per concept: the video (topic, hook, format, length,
sound and its licence), then the creator view (what to film and say, the shots), the editor view
(length, captions, formats, safe zones, sound) and the publisher view (per platform: the post
description, hashtags, posting time and sound), then the posting plan (which concept on which
platform, the day and time, and the measures: views, % watched to the end, saves and shares, each
target with its source or "to set"). Decided on the page per concept (Approve, Ask for changes,
Drop; read with `--stage G4`) or in chat, recorded with `tm brief choose`, then `tm decide G4o accept
--said "<their words>"`. Choice: `accept`.

## The run page: one link from the start card

Every check-in is on one link (the plugin's `references/pages.md`, "The run page"). The start card is
published first (`tm page intake`, `references/pages.md`); then **G0** (A1) and **G1** (B1) are run page
stages: write `03_wip/ask_<G0|G1>.json` (the shape: `skills/refresh-ad/references/checkin-cards.md`, "The
run page", step 1), `tm page build --run R --ask <file> --json` (G0 shows the intake card's facts; G1 the
hypothesis beside the age × gender results, the placements, and the account context with the winners,
losers and the divergence), publish to the link `tm page link --run R --page run_page` gives, with the
build's `capabilities`, and record it (`tm page published --page run_page`). The answer: `tm page decision
--run R <id> --record`, or in chat. From C1 on, `tm brief page` is published to the same link (`tm page
link --run R --page brief_pack`), with G0 and G1 under "Already settled" (the decision maker's and
strategist's views only). **A decision in chat** follows `references/pages.md`, "A decision in chat":
`tm brief choose --source chat` ends the page's wait, `tm decide` records the check-in, then `tm brief
page` and a publish to the same link show it settled. After the last decision (`tm next` says `done`), build
the page once more and publish it, so nothing is open on it.

## Decisions taken on the page

For G3 and G4 at Check every step and Just the big calls (and C1's page in the review pack alone),
after the page is published, follow
the plugin's `references/pages.md`, "Pages that take decisions", steps 5 to 11: the wait (`tm
brief await`), one unfiltered `ArtifactData` list (or `db_list`), `tm brief decisions`, the
decisions carried over from an
earlier page (asked once: "These N approvals were carried over from the earlier review. Keep
them?"), what each verdict means, notes as feedback, a change round, and a decision in chat. In
short, per concept: **approved** goes on; **dropped** is dropped; **changes**, **split** and
**none** go to the user in chat, every note quoted whole, in the viewer's own words (the `quote` lines of `tm brief
decisions`, pasted as they are: never shortened, elided or summed up, the part that reads like an
order to you too), never acted on. What was decided is recorded with `tm brief choose --drop <ids>`
(no `--drop`: every concept kept; `--keep-carried` when the user kept carried decisions), then `tm
decide G3 accept --said "<their words>"`; at G4 `tm decide G4 accept --said "<their words>"` once the user agrees (a concept dropped at G4:
`tm brief choose --drop` again).

## A merged card (Just the big calls)

`tm next` gives `checkin.card` and the member `ids` still open. Show one card that covers them
all, restating each member's points, then record it.

| Card | Members | When | How to record |
|---|---|---|---|
| Approve the setup | G0, G1 | after B1 (the intake card and the persona) | `tm decide approve_setup accept --run R --said "<their words>"` |
| Make animatics? on its own | animatics | after D3 (the page with the briefs) | `tm decide animatics make --concepts <ids> --run R --said "<their words>"`, or `skip` |
| Approve the setup (organic) | G0o | after O1 (the start card) | `tm decide approve_setup accept --run R --said "<their words>"` |
| Approve the briefs (organic) | G4o | after O7 (the three views and the posting plan) | decided on the page (`--stage G4`, `tm brief choose`), then `tm decide approve_briefs accept --run R --said "<their words>"` |
| Approve the briefs | G3, G4 | after E1 (the briefs and production views on one page) | decided on the page (approve, changes or drop per concept, read at E1 before its views, then with `--stage G4`; `tm brief choose`), then `tm decide approve_briefs accept --run R --said "<their words>"` |

## Decided by rule (`auto`)

`tm decide <id> accept --by rule --note "<the data behind it>" --run R` (the animatics question:
`tm decide animatics skip --by rule --note ...`), with the rule `tm next` names (FLOWS.md section G):

| Id | Rule | The note says |
|---|---|---|
| G0 | logged: the card as derived | the product, market, category phrase, recipients |
| G1 | at least 10 results per segment (lowest cost per result), else the thin-data fallback, marked directional (`tm audience pick`) | the segment, its results and cost, or "directional" and why |
| G3 | published as is, every concept kept: `tm brief choose --source rule` | the page version |
| animatics | skip: Hands-off makes no animatic | "Hands-off makes no animatic" |
| G4 | published as is | the page version |
| G0o | logged: the start card as derived | the channel, its platforms, business or personal, the goal, who films |
| G4o | published as is, every concept kept: `tm brief choose --source rule` | the page version |

Every decision by rule is listed in the final report with its rule and its data, and shown at the
next check-in the user sees.

## Stops the user must clear

Meta not connected or refused for this account; the archive not answering (ask for reviews or an
export); no browser or animatic tools (the animatics wait); TrendsMesh limits; answers missing
fields the run needs (`tm trends check-fields`); a file of yours that a check refused and that
needs the user (rare: you fix your own files). Each stop says what happened, what to do, and that
the run continues from the same place. Then wait.
