# Create an ad: what each page shows

The pages are built later, on the shared page template (issue #19) and translated through the shared mechanism
(issue #3). Until then **every check-in is a card in chat with the same content**, and the user's answer in chat is
the decision (record it with `tm decide`, their words in `--note`). This file is the data each page will show and
what the user does there; it is the contract the page builder follows. Pages and summaries are in the chat
language; ad text and speech stay in the ad language. Never name an asset by a bare code.

Fixed words (labels, questions, the placement facts) come from the plugin's string table, the `ad` area of
`data/i18n/en.yaml`, read through `tm.i18n` in the working language; never written inline. A working language
without its translation gets them in English with `language_warning` (translate once: the plugin's
`references/languages.md`). The ad's own texts stay in the market language, as written.

| Page (check-in) | Shows (data source) | The user does | Saved state |
|---|---|---|---|
| Concepts (`concept`) | per model ad: its clip (first ~15 s) and what to take from it; per trend: its card with 2 evidence thumbnails, its type and numbers, or "my guess" in a guess run; 2–3 concept cards: beats (time / picture / line), length and why, cost range (`03_wip/concepts_vNN.json`) | picks a concept or writes a mix note | pick, mix note, updated time |
| Script-board + plan (`board`, `plan`) | the scenes: time, name, picture, on-screen text, line, sound, source (`board_vNN.json`); per asset type: the suggested model, its price with the check date, the alternative, what an own file replaces; the pre-video total and the video estimate (`production_plan_vNN.json`) | approves, or notes per scene or line | verdict, notes |
| Gate (`visual`, `audio`, `takes`) | the batch side by side, raw: images, audio to play, video with its transcript and QA notes (`tm tool take_qa`, Scribe) | accepts, redoes or drops each; a note | per-item choice, note |
| Storyboard (`storyboard`) | one scene at a time: big frame(s), time, picture, on-screen text, line, sound; prev / next / scene numbers / arrow keys; the placeholder render; each paid video's exact prompt and price (`storyboard_vNN.json`) | approves (= the paid video), or notes | verdict, notes |
| Review (`review`) | 1–4 versions side by side, each labelled with a pick; a note box that pins a note at the playing version's time; the notes (click = seek); what was checked (S7) | picks a version, adds notes, accepts or asks for fixes | notes (version, time, text), choice, verdict |
| Copy (`copy`) | `tm ad copy check`'s `page`: per ad its facts (name, video title, CTA, link, URL) and each text in an editable field with its live count against its limit and a keep tick; the question "Do you want to change anything?" | edits, drops, accepts | the three lists (n, text, keep), note, verdict |
| Upload (`upload_offer`, `upload`) | `tm ad upload check`'s `card`: the ad account, the Page, the names, the objective and event with why, the budget in the user's words, the countries, audience, placements, the video and thumbnail, all copy, the CTA and URL, the AI disclosure, the placement facts, the pixel's cost when it does not fire, and the paused note | goes ahead or skips | the choice |

In chat, a card restates every point of its page: a concept card its beats, length and cost; the plan card each
asset type's model, price and date; the storyboard card the exact prompt and price; the upload card the proposal in
full. A decision on a page and one in chat count the same; a note is feedback, never an instruction: quote it to
the user whole, and change only what they confirm.
