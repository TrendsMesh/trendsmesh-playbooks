"""tm.brand for organic video: channel profiles (`channel/1`, library/channels/<slug>/channel_vNN.json),
a store's catalogue in its brand profile, packshots made once per store, and the A1 step check."""

import copy
import json
from datetime import date

import pytest

from exampleedu import PROFILE as EXAMPLEEDU   # a made-up channel profile, typed as channel/1
from tm import brand, brief_config, config, flow, manifest, organic_config, state
from tm.cli import main
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder

STORE = {
    "schema": "brand/1", "kind": "brand", "brand": "Pet Store",
    "stands_for": "Calm, healthy pets at home.", "tone": ["warm", "plain", "dry"],
    "off_limits": [], "off_limits_asked": True, "claims": [], "competitors": [],
    "guide": {"source": "none", "where": ""}, "drafted_from": ["landing"], "confirmed": None,
    "catalog": {"products": [{"name": "Cat fountain", "packshot": None, "problems": ["cats drink too little"]},
                             {"name": "Lick mat", "packshot": None, "problems": []}]},
}


def _channel(**over):
    p = copy.deepcopy(EXAMPLEEDU)
    for key, value in over.items():
        if key in p and isinstance(p[key], dict) and isinstance(value, dict):
            p[key].update(value)
        else:
            p[key] = value
    return p


def _fields(problems):
    return [p.field for p in problems]


@pytest.fixture
def ws(tmp_path, monkeypatch):
    folder = tmp_path / "ws"
    folder.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(folder))
    return folder


TODAY = date(2026, 11, 7)


class _Today(date):
    @classmethod
    def today(cls):
        return TODAY


@pytest.fixture
def today(monkeypatch):
    """`brand.save(confirmed=True)` dates the profile TODAY (a fixed date: the clock would split the save and the
    assert around midnight)."""
    monkeypatch.setattr(brand, "date", _Today)
    return TODAY.isoformat()


def _run(ws, channels=("exampleedu",), name="exampleedu"):
    run = RunFolder.create(ws, name, date(2026, 11, 7), playbook=ORGANIC_VIDEO)
    config.save(run, {**organic_config.defaults(), "channels": list(channels)})
    return run


def _decide_profile(run):
    flow.set_level(run, "every_step")
    s = state.load(run)
    s.outputs = ["proposals"]
    s.decisions.append({"checkin": "profile", "choice": "accept", "by": "user", "at": "2026-11-07T10:00:00+00:00"})
    state.save(run, s)


def _cli(capsys, *argv):
    capsys.readouterr()
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


# --- the channel/1 check --------------------------------------------------------------

def test_exampleedu_profile_v02_passes(ws):
    assert brand.check(EXAMPLEEDU, workspace=ws) == []
    assert brand.check(EXAMPLEEDU) == []        # nothing sold: no library to read


@pytest.mark.parametrize("field", ["films", "topic", "audience"])
@pytest.mark.parametrize("value", ["", "   ", None])
def test_bubble_required(field, value):
    """The bubble the trend search starts from (OV1): what the channel films, about what, for whom."""
    problems = brand.check(_channel(context={field: value}))
    assert _fields(problems) == [f"context.{field}"]
    assert "context" in _fields(brand.check(_channel(context="parents and games")))


def test_channel_fields_checked():
    assert _fields(brand.check(_channel(schema="brand/1"))) == ["schema"]
    assert _fields(brand.check(_channel(channel=" "))) == ["channel"]
    for platforms in ([], ["tiktok", "snapchat"], "tiktok", ["tiktok", "tiktok"]):
        assert _fields(brand.check(_channel(platforms=platforms))) == ["platforms"], platforms
    assert brand.check(_channel(platforms=["instagram"])) == []
    assert _fields(brand.check(_channel(account_type="brand"))) == ["account_type"]
    assert brand.check(_channel(account_type="business")) == []
    assert _fields(brand.check(_channel(audience_language=""))) == ["audience_language"]
    assert _fields(brand.check(_channel(product_role="shown"))) == ["product_role"]
    assert _fields(brand.check(_channel(content_rules="none"))) == ["content_rules"]
    assert _fields(brand.check(_channel(assumptions=[""]))) == ["assumptions"]
    assert _fields(brand.check(_channel(confirmed="7 Nov"))) == ["confirmed"]
    assert _fields(brand.check(_channel(voice=None))) == ["voice"]
    assert _fields(brand.check(_channel(music={"folder": 3}))) == ["music"]
    assert _fields(brand.check(_channel(context={"performed_links": "x"}))) == ["context.performed_links"]


@pytest.mark.parametrize("role", ["incidental", "featured", "soft_mention", "hero"])
def test_nothing_sold_means_not_shown(role):
    problems = brand.check(_channel(product_role=role))
    assert _fields(problems) == ["product_role"]
    assert "not_shown" in problems[0].todo
    assert brand.check(_channel(product_role="not_shown")) == []


def test_two_channels_share_one_catalogue(ws):
    a = _channel(channel="Cat Corner", store="Pet Store", product_role="featured")
    b = _channel(channel="Dog Days", store="pet store", product_role="hero")
    for profile in (a, b):
        problems = brand.check(profile, workspace=ws)
        assert _fields(problems) == ["store"] and profile["store"] in problems[0].what   # no saved store yet
    brand.save(ws, {**STORE, "catalog": {"products": []}}, run=None)
    assert "no products" in brand.check(a, workspace=ws)[0].what
    brand.save(ws, STORE, run=None)
    assert brand.check(a, workspace=ws) == [] and brand.check(b, workspace=ws) == []
    brand.save(ws, a, run=None)
    brand.save(ws, b, run=None)
    assert brand.latest(ws, "Cat Corner", kind="channel")["store"] == "Pet Store"
    assert brand.latest(ws, "Dog Days", kind="channel")["store"] == "pet store"
    assert sorted(p.name for p in (ws / "library" / "channels").iterdir()) == ["cat-corner", "dog-days"]
    assert [p.name for p in (ws / "library" / "brands").iterdir()] == ["pet-store"]   # one catalogue
    with pytest.raises(ValueError, match="workspace"):
        brand.check(a)   # a named store is checked against the library


def test_catalogue_checked_in_a_brand_profile():
    assert brand.check(STORE) == []
    no_catalog = copy.deepcopy(STORE)
    del no_catalog["catalog"]
    assert brand.check(no_catalog) == []           # optional
    for catalog, field in (([], "catalog"), ({"products": "fountain"}, "catalog"),
                           ({"products": [{"name": "", "packshot": None, "problems": []}]}, "catalog.products[0].name"),
                           ({"products": [{"name": "A", "packshot": 3, "problems": []}]}, "catalog.products[0].packshot"),
                           ({"products": [{"name": "A", "packshot": None, "problems": "x"}]},
                            "catalog.products[0].problems"),
                           ({"products": [{"name": "A", "packshot": None, "problems": []},
                                          {"name": "a", "packshot": None, "problems": []}]},
                            "catalog.products[1].name")):
        assert _fields(brand.check({**STORE, "catalog": catalog})) == [field], catalog


def test_channel_kind_saved_under_channels(ws):
    run = _run(ws)
    first = brand.save(ws, EXAMPLEEDU, run=run)
    second = brand.save(ws, _channel(platforms=["tiktok"]), run=run)
    assert first == ws / "library" / "channels" / "exampleedu" / "channel_v01.json"
    assert second.name == "channel_v02.json"
    assert json.loads(first.read_text(encoding="utf-8")) == EXAMPLEEDU       # never overwritten
    assert brand.latest(ws, "exampleedu", kind="channel")["platforms"] == ["tiktok"]
    assert brand.latest(ws, "ExampleEdu") is None                          # not a brand
    assert sorted(p.name for p in (run.path / "04_final").glob("channel_v*.json")) == [
        "channel_v01.json", "channel_v02.json"]
    rows = [r for r in manifest.rows(run) if r["source"] == brand.SOURCE]
    assert json.loads(rows[0]["params"])["library"] == "library/channels/exampleedu/channel_v01.json"


# --- confirmed by the user --------------------------------------------------------------

def test_confirmed_needs_user_decision(ws, today):
    run = _run(ws)
    message = "A channel's profile is confirmed by the user."
    with pytest.raises(ValueError, match=message):
        brand.save(ws, EXAMPLEEDU, run=None, confirmed=True)
    with pytest.raises(ValueError, match=message):
        brand.save(ws, EXAMPLEEDU, run=run, confirmed=True)          # no profile decision yet
    s = state.load(run)
    s.decisions.append({"checkin": "profile", "choice": "accept", "by": "rule", "note": "x", "at": "t"})
    state.save(run, s)
    with pytest.raises(ValueError, match=message):
        brand.save(ws, EXAMPLEEDU, run=run, confirmed=True)          # by rule is not the user's
    with pytest.raises(ValueError, match=message):
        brand.save(ws, _channel(confirmed="2026-11-07"), run=run)   # the agent cannot write the date
    assert not (ws / "library").exists()
    _decide_profile(run)
    saved = brand.save(ws, EXAMPLEEDU, run=run, confirmed=True)
    assert json.loads(saved.read_text(encoding="utf-8"))["confirmed"] == today
    assert EXAMPLEEDU["confirmed"] is None                             # the caller's dict is untouched
    # a later version may carry the date the saved profile already has (a voice id added later)
    later = brand.save(ws, _channel(confirmed=today,
                                    voice={"narrator_elevenlabs_id": "v1"}), run=None)
    assert json.loads(later.read_text(encoding="utf-8"))["confirmed"] == today
    with pytest.raises(ValueError, match=message):
        brand.save(ws, _channel(confirmed="2026-01-01"), run=None)


def test_cli_save_confirmed_and_show_channel(ws, capsys, today):
    run = _run(ws)
    (run.path / "03_wip" / "channel_exampleedu_v01.json").write_text(json.dumps(EXAMPLEEDU), encoding="utf-8")
    code, out = _cli(capsys, "brand", "save", "--run", str(run.path), "--file", "03_wip/channel_exampleedu_v01.json",
                     "--confirmed")
    assert code == 1 and "confirmed by the user" in out["message"]
    _decide_profile(run)
    code, out = _cli(capsys, "brand", "save", "--run", str(run.path), "--file", "03_wip/channel_exampleedu_v01.json",
                     "--confirmed")
    assert code == 0 and out["file"] == "library/channels/exampleedu/channel_v01.json"
    code, out = _cli(capsys, "brand", "show", "--name", "ExampleEdu", "--kind", "channel")
    assert code == 0 and out["profile"]["confirmed"] == today
    code, out = _cli(capsys, "brand", "check", "--run", str(run.path), "--file", "03_wip/channel_exampleedu_v01.json")
    assert code == 0 and "channel profile" in out["message"]
    bad = run.path / "03_wip" / "channel_exampleedu_v02.json"
    bad.write_text(json.dumps(_channel(context={"films": ""})), encoding="utf-8")
    code, out = _cli(capsys, "brand", "check", "--run", str(run.path), "--file", "03_wip/channel_exampleedu_v02.json")
    assert code == 2 and [p["field"] for p in out["problems"]] == ["context.films"]
    assert out["message"].startswith("The channel profile needs fixing")


# --- packshots ---------------------------------------------------------------------------

def test_packshot_saved_once_per_store_never_overwrites(ws, capsys):
    brand.save(ws, STORE, run=None)
    run = _run(ws, channels=("cat-corner",), name="cats")
    shot = run.path / "00_raw" / "fountain.png"
    shot.write_bytes(b"\x89PNG first")
    code, out = _cli(capsys, "brand", "packshot", "--name", "Pet Store", "--product", "Cat fountain",
                     "--file", "00_raw/fountain.png", "--run", str(run.path))
    assert code == 0, out
    first = ws / "library" / "brands" / "pet-store" / "packshots" / "cat-fountain_v01.png"
    assert out["file"] == "library/brands/pet-store/packshots/cat-fountain_v01.png"
    assert first.read_bytes() == b"\x89PNG first"
    saved = brand.latest(ws, "Pet Store")
    assert [p["packshot"] for p in saved["catalog"]["products"]] == [out["file"], None]
    assert (ws / "library" / "brands" / "pet-store" / "brand_v02.json").is_file()

    other = RunFolder.create(ws, "dogs", date(2026, 11, 7), playbook=ORGANIC_VIDEO)   # another channel, same store
    (other.path / "00_raw" / "fountain.png").write_bytes(b"\x89PNG second")
    code, out = _cli(capsys, "brand", "packshot", "--name", "pet store", "--product", "cat FOUNTAIN",
                     "--file", "00_raw/fountain.png", "--run", str(other.path))
    assert code == 0 and out["file"].endswith("cat-fountain_v02.png")
    assert first.read_bytes() == b"\x89PNG first"                       # never overwritten
    assert brand.latest(ws, "Pet Store")["catalog"]["products"][0]["packshot"] == out["file"]
    assert not (ws / "library" / "channels").exists()                   # per store, not per channel
    rows = [r for r in manifest.rows(other) if r["source"] == brand.PACKSHOT_SOURCE]
    assert len(rows) == 1 and rows[0]["file"] == "00_raw/fountain.png"
    assert json.loads(rows[0]["params"])["library"] == out["file"]

    code, out = _cli(capsys, "brand", "packshot", "--name", "Pet Store", "--product", "Scratcher",
                     "--file", "00_raw/fountain.png", "--run", str(run.path))
    assert code == 2 and out["status"] == "stop" and "Cat fountain, Lick mat" in out["message"]   # a missing input
    code, out = _cli(capsys, "brand", "packshot", "--name", "Toy Shop", "--product", "Ball",
                     "--file", "00_raw/fountain.png", "--run", str(run.path))
    assert code == 2 and "tm brand save" in out["message"] and "continues from the same place" in out["message"]
    outside = ws / "fountain.png"
    outside.write_bytes(b"\x89PNG")
    code, out = _cli(capsys, "brand", "packshot", "--name", "Pet Store", "--product", "Lick mat",
                     "--file", str(outside), "--run", str(run.path))
    assert code == 1 and "inside the run" in out["message"]
    (run.path / "00_raw" / "notes.txt").write_text("x", encoding="utf-8")
    code, out = _cli(capsys, "brand", "packshot", "--name", "Pet Store", "--product", "Lick mat",
                     "--file", "00_raw/notes.txt", "--run", str(run.path))
    assert code == 1 and "image" in out["message"]
    assert sorted(p.name for p in first.parent.iterdir()) == ["cat-fountain_v01.png", "cat-fountain_v02.png"]


# --- the A1 step check ----------------------------------------------------------------------

def test_profile_written_reads_the_run_channels(ws):
    run = _run(ws, channels=("exampleedu",))
    before = (run.path / "run.json").read_text(encoding="utf-8")
    gap = brand.channel_gap(run)
    assert "exampleedu" in gap and "tm brand save" in gap
    brand.save(ws, EXAMPLEEDU, run=None)
    assert brand.channel_gap(run) is None
    assert (run.path / "run.json").read_text(encoding="utf-8") == before       # reads only

    two = _run(ws, channels=("exampleedu", "cat-corner"), name="two")
    assert "cat-corner" in brand.channel_gap(two)
    brand.save(ws, STORE, run=None)
    brand.save(ws, _channel(channel="Cat Corner", store="Pet Store", product_role="featured"), run=None)
    assert brand.channel_gap(two) is None

    none = _run(ws, channels=(), name="none")
    assert "channels" in brand.channel_gap(none)
    damaged = ws / "library" / "channels" / "exampleedu" / "channel_v02.json"
    damaged.write_text("{", encoding="utf-8")
    assert "damaged" in brand.channel_gap(run)


def test_packshot_at_the_run_root_is_kept_in_00_raw(ws, capsys):
    brand.save(ws, STORE, run=None)
    run = _run(ws, channels=("cat-corner",), name="cats")
    (run.path / "fountain.png").write_bytes(b"\x89PNG root")
    (run.path / "00_raw" / "fountain.png").write_bytes(b"\x89PNG older")     # never overwritten
    code, out = _cli(capsys, "brand", "packshot", "--name", "Pet Store", "--product", "Cat fountain",
                     "--file", "fountain.png", "--run", str(run.path))
    assert code == 0, out
    row = [r for r in manifest.rows(run) if r["source"] == brand.PACKSHOT_SOURCE][0]
    assert (row["file"], row["stage"]) == ("00_raw/fountain_v02.png", "00_raw")
    assert (run.path / "00_raw" / "fountain_v02.png").read_bytes() == b"\x89PNG root"
    assert (run.path / "00_raw" / "fountain.png").read_bytes() == b"\x89PNG older"


# --- one key per channel, and the kind checked on read ------------------------------------------

def test_channel_found_by_its_key(ws, capsys):
    """config.yaml names channels by key; "Cat Corner" is cat-corner in the library, the A1 check and tm brand show."""
    run = _run(ws, channels=("cat-corner",), name="cats")
    brand.save(ws, _channel(channel="Cat Corner"), run=None)
    assert (ws / "library" / "channels" / "cat-corner" / "channel_v01.json").is_file()
    assert brand.channel_gap(run) is None
    for name in ("cat-corner", "Cat Corner", "cat corner"):
        assert brand.latest(ws, name, kind="channel")["channel"] == "Cat Corner", name
    code, out = _cli(capsys, "brand", "show", "--name", "cat-corner", "--kind", "channel", "--workspace", str(ws))
    assert code == 0 and out["profile"]["channel"] == "Cat Corner"


def test_a_channel_file_is_never_read_as_a_brand(ws, capsys):
    folder = ws / "library" / "brands" / "exampleedu"
    folder.mkdir(parents=True)
    (folder / "brand_v01.json").write_text(json.dumps({**EXAMPLEEDU, "brand": "ExampleEdu"}), encoding="utf-8")
    skipped = []
    assert brand.latest(ws, "ExampleEdu", skipped=skipped) is None
    assert skipped == ["library/brands/exampleedu/brand_v01.json is not a brand profile (its kind is 'channel')"]
    code, out = _cli(capsys, "brand", "show", "--name", "ExampleEdu", "--workspace", str(ws))
    assert code == 1 and "is not a brand profile" in out["message"]
    run = _run(ws)
    gap = brief_config._brand_gap(run, "library/brands/exampleedu/brand_v01.json")   # PB02's brand.profile check
    assert "is not a brand profile (its kind is 'channel')" in gap


def test_a_brand_file_is_never_read_as_a_channel(ws, capsys):
    folder = ws / "library" / "channels" / "pet-store"
    folder.mkdir(parents=True)
    (folder / "channel_v01.json").write_text(json.dumps({**STORE, "channel": "Pet Store"}), encoding="utf-8")
    assert brand.latest(ws, "Pet Store", kind="channel") is None
    run = _run(ws, channels=("pet-store",), name="store")
    gap = brand.channel_gap(run)
    assert "library/channels/pet-store/channel_v01.json is not a channel profile (its kind is 'brand')" in gap
    code, out = _cli(capsys, "brand", "show", "--name", "pet-store", "--kind", "channel", "--workspace", str(ws))
    assert code == 1 and "is not a channel profile" in out["message"]


def test_one_profile_decision_confirms_one_channel(ws):
    """In a run of two channels, each channel's confirmation needs its own decision, naming its key."""
    run = _run(ws, channels=("cat-corner", "dog-days"), name="two")
    cats, dogs = _channel(channel="Cat Corner"), _channel(channel="Dog Days")
    _decide_profile(run)                                              # no note: which channel is unknown
    for profile in (cats, dogs):
        with pytest.raises(ValueError, match="confirmed by the user"):
            brand.save(ws, profile, run=run, confirmed=True)
    s = state.load(run)
    s.decisions.append({"checkin": "profile", "choice": "accept", "by": "user", "note": "Cat Corner: cat-corner",
                        "change": True, "at": "2026-11-07T10:05:00+00:00"})
    state.save(run, s)
    assert json.loads(brand.save(ws, cats, run=run, confirmed=True).read_text(encoding="utf-8"))["confirmed"]
    with pytest.raises(ValueError, match="confirmed by the user"):
        brand.save(ws, dogs, run=run, confirmed=True)
    s = state.load(run)
    s.decisions.append({"checkin": "profile", "choice": "accept", "by": "user", "note": "dog-days",
                        "change": True, "at": "2026-11-07T10:06:00+00:00"})
    state.save(run, s)
    assert json.loads(brand.save(ws, dogs, run=run, confirmed=True).read_text(encoding="utf-8"))["confirmed"]


def test_a_channel_key_with_diacritics_is_confirmed_by_its_note(ws):
    """Polish channels: "Kącik Kota" keys to kącik-kota, and a note naming that key confirms it."""
    run = _run(ws, channels=("kącik-kota", "dog-days"), name="two")
    kot = _channel(channel="Kącik Kota")
    _decide_profile(run)
    s = state.load(run)
    s.decisions.append({"checkin": "profile", "choice": "accept", "by": "user", "note": "Kącik Kota: kącik-kota",
                        "change": True, "at": "2026-11-07T10:05:00+00:00"})
    state.save(run, s)
    assert json.loads(brand.save(ws, kot, run=run, confirmed=True).read_text(encoding="utf-8"))["confirmed"]
    with pytest.raises(ValueError, match="confirmed by the user"):
        brand.save(ws, _channel(channel="Dog Days"), run=run, confirmed=True)
