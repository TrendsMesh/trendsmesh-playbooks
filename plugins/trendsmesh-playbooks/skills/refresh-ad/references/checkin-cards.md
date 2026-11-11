# Check-in cards

A check-in is a decision the user makes. Which ones the user sees depends on the level; the
engine decides that (`data/checkins.yaml`) and says `ask`, `auto` or `stop` in `tm next`.

## How a card looks

Use Claude Code's question cards (the AskUserQuestion tool): one question per check-in, options
with a short label and a description, **your recommendation first** with "(recommended)" in its
label. The text follows the handoff's rules (`FLOWS.md` section H):

1. The header says what is decided, what happens after the answer, and what it costs (amount and
   budget, or "free").
2. Each option carries its data, with the source of every number (R3).
3. Things are shown in their context: a hook on a frame of the video, the first frame next to the
   original frame, before and after side by side. Media goes on the local review page
   (`tm review build --run R`, then give the path of `review/index.html`); the decision stays in
   the chat card.
4. The trail (prompt, model, parameters, cost, the parent file) is one line under "details", not
   the card's body.
5. In the user's language, plain words: no ids, commands or JSON. "Check-in", never "gate".

The user can always answer something else ("change the hook to…", "from now on, just the big
calls"). Redo the work as a new version and show the card again; record only the final answer.
A level change is `tm level <id>`; a decision changed later needs `--change`.

## A merged card (Just the big calls)

`tm next` gives `checkin.card` and the member `ids` still open. Show one card that covers them
all (one question per member is fine inside the same card), then record **each member** with its
own choice: `tm decide G1 <ad id>`, `tm decide G1a refresh --note hook`, `tm decide G1b accept
--note "<segment>"`. Use the card id itself (`tm decide pick_the_ad ...`) only when one choice
fits every member (`tm next` lists the card's `choices` when its members share them). In the
spending card, a user who approves one budget and not another gets one decision per member:
`tm decide G10 reject`, then `tm decide approve_spending approve` for the rest.

| Card | Members | What it shows |
|---|---|---|
| Pick the ad | G1, G1a, G1b | the ranking, the diagnosis and the persona, with your recommendation |
| Approve the changes | G2, G3, G4 | the direction, the hooks with the change register, the brief (in a middle run, the re-cut direction and its register); the re-cut variants (G3r) are asked on their own at CR3 |
| Approve the spending | VB, RB, G6, G10 | before any paid step: the voice budget, the re-cut budget (ProPainter and Veo in USD, ElevenLabs Music in credits), the AI generation plan and the live test plan, each priced, with R4's minimum events (run `tm r4` before this card: G10 is refused without a feasible plan) |
| Approve the launch | G11 | the R8 checklist, the final videos, the amount; asked at every level, Hands-off too |
| Act on the results | G12 | variant against control, the plan's thresholds, your recommendation |

## Choices per check-in

| Id | Name | Choices to record | Note |
|---|---|---|---|
| G1 | Pick the ad to refresh | the ad id (`none` when nothing is fading) | the ranking file |
| G1a | Accept the diagnosis | `refresh` or `do_not_refresh` | the target stage and its numbers; a structural weakness (R2b) is offered here as an option, and `tm flow R` is run before recording when the user takes it (`flow.md#a1a`); for a re-cut, every kind of variant on the card carries its level ("level 0, a pure edit, free"), none without one |
| G1b | Accept the persona | `accept` | the segment |
| G2 | Choose the direction of changes | `hook`, `ending`, `new_look` (a supported change only); in a middle run `recut` | the trend ids; in a guess run, what each direction rests on (a winner, an Ad Library ad); in a middle run, "re-cut the middle", the weak step and its seconds, the trends read (`flow.md#a5`) |
| G3 | Approve the hooks and the change register | `approve` | the hooks kept; in a middle run, the register of the diagnosed causes and the re-cut direction (no hooks; the variants come at G3r) |
| G4 | Approve the creative brief | `approve` | the file |
| G3r | Choose the re-cut variants | `approve` | the variants kept, each with its change id and level; on its own at Just the big calls too; Hands-off never keeps a new voiceover line (it waits) |
| VB | Approve the voice budget | `approve` or `reject` | the credits; then `tm budget approve voice_credits <running total>` |
| V1c | Confirm the voice match after listening | `voice_matches`, `none_matches`, `original_voice_found` | the voice id |
| GV | Blind listening test of the voice clone | `pass` or `fail` | what the user heard |
| RB | Approve the re-cut budget | `approve` or `reject` | the USD and credits; then `tm budget approve ai_usd` and `voice_credits`, each `<running total>` |
| G5 | Approve the edited video | `approve` | the file |
| G5r | Approve each re-cut variant (listen to it) | `approve` | each variant kept or dropped, with the user's words |
| G6 | Approve the AI video plan and budget | `approve` or `reject` | the USD; then `tm budget approve ai_usd <running total>` |
| G7 | Choose the first frame | the chosen file | |
| G8 | Accept the clip or regenerate it | `accept` (or regenerate first, then accept) | attempts so far |
| G9 | Approve the AI video | `approve` | known defects |
| G10 | Approve the live test plan | `approve` or `reject` | per day × days; then `tm budget approve test` |
| E2b | Quality and policy check | `green` or `red` (always by rule) | the checklist file |
| G11 | Approve the launch | `activate` (only after a green E2b) or `keep_paused` | the amount; never by rule, at any level |
| G12 | Act on the results | `scale`, `kill` or `keep` | the numbers against the thresholds |

`<running total>`: what is already approved for the kind plus this check-in's amount (`tm status
--run R --json` → `budgets`), as one approved amount per kind serves the whole run (SKILL.md
section 5).

`reject` on a spending check-in skips that output's paid steps: VB the new voiceover line and the
rest of the edited video (in a run that refreshes the hook and re-cuts with a new line, the
hook's render too: say so on the card), RB the re-cut's paid repairs, shots and music (the L0
to L2 variants are still rendered), G6 the AI video, G10 the live test. Nothing is spent on them, and the
run goes on with the other outputs (`tm decide` and the final report say what was skipped).
`keep_paused` at the launch skips the activation and the measurements the same way. A user who
changes their mind before the run reaches those steps: record the new answer with `--change`;
once the run has gone past them, the engine refuses the change (a new run makes that output).

## Decided by rule (`auto`)

`tm decide <id> <choice> --by rule --note "<the data behind it>"`, using the rule the message
names (FLOWS.md section G: #1 from the ranking, the R2 table, the lowest cost per result with at
least 10 results, the strongest confirmed and rising trend (in a guess run, the strongest
evergreen structure from the account's own winners not saturated in the Ad Library: the rule
`tm next` gives), the top 1 to 2 consistent with the
image, the re-cut variants for the causes marked "yes" with L0 to L2 first, QA green, the limit
from the config, the test plan's thresholds). Every decision by rule
is listed in the final report with its rule and its data, and shown at the next check-in the
user sees.

## Stops the user must clear

Voice checks in Hands-off (V1c, GV), a red R8 item, a budget that would be exceeded, a plan
below R4's minimum events (or its estimate on the chosen ad, right after the diagnosis), a missing file or an upload by hand, a missing install or sign-in.
Each stop message says what happened, what to do, and that the run continues from the same
place. Then wait for the user. While a stop is open, the engine refuses every spend, budget
approval and money decision (the spending check-ins, the launch, the results) except the
decision the stop is about (for an R4 plan, `G10 reject` to skip the live test).
