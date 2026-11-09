# Meta Ads MCP (official, connector "Facebook Ads MCP")

The user connects it in Claude Code (or through their claude.ai connector) with their Meta login.
Meta enables its Ads MCP **account by account**: a refusal for this ad account is `not_enabled`
in the doctor, and the user enables it in Meta. Read each tool's own schema for the exact
argument names; the notes below are what the tests found.

## From the playbook handoff (HANDOFF.md section 3, verbatim)

- `ads_get_ad_entities` gives metrics at the ad level (spend, frequency, CTR, plays, ThruPlay, p25–p100, cost per result, `time_increment=1`).
  - `3_second_video_plays` exist only at the ad set and campaign level.
  - Continuous 2-second plays at the ad level come back empty.
- `ads_get_ad_videos`: `download_hd_url` returns null, so **the winner's video file is a mandatory input from the user**.
- Upload: `ads_creative_upload_media` accepts a public URL or a local file (interactively). For AUTO, hosting with a public URL is needed.
- We always create campaigns, ad sets and ads as PAUSED.
- Ad Library (`ads_library_search`): keyword search is loose, so the results must be filtered for relevance. `ad_delivery_start_time` tells how long the ad has been running.

**Changed for the plugin:** we never host files publicly, at any level. When a local file can't
be sent, the user uploads the named files to their Ads Manager media library and you find them
by name (SKILL.md section 7). A community report says the MCP also rejects the `source` field, so
the video is never fetched through it (A2).

## The calls a run makes

| Step | Call | Notes |
|---|---|---|
| readiness | `ads_get_ad_entities`, one ad, the user's account | the cheap check: `ok`, `missing` or `not_enabled` |
| A1 | `ads_get_ad_entities`, ad level, `time_increment=7`, today−92 to today−2 | weekly totals for every ad; R1's fields plus the retention ladder R2 reads (`video_play_actions`, `video_p50_watched_actions`, `video_p75_watched_actions`, `video_p95_watched_actions`, `video_p100_watched_actions`, `video_avg_time_watched_actions`); every page saved |
| A1 | the same at account level | the account trend for R1; if empty, the ad files stand in |
| A1 | `ads_get_ad_entities`, `time_increment=1`, the top 5 ads by spend and the chosen ad | daily evidence and the chart, R1's fields only (no ladder); never beside their weekly rows in `tm r1` |
| A1a (R2b) | `ads_get_creatives` across the account; `ads_get_ad_videos` | the other ads with the same video: the same video id, or the same thumbnail and length (a re-upload gets a new id); the video's length for `tm structural --length-s` |
| A1a (R2b) | `ads_get_ad_entities`, ad level, each of those ads and the chosen ad, its whole life | `video_play_actions` and `video_p25_watched_actions` to `video_p100_watched_actions`, with `date_start`, `date_stop`; the rows copied unchanged into the uploads file `tm structural` reads (`flow.md#a1a`) |
| A2, A3 | `ads_get_creatives`, `ads_get_ad_videos` | copy, headline, call to action, thumbnail, the video's id and length (not its file) |
| A3b | `ads_get_ad_entities` at ad set level (targeting); breakdowns age × gender and `publisher_platform` × `platform_position` | region has no conversions |
| A4, A6 | `ads_library_search` | the market (and supporting markets); filter for relevance |
| E1 | `ads_experiment_check_eligibility` | before the plan is final |
| E2 | `ads_creative_upload_media`, `ads_create_*` (PAUSED), `ads_get_ad_preview` | ids saved in `05_results/` |
| E3 | `ads_experiment_abtest_create_test`, `ads_activate_entity` | only after a green R8 and the launch check-in |
| E4 | `ads_get_ad_entities` and the test's results | on day 3, 5 and 7 |

## Reading the numbers

Meta sends numbers as strings, with units and percent signs (`"14.24%"`,
`{"value": "93.22", "unit": "PLN"}`), and sometimes without `results`. Never convert or round
them yourself: save the answer verbatim and let `tm r1` read it (it accepts a list of rows, a
raw `{"data": [...]}` answer, and several pages). The result is the **campaign objective's
result** (purchase, lead, install), not always a purchase. The average watch time
(`video_avg_time_watched_actions`) comes in whole seconds per day: it is a rough figure, shown as
"about 6 s", never as a precise one. Meta counts p25 to p100 separately, so a later mark can
exceed an earlier one on a day; the engine clamps each step, never correct the numbers yourself.

## Links for the user

- An ad in Ads Manager: `https://adsmanager.facebook.com/adsmanager/manage/ads?act=<account
  id>&selected_ad_ids=<ad id>` (the account id without `act_`).
- The media library is in Ads Manager under the account's media (Meta Business Suite, Content →
  media); the user uploads files there by hand when the MCP can't send them.
