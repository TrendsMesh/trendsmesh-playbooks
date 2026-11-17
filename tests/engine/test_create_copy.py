"""Create an ad (playbook 05), S8 and S9: the Meta copy's check (CA13, CA3), the accepted copy, the copy page's data
and the delivery check."""

import json

import pytest

from tm import create_copy, manifest, stepchecks
from tm.cli import main

from test_create_plan import CLAIMS, _check, _new, _write

KEY = "planner-brief-freelancers-nobody-told-me"
URL = (f"https://planner.example.com/brief?utm_source=meta&utm_medium=paid_social&utm_campaign=planner-launch"
       f"&utm_content={KEY}")


def ad(**over):
    base = {"key": KEY, "ad_name": "Planner brief tool, freelancers, nobody told me",
            "video_title": "Client briefs in three minutes", "cta": "LEARN_MORE",
            "display_link": "planner.example.com", "url": URL,
            "primary_texts": [{"text": t, "claims": ["k1"]} for t in (
                "Write a client brief in 3 minutes", "Client briefs in 3 minutes flat",
                "Your brief, ready in 3 minutes")] + [{"text": "Made for freelance designers", "claims": ["k2"]},
                                                       {"text": "Briefs your clients answer", "claims": []}],
            "descriptions": [{"text": "For freelance designers", "claims": ["k2"]}] * 5}
    base["headlines"] = [{"text": t, "claims": []} for t in
                         ("Briefs, done fast", "Your next brief", "Brief your clients", "Stop chasing briefs",
                          "Briefs without the back-and-forth")]
    base.update(over)
    return base


@pytest.fixture
def run(tmp_path):
    run = _new(tmp_path)
    assert _check(run, "claims", CLAIMS) == []
    return run


def _draft(run, *ads, v=1):
    path = _write(run, f"03_wip/copy_v{v:02d}.json", {"ads": list(ads)})
    return create_copy.check(run, path)[1]


def _fields(problems):
    return " ".join(f"{p.field}: {p.what}" for p in problems)


def test_good_copy_passes_and_s8_follows_it(run):
    assert "tm ad copy check" in stepchecks.run("ad_copy_checked", run)
    assert _draft(run, ad()) == []
    assert stepchecks.run("ad_copy_checked", run) is None
    page = create_copy.page_data(run)
    assert page["lang"] == "en" and page["language_warning"]          # no Polish table yet: English, and it says so
    assert "tm i18n export --lang pl" in page["language_warning"]
    assert page["question"] == "Do you want to change anything?"
    first = page["ads"][0]["primary_texts"]["items"][0]
    assert (first["limit"], first["keep"]) == (125, True) and first["count_text"].endswith("of 125 characters")


@pytest.mark.parametrize("over,says", [
    ({"headlines": ad()["headlines"][:4]}, "has 4 headlines, not 5"),
    ({"headlines": [{"text": "x" * 41, "claims": []}] + ad()["headlines"][1:]}, "41 characters, over the 40"),
    ({"descriptions": [{"text": "x" * 31, "claims": []}] * 5}, "31 characters, over the 30"),
    ({"primary_texts": [{"text": "Doubles your bookings in 30 days", "claims": ["k1"]}] + ad()["primary_texts"][1:]},
     "says 30, which is in none of its claims"),                                 # CA3: no invented numbers
    ({"primary_texts": [{"text": "Write a brief in 3 minutes", "claims": []}] + ad()["primary_texts"][1:]},
     "says 3, which is in none of its claims"),                                  # the number needs its claim named
    ({"primary_texts": [{"text": "Ok", "claims": ["k9"]}] + ad()["primary_texts"][1:]}, "not checked: k9"),
    ({"cta": "CLICK_HERE"}, "is not one of Meta's"),
    ({"display_link": "other.example.org"}, "is not the brand's site"),
    ({"url": "https://other.example.org/?utm_source=a&utm_medium=b&utm_campaign=c&utm_content=" + KEY},
     "does not go to the brand's site"),
    ({"url": "https://planner.example.com/?utm_source=meta"}, "lacks utm_medium, utm_campaign, utm_content"),
    ({"url": URL.replace(KEY, "other")}, "not the ad key"),
    ({"ad_name": "Ad set 1"}, "does not say what it is"),
    ({"ad_name": "Ad 3"}, "does not say what it is"),
])
def test_copy_refused(run, over, says):
    assert says in _fields(_draft(run, ad(**over)))


def test_two_ads_need_their_own_keys(run):
    assert "share a key" in _fields(_draft(run, ad(), ad()))


def _choices(run, keep_primary=(1, 2), edit=None, v=1, **extra):
    picks = {"key": KEY,
             "primary_texts": [{"n": n, "keep": n in keep_primary, **({"text": edit} if edit and n == 1 else {})}
                               for n in range(1, 6)],
             "headlines": [{"n": n, "keep": n == 1} for n in range(1, 6)],
             "descriptions": [{"n": n, "keep": False} for n in range(1, 6)]}
    picks.update(extra)
    return _write(run, f"03_wip/copy_decisions_v{v:02d}.json", {"ads": [picks], "note": "shorter, please"})


def test_the_accepted_copy_keeps_the_users_choices(run):
    assert _draft(run, ad()) == []
    rel, problems = create_copy.accept(run, _choices(run, edit="Client briefs in 3 minutes"))
    assert problems == [] and rel == "04_final/copy_v01.json"
    done = create_copy.accepted(run)
    kept = done["ads"][0]
    assert [t["text"] for t in kept["primary_texts"]] == ["Client briefs in 3 minutes",
                                                         "Client briefs in 3 minutes flat"]
    assert kept["descriptions"] == [] and len(kept["headlines"]) == 1 and done["note"] == "shorter, please"


def test_an_edit_is_checked_again(run):
    assert _draft(run, ad()) == []
    _, problems = create_copy.accept(run, _choices(run, edit="Briefs in 5 minutes, guaranteed " + "x" * 100))
    text = _fields(problems)
    assert "over the 125" in text and "says 5" in text
    assert create_copy.accepted(run) is None


def test_the_accepted_copy_keeps_a_primary_text_and_a_headline(run):
    assert _draft(run, ad()) == []
    _, problems = create_copy.accept(run, _choices(run, keep_primary=()))
    assert "keeps no primary_texts" in _fields(problems)


def test_delivery_needs_the_accepted_copy_and_the_files_in_the_manifest(run):
    assert "accepted copy" in stepchecks.run("ad_delivered", run)
    assert _draft(run, ad()) == []
    create_copy.accept(run, _choices(run))
    gap = stepchecks.run("ad_delivered", run)
    assert f"{KEY}'s video" in gap and f"{KEY}'s thumbnail" in gap
    for rel in (f"04_final/{KEY}_v01.mp4", f"04_final/{KEY}_thumb_v01.jpg"):
        _write(run, rel, {})
    assert "recorded in the manifest" in stepchecks.run("ad_delivered", run)
    for rel in (f"04_final/{KEY}_v01.mp4", f"04_final/{KEY}_thumb_v01.jpg"):
        manifest.record(run, rel, "04_final", "the edit")
    assert stepchecks.run("ad_delivered", run) is None


def test_tm_ad_copy_on_the_command_line(run, capsys):
    path = _write(run, "03_wip/copy_v01.json", {"ads": [ad(cta="NOPE")]})
    assert main(["ad", "copy", "check", "--run", str(run.path), "--file", str(path), "--json"]) == 2
    capsys.readouterr()
    path = _write(run, "03_wip/copy_v02.json", {"ads": [ad()]})
    assert main(["ad", "copy", "check", "--run", str(run.path), "--file", str(path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["page"]["ads"][0]["key"] == KEY
    assert main(["ad", "copy", "accept", "--run", str(run.path), "--file", str(_choices(run)), "--json"]) == 0


# --- CA3 beyond numbers: promises of results or availability -----------------------------------

def _one(text, claims=()):
    return ad(primary_texts=[{"text": text, "claims": list(claims)}] + ad()["primary_texts"][1:])


@pytest.mark.parametrize("text,says", [
    ("Guaranteed client approval on every brief", "promises a result (\"guarantee*\")"),
    ("Your brief tool, in stock tomorrow", "promises availability (\"in stock\")"),
    ("See results in your first week", "promises a result (\"see results\")"),
    ("Ships the same day you sign up", "promises availability (\"same day\")"),
])
def test_a_promise_no_claim_says_is_refused(run, text, says):
    assert says in _fields(_draft(run, _one(text, ["k1"])))


def test_a_promise_its_claim_says_passes(tmp_path):
    run = _new(tmp_path)
    claims = {"claims": [*CLAIMS["claims"], {"id": "k3", "text": "Every plan is available now, on the site",
                                             "source": "site", "ref": "https://planner.example.com/pricing"}]}
    assert _check(run, "claims", claims) == []
    assert _draft(run, _one("Available now for freelance designers", ["k3"])) == []
    assert "available now" in _fields(_draft(run, _one("Available now for freelance designers", ["k2"]), v=2))


def test_promises_are_whole_words_in_any_case(run):
    assert _draft(run, _one("Briefs your clients answer GUARANTEED", [])) != []
    assert _draft(run, _one("Briefs, nextday style", []), v=2) == []          # "next day" is two words or next-day
    assert _draft(run, _one("Stockholm studios love it", []), v=3) == []      # not "in stock"


def test_polish_copy_reads_the_polish_list(tmp_path):
    from test_create_config import ANSWERS
    run = _new(tmp_path, answers={**ANSWERS, "languages": {"working": "pl", "market": "pl"}})
    assert _check(run, "claims", CLAIMS) == []
    assert "promises a result (\"gwarant*\")" in _fields(_draft(run, _one("Gwarantujemy zadowolenie klienta", [])))
    assert "promises availability (\"od ręki\")" in _fields(_draft(run, _one("Brief od ręki", []), v=2))
    assert create_copy.promise_note(run) is None


def test_a_market_language_without_a_list_says_so(tmp_path, capsys):
    from test_create_config import ANSWERS
    run = _new(tmp_path, answers={**ANSWERS, "languages": {"working": "en", "market": "de"}})
    assert _check(run, "claims", CLAIMS) == []
    assert _draft(run, _one("Garantiert in 3 Minuten", ["k1"])) == []         # numbers checked, promises unknown
    note = create_copy.promise_note(run)
    assert "German (de)" in note and "no list of promise phrases" in note and "tm i18n export --lang de" in note
    path = run.latest("03_wip", "copy", "json")
    assert main(["ad", "copy", "check", "--run", str(run.path), "--file", str(path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["promise_warning"] == note
