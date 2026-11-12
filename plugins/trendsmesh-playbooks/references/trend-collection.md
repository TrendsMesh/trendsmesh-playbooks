# Trend collection: every TrendsMesh answer saved to the run (shared: PB04, PB02, PB03)

A category run makes about 150 `get_trend_videos` calls and dozens of searches; one search answer
can pass 250 KB. Copying them by hand would cost millions of tokens. So the plugin has a
**collector**: a PostToolUse hook that saves each TrendsMesh answer (and each Ad Library answer)
into the run folder, with a manifest row, and shows you a short summary instead of the whole
answer. Every number the engine computes comes from these saved files (R3). It collects for
**trend research, creative brief and organic video runs**; in a creative brief run it also saves
the Meta reads and the page tools' answers, and in an organic video run the page tools' answers
(never a Meta read), unchanged (below).

## What was proven (Task 5's spike, Claude Code 2.1.319, under `claude plugin eval`)

- The hook fires for MCP tools. The tool names are
  `mcp__plugin_trendsmesh-playbooks_trendsmesh__<tool>` (the plugin's own TrendsMesh server); the
  hook also matches a server the user added under the name `trendsmesh`
  (`mcp__trendsmesh__<tool>`), and any server's `ads_library_search`.
- The answer reaches the hook as MCP content blocks (one text block holding the JSON). The hook's
  replacement (`updatedToolOutput`) in the same shape is what Claude sees.
- **Not proven:** the real TrendsMesh server's video fields (the mock has no `creator`, `url` or
  `thumbnail_url`): `tm trends check-fields` checks them on the first real pull. The claude.ai
  connector's tool names (`mcp__claude_ai_…`) are not matched: with that connector, nothing is
  saved by the hook (the fallback below).

## Turning it on and off

- `tm trends collect on --run R` **right before the first TrendsMesh call** of the run (trend
  research: B1, right before the first `search_trends`), and **again at every resume** (a new
  session, or after a stop), right before the first call after it, a TrendsMesh call or an
  `ads_library_search` (a trend research run that resumes at its Ad Library step). **A creative
  brief run** turns it on before its first TrendsMesh, Meta or page call: at A1, right before
  `ads_get_ad_accounts`; and at every resume, in any step, right before the next MCP call of any
  of the three. **An organic video run** turns it on at B1, right before the first
  `search_trends`; at every resume, right before the next TrendsMesh or page call; and **in each
  production run, right before its first page publish** (`Artifact`, or the older
  `publish_files`): the marker names one run, so the idea run's marker never collects for a
  production run.
- **One marker per session.** `collect on` writes `<workspace>/.trendsmesh/collect/<session>.json`
  for the Claude Code session it runs in: Claude Code gives every command it runs that session's id
  (`CLAUDE_CODE_SESSION_ID`, the same id its hooks receive), and `--session <id>` names one by
  hand. An answer is saved only into the run its own session turned collection on for (a
  subagent's calls count as its session's); a session that did not turn it on (a refresh-ad
  session, a session of another run) has nothing saved, anywhere. So several sessions can run playbooks in one
  workspace at the same time, each collecting into its own run. `collect on` never takes or
  changes another session's marker; it says which other sessions collect in the workspace, and
  when one collects for the same run. A Meta read is kept by a creative brief run only, and a page
  tool's answer by a creative brief or an organic video run only.
- Without a session id (tm not run by Claude Code, or by a version that does not set it, and no
  `--session`), `collect on` refuses: nothing would tie the answers to this session. Save each
  answer with `tm trends ingest` (the fallback below), or update Claude Code and turn it on again.
- The marker has no time limit: it collects for its session however long the run takes. Turning
  it on again (a resume) only rewrites this session's own marker.
- `tm trends collect off --run R` **at the end of the run** (trend research: after E3; creative
  brief: after E2; organic video: an idea run after C3, a production run after H1) removes this
  session's marker. `tm run new` for a new trend research, creative brief or organic video run
  also turns this session's collection off; another playbook's `run new` leaves it, and another
  session's collection always stays on.
- **Stale markers** (a session that ended without `collect off`): a marker whose run is finished
  or gone, or that cannot be read, collects nothing, and every `collect on` removes it, as well as
  the old one-per-workspace `.trendsmesh/collect.json` of 0.10.0 and earlier, which belongs to no
  session and is never used.
- `collect on` refuses a run of another playbook and a finished run.

## What you see instead of the answer

| Tool | Saved to (`02_research/`) | You see |
|---|---|---|
| `search_trends` | `search/search_<about>[_<type>][_pNN].json` | `{saved_to, results, has_more, page, cards: [{id, kind, name, match, creators, status}]}`, and `total` when the answer gives one (then `has_more` says whether the pages so far hold fewer cards than it) |
| `list_trends` | `lists/list_<sort>_<type>_pNN.json` | the same summary as a search; with `sort` `updated` also `oldest_updated_at`, the oldest `updated_at` on the page (null when no card has one), to page back to the previous run's date |
| `get_trend_videos` | `videos/<trend_id>_pNN.json` | `{saved_to, trend_id, page, videos, has_more, newest, oldest, creators_on_page}` |
| `get_trend` | `trend_<trend_id>.json` | the whole card (it is small) |
| `get_usage` | `usage/usage_<time>.json` | the whole answer |
| `ads_library_search` | `ad_library/ads_<search terms>.json` | the whole answer (you read the ads) |

**In a creative brief run** these are saved as well, each as a new `<tool>_vNN.json` with the
tool's input and the time it was saved, and you see the answer unchanged:

| Tool | Saved to (run folder) |
|---|---|
| `ads_get_ad_accounts`, `ads_get_ad_entities`, `ads_get_creatives` | `01_base/meta/` |
| `ArtifactData` `list` and `query` (saved as `db_list`, `db_query`); the older `db_list`, `db_query` | `03_wip/decisions/` |
| `Artifact` publish (saved as `artifact_publish`); the older `publish_files`, `read_declaration`, `declare_capabilities` | `03_wip/publish/` |

Only these actions of the built-in `Artifact` and `ArtifactData` tools are saved: an `Artifact`
read or file listing, an asset upload, a database write is not, nor a read with `as_level` (it shows
what a viewer sees, not the decisions), and Claude sees every answer whole. The keys the desktop app
adds to their input (`__artifact…`) are not saved. **In an organic video run** only the page tools' answers are saved this way (the same two
folders); a Meta read is never saved to it, and none is needed.

The engine finds them by their input, not their file name (the audience order at B1, the
near-duplicate check at C1, the page's decisions at G2 to G4; in organic video, the proposals
page's decisions at C2, `tm organic decisions`). The TrendsMesh answers are saved
and summarised exactly as in trend research, so read the saved video pages for the evidence
(`02_research/videos/`).

A second answer for the same file name is saved as `_v02`, never over the first. An error answer
(`not_in_plan`, a rate limit, `isError`) is saved and shown to you unchanged: read it and act on
it (the sign-in reference, or wait for the reset). Read a saved file only when a step needs its
content (the evidence videos at D1: `tm research evidence` gives the top five per trend).

## When an answer is not saved

- **The hook says so.** "This answer was not saved to the run (<reason>). Save it with tm trends
  ingest …" arrives with the answer (the same line goes to
  `02_research/collect_failures.log`). Save it: write the tool's input to `03_wip/ingest_input.json`
  and the answer, verbatim, to `03_wip/ingest_answer.json` (the Write tool), then
  `tm trends ingest --run R --tool <tool> --input 03_wip/ingest_input.json --file
  03_wip/ingest_answer.json --json`. The engine names the file as the hook would have (in a
  creative brief run a Meta or page answer, and in an organic video run a page answer, goes where
  the collector keeps it; a page's database read goes to `03_wip/decisions/` in any run, also a
  Refresh an ad run, which has no collector).
- **An answer too large to show** is saved by the collector itself: Claude Code saves it to a file
  and shows a notice naming that file, and the hook reads that file from this session's own
  tool-results folder, saves the answer and gives you the usual summary (or "This answer was saved
  to the run …" for a card). Nothing to do.
- **The answer was not JSON** (the hook says "it is not JSON"): the notice's file could not be read
  (moved, or not in this session's tool-results folder), so nothing reached the run. Save that file
  whole: `tm trends ingest … --file <the file the notice names>`, with the input as above. A tool's
  own plain-text message (a limit, an outage) is not saved and needs nothing.
- **Nothing is said, and the whole answer came back** (the claude.ai connector, collection off,
  or a new session that did not turn it on again for itself): run `collect on` right before the
  next call; if answers still come back whole, use the fallback.

## The fallback: no collector in this session

When answers reach you whole and are not saved (check after the first call: `tm research
search-status` lists no search, the answer had no `saved_to`, or, in a creative brief run, no
new file appeared in `01_base/meta/`), save each answer with
`tm trends ingest` as above. For the video pull (C1), which is too large to pass through this
conversation, dispatch subagents in **batches of ten trends**: each fetches every page of its ten
trends, writes each page verbatim with the Write tool and saves it with `tm trends ingest`, and
returns only one line per trend (pages, videos, the newest date). Say once that this run costs more
tokens without the collector.

## Pacing with `get_usage`

Before a long pull (trend research: the hooks' videos at B4, the evidence videos at C1, the weekly
fetch; creative brief: the evidence videos at B3), call `get_usage` and compare the calls left in
each meter with the pull's size (`tm research fetch-plan`'s `calls_estimate`, plus the `get_trend`
checks; in a brief, the pages of every trend whose videos you read). If it is short, say so plainly
("TrendsMesh allows N more calls until <reset time>; the pull needs about M"), stop and wait for
the reset, then continue from the same place and fetch only what is not saved yet. In the same
session collection stays on; in a new session it is a resume: `collect on` right before the next
call. A rate limit hit mid-pull is handled the same way.
