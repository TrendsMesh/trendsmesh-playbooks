"""tm.brand: the brand profile every playbook can reuse (library/brands/<slug>/brand_vNN.json)."""

import copy
import json
from datetime import date

import pytest

from tm import brand, manifest
from tm.cli import main
from tm.runfolder import RunFolder

PROFILE = {
    "schema": "brand/1", "kind": "brand", "brand": "Night School",
    "stands_for": "Sleep better with a calm evening routine.",
    "tone": ["warm", "plain", "dry"],
    "off_limits": ["medical claims"], "off_limits_asked": True,
    "claims": [{"claim": "Read in 20 minutes", "wording": "A 20-minute read",
                "source": "00_raw/landing_nightschool.md"}],
    "competitors": ["Calm"], "guide": {"source": "none", "where": ""},
    "drafted_from": ["landing", "user"], "confirmed": None,
}


def _profile(**over):
    p = copy.deepcopy(PROFILE)
    p.update(over)
    return p


def _fields(problems):
    return [p.field for p in problems]


def test_a_good_profile_has_no_problems():
    assert brand.check(_profile()) == []


@pytest.mark.parametrize("tone", [["warm", "plain"], ["a", "b", "c", "d"], [], "warm plain dry", ["warm", "plain", ""],
                                  ["warm", "plain", "very dry"]])
def test_tone_needs_three_words(tone):
    assert "tone" in _fields(brand.check(_profile(tone=tone)))


@pytest.mark.parametrize("text", ["Skincare for real life, e.g. busy mornings.", "No. 1 for dry skin.",
                                  "Sleep, i.e. real sleep, vs. pills, etc. Done right.".replace("Done", "done"),
                                  'We say "calm evenings."', "Calm evenings (really)?", "Dr. Smith approves of sleep!"])
def test_stands_for_accepts_one_sentence(text):
    assert "stands_for" not in _fields(brand.check(_profile(stands_for=text)))


@pytest.mark.parametrize("text", ["One. Two.", "Calm evenings! Better sleep.", "We care. You glow.", "Why? Because.",
                                  'We care. "You glow."', "", "No stop at the end"])
def test_stands_for_is_one_sentence(text):
    assert "stands_for" in _fields(brand.check(_profile(stands_for=text)))


def test_names_sharing_a_slug_keep_their_own_profiles(tmp_path):
    brand.save(tmp_path, _profile(brand="A&B"), run=None)
    assert brand.latest(tmp_path, "A B") is None
    brand.save(tmp_path, _profile(brand="A B", stands_for="Other things."), run=None)
    assert brand.latest(tmp_path, "A&B")["stands_for"] == PROFILE["stands_for"]
    assert brand.latest(tmp_path, "A B")["stands_for"] == "Other things."


def test_second_save_with_a_run_copies_to_the_next_version(tmp_path):
    run = RunFolder.create(tmp_path, "t", date(2026, 11, 7))
    brand.save(tmp_path, _profile(), run=run)
    brand.save(tmp_path, _profile(), run=run)
    assert sorted(p.name for p in (run.path / "04_final").glob("brand_v*.json")) == ["brand_v01.json", "brand_v02.json"]


def test_claim_without_source_refused():
    for source in ("", "  ", None):
        claims = [{"claim": "Cures insomnia", "wording": "Cures it", "source": source}]
        problems = brand.check(_profile(claims=claims))
        assert "claims[0].source" in _fields(problems)
    assert "claims" in _fields(brand.check(_profile(claims={"claim": "x"})))


def test_off_limits_must_be_asked():
    assert "off_limits_asked" in _fields(brand.check(_profile(off_limits_asked=False)))
    no_key = _profile()
    del no_key["off_limits_asked"]
    assert "off_limits_asked" in _fields(brand.check(no_key))
    assert brand.check(_profile(off_limits=[])) == []     # asked, and nothing is off limits


def test_channel_kind_checked():
    """kind is read before the schema: a channel is checked against channel/1, so a brand profile
    relabelled as a channel fails on the channel's own fields, never on the brand's."""
    fields = _fields(brand.check(_profile(kind="channel")))
    assert fields[0] == "schema" and {"channel", "platforms", "context", "product_role"} <= set(fields)
    assert not {"tone", "stands_for", "off_limits_asked"} & set(fields)
    problems = brand.check(_profile(kind="shop"))
    assert _fields(problems) == ["kind"] and "brand, channel" in problems[0].todo


def test_save_never_overwrites_and_latest_reads_back(tmp_path):
    assert brand.latest(tmp_path, "Night School") is None
    first = brand.save(tmp_path, _profile(), run=None)
    second = brand.save(tmp_path, _profile(tone=["calm", "kind", "wry"]), run=None)
    assert first == tmp_path / "library" / "brands" / "night-school" / "brand_v01.json"
    assert second.name == "brand_v02.json"
    assert json.loads(first.read_text(encoding="utf-8"))["tone"] == ["warm", "plain", "dry"]   # not overwritten
    assert brand.latest(tmp_path, "Night School")["tone"] == ["calm", "kind", "wry"]
    assert brand.latest(tmp_path, "night school")["tone"] == ["calm", "kind", "wry"]
    assert brand.latest(tmp_path, "Other") is None


def test_save_refuses_a_bad_profile(tmp_path):
    with pytest.raises(ValueError, match="tone"):
        brand.save(tmp_path, _profile(tone=["a"]), run=None)
    assert not (tmp_path / "library").exists()


def test_save_with_a_run_adds_a_manifest_row_and_a_copy(tmp_path):
    run = RunFolder.create(tmp_path, "t", date(2026, 11, 7))
    saved = brand.save(tmp_path, _profile(), run=run)
    rows = [r for r in manifest.rows(run) if r["source"] == brand.SOURCE]
    assert len(rows) == 1
    assert json.loads(rows[0]["params"])["library"] == saved.relative_to(tmp_path).as_posix()
    assert json.loads((run.path / rows[0]["file"]).read_text(encoding="utf-8")) == _profile()


def test_cli_check_save_show(tmp_path, capsys):
    run = RunFolder.create(tmp_path, "t", date(2026, 11, 7))
    good, bad = tmp_path / "good.json", tmp_path / "bad.json"
    good.write_text(json.dumps(PROFILE), encoding="utf-8-sig")
    bad.write_text(json.dumps(_profile(tone=["a"], off_limits_asked=False)), encoding="utf-8")
    assert main(["brand", "check", "--file", str(good), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "done"
    assert main(["brand", "check", "--file", str(bad), "--json"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "stop" and {p["field"] for p in out["problems"]} == {"tone", "off_limits_asked"}
    assert main(["brand", "save", "--run", str(run.path), "--file", str(bad)]) == 2
    assert not (tmp_path / "library").exists()
    capsys.readouterr()
    assert main(["brand", "save", "--run", str(run.path), "--file", str(good), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["file"] == "library/brands/night-school/brand_v01.json"
    assert main(["brand", "show", "--name", "Night School", "--workspace", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["profile"]["brand"] == "Night School"
    assert main(["brand", "show", "--name", "Nobody", "--workspace", str(tmp_path)]) == 1


def test_latest_names_a_damaged_library_file(tmp_path, capsys):
    brand.save(tmp_path, _profile(), run=None)
    damaged = tmp_path / "library" / "brands" / "night-school" / "brand_v02.json"
    damaged.write_text('{"brand": "Night Sch', encoding="utf-8")
    with pytest.raises(ValueError, match="library/brands/night-school/brand_v02.json is damaged"):
        brand.latest(tmp_path, "Night School")
    assert main(["brand", "show", "--name", "Night School", "--workspace", str(tmp_path), "--json"]) == 1
    assert "brand_v02.json is damaged" in json.loads(capsys.readouterr().out)["message"]
