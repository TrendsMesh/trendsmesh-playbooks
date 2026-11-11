# Changelog

What changed in each version of the TrendsMesh playbooks plugin.

## Unreleased

- **Developed in the open.** Issues, changes and releases now happen in this repository; release candidates come
  before each release (RELEASING.md).

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
