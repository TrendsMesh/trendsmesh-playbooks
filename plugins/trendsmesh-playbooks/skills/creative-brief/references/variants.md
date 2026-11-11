# Variants and edge cases

Copied verbatim from the reference playbook's `VARIANTS.md` (reference playbook `creative-brief_v02`, sections 1 to 6). The
flow is `flow.md`; the rules `rules.md`. **What the plugin does with them:**

- **Built:** thin account data (`tm audience pick`'s directional fallback); a new product with no
  ad history (`tm audience pick --no-data`); no own reviews (tier B from the Reddit archive, the
  landing page as the brand's hypothesis); rich own reviews (`tm voice import --tier A`); a brand
  guide (read at A1 into the brand profile); a PB4 seed (`tm run new --seed`, re-checked at B3
  with `tm brief seed-check`); every trend case (the shortlist's four lists, "weak fit", the
  licence and "organic only", the 14-day valid-until); money in another currency (USD with the
  rate stated); one recipient (the page shows that view only); an external creator (the creator
  view holds nothing confidential); a recipient without claude.ai (`tm brief page
  --single-file`, decisions by "Copy my decisions" or in chat).
- **Not supported yet**, said plainly: seeds from PB5 and PB8 (no such playbooks yet); the
  Shopify connector and Notion or Drive connectors (an export or a file the user has works);
  Goodreads reviews (`references/voice.md` says why); local forums and review sites for
  non-English markets are found by web search at B2, and a site that refuses programs is skipped
  (any reviews the user exports go in through `tm voice import`); organic use only
  (the media-buyer view off, an organic KPI); Foreplay (section 6, test 5).
- Where it says "HITL" or "AUTO", read the levels (`checkin-cards.md`); `voice_mine.py`,
  `trend_shortlist.py` and `build_brief_pack.py` are `tm voice …`, `tm trends shortlist` and `tm
  brief page`.

## 1. Input situations
| Case | What changes | What the agent does | Status |
|---|---|---|---|
| **Thin account data** (few results per segment) | G1 cannot use the ≥ 10 rule | thin-data fallback (CB1): largest directional cluster, cross-checked with the same product in another market or campaign; "directional" on every output | tested (CA: 28 checkouts) |
| **New product, no ad history** | no account context, no baseline for the media-buyer part | persona from the product hypothesis + customer voice only, marked as hypothesis (R3); formats default to 9:16 + 4:5; media-buyer target set relative to the first test's control, or "to set" | untested |
| **Account optimises a different event** (purchase, lead, install) | decision metric changes | use the campaign objective's result, as PB1 R1; state it in the media-buyer part | untested |
| **No own reviews** (tier A empty) | angle evidence comes from tier B | category voice (`voice_mine.py`), brand voice from the landing page as hypothesis; say so at intake | tested |
| **Rich own reviews** (Shopify, Amazon, exports) | tier A leads | tier A themes first, tier B only to confirm; testimonial concepts become possible (only when the concept calls for it) | untested |
| **No public category discussion** (B2B, very niche) | tier B thin | ask for sales-call notes, support tickets, CRM fields; competitor reviews (G2, Capterra); keep counts honest ("x of y items") | untested |
| **Brand guide exists** (Notion, Drive, PDF) | short brand intake skipped | read the guide; extract tone, must-haves, never-list into `tone` | untested |
| **Seed from PB4, PB5 or PB8** | a concept idea arrives first (PB4: a trend pick with `valid_until`) | treat the seed as a candidate in C1; still run B1–B4 for evidence; a PB4 seed past its `valid_until` is re-checked in B3 | untested |

## 2. Trends
| Case | What the agent does | Status |
|---|---|---|
| **Loose search, few relevant topic trends** | show the best-fitting trends: hooks that fit the concepts plus the closest topics (`trend_shortlist.py`); never write "no category trend" (CB2) | tested |
| **Strong topic trend in the category** | topic-led concept (topic + customer phrase + clips, as on the presentation slide); still pair it with a fitting hook | untested |
| **Hook evidence only in another language** | transferability flag; ranks low; usable only with English evidence or as a deliberate test (CB2) | tested ("repeat after me", Russian only) |
| **Sound trend** | licence from TrendsMesh: commercial → may go into ads; organic or missing → flag "organic only", licensed equivalent in the ad brief (CB9); with `music.require_ads_license` only commercial sounds are listed | tested on a synthetic fixture (tool), not on real data |
| **Format-led concept** (formats arriving in TrendsMesh) | the format is the spine of the concept (structure of the beats), paired with a customer angle and phrase; scored like hooks; only if it can be made honestly | tested on a synthetic fixture (tool), not on real data |
| **Trend about to expire** (`visible_until` soon, or event trend) | valid-until on the page; prefer trends with longer life; event trends only with a dated brief | untested |
| **Format trend** (e.g. a story-over-clips format) | allowed only when it can be made honestly: no fabricated posts or testimonials presented as real | tested (Reddit storytime left out) |

## 3. Market and language
| Case | What changes | Status |
|---|---|---|
| **Non-English market** (e.g. PL) | trends mostly EN: transfer is a hypothesis, rank by creators and view lift (PB1 lesson 5); category voice from local forums / reviews (Wykop, Ceneo, local Facebook groups) plus EN as a fallback marked as such; page and brief in English, ad copy and lines in the market language | untested |
| **Money in another currency** | page shows USD at a stated rate (CB13); run files keep the account currency | tested (1 USD = 3.70 PLN) |

## 4. Recipients and delivery
| Case | What the agent does | Status |
|---|---|---|
| **One recipient only** (e.g. a creator) | page shows that view only, no view bar | untested |
| **External creator** | share the creator view link; confidential parts are never in that view; Contributor access only for people who decide | tested (view check) |
| **Recipient without claude.ai** | self-contained HTML file (videos embedded) as fallback (CB12); decisions via "Copy my decisions" | untested |
| **Organic use only** (no ads) | media-buyer view off; sound trends allowed if licensed for organic; KPI becomes organic (views, saves, follows) | untested |

## 5. Production routes after the brief
| Route | What the brief must contain | Status |
|---|---|---|
| UGC creator | creator part (CB13) with key points, shots, extra takes for hook variants, usage rights | tested (dry run, not produced) |
| In-house edit from stock or existing footage | editor part plus a footage list | untested |
| AI generation (later, outside PB2) | beats with visual descriptions are the prompt base; generation is out of scope at the brief stage | — |

## 6. Proposed order of tests
1. Finish the LD dry run on the page (decisions at G2–G4) and produce one concept with a real creator.
2. Live test of that concept through PB1 (R4), with `brief_id` in the results library (R5).
3. A run on a product with tier A reviews (Shopify or Amazon).
4. A run for a non-English market (PL).
5. A run with Foreplay connected (hook-level saturation in paid).
