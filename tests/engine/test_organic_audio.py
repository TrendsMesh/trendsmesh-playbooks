"""organic_audio: character alignment -> words -> phrases -> SRT, and the voice pace."""

import pytest

from tm import organic_audio as oa


def alignment(text, step=0.1, gap=0.0):
    """A /with-timestamps alignment for `text`: every character `step` seconds long."""
    return {"characters": list(text),
            "character_start_times_seconds": [round(gap + i * step, 3) for i in range(len(text))],
            "character_end_times_seconds": [round(gap + (i + 1) * step, 3) for i in range(len(text))]}


def test_words_from_alignment_splits_at_spaces():
    words = oa.words_from_alignment(alignment("Co dziecko widzi tam"))
    assert [w["word"] for w in words] == ["Co", "dziecko", "widzi", "tam"]
    assert words[0] == {"word": "Co", "start": 0.0, "end": 0.2}
    assert words[1]["start"] == pytest.approx(0.3) and words[1]["end"] == pytest.approx(1.0)


def test_words_from_alignment_refuses_a_broken_alignment():
    with pytest.raises(ValueError):
        oa.words_from_alignment({"characters": ["a"]})
    with pytest.raises(ValueError):
        oa.words_from_alignment({"characters": ["a", "b"], "character_start_times_seconds": [0],
                                 "character_end_times_seconds": [1]})


def test_phrases_split_at_punctuation_and_five_words():
    text = "Co daje dziecku nowa gra, którą lubi. Jeden dwa trzy cztery pięć sześć siedem? Tak…"
    cues = oa.phrases(oa.words_from_alignment(alignment(text)))
    assert [c["text"] for c in cues] == [
        "Co daje dziecku nowa gra,",               # the comma
        "którą lubi.",                             # the full stop
        "Jeden dwa trzy cztery pięć",              # five words
        "sześć siedem?", "Tak…"]
    assert cues[0]["start"] == 0.0 and cues[1]["start"] > cues[0]["end"] - 0.001
    assert [c["text"] for c in oa.phrases(oa.words_from_alignment(alignment("a b c d")), max_words=2)] == ["a b", "c d"]


def test_a_phrase_ends_past_a_closing_quote_or_bracket():
    """Task 14 M1: punctuation inside a closing quote or bracket still ends the phrase."""
    text = 'Mówi: „dziecka." Ona krzyczy.” (tak!) «cóż?» [koniec.] dalej \'raz,\' dwa'
    cues = oa.phrases(oa.words_from_alignment(alignment(text)))
    assert [c["text"] for c in cues] == ['Mówi: „dziecka."', "Ona krzyczy.”", "(tak!)", "«cóż?»", "[koniec.]",
                                         "dalej 'raz,'", "dwa"]
    assert [c["text"] for c in oa.phrases(oa.words_from_alignment(alignment("a) b» c")))] == ["a) b» c"]


def test_to_srt_text_and_timestamps():
    words = oa.words_from_alignment(alignment("Co dziecko", step=0.5))
    assert oa.to_srt(words) == ("1\n00:00:00,000 --> 00:00:01,000\nCo\n\n"
                                "2\n00:00:01,500 --> 00:00:05,000\ndziecko\n")
    cues = [{"text": "Hello, you", "start": 3661.25, "end": 3662.0}]
    assert oa.to_srt(cues) == "1\n01:01:01,250 --> 01:01:02,000\nHello, you\n"
    assert oa.to_srt([]) == ""


def test_pace_is_words_per_second_of_speech():
    # 4 words spoken between 1.0 s and 3.0 s: the silence before is not speech
    words = oa.words_from_alignment(alignment("a b c d", step=0.2857142857, gap=1.0))
    assert oa.pace(words) == pytest.approx(4 / (words[-1]["end"] - 1.0))
    assert oa.pace([]) == 0.0
