# Changelog

What changed in each version of the TrendsMesh playbooks plugin.

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
