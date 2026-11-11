"""Create an ad (playbook 05), S10: the upload proposal's check (CA14: in full, the budget never inferred, the AI
disclosure the user's, conversions only from a pixel that fires), its card, and the record of the objects read back
(PAUSED only: an active object is a stop)."""

import json

import pytest

from tm import create_copy, create_upload, manifest, stepchecks
from tm.cli import main
from tm.stops import Stop

from test_create_copy import KEY, _choices, ad
from test_create_plan import CLAIMS, _check, _new, _write


@pytest.fixture
def run(tmp_path):
    run = _new(tmp_path)
    assert _check(run, "claims", CLAIMS) == []
    _write(run, "03_wip/copy_v01.json", {"ads": [ad()]})
    assert create_copy.check(run, "03_wip/copy_v01.json")[1] == []
    assert create_copy.accept(run, _choices(run, keep_primary=(1, 2, 3)))[1] == []
    for rel in (f"04_final/{KEY}_v01.mp4", f"04_final/{KEY}_thumb_v01.jpg"):
        _write(run, rel, {})
        manifest.record(run, rel, "04_final", "the edit")
    for rel in ("02_research/meta_pages_v01.json", "02_research/meta_pixel_v01.json", "05_results/answers_v01.json"):
        _write(run, rel, {"saved": "an MCP answer"})
    return run


def proposal(**over):
    base = {"ad_account_id": "act_0000", "page_id": "page_a", "copy": "04_final/copy_v01.json",
            "checks": {"pages": {"saved": "02_research/meta_pages_v01.json", "ids": ["page_a", "page_b"]},
                       "pixel": {"dataset_id": "ds_1", "fires": True, "events": ["PageView", "CompleteRegistration"],
                                 "saved": "02_research/meta_pixel_v01.json"}},
            "objective": {"options": [{"objective": "OUTCOME_LEADS", "event": "COMPLETE_REGISTRATION",
                                       "why": "the sign-up arrives, enough a week at this budget"},
                                      {"objective": "OUTCOME_TRAFFIC", "event": "LINK_CLICKS", "why": "volume"}],
                          "chosen": 0, "said": "go for sign-ups"},
            "budget": {"amount": 20, "cadence": "daily", "currency": "USD", "said": "20 a day"},
            "country": ["PL"], "audience": "advantage_plus", "placements": "advantage_plus",
            "names": {"campaign": "Planner brief tool launch, sign-ups", "adset": "Planner freelancers Poland broad",
                      "ads": {KEY: "Planner brief tool, freelancers, nobody told me"}},
            "ads": [{"key": KEY, "video": f"04_final/{KEY}_v01.mp4", "thumbnail": f"04_final/{KEY}_thumb_v01.jpg"}],
            "ai_disclosure": {"value": "OPT_IN", "said": "yes, the presenter is AI"},
            "status": "PAUSED"}
    base.update(over)
    return base


def _propose(run, data, v=1):
    _write(run, f"05_results/upload_proposal_v{v:02d}.json", data)
    return create_upload.check(run, f"05_results/upload_proposal_v{v:02d}.json")[1]


def _says(problems):
    return " ".join(f"{p.field}: {p.what}" for p in problems)


def test_a_full_proposal_passes_and_its_card_says_the_placement_facts(run):
    assert "tm ad upload check" in stepchecks.run("ad_upload_proposed", run)
    assert _propose(run, proposal()) == []
    assert stepchecks.run("ad_upload_proposed", run) is None
    card = create_upload.card(run)
    assert "Video ads show no description on Facebook Feed or Instagram." in card["facts"]
    assert card["pixel_notes"] == [] and card["objective"] == "OUTCOME_LEADS" and card["status"] == "PAUSED"
    assert "nothing runs and nothing is spent" in card["paused_note"]


def _drop(data, *path):
    node = data
    for p in path[:-1]:
        node = node[p]
    node.pop(path[-1])
    return data


@pytest.mark.parametrize("data,says", [
    (proposal(budget={"amount": 20, "cadence": "daily", "currency": "USD"}), "never inferred"),
    (proposal(budget={"amount": 20, "currency": "USD", "said": "20"}), "never inferred"),
    (proposal(ai_disclosure={"value": "OPT_IN"}), "advertiser's decision"),
    (proposal(ai_disclosure={"value": "UNSET", "said": "x"}), "advertiser's decision"),
    (proposal(status="ACTIVE"), "never 'ACTIVE'"),
    (proposal(names={"campaign": "Campaign 1", "adset": "Ad set 1", "ads": {KEY: "Ad 1"}}), "does not say what"),
    (proposal(page_id="page_z"), "not one the ad account can use"),
    (proposal(checks={"pages": {"saved": "02_research/meta_pages_v01.json", "ids": ["page_a"]}}), "pixel is not checked"),
    (proposal(copy="04_final/copy_v09.json"), "not the accepted copy"),
    (proposal(ads=[{"key": KEY, "video": "00_raw/other.mp4", "thumbnail": f"04_final/{KEY}_thumb_v01.jpg"}]),
     "not the delivered one"),
    (proposal(country=["Poland"]), "two-letter codes"),
    (proposal(objective={"options": [{"objective": "OUTCOME_LEADS", "event": "LEAD", "why": "x"}], "chosen": 0}),
     "user's words"),
])
def test_proposal_refused(run, data, says):
    assert says in _says(_propose(run, data))


def test_a_conversion_needs_a_pixel_that_sends_it(run):
    silent = proposal()
    silent["checks"]["pixel"].update(fires=False)
    assert "does not send" in _says(_propose(run, silent))
    other = proposal()
    other["objective"]["options"][0]["event"] = "PURCHASE"
    assert "does not send" in _says(_propose(run, other, v=2))
    clicks = proposal()
    clicks["checks"]["pixel"].update(dataset_id=None, fires=False, events=[])
    clicks["objective"] = {"options": [{"objective": "OUTCOME_ENGAGEMENT", "event": "LINK_CLICKS", "why": "no pixel"}],
                           "chosen": 0, "said": "clicks then"}
    assert _propose(run, clicks, v=3) == []
    assert create_upload.card(run)["pixel_notes"][0].startswith("This site has no pixel")


def test_several_texts_do_not_run_under_traffic(run):
    traffic = proposal()
    traffic["objective"]["chosen"] = 1
    assert "Traffic takes one" in _says(_propose(run, traffic))


def test_nothing_is_proposed_before_the_copy_is_accepted(tmp_path):
    run = _new(tmp_path)
    assert "not accepted yet" in _says(_propose(run, proposal()))


def objects(**over):
    base = {"created_as": "paused", "proposal": "05_results/upload_proposal_v01.json",
            "campaign": {"id": "c1", "name": "Planner brief tool launch, sign-ups", "status": "PAUSED"},
            "adset": {"id": "s1", "name": "Planner freelancers Poland broad", "status": "PAUSED"},
            "videos": [{"key": KEY, "id": "v1", "status": "ready"}],
            "creatives": [{"key": KEY, "id": "cr1", "self_ai_disclosure": "OPT_IN"}],
            "ads": [{"key": KEY, "id": "a1", "name": "Planner brief tool", "status": "PAUSED",
                     "preview_url": "https://example.com/preview"}],
            "answers": "05_results/answers_v01.json"}
    base.update(over)
    return base


def _record(run, data, v=1):
    _write(run, f"05_results/meta_objects_v{v:02d}.json", data)
    return create_upload.record(run, f"05_results/meta_objects_v{v:02d}.json")[1]


def test_paused_objects_are_recorded_and_the_user_hears_how_to_switch_them_on(run):
    assert _propose(run, proposal()) == []
    assert "tm ad upload record" in stepchecks.run("ad_upload_recorded", run)
    assert _record(run, objects()) == []
    assert stepchecks.run("ad_upload_recorded", run) is None
    said = create_upload.outcome(run)
    assert said["ids"] == {"campaign": "c1", "adset": "s1", "creatives": ["cr1"], "ads": ["a1"]}
    assert "Created PAUSED" in said["text"] and "Nothing in this run switches it on." in said["text"]


@pytest.mark.parametrize("data", [
    objects(campaign={"id": "c1", "status": "ACTIVE"}),
    objects(ads=[{"key": KEY, "id": "a1", "status": "ACTIVE", "preview_url": "x"}]),
    objects(created_as="paused", adset={"id": "s1", "status": "DRAFT"}),   # said paused, came back otherwise
])
def test_an_object_that_is_not_paused_is_a_stop(run, data):
    assert _propose(run, proposal()) == []
    with pytest.raises(Stop, match="is not paused in Meta"):
        _record(run, data)
    assert stepchecks.run("ad_upload_recorded", run) is not None


def test_drafts_count_when_meta_made_drafts(run):
    assert _propose(run, proposal()) == []
    data = objects(created_as="draft", campaign={"id": "c1", "status": "DRAFT"})
    assert _record(run, data) == []
    assert "Created as a draft" in create_upload.outcome(run)["text"]


@pytest.mark.parametrize("data,says", [
    (objects(videos=[{"key": KEY, "id": "v1", "status": "processing"}]), "not uploaded and ready"),
    (objects(creatives=[{"key": KEY, "id": "cr1", "self_ai_disclosure": "OPT_OUT"}]), "AI disclosure"),
    (objects(creatives=[{"key": KEY, "id": "cr1"}]), "AI disclosure"),
    (objects(ads=[{"key": KEY, "id": "a1", "status": "PAUSED"}]), "no preview link"),
    (objects(answers=None), "not saved"),
])
def test_record_refused(run, data, says):
    assert _propose(run, proposal()) == []
    assert says in _says(_record(run, data))


def test_the_go_ahead_needs_a_checked_proposal(run, monkeypatch):
    from tm import checkins, flow
    real = stepchecks.run
    monkeypatch.setattr(stepchecks, "run", lambda name, folder: None)   # every step done, the proposal unchecked
    cat = checkins.load(playbook="05-create-ad")
    for _ in range(60):
        nxt = flow.next(run)
        if nxt.action == "ask" and nxt.checkin.ids == ["upload"]:
            break
        if nxt.action == "work":
            flow.complete(run, nxt.step)
        else:
            for cid in nxt.checkin.ids:
                flow.decide(run, cid, cat.checkins[cid].choices[0], by="user" if nxt.action == "ask" else "rule",
                            note=None if nxt.action == "ask" else "data")
    assert nxt.checkin.ids == ["upload"]
    monkeypatch.setattr(stepchecks, "run", real)
    with pytest.raises(Exception, match="upload proposal"):
        flow.decide(run, "upload", "create", by="user", note=None)
    assert _propose(run, proposal()) == []
    flow.decide(run, "upload", "create", by="user", note=None)


def test_tm_ad_upload_on_the_command_line(run, capsys):
    _write(run, "05_results/upload_proposal_v01.json", proposal())
    assert main(["ad", "upload", "check", "--run", str(run.path), "--file", "05_results/upload_proposal_v01.json",
                 "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["card"]["question"].startswith("Shall I create these")
    _write(run, "05_results/meta_objects_v01.json", objects(campaign={"id": "c1", "status": "ACTIVE"}))
    assert main(["ad", "upload", "record", "--run", str(run.path), "--file", "05_results/meta_objects_v01.json",
                 "--json"]) == 2
    assert "is not paused in Meta" in json.loads(capsys.readouterr().out)["message"]
