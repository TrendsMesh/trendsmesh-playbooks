"""Organic video's voice timing: ElevenLabs character alignment -> words -> phrases -> SRT.

`words_from_alignment` reads the `alignment` object of a `/with-timestamps` answer
({characters, character_start_times_seconds, character_end_times_seconds}) and returns
[{word, start, end}] in seconds: a word is a run of non-space characters. `phrases` joins words into
cues {text, start, end}, closing a cue after a word that ends in `, . ? ! …` and at `max_words`.
`to_srt` writes cues (phrases, or words as {word, start, end}) as SRT text with "\\n" line ends
(write it as text; `tm organic atlas-prompt --srt` takes the word SRT, one word per cue). `pace` is words per second
of speech, from the first word's start to the last word's end (the silence before and after the
voice is not speech).
"""

from __future__ import annotations

PHRASE_END = (",", ".", "?", "!", "…")
CLOSING = "\"'”’)]»"   # a closing quote or bracket after the punctuation (`dziecka."`, `krzyczy.”`, `(tak!)`)


def words_from_alignment(alignment: dict) -> list[dict]:
    try:
        chars = alignment["characters"]
        starts = alignment["character_start_times_seconds"]
        ends = alignment["character_end_times_seconds"]
    except (KeyError, TypeError):
        raise ValueError("The alignment needs characters, character_start_times_seconds and "
                         "character_end_times_seconds.") from None
    if not (len(chars) == len(starts) == len(ends)):
        raise ValueError("The alignment's characters and times are not the same length.")
    words: list[dict] = []
    cur: list[str] = []
    start = end = 0.0
    for ch, s, e in zip(chars, starts, ends):
        if str(ch).strip() == "":
            if cur:
                words.append({"word": "".join(cur), "start": start, "end": end})
                cur = []
            continue
        if not cur:
            start = float(s)
        cur.append(str(ch))
        end = float(e)
    if cur:
        words.append({"word": "".join(cur), "start": start, "end": end})
    return words


def phrases(words: list[dict], *, max_words: int = 5) -> list[dict]:
    if max_words < 1:
        raise ValueError("max_words must be at least 1.")
    cues: list[dict] = []
    group: list[dict] = []
    for w in words:
        group.append(w)
        if w["word"].rstrip(CLOSING).endswith(PHRASE_END) or len(group) >= max_words:
            cues.append(_cue(group))
            group = []
    if group:
        cues.append(_cue(group))
    return cues


def _cue(group: list[dict]) -> dict:
    return {"text": " ".join(w["word"] for w in group), "start": group[0]["start"], "end": group[-1]["end"]}


def _stamp(seconds: float) -> str:
    ms = round(max(seconds, 0.0) * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: list[dict]) -> str:
    blocks = []
    for i, cue in enumerate(cues, 1):
        text = cue["text"] if "text" in cue else cue["word"]
        blocks.append(f"{i}\n{_stamp(cue['start'])} --> {_stamp(cue['end'])}\n{text}\n")
    return "\n".join(blocks)


def pace(words: list[dict]) -> float:
    if not words:
        return 0.0
    span = words[-1]["end"] - words[0]["start"]
    return len(words) / span if span > 0 else 0.0
