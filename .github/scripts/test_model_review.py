"""The two-weekly model review (issue #115, section 5), offline: saved pages and a saved snapshot, never the network."""

import hashlib
import json
import urllib.request
from datetime import date
from pathlib import Path

import pytest

import model_review as mr

FIX = Path(__file__).parent / "fixtures" / "model_review"
WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "model-review.yml"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("the review's tests never touch the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)


def _report():
    registry, aliases = mr.load(mr.DATA / "registry.yaml"), mr.load(mr.DATA / "aliases.yaml")
    snap = json.loads((FIX / "snapshot.json").read_text(encoding="utf-8"))
    return registry, mr.compare(registry, aliases, snap)


def test_the_pages_are_read_as_they_are_written():
    assert mr.parse_arena((FIX / "arena_image_to_video.json").read_text()) == [
        {"name": "Gemini Omni 1.2 Flash", "rank": 1}, {"name": "Acme Motion 2 (720p)", "rank": 2},
        {"name": "MiniMax H3", "rank": 3}]                            # the overall board only
    assert mr.parse_aa((FIX / "aa_image_to_video.html").read_text()) == [
        {"name": "Dreamina Seedance 2.5", "rank": 1}, {"name": "Utopai X", "rank": 2}]
    assert mr.parse_billing((FIX / "replicate_h3.html").read_text()) == {"tiers": [
        {"criteria": "target resolution=768P", "price": "$0.09", "unit": "second of output video"},
        {"criteria": "target resolution=2K", "price": "$0.13", "unit": "second of output video"}]}
    assert mr.parse_billing("<html>no prices</html>") == {"error": "billingConfig not found"}
    assert mr.parse_collection((FIX / "replicate_collection.html").read_text()) == [
        "acme/acme-motion-2", "acme/acme-motion-2-avatar", "minimax/h3"]


def test_names_match_through_the_alias_table():
    registry, aliases = mr.load(mr.DATA / "registry.yaml"), mr.load(mr.DATA / "aliases.yaml")
    index = mr.name_index(registry, aliases)
    for name, model in [("GPT-Image-2 (Medium)", "openai/gpt-image-2"), ("Dreamina Seedance 2.0 (720p)",
                        "bytedance/seedance-2.0"), ("MiniMax H3 (768p)", "minimax/h3"), ("Wan 3.0", "alibaba/wan-3"),
                        ("Gemini Omni Flash 1.2", "google/gemini-omni-1.2-flash"), ("Eleven v4", "eleven_v4")]:
        assert index.get(mr.norm(name)) == model, name


def test_a_new_model_near_the_top_on_replicate_is_proposed_with_a_test_and_its_cost():
    _, report = _report()
    assert [g["model"] for g in report["new"]] == ["acme/acme-motion-2"]   # the same name, not its avatar sibling
    new = report["new"][0]
    assert new["places"] == ["#2 Arena image_to_video"] and new["tasks"] == ["image_to_video"]
    assert new["price"] == "$0.05 per second of output video (target resolution=720p)"
    assert new["test"].startswith("3 takes of 15 s for each of image_to_video") and new["test_usd"] == 2.25


def test_names_it_cannot_match_are_listed_to_match_and_a_left_out_model_is_not_proposed_again():
    _, report = _report()
    assert [t["name"] for t in report["to_match"]] == ["Utopai X"]
    assert "Gemini Nano Banana 2.1" not in json.dumps(report)        # left out after the owner's test
    assert "Far Down Model" not in json.dumps(report)                # not near the top


def test_price_availability_and_ranking_changes_of_the_registrys_models():
    _, report = _report()
    assert {(c["model"], c["variant"], c["was"], c["now"]) for c in report["price_changes"]} == {
        ("minimax/h3", "768P", 0.08, 0.09)}                          # Topaz's $0.08 units are its $0.0186 a second
    gone = {g["model"]: g for g in report["gone"]}
    assert set(gone) == {"kwaivgi/kling-avatar-v2"}                  # ProPainter is billed by time: no price is normal
    assert gone["kwaivgi/kling-avatar-v2"]["routes"] == ["talking person: fallback", "voice: lipsync",
                                                         "lip-sync fallback"]
    assert report["rankings"]["minimax/h3"] == ["#3 Arena image_to_video"]
    assert report["rankings"]["eleven_v4"] == ["#1 Artificial Analysis leaderboard"]
    assert report["elevenlabs_new"] == ["eleven_v5"]                 # the deprecated v2 sound model is left out


def test_the_issue_mentions_the_owner_and_holds_every_part():
    registry, report = _report()
    title, body = mr.render(report, date(2026, 11, 17), date(2026, 12, 1), registry_checked="2026-11-17")
    assert title == "Model review 2026-11-17 – 2026-12-01"
    assert body.startswith("@piotr-lezon: ") and "Nothing in the registry was changed" in body
    for part in ("## New models near the top of a ranking, on Replicate", "`acme/acme-motion-2`", "$2.25",
                 "`minimax/h3` 768P: $0.08 in the registry, $0.09 today", "## Gone from Replicate or ElevenLabs",
                 "`kwaivgi/kling-avatar-v2` (HTTP 404)", "## To match", "Utopai X", "`eleven_v5`",
                 "## Not read this time", "music/leaderboard"):
        assert part in body, part


def test_a_run_never_changes_the_registry(capsys):
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in mr.DATA.iterdir()}
    assert mr.main(["--snapshot", str(FIX / "snapshot.json"), "--dry-run", "--today", "2026-12-01"]) == 0
    assert "Model review 2026-11-17 – 2026-12-01" in capsys.readouterr().out
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in mr.DATA.iterdir()} == before


def test_the_workflow_runs_every_two_weeks_with_no_paid_key():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "cron: \"0 7 1,15 * *\"" in text and "workflow_dispatch" in text
    assert "issues: write" in text and "contents: read" in text
    assert "secrets." not in text.replace("secrets.GITHUB_TOKEN", "")   # only the workflow's own token
    assert ".github/scripts/model_review.py" in text
    assert mr.OWNER == "piotr-lezon"
