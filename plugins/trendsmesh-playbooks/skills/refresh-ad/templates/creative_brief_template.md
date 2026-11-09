# Template: creative brief (shared by all playbooks)

**A creative brief describes all the changes that must be made in the video.** It must be enough for every executor (content creators, camera operators, editors, voice artists, the person handling AI generation) to do their part without follow-up questions. The brief is built from the run's **change register**: each change is one card, with a type from the catalog, an assigned executor and a justification in data.

The scope depends on the run: sometimes it is a single caption change for the editor (example: `runs/01-refresh-ad/2026-11-02_ad3-dry-run/04_final/creative_brief.md`), sometimes new shots to record, a new voiceover and a re-edit of the whole video.

---

## Brief structure
1. **Goal and diagnosis:** what the video is to achieve and why we are changing it, in 2–3 sentences with numbers (e.g. cost per purchase peak → now).
2. **Source material:** file(s), parameters (resolution, fps, length, audio), whether the captions are burned-in, whether a better or cleaner source exists (project, clean clips, higher resolution), the agent's reference version (if one was produced).
3. **Executors and scope:** a "role → which changes → what they receive → what they deliver" table. Roles: content creator (performance, speaking to camera), operator (shooting the shots), editor, voice artist, AI generation, graphic designer. For each role, a list of card IDs.
4. **Changes:** cards according to the type catalog, in the order of the video timeline.
5. **No changes:** an explicit list of what not to touch (verified elements of the winner).
6. **References:** evidence videos from trends (link, views, *what to take from them*) + the note "reference only, not material for the ad".
7. **Deliverables:** files from each role (raw footage, audio, render), names, formats, aspect ratio versions, a clean version without captions.
8. **QA checklist:** yes/no checkable items, including lessons from previous runs.
9. *(HITL)* **Approvals and costs:** changes requiring consent (paid generations, shooting day, creator, voice artist, music license).

## Fields common to every change card
| Field | Description |
|---|---|
| ID, type, **executor** | e.g. `C1 · TEXT_OVERLAY · editor` |
| Time | from–to (s and frames) in the target video; for new shots, the position in the sequence |
| Was → to be | the current and target state, concretely (verbatim text, shot description, script) |
| **Why (data)** | source + numbers: TrendsMesh (trend, status, creators, views, sub-pattern), Meta (metrics, buyer demographics), Ad Library (saturation). No data, no change. A change without TrendsMesh data says so: "Guess: <what it rests on, e.g. the account's own winner, an Ad Library ad>" |
| Consistency with image and narrative | consistent · setup and payoff · deliberate contradiction (with justification) |
| How to execute | specification by type (below) |
| Change QA | how to check that it was done correctly |

## Change type catalog and type-specific fields

**NEW_SHOT** (recording: creator and/or operator)
- Action and performance (what the person does, says, what emotion), framing (shot size, angle, lens), camera movement, lighting, location, person (gender, age, look: matched to the data on buyers), wardrobe, props (the product!), length, number of takes, on-set sound, visual reference, delivery method (raw files, file names).

**VOICEOVER / DIALOGUE** (creator, voice artist or TTS)
- Verbatim script with times and an "own words" version with the points that must be said; voice (gender, age, tone, pace), language, source (recording or TTS: provider and voice), synchronization with the image and captions.

**TEXT_OVERLAY** (editor or graphic designer)
- Old overlay: text, **full lifecycle in frames** (with entry and exit animation), outline, semi-transparent elements (bars, shadows), whether it touches the frame edge.
- New text: verbatim, with line breaks; font, size (at the source resolution), colors (hex), position (px), animation or none, time.
- Method, in order: clean footage → caption removal (inpainting) → covering text card (static, full cycle + frame margin; full width when the overlay touches the edge) → reframing. UI safe zones.

**CUT** (editor)
- In and out points, new order (sequence table), target length, transitions (hard cuts by default), music editing (to the beat, audio crossfade).

**INSERT** (editor)
- Source file + in and out, position on the timeline, cropping, transition (**no dissolves over covered captions**), muting the insert's audio.

**AI_GENERATION** (agent or AI operator)
- Model, prompt, negative prompt, reference images, start and end frame (matching the neighboring shots), length, aspect ratio, number of variants, **estimated cost and approval status**.

**MUSIC / SFX** (editor)
- Track (source + **advertising license**), entry points, levels (dB relative to the voiceover), effects and their times. Trending sounds from TikTok: only with a license.

**DIALOGUE_CAPTIONS** (editor)
- Transcription, style (font, size, color, background), burned-in or as a file, max number of characters per line.

**FORMAT / COLOR** (editor)
- Aspect ratio versions (9:16, 4:5, 1:1) with framing decisions, color correction (reference), resolution, bitrate.

**CTA / END CARD** (editor or graphic designer)
- Text, product element (cover, price, offer), duration, consistency with the landing page.

## Generation rules (for the agent)
- One change in the register = one card with an executor; no justification in data = the change does not enter the brief.
- Section 3 (executors) is always present, even with a single role: everyone immediately sees what is theirs.
- In HITL mode the brief is shown for approval **before** it is handed to the executors.
- Take numbers, times and positions from measurements in `03_wip/breakdown/` and `03_wip/qa/`, not by eye.
- The agent's reference version (e.g. a Remotion render) is a preview, but describe the changes so that they can be executed from scratch in any tool.
