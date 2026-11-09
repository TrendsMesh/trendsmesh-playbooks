# Re-cuts (path C-R): the methods, how to build each one, and the limits

Source: the playbook handoff v03, `HANDOFF.md` 9a (methods) and 9c (limits), `FLOWS.md` path C-R,
`VARIANTS.md` 3b and 3c, with what the engine checks. Every method below was built by hand on a
real ad (Ad 3: AI flight, music only, burned-in cards; ad_2: talking-head UGC with word captions;
ExampleTravel: voiceover, captions and music) and reviewed by the playbook owner. The steps are in `flow.md#cr1` to
`#cr7`; this file is what you choose from at CR3 and build at CR4 to CR6.

**The engine decides what is legal.** You propose cut points; `tm recut check` says whether the
edit list may be rendered, and `tm tool recut` runs the same check again before it renders. Never
render, cut or judge a joint around it, whatever it looks like on the frames.

## 1. When a re-cut is on

- **A middle diagnosis** (`diagnosis.target_stage` is `middle`): flow R is on by itself; `tm next`
  walks CR1 to CR7. The card steps of the hook (C2 to C4) are not in such a run.
- **A structural weakness** (R2b, `diagnosis.structural.structural` is true) while the target is
  another stage: an improvement opportunity, never a refresh trigger. At Check every step and Just
  the big calls, offer it at the "Accept the diagnosis" check-in; if the user takes it, run `tm flow
  R --run R` then, before the diagnosis is recorded. Hands-off turns it on only when the config has
  `diagnosis.structural_recut: true` (asked at intake); otherwise don't run `tm flow R`: the
  weakness stays in the report as an opportunity. `tm flow R` refuses (exit 1, with the reason)
  when the diagnosis allows no re-cut, in Hands-off without that setting, and once the run is past
  C1 (method selection): the refusal is the answer, never something to work around.
- **Still not supported** (say so plainly, in the user's words): lip-sync or any new speech on
  camera (a talking head gets only the re-cuts below), static graphics, and a reorder or cut inside
  one continuous shot at level 0 (offer the level-4 regeneration instead, section 4).

## 2. Levels (VARIANTS.md 3b)

Choose the **lowest level that removes the cause**; go up only when QA shows the lower one is not
enough. A variant's `level` is the highest level of the work it needs.

| Level | What | Budget | Cost |
|---|---|---|---|
| 0 · pure edit | cuts, shortening, speed change | none | free |
| 1 · graphics layer | cards rebuilt, moved or covered in the original style (HookSwap) | none | free |
| 2 · own assets | product, screen or review footage inserted (from the user) | none | free |
| 3 · repair AI | ProPainter: a clean image under a removed card | `ai_usd` | cents (about $0.05 per 2.5 s) |
| 4 · generative AI | a new or regenerated shot (Veo 3.1 Fast, first + last frame) | `ai_usd` | $0.80 per 8 s |
| 5 · audio | a new music take (method E) or a new voiceover line | `voice_credits` | about 220 credits per music take; a one-off upload of about 366 credits per track |

A music take already saved in the run that `tm recut music` calls `reuse` (within ±0.05 s of the
picture) is an input file, not paid work: it does not raise the level. Any other take (a longer
one to trim, a new one) is level 5.

`recut.max_level` caps the level: above it an edit list waits in Hands-off and is refused at the
other levels. Unset, Hands-off stops at 2 and the other levels ask at the variants check-in.
**Hands-off never stops the run for a re-cut budget:** an L3 to L5 edit list without its budget, or above `recut.max_level`, is left `waiting` by `tm recut check`, and the free
L0 to L2 variants are still rendered. At the other levels, the re-cut budget check-in comes before
the paid steps (one yes for `ai_usd` and `voice_credits` together). A budget is one running
total per kind in the run, shared with the AI video (`ai_usd`) and the voice budget
(`voice_credits`): approve the kind's running total, not the re-cut's amount alone (SKILL.md
section 5). While the re-cut budget's answer is `reject`, `tm recut check` counts no budget as
approved for a re-cut.

## 3. The methods (HANDOFF 9a)

`change_id` is the edit list's header field: a `stage: middle` entry of `tm changes --stage middle
--material <material> --json` that fits the run's material (`tm recut check` refuses another).

| Method | `change_id` | Level | Choose it when | How | QA that must pass | Reference |
|---|---|---|---|---|---|---|
| Shorter cut (15 s, 12 s) | `recut_shorter` | 0 (1 when a card moves, 3 when the image under a removed card must be clean) | the last new information comes early and the rest repeats (causes "ad longer than its content", "visual monotony") | segments at shot changes or between cards; a card that must move is rebuilt (HookSwap, L1); the image under a removed card is cleaned with ProPainter (L3, never OpenCV Telea on a large card) | joint strips, no flash, music checks | Ad 3 R1 (15 s), R5 (12 s) |
| Speed-up of a slow segment | `recut_speedup` | 0 | a calm, near-static segment (visual change falls) | the segment's `speed` about 1.5; the picture speed fitted to the music length | as above | Ad 3 R3 (1.52×) |
| 6 s bumper | `bumper_6s` | 1 | a 6 s placement, or a hook + CTA test | one continuous shot, never a cut to the CTA shot (it broke the flight); the hook card pre-typed from frame 0; the CTA typed into the same card at 3 s; music: the ad's own track from 0, uncut, short fade | card against the burned card, length | Ad 3 R7 v02 |
| Scene reorder (cold open) | `recut_reorder` | 0 | the strongest line or moment sits late, where most viewers have already left | move the scene (sentence, shot) to the start; drop a set-up line whose payoff moved away; speech in sync mode. Needs separable scenes: an ad of one or two continuous shots has nothing to reorder at level 0 | no flash, no word across a fade point, no caption flash, transcript = the expected script | ad_2 cold open v03 |
| Proof in the weak window | `recut_proof_insert` | 2 (1 for the rebuilt card) | "no proof" or "visual monotony" in the weakest window, and a product asset exists | a HookSwap insert (about 4 s) in the weakest window; the burned CTA covered from the insert's end by a card rebuilt in the original style (`style: "outlineBar"`, geometry measured per frame), so it never covers the product's title | rebuilt card against the burned one | Ad 3 R2 v02 |
| New shot (AI) in the middle | `recut_new_shot` | 4 | no existing footage carries the needed content (e.g. a moment from the primary text) | Veo 3.1 Fast 8 s, `image` = the original frame at the cut-in, `last_frame` = the original frame at the cut-out, both cleaned of cards with ProPainter on short crops; the prompt describes the original motion and asks for calm water, stable scenery | joint jump against the typical frame change (2.0× with both frames, 7.1× with a start frame only) | Ad 3 R4 v02 |
| Shortening one continuous shot | `recut_new_shot` | 4 | the shot must be shorter and a cut inside it would show | regenerate the whole shot at the target length (4, 6 or 8 s) with Veo, first + last frame of the shot; never a dissolve or FILM inside the shot (both looked poor) | as above | Ad 3 R6 v02 (a short grey-water artefact, accepted) |
| New voiceover line where the shortened script breaks | `recut_new_vo_line` | 5 | sentences were removed and the rest no longer connects (voiceover ads only; never in Hands-off, where it waits) | flow V: the line in the original voice (the original voice or a clone, never a library lookalike); the captions under it removed with ProPainter and rebuilt with WordCaptions | whisper hears every line in order (`--expected`); caption style against the original | ExampleTravel R15 |
| Talking head: sentence and pause cuts | `recut_shorter` | 0 (1 for a b-roll cover) | a slow or redundant sentence, long pauses | `audio_mode: "sync"`; the picture cut at the caption switch, the audio in the speech gap, `audio_tail` / `audio_head` when captions switch early or late; jump treatment `jump`: `hard` (native UGC), `punch_in` (112 %, scales the burned text too) or `broll` (an insert with the covered words rebuilt) | no word across a fade point, no caption flash, transcript complete, no flash | ad_2 J1 v05, J2 v05, J3 v03 |
| Music for a new length | (part of any variant) | 5 for a new take | any re-cut that changes the length of a music track | the chain in section 6; never a beat-cut edit of the track as the final music | tempo drift ≤ 4 %, no fade before the end, music by ear | Ad 3 R1 E, R3 v02 |

Talking heads (material `talking_head`) get `recut_shorter`, `recut_reorder` and
`recut_proof_insert` only. `recut_speedup` and `bumper_6s` are for text-card ads; `recut_new_shot`
is not for talking heads; `recut_new_vo_line` is for voiceover ads.

**One change per variant**, so the test can tell what worked. The six kinds to propose: a shorter
cut (15 s, 12 s or 6 s), a speed-up of a slow segment, a scene reorder (cold open), proof inserted
in the weak window, a new shot, a new voiceover line.

## 4. Refusals you will meet, and what to offer instead

- **A cut or reorder inside one continuous shot** (`tm recut check`: a joint whose two sides lie in
  the same shot, or a shot played in separated pieces): refuse it at level 0 and offer the
  level-4 regeneration of the whole shot with Veo first + last frame, with its estimate
  ($0.80 per 8 s) asked before any call. Never offer a dissolve or FILM as the final.
- **A flash** (a segment ending within 2 frames of a shot change, or a piece of another shot
  shorter than 8 frames at its edge): end the segment at least 2 frames before the change, or 8
  frames or more after it; start at the change or 8 frames or more before it. Frames are the
  source's frames at its own fps (`tm recut points` gives them), never an assumed 30.
- **Speech not in sync mode, or an audio cut inside a word**: `audio_mode: "sync"`, audio cut points
  in the speech gaps `tm recut points` lists (0.12 s or longer).
- **A dissolve in sync mode**: cut instead (the sound would play late after it).
- **More than one `audio` segment of the same file**: a beat-cut music edit, never the final. Use
  the music chain (section 6). `"draft": true` lets a draft through for a listen, never a final.

## 5. The edit list

One JSON file per variant, `03_wip/recut/<variant>_vNN.json` (a new version for every change, never
an edit in place), recorded with `tm record` (stage `03_wip`, source "edit list for <variant>").
The reference tool's (`tools/recut.py`) format plus the header fields:

```json
{"variant": "R1-15s", "change_id": "recut_shorter", "level": 5,
 "cause": "ad longer than its content: no new information after 14.2 s",
 "music_source": "elevenlabs_continuation",
 "fps": 30, "width": 720, "height": 1280,
 "video": [{"src": "../../01_base/123_original.mp4", "from": 0.0, "to": 11.146},
           {"src": "../../01_base/123_original.mp4", "from": 20.735, "to": 24.149}],
 "audio": [{"src": "../audio/music_take_v01.mp3", "from": 0.0, "to": 20.0}],
 "audio_xfade_ms": 40, "audio_tail_fade_ms": 300}
```

(Ad 3's 15 s cut, 14.533 s of picture. `tm recut music --target-s 14.533` found no take within
±0.05 s, so a method E take was generated for it at CR5b: 20 s, 10 s of the original and a 10 s
continuation, trimmed at the picture's end with the 300 ms fade. A new take makes the variant
level 5. Had an earlier take of 14.53 s been saved in the run, `tm recut music` would have said
`reuse`, and the same edit list with that take would be level 0.)

Only a take `tm recut music` calls `reuse` keeps the variant at level 0; otherwise follow its
`generate` or `resume`.

- **Header:** `variant` (the name, in letters, digits and hyphens: it names the output file, and
  any other character becomes a hyphen there), `change_id` (section 3), `level` 0 to 5,
  `cause` (the diagnosed cause it removes, in words), `music_source` (one of `original_file`,
  `elevenlabs_continuation`, `licensed_track`, `generated`, or `sync` when the picture segments
  carry their own sound), optional `jump` (`hard`, `punch_in` or `broll`) and `draft` (true or
  false).
- **Paths** (`src`, `audio_src`, `extra_audio[].src`) are relative to the edit list's own folder:
  from `03_wip/recut/`, the original is `../../01_base/<file>`, a music take `../audio/<take>`, a
  cleaned plate `../clean/<file>`.
- **Picture:** `video` segments `{src, from, to}` in seconds of the source, with optional `speed`,
  `seam` (`cut` or `dissolve`, `seam_frames`), `audio_head`, `audio_tail`, and for a pre-rendered
  clip `audio_src` + `audio_from` (its sound read from the original). `fps`, `width` and `height`
  are the output's: give the original's size. A segment that carries straight on from the previous
  one (same file, next frame, no dissolve, e.g. a speed change) is not a cut.
- **Sound:** either `audio` (the music, one segment per file) with `audio_xfade_ms` and
  `audio_tail_fade_ms` (300), or `"audio_mode": "sync"` (each segment keeps its own sound,
  `sync_xfade_ms` 40, `"audio": []`, `music_source: "sync"`; no `speed` and no dissolve in sync
  mode). `extra_audio: [{src, at, gain_db}]` lays a file over the mix (a new voiceover line).
  The renderer trims longer music at the picture's end with the `audio_tail_fade_ms` fade, and pads
  shorter music with silence (which QA then flags as a fade before the end).
- **Check it on the teardown of the file being cut:** `tm recut check --teardown` takes the
  teardown whose `video` is the file the segments cut (the A3 teardown of `01_base/<ad>_original`).
  Other files in the list count as their own shots. An edit list cut only from a derived copy (a
  transcode or a full-length cleaned plate) is refused against the original's teardown: teardown
  the copy and check against that. When the copy keeps the original's timing, give the teardown
  the original's transcript (`tm tool teardown --run R <copy> --transcript
  02_research/transcript_vNN.json --json`), so the speech rules still apply.

## 6. Music for a re-cut (VARIANTS.md 3c)

The source chain, in order (`recut.music_source`):

1. **`original_file`**: the user's own music file or project (asked at A2 with the clean sources),
   cut at a phrase boundary; also the ad's own track played whole from its start in one segment
   (the 6 s bumper).
2. **`elevenlabs_continuation`** (method E, music-only ads): the ad's own track continued by
   ElevenLabs Music in one take, no joint.
3. **`licensed_track`**: another licensed track from the user, edited to length.
4. **`generated`**: ElevenLabs Music from a composition plan with fixed section lengths, the last
   section a full-energy ending and "fade out" among the negative styles.

**Never a beat-cut edit of the track as the final music** (the joints are audible even when the
numbers pass). **Voiceover ads:** never extract the music from under the voice (the playbook
owner's decision); cut the mix together with the voice (`audio_mode: "sync"`, `music_source: "sync"`), or
use a music file from the user.

**Before generating anything:** `tm recut music --run R --target-s <picture length from tm recut
check> --json`. Its `decision`:
- `reuse`: a saved take within ±0.05 s of the picture fits: use it whole, one segment, 0 credits.
- `resume`: a paid take whose file was not saved waits: `tm tool elevenlabs music-compose --run R
  --resume <the record it names> --json` fetches it for free; then ask `tm recut music` again.
- `generate`: method E below, about 220 credits per take, estimated and approved first.

**Method E** (the accepted recipe, Ad 3 R1 E):
1. The ad's track: `tm tool ffmpeg --run R --out 03_wip/audio/<ad>_track_v01.wav --parent
   01_base/<original> -- -i 01_base/<original> -vn -ac 2 -ar 48000`.
2. Upload it once per track, with its composition plan extracted: `tm tool elevenlabs music-upload
   --run R 03_wip/audio/<ad>_track_v01.wav --cost <credits> --json` (about 366 credits) →
   `03_wip/audio/music_upload_vNN.json` (`song_id`, `composition_plan`). The plan gives the natural
   section boundaries (Ad 3: intro 0 to 10 s, main theme 10 to 24 s).
3. The plan for `music_v2_5`, a file in `03_wip/audio/`: the original up to a **section boundary**
   (not the picture cut), then **one generation chunk of at least 10 s** conditioned on the next
   section. Shorter continuations always end in a fade.
   ```json
   {"chunks": [{"song_id": "<song_id>", "range": {"start_ms": 0, "end_ms": 10000}},
               {"text": "[Main Theme]\n{the theme enters and keeps building with full energy}",
                "duration_ms": 10000, "positive_styles": ["..."], "negative_styles": ["fade out", "..."],
                "context_adherence": "high",
                "conditioning_ref": {"song_id": "<song_id>", "range": {"start_ms": 10000, "end_ms": 24148}},
                "condition_strength": "high"}]}
   ```
4. `tm tool elevenlabs music-compose --run R --plan 03_wip/audio/<plan>_v01.json --cost 220 --json`
   → `03_wip/audio/music_take_vNN.mp3` and its record. A 401, 402 or 403 means the plan or key has
   no Music: a stop, nothing spent.
5. Put the take in the edit list as one `audio` segment from 0; the renderer trims it at the
   picture's end with the 300 ms fade (`audio_tail_fade_ms`). QA checks the tempo, the tail and the
   loudness; the final verdict is by ear (the "Approve each re-cut variant" check-in).

## 7. Building each kind (the commands)

Shared: `tm recut points --run R --teardown 02_research/teardown_vNN.json [--transcript
02_research/transcript_vNN.json] --json` lists the shot changes (frame and seconds), the card
switches and the speech gaps: take cut points from it. Then the edit list, `tm recut check`, the
paid parts (CR5a, CR5b), `tm tool recut`, the cards, and `tm tool recut_qa` (`flow.md`).

- **Cards (L1) and inserts (L2)** go over the rendered cut: HookSwap props with `base` = the re-cut
  (`04_final/<variant>_vNN.mp4`, paths relative to the run folder), `cards` (`style: "outlineBar"`
  for the Ad 3 look, with `left`, `top`, `width`, `height`, `barExt`, `barHeight`, `borderPx`
  measured per frame on the burned card; `"box"` is the default white box) and `inserts` (`src`,
  `from`, `to`, `trimStart`, `zoom`). `tm render still` at the key frames next to the burned card,
  then `tm render video --run R --comp HookSwap --props <props> --json`. A pre-typed card has
  `typeCharsPerSec` of 1000 or more.
- **Files for a Replicate spec** sit in the spec's own folder: `tm tool replicate_run` reads a
  relative input path from the spec's folder. Write them there with `tm tool ffmpeg --out`
  (`--name` writes to the stage folder, `03_wip/`, not to a subfolder).
- **ProPainter (L3)**: the crop of the card's region, `tm tool ffmpeg --run R --out
  03_wip/clean/<name>_crop_v01.mp4 --parent 01_base/<original> -- -ss <from> -to <to> -i
  01_base/<original> -vf crop=<w>:<h>:<x>:<y>`; the mask, white over the card plus 16 px on black,
  the crop's size: `tm tool ffmpeg --run R --out 03_wip/clean/<name>_mask_v01.png -- -f lavfi -i
  color=c=black:s=<w>x<h> -vf drawbox=x=<x>:y=<y>:w=<w>:h=<h>:color=white:t=fill -frames:v 1`;
  the spec `03_wip/clean/<name>_v01.json`, its inputs named relative to that folder:
  `{"model": "jd7h/propainter:e5ea7ae04e97c96a0e14c70d8e4cb899abdf326a377c01f1c10966ccd6c6bae4",
  "input": {"video": "<name>_crop_v01.mp4", "mask": "<name>_mask_v01.png", "mode":
  "video_inpainting", "fp16": true},
  "file_encoding": "base64"}` (ProPainter checks the file extension, so data URIs with a pinned
  version; `fp16` true or it fails). `tm tool replicate_run --run R 03_wip/clean/<name>_v01.json
  --name <name> --cost <USD> --json` → `03_wip/<name>_vNN_0.mp4`. The result comes back slightly
  larger (608×528 for a 600×520 crop): scale it to the crop and paste it in within a soft mask
  with `tm tool ffmpeg` (`flow.md#vc` and `variants.md` 4a). Never OpenCV Telea on a large card: it smears.
- **Veo (L4)**: the frames at the cut-in and the cut-out, each cleaned of cards with ProPainter on
  a short crop around it, then taken as one exact frame into the spec's folder: `tm tool ffmpeg
  --run R --out 03_wip/ai/<name>_in_v01.png --parent <the cleaned clip> -- -ss <seconds> -i <the
  cleaned clip> -frames:v 1 -update 1` (and `<name>_out_v01.png` the same way); the spec
  `03_wip/ai/<name>_v01.json`: `{"model": "google/veo-3.1-fast", "input": {"image":
  "<name>_in_v01.png", "last_frame": "<name>_out_v01.png", "prompt": "<the original motion; calm
  water, stable scenery>", "negative_prompt": "text, captions, cuts, scene change, ...", "duration": 8, "resolution":
  "1080p", "aspect_ratio": "9:16", "generate_audio": false}}`; `tm tool replicate_run --run R
  03_wip/ai/<name>_v01.json --name <name> --cost 0.80 --json` (confirm Replicate's price first,
  lesson 7). The clip is a segment of its own in the edit list; keep the cards continuous over it.
- **New voiceover line (L5)**: `tm flow V --run R` at the variants check-in; flow V's steps (V0 to
  VC) come after CR4. Never in Hands-off: the voice match (V1c) needs a person, so the variant
  waits, flow V stays off, and the final report lists it. The line goes into the edit list as `extra_audio` at its time, the captions
  under it are removed (VC) and rebuilt with WordCaptions. Cut the takes in silence, never at a
  TTS word start that begins with a sibilant (lesson 14).
- **Talking-head jumps**: `hard`: a plain cut. `punch_in`: render that segment at 112 % with `tm
  tool ffmpeg` (`-vf crop=iw/1.12:ih/1.12,scale=<width>:<height>`) and use the clip as the segment,
  its sound from the original (`audio_src`, `audio_from`); a 720p source limits zooms above about
  115 %. `broll`: a HookSwap insert over the jump (about 1 s), the covered words rebuilt with
  WordCaptions in the original style (ad_2, in the props' `style`: `"font": "montserrat600"`
  needs `"fontWeight": 600` too, and `"textTransform": "none"` keeps the words lowercase as
  given; the default is uppercase).
- **QA**: `tm tool recut_qa --run R <render> [--sidecar <the re-cut's .recut.json>] [--caption-band
  x0,y0,x1,y1] [--expected "<the kept script>"] [--lang <code>] [--original 01_base/<original>]
  --json`. The sidecar sits next to `tm tool recut`'s output; give it with `--sidecar` when you QA a
  HookSwap render made over it. `--caption-band` is the burned captions' box in output pixels (ad_2:
  150,840,570,930); `--expected` the words that should be heard.

## 8. Known limits (HANDOFF 9c and the build)

- **Music is accepted by ear.** Beat-cut joints pass the measurements (level, beat regularity) but
  are audible; method E avoids joints. The tempo check rarely fires on real audio.
- **Music checks run on the whole soundtrack.** On a mix with a voiceover the tempo and tail
  measurements are unreliable (ExampleTravel flags tempo drift and a −7.6 dB tail caused by the speech
  ending, not by the music): read them as notes, not as reds, in a voiceover ad.
- **Whisper mishears brand and rare words** ("e-booka" heard as "i buka"): the transcript check
  reports missing words and flags only when more than 10 % are missing.
- **The caption-flash check needs the caption band** (`--caption-band`). White details under the
  captions (a tablet screen) are filtered by a threshold relative to the typical caption.
- **A pre-rendered clip hides its source frames** (a punch-in clip): `tm recut check` cannot see a
  flash baked into it; `tm tool recut_qa` on the output is the net.
- **Sync mode cuts only**: no speed change and no dissolve with speech.
- **The voice budget covers both the hook's new line and a re-cut's new line.** In a run that
  refreshes the hook and also re-cuts with a new voiceover line, declining the voice budget skips
  the new line and also the hook's render (the card steps after it). Say so when you ask for it.
- **The average watch time** Meta gives is whole seconds per day: a shorter version's test reads it
  next to cost per result, never as a precise number ("about 6 s", not "6.04 s").
- **Talking heads**: re-cut entries only. Lip-sync and new speech on camera stay unsupported.
