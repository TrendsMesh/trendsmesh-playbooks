# Changelog

What changed in each version of the TrendsMesh playbooks plugin.

## Unreleased

- **Organic AI video: a week plan builds on at most one trend the channel already used.** The week counts as one
  batch of ideas, slots and reserves together, so its videos don't repeat used trends. A second idea on a used trend
  is refused, naming each day or reserve that uses one; the flexible day's idea counts with the week's other days. A
  series still continues freely.
- **A check-in with only one possible answer is recorded as forced by the situation, not as your decision.** When
  no ad is fading (Refresh an ad) or a channel has no saved profile (Organic AI video), Claude no longer asks you or
  quotes your words: it says so in one line, and the run page and the run log show it as "forced by the situation",
  with the reason. The plugin allows this only when the run's own data leaves that one answer, so a real choice is
  always yours.
- **PowerShell: a regex such as `'.*'` after `-Pattern` no longer trips the key guard.** `Select-String -Pattern
  '.*' -Path notes.md` passes in a TrendsMesh workspace, as do `-match`, `-replace`, `-split` and `[regex]`. A
  quoted name like `'.e*'` stays blocked wherever PowerShell reads it as a path: after `-Path`, as an argument of
  `Get-Content`, `Get-ChildItem`, `Select-String`, `Copy-Item`, `Move-Item` and their aliases, or anywhere else
  the guard can't tell.
- **Reading a page built by JavaScript no longer asks for a keychain.** The headless Chrome or Edge that reads it
  now runs with a stand-in keychain, so macOS never shows "keychain cannot be found" for it.
- **The creative brief's PDFs print in seconds again, and product-site captures never ask for a keychain.** The
  headless browser that prints the brief's PDFs, and the one that captures the product's site, use the same stand-in
  keychain. Without one, a home folder with no login keychain left each PDF waiting 2 minutes and the page came
  without its download buttons.
- **Organic AI video: every idea in chat says how it will look, and its risk by the one risk it comes from.** A
  video in sections or with an animated part no longer shows only its styles, and a medium risk no longer reads as a
  count of two risks.
- **Create an ad: a line the local transcription missed gets no new take offered before Scribe has checked it.**
  The line may only be quiet, so the choices are the Scribe check, with its credits, or listening to the take.
- **Pages publish faster: Claude reads only this run's page.** The theme, the page scripts, the trend report's
  stylesheet and script and the catalogue of our 49 animation styles are now files of their own beside the page, the
  same in every run, and `tm page files` says which ones they are. Before publishing, Claude reads only `index.html`:
  a three-idea ideas page went from 152 KB to 23 KB, a trend report from 49 KB to 17 KB. The pages look and work as
  before, also when opened as a local file.
- **Organic AI video: the style gallery once on the ideas page.** All 49 styles are shown once, under the ideas,
  instead of again for every idea. Each idea keeps its suggested styles and has a list to pick any other one.
- **Windows: the plugin runs on python.org's Python, signed by the Python Software Foundation.** Smart App Control
  could block the unsigned conda-forge Python the plugin used, on one machine and day and not on another. On Windows
  the plugin now installs python.org's Python 3.11.9 (its plain NuGet package: no installer, nothing in the Apps
  list, a Python you have yourself is never touched) into its own data folder, checks the file's fingerprint and
  every program's signature first, and gives each set of tools its own Python environment, with every package
  checked against its fingerprint. The first session downloads about 17 MB more, from `api.nuget.org`; the tools'
  packages come from `pypi.org` and `files.pythonhosted.org` (the voice tools also from `download.pytorch.org`).
  macOS and Linux are unchanged.
- **Creative brief: every animatic is drawn in a style matched to the concept.** Animatics are still made only
  when you ask for them, after the briefs, for the concepts you name. Each one is drawn in one of the 49 animation
  styles, picked for the concept's format: a talking head, a screen recording and a UGC phone video each get their
  own look, and a channel with its own style gets that one first. You can also name a style. The quick pencil
  sketch is gone, and a brief no longer needs a sketch scene for each beat. The brief's page shows each animatic's
  style by name, with its poster. The animatics question says how many minutes an animatic takes per concept on
  your computer, from its last render, or about 5 before the first one.
- **A decision you give in chat is saved exactly, or Claude asks again.** Every page build now lists the answers it
  takes in chat, one line per item or section, with the name the page shows. You may name an image by its name in
  the pack (`still_01`) and a track by its file (`mixkit-cat-walk-371.mp3`). A line Claude can't read, or a name that
  fits two things, stops with the list of what the page offers; nothing is saved half-empty any more.
- **Trend research: every check-in on the report's link.** The seed phrases, the category map, the picks, the
  report's approval and the weekly schedule are now asked on one page, the report's own link, which stays the same
  every week. From the moment the report is built, it is the page's content and each later question sits under it.
- **Creative brief: the intake card and the persona on the page.** Both are stages of the run's page now, with the
  persona's hypothesis next to the account's data. The brief's page later goes to the same link, with them under
  "Already settled" (only in the decision maker's and strategist's views).
- **A start card in every playbook.** Trend research, Creative brief, Refresh an ad and Create an ad now ask their
  start questions on one page, each with its default ticked, as Organic AI video does. It is the run's first page:
  every later check-in goes to the same link, with your start answers shown as settled. Answering in chat still
  works.
- **Organic AI video: the channel profile, the script draft and the pack on the page.** The profile's fields, the
  voiceover script line by line with its times (shown right after the idea is picked, before the style, voice and
  music), and the generation pack with each paid item's model and price, the total and the budget cap are now
  stages of the run page. The script draft is a new check-in: its own question at "Check every step", part of the
  plan card at "Just the big calls", and decided by rule at "Hands-off".
- **Refresh an ad: the run page builds again after the edit.** An edited video over 15 MB (a 27 s edit is about
  24 MB) is shown by its 720p preview, so the page is built and published at the edited video's check-in and every
  later one. The full video stays in the run.
- **The last version of every run's page has nothing open.** After the last decision the page is built once more:
  every decision under "Already settled", ending with "Done".
- **A decision in chat updates the page.** Once Claude records it, the page stops waiting, is built again with that
  check-in settled, and goes to the same link. No more "People are deciding on the page now" after a chat answer.
- **A brief or a video starts from the right research's picks.** Every pick trend research hands on now names its
  category and the run it came from, and `tm research seeds` stops, writing nothing, when the run names no category.
  Creative brief and Organic AI video offer the picks of the category you named; a pick from another research is
  listed apart ("From another research (use it?)", with its category and run) and used only after you say yes.
  Picks saved before this change are listed there as "category unknown".
- **Trend research: the report's name says the market, and a hook's age is TrendsMesh's.** The report page is named
  "Trend report: <category> (<market>)", so the gallery shows the market too. The "trend seen for" line takes the
  trend's age from its TrendsMesh card, as the card shows it, instead of the oldest saved video. With the weekly
  report run by hand, Claude no longer tries to finish the schedule step, which failed with "Steps are finished in
  order".
- **Start from any input.** Trend research, Organic AI video and the creative brief start from a product or site
  link, a store, a description, a product photo or a note about the client, not only a category phrase. Claude
  reads it, proposes 2 to 5 category and search phrases, and you approve or correct them; the original input is
  kept with the run. A store keeps the brand as the focus, with one phrase per product line. Competitors and an
  existing ad as the start are still "not supported yet".
- **Organic AI video: the start page is filled from the chat.** What you already told Claude (the channel, the
  bubble, the output, the links, anything else) is on the start page, marked "from the chat", and every field stays
  editable. Leaving it as it is counts as your answer.
- **Organic AI video: the idea count is a default.** The start page asks "How many ideas": by default 5, or as
  many as you need, up to 12; the proposals page holds that many. Runs started before keep their 4 to 6.
- **Organic AI video: the start page asks for your channel's own style** (for example "paper cut-out collage, flat
  colour"). It is saved in the channel profile and offered first as "Your channel's style".
- **Organic AI video: the product in any form, and each role says what it needs.** "The product" takes a link, a
  photo, a description or a few words. "Not shown" needs nothing; "incidental" and "soft mention" the product's
  name and what it does; "featured" and "hero" also a product image, taken only from your own photo or product
  page. Claude drafts the store profile with its catalogue (a SaaS product too) and saves the packshot, so picking
  a role no longer ends in "Nothing is sold (store is null)"; with nothing usable given, Claude asks once.

- **Trend research: Claude reviews at most 50 trends and 50 hooks.** Before the relevance review the plugin now
  sets the obvious cases aside: last week's dropped trends stay dropped in a weekly run, and when more than 50 trends
  are mapped, only the 50 best by match are reviewed. The rest are listed under "Set aside", on the map and on the
  report, each with its reason, and any of them comes back when you ask. Hooks work the same way: Claude scores at
  most 50, in TrendsMesh's rising order (new `tm research hook-candidates`), and the others are listed as not scored.
  A run with 300 mapped trends and 150 hooks no longer has Claude scoring every card by hand.
- **TrendsMesh calls are paced, so none hits the rate limit.** A small hook holds each TrendsMesh call until it fits
  your plan's limits (10 calls a second, 10 searches and 20 video pages a minute, or the limits TrendsMesh's usage
  check reports), so parallel fetches no longer get "Rate limit reached" and are never retried. It runs without
  Python, in about 30 ms a call. When the day's calls are spent, Claude says how many are left and when they reset.
- **Organic AI video: at most 50 hooks and formats are scored for your channel.** The best 50 by the plugin's own
  score are scored (topics keep their own 20); the rest are set aside, listed, and scored when you ask for one.
- **Pages say their sources in plain words.** The brief page and the run page no longer show trend ids, run file
  names, theme codes such as T02, or a choice's internal name. A brief row's source reads like `TrendsMesh: Rising
  hook "who said _"` or `Meta Ad Library, query "lucid dream", US`; the ids and files behind it sit in a folded
  "Technical details" under the evidence, the audience and "What the evidence changed", never in the creator view.
  `tm brief check` refuses a code or a file in anything the page shows, naming the field.
- **The run page: settled choices in words, files folded away.** "Already settled" now says "A new channel profile"
  or "Approved" (in Polish too, for Organic AI video), never `new` or `approve`. Each stage's data sources and media
  files are listed in one folded "Technical details"; a settled image or take is captioned with the item's name,
  not its file name. Claude's question on the page is refused when it shows a code or a file, or an option labelled
  with its internal name.
- **Refresh an ad: you can refresh against the diagnosis.** When the diagnosis says "the landing page" (or another
  cause outside the video) and you know better, tell Claude which part of the ad to refresh (the opening, the middle,
  the promise or call to action, or image fatigue) and why. Claude records it in your words, the run goes on with
  that part, and the briefs and the run page show the diagnosis next to your decision, with Meta's numbers unchanged.
  Every cost and test budget asked after that says the run goes against the diagnosis.
- **Refresh an ad: the ads that spent are fetched first.** Claude first asks Meta for the ads that spent in the 90
  days, biggest first, then their weekly numbers. A fetch that came back with only the ads that did not spend now
  stops with that reason, instead of a message about a missing field.
- **Refresh an ad: only your product's ads are ranked.** Each ad's link is compared with the product's landing page
  (the site and the page, never the tracking parameters). Ads of another product are listed apart and never picked;
  an ad on the same site but another page is shown for you to confirm. Ads without spend in the last 14 days are
  marked "paused".
- **Refresh an ad: "too little data" said plainly.** When none of your product's ads has the 30 results a judgement
  needs, the "Pick the ad" card says so with the best ad's numbers and asks whether to refresh one anyway; on a yes,
  you choose the part to refresh.
- **Refresh an ad: the account trend when Meta's account rows have no results.** The trend is then built from the ad
  rows, and each ad's note says so, instead of being left out with a wrong reason.
- **Refresh an ad: a diagnosis report when the run ends at the diagnosis.** The run now saves
  `04_final/diagnosis_report_v01.md`: what was checked, what the data shows, what to fix (for a landing page, what to
  check on it) and what was spent. The run page is built again with the diagnosis settled and a "Done" stage.
- **Refresh an ad: the 4:5 version whenever your formats need it.** The edited video's 4:5 version is made right after
  its render, with or without the live test, and the test reuses it.
- **Refresh an ad: the original video from any folder.** When the video isn't in your brand folder, give its path or
  drop the file into the chat; Claude copies it into the run and records where it came from (`tm record
  --copy-from`).

- **Organic video: the text fits the animation's style.** When an animation's style belongs to a family that another
  text set suits better (marker for hand-drawn and paper styles, block for explainer, data and print styles, pop for
  retro ones), the text look shows that set beside the channel's: "The channel's set is outline; for a Hand-drawn
  style, marker fits better." The saved set stays as it is. When the animation draws its own headings, the top
  overlay is off, so it no longer covers them or repeats them; you can turn it back on.
- **The cover keeps the video's text style.** A cover takes the text style you approved for the video: its set, brand
  colour and font, so the key word shows in the brand colour (no more `*` around it) and the text gets the set's box
  or outline instead of white on white.
- **Spaces between words in outlined text.** In the outline, marker, pop and karaoke overlays the outline no longer
  swallows the space between words, so "Your ad text" no longer reads as one word.
- **Create an ad: text over a face comes with its fix.** The edit's layer check now says how to clear a face ("move
  it down 184 px, or set its size to 53"), and running `tm ad text` again moves or shrinks that text by itself and
  says what it changed. A "face" that covers almost the whole frame is no longer taken for one.
- **Creative brief: an animatic's hook keeps clear of the phone and the face.** Before an animatic is rendered, a hook
  that would cover a face, the product screen or the brand's name is moved to the free place (top, centre or
  bottom), or made smaller, and Claude tells you what it changed.
- **Refresh an ad: the new text uses the brand's text set.** When the brand has a saved text set, the refreshed
  ad's new opening and ending cards, and its rebuilt captions, are drawn in it: its colours, its font, its logo on
  the ending card, and the key word in the brand colour.
- **Create an ad: every model ad from the Ad Library can be opened.** The concepts page shows each Ad Library model
  ad with its thumbnail and an "Open in the Ad Library" link to its public page, also when the Ad Library gave no
  video file.
- **Create an ad: a planned continuous take is not reported as missing cuts.** Each paid take in the storyboard now
  names the cuts its prompt asks for (none for one continuous shot), and the take's QA measures against those cuts,
  never the scene times, so a single take no longer gets "no cut near 3 s" notes.
- **Create an ad: a sharp logo for the end card.** `tm tool site brand` takes the largest version of a logo the site
  offers and prefers the brand's SVG wordmark. When the best logo is smaller than 600 px, Claude asks you for the logo
  as an SVG or a larger PNG, instead of scaling it up on the end card.
- **Create an ad: site captures without the cookie banner.** `tm tool site capture` hides the common cookie and
  consent banners (OneTrust, Cookiebot, Usercentrics and others) before it takes the picture, and says what it hid.
  For a site's own banner, add `--hide <its selector>`. When the page can't be drawn that way, it takes the plain
  capture and says so.
- **Organic AI video: topics are scored for your channel too.** Claude now scores up to 20 of the shortlist's topics
  for your channel, as it does hooks and formats. A topic that fits badly (for example "Temu product hauls" for an AI
  explainer channel) no longer takes a place among the trends whose evidence is pulled.
- **Music in one step, from your whole library.** At the style, voice and music step, Claude puts 2 to 3 free Mixkit
  tracks straight on the page, each with its licence line, with no question asked first: the track you pick is your
  yes, and it goes into the channel's music library. Free-licence tracks fetched for another of your channels are
  offered too, marked with that channel's name; a channel's own or bought tracks stay with it.
- **Create an ad: free Mixkit music works without a channel.** A track fetched in an ad run goes into the run's
  audio folder and the brand's music library, so the brand's next ad finds it, with its licence. Before the
  download, Claude says where the track will go.
- **Organic AI video: a trend you used can come back once, with a new angle.** A trend counts as used only once a
  video or a script was delivered from it; runs that were started and never finished no longer block it. The
  shortlist keeps used trends, marked. One idea per batch may build on a used trend that is still rising, saying
  what is new (topic, hook or format), and the proposals page shows which earlier video it was in.
- **Organic AI video: the channel profile stays confirmed after the voice and music picks.** Saving the picked voice
  and music into the channel profile keeps the date you confirmed it, so the next run reuses the profile without
  asking again. Any other change to the profile still asks you to confirm it, and Claude says why.
- **Organic AI video: the picked style shapes every kind of video.** A style from the library can now be picked for
  AI footage, a talking character and stills too, not only an animation. Its look (what it looks like, what it
  avoids, its colours and fonts) goes into every image and video prompt, and the plugin refuses a paid image or
  video whose prompt leaves it out, before anything is paid.
- **Organic AI video: every batch of ideas has variety.** Each idea is built on a format rising now, and no two ideas
  share a format and a production type. When your channel has its own style, at least one idea comes in another
  look, unless you say you want every idea in your channel's style. The proposals page says how many ideas are in
  your channel's style and how many in other styles.
- **Organic AI video: the Models page shows only what the video uses.** An animation shows only its voice model and
  needs no Replicate prices; stills with motion graphics show their pictures (illustrations, or photos for a
  realistic face) and the voice; AI footage shows the first frames and the video, the upscale only when the run
  upscales, and the voice only when ElevenLabs says a line. The pictures are the ones the recipe plans, not one per
  15 s, and the total holds only these tasks. `tm models ids --run R` names just the models to price.
- **Exact costs in the pack.** Each cost line is its unit price × units as it is (0.047 × 5 = 0.235), the totals are
  their exact sum, and only the total shown to you is rounded.
- **The week plan prices each video itself.** `tm organic week check` works out each idea's video cost from the
  model registry's selected models and the idea's planned length and pictures, writes it with its source and date,
  and replaces a typed cost with a note. The week page says where the costs come from.
- **A refused reference picture is never dropped without asking.** When a take that sends your approved casting or
  host picture is refused (nothing is spent), it is tried once more exactly as it was. After a second refusal
  nothing more is made until you choose: try once more, another model that takes a reference picture (priced
  first), or go without it, knowing the face will not be the one you approved.
- **Create an ad: the transcription price is dated.** `tm ad prices` also saves the Scribe transcription rate, dated
  today, so a transcription line can be priced from it.
- **Organic AI video: the voice is checked before it is paid for.** The pack check estimates the picked voice's pace
  for free, from your channel's earlier recordings with it or from its preview clip, and says where the estimate
  comes from. A voice too slow for the script is a warning inside the pack approval, with three options: cut a few
  words, a brisker voice by name, or a longer video.
- **The voiceover's characters and credits are given, not guessed.** The pack check always says the voiceover's
  characters and credits, a refused voice line names the exact line to write, and `tm organic vo-text` writes the
  text exactly as ElevenLabs gets it, so the count on the Models page, in the pack and in the recording is the same.

- **Creative brief: every concept is written up at once.** There is no "Choose the concepts" stop after the concepts
  any more: Claude writes every concept as a full brief, and the first page your team sees has them all. On it,
  each person decides per concept: Approve, Ask for changes (with a note) or Drop. A dropped concept is left out of
  the next brief version, the production views and the hand-off. Hands-off keeps every concept. With the review pack
  alone, the concepts are decided on its page the same way. Runs started earlier carry on as they are.
- **Creative brief: animatics on request.** Animatics are no longer an output chosen on the intake card. After the
  briefs are shown, Claude explains what an animatic is (a short moving storyboard of the ad, free, about a minute
  per concept and format) and asks for which concepts you want one: all, some or none. Only those are drawn, then
  the page is published again to the same link; a concept without one shows "Animatic on request". Hands-off makes
  none.
- **Creative brief: customer voice belongs to the ad brief.** The customer-voice step and its rule (CB5) are now said
  to apply to the ad brief; a brief for an organic video will have no customer-voice step.
- **Creative brief asks what the brief is for.** Its first question is whether the brief is for an ad on Meta (it
  reads your ad account) or for an organic video on a channel (no ad account needed). For an organic video the
  readiness check no longer asks for Meta Ads, and no Meta tool is called in the run. Runs started earlier are ad
  briefs, as before.
- **Creative brief: an organic video brief.** For a channel's organic videos, filmed by you, a creator or a team:
  one start card (the product or brand, the channel and its platforms, whether it is a business account, the goal,
  who films), the channel's context from its page or your description, a directional persona, the rising trends of
  the channel's bubble, and three concepts, each with its topic, hook, format, length and sound. A business account
  is offered only sounds licensed for business use; a personal account gets trending sounds with their licence
  shown. Animatics on request, as in the ad brief. The page has a creator, an editor and a new publisher view (the
  post description, hashtags, posting time and sound per platform, held to the platforms' limits) and a posting
  plan measured by views, % watched to the end, saves and shares. There is no customer-voice step and no Ad
  Library check.
- **From an organic video brief to the video.** At the end of an organic video brief, Claude asks whether
  organic-video should make one of the videos. On a yes, the concept is handed on as a seed, and an organic video
  run started from it keeps the concept's hook, format, length and sound. Both skills now say which does what: the
  brief is for the people who film, organic-video makes the video itself.
- **Creative brief ships an example brief file.** `templates/brief_pack_example.json` is a complete brief pack in
  the shape the brief check holds it to, with its plugin blocks, an ad brief and an organic video brief. Claude
  writes the run's brief from it, instead of from files that were only in the repository.
- **Creative brief: the creator view checks data, not words.** The creator view is built from the creator fields
  and each concept's one-liner and key message (what the creator conveys on camera), so hooks and ad copy are shown
  as written ("DO NOT show this to your competitors" passes) in every language alike. Its check now refuses the
  run's own account figures (spend, cost per result, results) and the advertisers seen in the Ad Library, naming the
  field and the value, in the page and in the creator PDF, the one-liner and the key message included.
- **`tm brief choose` takes a comma list.** `--drop C2,C3`, `C2, C3` and `C2 C3` all work, and so does
  `--concepts`; an error names only the ids that are not in the brief.
- **Free or Paid: you choose how the playbooks find trends.** When TrendsMesh isn't connected, a playbook asks one
  question: Paid (sign in to TrendsMesh, or the plan offer) or Free (Claude guesses the trends from what it can see,
  each guess labelled). Claude remembers the choice for the folder you work in and opens each Free run with one line
  on what TrendsMesh would add; say "connect TrendsMesh" any time. Free never starts on its own: the engine refuses a
  guess run until you chose it, and a sign-in skipped in an earlier version is asked about once. On Free the plan
  offer comes back at most once a month. The doctor shows Free as "Free mode, your choice", not as a warning.
- **Guesses say what they missed.** On Free, the notices with the direction of changes, the concepts and the ideas
  say what TrendsMesh would have shown (whether a hook is repeating across creators right now, and how early), and
  each Free run's final report ends with a short "What TrendsMesh would have changed" box about its own guesses.
- **Organic AI videos run on Free.** Without TrendsMesh, the ideas are built on trends Claude saw on trending tabs and
  public trend lists, your channel and web search, each with where it was seen and labelled a guess: no lifecycle
  stage and no number without its source, Inspire ideas only. The ideas page says so at the top and shows, for
  each idea, what TrendsMesh would add in its place. The week plan works on Free too.
- **Trend research stays Paid only,** and says why: its calls rest on what repeats across creators over time.
- **When TrendsMesh stops mid-run,** Claude says what stopped and how to get it back, and waits; going on as
  guesses needs your yes, as before.
- **The README shows Free and Paid side by side,** and why TrendsMesh sees more than Claude alone.
- **The plugin has a README of its own, with what it sends where:** every outside service it reaches, when, and what
  goes there, what each hook does, and a privacy policy link. It is the listing text for Anthropic's plugin
  directory. The plugin's description now names Create an ad too.
- **A smaller install.** The tests and the evals moved out of the plugin folder, to `tests/` and `evals/` at the
  repository root, so the plugin ships about 350 files instead of 1,700.
- **See an animation style move before you pick it, and 10 new styles.** Every animation style has a poster and a
  short loop, and there are ten new styles, among them two collage looks, a product launch, glass app screens and
  vaporwave (49 in all). Thanks to @piotr-lezon, who made the previews, the new styles and their tags. The
  ideas page and the style, voice and music page play the 2 to 3 suggested styles, each with Claude's one-line reason,
  then show every style by family: click a poster to see it move, and pick any of them instead.
- **Your channel's style comes first, every time.** The styles are suggested in a fixed order: your channel's own
  style first (the look in its profile, matched to the nearest library style, or a style you picked three times
  or more), then the styles that suit your channel's type and the topic's tone (styles that show numbers well
  first when the idea has a key number), and a style you turned down for the channel earlier last.
- **Text sets: 8 looks for the captions and the overlays, together** (by @piotr-lezon): `native` (like
  TikTok's own captions and text boxes, in TikTok Sans), `outline`, `pill`, `block`, `karaoke`, `pop`, `quiet` and
  `marker`, each a look for both text layers in the brand's colour, every animation timed from its own word. The
  overlays say what they are (the hook, a label, a key number that counts up, the CTA, the end card), and the one or
  two words that carry a line are lit. Two captions back to back no longer share a frame.
- **The text set is the channel's or the brand's, kept and used in every video.** The first time, the images
  check-in shows the three sets that fit the channel on your own words, side by side; your pick is saved beside the
  channel's or brand's profile and every later video uses it without asking (change it any time; one video can use
  another for its format). Without a saved set the default is `outline`, or `native` for a channel meant to look
  filmed in the app. The brand's own font replaces the default one in every set but `native`, the text on the
  brand's colour is dark or white by contrast, and the end card shows the brand's logo, or its name without one.
- **The hook can stay on screen for the whole video,** in every set.
- **Create an ad draws its text in the brand's text set too:** the cut is still ffmpeg's, and the captions and the
  overlays are drawn over it with the same sets as organic videos, so an ad and an organic video of a brand look
  like the same brand. The layer check still sees every caption and overlay. Create an ad now installs the video
  editing tools (Remotion) for this. Refresh an ad keeps copying the original ad's captions.
- **One list of models for every paid step (the model registry).** Which model makes which image, video, voice,
  sound or upscale, the variant it is sent with, its price and its limits now live in one file, from the owner's blind
  test of 2026-11-17, and every paid playbook reads it. Organic AI video, Create an ad and Refresh an ad show the same
  Models page: per task a budget, a suggested and a best choice with the selected one ticked, each with its price per
  unit and one sentence, and a field for your own model. Only price and availability are checked in a run, so the list
  no longer changes from run to run. Every call sends its variant (MiniMax H3 at 768P unless you choose 1080p, GPT
  Image never at the dearer "auto" quality), so the price shown is what it costs. Sound effects use ElevenLabs'
  current model, and Topaz's upscale is priced per second as Replicate bills it. Seedance 1.5 Pro, gone from
  Replicate, is gone here too; a talking person in your own or a brand voice is now Gemini Omni with the Voice Changer.
- **A model review every two weeks.** A scheduled check compares the public rankings and Replicate's and ElevenLabs'
  pages with the list and opens one issue for the owner with what is new, what changed price and what is gone.
  Nothing in the list changes without the owner's decision.
- **One path rule for run files.** Every `tm` command with `--run` reads a relative path inside the run folder,
  whatever folder it is started from, and a path written from the workspace (`runs/<playbook>/<run>/03_wip/…`)
  works too. A missing file, or a relative path to a file outside the run, stops with one clear message: give it
  relative to the run folder (`03_wip/<name>`), or as a full path. `tm ad check` and `tm organic text approve
  --style` no longer say a file that is there "is not a file in the run", and `tm page build` no longer fails on a
  relative `--run`.
- **Commands find your project folder from anywhere inside it.** `tm brand show`, `tm organic used`, `tm organic
  history` and the other commands without `--run` look up from the current folder for the workspace (the folder
  with `runs/` or `.trendsmesh/`), and a command with `--run` uses that run's workspace. "No brand profile named …"
  names the full folder it looked in.
- **Brand logos are saved once, in the run's brand folder.** `tm tool site brand` no longer writes them under a
  doubled `runs/…/runs/…` folder.
- **A Replicate spec that names a missing file stops before anything is paid.** A spec input that reads as a
  local file (an image, a clip, a sound) is found in the run folder first, else beside the spec; one that is not
  there is an error, never sent to the model as text. The organic spec check says the same.
- **JSON files saved by Windows PowerShell are read.** Files with a byte order mark (what PowerShell 5.1's
  `Out-File -Encoding utf8` writes) are accepted by `tm trends shortlist --fit` and every other command that
  reads JSON or YAML.
- **`--json` on every command.** `tm env install` and `tm report check`, `send` and `github` take `--json` too;
  `tm env install … --json` prints one object (`status`, `tier`, `message`), with the installer's own output on
  stderr.
- **`tm organic pack check --stage recipe` names the step the run is really at,** instead of always saying "D1
  can be done", also after D2.
- **The doctor tests a render before it says the video editing tools are ready.** A setup whose files are in place
  but cannot render (as when the Remotion setup stopped halfway) now shows as something Claude sets up again after
  your yes, with what failed. The test takes about a minute, once per plugin version; `tm env install video` runs
  it too, and sets Remotion up again from scratch when an earlier setup's files do not render.
- **Connections Claude has not checked yet no longer read as missing.** They show as ⏳ "checking in a moment", and
  the card still says "Ready to go"; the doctor stops (exit 2) only for something really missing.
- **"Free or Paid is your choice" shows only while you have not chosen.** With Paid saved, the TrendsMesh row says its
  own next step.
- **Each playbook names its exact output ids for the readiness check,** and a wrong name gets a hint: "Unknown output
  brief. Did you mean creative_brief?"
- **One support report, `trendsmesh-support.md`, written again each time,** so the current one is never in doubt. It
  now names the plugin version next to the engine's.
- **The doctor says which Meta ad account it checked,** by its currency and the number of accounts ("EUR; 1 of 2
  accounts checked"), on the card and in the report; never an account name or id.
- **When Claude Code's permissions refuse a step, the playbook stops and tells you.** A decision, a spending approval,
  a paid call or a page publish that auto mode (or a deny rule) blocks is no longer reworded, retried another way or
  quietly replaced by a local page: the run stops with what was blocked and why, says nothing was saved, spent or
  published, and gives the rule to add to your settings (for example `Bash(tm decide *)` or `Artifact`). Say "done"
  and it goes on from the same step. The readiness check can show shared pages as refused, with the same step.
- **A decision you make in chat keeps your own words.** `tm decide` records them as you said them (`--said`, or
  `--said-file` for long ones), next to your choice; decisions made on a page keep their own record.
- **The key guard no longer blocks regexes and notes.** In a workspace, a `.*` inside a quoted `sed` or `grep`
  pattern, a note written with a heredoc or a PowerShell here-string, and a `find` over one of your own folders (one
  with "keynote" in its path, or with `-not -path "*/.*"`) now run. `cat .env`, `cat .*`, `ls .s*`, a note that names
  `secrets.env` and a search of a workspace that holds the keys are still blocked, by the same rules as before.
- **Windows Smart App Control is named when it blocks the plugin's Python.** When Windows stops a file of the
  plugin's Python (error 4551, "An Application Control policy has blocked this file"), `tm`, the doctor and every
  playbook's readiness check stop and say what it is and what to do: update the plugin, or turn Smart App Control
  off (it can be turned back on later). Session start says it in one line instead of nothing.
- **Large answers are saved by themselves again, on Windows too.** When an answer is too large for Claude Code to
  show, the collector reads the file Claude Code saved it to in every form Claude Code 2.1.326 writes its notice
  (a count grouped with a no-break space, a file name with a suffix), and you see the usual short summary: no more
  `tm trends ingest` by hand for a search, a list or a page of videos. A Meta read or a page answer too large to show
  is saved from that file too, never as the notice. When the file can't be read, the message says which check it
  failed instead of "it is not JSON".
- **Refresh an ad saves its Meta answers by itself.** From A1 on, the collector keeps every Meta read (with
  `ads_get_ad_videos`), TrendsMesh, Ad Library and page answer of the run, and `tm r1` takes the weekly ad and account
  reads from `01_base/meta/` by the input each was fetched with, never the daily rows, and says which it took. No
  more saving each Meta page by hand.
- **Create an ad saves its trend cards by itself.** From S1 on, every `get_trend`, search, video page and Ad Library
  answer, and the page's decisions read, is saved to the run: `tm ad check concepts` finds the cards with no ingest.
- **Stills videos in any format.** A stills video is now laid out in the format the trend's own videos use (a tips
  list, a before and after, a ranking, a quiz ...), not only as a quiz or a ranking: Claude builds the layout from the
  trend's evidence like an animation, with your picked pictures in it, and it renders on your computer for free. It
  shows on the video check-in with the voiceover under it and finishes the second stage once you pick it, so a stills
  video whose pictures and voice you paid for always becomes a video. The quiz and ranking templates stay for a real
  quiz or ranking.
- **One storyboard panel per scene.** An animation's storyboard draws one panel per scene of the script, each at the
  moment its scene is complete, labelled with that scene's name; the panel files and the contact sheet always match.
  A storyboard whose scenes don't match the frames list is refused with what to fix, and `--panels` is gone (the
  count comes from the storyboard). The animation's check stills are taken at the same moments, so the video
  check-in compares the same frames as the storyboard you accepted.
- **The full animation has its own prompt.** After the storyboard is accepted, `tm organic atlas-prompt --animation
  --from <the storyboard's module>` writes the prompt for the full animation: the accepted storyboard, your notes on
  it and the video's planned length, with no "stop after the storyboard". An animation is now as long as the pack
  planned, holding its last scene until the end, rather than ending with the voiceover's last word.
- **Creative brief: no black boxes before the animatics.** A concept without an animatic shows its hook where the
  video will play, in the concept and in the three phones at the top, with "Animatic on request" while one can still
  be made. Once you skip the animatics, or in Hands-off, the hook stands alone. The PDFs show the same.
- **Trend research: the CSV buttons work on the published report.** The report is published with the `downloads`
  permission, so a CSV button saves the file instead of doing nothing.
- **Trend research: one act-now number.** The "Act now" tile and the act-now table count and list only the trends
  the report recommends, the same number as the heading. The other act-now trends stay in the list under the cards.
- **Create an ad: the image gate shows the whole batch.** A plan line of several calls shows every image of its
  latest batch side by side, each with its own accept, redo or drop, not only the last call's.
- **Create an ad: the review shows only versions that passed their check.** A version of the edit that failed
  `tm ad check edit` is never shown at the review; the newest version that passed is picked first, with what was
  checked for it.

## 0.13.1

- **Organic AI video's ideas in chat say how each video will look.** With the ideas on the run page, the chat
  card again gives every idea its look, an animation's styles each with its reason, and the risk level with the
  one risk it comes from, so an answer in chat has everything the page shows.
- **Create an ad never offers an edit that failed its check.** An edit with a caption over a face is held back
  until the fixed version passes, and the message no longer gives its path for a rough look.
- **Create an ad asks for the plan's yes even before a key is set.** The plan's page and card come first, with
  each cost and its date; a missing Replicate or ElevenLabs key is named as the step before the first paid call.
- **The README starts with a 72-second film of what the playbooks do.** Under the first paragraph, a 6-second
  preview links to the whole film, with sound and English captions.
- **Organic AI video asks what to make and approves the week on the run page.** The video ideas and the week plan
  are now stages of the one page per run, like the images, takes, final video and taste. Per idea you pick
  Produce, Maybe later or Skip, how involved to be, the output, the platforms, the taste answers, the look and a
  note, with "Produce all" and a live count with the estimated cost. Per day of the week you pick AI video or
  Script, OK or Skip, swap the idea for another from the list, and add a note, with a live budget bar: over budget
  it says so and the week cannot be approved. Once recorded, each stage shows what was decided, read-only, under
  "Already settled". Claude writes the same files as before, so starting the videos and producing the week work
  unchanged, and a week over its budget, or one idea on two days, is refused before anything is recorded.
  Answering in chat still counts, and a run that published the old proposals or week page reads it as before.
- **Organic AI video's other pages have the TrendsMesh look too.** The proposals, the week plan, the script to film,
  the intake, the models page and the week's delivery now have the run page's top bar, with an "Organic AI video"
  pill, and its colours and font, light on every screen. The old look's colours and Source Sans font are gone. Each
  page still works as before: the same choices, the same saving, and Claude reads them back the same way. A
  language translated for these pages also names the playbook in its own words.
- **Create an ad shows the talking person's options on the plan's page.** At the production plan, the page lists
  the five ways to make the person who talks: from a description, from an approved image, with your own or a brand
  voice, with the exact wording, and the fallback after a weak take. Your plan's situation comes first. Each row
  gives its model, what it needs (a description, a face, a voice sample, the lines as text) and today's price for a
  15 s take, read from Replicate. You pick the situation, and another model if you want one. Your pick goes into the
  plan, which is checked again and asks for your yes again when it changes. The fallback can only be picked once a
  review asked for it.

## 0.13.0

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
- **Create an ad prices ElevenLabs music by the second, at what ElevenLabs bills.** A music take was planned at
  about 220 credits, a price from Refresh an ad, and one 20 s take cost about 1,550 without the run noticing. The
  plan now prices music by the second for the model used, from a dated price table (`tm ad prices`), and the engine
  refuses a music take whose plan costs more than its approved line before anything is sent. When ElevenLabs doesn't
  report a take's cost, the subscription is read again after the take, then the take is booked at its length at the
  rate, so a take that costs more than approved stops the run and asks you.
- **ElevenLabs music plans have the right shape for music_v2_5.** The tool now checks the composition plan before
  the paid call: `music_v2_5` and `music_v2` take chunks, not music_v1's styles and sections, and the docs show an
  example. Before, ElevenLabs refused the plan with a 422.
- **One approved plan line can cover several calls.** A line can say `calls: 3` with a cost a call, so casting
  makes three different people from three prompts under one yes, and no fourth call runs.
- **The spend on rejected takes is kept apart.** Asking for a new take, or turning a take down for a new line,
  books what that take cost as rejected spend in the run, and `tm ad costs` shows it on its own line under each
  budget.
- **Create an ad's concepts check says which trend cards it needs.** Each TrendsMesh trend a concept uses must have
  its card saved first, and the playbook now says so at S1 with the command that saves it. The check names each
  missing `trend_<id>.json` and the step that saves it, instead of failing on cards it never asked for.
- **An unclear model name is confirmed before any money is spent on it.** When the model you name doesn't match one
  exactly ("Gemini Sequence 2.0"), Claude asks one short question ("Do you mean Seedance 2.0?") before the paid
  call, and the engine refuses the call until your answer is recorded. A paid call also runs only the model on its
  approved line.
- **The key guard lets through only the plugin's own programs.** A call could name anything under the plugin
  data folder's `envs/` and `pixi/`; now it can name only the programs the plugin installs there (pixi, the
  environments' python, ffmpeg, ffprobe, node, npm and npx, and Remotion's headless browser), by their full path,
  listed in one file, `bootstrap/guard-programs.txt`, that the guard reads on every system. A test runs every
  command the playbooks and the engine tell Claude to run through the guard, and fails when one would be blocked or
  when the engine starts a program the list doesn't name. When the guard blocks a note or a regex that only looks
  like a key store, or a search whose pattern holds a lone `/`, its message says how to rephrase it.
- **Where to set a key, as Claude Code names it.** The doctor, the playbooks and the key messages said to choose
  "configure" in `/plugin`; the menu item is `/plugin` → **Installed** → trendsmesh-playbooks → **Configure
  options**, and they now say so.
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
- **A quiet line in a take is no longer reported missing.** The take QA's local transcription could drop a whispered
  line, so Claude told you a line was missing that was in the take. It now listens to that part again, raised to the
  take's level, and a line it still can't hear is "not missing yet": Claude checks it with ElevenLabs Scribe first
  (the new `tm tool elevenlabs scribe`, about 330 credits a minute, its cost shown first) before it calls the line
  missing or suggests a paid re-take. In Create an ad and Organic AI video.
- **Cut offsets measure each cut against the nearest mark.** A take's QA compared each cut with every mark of the
  board (8.75 / 5.75 / 2.75 / 0.75 s for one cut); it now gives one offset per cut, from its nearest mark, and names
  the marks with no cut.
- **One table says which model makes the talking person in Create an ad.** The rules and the model guide used to
  disagree on the default presenter. Now one table, by situation, is in both: a person from a description (Seedance
  2.0), a specific person from an approved image (MiniMax H3), your own or a brand voice (MiniMax H3 with a voice
  sample), exact wording (Gemini Omni 1.2 Flash), and ElevenLabs with Kling Avatar only when a take looks or sounds
  wrong. The plan asks which applies before any casting, and its check holds the plan to it, unless you picked
  another model.
- **A prompting recipe for Gemini Omni 1.2 Flash.** Its inputs, what it can't take (audio, so a library voice can't
  drive its lips), its 3 to 15 s length and its Replicate prices, read on 2026-11-12.
- **One speaker, one take.** A person who speaks in two places is one take, with the cut between the places written
  into the prompt; two takes gave two slightly different faces, voices and light. The plan's check refuses two
  takes for one speaker whose lines fit one.
- **A weak voice is changed without losing the lip sync.** When the lines and their timing are right and only the
  voice is wrong, Claude offers the new `tm tool elevenlabs sts` first: ElevenLabs' Voice Changer says the take's
  own audio again in another voice and keeps its timing (about 1,000 credits a minute, its cost shown first). A new
  take is offered only when the lines are wrong.
- **No casting paid for a face Seedance can't use.** Seedance refuses a realistic face in its inputs. When the plan
  picks it for a person, Claude says so before the casting, casts the person from a description, and the plan's
  check refuses a casting line beside a Seedance take.
- **Create an ad uses the brand's own font and logo.** At the intake the plugin reads the product's site and keeps
  the fonts it uses (its own files, or the same family from Google Fonts) and its logo, and shows you both. A font
  bought for the web may not cover video, so you are asked about its licence; what the site doesn't give is asked
  for with your other files. The captions and the end card use them, not a system font or the name as plain text.
- **Create an ad keeps captions and overlays off faces and off each other.** Before you see an edit, the plugin
  checks every caption, tag, code chip and window against the faces in the shots under it and against each other,
  and the edit is fixed first when one covers a mouth or a chin, or runs under the caption band.
- **Create an ad's loudness goes through the plugin.** The edit is levelled by the plugin's own finish (free, on
  your computer): a quiet line such as a whisper is lifted where it is, the speech is evened out, and the ad lands
  at −14 LUFS with its peaks under −1.5 dBFS. An edit levelled any other way is not shown.
- **Sharp captures of your site.** Screens of the product's site are captured in your own Chrome or Edge at two or
  three times the screen's resolution, or of the one element the scene shows, so a card is never blown up and
  blurry. The edit check finds a capture drawn larger than it is.
- **A small set of sound effects, with their licence.** A whoosh, a sweep, a click, a pop and a notification from
  Mixkit (free in ads, no credit needed), fetched after your yes and kept for your next ads. Other Mixkit effects can
  be searched; one Mixkit doesn't have can be made with ElevenLabs Sound Effects, for credits, after your yes.
- **Create an ad no longer installs Remotion.** Its edit is built with the plugin's ffmpeg, so its check no longer
  asks for the video editing tools (about 0.5 GB). It now says when Chrome or Edge is missing: without one, the site's
  captures, logo and font come from you as files.
- **Trend research judges in any language whether your category uses a hook.** The report's "already used in
  your category" and "transfer" lists came from searching each hook's videos for the category's words, as whole
  words. In a language that changes word endings (Polish "makijażu", "makijażem") or has no spaces (Japanese,
  Chinese), the search missed, and a hook your category already uses was shown as a transfer. Claude now reads the
  captions of each shortlisted hook's most-viewed videos (`tm research hook-captions`) and records whether they are
  about the category, how many are, and why, in one line; `tm research hooks --file` checks that every shortlisted
  hook has that judgement. A trend's holiday is named the same way: Claude names it in the market language, with
  its date, when it reviews the map, so the seasonal guard puts a trend past its peak after Wszystkich Świętych or
  ハロウィン too, not only after the English holidays it knew. Runs made before keep their lists and still build
  their report.
- **Videos in Japanese, Korean and Chinese render faster, and other scripts keep the caption font.** For these
  languages Remotion fetched every piece of the fallback font, about 120 per weight, so a single frame took
  seconds. `tm render` now names only the pieces the on-screen text needs: a Japanese caption fetches 10 font files
  instead of 244. Greek, Japanese, Arabic and other captions whose script the caption font lacks were drawn
  entirely in Noto Sans; now the caption font draws its own letters and digits, and Noto Sans only the others.
- **The teardown can read the words it is unsure of.** An optional OCR tier (RapidOCR: free, local, about 350 MB,
  nothing to install outside the plugin, Windows included) reads the rows of the teardown's check sheet. Text found
  by edges only becomes a caption or card when words are read in it, and is dropped when none are (the edge method's
  false finds); captions that say what is spoken are marked sure, a box that cut letters off grows, and missed
  captions are added. What OCR can't settle stays on the sheet for Claude to check. It isn't installed by default:
  in Refresh an ad, Claude offers it once, at the winner breakdown, when the ad's on-screen text is to be removed or
  replaced and the teardown is unsure of it. Say no, and Claude checks the frames by eye as before.

- **No command stops on "partially initialized module" any more.** Trend research's report imported the run page at
  its top, and the run page loads every playbook's page code, so `tm tool deliver`, `tm kit`, the Organic AI video
  pages and nine other commands stopped when they were the first thing loaded. A test now loads every part of the
  engine first, on its own.
- **Organic AI video's ideas in chat say how each will look.** The "Choose what to make" message restates each
  idea's look, an animation's 2 to 3 styles with a one-line why each, and the risk level from its highest risk, as
  the ideas file and page already did.
- **An accept with a note stays an accept.** On Organic AI video's images page, a picked image with a note on it is
  recorded as the pick, the note is quoted and carried into the takes' prompts, and a redo is only offered.
- **Trend research asks about an unfinished run first**, before its readiness checks.
- **Create an ad's production plan is asked on the run page**, with each line's cost and the price's date, like
  every other check-in, even when the user says not to ask about prices.
- **Creative brief, publishing with the older tools:** the declaration is read once, before it is declared; the
  declare answer is the check.

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
