# Channel profile vNN: <channel> (PB3 step 0, <date>)

Source: the user's intake answers (<date>). Assumptions are marked (A) and confirmed at the profile check-in. Example: `handoff/organic-video_v02/examples/<walkthrough run>/00_raw/channel_profile_v02.md` in the repository. The plugin saves it as JSON (`channel/1`, `references/brand-and-audience.md` at the plugin root); this is how it is shown on the card.

- **Channel:** <name> on <TikTok / Instagram Reels / YouTube Shorts / Facebook Reels>.
- **Account type:** creator / business. Business accounts get a commercial-library alternative instead of trending sounds.
- **Audience language:** <pl / en / …>, used for captions and speech. Pages follow the chat language.
- **Topic and bubble:** what the channel films, about what (the search bubble).
- **Channel type** (A, proposed from the channel's videos and what performed): News and explainers / How-to and education / Entertainment and skits / Music and dance / Lifestyle and vlog / Shop and product / Other (the user's one sentence about the channel). It sets how many trends of each kind are pulled: "A news channel, so topics come first."
- **Audience:** who watches (A).
- **Tone and style:** (A).
- **What performed:** 2–3 links, or "none yet".
- **Products:** <catalog with packshots and the problems they solve>, or "nothing sold".
- **Product role:** not shown / incidental / featured / soft mention / hero.
- **Output:** script to film / ready AI video / weekly pack (a later version).
  - Weekly pack only:
    - contents: scripts / videos / mix;
    - count per week;
    - posting days;
    - flexible day;
    - run day;
    - rhythm: all at once.
- **Quality tier:** budget / default (MiniMax H3) / top (Seedance 2.0).
- **Resolution:** 768P default, Pruna upscale on request.
- **Level:** Check every step / Just the big calls / Hands-off.
- **Budget:** $<n> per run (per week for the weekly pack).
- **Tools:** TrendsMesh, generation provider (Replicate; Higgsfield not supported yet), ElevenLabs, browser, shared page links, music folder; no publishing tool (you download and post).
- **Voice:**
  - narrator: ElevenLabs voice id;
  - host: image + voice description.
- **Content rules:** for sensitive niches, e.g. no real children's faces, sources for claims, no medical claims.
