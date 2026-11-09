# Customer voice: the angle comes from what customers say (shared: PB02; later PB03)

A concept leads with the aspect of the product that customers themselves stress (CB5). This is
how a run finds it, codes it and proves it. The engine fetches and checks (`tm voice`); you read,
code the themes and choose the phrases.

## Three tiers, always labelled

| Tier | What | Where it comes from | Counts as evidence? |
|---|---|---|---|
| A. Own customers | what the product's buyers say | reviews, support tickets, surveys, DMs, comments: an export the user has, or a page they named | yes, the strongest |
| B. Category | what people in the category say, not about this product | the Reddit archive; reviews of comparable products or competitors the user points to | yes, when tier A is thin or missing |
| C. Brand | how the brand talks to its customers | the landing page, the brand guide, the running ads | **never**: it is the brand's hypothesis, set against A and B |

Missing reviews never block a run: say what you use instead (tier B, with the landing page as
the brand's hypothesis) and go on.

## Tier B: the Reddit archive

`tm voice reddit-posts --run R --subreddit <sub> --query "<keyword>" --json` and `tm voice
reddit-comments --run R --subreddit <sub> --query "<keyword>" --json`. The archive is Arctic
Shift, a **volunteer-run, read-only mirror** of public Reddit posts and comments, not Reddit's own
API (Reddit's own endpoints refuse scripts). Say so in one line when you use it. What it gives:

- **The newest matches for the keyword**, at most 100 a call, never the year's top posts. So every
  count is a frequency within a keyword sample: run **several keyword samples** (the category
  phrase, the pains and desires the landing page names, the persona's words), and always say the
  query beside a count (an invented example: "40 of 300 posts in the archive's answers to 'linen
  sheets' and 'bedding too hot'").
- **It times out under load.** The engine retries, halves its window, and keeps what it got with
  `partial` saying why (the oldest part of the window was not covered): say so when you cite that
  sample. A call takes minutes: give it the Bash tool's longest timeout (10 minutes). A failure
  partway through drops the chunks that call had already fetched: say so and run it once more.
- **It not answering at all is a stop**: say the archive did not answer, then ask for reviews or
  an export, name another source the user can point you to, or offer to try the archive again
  later. The landing page is the brand's own view (tier C, its hypothesis about its customers): say
  it does not stand in for the customers' words. Never quote from memory.
- Each answer is saved as `02_research/voice/reddit_<sub>_<kind>_<query>_vNN.json` (with the URL
  it asked, `_query_url`), and its items go into `02_research/voice/items.jsonl` (ids `t3_…` for
  posts, `t1_…` for comments). AutoModerator is dropped.

**Goodreads is not used.** The dry run read book reviews from Goodreads, but its terms
forbid scrapers, it put a bot challenge on 5 of the 7 books, and it gave about 7 % of the dry
run's items. Reviews the user has (or that you saved from a page they named) go in through
`tm voice import` instead.

## Imports: tier A, and tier B the user points to

`tm voice import --run R --file <file> --format csv|jsonl|text --source <label> --tier A|B
[--text-column <column>] --json`. Ids are `<label>:<n>`.

- **Reviews go in one per row:** a CSV (with `,` or `;`, as Excel writes it in Poland), or JSONL;
  `--text-column` names the column or key that holds the text (default `text`).
- The `text` format is for texts separated by blank lines (each block one item).
- **A second file needs another `--source` label** ("amazon", "amazon2"): the same label twice
  is refused.
- A page the user named: fetch it, save what it says as a file in the run with the Write tool,
  record it, then import that file.

## The themes file

Code the items yourself: read them in `02_research/voice/items.jsonl`, cluster tiers A and B into
themes (an aspect of the product, a pain, a desire, an objection, an outcome), and write
`02_research/voice/voice_themes_v01.json`:

```json
{"schema": "voice-themes/1",
 "samples": [{"source": "reddit_post", "community": "r/LucidDreaming", "query": "lucid dream", "items": 100},
             {"source": "import", "community": "amazon", "query": "every review in the user's Amazon export",
              "items": 40}],
 "themes": [{"id": "T01", "title": "Tried everything, nothing works", "kind": "pain",
             "items": ["t3_abc1234", "t3_abc5678"],
             "quotes": [{"item_id": "t3_abc1234", "text": "nothing I try works"}]}],
 "language_bank": [{"phrase": "nothing I try works", "item_id": "t3_abc1234"}],
 "brand_claims": [{"claim": "You trust tested techniques more than mystical promises",
                   "source": "00_raw/landing_nightschool_2026-11-04.txt", "verdict": "repeated",
                   "items": ["t1_def9012"]}],
 "brand_never_mentions": [], "thin": null}
```

- A theme's frequency is the number of its `items`: there is no separate count to get wrong. List
  each item once.
- **Quotes and bank phrases are verbatim**: each is in its item's title or text, on whole words
  (case, spaces, curly quotes and the ellipsis aside). Never tidy a customer's words.
- **The language bank** holds 20–40 short phrases (the example shows one) (`voice.bank_min`, `voice.bank_max`). When the
  sources are too thin for that, `thin` says why, and the bank holds at least one.
- **Every sample names its query.** A sample pulled without a keyword (an import, a whole thread)
  is either left out of the counts, or its query is described in words ("every review in the
  user's Amazon export").
- **Brand claims** (tier C) each have their source and a verdict: `repeated` (customers say it
  too: a strong angle), `not_repeated` or `contradicted` (a finding). `brand_never_mentions`
  lists the themes the brand never talks about (also a finding).
- `tm voice check --run R --file 02_research/voice/voice_themes_vNN.json --json` proves the file
  against the items. Exit 2 lists what to fix: write a new version and check again.

## How the voice is used

- A recurring theme is an **angle candidate**: which aspect of the product to lead with.
- **Every concept uses at least one bank phrase** (`voice.min_phrases_per_concept`), verbatim or
  minimally adapted, where it sounds natural: in the hook, the on-screen text, a spoken line or the
  primary text. The brief marks the phrase, where it is used and its source.
- Testimonials appear only when the concept calls for it, never invented: a quote is a customer's
  words with its link.
- Comment texts under ads are not available (the Meta connection gives counts only): they come
  from an export.
