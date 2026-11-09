# Template: one-page concept brief (PB2, check-in G3)

**A concept brief describes a new ad to be made from scratch.** It is the PB2 variant of the shared creative brief (`skills/refresh-ad/templates/creative_brief_template.md` in the plugin): same core (executors, specification, **why: data**, deliverables, QA), but there is no source video and no "was → to be". It must be enough for every executor (creator, operator, editor, voice artist, graphic designer, later an AI pipeline) to do their part without follow-up questions. The animatic (CB11) is attached to it.

---

## 1. Header
`brief_id` (e.g. `PB2-LD-CA-2026-11-04-C1`), product, market, language, formats (R6), target length, valid until, test hypothesis in one sentence.

## 1a. Standard fields (CB13)
| Field | Content | Goes to views |
|---|---|---|
| Key message | one sentence: the single thing the viewer must take away | decision, strategy, creator, editor |
| Tone and mandatories | tone of voice; must-haves (product before CTA, claims as on the landing page); don'ts | strategy, creator, editor |
| KPI | decision metric vs the account baseline, minimum events per variant, estimated test spend | decision, media buyer |
| Budget, deadline, approver | from intake; "to set" when missing | decision, creator (deadline) |
| Usage rights and creator fee | from intake; "to set" when missing | creator, decision |

## 2. The idea
- **Evidence at a glance first** (same block as in the review pack: trend with status, creators, views, lift, last seen; customer theme with frequency; the account number; saturation), then the details below.
- One sentence, then 3–4 sentences: what the viewer sees and feels, why it ends in the product.
- **Angle:** customer theme, tier, frequency, 2 verbatim quotes with source (CB5).
- **Customers' own words:** at least one language-bank phrase used in the ad (hook, on-screen text, line or primary text), with where and its source (CB5).
- **Trend:** name, type, status, numbers, 3 evidence clips with "as of" date; what we reproduce from it (CB7). Reference only, never footage (CB9).

## 3. Executors and scope
| Role | What they do | What they receive | What they deliver |
|---|---|---|---|
| creator / operator / editor / voice / graphic designer | | | |

## 4. Beat sheet (the spine of the ad)
| # | Time (s) | What we see | What we hear (line / VO / sound) | On-screen text (verbatim) | Why (data) |
|---|---|---|---|---|---|
| 1 | 0–3 | hook | | | trend structure, angle |
| … | | | | | |
| n | | CTA / end card | | | landing page promise |

Hook-to-image relation for beat 1: consistent / setup and payoff / deliberate contradiction (+ reason).

## 5. Hook variants for testing
2–3 variants that change only the hook (text + first line + first shot), each with the trend sub-pattern it follows.

## 6. Copy and thumbnail (R7)
Primary text (2 lengths), headline, CTA button, thumbnail / cover frame: each with a one-line justification.

## 7. Sound
Track (source + advertising license) or "sound trend X → licensed equivalent Y" or "organic only" (CB9). Levels relative to voice.

## 8. Look and casting
Persona of the person on screen (age, gender, look, matched to buyer data), setting, light, wardrobe, props (the product: how it appears), visual references (trend clips, timestamps).

## 9. Deliverables
Per role: raw footage **without burned-in captions**, separate VO / audio track, project files, renders in every format (R6), file naming.

## 10. QA checklist
Yes/no items: hook in the first frame, text legible in feed preview, safe zones, product shown before the CTA, claims match the landing page, sound licensed, formats delivered, clean files delivered.

## 11. Animatic
File(s) in `03_wip/animatic/renders/` (the page plays them), style used, what it shows (beats, timing, on-screen text) and what it does not (realistic footage).

## Generation rules (for the agent)
- No data, no element: every beat, hook and copy line names its source (trend, customer voice tier, Meta, Ad Library).
- Hooks reproduce the trend structure from its evidence videos (CB7), not our paraphrase.
- At Check every step the brief and animatic are shown for acceptance (G3) before the shot list is written; at Just the big calls G3 is asked with G4 ("Approve the briefs"), after the production views.

## Views (CB13)
The brief is one data source. The page renders a view for each recipient ticked at intake: Decision, Strategy, Creator, Editor, Media buyer (contents and exclusions: `PLAYBOOK.md`, CB13). The creator view never shows account data, results, competitors or customer research.
