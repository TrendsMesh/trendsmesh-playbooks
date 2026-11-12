# Eleven v4: prompting recipe (checked 2026-11-12)

The voiceover model in every playbook (issue #88): an off-screen narrator, a lip-sync line, an animation's voice, a
new ad voiceover. `tm tool elevenlabs tts` records with it unless `--model` names another. Each finding keeps the
date it was made.

Sources:
- ElevenLabs docs, read 2026-11-12: the models page (https://elevenlabs.io/docs/overview/models), the Eleven v4 page
  (https://elevenlabs.io/docs/overview/capabilities/text-to-speech/eleven-v4), the text-to-speech API reference
  (https://elevenlabs.io/docs/api-reference/text-to-speech/convert and `.../convert-with-timestamps`), the
  best-practices page (https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices) and the
  pricing pages (https://elevenlabs.io/pricing, https://elevenlabs.io/pricing/api).
- The owner's live run of Organic AI video on 0.11.0 (a Polish-language channel, two videos with a voiceover,
  reported in issue #88): v4 gave the better read; the credits ElevenLabs billed; the digits read in the wrong case.
- Refresh an ad's clone test of 2026-11-03 (`skills/refresh-ad/references/variants.md` section 3): v4's timbre close
  to the original's, its pace 10 to 43% slower than Multilingual v2's.

## The model

- **`model_id`: `eleven_v4`.** A faster, cheaper `eleven_v4_turbo` exists; the plugin does not price it yet (no
  credit rate for it is known), so it is used only on the user's request, with its cost read from the account.
- **Up to 10,000 characters** a request. 90+ languages (the list is on the models page), Polish and English among
  them.
- **Language:** the request carries `language_code`, ISO 639-1 (ISO 639-3 for a few languages, such as `yue`, `fil`).
  The engine sends the run's market language without its region (`pt-BR` → `pt`); `--language` overrides it. A
  language the model does not support is ignored, not refused. `eleven_multilingual_v2` does not take
  `language_code`, so none is sent there.
- **Voice settings: Stability and Similarity only** (`stability`, `similarity_boost`). "Style and Speed sliders are
  not available in Eleven v4, and SSML is not supported." The engine sends no `speed` for v4 and refuses a
  `--speed` other than 1.0 before anything is sent. A line that must be read faster to fit a slot is made on
  `eleven_multilingual_v2` (0.7 to 1.2). Lower stability gives a more varied, expressive read; higher keeps it
  close to one baseline. With a clone keep `similarity_boost` at 0.75 or less (refresh-ad V4).
- **Word times:** `tts --timestamps` (`/with-timestamps`) gave the alignment in the owner's run; the docs do not say
  per model. `tm organic vo-sync` reads the `.words.json` it writes.

## Credits

- **0.5 credits a character** on v4: what ElevenLabs billed (its `character-cost` answer header) in the owner's run,
  105 credits for 214 characters and 231 for 473. The docs give no number for v4: they say it "uses the same credit
  pricing as our other Text to Speech models", 1 credit a character on Multilingual v2 and "50% lower price per
  character" on Flash v2.5; the API price list has v4 at $0.08 per 1,000 characters, as Multilingual v2. The rate
  lives in `engine/src/tm/tts_models.py`; read the account's real cost from the take's `credits_used` and correct the
  table when it differs.
- An estimate is the text's characters × the rate (`tts_models.credits`). The pack check holds the voice line to it.
- A re-record is priced the same way. When the approved voice budget no longer covers it, the engine refuses the call
  before anything is sent and names the total to ask for: what the run has already spent plus this estimate. The
  run is not stopped.

## Writing the text

- **Numbers, dates and percentages are written out as words**, in the grammatical case the sentence needs, in the
  market's language: "w dwa tysiące dwudziestym szóstym roku", not "w 2026 roku"; "trzy na cztery psy", not
  "3 na 4 psy"; "siedemdziesiąt pięć procent", not "75%". In the owner's run a year in digits was read in the
  wrong form: in Polish a year or a count changes with its case. Captions and on-screen cards may keep digits.
- **Pauses and delivery**: punctuation and ellipses make the pauses (v4 has no SSML break tags); audio tags in
  square brackets steer the delivery (`[whispers]`, `[laughs]`, `[sighs]`), and a tag describes the voice
  (`[low, calm voice]`), never a sound the voice could read out. Keep tags out of a line whose words must be exact.
- **A pronunciation** that keeps coming out wrong (a brand, a foreign name) may be written in IPA between slashes
  (`/ˌbaɪoʊˈkemɪstri/`).
- **The pace:** a voice runs at its own pace, 2.5 to 3.8 words a second. Record first, then time the video to it:
  `tm organic vo-sync` compares the recorded lines with the pack and the take's cuts, and holds the voice to
  `qa.wps_min`.

## When another model

- **`eleven_multilingual_v2`**: Refresh an ad's line pasted in among the original's sentences (it keeps their pace),
  or any line that needs `--speed`. 1 credit a character; no `language_code`.
- **`eleven_flash_v2_5`**: only on the user's request (the lowest latency, 0.5 credits a character); its read is
  flatter.
