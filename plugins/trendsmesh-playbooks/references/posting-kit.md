# Posting kit: organic short vertical video, best practices (as of 2026-11-06)

Use case: faceless, AI-generated dog videos posted by a DTC pet store's own channels.
Source tags `[Sx]` point to the list at the end. **T2** marks a second-tier (non-official) source. **NEW** marks a change made in 2025–2026.

## 0. Rules that apply on every platform (read first)

- **Label photoreal AI dogs on every platform.** TikTok requires a label on "realistic-looking scenes" [S1]. Meta requires disclosure of "photorealistic video" [S13]. YouTube requires it for "a realistic scene that didn't occur"; a clearly animated or fantastical style is exempt there [S19].
- **AI labels and reach.** Only YouTube addresses this directly: disclosure "alone won't limit a video's audience" [S19]. Neither TikTok nor Meta says anything about reach [S2][S14]. Two indirect effects exist:
  - **NEW:** TikTok viewers can turn AIGC down with a slider in Manage Topics (announced 2025-11-19) [S2].
  - Unlabelled realistic AI can be removed, restricted, or labelled by the platform, and penalties may follow [S1][S13][S19].
- **Originality beats volume.**
  - TikTok makes "unoriginal or reused material without anything new" ineligible for the For You feed [S1].
  - **NEW:** Facebook demotes duplicates and repeat reposters (2025-07-14) [S17 T2].
  - **NEW:** YouTube has tightened its "inauthentic content" rules for template-based, mass-produced videos (2025-07-15, clarified 2026-07-16) [S27 T2].
- **No "dog in distress, then rescued" setups.** **NEW:** YouTube names this as off-putting content that cannot earn money (2026-07) [S27 T2].
- **Engagement bait reduces reach** on Instagram [S10][S11 T2], Facebook [S18] and TikTok [S1]. Ask open questions instead.

## 1. TikTok

- **Text:**
  - Caption limit: 4,000 characters in the app [T2]; **2,200 via API** [S4].
  - Only about the first 1–2 lines show before "more" (UI observation, no official figure).
  - Search: the Creator Academy says to make the topic clear across caption, voiceover, captions and on-screen text. Keyword text that doesn't fit the video can be flagged as spam [S3].
- **Caption:** put the hook and the main search phrase in line 1, written as natural language. Find the phrases in Creator Search Insights [S3]. A good CTA is a genuine question. Content "that tries to manipulate people into… inflating likes or follows" is not eligible for For You [S1]. There is no official guidance on emoji, so use them sparingly.
- **Hashtags:**
  - Use 3–5 specific tags. The Creator Academy warns that piling on loosely related tags can hurt [S3].
  - **NEW:** some accounts see an in-app cap of 5 since 2025-08. This is unconfirmed by TikTok [S7 T2].
  - No official source supports #fyp, so it wastes a slot.
- **Cover:** in the app you pick a frame and can add text. Through the API, the only option is `video_cover_timestamp_ms` (the default is the first frame) [S4]. Best practice: a frame showing the dog's face plus 2–4 words of keyword text.
- **AI label:** turn on Post settings → "AI-generated content", or set `is_aigc=true` in the API [S4]. Content Credentials (C2PA) can trigger the label automatically [S2].
- **Sound:**
  - In the app: upload → Add sound → choose a track → Volume, which has separate sliders for original and added sound. Set the added sound to about 10–20% [T2].
  - **Business accounts only see the Commercial Music Library.** It is cleared for organic and paid use on TikTok, and some "Premium" tracks cost extra [S5].
  - The API has no music field [S4]. For a trending sound, publish to drafts with the Upload/inbox mode and add the sound in the app.
- **Product:** use the content disclosure toggle "Your brand" (`brand_organic_toggle`) [S4]. Undisclosed commercial content can lose For You eligibility [S6]. Mention the product softly ("link in bio"), and make the video a scene first, product second.

## 2. Instagram Reels

- **Text:**
  - Caption: 2,200 characters, 20 @ tags [S9].
  - About 125 characters show before "more" [T2].
  - **NEW:** public posts from professional accounts have been indexed by Google since 2025-07-10, so captions act as SEO [S32 T2].
- **Caption:** line 1 is the hook plus a plain-language keyword ("golden retriever puppy first snow").
  - Asking people to "comment a word / share / tag" to gain reach is engagement bait and won't be recommended [S11 T2, 2024-06-02].
  - Comment-keyword DM automations that serve a real purpose are acceptable [S11 T2, 2024-06-05].
  - Shares matter: Mosseri named watch time, likes and sends as the top signals, with sends weighing more for non-followers (2025-01) [S12 T2].
- **Hashtags:**
  - **NEW: hard cap of 5 per post or Reel** (announced by @creators 2025-12-18) [S8 T2].
  - The API docs still say 30 [S9]; the cap in the app wins.
  - Mosseri: hashtags help categorise a post but don't drive reach [S8 T2].
  - Use 3–5 niche tags.
- **Cover:** a custom cover is possible in the app, and via the API with `cover_url` or `thumb_offset` [S9]. **NEW:** the profile grid crops to 3:4 (since 2025-01) [S31 T2], so keep the dog's face and text centred.
- **AI label:** use the "AI info" toggle in Advanced settings, or set `is_ai_generated=true` in the API [S9]. **NEW:** Instagram is testing an optional profile-level "AI creator" label (2026-05) [T2].
- **Sound:**
  - In the app: Create → Reel → pick the video → Audio → choose a track [S33]. In the audio editor, lower the music volume and keep the original audio.
  - Business accounts get a restricted, commercial-cleared library [S34 T2].
  - The API can only name original audio (`audio_name`); it cannot attach library audio [S9].
- **Product:** product tags work in the app (Instagram Shop), but the API doesn't support shopping tags [S9]. **NEW:** you can publish a **Trial Reel** (shown only to non-followers) through the API with `trial_params` to test hooks [S9].

## 3. YouTube Shorts

- **Text:**
  - Title: **100 characters**. Description: 5,000 bytes [S21][S30].
  - The title is what viewers see in the Shorts feed, so it should carry the hook and the keyword.
  - Hashtags can go in the title or description. Up to 3 appear above the title, and more than 60 means all of them are ignored [S20].
- **Caption/description:** write 1–2 natural sentences with the keyword, then hashtags. Tags that are "misleading or unrelated" can get a video removed [S20].
- **Hashtags:** use 2–3 relevant tags. Over-tagging "may result in the removal of your video… from search" [S20]. #shorts is not required: the official upload guide doesn't mention it [S21], and Shorts are identified by vertical format and a length up to 3 minutes.
- **Thumbnail:**
  - **NEW:** custom Shorts thumbnails are rolling out to YPP creators (2026-07-24) [S25 T2], and the API has supported them via `thumbnails.set` since **2026-11-03** [S24].
  - **They don't appear in the Shorts feed**, where most views come from. They show on the channel page, the home feed and similar surfaces. The usable area is about 3:2 in the centre [S26 T2].
  - **Verdict:** generate one only if the channel is in YPP and it costs almost nothing. Otherwise, make the first frame work as the thumbnail.
- **AI label:** in the upload flow, open Attributes → "AI use" → Yes, or set `status.containsSyntheticMedia` in the API [S19][S24]. C2PA content is labelled automatically [S19].
- **Sound:**
  - In the mobile app: Shorts camera → gallery import → Sound → Volume, which balances music, original audio and voiceover [S22].
  - Shorts library tracks are "free for personal, non-commercial use" unless you are licensed [S22]. A brand should use the YouTube Audio Library or its own licensed track.
  - In a Short longer than 60 seconds, any active Content ID claim blocks the video worldwide [S23].
  - The API has no music field.
- **Product:**
  - Links in Shorts descriptions are not clickable (since 2023-08-31) [S29 T2]. Use the channel links or a "Related video" link instead.
  - Shopping product tags for your own store require YPP eligibility. Some sounds disable the shopping sticker [S28].

## 4. Facebook Reels

- **Text:** the description supports hashtags. The API allows 3–90 seconds at 9:16 [S15]. **NEW:** since 2025-06, all Facebook videos are published as Reels [T2].
- **Caption:** the same hook-plus-keyword pattern. Facebook demotes vote-, react-, share-, tag- and comment-bait [S18, 2017, still in force].
- **Hashtags:** 1–3. There is no official count.
- **Cover:** a custom cover is possible in the app and via the API [S15].
- **AI label:** use the "AI info" toggle, or set `is_ai_generated` in the API [S15]. The requirement is the same as on Instagram [S13].
- **Sound:**
  - Use the music picker in the app's Reels editor.
  - The API only lists recommendations (`/audio/recommendations`), and "Business Facebook Pages may see limited results" [S16].
  - No API parameter attaches a track.
- **Product:** original content only. Duplicates and copied content get demoted [S17 T2].

## 5. Posting time and frequency

No current official guidance is solid enough to encode. Use each platform's own analytics. On Instagram, test hooks with Trial Reels [S9].

## 6. Template: minimal posting-kit fields per platform

```yaml
common:
  video_file: 9:16, 1080x1920, MP4 H.264, AAC 48 kHz
  ai_style: photoreal | animated      # photoreal => AI label ON everywhere
  original_audio: kept | muted
  on_screen_text_keyword: "<2–4 words in first 2 s>"
  product_mention: none | soft_in_video | link_in_bio
tiktok:
  caption: "<hook + search phrase, line 1>"   # <=2200 if API
  hashtags: [3-5 specific]
  cover: {frame_ms: <int>, text: "<2-4 words>"}
  ai_generated: true|false
  content_disclosure: your_brand | none
  sound: {source: CML | original, track: "<name/url>", added_volume_pct: 10-20}
  publish_mode: direct | draft_for_in_app_sound
instagram:
  caption: "<hook line ≤125 chars + keywords>"
  hashtags: [≤5]
  cover_image: <path, safe 3:4 center>
  ai_info: true|false
  audio: {source: library | original, track: "<name>", music_volume_pct}
  trial_reel: true|false
  product_tags: [optional, in-app only]
youtube_shorts:
  title: "<≤100 chars, hook + keyword>"
  description: "<1-2 sentences + 2-3 hashtags>"
  thumbnail: <path or null>   # YPP only; not shown in Shorts feed
  ai_use: yes|no              # containsSyntheticMedia
  audio: {source: yt_audio_library | own_licensed | original, volume_pct}
  related_video_link: <url or null>
facebook_reels:
  description: "<hook + keyword + 1-3 hashtags>"
  cover_image: <path>
  ai_info: true|false
  music: {track: "<name>", volume_pct}
```

## Sources (date of publication or access)

- S1 TikTok Community Guidelines, Integrity & Authenticity, released 2026-08-25, effective 2026-09-24: https://www.tiktok.com/community-guidelines/en/integrity-authenticity
- S2 TikTok Newsroom, "More ways to spot, shape and understand AI-generated content", 2025-11-19: https://newsroom.tiktok.com/more-ways-to-spot-shape-and-understand-ai-content?lang=en
- S3 TikTok Creator Academy, "Getting discovered with Search", undated, accessed 2026-11-06 (read via search index; the page is JS-rendered): https://www.tiktok.com/creator-academy/article/Getting-discovered-with-Search
- S4 TikTok for Developers, Content Posting API, Direct Post reference, accessed 2026-11-06: https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
- S5 TikTok Ads Help, "About the Commercial Music Library", accessed 2026-11-06: https://ads.tiktok.com/help/article/commercial-music-library?lang=en
- S6 TikTok Ads Help, "About the Commercial Content Disclosure setting", accessed 2026-11-06: https://ads.tiktok.com/help/article/about-the-commercial-content-disclosure-setting-for-advertisers
- S7 T2 Social Media Today, TikTok five-hashtag limit, 2025-08-17: https://www.socialmediatoday.com/news/tiktok-implements-five-hashtag-limit-per-post/757857/
- S8 T2 Business Today, Instagram caps hashtags at 5, 2025-12-19: https://www.businesstoday.in/technology/news/story/no-more-hashtag-stuffing-instagram-limits-hashtag-usage-to-just-5-per-reel-and-post-507444-2025-12-19
- S9 Meta for Developers, IG User Media reference and Content Publishing, accessed 2026-11-06: https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media
- S10 Instagram Help, Recommendations Guidelines, accessed 2026-11-06: https://help.instagram.com/313829416281232
- S11 T2 Social Media Today, Instagram on CTAs, 2024-06-02: https://www.socialmediatoday.com/news/instagram-certain-ctas-impact-post-reach/717732/ and the clarification of 2024-06-05: https://www.socialmediatoday.com/news/instagram-clarifies-advice-on-single-word-ctas-longer-reels/718151/
- S12 T2 Social Media Today, Mosseri on ranking signals, 2025-01: https://www.socialmediatoday.com/news/instagram-shares-algorithm-insights-2025/738034/
- S13 Meta Newsroom, "Labeling AI-Generated Images on Facebook, Instagram and Threads", 2024-02-06 (updated 2025-04-01): https://about.fb.com/news/2024/02/labeling-ai-generated-images-on-facebook-instagram-and-threads/
- S14 Meta Newsroom, "Our approach to labeling AI-generated content", 2024-04-05 (updated 2024-09-12): https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/
- S15 Meta for Developers, Reels Publishing API, accessed 2026-11-06: https://developers.facebook.com/docs/video-api/guides/reels-publishing
- S16 Meta for Developers, Music Recommendations, accessed 2026-11-06: https://developers.facebook.com/docs/video-api/guides/music-recommendations
- S17 T2 Social Media Today, Facebook on unoriginal content, 2025-07-14: https://www.socialmediatoday.com/news/facebook-cracking-down-unoriginal-content-ai-replicas/753001/
- S18 Meta Newsroom, "Fighting Engagement Bait on Facebook", 2017-12-18: https://about.fb.com/news/2017/12/news-feed-fyi-fighting-engagement-bait-on-facebook/
- S19 YouTube Help, altered or synthetic content, accessed 2026-11-06: https://support.google.com/youtube/answer/14328491
- S20 YouTube Help, hashtags, accessed 2026-11-06: https://support.google.com/youtube/answer/6390658
- S21 YouTube Help, Upload Shorts, accessed 2026-11-06: https://support.google.com/youtube/answer/10059070
- S22 YouTube Help, Enhance your Shorts, accessed 2026-11-06: https://support.google.com/youtube/answer/16215842
- S23 YouTube Help, three-minute Shorts, accessed 2026-11-06: https://support.google.com/youtube/answer/15424877
- S24 YouTube Data API revision history (entries of 2024-10-30 and 2026-11-03): https://developers.google.com/youtube/v3/revision_history
- S25 T2 Tubefilter, custom Shorts thumbnails, 2026-07-24: https://www.tubefilter.com/?p=193294
- S26 T2 PPC Land, Creator Insider on Shorts thumbnails, 2026-07-25: https://ppc.land/youtube-ends-2-year-wait-for-shorts-thumbnails-but-blocks-a-b-testing/
- S27 T2 TechCrunch, YouTube clarifies inauthentic content, 2026-07-20: https://techcrunch.com/2026/07/20/youtube-clarifies-policies-around-ai-slop-and-upsetting-videos/
- S28 YouTube Help, selling your own products in Shorts, accessed 2026-11-06: https://support.google.com/youtube/answer/13383309
- S29 T2 PhoneArena, Shorts links no longer clickable, 2023-08: https://www.phonearena.com/news/youtube-shorts-blocks-clickable-links_id149677
- S30 YouTube Data API, videos resource (title and description limits): https://developers.google.com/youtube/v3/docs/videos
- S31 T2 Planoly, Instagram vertical grid, updated 2025-10: https://www.planoly.com/blog/guide-to-instagrams-new-vertical-grid
- S32 T2 ContentGrip, Instagram searchable on Google, 2025-07: https://www.contentgrip.com/instagram-searchable-on-google/
- S33 Instagram Help, "What audio you can use in your reel": https://help.instagram.com/329208821595430 and the Instagram blog on adding music: https://about.instagram.com/blog/tips-and-tricks/how-to-add-music-to-instagram-reels
- S34 T2 Soundstripe, Instagram music library for business accounts: https://www.soundstripe.com/blogs/instagram-music-library
- T2 without a number: the TikTok 4,000-character in-app limit, TikTok volume sliders, Instagram's 125 visible characters, Instagram's "AI creator" label (Engadget, 2026-05) and Facebook "all videos are Reels" (Tubefilter, 2025-06-17) come from several second-tier outlets that agree with each other.
