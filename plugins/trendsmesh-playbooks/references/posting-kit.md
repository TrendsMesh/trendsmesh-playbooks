# Posting kit: organic short vertical video, best practices (as of 2026-11-12)

Use case: any channel that posts short vertical videos made with the plugin: a creator's own channel, an education
channel, or a shop's brand channel. The video may be AI-generated (photoreal or clearly animated) or filmed by a
person from a script. The examples below mix the three on purpose: copy the pattern, never the example's topic.

Source tags `[Sx]` point to the list at the end. **T2** marks a second-tier (non-official) source. **NEW** marks a
change made in 2025–2026.

**The limits `tm kit check` holds a kit to** are in `data/organic-video/platform_rules.yaml`, each with its source
and the day it was checked there. That file and this document carry the same date. A kit records the date of the
rules its writer read as `rules_read` (`"2026-11-12"`), and `tm kit check` refuses a kit without it. When this date
is older than about 3 months, `tm kit check` warns: check every limit against its source again.

## 0. Before writing a kit (read first)

- **The kit is what the user pastes, and what they do at posting.** The delivery page shows, per platform:
  - **TikTok, Instagram, Facebook: one description to paste, with the hashtags in it.** Write the caption and the
    hashtags; the page joins them (the hashtags after a blank line) and the limits are checked on that text.
  - **YouTube: the title, the description (with 2 to 3 hashtags) and the tags**, each pasted on its own.
  - **At posting**: the cover, the AI label, the sound and the product, as steps in plain words, never as text to
    copy. Write what to do, e.g. "Pick the frame at 3 s as the cover and add the words “Fix a wobbly table”", "If
    you add a trending sound in the app, turn it down under the voiceover", "Turn on the AI-generated content
    setting before you post". Never a bare value such as "voiceover and music".
- **The search phrase comes from the run's trend data**: the hook's or the topic's own words, as the proposal has
  them (its title and beats), never a guess. Record it as `search_phrase`; TikTok's first line leads with it word
  for word. The page tells the user to look it up in TikTok's Creator Search Insights [S3] before posting, and to
  use the words people really search if they differ. Examples: "how volcanoes erupt" (education), "sourdough
  starter for beginners" (creator), "linen duvet cover care" (shop).
- **The AI label goes by the production type**:
  - **Photorealistic scenes** (a person, animal, place or event that looks real, an AI host): **on, on every
    platform**, with the in-app step on each. TikTok requires a label on "realistic-looking scenes" [S1]. Meta
    requires disclosure of "photorealistic video" [S13]. YouTube requires it for a realistic scene that didn't
    occur [S19]. An AI human host always needs it.
  - **A clearly animated style** (cartoon, drawn, motion graphics, stylised animation): **off by default**. YouTube
    exempts clearly unrealistic or animated content [S19]; TikTok's and Meta's rules name realistic content
    [S1][S13]. The user can switch it on: the kit then says so in `plugin.ai_label_request`, with their words.
  - **A mix** (an animation with photoreal shots): on.
  - **Filmed by a person** (a script to film): no label, unless AI made what was filmed look like something real.
  - `tm kit check` checks the label against the run's production type (the checked pack).
- **AI labels and reach.** Only YouTube addresses this directly: disclosure "alone won't limit a video's audience"
  [S19]. Neither TikTok nor Meta says anything about reach [S2][S14]. Two indirect effects exist:
  - **NEW:** TikTok viewers can turn AIGC down with a slider in Manage Topics (announced 2025-11-19) [S2].
  - Unlabelled realistic AI can be removed, restricted, or labelled by the platform, and penalties may follow
    [S1][S13][S19].
- **Originality beats volume.**
  - TikTok makes "unoriginal or reused material without anything new" ineligible for the For You feed [S1].
  - **NEW:** Facebook demotes duplicates and repeat reposters (2025-07-14) [S17 T2].
  - **NEW:** YouTube has tightened its "inauthentic content" rules for template-based, mass-produced videos
    (2025-07-15, clarified 2026-07-16) [S27 T2].
- **No staged peril.** A person, child or animal in distress and then rescued is off-putting content that cannot earn
  money on YouTube (**NEW**, 2026-07) [S27 T2].
- **Engagement bait reduces reach** on Instagram [S10][S11 T2], Facebook [S18] and TikTok [S1]. Ask one genuine
  question instead ("Which experiment should we try next?", "What would you bake with it?").
- **No links, no domains and no sources in any post text** (the plugin's rule, OV11): links go on the channel page,
  sources stay in the pack or the script's fact check.

## 1. TikTok

- **Text:**
  - Caption limit: **2,200 UTF-16 characters through the Content Posting API** [S4] (an emoji outside the basic
    plane counts 2); 4,000 characters in the app [T2]. The kit keeps to 2,200, hashtags included.
  - Only about the first 1–2 lines show before "more" (UI observation, no official figure).
  - Search: the Creator Academy says to make the topic clear across caption, voiceover, captions and on-screen text.
    Keyword text that doesn't fit the video can be flagged as spam [S3].
- **Caption:** line 1 is the hook and the search phrase, as natural language ("How volcanoes erupt, in 30
  seconds"). A good CTA is a genuine question. Content "that tries to manipulate people into… inflating likes or
  follows" is not eligible for For You [S1]. There is no official guidance on emoji, so use them sparingly.
- **Hashtags:**
  - Use 3–5 specific tags. The Creator Academy warns that piling on loosely related tags can hurt [S3].
  - **NEW:** accounts see an in-app cap of 5 since 2025-08. This is unconfirmed by TikTok [S7 T2].
  - No official source supports #fyp, so it wastes a slot.
- **Cover:** in the app you pick a frame and can add text. Through the API, the only option is
  `video_cover_timestamp_ms` (the default is the first frame) [S4]. Best practice: a frame with the subject (a face,
  the result, the product in use) plus 2–4 words of keyword text.
- **AI label:** after Next, tap More options (…) and turn on "AI-generated content" [S39], or set `is_aigc=true` in
  the API [S4]. TikTok requires it for realistic AI images, audio or video and says turning it on doesn't affect
  distribution [S39]. Content Credentials (C2PA) can trigger the label automatically [S2][S39].
- **Sound:**
  - In the app: upload → Add sound → choose a track → Volume, which has separate sliders for original and added
    sound. Set the added sound to about 10–20% [T2].
  - **Business accounts only see the Commercial Music Library.** It is cleared for organic and paid use on TikTok,
    and some "Premium" tracks cost extra [S5].
  - The API has no music field [S4]. For a trending sound, publish to drafts with the Upload/inbox mode and add the
    sound in the app.
- **Product:** use the content disclosure toggle "Your brand" (`brand_organic_toggle`) [S4] when the product is
  shown. Undisclosed commercial content can lose For You eligibility [S6]. Mention the product softly, and make the
  video a scene first, product second.

## 2. Instagram Reels

- **Text:**
  - Caption: **2,200 characters, 20 @ tags** [S9].
  - About 125 characters show before "more" [T2].
  - **NEW:** public posts from professional accounts have been indexed by Google since 2025-07-10, so captions act
    as SEO [S32 T2].
- **Caption:** line 1 is the hook plus a plain-language keyword ("sourdough starter for beginners", "photosynthesis
  in one minute", "how to wash a linen duvet cover").
  - Asking people to "comment a word / share / tag" to gain reach is engagement bait and won't be recommended
    [S11 T2, 2024-06-02].
  - Comment-keyword DM automations that serve a real purpose are acceptable [S11 T2, 2024-06-05].
  - Shares matter: Mosseri named watch time, likes and sends as the top signals, with sends weighing more for
    non-followers (2025-01) [S12 T2].
- **Hashtags:**
  - **NEW: at most 5 per post or reel**: the Help Center states the cap [S35] (announced by @creators 2025-12-18
    [S8 T2]). The Graph API page still says 30 [S9]; the cap wins.
  - Mosseri: hashtags help categorise a post but don't drive reach [S8 T2].
  - Use 3–5 niche tags.
- **Cover:** a custom cover is possible in the app, and via the API with `cover_url` or `thumb_offset` [S9]. **NEW:**
  the profile grid crops to 3:4 (since 2025-01) [S31 T2], so keep the subject and the text centred.
- **AI label:** use the "AI info" toggle in Advanced settings, or set `is_ai_generated=true` in the API [S9].
  **NEW:** Instagram is testing an optional profile-level "AI creator" label (2026-05) [T2].
- **Sound:**
  - In the app: Create → Reel → pick the video → Audio → choose a track [S33]. In the audio editor, lower the music
    volume and keep the original audio.
  - Business accounts get a restricted, commercial-cleared library [S34 T2].
  - The API can only name original audio (`audio_name`); it cannot attach library audio [S9].
- **Product:** product tags work in the app (Instagram Shop), but the API doesn't support shopping tags [S9].
  **NEW:** you can publish a **Trial Reel** (shown only to non-followers) through the API with `trial_params` to
  test hooks [S9].

## 3. YouTube Shorts

- **Text:**
  - Title: **100 characters**, no `<` or `>` [S30].
  - Description: **5,000 bytes** through the API (a Polish or other accented letter counts 2), no `<` or `>` [S30];
    Studio's help says 5,000 characters [S36]. The kit keeps to 5,000 bytes.
  - Tags: **500 characters for the whole list**, the commas between tags counted, and a tag with a space counted
    with the quotes YouTube puts around it ("Foo-Baz" is 7, "Foo Baz" 9) [S30].
  - The title is what viewers see in the Shorts feed, so it carries the hook and the keyword.
  - Hashtags can go in the title or description. Up to 3 appear by the title, and more than 60 means all of them
    are ignored [S20].
- **Description:** write 1–2 natural sentences with the keyword, then 2–3 hashtags. Tags that are "misleading or
  unrelated" can get a video removed [S20].
- **Tags:** a few phrases people search for: the topic, the search phrase, a broader one ("volcano", "how volcanoes
  erupt", "earth science"). YouTube says tags play a minimal role in discovery, useful mostly for words often
  misspelled [S38]: keep them few and exact. The page shows them comma-separated, as Studio takes them.
- **Hashtags:** use 2–3 relevant tags. Over-tagging "may result in the removal of your video… from search" [S20].
  #shorts is not required: the official upload guide doesn't mention it [S21], and Shorts are identified by vertical
  format and a length up to 3 minutes.
- **Thumbnail:**
  - **NEW:** custom Shorts thumbnails are rolling out to YPP creators (2026-07-24) [S25 T2], and the API has
    supported them via `thumbnails.set` since **2026-11-03** [S24].
  - **They don't appear in the Shorts feed**, where most views come from. They show on the channel page, the home
    feed and similar surfaces. The usable area is about 3:2 in the centre [S26 T2].
  - **Verdict:** generate one only if the channel is in YPP and it costs almost nothing. Otherwise, make the first
    frame work as the thumbnail.
- **AI label:** in the Studio upload flow, Attributes → "AI use" → Yes, or set `status.containsSyntheticMedia` in the
  API [S19][S24]. Non-realistic content (a fully animated video) needs no disclosure [S19]. C2PA content is labelled
  automatically [S19].
- **Sound:**
  - In the mobile app: Shorts camera → gallery import → Sound → Volume, which balances music, original audio and
    voiceover [S22].
  - Shorts library tracks are "free for personal, non-commercial use" unless you are licensed [S22]. A brand or a
    shop should use the YouTube Audio Library or its own licensed track.
  - In a Short longer than 60 seconds, any active Content ID claim blocks the video worldwide [S23].
  - The API has no music field.
- **Product:**
  - Links in Shorts descriptions are not clickable (since 2023-08-31) [S29 T2]. Use the channel links or a "Related
    video" link instead.
  - Shopping product tags for your own store require YPP eligibility. Some sounds disable the shopping sticker
    [S28].

## 4. Facebook Reels

- **Text:** the description supports hashtags; Facebook documents no length for a Reel's description [S15]. The API
  allows 3–90 seconds at 9:16 [S15]. **NEW:** since 2025-06, all Facebook videos are published as Reels [T2].
- **Caption:** the same hook-plus-keyword pattern, short. Facebook demotes vote-, react-, share-, tag- and
  comment-bait [S18, 2017, still in force].
- **Hashtags:** 1–3, each one word with no spaces or punctuation [S37]. Facebook gives no count, so 1–3 is the
  plugin's.
- **Cover:** a custom cover is possible in the app and via the API [S15].
- **AI label:** use the "AI info" toggle, or set `is_ai_generated` in the API [S15]. The requirement is the same as
  on Instagram [S13].
- **Sound:**
  - Use the music picker in the app's Reels editor.
  - The API only lists recommendations (`/audio/recommendations`), and "Business Facebook Pages may see limited
    results" [S16].
  - No API parameter attaches a track.
- **Product:** original content only. Duplicates and copied content get demoted [S17 T2].

## 5. Posting time and frequency

No current official guidance is solid enough to encode. Use each platform's own analytics. On Instagram, test hooks
with Trial Reels [S9].

## 6. The kit's fields

The kit is `04_final/kits/<id>_kit_vNN.json` (`engine/src/tm/schemas/pb3_kit.schema.json`), in the audience
language. `tm kit check` reads these fields and warns about any other (nothing shows or checks it):

```yaml
id, version, date, channel, language, video      # the video's file: 04_final/<id>_final_vNN_upload.mp4
rules_read: "2026-11-12"                          # the date of this document, which the writer read
search_phrase: "<the hook's or topic's own words>" # TikTok's line 1 leads with it
cover: {file, frame_sec, text}                    # text: 2-7 words of keyword text
product: "<level, or none>"
platforms:
  tiktok | instagram | facebook:
    caption: "<hook + search phrase in line 1; one genuine question at most>"
    hashtags: ["#…"]                              # TikTok 3-5, Instagram at most 5, Facebook 1-3
    cover | ai_label | sound | product: "<a step at posting, in plain words>"
  youtube:
    title: "<at most 100 characters, hook + keyword>"
    description: "<1-2 sentences>"                # plus 2-3 hashtags, in it or in hashtags
    hashtags: ["#…"]                              # optional: joined to the description
    tags: ["<topic>", "<search phrase>", "<broader phrase>"]   # at most 500 as YouTube counts
    cover | ai_label | sound | product: "<a step at posting>"
plugin:
  ai_label: true | false                          # by the production type (section 0)
  ai_label_request: "<the user's words>"          # only when they asked for the label on an animation
  trending_sound: {name, evidence, replaces_track} | null
  business_alternative: "<a commercial-library track>" | null
  platforms: [ticked platforms]
  youtube_thumbnail: true | false
```

## Sources (date of publication or access)

- S1 TikTok Community Guidelines, Integrity & Authenticity, released 2026-08-25, effective 2026-09-24: https://www.tiktok.com/community-guidelines/en/integrity-authenticity
- S2 TikTok Newsroom, "More ways to spot, shape and understand AI-generated content", 2025-11-19: https://newsroom.tiktok.com/more-ways-to-spot-shape-and-understand-ai-content?lang=en
- S3 TikTok Creator Academy, "Getting discovered with Search", undated, accessed 2026-11-06 (read via search index; the page is JS-rendered): https://www.tiktok.com/creator-academy/article/Getting-discovered-with-Search
- S4 TikTok for Developers, Content Posting API, Direct Post reference (last updated 2026-10-27), accessed 2026-11-12: https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
- S5 TikTok Ads Help, "About the Commercial Music Library", accessed 2026-11-06: https://ads.tiktok.com/help/article/commercial-music-library?lang=en
- S6 TikTok Ads Help, "About the Commercial Content Disclosure setting", accessed 2026-11-06: https://ads.tiktok.com/help/article/about-the-commercial-content-disclosure-setting-for-advertisers
- S7 T2 Social Media Today, TikTok five-hashtag limit, 2025-08-17: https://www.socialmediatoday.com/news/tiktok-implements-five-hashtag-limit-per-post/757857/
- S8 T2 Social Media Today, Instagram's new limits on hashtag use, 2025-12-18: https://www.socialmediatoday.com/news/instagrams-implementing-new-limits-on-hashtag-use/808309/
- S9 Meta for Developers, IG User Media reference and Content Publishing, accessed 2026-11-12: https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media
- S10 Instagram Help, Recommendations Guidelines, accessed 2026-11-06: https://help.instagram.com/313829416281232
- S11 T2 Social Media Today, Instagram on CTAs, 2024-06-02: https://www.socialmediatoday.com/news/instagram-certain-ctas-impact-post-reach/717732/ and the clarification of 2024-06-05: https://www.socialmediatoday.com/news/instagram-clarifies-advice-on-single-word-ctas-longer-reels/718151/
- S12 T2 Social Media Today, Mosseri on ranking signals, 2025-01: https://www.socialmediatoday.com/news/instagram-shares-algorithm-insights-2025/738034/
- S13 Meta Newsroom, "Labeling AI-Generated Images on Facebook, Instagram and Threads", 2024-02-06 (updated 2025-04-01): https://about.fb.com/news/2024/02/labeling-ai-generated-images-on-facebook-instagram-and-threads/
- S14 Meta Newsroom, "Our approach to labeling AI-generated content", 2024-04-05 (updated 2024-09-12): https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/
- S15 Meta for Developers, Reels Publishing API, accessed 2026-11-12: https://developers.facebook.com/docs/video-api/guides/reels-publishing
- S16 Meta for Developers, Music Recommendations, accessed 2026-11-06: https://developers.facebook.com/docs/video-api/guides/music-recommendations
- S17 T2 Social Media Today, Facebook on unoriginal content, 2025-07-14: https://www.socialmediatoday.com/news/facebook-cracking-down-unoriginal-content-ai-replicas/753001/
- S18 Meta Newsroom, "Fighting Engagement Bait on Facebook", 2017-12-18: https://about.fb.com/news/2017/12/news-feed-fyi-fighting-engagement-bait-on-facebook/
- S19 YouTube Help, "Disclosing use of GenAI content", accessed 2026-11-12: https://support.google.com/youtube/answer/14328491
- S20 YouTube Help, hashtags, accessed 2026-11-12: https://support.google.com/youtube/answer/6390658
- S21 YouTube Help, Upload Shorts, accessed 2026-11-06: https://support.google.com/youtube/answer/10059070
- S22 YouTube Help, Enhance your Shorts, accessed 2026-11-06: https://support.google.com/youtube/answer/16215842
- S23 YouTube Help, three-minute Shorts, accessed 2026-11-06: https://support.google.com/youtube/answer/15424877
- S24 YouTube Data API revision history (entries of 2024-10-30 and 2026-11-03): https://developers.google.com/youtube/v3/revision_history
- S25 T2 Tubefilter, custom Shorts thumbnails, 2026-07-24: https://www.tubefilter.com/?p=193294
- S26 T2 PPC Land, Creator Insider on Shorts thumbnails, 2026-07-25: https://ppc.land/youtube-ends-2-year-wait-for-shorts-thumbnails-but-blocks-a-b-testing/
- S27 T2 TechCrunch, YouTube clarifies inauthentic content, 2026-07-20: https://techcrunch.com/2026/07/20/youtube-clarifies-policies-around-ai-slop-and-upsetting-videos/
- S28 YouTube Help, selling your own products in Shorts, accessed 2026-11-06: https://support.google.com/youtube/answer/13383309
- S29 T2 PhoneArena, Shorts links no longer clickable, 2023-08: https://www.phonearena.com/news/youtube-shorts-blocks-clickable-links_id149677
- S30 YouTube Data API, videos resource (title, description and tags limits), accessed 2026-11-12: https://developers.google.com/youtube/v3/docs/videos
- S31 T2 Planoly, Instagram vertical grid, updated 2025-10: https://www.planoly.com/blog/guide-to-instagrams-new-vertical-grid
- S32 T2 ContentGrip, Instagram searchable on Google, 2025-07: https://www.contentgrip.com/instagram-searchable-on-google/
- S33 Instagram Help, "What audio you can use in your reel": https://help.instagram.com/329208821595430 and the Instagram blog on adding music: https://about.instagram.com/blog/tips-and-tricks/how-to-add-music-to-instagram-reels
- S34 T2 Soundstripe, Instagram music library for business accounts: https://www.soundstripe.com/blogs/instagram-music-library
- S35 Instagram Help, hashtags (at most 5 per post), accessed 2026-11-12: https://help.instagram.com/351460621611097
- S36 YouTube Help, edit video settings (title and description in Studio), accessed 2026-11-12: https://support.google.com/youtube/answer/57404
- S37 Facebook Help, how to use hashtags, accessed 2026-11-12: https://www.facebook.com/help/587836257914341
- S38 YouTube Help, add tags to your videos, accessed 2026-11-12: https://support.google.com/youtube/answer/146402
- S39 TikTok Support, "About AI-generated content", accessed 2026-11-12: https://www.tiktok.com/support/faq_detail?id=7636670084747893268
- T2 without a number: the TikTok 4,000-character in-app limit, TikTok volume sliders, Instagram's 125 visible characters, Instagram's "AI creator" label (Engadget, 2026-05) and Facebook "all videos are Reels" (Tubefilter, 2025-06-17) come from several second-tier outlets that agree with each other.
