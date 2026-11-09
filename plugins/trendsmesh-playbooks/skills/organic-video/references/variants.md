# Variants and edge cases

Copied verbatim from the handoff's `VARIANTS.md` (handoff `organic-video_v02`, sections 1 to 4), with
one column added: **In the plugin**, the status of each row in this version, or what is left for
a later version (the weekly pack's parallel production and combined check-in pages). The
flow is `flow.md`; the rules `rules.md`. Sections 5 (known risks) and 6 (the order of tests) are
in the living spec, `spec/03-organic-ai-video/VARIANTS.md`.

- Where it says "gated" or "A–Z", read the levels (`checkin-cards.md`); its gates are check-ins.
- **Not supported yet**, said plainly, with the issue link the engine gives: a publishing tool,
  Higgsfield, speech longer than one take, pages in languages other than English and Polish, the
  sensitivity filter, measurement.
- **What arrives in a later version**, said plainly when asked: the weekly pack's parallel production, its
  check-in pages combined across the week, and a fully automatic weekly run. This version makes the week's
  videos one after another, each with its own check-ins.

## 1. Input situations
| Case | What changes | What the agent does | Status | In the plugin |
|---|---|---|---|---|
| **Store with several faceless channels** | one catalog, several bubbles | one profile per channel; the same video is never reposted across channels; packshots made once per store | tested (pet store) | built: one channel profile per channel, sharing the store's brand profile and catalogue; an idea is started for one channel, once (`tm organic start`); packshots kept once per store (`tm brand packshot`) and reused by every channel |
| **Channel that sells nothing** | no product decision beyond "not shown" | product level "not shown" everywhere; no packshots | tested (ExampleEdu) | built: `store: null`; the proposals check refuses any product level but "not shown" |
| **Non-English audience** (Polish) | trends mostly EN/ES | search the audience language + English; every proposal is adapted (Inspire) or keeps a low-speech format; captions and speech in the audience language | tested (ExampleEdu) | built: the searches in the audience language and English (B1); post text and speech in the audience language (the kit's language is checked) |
| **Chat language ≠ audience language** | pages vs post text | pages and summaries in the chat language; post text in the audience language; an explicit request (e.g. "English version") wins | tested (script page in English) | built: pages in the chat language (English or Polish; another language gives English pages and a note); `plugin.lang_request` for an explicit request |
| **No generation provider** | no video model | animations, infographics, quizzes and scripts only; AI footage and talking characters hidden | untested | built: the stack check hides AI footage and talking characters for an AI video, and the proposals check refuses them there; a script to film may use any type |
| **No ElevenLabs** | no narrator voice | H3 narrator from the prompt (alternative), text-only versions, or the lines in the script | untested | built: the stack check records ElevenLabs (its credits read at D1); without it the ElevenLabs routes are refused, and the H3 narrator from the prompt is the alternative |
| **No music folder** | — | Mixkit tracks with a free commercial licence, indexed; or a trending sound added in the app | tested (pet store, ExampleEdu) | built: the user's folder or Mixkit tracks indexed with `tm tool music_index`; a trending sound added in the app per the kit |
| **Business account** | trending sounds limited | commercial-library alternative in the kit; "Your brand" disclosure when the product is shown | untested (kit marker only) | built: the kit check requires a commercial-library alternative to a trending sound, and "Your brand" when the product is shown |
| **Publishing tool connected** | posting by the agent | draft or schedule after the user's yes; TikTok draft when a trending sound must be added in the app | untested | not supported yet: the user downloads and posts (`publishing.tool` other than none is refused, with the issue link) |
| **Higgsfield as provider** | — | supported in the profile; the test account has 0 credits | untested | not supported yet: `generation.provider` is replicate (refused otherwise, with the issue link) |

## 2. Trends
| Case | What the agent does | Status | In the plugin |
|---|---|---|---|
| Shared-word noise ("groom", "hack") | require a niche anchor term next to the activity term | tested (dry run) | built: `tm trends shortlist --anchor-terms` |
| Sounds with no niche relevance | score sounds from their description and evidence captions | tested (dry run, by hand) | built: `tm trends shortlist --sound-relevance` |
| No format trends (`format_trend` empty) | read the format from the hook's or topic's evidence videos | tested | built in the skill: the format read from the evidence videos (`flow.md#b1`); filed with the backend requests |
| Hook evidence only in another subject or language | transfer flagged as a hypothesis; lowers expected reach, not feasibility | tested ("dad, why is _" from sports) | built: `plugin.transfer`, and the proposals check asks for the weak link |
| Trend already used on the channel | skipped; series continue (e.g. brainrot part 2) | tested on the weekly page (dry cycle) | built: the channel's used-trends log (`tm organic used`); the proposals check refuses a used trend without a series |
| News, tragedy, real people in topic trends | sensitivity filter **postponed** (round 49); today the agent leaves such topics out by judgement | untested | left out by judgement (B2); the sensitivity filter is not built (issue) |

## 3. Production types
| Type | How | Status | In the plugin |
|---|---|---|---|
| AI footage with native sound (ASMR, mukbang) | H3 from first frames; sound kept | tested (pet store: grooming ASMR, lick-mat mukbang) | built: H3 from picked first frames; a sound-led format never on the budget tier; ASMR finished near −16 LUFS (`--asmr`) |
| Talking AI human host, English | H3, dialogue in the prompt; product via reference mode | tested (pet store: "what my husky eats in a day"; ExampleEdu host in English) | built: H3, a host image always goes to H3; reference mode needs `ratio: "9:16"` |
| Talking AI human host, Polish | H3, dialogue in the prompt, word for word; slower pace, sped up 1.2× in the edit | tested (ExampleEdu, A–Z) | built: QA measures the pace; `tm tool deliver speed`, at most 1.25× |
| Talking AI animal | H3 reference mode, dialogue in the prompt | tested (pet store: bath-day skit) | built: H3 reference mode, native speech |
| Person generated from a description (no fixed influencer) | Seedance 2.0 with the person in text + product references | tested (one take, pet store) | built: Seedance 2.0, never with a host image (E005) |
| ElevenLabs voice + lip-sync (alternative) | Kling Avatar v2 pro; check for burned-in text | tested (pet store: bath-day skit, route B) | built: only on request, or for exact wording or a brand voice, with its reason in the pack; the contact sheet checked for burned-in text |
| Off-screen narrator | ElevenLabs voice by default; H3 narrator from the prompt as the alternative (EN and PL generated) | tested | built: ElevenLabs by default, timed with `--timestamps` before the takes are sized |
| Voice reference on H3 | worse in Polish (garbled words, an extra sentence), fine in English with a same-text sample; **off by default** | tested | built, off by default: only on the user's words, the sample at most 14 s |
| Claude animation in one of our styles, whole video | storyboard gate → full animation → render; VO timing from word stamps | tested (ExampleEdu brainrot explainer; dry run) | built: the storyboard check-in, then `tm organic animate` from the accepted storyboard |
| Sections: footage → animation insert → footage | one video model for footage; insert keeps the caption band free | tested (pet store: "why dogs spin before lying down") | built: one video model for every footage section; the insert's prompt in 9:16 with the caption band; G1 checks the edit cuts the sections in order |
| Quiz / ranking with stills + Remotion | `QuizGrid`, `RankingList`/`RankingSplit` | tested (pet store) | built: the cards picked at F1 (or the user's own pictures), the free render at F2 |
| Lines that do not fit one take | propose an extra take; **known risk: the voice may differ between takes** | untested | not supported yet: speech stays within one 15 s take (issue) |
| Two characters talking (parent + kid) | H3, both in one image | untested (proposed for ExampleEdu) | built: allowed, with the risk "several characters" |
| Real creator's photo as reference | out of scope (consent, Seedance face block) | — | out of scope |

## 4. Variants and outputs
| Case | Status | In the plugin |
|---|---|---|
| Gated, all gates, on pages | tested (ExampleEdu brainrot explainer) | the levels Check every step and Just the big calls; the proposals page, the script page and the check-in pages (images, takes, delivery) |
| A–Z with a delivery page showing every step | tested (ExampleEdu ChatGPT 13+ host video, $1.46) | built: Hands-off ends on the delivery page with every step |
| Script to film (page + .md download) | tested (ExampleEdu, English script) | built (this version): `tm organic script check`, `tm organic page script` |
| Weekly pack: plan page (calendar, budget, swaps) | tested as a dry cycle (no schedule, nothing generated) | built: `tm organic week check`, `tm organic page week`, the week approved once within its budget (`flow.md#i2`) |
| Weekly pack: scheduled run, parallel production, combined gates | untested (to test on the built SKILL) | built: one week run, the slots produced one after another (`tm organic start`), the flexible day the day before (`tm organic flexible`), one delivery page and the posting plan (`tm organic deliver-week`), a desktop scheduled task or by hand (`tm schedule`); parallel production and combined check-in pages arrive in a later version (issue) |
| A gate decision that fails to save | seen once (edit gate store empty); the chat decision is the fallback; never republish during a decision | built: an empty page store stops and sends you to chat; no new page version while people decide; a chat decision counts |
| Video that fails QA in A–Z | goes to the user with findings and options; never regenerated automatically | built: the take goes to the user (`fails_qa`), never regenerated |
