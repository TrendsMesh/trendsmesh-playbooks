"""ElevenLabs text-to-speech models: the default, each model's credit rate, and what each request may carry (#88).

Read by `tm tool elevenlabs tts` (the model, `language_code`, `speed`) and by organic video's pack check (the
voiceover's credits: its characters at the chosen model's rate). The ids, rates and limits come from the model
registry (`data/models/registry.yaml`, `tm.model_registry`, #115); the notes below say where they come from. Checked
against ElevenLabs' docs on 2026-11-12:
https://elevenlabs.io/docs/overview/models, .../capabilities/text-to-speech/eleven-v4,
.../api-reference/text-to-speech/convert and https://elevenlabs.io/pricing (the credits FAQ).

- Eleven v4 (`eleven_v4`) is the default in every playbook. Refresh an ad picks `eleven_multilingual_v2` for a
  line that sits among the original's own sentences: it keeps the original's pace, and v4 spoke 10 to 43% slower
  (refresh-ad `references/variants.md` section 3).
- Credits per character: the docs say Multilingual v2 is 1 credit a character and Flash v2.5 costs "50% lower price
  per character"; for v4 they say only that it "uses the same credit pricing as our other Text to Speech models",
  with no number. The v4 rate here is the one ElevenLabs billed (its `character-cost` header) in the owner's live
  run on 0.11.0: 105 credits for 214 characters and 231 for 473, 0.5 a character. A model not listed here is priced
  at the docs' general "1 credit per character", the higher rate.
- `language_code` (ISO 639-1, ISO 639-3 for a few): "This parameter is not supported for multilingual_v2 models"; any
  other model takes it, and one that does not support the given language ignores it.
- Speed: "Style and Speed sliders are not available in Eleven v4", so a v4 request sends no `speed`, and a speed
  other than 1.0 is refused before anything is sent (record with `eleven_multilingual_v2` to set a speed).
- Speech to text (Scribe, `scribe_v3`, the docs' model for recorded audio) and the Voice Changer (speech to speech,
  `eleven_multilingual_sts_v2`) are billed by the minute of audio: the pricing page's credits FAQ, read 2026-11-12,
  gives 330 credits a minute for Speech to Text and 1,000 for the Voice Changer ("approximate"). An estimate is the
  audio's minutes at that rate, rounded up to a whole credit (`scribe_credits`, `sts_credits`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from tm import model_registry

DEFAULT = model_registry.star("voiceover")["model"]   # Eleven v4, the registry's selected voiceover (#88, #115)
KEEPS_PACE = "eleven_multilingual_v2"   # Refresh an ad: a line among the original's sentences
GENERAL_RATE = 1.0                      # the docs' "1 credit per character", for a model not listed
CHECKED = model_registry.price(DEFAULT, "default")["checked"]


@dataclass(frozen=True)
class Model:
    credits_per_char: float
    language_code: bool    # the request may carry `language_code`
    speed: bool            # `voice_settings.speed` is honoured
    source: str


def _models() -> dict[str, Model]:
    """The registry's text-to-speech models (an ElevenLabs model priced per character): the rate and what a request
    may carry, from its `cannot` (`language_code`, `speed`)."""
    out = {}
    for mid in model_registry.ids(provider="elevenlabs"):
        price = model_registry.price(mid, "default")
        if price.get("per") != "character":
            continue
        limits = model_registry.cannot(mid)
        out[mid] = Model(float(price["credits"]), "language_code" not in limits, "speed" not in limits,
                         f"the model registry, checked {price['checked']}")
    return out


MODELS: dict[str, Model] = _models()
assert KEEPS_PACE in MODELS, "the model registry has no eleven_multilingual_v2"


def known(model: str) -> bool:
    return model in MODELS


def rate(model: str) -> float:
    """Credits per character for `model` (the general 1 for a model not listed)."""
    found = MODELS.get(model)
    return found.credits_per_char if found else GENERAL_RATE


def credits(text: str, model: str = DEFAULT) -> float:
    """The estimate for one take of `text`: its characters at the model's rate (as the pack's cost line prices it)."""
    return round(len(text) * rate(model), 2)


def takes_language(model: str) -> bool:
    found = MODELS.get(model)
    return found.language_code if found else not model.startswith("eleven_multilingual")


def takes_speed(model: str) -> bool:
    found = MODELS.get(model)
    return found.speed if found else True


SCRIBE_MODEL = model_registry.star("transcription")["model"]
STS_MODEL = model_registry.star("voice_changer")["model"]
SCRIBE_PER_MINUTE = int(model_registry.price(SCRIBE_MODEL, "default")["credits"])
STS_PER_MINUTE = int(model_registry.price(STS_MODEL, "default")["credits"])


def _per_minute(seconds: float, rate: int) -> int:
    return max(1, math.ceil(max(0.0, seconds) / 60 * rate))


def scribe_credits(seconds: float) -> int:
    """The estimate for Scribe on `seconds` of audio."""
    return _per_minute(seconds, SCRIBE_PER_MINUTE)


def sts_credits(seconds: float) -> int:
    """The estimate for the Voice Changer on `seconds` of audio."""
    return _per_minute(seconds, STS_PER_MINUTE)
