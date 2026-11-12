# Changelog

What changed in each version of the TrendsMesh playbooks plugin.

## Unreleased

- **Creative brief's page has the TrendsMesh look of every playbook page.** The brief page now has the TrendsMesh
  top bar with the playbook's name, the theme, and the run page's layout. The brief sits under the check-in it is
  up for. The check-ins already decided are folded below it, read-only, with what was chosen, the team's verdicts
  and every note in full. Nothing in them can be clicked, and the creator's view never shows them. Every view, the
  PDF downloads and the team's own decisions (each person saves theirs) work as before. A page in another language
  now also needs the run page's words translated, else it is built in English and says so.
- **Create an ad's pages leave no decision empty.** On a page with a choice per item, the recommended one now comes
  selected: the first concept, accept for each gate item (redo for a take that fails its QA), and the checked
  edit's version. Change only what you want; what you leave as it was is recorded with your answer, so the takes'
  halves no longer come back without a verdict.
- **The run page's counts read right in your language.** "Out of 1 videos read" on a trend card, "Running for 1
  days" on a model ad and the copy's "of 125 characters" now take the form their number needs: "1 video" in
  English, and each translated language's own forms, as the trend report's counts already do.
- **The model ads play on the concepts page.** Create an ad saves each model ad's thumbnail and its first 15 seconds
  from the Ad Library answer into the run, and the concepts page plays them, instead of linking out to the Ad
  Library. An image ad shows its picture.
- **The plugin installs on Windows paths.** Cloning the plugin on Windows could fail with "Filename too long": its
  longest file path was 124 characters, and Claude Code's plugin folder and your user profile come in front of it,
  against Windows' limit of 260. Every path in the plugin is now 90 characters or fewer, and a test keeps it so.
  Some eval cases have shorter names (`evals/RESULTS.md` lists the old and new ones).
- **The doctor with no playbook named is a quick general check.** `/trendsmesh-playbooks:doctor` on its own, or
  "check the plugin", used to check Refresh an ad and wait minutes for the Meta Ads tools. It now checks only what
  every playbook shares: the base tools, whether your Replicate token and ElevenLabs key work, and your TrendsMesh
  sign-in, without Meta Ads. Name a playbook ("check trend research") for its full check.
- **The README says what a first install needs.** On Windows, install Git for Windows first; Claude Code needs a
  paid Claude plan; and where to add the Replicate token and the ElevenLabs key when the install didn't ask.
- **The support report names Windows 11.** It said "Windows 10" on Windows 11; it now reads the build number.
- **One way to send the support report.** The doctor now says what the report itself says: read it, then send it
  privately to contact@trendsmesh.com, not to a public issue.
- **Create an ad checks the takes and the edit itself.** Moving past the takes now needs every generated take QA'd,
  and the takes are accepted only when each passes, or after you have seen the one that failed: a word heard twice
  in a row that the script says once fails it, and a word that lasts about twice as long as it should is flagged as
  a possible hidden repeat. The edit is shown for review only after its QA: the loudness at −14 LUFS with a true
  peak at or below −1.5 dBFS, the lines heard in full, and every CA11 check written down, which the review shows as
  "what was checked".
- **Create an ad's copy makes no promise its claims don't.** Besides numbers, the copy check now refuses a promise
  of results or availability ("guaranteed", "in stock", "results in", "gwarantujemy", "od ręki") that none of the
  text's checked claims says. The phrases are read in the ad's market language, English and Polish to start; for
  another language the check says plainly that it read the numbers only.
- **Create an ad is in the README.** The playbook list now says what Create an ad makes and needs (a product with a
  website, the Meta Ads connector, Replicate and ElevenLabs for the paid parts, TrendsMesh optional), with an example
  of what to say.
- **An acceptance suite for Create an ad.** `/trendsmesh-playbooks:acceptance ads` runs five cases on your own
  product: an ad with a presenter, a site whose pixel fires (an upload proposal with a conversion objective), an ad
  without a presenter, your own voice-over and footage, and the PAUSED upload with every object read back paused. It
  spends at most 8 US dollars on Replicate and 4,000 ElevenLabs credits in all, and nothing on Meta ads.
- **Create an ad's check-ins are on its run page.** Each check-in you see now goes on one page per run, in the
  TrendsMesh look, as in Refresh an ad: the concepts with their model ads and trends, the script-board and the
  production plan with every price and its date, the first visuals, the music and the takes side by side and raw,
  the storyboard one scene at a time (the arrow keys move between scenes), the edit's versions side by side with
  notes pinned at the playing version's time, the Meta copy editable with live counts against each limit, and the
  PAUSED upload proposal. Everything on it comes from the run's files. You choose on the page (the concept, each
  take, a note per scene, the copy's edits) or in chat: both count the same. Without a way to publish pages, Claude
  gives you the page as a file and you answer in chat. Nothing on the page spends money or switches anything on:
  the upload page only records "go ahead" or "skip".
- **A saved profile says which run it comes from.** When Organic AI video offers to reuse a channel profile (or any
  playbook a brand profile), it now names the run the profile was saved from and that run's date, and when you
  confirmed it, so you can tell whether it is still yours and current. `tm brand show` gives it as `saved_from`; a
  profile saved by an earlier version is found too.
- **The resume question says when the trend data has expired.** When you have an unfinished run and ask for
  something else, Claude still asks whether to continue it, and now also says when that run's trend data is past
  its valid-until date, offering a new run with fresh data or to continue on the old data. `tm status` gives it as
  `trend_data`.
- **The teardown shows what it is unsure of in one picture.** `tm tool teardown` now also writes a check sheet,
  `teardown_vNN_check.png`: one row per overlay it is unsure of (and each band or whole-shot note to check), with the
  box drawn on its first, middle and last frame, so Refresh an ad's "look before you trust it" starts from one image.
  It is free and local. The text pass's limits are listed with it: it does not read the words (no OCR), may miss
  stylised or thin fonts, and can take a product label in a still shot for a full-frame card.
- **A failed video render no longer leaves Chrome running.** When a render stopped before Remotion's headless Chrome
  answered (a connection timeout), that Chrome kept running in the background. `tm render` now closes it after the
  render, and leaves alone a Chrome whose render is still going. Two renders that update the copied sources at the
  same moment no longer delete each other's copy.
- **Every voiceover is recorded with Eleven v4.** Refresh an ad, Organic AI video and Create an ad now record with
  ElevenLabs' Eleven v4 unless you pick another model. Refresh an ad still uses Multilingual v2 for a line pasted in
  among the original ad's sentences, since it keeps their pace. A new recipe says how to write for v4.
- **Numbers are read right in your market's language.** The voiceover is recorded in the run's market language, and
  its numbers, dates and percentages are written out as words in the right grammatical form (in Polish a year or a
  count changes with its case). Captions and on-screen cards can keep the digits. Organic AI video's pack check
  refuses digits in an ElevenLabs line.
- **The voice budget matches what the recording uses.** The estimate is the text's characters at the chosen model's
  credit rate: about half a credit a character on v4, where it used to count one, so it asked about twice what the
  recording used. A re-record that the approved voice budget no longer covers no longer stops the run: Claude asks
  you to approve the difference (what the run already spent plus the new recording), then records it.
- **A budget of 0 can be approved.** An animation costs $0 on Replicate, and `tm budget approve ai_usd 0` was
  refused.
- **The video's cuts follow the recorded voice.** After the voiceover is recorded, `tm organic vo-sync` compares its
  word times with the pack's line times and the take prompt's cuts, and proposes new times for anything more than
  about 0.3 s off. It is free and runs before anything paid. A narrator's take whose cuts are off the recorded voice
  is not run. The pace check (`qa.wps_min`) now covers an ElevenLabs voiceover too.
- **Your own ElevenLabs voices.** `tm tool elevenlabs voices --mine` lists the voices on your account, your clones
  and the voices you saved, with previews. It is free.
- **`--help` works on every tool.** `tm tool elevenlabs --help` said it costs money and needed a run and a cost.
  The help of every tool, paid or not, now shows with no run, no cost and no key.
- **Organic AI video closes the images and takes stages after your decision.** The check-in on the images (F1) and
  on the takes (F2) now comes while the stage is open, and the stage closes only after your answer, so the chat no
  longer shows a step finished before you judged anything. A redo keeps the stage open and asks you again.
- **Redoing the final edit goes back to the edit.** "Redo" on the final edit now takes the run back to the edit
  (G1): the new final, its cover, the posting kit and the delivery page go through their steps again, and the
  engine refuses a final older than your redo. Before, the run moved on to posting and the new files were made
  outside the steps.
- **A word changed for the voice keeps the storyboard's approval.** An animation's storyboard is approved on what
  it shows: its scenes, their order, the on-screen text (a new `on_screen` per script line in the pack) and the
  style. Changing a word of the voiceover so it is read right no longer asks you to accept the same storyboard
  again.
- **The upscale is checked and picked by itself.** After you accept a take, its upscale to 1080p is an automatic
  step: `tm organic upscale` checks only what an upscale may change (the size, the frame rate, the sound) against
  the take you accepted, and picks it by rule. You are not asked about it again, and one that changed the take
  stops with what it found.
- **Every command finds a run's file by the same relative path.** A path such as `03_wip/edit_v01.props.json` is
  now read in the run folder first, whatever folder Claude works in, for every `tm` command with `--run`: among
  others `tm render`, `tm tool transcribe`, `tm tool teardown`, the ElevenLabs and inpaint tools, `tm record`,
  `tm register check`, `tm library add`, `tm r1`, `tm diagnose`, `tm r4` and `tm trends shortlist`.
- **Pages build without manual previews.** A check-in or delivery page now makes the 720p preview of every video
  over 15 MB itself (free, on your computer) and shows it, instead of stopping and naming one file at a time.
- **A new page version can't overwrite decisions you are making.** While the engine waits for your decisions on a
  page, `tm page published` and `tm page await` refuse another version of it until they are read, in every
  playbook. When nobody has decided yet, an empty read of the page's store says so and lets it through.
- **Starting a run lists your unfinished ones.** `tm run new` now returns the unfinished runs of the same playbook
  and name (for Organic AI video, the same channel too), with their folder, date and step, and every playbook asks
  you whether to continue one or start the new one.

- **Organic AI video saves every trend answer, however large.** A search of 15 or a list of 50 is often too large for
  Claude Code to show: it saves the answer to a file and shows a notice instead, and the agent had to save each one
  by hand. The collector now reads that file, only from the session's own folder of Claude Code's tool results, and
  saves the answer itself. The agent says which part of the trend search is running and how many are done, and that
  the search takes about 20 minutes.
- **Organic AI video's shortlist keeps the hooks and formats a channel can use.** A word filter dropped formats such
  as a talking-head explainer because their descriptions don't name the niche. Hooks and formats now get a fit score
  for the channel instead, shown with one line on why, and the search lists format trends too. Topics are still
  filtered, by the broader subjects the channel covers.
- **Organic AI video's shortlist speaks of organic videos.** Its sounds and formats no longer carry Creative brief's
  ad wording, and a trend whose videos aren't pulled yet says "evidence videos not pulled yet" instead of "no
  evidence in the last 7 days".

- **Organic AI video picks trends by the channel's type.** The channel profile now has a type (news and explainers,
  how-to and education, entertainment and skits, music and dance, lifestyle and vlog, shop and product, or other in
  your own sentence), proposed from the channel's videos and confirmed by you. It sets how many trends of each kind
  are pulled, out of 12: a news channel gets 6 topics, a music channel 6 sounds, instead of 3 of each for every
  channel. A trend that doesn't fit the channel never takes a place; its place goes to the type's leading kind. At
  least half of the proposals are built on that kind, and the proposals page says why ("A news and explainer channel,
  so topics come first."). A profile saved before keeps working, with 3 of each, until you give it a type.
- **Organic AI video's delivery page gives one text to paste per platform.** On TikTok, Instagram and Facebook
  you copy one description with the hashtags already in it; on YouTube the title, the description (with its
  hashtags) and, new, the tags, each with its own Copy. The cover, the AI label, the sound and the product are an
  "At posting" list of plain steps with no Copy button, and TikTok's search phrase comes with a reminder to check it
  in Creator Search Insights. The platform ticks on the proposals and delivery pages now read "Posting kit for",
  with a note that you post the video yourself. The kit's Markdown follows the same layout.
- **Organic AI video's posting kit follows platform rules written for every niche, and checks them.** The posting
  rules are rewritten for creators, education channels and shops (they were about one pet store), and their limits
  were checked again against each platform's own pages on 2026-11-12. They are dated: Instagram's cap is now 5
  hashtags per its Help Center, YouTube's tags take 500 characters counted as YouTube counts them, and the
  description 5,000 bytes. Every kit records the date of the rules it was written to, and `tm kit check` refuses a
  kit without it; it checks the limits on the text as you paste it, the TikTok search phrase in the first line, and
  the AI label against what the video is: on everywhere for photoreal scenes, off for a clearly animated style
  unless you ask for it. It warns about a field it does not use, a search phrase that is not from the trends, and
  rules more than 3 months old. Kits saved before still load, show and pass the earlier checks; checking one again
  asks for the two new fields.

- **Each Organic AI video idea says how it will look.** A proposal now suggests its look from the trend and the idea
  (for example "realistic, 1990s home camcorder"), and you can change it on the proposals page. The recipe keeps it,
  and every scene's prompt follows it, so the look stays the same from the first shot to the last.
- **An animation says up front what it needs, and suggests its styles.** On the proposals page, an AI video lists
  what it still needs installed, with the size and time, before you pick it. Once you pick, Claude asks once for
  everything the chosen videos need. An animation asks only for its own tools, not the video breakdown or AI video
  tools it never uses. An animation idea also suggests 2 to 3 of our styles, each with its colours and one line on
  why, and the one you pick is already selected when the style is chosen. `tm env install` now names the tools it
  installed (it said "video" for the animation tools).
- **Your channel's own style is kept.** At the start you can describe the style your channel's videos are made in
  (for example "paper cut-out collage, old engravings, flat colour"). It is saved in the channel profile, and every
  later run puts it first on an animation's style list as "Your channel's style", already selected.
- **A video idea's risk level counts what can really go wrong.** The level is now the highest risk left after its
  mitigation, not the number of risks: several characters are a low risk on still images and a medium one in AI
  footage, and text the model would draw is no risk when all the text is added in the edit. The proposals page says
  where the level comes from, for example "Highest risk: several characters, in AI footage (medium)".
- **Organic AI video's text on screen is two layers, in a style you approve.** Under a voiceover, captions now read
  like the platform's own: 2 to 4 words at a time from the recording's word times, white with a black outline, at
  the bottom, made by the plugin (`tm organic captions`), with the spoken word lit if you like. Only the hook, the
  key number and the closing question go on top, in a box. Before the edit, the images check-in shows both drawn
  on your first frame (free): accept it or say what to change. The text can now move up or down off a face, use the
  whole width of the safe zone, and wraps to its size.
- **No AI shot sound under a voiceover.** A generated shot always comes with its own sound; with a voiceover it is
  now muted in the edit, and the render refuses to keep it unless you asked for it.
- **The cover's text stays clear of the face.** The plugin finds the face in the cover's frame and moves the words
  above or below it, or makes them smaller, inside the 3:4 crop (`tm tool cover_fit`).
- **The plugin fetches the music.** A Mixkit track (free for commercial use, no credit needed) is found with
  `tm tool music_fetch`, shown with its title, author, length, size and licence, and downloaded into your channel's
  music folder only after your yes, indexed with every field filled in. The tracks offered to you are copied into
  the run, where the page plays them and the edit uses the one you pick: you never download or copy a music file by
  hand.
- **Organic AI video asks its start questions on a page.** The intake is one page with an option set per question,
  the default already ticked, a text field only where something has to be typed, and one Done button. The free script
  to film is the default; an AI video is chosen only by a click. An answer in chat still counts the same.
- **Pick the style, voice and music after hearing them.** A new page shows the voiceover script with its times and a
  note on each line, the styles, a few voices with a player (your own ElevenLabs voices too) and the music: "No track,
  I'll add a sound in the app" first, then the trending sound when one fits, then 2 to 3 tracks you can play. Your
  picks go into the pack by themselves.
- **The storyboard is a list of frames.** The images page shows each frame large (full size on a click), with its
  time, the voiceover line and what is on screen, and a note under each, so only the frames with a note are drawn
  again.
- **The voiceover is on the check-in pages.** The images page plays the recorded voiceover before anything paid is
  made, and the video page plays each take with the voiceover laid under it and the take's own sound turned down.
- **Choose the models of your video on a page.** After the idea is picked, before the pack, a Models page lists
  the models for the images, the video, the upscale and the voice, in three groups (budget, suggested, best quality),
  from today's rankings and Replicate prices read for free. Each shows its price for this video, its place in a
  ranking with the date, what it is good at and a link to its Replicate page; the total follows every click. A model
  that can't work for this video is greyed out with the reason (Seedance with a realistic face in the frame), and a
  model without a prompting recipe gets one written first. The intake no longer asks for a quality tier. At Hands-off
  the suggested models are taken by rule.
- **One click in the chat after a page is saved.** When Claude shows a page with decisions and waits, it ends with a
  reply button "Saved, read my choices" where the app has one, in every playbook. In the terminal you still write
  "done".
- **The trend report in the TrendsMesh look.** Trend research's page is now built on the same run page as Refresh an
  ad and Create an ad: the TrendsMesh top bar with "Trend research", the same colours and shapes, and under the
  report, folded, the check-ins that shaped it (the seed phrases, the category map, the picks, the page, the weekly
  schedule), each with what was decided, by you or by rule, and your note. They are read only: the report still
  takes no clicks and is never published while you are deciding. Its three views, the hooks lists, the Ad Library
  results and the translated words are as before. The page still loads no Google Fonts. For a page in another
  language, the run page's words need translating too (`tm i18n export` lists them).
- **Organic AI video's check-ins are on the run page.** The images, the takes, the final video with its posting kit
  and the style, voice and music are now stages of one page per video, in the TrendsMesh look with the playbook's
  name in the top bar, as Refresh an ad's and Create an ad's pages are: the newest question on top, the earlier
  ones folded below as read-only summaries of what you decided, so an earlier choice can't be saved again by
  mistake. Each item still takes its option, Accept, Redo with a note or Drop, a note on each storyboard frame, the
  platform ticks and the YouTube thumbnail, and the kit's texts still come one per platform with their Copy
  buttons. Large videos are still shown as 720p previews, and the page is in Polish for a Polish run. The
  proposals, the week, the script, the intake and the models pages are unchanged for now.
- **The week page counts its videos in your language.** Its summary said "1 videos this week", and in Polish
  "filmów" for every number; it now says "1 video", "2 videos", and in Polish "1 film", "3 filmy", "5 filmów".

## 0.12.0

- **Creative brief's PDFs print when the run is given by a relative path.** `tm brief page --run <relative path>`
  printed no PDFs on Windows (the browser could not write to the relative path), so the page was built without
  its download buttons. The browser is now always given the full path. And when the PDFs can't be printed, Claude
  now tells you the page has no download buttons and why, instead of leaving it unsaid.
- **Creative brief quotes every note from the page whole.** A note the team left on the brief page was sometimes
  quoted cut short, with "[passage omitted]" where a sentence asking Claude to do something stood. `tm brief
  decisions` now hands over each note as it was written, an approval's note too, in lines ready to quote, and
  Claude pastes them into its reply unchanged and tells you nothing was done with them.
- **A choice saved on Refresh an ad's run page is read.** `tm page decision` used to stop with "Read the decisions
  again…" even after a fresh read, because nothing put a Refresh an ad run's read where it looks. Now
  `tm trends ingest` files a page's database read under `03_wip/decisions/` in any run, the playbook saves the read
  that way (Refresh an ad has no collector), and the stop message names the command.
- **A viewer's check of a page is never taken as its decisions.** The read the Artifact tool suggests after a
  publish (`as_level`, which sees none of the owner-only choices) is no longer saved by the collector, `ingest`
  refuses it and says why, and one saved by 0.11.0 is skipped, so `tm page decision` no longer says no choice is
  saved.
- **The desktop app's own keys stay out of the run.** The `__artifact…` keys the app adds to the Artifact and
  ArtifactData tools' input (one holds a local path and a file hash) are no longer copied into the saved answers or
  the manifest.
- **Live trend searches are summarised again.** The live server's `{"trends": [...], "total": N}` answer is now
  replaced by the short summary, which also gives the `total` and, from it, whether more pages follow; an error is
  still shown whole.
- **The run page carries its title in the run's language.** The Artifact tool keeps a page's own `<title>` over the
  title it is given, so the run page's `<title>` now names the playbook in the page's language, and `tm page build`
  gives that title for the publish.
- **Refresh an ad: the free caption removal no longer adds the AI label on its own.** A clean plate made with the
  free OpenCV caption removal (classical image processing, no model) is no longer counted as AI-edited media for
  Meta's AI disclosure; the paid ProPainter removal and every other AI tool still are. The disclosure card says
  when the free plate was the only edit. Runs already on disk read the same way: their free plates, recorded under
  the old name, stop counting as AI media too, while an answer you already gave to the disclosure question stays as
  you gave it, and ads already uploaded keep the label they were created with.
- **Refresh an ad: when the variant wins, it moves into your campaign, PAUSED.** The live test still compares two
  new ads (the control is made of your original's files), so the test changes one thing only, and your original ad
  keeps running untouched in its own campaign: the test plan now says so, and that the original reaches the same
  people and may slow the test's delivery. When the variant wins and you say yes, the playbook creates a new ad set
  in your original campaign, PAUSED, with the winning ad made from the test ad's post, so its likes, comments and
  shares come along; it never puts it inside your original's ad set, which would restart its learning, and shows
  you the preview. The new ad set copies your original ad set's targeting, placements, optimisation event and bid
  strategy; under a campaign budget it gets none of its own, otherwise the daily budget you name, with your
  original's shown for reference. Nothing is switched on or off: the final report ends with your part, step by step
  (switch the new ad on, move the budget, switch the original off), and under a campaign budget it says that Meta
  can move budget away from your original at once and suggests ad set spend limits for a gradual move.
- **Refresh an ad: the control is a new ad even when the test runs in 9:16 only.** When the 4:5 version of your
  original can't be made, the control used to be your original's own creative, with its post's likes, comments and
  shares, so the two ads differed in more than the change under test. Now the control is always a new creative
  made of your original's files, PAUSED like the variant. The one exception is an ad a new creative can't match,
  such as a partnership ad run from a creator's account: then the control is your original's creative, and the
  plan says so and why.
- **Trend research checks the shortlisted hooks in the Ad Library.** Each hook that fits your category is
  searched in your market's Meta Ad Library in the category's words ("pov nail salon", never the hook's name
  alone), as Creative brief does, and says "competitor found" with the advertiser or "none found in Ad Library
  titles". The map check-in and the report show it next to the hook's fit, and the paid view reuses it instead of
  "Not checkable without Foreplay". If Meta isn't connected, the hooks say "not checked" and the run goes on.
- **The trend report lists hooks in two lists.** A new "Hooks for <category>" section shows the shortlisted hooks
  in fit order: those already used in your category, with how many of their videos are, and those that fit your
  message although nobody in the category uses them yet, each labelled as a transfer to test.
- **A hook's band compares it with every rising hook.** A hook's band ("top 10% of TrendsMesh's 101 rising hooks")
  now comes from its place in TrendsMesh's rising list, not from the roughly 8 shortlisted hooks whose videos
  were read. Its stage still comes from how fast new creators join it. A hook only a search found has no band.
  Reports built before keep their wording.
- **Counts read right in every language.** The trend report and the Organic AI video pages now choose the form of
  each count the way your language does, not just English one-or-many: in Polish "1 trend", "3 trendy", "5
  trendów", "22 trendy". Claude translates each form your language uses once, with the numbers each one is for.
- **The pack and the posting kit in your language.** Organic AI video's pack and posting kit Markdown files have
  their headings and labels in your working language, like the pages, and the QA findings under each take on the
  video check-in are in that language too, instead of English on a Polish page.
- **Stored values in your language.** Words the run keeps as data, such as "top 10%" or "medium" on the trend
  report and "soft mention", "confirmed" or "long_takes" on Organic AI video's pages and pack, are shown in your
  working language. The run's files keep them as they are, so earlier runs open and check as before.
- **Setting up the Replicate and ElevenLabs keys says where to get them.** The plugin settings and the readiness
  card now name the page where each key is made, with a direct link, and what it is for. For ElevenLabs they also
  list the permissions a restricted key needs.
- **The readiness card checks each key.** Each key that is set gets one free call to its provider, so a bad paste
  shows up before the run, not halfway through it. Replicate and ElevenLabs now show the same three states: works,
  connected but unusable (with why and what to do), or missing (with where to make one). When the ElevenLabs answer
  says whether the plan includes voice cloning, the card uses that instead of leaving it unknown. Keys are still
  never shown, not even in part.
- **A refused paid step says why.** When Replicate or ElevenLabs refuses a step, the message now names the cause:
  a wrong or revoked key (where to make a new one, where to put it), a restricted key (which permissions to allow),
  no credit or credits used up (the billing page, and how much the step needed), a plan without the feature (which
  plan has it), or too many requests (wait, or add a payment method on Replicate). Nothing is spent, and the run
  continues from the same place after the fix. An answer the plugin doesn't recognise keeps the old message.
- **ElevenLabs credits are checked before a paid step.** Before a voice, music or isolation call, the plugin compares
  the credits left (counting usage-based billing) with the approved estimate. When they fall short it stops and
  says so, before anything is sent. Replicate has no balance to read, so its runs are not checked this way.
- **Reading the ElevenLabs credits no longer needs the voice tools.** This free check used to wait for the voice
  tools (about 1 GB). It now works as soon as the key is set. The tools also no longer print "ignoring
  SSL_CERT_DIR: no certificates found" on Windows.

## 0.11.0

- **New playbook: Create an ad (first build).** Makes a new Meta video ad from zero for a product with a website:
  a short intake, concepts built on a proven ad format and rising trends, the claims, a script-board, a production
  plan with each model's dated price, the paid stages each shown first, the Meta copy (5 primary texts, 5 headlines,
  5 descriptions, checked for length, links, UTM tags and no invented numbers) and, when you take the offer, the
  campaign, ad set, creative and ad created in your account, all PAUSED. You approve the plan's cost before anything
  is made and the video's cost before the video; a video is never made again without your say. The ad budget and
  the AI-content label are always yours to state, and nothing in this playbook ever switches an ad on: you do that in
  Ads Manager. Without TrendsMesh it still runs, and says plainly that its model ads and trends are guesses. Its
  pages come in a later version: for now each step is shown and decided in chat.
- **Video captions keep their font in every language.** Letters with diacritics (ą, ł, ő, ş, …) and Cyrillic letters
  no longer come out in a thinner fallback font in Organic AI video's captions, rankings and quizzes. Every video
  now loads the letters of the market language, and when its font has no letters for that script (Greek, Arabic,
  Hebrew, Thai, Japanese, Chinese, Korean, or Cyrillic in Refresh an ad's cards and the Poppins ranking) the whole
  video switches to a matching Noto Sans font. Before a render, `tm render` checks that the font has every letter
  on screen, and if one is missing it stops and names the letter, instead of rendering it in another font.
- **Every run has a working language and a market language.** The working language is what you and your team
  read (cards, pages, briefs, reports); the market language is what your audience sees and hears (ad copy,
  captions, voiceover, on-screen and cover text). Both are filled in from the language you write in, shown on the
  intake card and corrected in the same reply, with no extra question. Runs set up before keep their language.
- **Pages in your language, whatever it is.** The Creative brief page, the trend report (with its digest and
  paid view) and the Organic AI video pages take their headings, labels, buttons and help from one table that
  Claude translates into your language once and reuses in every later run; each page declares its language.
  Until a language is translated, the page is built in English and Claude tells you so, instead of mixing the
  two. Organic AI video is no longer limited to English or Polish pages.
- **The creator-view check reads your languages.** In Creative brief, the check that keeps ad numbers, research
  sources and competitors out of the creator's view now also looks for those words in the run's languages, and
  says plainly when a language isn't covered yet. Brief rows like Account and Competition can carry your
  language's labels.
- **Customer words translated, and said so.** When a customer phrase comes from another language, Creative brief
  translates it into the market language, marks it as translated and keeps the original as its source.
- **The trend shortlist ranks for your market's language.** It no longer assumes English: it reads the run's
  market language unless you name another.
- **The weekly update phrase is in your language.** When no schedule is set up, the phrase Claude offers for next
  week's report is in the language you work in.
- **File names keep their letters.** Saved files whose names come from a search phrase or a query now turn
  accented letters into plain ones (é → e, ß → ss, ł → l, ś → s) instead of dropping them.
- **Refresh an ad shows every check-in on one page, in the TrendsMesh look.** At each check-in you see, the run's
  page puts what's new on top, with that stage's results (the diagnosis, the audience, the trend cards with their
  type, strength and what confirms them, the change register, the brief, the budgets, before and after, the test
  plan, the pre-launch check) and the decision right under them. Earlier stages fold below as "Already settled",
  each with what was decided. Every number shows its source when you hover over it, and each table downloads as
  CSV. Claude publishes the page once and updates the same link at every check-in; the engine builds it from the
  run, so it never has to be rebuilt by hand.
- **Choose on the page, and the choice is the one recorded.** Clicking an option saves it at once, with your
  note, and only the question open now can be clicked: an earlier decision is a summary, never a button, so it
  can't be saved again by mistake. Claude reads your choice from the page and records it as your answer "(from
  the page)", and refuses a choice made on an earlier version of the question. Answering in chat still works at
  every check-in. Without a tool to publish pages, the same page opens from your computer and asks you to answer
  in chat; the old review page (`tm review build`) now builds this page.
- **A page's file links survive Git Bash on Windows.** A page whose link to a stored file was rewritten by the
  shell (`C:/Program Files/Git/_blob/...`) is refused before it is published, with the fix, instead of showing
  "This file isn't stored" when you open it.

- **Organic AI video shows up again.** A colon in its description kept Claude Code from loading the playbook, so
  Claude didn't know it was there. It loads now, and a test checks every playbook and command file the way Claude
  Code reads them, so one can't go missing like that again.
- **The readiness check sees an unfinished video tools install.** When the video editing tools were installed
  but their Remotion part was missing, interrupted or out of date, the check said ready and the render stopped at
  the end of the run. The check now asks what the render asks, so the install is offered at the start, with its
  size and time.
- **Refresh an ad starts without knowing your ElevenLabs plan.** Not knowing whether your plan includes voice
  cloning no longer stops the readiness check: it's a note that the plan is checked later, at the voice step,
  and only if the ad needs a clone of its voice because the original voice isn't in your ElevenLabs history.
  Claude then reads the plan from your key, and asks you only if ElevenLabs doesn't say.
- **A plan without voice cloning doesn't stop Refresh an ad at the start either.** When you say your ElevenLabs
  plan has no voice cloning, the readiness check notes that cloning isn't available and lets you start. It matters
  only if the ad needs a clone of its voice: then the voice step stops and you choose a plan with cloning, a stock
  voice, or no voice change.
- **Old captions come off for free.** When there is no clean copy of the ad without its captions, Refresh an ad
  now removes them itself at no cost and without asking for money: it paints them out where the ad's breakdown
  found them, word by word, steady from frame to frame so the patch doesn't flicker. When the paid way (ProPainter)
  would look better and no AI budget is approved yet, Claude shows you both and asks first.
- **The brief check flags a product shot with no product.** A storyboard scene that shows the product on a phone
  but doesn't name it draws a plain placeholder. The brief check now says so as a warning, without stopping the
  brief, so Claude names the product before the animatics are made.
- **Refresh an ad reads Meta's answers as they come.** Picking the ad to refresh now reads the Meta Ads MCP's own
  answer shape, so it no longer reports "no ad is fading" after reading nothing. When a Meta file holds no ad rows,
  no spend or no results it can read, it stops with a clear error instead of an empty ranking, and it says how many
  ads, rows, days and how much spend it read.
- **The 4:5 version is no longer dropped.** Refresh an ad now reads Meta's results by placement, so a feed that
  brings a quarter of the results or more gets its 4:5 version again. A placement breakdown with no results it can
  read is an error, not "9:16 only", and the answer shows the feed's share of the results.
- **The teardown finds word-by-word captions and the rest of the text.** In Refresh an ad (A3), `tm tool teardown`
  now also looks for text in frames every 0.1 s: word-by-word captions come out as one overlay with their start,
  end and the moments words are on screen, checked against the spoken words; both lines of a two-line caption
  share one box with its bar; text that comes and goes in the same place stays separate; and an end card or
  full-frame title is listed as an overlay to check. Each overlay says what kind it is, how sure the tool is and
  why to look at its frames, and places where the picture changes with the speech but no text was found are
  listed for a frame check.
- **Pages publish in the Claude desktop app.** Creative brief, trend research and organic video now find the app's
  built-in `Artifact` tool: the readiness check shows shared page links as ready, each page is published as a
  private claude.ai artifact, a later version updates the same link, and the choices people make on a page are read
  back from its database. Sessions with the older artifacts tools (`publish_files`) work as before.
- **A page that can't save says to choose in chat.** Opened as a local file, the creative brief page and organic
  video's proposals, check-in and week pages no longer say your choices are saved or that Claude reads them from the
  page: they ask you to tell Claude your choices in chat.
- **The real reason when a page stays local.** When a session can't publish claude.ai artifacts, Claude says so,
  instead of telling you that shared links need the Claude desktop app.
- **Trend research ranks rising hooks by fit instead of filtering them.** Claude scores every rising hook for
  your category from its card (the same seven criteria Creative brief uses), fetches videos only for the best
  few (8 by default), and shows each one as already used in your category or as a transfer. A niche category
  no longer ends with no hooks after a fetch of several minutes, and category words match whole words only
  ("curl" no longer counts a video that says "curlyhead"). Claude tells you up front when fetching the
  evidence videos will take minutes.
- **Creative brief: the creator view keeps account data out of its header.** The phone cards at the top of the
  page show each concept's title and phone note in the creator view; who each concept is for and its trend line
  stay in the other views. `tm brief check --stage production` now reads the creator view as the page builds it,
  header included, so nothing it shows escapes the CB13 check.
- **Creative brief: every evidence clip gets its own thumbnail.** `tm brief evidence` names each kept thumbnail
  after the clip's video (`02_research/evidence/<video id>.jpg`) instead of the end of its URL, which is
  `thumb.jpg` for every TrendsMesh clip, and writes that path into the new brief version, so `tm brief page`
  builds without any thumbnail edited by hand. A thumbnail it cannot get is taken out of its clip, and the page
  shows the clip link without it.
- **Creative brief: the animatic's product shots show your product.** The `product_phone` and
  `morning_then_product` scenes draw a product screen from the beat's params: the product's name, what is on its
  screen, and optionally a picture of it kept in the run. They no longer draw the dry run's book, whatever the
  product.
- **The creative brief keeps the landing page's own words.** The product page is saved as its literal text
  (`tm page fetch`; a page built by JavaScript is read in your own Chrome or Edge), not as a WebFetch summary, and
  `tm brief check` refuses a quote given as the landing page's that is not on the saved page, or that would come
  from a summary.
- **The creative brief finds the landing page when Meta gives no ad link.** It reads the ad sets' Pixel for the
  pages it fires on and picks the site that matches the market and language, then looks in the Ad Library; you are
  asked "Which page is this product sold on?" only when none of that finds it, and the run notes where the link
  came from.
- **Customer voice comes from reviews and the web first, and Reddit no longer holds up the brief.** The creative
  brief reads reviews of comparable products and discussions in the market's language before the Reddit archive,
  caps each archive query at 90 seconds (over the last 12 months), stops once there is enough, and tells you up
  front that the step takes a few minutes, with progress as it goes. Imported reviews keep their link and date.
- **Refresh an ad: the live test is never a default.** Accepting the intake's defaults gives the creative brief,
  the edited video and the AI video, nothing that spends ad money. The live test is offered on its own and is in
  the run only when you pick it, with your own daily budget and days. Runs and configs that already have the live
  test keep it.
- **Refresh an ad: going live is always your call.** At every level, Hands-off too, the run stops at the paused
  ads and the green pre-launch check and asks: launch or keep paused.
- **Refresh an ad: the test budget is checked at the start.** A rough estimate from the account's numbers at the
  intake, then again on the chosen ad's numbers right after the diagnosis. If your budget can't reach the minimum
  events, the run says so there, with the choices (a higher daily budget, more days, or no test), not at the test
  design after all the work.
- **Refresh an ad: add the live test at the end.** When a run made a video without a test, the final report asks
  whether to test it against the original; a yes, with your budget, reopens the run at the test design.
- **Refresh an ad: caption removal can be approved when the AI video is in the run.** The few cents for
  ProPainter are approved on their own at the caption step, without approving the AI video's plan early; the AI
  video's budget later counts them in its total.
- **Refresh an ad: hook, middle and CTR tests are sized by what they measure.** The budget covers the impressions
  or plays the decision metric needs, with a 4-day minimum run, instead of 30 results per ad, so these tests are
  much shorter and cheaper. Cost per result stays the guardrail; a variant that wins with few results is reported
  as "won, cost per result not confirmed yet", to scale step by step. The plan says what its budget is based on.
- **Refresh an ad asks about AI labelling before the upload.** Meta's AI label can only be set when an ad's
  creative is made, so Claude now asks it with the test plan: it shows what the run made or edited with AI (a
  cloned voice line, music, cleaned-up frames, AI shots) and asks whether to label both ads, neither or only the
  new one. The ads are created once with your answer, and the pre-launch check confirms it instead of asking.
- **The original gets a 4:5 version too.** When the feed needs 4:5 and your original ad exists only in 9:16,
  Claude crops the original to 4:5 as well (free), so both ads in the test run the same formats on the same
  placements and differ only in the change being tested. The test plan lists the files per ad and placement,
  the ads are built exactly as approved (Claude asks before any change), and the pre-launch check confirms it.
- **One upload round in the desktop app.** When Meta's upload opens a file window in the chat, Claude first sends
  you every file it needs, videos and thumbnail, says which to pick, and you upload them all at once.
- **Several sessions in one folder keep their answers apart.** Collection now belongs to the Claude Code session
  that turned it on: each session's TrendsMesh, Ad Library, Meta and page answers are saved only into that
  session's own run, and a session that never turned it on (a Refresh an ad session, for example) has nothing saved
  anywhere. Turning collection on never takes over another session's run, says which other sessions collect in the
  folder, and no longer needs the first call within 10 minutes. Leftover markers of finished runs are cleaned up.
- **An unfinished run is no longer resumed without asking.** When a run of the playbook is unfinished and your
  request doesn't plainly continue it, Claude first asks one short question: continue that run (named, with its
  date and step) or start a new one. Saying "carry on" or naming the run still continues it straight away.
- **A run name already taken suggests a free one.** `tm run new` with a name used that day now names the existing
  run, its step and how to continue it, and offers a free name (for example `Ad-3-2`) for a new run.
- **The key guard blocks only calls that reach a key.** Words such as "secret" or "key features" in a search
  phrase, output redirects, pipes to `head`, heredocs for `tm record`, the plugin's own `tm tool …` commands and
  reading the guard's own files are no longer blocked, and the ffmpeg and pixi the plugin installs can be run by
  their full path. Reading `secrets.env`, the rest of the plugin's data folder, the key variables or a workspace's
  `.secrets/` is still blocked, and so are now a dump of the whole environment (`env`, `printenv`,
  `Get-ChildItem Env:`) and a recursive search or copy of a folder above the data folder (`~/.claude`). A block
  names its rule and the part of the call that matched, and says how to go on.
- **Creative brief: download the report or one view as a PDF.** `tm brief page` now prints the full report and
  one PDF per view with your Chrome or Edge, published with the page, and two buttons in the view bar download
  them (on claude.ai after you confirm the save; opened as a file, they open the PDF). Each PDF shows only its
  view, with the animatic's stills in place of the video and no decision forms. The page's link opens every
  view, so it now says to share it with your team only and to send one view to someone outside it as its PDF;
  the production check also reads the creator PDF for ad numbers, sources, competitors and the currency.

## 0.10.0

- **Developed in the open.** Issues, changes and releases now happen in this repository; release candidates come
  before each release (RELEASING.md).
- **Report an issue.** Ask Claude to report a problem or request a change: it removes your account details, shows
  you the exact text, and files it on GitHub, or sends it privately to TrendsMesh if you have no GitHub account.

## 0.9.2

- **A failed tools install says why.** When the plugin cannot install its tools at the start of a session, Claude
  now gets the installer's own reason (for example "Could not resolve host: pixi.sh") and the path of a log, instead
  of a guess. Running `tm`, or `/trendsmesh-playbooks:doctor`, tries the install again, so a new session is no
  longer needed once the connection is back.
- **Windows:** the pixi installer runs as its own process, and what it says lands in the log.

## 0.9.1

- **Acceptance reports stay private.** `/trendsmesh-playbooks:acceptance` saves its report in the suite's folder;
  you keep it, or send the file to the TrendsMesh team privately. It never suggests posting it in a public place.
- **Ready to publish.** The examples and tests use made-up brands, people and texts, and no team member is named;
  TrendsMesh is the author. Licence: MIT.

## 0.9.0

- **Animations are checked before they are drawn.** When Claude writes an animation, the plugin opens it in your browser and checks it the way a viewer on a phone sees it: every label big enough to read, nothing in the strips TikTok and Reels cover with their own buttons, and no large empty part of a vertical frame. Claude fixes what it finds before you see a storyboard.
- **All 39 styles polished.** Each style's reference animation now passes that check at 9:16 and 16:9 and a visual review of every frame, so the videos made from them start from a clean layout.

## 0.8.0

- **20 more animation styles**, 39 in all: Ink Wash, Stained Glass, Folded Paper, Chalkboard Lesson, Blueprint, Notebook Doodle, Noir, Neon Sign, Manga Panel, Sticky Notes, Riso Print, Newsprint, Isometric Diorama, Low Poly, Green Screen Terminal, Woodblock Print, Art Deco, Memphis Pop, Transit Map and Synthwave. Styles 1 to 19 keep their numbers.

## 0.7.0

- **Our own animation styles.** Animations now use a style library written for this plugin: 19 styles in 14 families, each with its own reference animation, drawing helpers, sound kit and build prompt. It replaces a third-party catalogue whose licence did not allow shipping it.
- Style numbers and names changed. `tm organic atlas-styles` lists the new ones; each says what topics it suits.

## 0.6.0

- **Organic AI videos for your channels.** A new playbook. It reads real trends and proposes videos for your channel on a shared page. You choose which to make.
- **Three outputs.** A script to film yourself, an AI video, or a weekly pack.
- **AI video types.** A talking host. Footage with its own sound. A narrator over visuals. An animation in a style from a library, with a storyboard check before it is made. Quiz, ranking and sections videos.
- **Every spend is priced and approved first.** Prices carry the date they were checked. Nothing is made until you approve the cost. A failed take costs $0.
- **A posting kit for each platform.** Title, caption, tags and the AI label, ready to paste.
- **A weekly plan.** One approval plans the whole week inside a budget you set. Each AI video's cost is still approved before it is made.
- Existing installs pick up organic video when the plugin updates.

## 0.5.0

- **Creative briefs.** A new playbook that writes a creative brief for new ads from your product, or from a trend you picked in a trend report. It needs the Meta Ads connector, and Chrome or Edge to make the animatics. Optional: Claude Code in the Claude desktop app, to share the brief page as a link; otherwise you get a file.
- Existing installs pick up creative briefs when the plugin updates.

## 0.4.0

- **Trend research.** A new playbook that maps one category in TrendsMesh. It sorts the trends into four stages: act now, still rising, too late, and past their peak. For the picks it shows the videos that back them up.
- **A weekly digest.** Each week you ask for the update, and the report is updated under the same link. Claude reminds you when it is due; in the Claude desktop app it can set a weekly scheduled task instead, which runs while the app is open. It shows what changed, and whether last week's calls held.
- **Paid vs organic.** It checks the Meta Ad Library for rising trends that advertisers already use. Where it cannot check, it says so.
- **Your choice of check-ins.** Trend research uses the same three levels as refresh an ad. Running it costs nothing per run.
- Existing installs pick up trend research when the plugin updates.

## 0.3.0

- **Re-cuts of the middle of an ad.** When the drop is in the middle (people leave between 50 % and 75 % of the video, say), Claude now offers re-cuts instead of stopping: a shorter version, a faster middle, a moved or removed scene, a proof shot, a new AI shot or a new voiceover line. Each variant has a level from 0 (a pure edit, free) to 5 (new music, paid). Every cut point is checked before anything is rendered, so a cut never lands inside a shot or a word. Paid steps wait for your budget, as before.
- **A structural check.** If the same step is the weakest in every upload of the same video, Claude says the weakness is in the video itself and offers a re-cut. In Hands-off it is only reported, unless `diagnosis.structural_recut` is true.
- **`/trendsmesh-playbooks:acceptance recuts`.** Claude runs the re-cut acceptance with you on your own ads (cases H1 to H9). It asks for whatever it needs, one question at a time: a file, a key, a budget, or your verdict after you watch or listen. It records each result and writes a report in the suite's folder (`acceptance/<date>_recuts/`). It keeps track of a suite budget of $4 of AI and 3,000 voice credits, and stops the cases that spend once it is used up.
