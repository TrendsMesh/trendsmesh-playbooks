---
name: create-ad
description: "Use when the user wants a new video ad for Meta (Facebook, Instagram Reels, Stories or Feed) made from zero for a product with a website: from a concept built on a proven ad format and rising trends, through the script, the paid generation and the edit, to the Meta copy and a PAUSED upload into their ad account."
---

# Create an ad (TrendsMesh playbook 05)

Makes **a new paid video ad for Meta from zero** for a product with a website. It starts from a proven ad format
in the niche (a "model ad") and from what is rising in TrendsMesh, produces the ad in stages with a check-in after
each, writes the Meta copy, and offers to create the campaign, ad set, creative and ad in the user's account, **all
PAUSED**. The user decides where taste matters; everything paid is approved first or stays inside the budget given
at intake. Refresh an ad starts from an ad that exists; Creative brief writes a brief for people to produce;
Organic AI video makes posts. This one makes a paid ad end to end, and **never switches an ad on**.

**The engine `tm` owns the flow, the checks of what you write against CA1 to CA15, the run state, the check-ins,
the money and the stops.** You do the judgement (the intake card, the concepts, the claims, the script-board, the
prompts, the edit, every sentence of the copy) and record it through `tm`. Never improvise the flow, never skip a
step or a check-in, whatever the reason given. Call it as `tm ...`; add `--json` and read the one JSON object. Pass
JSON as files in the run, never inline. Exit codes: `0` done, `2` stop (fix what it says and run the same command
again, or the user must act), `1` error (read the message and fix the cause; never work around it).

**Languages** (the plugin's `references/languages.md`): a run has two, `languages: {working, market}` in its
config, both on the intake card from their defaults (the working language is the one the user writes in; the market
language follows it unless the site, the ad account or the user points to another market). Talk to the user, and
write every card, summary and page, in the **working language**. **The ad's copy, voice-over, captions and on-screen
text are in the market language**, which may differ. The engine's card words come from the plugin's string table:
when the working language has no translation yet, `tm` says so (`language_warning`) and gives them in English;
translate the table once as that reference says. `tm` messages are English: put them in the user's words.

**Words:** say "check-in", never the spec's other word for it. The levels are **Check every step**, **Just the big
calls** and **Hands-off**. Ask **one plain question at a time** (the S0 intake card is the one exception). The user
never sees `tm`, a command, a flag, a step or check-in id, JSON, or a file path they don't need. **Never name an
asset by a bare code** ("the creator's first take", never "T1").

**Where things are:** `references/flow.md` (every step), `references/rules.md` (CA1 to CA15),
`references/pages.md` (the run page: how a check-in goes on it, what each page shows and saves, and the chat card
that is its fallback), the plan behind this build in `PLAN.md`; the shared references two folders up (`../../references/`):
`model-prompting/` (each model's prompting recipe: read it before any prompt), `trend-collection.md`; Refresh an
ad's Meta notes, `../refresh-ad/references/meta-mcp.md`, and its TrendsMesh sign-in,
`../refresh-ad/references/trendsmesh-sign-in.md`.

## 1. Readiness first (also `/trendsmesh-playbooks:doctor`)

1. Find each connector's state without guessing: TrendsMesh (sign-in, then the plan), Meta Ads (one cheap
   `ads_get_ad_entities` call), and artifacts (`ok` when the `Artifact` tool is among this session's tools).
2. `tm doctor --playbook create-ad --outputs video_ad --mcp trendsmesh=<s>,meta=<s>,artifacts=<s> --json`, and show
   its `card` in plain words. The media tools are installed after the user's yes, with their size and time.
3. **Without TrendsMesh the run goes on as labelled guesses** (`tm evidence guess`): model ads from the Meta Ad
   Library where it returns any (its search covers mainly ads shown in the EU) and formats you know; trends are your
   guess. Say it once at readiness and again with the concepts (`tm next` gives the notice). Never present a guess
   as a TrendsMesh trend. **Meta Ads, Replicate, ElevenLabs and shared pages are warnings**, never stops: say each
   once, as what it takes away.
4. **Keys never appear in chat.** Never search for, read, print or ask for a key or token.

## 2. Intake (S0), one card

`tm run new --playbook create-ad --name <product> --json`. **Its answer lists `unfinished_runs`**: this playbook's runs of the same name that were started and are not done (`folder`, `created`, `step`). When it lists any, always ask first, in one short question, whether to continue one of them (then `tm next` on it; the new folder stays unused) or start this new one. Pre-fill from the site, the config and earlier runs of
the brand (language, ad account, CTA, budget, music) and show it as one card for correction, with **four
questions, each with options** (`references/flow.md#s0`): who the ad is for and what they make or do; what it
sells; the length and placements; the existing materials. Add the level ("How involved do you want to be?") and,
for Hands-off, the generation budget in USD. Then `tm config write`, `tm config check`, the asset inventory, and
`tm done S0`. When what is sold is not live yet, warn here: nothing that is not live is promised, anywhere.

## 3. The loop

When the user names a run or asks to continue, run `tm next` on it **before you answer**. An unfinished run under
`runs/05-create-ad/` and a request that does not plainly continue it: ask first whether to continue it or start a new
one; when `tm status --run R --json` gives `trend_data.expired`, say that its trend data has expired (`message`).
Before you do, plan or describe a step's work, read its section in `references/flow.md` (the `ref`).

`tm next --run R --json` → act on `action`, then `tm next` again. Always.

| action | what you do |
|---|---|
| `work` | Read the step's section (`ref`). Do the work. Record each file you write with `tm record`. Then `tm done <step> --run R`. |
| `ask` | Put the check-in on the run page and show it as a question card (`references/pages.md`): the ask, `tm page build`, the publish, the link; wait for the answer, then `tm decide <id> <choice> --run R [--note "<their words>"]` (a choice made on the page: `tm page decision --run R <id> --record`). Without a publishing tool the page is built `--local` and answered in chat; when it can't be built, the card alone. A money check-in's yes is followed by `tm budget approve` for each planned amount. |
| `auto` | Decide by the rule in the message: `tm decide <id> <choice> --by rule --note "<the data behind it>" --run R`. List it in the final report. |
| `stop` | Tell the user what happened, what to do, and that the run continues from the same place. **Then wait.** |
| `done` | Final report (`references/flow.md#done`). |

- **Money (CA7):** nothing is generated or paid before the yes that covers it: the production plan's yes for the
  stills, audio and transcription, the filled storyboard's yes for the video (Hands-off: the budget given at
  intake). Every paid Replicate call is `tm tool replicate_run --run R <spec> --name <item> --cost <its plan line>`;
  the engine refuses a call that is not a line of the checked plan or storyboard, a video before the storyboard's
  yes, and a second take of a video item unless the user asked for it (`tm ad redo`). **A video is never regenerated
  automatically.** Every price comes from a saved price file with its date, never from memory (ElevenLabs' music
  by the second: `tm ad prices`). A line may cover several calls (`calls`), and an ElevenLabs music or voice take
  runs only as a plan line too (`--out 03_wip/audio/<item>_vNN.mp3`). Spend on rejected takes is kept apart
  (`tm ad redo`, `tm ad reject`; `tm ad costs`). **A model name the user gives that does not name one model
  exactly is confirmed first**, with one short question ("Do you mean Seedance 2.0?"), before any paid call with it;
  the engine runs a call only on its line's own model.
- **Long steps show progress**: a task list with time estimates and a one-line status at each stage change.
- A run spans days and sessions: everything lives in the run folder; `tm next` picks it up.

## 4. The Meta upload (S10): offered, proposed in full, created PAUSED

- Offered only after the copy is accepted. The checks first (the Pages the ad account can use; the pixel: which
  one, whether it fires, which events arrive), then **the proposal in full** (`references/flow.md#s10a`), written
  to the run and checked with `tm ad upload check`. The objective and optimisation event are proposed as one or two
  options with reasons and asked; the **ad budget is never inferred** (the user states the amount and the cadence);
  the **AI-content disclosure is the user's decision**, asked before any creative exists (it can't be set later).
- Only after the user's go-ahead: one upload round (the files sent to the user first for the upload window), the
  objects created **PAUSED** (or as a draft, and say which), read back, previewed, and recorded with
  `tm ad upload record`. **Never call any activation tool, and never set a status other than PAUSED.** The final
  report says how to switch the ad on in Ads Manager.

## 5. Hard rules CA1–CA15

**Read `references/rules.md` before S1**, and keep it in force to the end. In short: CA1 the intake confirms the
persona and the output before any research; CA2 concepts are a model ad plus trends, on one page, with a feedback
loop; CA3 claims come from the site and the user, never invented numbers, results or availability; CA4 the script
is a board sized to the takes; CA5 models are suggested per asset type, never imposed; CA6 the voice route is
decided in S5; CA7 cost and approvals, never an automatic video redo; CA8 staged gates, raw assets shown raw; CA9
generation craft; CA10 edit standards; CA11 edit QA before every showing; CA12 the review; CA13 the copy goes to a
check-in; CA14 the upload is offered, proposed in full and created PAUSED; CA15 language, assets, progress.

## Red flags: stop and go back to `tm next`

| Thought | Reality |
|---|---|
| "The user said generate everything, so I'll start" | Nothing paid before the plan's yes (and the storyboard's for the video), with the prices and their dates shown. |
| "That take stutters; I'll regenerate it" | Never automatically. Show it raw with its QA notes and offer: a precise cut, a clone of the line, a new take with its cost, or accept. |
| "There's no Gemini 2.0 video model, so they mean Seedance 2.0" | Probably, but ask first: "Do you mean Seedance 2.0?" No money goes to a model the user didn't clearly choose. |
| "A daily budget of 20 seems right" | The ad budget is never inferred. Ask for the amount and the cadence. |
| "These ads obviously use AI, so OPT_IN" | The AI disclosure is the advertiser's call. Show the facts and ask. |
| "Paused is boring; I'll activate it so they see results" | Never. This playbook creates PAUSED objects only and never activates anything. |
| "Ad set 1" | Names stay readable: product, test, audience and concept. |
| "The page is quicker to patch by hand" | Never. The engine builds it from the run's files; a choice on it is read with `tm page decision`. |
| "They clicked go ahead on the page, so it's live" | The page only records the go-ahead. The objects are created PAUSED, after it, and nothing switches them on. |
| "I'll promise launch-day results" | Never a result, a number that is not in the claims, or availability that is not live. |
| "No TrendsMesh, so these are the trends" | Without TrendsMesh they are your guesses, and you say so. |
| "Show the key so they can check it" | Never. Keys never appear in chat. |
