# Customer voice: the angle comes from what customers say (shared: PB02; later PB03)

A concept leads with the aspect of the product that customers themselves stress (CB5). This is
how a run finds it, codes it and proves it. The engine fetches and checks (`tm voice`); you read,
code the themes and choose the phrases.

## Three tiers, always labelled

| Tier | What | Where it comes from | Counts as evidence? |
|---|---|---|---|
| A. Own customers | what the product's buyers say | reviews, support tickets, surveys, DMs, the comments under the brand's own ads: an export the user has, text they paste, or a page they named | yes, the strongest |
| B. Category | what people in the category say, not about this product | reviews of comparable and competing products, discussions on the web (forums, Q&A sites, local-language communities), the Reddit archive | yes, when tier A is thin or missing |
| C. Brand | how the brand talks to its customers | the landing page, the brand guide, the running ads | **never**: it is the brand's hypothesis, set against A and B |

Missing reviews never block a run: say what you use instead (tier B, with the landing page as
the brand's hypothesis) and go on.

## Tier B: reviews and discussions on the web, first

Reddit alone is a weak default: one kind of voice (younger, more engaged than many buyers), slow,
and outside TrendsMesh's control. So tier B starts with what people who bought in the category
wrote, in the market's language, with the tools you already have:

- **Reviews of comparable and competing products** (the competitors from the landing page, the Ad
  Library and the user; one or two web searches find more): public review pages of 3 to 5
  products, on marketplaces, price-comparison sites, Trustpilot, app stores, bookstores and
  book-review sites. The 1 to 3 star reviews give the pains and objections, the 4 and 5 star ones
  the words for the outcome people want.
- **Discussions on the web:** web searches with problem phrases in the market's language ("I
  can't…", "has anyone tried…", "nothing works"): forums, Q&A sites, comment sections, and a
  non-English market's own local-language communities. Items from the last 12 months only.
- **Save each page's own text,** never a WebFetch summary (a model's retelling, not the page):
  `tm page fetch --run R --url <url> --name <short name> --kind voice --json` writes
  `00_raw/voice_<name>.txt`. Copy its reviews or posts word for word into a JSONL file, one per
  row with its `url` and `date`, and import it (below). A site that refuses programs is skipped:
  never work around it.
- **Stop when there is enough:** about 60 to 100 items, and the next source adds no new theme.

## Tier B: the Reddit archive, capped

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
  sample. Each query stops at 90 seconds (`--max-seconds`) or after 4 timeouts in a row, keeping
  what came back: move on rather than run it again. Give it the Bash tool's longest timeout (10
  minutes) all the same: one slow answer can stretch the cap. A failure partway through drops the
  chunks that call had already fetched: say so.
- **After the web, and only as much as it adds:** at most 3 or 4 queries, posts before comments,
  over the last 12 months (the default window). For an English-language market it stays a regular
  source; for a market where Reddit has little in its language, the reviews and discussions carry
  tier B.
- **It not answering at all is a stop**: say the archive did not answer. When other sources
  already gave items, go on without it; when none did, ask for reviews or an export, name another
  source the user can point you to, or offer to try the archive again later. The landing page is the brand's own view (tier C, its hypothesis about its customers): say
  it does not stand in for the customers' words. Never quote from memory.
- Each answer is saved as `02_research/voice/reddit_<sub>_<kind>_<query>_vNN.json` (with the URL
  it asked, `_query_url`), and its items go into `02_research/voice/items.jsonl` (ids `t3_…` for
  posts, `t1_…` for comments). AutoModerator is dropped.

**Goodreads is not used.** The dry run read book reviews from Goodreads, but its terms
forbid scrapers, it put a bot challenge on 5 of the 7 books, and it gave about 7 % of the dry
run's items. Reviews the user has, or that you saved from a review page, go in through `tm voice import`
instead.

## Imports: tier A, and tier B from the web

`tm voice import --run R --file <file> --format csv|jsonl|text --source <label> --tier A|B
[--text-column <column>] [--url <page>] --json`. Ids are `<label>:<n>`.

- **Reviews go in one per row:** a CSV (with `,` or `;`, as Excel writes it in Poland), or JSONL;
  `--text-column` names the column or key that holds the text (default `text`).
- The `text` format is for texts separated by blank lines (each block one item).
- **A second file needs another `--source` label** ("amazon", "amazon2"): the same label twice
  is refused.
- **Each text keeps its link and day:** a CSV column or JSONL key `url`, and `date` (YYYY-MM-DD,
  the day it was posted), are kept on its item; `--url` names the page a whole file comes from.
- A page (one the user named, or a review page you found): save its text with `tm page fetch
  --kind voice`, copy its texts word for word into a JSONL file (record it), then import that file.

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
