# Create an ad (playbook 05): plan for the engine core

> Executed inline (the wave-2 rules: the session approves its own plan). Steps use checkboxes.

**Goal:** a new playbook, `create-ad` (`05-create-ad`), that takes a product with a website from intake to a
PAUSED Meta upload, with the engine owning the flow, the gates, the money and the Meta objects.

**Spec:** issue #17 (spec v0.1: flow S0–S10, gates G1–G5, rules CA1–CA15, pages, config, edge cases). Owner
decisions in this session (below) and issue #46 (activation, open).

**Architecture:** the same engine as the other playbooks. `data/create-ad/steps.yaml` and `checkins.yaml` give
the steps, gates and levels; `tm next` / `tm decide` / `tm done` run them. New engine modules check what the
agent writes (concepts, claims, script-board, production plan, storyboard, copy, upload proposal, upload
record) and record it with `stepchecks.mark`, so `requires` holds the rules. Money reuses the declared-budget
mechanism organic video uses (`planned`, `planned_at`, `yes_for`), the manifest (`tm record`, `manifest.md`),
the paid-tool guard (`tools.PRECHECK`) and refresh-ad's E2 upload knowledge.

**Scope of this build:** the engine core. Pages come later (the shared page template, issue #19, and the
translation mechanism, issue #3, are built in parallel): every gate is answerable in chat, and the data each
page will show is defined (`references/pages.md`) and, for the copy page and the upload proposal, built by the
engine. Fixed UI words are the `ad` area of the shared table (`data/i18n/en.yaml`), read through `tm.i18n`.

## Owner decisions (this session)

1. **Activation:** the playbook never activates. The run ends with PAUSED objects (or drafts), the preview
   link and every ID recorded; the final report says how to switch the ad on in Ads Manager. Whether a later
   version should add a launch check-in is asked in issue #46.
2. **Pre-video money:** the yes to the production plan (S5) approves its pre-video amount (stills and casting,
   music, SFX, transcription). The video amount is a second, separate yes at the filled storyboard (G3).
3. **Levels:** Check every step asks every gate. Just the big calls asks the intake, the concept, the
   script-board with the plan, the first visual output, the filled storyboard (the paid video), the review,
   the copy and the upload; audio and takes go by rule (a take failing QA always goes to the user). Hands-off
   asks the intake and the upload; everything else by rule, and paid steps only inside the budget given at
   intake. A video is never regenerated automatically, at any level.
4. **Guess mode:** the playbook runs without TrendsMesh (`guess: true`), always saying that the agent is
   guessing. Model ads then come from the Meta Ad Library where it answers (its search covers commercial ads
   mainly for EU delivery, so it is often empty elsewhere) and otherwise from formats the agent knows; trends
   are the agent's guess. Both are labelled as guesses on the concept check-in and in the final report.
   TrendsMesh is a warning in the doctor, with that notice; so are Meta Ads, Replicate, ElevenLabs and
   shared page links.

## Global constraints

- Ad: 9:16 MP4, 1080×1920, −14 LUFS integrated, true peak ≤ −1.5 dBFS.
- Copy (CA13): 5 primary texts (≤ 125 characters), 5 headlines (≤ 40), 5 descriptions (≤ 30), CTA, display
  link, URL with UTM (`utm_content` = the ad key), ad name, video title. Claims follow CA3.
- Upload (CA14): created PAUSED (or as a draft) and read back; activation and spend are never part of it;
  the ad budget is never inferred (the user's amount and cadence, in their words); the AI disclosure is the
  advertiser's call, never set silently; names readable (not "Ad set 1").
- Money (CA7): every paid step shows prompt, parameters and price with its check date first; nothing paid
  without a yes or outside the intake budget (Hands-off); money in USD, with the rate when the account
  currency differs; a video is never regenerated automatically.
- Never overwrite (`_vNN`); every asset in the manifest with source, prompt, model and cost; every decision in
  run.json's decisions (CA15). Never an asset by a bare code in messages.
- No account data in code, tests or commits.

## Mapping the spec onto the engine

| Spec | Step | Check-in (every / big / hands) | Engine check (`requires`) |
|---|---|---|---|
| S0 intake + asset inventory | S0 | `intake` own / own / own | `ad_intake_written` |
| S1 concepts | S1 | `concept` own / own / rule | `ad_concepts_checked` (evidence recorded) |
| S3 sources and claims | S3 | — | `ad_claims_checked` |
| S4 script-board | S4 | `board` own / card / rule | `ad_board_checked` |
| S5 production plan | S5 | `plan` 💰 own / card / rule | `ad_plan_checked` (sets `planned`) |
| G1 first visual output | G1 (spends) | `visual` own / own / rule | — |
| G2 audio | G2 (spends) | `audio` own / rule / rule | — |
| G3 filled storyboard | G3 | `storyboard` 💰 own / own / rule | `ad_storyboard_checked` (re-plans with the video) |
| G4 takes | G4 (spends) | `takes` own / rule / rule (`fails_qa` stops) | — |
| S6 edit, S7 QA | S6, S7 | — | — (tools: `tm render`, `tm tool take_qa`, `deliver`) |
| G5 review | G5 | `review` own / own / rule | — |
| S8 Meta copy | S8 | `copy` own / own / rule | `ad_copy_checked` |
| S9 deliver | S9 | — | `ad_delivered` |
| S10 upload (offered) | S10a, S10b | `upload_offer` own×3 before S10a; `upload` own×3 after it | `ad_upload_proposed`, `ad_upload_recorded` |

The card at Just the big calls: "Approve the script-board and plan" (`board`, `plan`). Rules for the `rule`
routes are written in `checkins.yaml`. The skip choices: `upload_offer: skip` and `upload: skip` skip the
upload; `plan: reject` and `storyboard: reject` skip the paid steps after them.

Run folder: `00_raw` the user's files (asset inventory); `02_research` saved MCP answers, model ads, trends;
`03_wip` concepts, claims, script-board, plan, storyboard, takes, edit versions, copy drafts; `04_final` the
ad, its cuts, the thumbnail, the copy; `05_results` the upload proposal and `meta_objects_vNN.json`.

Budgets: `ai_usd` (Replicate: stills, video, upscale; config `budget.generation_usd`) and `voice_credits`
(ElevenLabs: music, SFX, voice, Scribe; config `budget.voice_credits`). Meta ad spend is no engine budget:
nothing spends it in this playbook, and the ad set's amount comes from the user's words in the proposal.

## Review focus

1. A paid video call before the storyboard's yes, or a second take of the same item without the user's
   request: refused by the guard (Task 3).
2. An upload record holding an ACTIVE object (or one the MCP left active): a stop that says to pause it now,
   and `tm done S10b` refused (Task 5).
3. An ad budget, AI disclosure or objective in the proposal with no words from the user: refused (Task 5).
4. Copy with a number that is in no claim, or more than one text variant under the Traffic objective (Task 4,
   Task 5).
5. A Hands-off plan above the intake budget: waits for the user, nothing generated (Task 3).

---

### Task 1: Registration, skeleton, config, doctor

**Files:** `data/playbooks.yaml`, `engine/src/tm/playbooks.py` (`CREATE_AD = "05-create-ad"`),
`engine/src/tm/create_config.py` (new), `engine/src/tm/config.py` (`_for_playbook`), `data/requirements.yaml`,
`engine/src/tm/evidence.py` (`NOTICES[CREATE_AD]`), `engine/src/tm/flow.py` (`_EVIDENCE_WINDOW[CREATE_AD] =
("S1", "S3")`), `skills/create-ad/SKILL.md`, `skills/create-ad/references/{flow,rules,pages}.md`,
`data/i18n/en.yaml` (the `ad` area), tests `engine/tests/test_create_config.py`, `test_create_doctor.py`,
`test_playbooks.py`.

- Config schema (spec "Config" plus the plugin's): `brand.{product,url,persona,language}`,
  `intake.{audience,makes,sells,length_s,placements,live,assets}`, `meta.{ad_account_id,page_id,dataset_id}`,
  `mode` (from the level), `budget.{generation_usd,voice_credits,daily_ad_spend}` (the last never a default),
  `generation.provider` (fixed `replicate`), `models.<asset_type>`, `audio.{music_source,transition_sound}`,
  `languages: {working, market}` (tm.i18n), `currency`, `fx_rate`, `copy` limits, `take.max_s` (15) and `take.words_max` (45).
- `write_from_intake(run, answers)`: level and outputs (`video_ad`) to run.json; Hands-off approves
  `generation_usd` and `voice_credits` from the intake (`budget.approve_from_intake`).
- `intake_gap`: the config validates; the four questions answered (who + what they make, what it sells,
  length and placements, existing materials), the asset inventory written (`03_wip/assets_vNN.json`).
- Doctor rows for `05-create-ad`: base tier always; breakdown, video, voice and AI tiers for `video_ad`;
  disk; TrendsMesh and its plan, Meta Ads, Replicate, ElevenLabs and shared pages as warnings.
- Tests: intake written and refused; Hands-off approves the intake budgets; ad spend never defaulted; doctor
  card warns (not blocks) without TrendsMesh, with the guess notice.

### Task 2: Steps, check-ins, levels

**Files:** `data/create-ad/steps.yaml`, `data/create-ad/checkins.yaml`, test `engine/tests/test_create_flow.py`.

- The table above. `concept` carries the guess notice. `takes`' `fails_qa` stops ("a video is never
  regenerated automatically"). `upload` is `money: true` (refused while the run is stopped).
- Tests: the walk at each level asks exactly the check-ins of the table; skips work; the guess notice comes
  with `concept`.

### Task 3: Plan, storyboard, money and the paid guard

**Files:** `engine/src/tm/create_plan.py` (new, `tm ad check ...`, `tm ad redo`), `engine/src/tm/tools/__init__.py`
(`PRECHECK[CREATE_AD]`), `engine/src/tm/stepchecks.py`, test `engine/tests/test_create_plan.py`.

- `check_concepts`, `check_claims`, `check_board`, `check_plan`, `check_storyboard(run, path) ->
  list[Problem]`; a clean check marks the file (`stepchecks.mark`) and, for the plan and the storyboard, sets
  `planned` and `planned_at` (a re-plan needs a new yes).
- Board: word budget = seconds × the model ad's words per minute; one take carries all speech of one speaker,
  at most `take.words_max` words and `take.max_s` seconds; every line names its claims; the hook has on-screen
  text in the first second.
- Plan: one line per asset type with model, price, price date (≤ `pricing.max_age_days` old), alternative,
  stage (`pre_video` or `video`), and what an existing file replaces; the voice route (CA6).
- Guard `guard(run, args)`: the item is a line of the checked plan or storyboard at its cost; a video item needs
  the storyboard's yes; a video item with a finished take runs again only after `tm ad redo --item --note`.
- Tests: Review focus 1 and 5; plan totals approve through `plan`, the video through `storyboard`.

### Task 4: Meta copy

**Files:** `engine/src/tm/create_copy.py` (new, `tm ad copy check`, `tm ad copy accept`), test
`engine/tests/test_create_copy.py`.

- The draft `03_wip/copy_vNN.json`: per ad key, 5 / 5 / 5 texts with their claims, CTA, display link, URL,
  ad name, video title. Problems: counts, lengths, CTA not Meta's, URL host not the brand's, UTM missing or
  `utm_content` ≠ ad key, a number in no claim, a claim marked not live used, a name like "Ad 1".
- `accept(run, decisions)`: the kept and edited texts as `04_final/copy_vNN.json` (re-checked); the copy
  page's data (`page_data`).
- Tests: each problem; an edited text over its limit refused; Review focus 4 (copy part).

### Task 5: The PAUSED upload

**Files:** `engine/src/tm/create_upload.py` (new, `tm ad upload check|record`), test
`engine/tests/test_create_upload.py`.

- Proposal `05_results/upload_proposal_vNN.json` checked against CA14: pages and pixel checks saved; objective
  and event among 1–2 options with reasons, the user's pick in their words; conversion events only from a pixel
  that fires; text variants and objective; budget amount, cadence and the user's words; country, audience,
  placements; readable names; video and thumbnail in `04_final`; copy equal to the accepted copy; AI disclosure
  `OPT_IN`/`OPT_OUT` with the user's words; status PAUSED. The card text carries the placement facts.
- Record `05_results/meta_objects_vNN.json`: every object's id and status read back, videos `ready`, the
  creative's disclosure as proposed, preview links. Any object not PAUSED or a draft: a stop with what to do.
- Tests: Review focus 2 and 3; a clean record passes `ad_upload_recorded`.

### Task 6: Evals, changelog, report

- Evals (not run): `ca_upload` (Hands-off at the go-ahead: nothing activated), and
  `ca_plan_cost_needs_yes` (the user says "generate everything": the cost is asked, nothing generated).
- `CHANGELOG.md` bullet; full test run; commits per task.

## Status of this build

Built: Tasks 1 to 6 (commits on the branch, one per step). The engine modules are `create_config`, `create_plan`,
`create_copy`, `create_upload` and the `tm ad` command (`create_ad`). Evals added, not run:
`ca_upload`, `ca_plan_cost_needs_yes` (scenarios `ca_at_s10b_hands_off`, `ca_at_s5_plan`).
Calls made while building, beyond the spec: the edit QA (S7) and the takes (G4) have no engine check yet (the
tools exist; the gate decides); a Create an ad money wait names the plan or the storyboard, not organic video's
pack; the copy's claim check is numbers only (results and availability promises are the agent's, CA3).

## Left for later (not in this build)

- The pages (concepts, script-board + plan, storyboard, gate, review, copy) on the shared template (#19),
  translated through `tm.i18n` (#3); the edit builder, edit QA (Scribe repeats, motion at cuts, loudness) as
  engine checks; the review page's time-pinned notes; the ad-language checks of the copy beyond numbers.
- Measurement after launch, and activation (issue #46).
