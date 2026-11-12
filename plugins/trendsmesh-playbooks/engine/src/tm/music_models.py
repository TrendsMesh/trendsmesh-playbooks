"""ElevenLabs Music: each model's price per second, and the composition plan each model takes (#93).

Read by `tm tool elevenlabs music-compose` (the plan's shape is checked before anything is sent; a take whose cost
ElevenLabs does not report is booked at its measured length times the rate), by Create an ad's plan check and its
paid-call guard (a music line costs at least its seconds at the rate), and by `tm ad prices` (the dated price file a
plan line names). Checked on 2026-11-12 against https://elevenlabs.io/pricing (the credits FAQ),
https://elevenlabs.io/docs/capabilities/music and .../api-reference/music/compose.

- Credits per second: the docs say "Eleven Music 900 credits per minute" (15 a second) and call it approximate, with
  no rate per model. Refresh an ad's takes on 2026-11-05 cost about that (220 credits for 14.5 s). The owner's live
  run of Create an ad on 0.12.0 was billed about 1,550 credits for one 20 s `music_v2_5` take, 77.5 a second: five
  times the docs. The billed rate is the one used, and a model not listed is priced at the highest rate listed, so
  an estimate is never below what ElevenLabs charges.
- The plan: `music_v2` and `music_v2_5` take `{"chunks": [...]}`, each chunk either generated
  (`{"text", "duration_ms" (3,000 to 120,000), "positive_styles": [...], "negative_styles"?, "context_adherence"?,
  "conditioning_ref"?, "condition_strength"?}`) or an audio reference into an upload (`{"song_id", "range":
  {"start_ms", "end_ms"}}`). `music_v1` takes `{"positive_global_styles", "negative_global_styles", "sections":
  [{"section_name", "positive_local_styles", "negative_local_styles", "duration_ms", "lines"}]}`. A plan of the other
  shape is refused by ElevenLabs (422 "Invalid type of composition_plan"), so it is refused here before it is sent.
"""

from __future__ import annotations

import math

DEFAULT = "music_v2_5"
CHECKED = "2026-11-12"
DOCS_RATE = 15.0          # "900 credits per minute": the docs' approximate rate, below what was billed
CHUNK_MS = (3000, 120000)

RATES: dict[str, tuple[float, str]] = {   # model -> (credits a second, where the rate comes from)
    "music_v2_5": (77.5, "billed about 1,550 credits for a 20 s take in the owner's live run (0.12.0)"),
}
OTHER = max(rate for rate, _ in RATES.values())   # a model not listed: the highest rate listed

V2_EXAMPLE = {"chunks": [{"text": "[Intro] warm, bright", "duration_ms": 10000,
                          "positive_styles": ["upbeat pop", "bright synths", "tight drums", "no vocals",
                                              "clean mix", "120 bpm"]}]}
V1_KEYS = ("positive_global_styles", "negative_global_styles", "sections")


def rate(model: str) -> float:
    """Credits a second for `model` (the highest rate listed for a model not listed)."""
    found = RATES.get(model)
    return found[0] if found else OTHER


def credits(seconds: float, model: str = DEFAULT) -> int:
    """The estimate for `seconds` of music made by `model`, rounded up to a whole credit."""
    return math.ceil(round(max(float(seconds), 0.0) * rate(model), 6))


def table() -> dict:
    """The dated price table (`tm ad prices` saves it in the run as a plan line's price file)."""
    return {"checked": CHECKED, "unit": "credits a second", "default": DEFAULT,
            "models": {m: {"credits_per_second": r, "source": why} for m, (r, why) in RATES.items()},
            "other_models": OTHER, "docs_rate": DOCS_RATE,
            "docs": ["https://elevenlabs.io/pricing", "https://elevenlabs.io/docs/capabilities/music"]}


def _ms(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _styles(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)


def _ref(chunk: object) -> bool:
    if not isinstance(chunk, dict) or not isinstance(chunk.get("song_id"), str) or not chunk["song_id"].strip():
        return False
    span = chunk.get("range")
    return isinstance(span, dict) and _ms(span.get("start_ms")) and _ms(span.get("end_ms")) \
        and 0 <= span["start_ms"] < span["end_ms"]


def _v2(model: str) -> bool:
    return model.startswith("music_v2")


def plan_problems(plan: object, model: str = DEFAULT) -> list[str]:
    """What is wrong with `plan` for `model`, in words; [] when ElevenLabs takes its shape. A model this table does
    not know the shape of is not checked."""
    if not isinstance(plan, dict):
        return ["The composition plan must be one JSON object."]
    if _v2(model):
        if any(k in plan for k in V1_KEYS) or "chunks" not in plan:
            return [f"{model} takes a plan of chunks, {{\"chunks\": [...]}}, not music_v1's positive_global_styles "
                    "and sections."]
        chunks = plan.get("chunks")
        if not (isinstance(chunks, list) and chunks):
            return ["The plan's chunks must be a list of at least one chunk."]
        out = []
        for n, ch in enumerate(chunks, 1):
            if isinstance(ch, dict) and "song_id" in ch:
                if not _ref(ch):
                    out.append(f"Chunk {n} points into an upload: it needs song_id and range {{start_ms, end_ms}}.")
                continue
            if not (isinstance(ch, dict) and isinstance(ch.get("text"), str) and _styles(ch.get("positive_styles"))
                    and ch["positive_styles"]):
                out.append(f"Chunk {n} needs text and positive_styles (a list of styles).")
                continue
            if not (_ms(ch.get("duration_ms")) and CHUNK_MS[0] <= ch["duration_ms"] <= CHUNK_MS[1]):
                out.append(f"Chunk {n}'s duration_ms must be a whole number from {CHUNK_MS[0]} to {CHUNK_MS[1]}.")
            if "negative_styles" in ch and not _styles(ch["negative_styles"]):
                out.append(f"Chunk {n}'s negative_styles must be a list of styles.")
            if ch.get("conditioning_ref") is not None and not _ref(ch["conditioning_ref"]):
                out.append(f"Chunk {n}'s conditioning_ref needs song_id and range {{start_ms, end_ms}}.")
        return out
    if model == "music_v1":
        if "chunks" in plan:
            return ["music_v1 takes positive_global_styles, negative_global_styles and sections, not chunks (that "
                    "is music_v2's and music_v2_5's shape)."]
        sections = plan.get("sections")
        if not (_styles(plan.get("positive_global_styles")) and _styles(plan.get("negative_global_styles"))
                and isinstance(sections, list) and sections):
            return ["music_v1's plan needs positive_global_styles, negative_global_styles and sections."]
        return [f"Section {n} needs section_name, its styles, lines and duration_ms from {CHUNK_MS[0]} to "
                f"{CHUNK_MS[1]}." for n, sec in enumerate(sections, 1)
                if not (isinstance(sec, dict) and isinstance(sec.get("section_name"), str)
                        and _styles(sec.get("positive_local_styles")) and _styles(sec.get("negative_local_styles"))
                        and isinstance(sec.get("lines"), list) and _ms(sec.get("duration_ms"))
                        and CHUNK_MS[0] <= sec["duration_ms"] <= CHUNK_MS[1])]
    return []


def plan_seconds(plan: object) -> float:
    """How long the take of `plan` is: its chunks (generated, and the ranges kept from an upload) or its sections."""
    if not isinstance(plan, dict):
        return 0.0
    total = 0
    for ch in plan.get("chunks") or plan.get("sections") or []:
        if not isinstance(ch, dict):
            continue
        if _ms(ch.get("duration_ms")):
            total += ch["duration_ms"]
        elif _ref(ch):
            total += ch["range"]["end_ms"] - ch["range"]["start_ms"]
    return total / 1000
