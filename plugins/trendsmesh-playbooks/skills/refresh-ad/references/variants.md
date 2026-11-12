# Variants by material, the change catalogue, flow V and captions

Copied verbatim from the handoff's `VARIANTS.md` (handoff v03, sections 1 to 4a; v03 adds the re-cut
rows of section 3 and sections 3b and 3c). **What the plugin does:** only the edits that `tm
changes` lists (the design's supported-changes catalogue, in `data/supported_changes.yaml`): a new
opening text card, a new first voiceover line in the same voice with recreated captions (flow V),
a new ending card, an AI video with a new look, the re-cuts of a fading or structurally weak
middle (path C-R, `recut.md`: shorter cuts, a speed-up, a 6 s bumper, a scene reorder, proof
inserted, a new or regenerated shot, a bridging voiceover line, with their music), a 4:5 version
(R6) and the copy and thumbnail decision (R7). Text cards and off-screen voiceover with captions
get every change; a talking head gets the re-cuts only. Still not supported, said plainly as
"isn't supported yet": lip-sync or any new speech on camera, a new speaker, static graphics, a
cut or reorder inside one continuous shot at level 0 (the shot is regenerated at level 4
instead), and the other rows marked ❌ outside that list (video-to-video, dubbing, a whole new
voice). Gate V2 (voice rights) is replaced by the one confirmation at intake. V6 (talking head) is
not supported: no new line is spoken on camera. Where the text says "gate", the plugin says
"check-in"; "HITL" and "AUTO" are the levels as in `rules.md`.

Read the older rows with 3c, which came last and wins: music edited on the beat grid (3's
"replacing the music" row, 3b's level 0) is never the final music, and `tm recut check` refuses
it unless the edit list is marked a draft. 3b's "~$0.65 / shot" is a 6 s clip from one start
frame; the first + last frame shot the plugin makes is Veo 3.1 Fast at $0.80 per 8 s.

## 1. The source material decides the flow

Review of the ads in the client's ad folder (faster-whisper transcription and frames):

| Material type | Example | What complicates editing | Test status |
|---|---|---|---|
| No speech, text on text cards, music | ad_3 | old text cards must be covered (solved: `fullBleed` card) | ✅ tested |
| Off-screen VO over b-roll, word-by-word captions | VO ad PL (1), (2), 202609240917 | new VO text means new captions; the old captions sit on the image, not on a bar | ❌ |
| Talking head (a person speaks to camera), word-by-word captions | ad_1, ad_2 | changing the words means the lip movement no longer matches; captions on the face and body | ❌ |
| Static graphic, carousel | none in the sample | different tools (GPT Image edit), different metrics | ❌ |

The account's ElevenLabs history (last 5000 generations, 8 voices, mostly English) **contains none of the scripts of these ads**. The voices come from outside the account, probably from Veo native audio or another tool. This is exactly the "we do not know which voice it was" case.

## 2. Diagnosis from data → type of change

The change follows from which funnel stage is fading (daily data from Meta MCP, peak window vs now):

| Symptom in the data | What is fading | Type of change | Executor |
|---|---|---|---|
| Start-of-video view rate falls (3-sec plays / impressions, ad set level; at ad level p25 / impressions) | hook | hook text, first shot, first VO line, cold open | editor, AI, voice artist |
| Hook holds, a conditional middle step falls (p50/p25, p75/p50, p95/p75; `PLAYBOOK.md` R2, amended 2026-11-06) | middle | pacing, shortening (15 s, 6 s), reordering scenes, stronger proof in the middle | editor |
| Retention OK, CTR falls | promise / CTA | promise text card, CTA, on-screen offer, VO ending | editor, voice artist |
| CTR OK, conversion falls (results / clicks) | landing page or offer | **do not change the creative**; flag it in the brief as a problem outside the video | marketer |
| Everything falls proportionally, frequency rises | audience fatigue with the same image | new aesthetic with the same message (like variant C), new creator, new format | AI, creator |
| Only CPM rises | auction and season | no creative change; observation | — |

For Ad 3 we assumed the hook was fading. As of 2026-11-04 this table is hard rule **R2** and gate **G1a** (`PLAYBOOK.md`, `FLOWS.md` A1a): the playbook says "we change X because stage Y is fading" or "we do not refresh".

## 3. Change catalog (video layers)

| Layer | Change | Tool | Cost | Test |
|---|---|---|---|---|
| Text | hook on an overlay | Remotion `HookSwap` | 0 | ✅ |
| Text | promise, CTA, offer, price; rebuilding a burned-in card in the original style (to move it or to cover it) | Remotion `HookSwap`, card style `outlineBar` (Ad 3 original: orange outline + white bar), geometry measured per frame | 0 | ✅ (Ad 3 re-cut R2, R4, R5, 2026-11-05) |
| Text | removing burned-in captions from the image | clean sources from the user (📥, preferred); without them video inpainting in two modes: **budget: OpenCV Telea** (free) or **pro: ProPainter** (`jd7h/propainter`, fills in from neighboring frames via optical flow, `fp16=true`, files as data URIs); **automatic selection by default** (`tools/inpaint_mode.py`). Telea is only for small captions: on a large card (Ad 3, 520×160 px) it smears | pro: about $0.05 / 2.5 s; budget: 0 | ✅ (ExampleTravel; Ad 3 card 4.8 s) |
| Text | recreating word-by-word captions in the original's style | caption box detection (OpenCV), typeface and size chosen with comparison stills, Remotion `WordCaptions`, timings from whisper word timestamps | 0 | ✅ (ExampleTravel) |
| Audio | new VO line in the same voice | **flow V below** | ElevenLabs | ✅ (ExampleTravel H1 2026-11-03; bridging line in the ExampleTravel re-cut 2026-11-05) |
| Audio | entire new VO, new voice | ElevenLabs TTS | ElevenLabs | ❌ |
| Audio | replacing the music with licensed music | ElevenLabs Music; trending organic sounds only as a reference (no license). The model writes an outro (fades from ~9 s of 14.5 s) even when told not to: generate it as raw material and edit it on the beat grid (`tools/recut.py`) | ElevenLabs | ✅ (Ad 3 R1, 2 takes) |
| Audio | separating the tracks (voice / music) | Demucs (Replicate `ryan5453/demucs`) or ElevenLabs Voice Isolator (voice); music = Demucs stem | low | ✅ (ExampleTravel re-cut) |
| Audio | music edit to a new length | beat grid (librosa), whole bars removed, 40 ms equal-power crossfade, fade to the picture length (`tools/recut.py`); QA: level jump ≤ 3 dB, beat interval ≤ 15% (`tools/recut_qa.py`) | 0 | ⚠️ technically passes QA, but **user review 2026-11-05: the jumps are audible** (Ad 3 R1). Not a default: see "music for a re-cut" below |
| Image | new first shot (AI) | GPT Image 2 + Veo 3.1 Fast | $ | ❌ (planned, postponed) |
| Image | new aesthetic of the whole ad / **topic swap** (topic from a topic trend in the background + hook matched to the topic, section 4b) | GPT Image 2 + Veo chain + Remotion | $$ | ✅ (variant C v02) |
| Image | change of scenery or clothing while keeping the motion (video-to-video) | `runwayml/gen4-aleph`, `luma/modify-video` | $$ | ❌ |
| Image | new words for the speaking person | lip-sync: `sync/lipsync-2-pro`, `bytedance/latentsync`, `kwaivgi/kling-lip-sync` | $ | ❌ |
| Image | new speaker (avatar from image and audio) | `bytedance/omni-human` | $$ | ❌ |
| Structure | shorter cuts (15 s, 12 s), speeding up a segment; with a VO: picture and VO cut together at sentence gaps, so burned-in captions stay in sync | `tools/recut.py` (picture and music cut separately), `tools/recut_qa.py` | 0 | ✅ (Ad 3 R1, R3, R5; ExampleTravel 26.9 → 18.6 s). **User review 2026-11-06: R5 (12 s on the moving shot only, ProPainter-cleaned sky) OK, 12 s not too fast; R3 (second shot sped up 1.52×) looks natural.** Speeding up a calm, slow shot by ~1.5× is an acceptable L0 fix for a static middle; music redone 2026-11-06 with method E (3c) at no cost: the round-3 take (original 0–10 s + 10 s continuation, 20.04 s) already matched the 20 s cut, so it is used whole with no joint (`ad3_R3_speedup_inpaintE_L5_v02.mp4`). Reuse rule: before generating, check whether an existing E take has the needed length |
| Structure | 6 s cut (hook + CTA) | one continuous shot (no cut to the CTA shot): the hook card pre-typed from the first frame (no time for the typewriter) types the CTA at 3 s in the same card; music: the original from 0, uncut, short fade (`recut.py` + `HookSwap`) | 0 | ✅ (Ad 3 R7 v02, 2026-11-05). **User chose the continuous flight over v01 (cut to the CTA shot), which broke the flight** |
| Structure | reordering scenes, cold open | move the strongest scene (sentence, shot) to the start and drop a set-up line whose payoff moved away; `recut.py` (speech: `audio_mode: "sync"`), picture cut at caption switches or shot changes and ending ≥ 2 frames before a shot change (the 30 fps conversion otherwise pulls in the next shot's first frame); `recut_qa.py` with `--caption-band` and `--expected` | 0 | ✅ (ad_2 cold open v03, 2026-11-06: "Wystarczy dziesięć minut ćwiczeń przed snem, a efekt widać już pierwszej nocy" first, "Chcecie znać mój sposób?" dropped, 28.3 s; QA pass; **user review 2026-11-06: OK**). **Needs separable scenes:** an ad of one or two continuous shots (Ad 3) cannot be reordered without cutting inside a shot, so it is not offered at level 0 there |
| Structure | talking head / UGC: cutting sentences and pauses | picture and audio cut together in speech gaps (`recut.py` `audio_mode: "sync"`, 40 ms crossfade without shortening; never a plain crossfade, which shifts the audio ahead of the lips by its length at every joint). Burned word captions switch ~0.1–0.2 s before or after the speech: cut the picture at the caption change and let the audio run on into the neighbour's silence (`audio_tail` / `audio_head`, L- or J-cut). AI UGC is often one shot per sentence, so most sentence cuts are shot changes; a face-to-face jump appears only inside a multi-sentence shot. Jump treatments: hard cut (native UGC), punch-in 112% (also scales burned captions and strips), b-roll cover 1 s with the covered words rebuilt (`WordCaptions`, Montserrat 600, lowercase) | 0 | ✅ (ad_2 29.7 → 19.3 s, J1–J3, 2026-11-05). **User review: all three treatments acceptable; the choice depends on the concept of the ad.** 2026-11-06: the new `recut_qa.py` check found a one-frame flash at 15.20 s in J1 v04 (and in J2 v04, J3 v02 built on it: the segment ended at 19.80 s, the shot changes at 19.798 s) → J1 v05, J2 v05, J3 v03 with the segment ending at 19.76 s (**user review of J1 v05 2026-11-06: OK**) |
| Structure | hiding a jump cut inside one continuous shot | 8-frame dissolve (0) or FILM interpolation (`google-research/frame-interpolation`, text must be identical in both frames); Veo first/last frame unsuitable for short trims (min 4 s, needs frames without burned-in text) | 0 / cents | ❌ **user review 2026-11-05: looks poor** (Ad 3 R6). Avoid cuts inside one continuous shot; tested next: the whole shot regenerated by Veo with first + last frame of the original (R6 v02, 12 s → 8 s): continuous; grey-water artefact mid-clip (~2 s) **accepted by the user 2026-11-05 without a fix**; ask for calm water in the prompt from the start |
| Structure | new shot inserted in the middle (AI), e.g. proof or a moment from the copy | GPT Image 2 edits a frame of the original (cards removed, pose changed) → Veo 3.1 Fast 6 s; use only the clean part of the clip | $0.65 | ❌ **user review 2026-11-05: no continuity** (Ad 3 R4 v01 used only a start frame with a changed pose, and cut back to the original in a different pose). **v02 (2026-11-05): first frame = the original frame at the cut-in, last_frame = the original frame at the cut-out (cards removed by ProPainter on short crops), 8 s: return-joint jump 2.0× instead of 7.1×.** Prompt must ask for calm water (first take turned the river into grey streaks). Keep cards continuous over the generated part (ProPainter residue band). **User review 2026-11-05: v02 continuity is usable** |
| Structure | own asset inserted in the middle (product, screen, review) | Remotion `HookSwap` inserts + rebuilt card | 0 | ✅ (Ad 3 R2; user review 2026-11-05: OK as an option) |
| Format | crop to 4:5 and 1:1, Stories and Reels safe zones | Remotion | 0 | ❌ |
| Localization | the same voice in another language | ElevenLabs Dubbing | ElevenLabs | ❌ |
| Human | reshoot by the creator according to the brief | creative brief → 📥 new material | outside the system | ❌ |

Replicate models verified as available on 2026-11-03 (API `/v1/models`).

### 3b. Re-cut levels (tested 2026-11-05)

A re-cut uses the lowest level that removes the diagnosed cause. It moves up only when QA shows that the lower level is not enough. Test and outputs: `runs/01-refresh-ad/2026-11-05_ad3-middle-recut/04_final/recut_levels_test.md`.

| Level | What | Needed when | Cost |
|---|---|---|---|
| 0 · pure edit | cuts, shortening, speed change, music edited on beats | cut points fall between burned-in cards and between shots or sentences | 0 |
| 1 · graphics layer | rebuilt or covering cards in the original style | a burned-in card must move, appear earlier or be hidden | 0 |
| 2 · own assets | product, screen, review inserted | the diagnosis says new information or proof is missing | 0 (📥 asset) |
| 3 · repair AI | ProPainter (clean image under a card), FILM (seam) | the image under a card must be clean, or a jump cut inside a shot must be hidden | cents |
| 4 · generative AI | new shot from an edited frame of the original | no existing footage carries the needed content | ~$0.65 / shot |
| 5 · audio | new music (as raw material, then edited), new VO line in the same voice | the music cannot be edited to the length, or the shortened script needs a sentence that does not exist | ElevenLabs |

Constraints that decide the level: burned-in text, continuous shots (jump cuts), music continuity, sentences cut in half by the VO, source resolution (720p limits zooms above ~115%).

**Shortening one long continuous shot (user proposal 2026-11-05, to test):** do not patch a cut inside it (dissolve and FILM looked poor in R6). Regenerate the whole shot at the target length instead: Veo 3.1 Fast (4, 6 or 8 s) with `image` = the original's first frame of the shot and `last_frame` = its last frame, both cleaned of burned-in cards only, the motion described from the original; the cards are rebuilt over it in Remotion. The same first/last-frame rule applies to a new shot inserted in the middle (R4 v02).

### 3c. Music for a re-cut (decided 2026-11-05 after user review and three ElevenLabs test rounds)

Cutting the mixed or extracted music on beats gave audible jumps (Ad 3 R1). Proposed order of sources:

1. **Original music file or editing project from the user** (📥, asked at A2 together with the clean sources). Cut at phrase boundaries, or let ElevenLabs re-compose it (point 2) from a clean file.
2. **No original file: ElevenLabs Music inpainting on the track taken from the ad (music-only ads; for an ad with a VO we do not extract the music from under the voice: user decision 2026-11-05, too complicated; there the music comes from points 1, 3 or 4).** `music.upload` (own audio, optionally with an extracted composition plan) → a plan for `music_v2_5` that keeps the original's opening and ending slices (audio reference chunks: `song_id` + `start_ms`/`end_ms`) and **generates the transition between them** at the exact length. This removes the hard cut. **First test (Ad 3 R1, 2026-11-05):** no hard cut (join level jumps 0.9–2.3 dB), but the model re-renders the "kept" slices instead of copying them (spectrally close to the original, not identical), and one take drifted in detected tempo. A hybrid that splices the real original back at both ends around the generated join is the third option. Cost: upload with plan extraction ~366 credits, each 14.5 s compose ~220. User verdict: the joins are still audible. **Round 2:** continuing from the natural section boundary (C) and a one-take generation conditioned on the original (D) both fade to silence over the last ~3.5 s despite "no fade" in prompt and negatives; D also starts near-silent. Rule so far: a short generated continuation always ends with a fade, so generate it longer than needed and trim before the fade. **Round 3 (E):** original intro to the section boundary (10 s) + a 10 s generated continuation: full energy to the end, original tempo, trimmed to the picture with a 300 ms fade between beats. **User verdict: E works (2026-11-05). This is the method.** For an ad with a VO, the uploaded audio is the music stem (Demucs), whose artefacts may carry over. No rights confirmation is asked (user decision 2026-11-05, as for the voice).
3. **Another track from the user** (licensed), edited to length.
4. **Generated music** (ElevenLabs Music) with a `composition_plan`: sections with fixed `duration_ms` (v2 models always enforce them), the last section written as a full-energy ending, "fade out" in the negative styles. A plain prompt with `music_length_ms` gave the right total length but a ~5 s fade-out inside it (R1, two takes).

**Accepted recipe (point 2, Ad 3 R1 version E):**
1. Upload the ad's music (the whole audio track, or the music stem for an ad with a VO) with `music.upload`, `extract_composition_plan="music_v2"`. The plan gives the natural section boundaries (Ad 3: intro 0–10 s, main theme 10–24 s).
2. Plan for `music_v2_5`: an audio reference chunk with the original up to a **section boundary** (not the picture cut), then **one generation chunk at least 10 s long**, conditioned on the original's next section (`condition_strength: high`). Short continuations (3–4.5 s) always end in a fade, even with "no fade" in the prompt and negatives.
3. Trim the result to the picture length with a short fade (300 ms) placed between two beats.
4. QA: tempo against the original, no fade before the end (per-second RMS), loudness. The final verdict is by ear.
Cost: upload with plan extraction ~366 credits (once per track), each compose ~220.

## 4. Flow V: new VO in the same voice when we do not know the voice

Processing of the new line (length fitting, stretching, QA without "reverb") is governed by hard rule **R9** in `PLAYBOOK.md`.

ElevenLabs account: Pro plan, instant (IVC) and professional (PVC) cloning available, 79 of 160 voice slots used.

```
V0  🤖 Audio breakdown      transcription with word timestamps, number of speakers, pace (words/s),
                            VO loudness, whether the speaker is on screen (talking head → V6)
V1  🤖 Does the same voice already exist? (VO made in ElevenLabs = we look for the original voice, we do not clone)
      a) the account's ElevenLabs history: search by transcript → voice_id, model, settings
      b) 📥 user: voice ID or project in ElevenLabs
      c) 🤖 identification by sound (tested 2026-11-03 on ExampleTravel):
         the voice from the ad isolated with ElevenLabs Voice Isolator → candidates: account voices
         (`/v1/voices`) + library (`/v1/shared-voices`, language and gender from the breakdown) →
         free `preview_url` samples → speaker similarity (ECAPA, 100 Hz–4 kHz band) →
         top 3–5 for listening. Bonus: a voice added to the brand's account is a strong signal.
         ✋ user confirms after listening (optionally 💰 the candidates read the original sentence)
         ExampleTravel result: 1472 voices, the library voice "Engaging, Reassuring Storyteller" #1 (0.63;
         median 0.18), confirmed by the user; the original sentence generated with this voice
         has a similarity of 0.59 to the original and the same noise level (−69 dB)
         Signal: an IVC clone from a clean recording gets "requires_verification" in ElevenLabs
         when the voice is a protected professional clone from the library → search the library, do not work around it
      → found: this is the 1:1 original, go to V4 with the same settings
         (default voice settings from `/v1/voices/{id}/settings`)
V2  ✋ Voice rights          who owns it: voice artist with a contract / AI voice (Veo etc.) / unknown.
                            Cloning a human's voice only with their consent (ElevenLabs and legal requirement).
V3  1:1 clone. Goal: the same voice, not a similar one. We do not pick "similar" voices from the library.
      Option 1: 📥 we have source recordings (raw voice artist recording, clean VO track, other
         materials with this voice)
         → ≥ 30 min of clean speech: 💰 professional clone (PVC), the most faithful
         → shorter: 💰 instant clone (IVC) from the cleanest 1–3 min
      Option 2: no recordings, 🤖 we extract the voice from the ad itself
         a) collect the speech: this ad + other ads with the same voice (confirmed by
            comparing speaker embeddings, so as not to mix two voices in one clone)
         b) 💰 isolating the voice from under the music: **always ElevenLabs Voice Isolator** (user decision;
            noise between words −60…−78 dB vs −29…−58 dB with Demucs). Demucs only for the music track
         c) 🤖 cutting into sentences (whisper timestamps), rejecting fragments with effects,
            music bleeding through the isolation, or overlapping speech
         d) 💰 IVC clone from the clean fragments (ElevenLabs recommends 1–3 min; one ad gives
            15–25 s, so the number of ads with this voice decides the fidelity)
         e) quality of the clone material: the clone inherits the quality of the recordings (noise, music
            residue, clipped bandwidth). Fragments are ranked by voice-to-music ratio and bandwidth;
            the best go into the clone, and weaker ones only if there is not enough speech without them
            (example: PL1 12.3 dB > PL2 5.9 dB)
      On both paths, to direct the intonation: speech-to-speech (recording of the new line →
      conversion to the cloned voice).
    🤖 Clone QA: the same line as in the original, generated by the clone → speaker similarity
       to the original (ECAPA, local) ≥ threshold
    ✋ G-V: blind listening test: original line vs the same line from the clone
V4  💰 Generating the new line: several takes (PCM 44.1 kHz), pace and emotion as in the original.
     Selection in two steps: (1) quality gate: noise between words ≤ −55 dB, brightness
     (4–8 kHz vs 0.3–3 kHz) ≥ −10 dB, length fits in the slot; (2) of those that passed,
     the highest speaker similarity. In the test, similarity alone picked the take that sounded worst
     (ExampleTravel v1: dull −18.6 dB, noise −22 dB). With a clone: similarity_boost ≤ 0.75, because higher
     copies the flaws of the material
V5  🤖 Pasting in and QA:
      cut in the pause between words (whisper timestamps), matching of loudness (LUFS) and timbre
      (EQ, room reverb), music from underneath taken from the separated tracks;
      quality matching in both directions: the new line from the clone is usually cleaner than the rest
      of the ad, so it gets the same bandwidth, compression and timbre as the neighboring sentences;
      a line that is too clean sticks out just like one that is too dirty;
      QA: speaker similarity ≥ threshold, transcription of the new line = intended text,
      no loudness jump at the splice, new word-by-word captions match the audio
V6  Speaker on screen (talking head):
      a) cutaway (b-roll, product) for the duration of the changed line: 0 zł, the safest
      b) 💰 lip-sync on the original shot (sync lipsync-2-pro / LatentSync)
      c) 💰 for AI material: a new Veo shot with audio (mouth matches the new words)
         → speech-to-speech into the target voice, so the timbre is the same as in the rest of the ad
      d) reshoot by the creator (brief)
```

**Quality rule:** if the clone does not pass QA (similarity below the threshold or the blind listening test recognizes it), we do not patch a single line. First we add material to the clone (📥 recordings from the user, further ads with this voice). If that is not enough, we generate the entire VO with a new, consistent voice. An audible change of timbre mid-ad is worse than a new voice.

**Speaker similarity model** (`tools/speaker_sim.py`, ECAPA-TDNN from SpeechBrain, local, 0 zł). Calibration from 2026-11-03: `runs/01-refresh-ad/2026-11-02_ad3-dry-run/03_wip/voice_calib/calibration_results_v01.json`.

| Test | Same voice (min / median) | Different voice (median / max) | Error (EER) |
|---|---|---|---|
| 9 known voices, clean recordings (ElevenLabs history + promo VO), 59 clips | 0.46 / 0.83 | 0.12 / 0.54 | 0.6% |
| Same voice with music at −12 dB | 0.67 / 0.82 | 0.11 / 0.47 | 0% |
| as above after Demucs isolation | 0.70 / 0.84 | 0.12 / 0.47 | 0% |
| PL ads, isolated voice, fragments of the same ad | 0.53 / 0.68 | — | — |

Conclusions:
- The model tells clearly different voices apart well, including ones similar to each other (two young male American voices: 0.30). Music underneath does not bother it.
- The uncertain zone is 0.45–0.6. Example: the voice artists PL1 and PL2 average 0.60, so it is not known whether it is the same voice.
- A "nearly identical" clone will land exactly in the zone of high scores, where the model does not decide on nuances.

**PL1 vs PL2, i.e. the effect of quality.** Listening (user): the voice is very similar, the difference is in quality.

The measurement confirms this (`calibration_PL1_PL2_quality_v01.json`):
- PL2 has the voice only 5.9 dB above the music, while PL1 has 12.3 dB. PL2 has more music residue in the high frequencies.
- After limiting both recordings to the common 100 Hz–4 kHz band, the similarity of PL1 to PL2 rises from 0.60 to 0.69. That is almost the level of fragments from the same ad (0.72–0.74).
- Equalizing the timbre (EQ) alone changes nothing.

Conclusion: part of the uncertain zone is **the same or a twin voice in different quality**, not a different voice.

Rules of use:
0. We compare only with equalized quality: isolated voice and both recordings in the 100 Hz–4 kHz band. A result on a raw recording mixes voice identity with recording quality.
1. Grouping ads with the same voice for a clone (after step 0): ≥ 0.65 same, ≤ 0.40 different, in between the listening test decides.
2. Clone QA, relative criterion: the similarity of the clone to the original must not be lower than the similarity of the original's fragments to each other (median from the same ad, here about 0.68).
3. The final decision always belongs to the blind listening test (G-V).

**Clone test from the ad alone (2026-11-03, `runs/01-refresh-ad/2026-11-03_pl-vo-clone/`).**
- Material: about 31 s of speech from PL1 and PL2 after Demucs.
- Variants: 2 IVC clones × 2 models, evaluated on sentences excluded from the clone.
- Blind listening result: the user did not identify the original in any group (5 recordings per group, clone pasted in after a sentence of the original over the original music).
- Similarity model: all clones within the variation of the original.

Findings:
- adding the lower-quality PL2 helped (K2 > K1);
- eleven_multilingual_v2 keeps the pace of the original;
- eleven_v4 has a similar timbre but speaks more slowly (+10–43%).

Defaults in flow V: IVC clone from all available speech, model eleven_multilingual_v2, check of the sentence length against the slot.

Untested: pasting a new line (not a sentence from the original) into the full ad, and the new captions.

## 4a. Removing burned-in captions and recreating them (tested on ExampleTravel, 2026-11-03)

1. 📥 First a clean source (project, render without captions). If there is none:
2. 🤖 **Mask:** caption detection in every frame (white text with a dark outline, in the caption band). Box +16 px, union with neighboring frames, only in the window where we change the text.
3. **Inpainting: mode `auto` (default), `budget` or `pro` in the config.** A manually set mode always wins.
   - First always free OpenCV Telea, then render the new captions on that background.
   - 🤖 `tools/inpaint_mode.py` computes how much of the space left by the old captions stays uncovered by the new captions. **Budget** when in every frame ≤ 0.3% of the frame is visible and ≤ 1.5 s in total. Otherwise **pro** (💰 ProPainter).
   - ExampleTravel: at most 0.21% of the frame, 1.13 s → budget. In listening and viewing, the user saw no difference between OpenCV and ProPainter. On static close-ups the difference was clear, but the assessment must take into account motion, the full frame and the new captions on top.
   - ProPainter is needed when the text disappears without a replacement, the new words are shorter or in a different place, the background is sharp and textured (face, lettering, static shot) or the caption is large.
   - **pro, 💰 ProPainter** on a crop around the captions (ExampleTravel: 600×520 px, 75 frames, 34 s GPU, about $0.05). Inputs as `.mp4` data URIs, because the model checks the file extension. The result comes back at 608×528, so we scale it to the crop and paste it in only within a soft mask.
   - **budget, 0 zł, OpenCV Telea:** on a close-up it leaves patches on texture (sand, water). Classical image processing, no model: not AI media, so the free plate alone adds no AI label (`tm ai-media`, `flow.md#e1`). ProPainter is AI media.
4. 🤖 **Style recreation:** stills with typeface candidates over the original word → comparison of the boxes (width, height, baseline) → correction of size, scaleY and position. ExampleTravel: Nunito 900, 64 px, scaleY 1.11, outline #15151A 7 px, center x 540, baseline y 1509.
5. 🤖 **Timings:** a word is visible from its start to the start of the next one, the last one until the end of speech +0.15 s (rule read from the original).
6. 🤖 **QA:**
   - difference vs the original outside the caption band ≈ codec noise (ExampleTravel 2.9–3.3);
   - jump at the splice with the original ≤ median of the jumps (4.2 with a median of 6.0);
   - loudness of the hook window = original ±0.5 LU (v01 was 1.2 LU louder, corrected to −19.1 LUFS).
