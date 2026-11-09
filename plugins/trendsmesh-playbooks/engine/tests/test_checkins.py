"""The check-in catalogue (data/checkins.yaml) and the step list (data/steps.yaml)."""

import re
from pathlib import Path

import pytest

from tm import checkins, flow

REPO = Path(__file__).resolve().parents[4]
FLOWS = REPO / "handoff" / "refresh-ad_v02" / "playbook-01-refresh-ad" / "FLOWS.md"
FLOWS_V03 = REPO / "handoff" / "refresh-ad_v03" / "playbook-01-refresh-ad" / "FLOWS.md"
LEVELS = ("every_step", "big_calls", "hands_off")
G_IDS = ["G1", "G1a", "G1b", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10", "G11", "G12"]


def _flows_section(letter: str, flows: Path = FLOWS) -> str:
    text = flows.read_text(encoding="utf-8").replace("\r\n", "\n")
    start = text.index(f"\n## {letter}. ")
    end = text.find("\n## ", start + 1)
    return text[start:end]


def test_levels_are_the_three_named_levels():
    cat = checkins.load()
    assert cat.levels == {
        "every_step": "Check every step",
        "big_calls": "Just the big calls",
        "hands_off": "Hands-off",
    }


def test_catalogue_has_every_checkin():
    cat = checkins.load()
    assert set(cat.checkins) == set(G_IDS) | {"VB", "V1c", "GV", "E2b", "G3r", "RB", "G5r"}
    for c in cat.checkins.values():
        assert c.name and "gate" not in c.name.lower()
        assert set(c.route) == set(LEVELS)
        assert set(c.route.values()) <= {"own", "card", "rule", "stop"}


def test_cards_merge_the_design_groups():
    cat = checkins.load()
    members: dict[str, list[str]] = {}
    for c in cat.checkins.values():
        if c.card:
            members.setdefault(c.card, []).append(c.id)
    assert members == {
        "pick_the_ad": ["G1", "G1a", "G1b"],
        "approve_changes": ["G2", "G3", "G4"],
        "approve_spending": ["VB", "RB", "G6", "G10"],
        "approve_launch": ["G11"],
        "act_on_results": ["G12"],
    }
    for card, ids in members.items():
        for cid in ids:
            route = cat.checkins[cid].route
            assert route == {"every_step": "own", "big_calls": "card", "hands_off": "rule"}, cid
    assert set(cat.cards) == set(members)
    assert cat.cards["approve_spending"].ask == "before_first_spend"


def test_review_steps_go_by_rule_above_every_step():
    cat = checkins.load()
    for cid in ("G5", "G7", "G8", "G9"):
        assert cat.checkins[cid].route == {"every_step": "own", "big_calls": "rule", "hands_off": "rule"}


def test_voice_checks_stop_in_hands_off():
    cat = checkins.load()
    for cid in ("V1c", "GV"):
        c = cat.checkins[cid]
        assert c.route == {"every_step": "own", "big_calls": "own", "hands_off": "stop"}
        assert c.stop and c.stop["what"] and c.stop["todo"]


def test_e2b_red_stops_green_goes_by_rule():
    c = checkins.load().checkins["E2b"]
    assert set(c.route.values()) == {"rule"}
    assert c.choices == ("green", "red")
    assert "stop" in c.on_choice["red"]
    assert "green" not in c.on_choice


@pytest.mark.private_data
def test_rules_are_verbatim_from_flows_section_g():
    table = _flows_section("G")
    defaults = {}
    for line in table.splitlines():
        cells = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0] not in ("Code", "---"):
            code = cells[0] if cells[0] != "—" else cells[1]
            defaults[code] = cells[4]
    # the plugin's middle-run clauses (Task 12 fix round 1), after FLOWS' text, which stays verbatim
    middle = {"G2": "; in a middle run, recut (the re-cut of the middle)",
              "G3": "; in a middle run, the register of the diagnosed causes and the re-cut direction"}
    cat = checkins.load()
    for cid in G_IDS + ["E2b"]:
        assert cat.checkins[cid].rule == defaults[cid] + middle.get(cid, ""), cid


@pytest.mark.private_data
def test_steps_follow_flows_a_to_e_in_order():
    ids_in_flows = []
    for letter in "ABCDE":
        for line in _flows_section(letter).splitlines():
            m = re.match(r"^\| ([A-E]\d+[a-z]?) \|", line)
            if m:
                ids_in_flows.append(m.group(1))
    assert [s.id for s in flow.steps() if s.flow is None] == ids_in_flows


def test_flow_v_steps_sit_before_the_render():
    ids = [s.id for s in flow.steps()]
    v = [s.id for s in flow.steps() if s.flow == "V"]
    assert v == ["V0", "V1", "V3", "V4", "V5", "VC"]
    assert ids.index("C1") < ids.index("V0") and ids.index("VC") < ids.index("C2")
    by_id = {s.id: s for s in flow.steps()}
    assert by_id["V1"].before == ("VB",) and by_id["V1"].checkins == ("V1c",)
    assert by_id["V3"].checkins == ("GV",)
    assert flow.flows() == {"V", "R"}


def test_step_outputs_and_refs():
    all_four = {"creative_brief", "edited_video", "ai_video", "live_test"}
    by_id = {s.id: s for s in flow.steps()}
    for s in flow.steps():
        assert s.title
        assert s.ref == f"skills/refresh-ad/references/flow.md#{s.id.lower()}"
        expected = {"A": all_four, "B": {"creative_brief"}, "C": {"edited_video"},
                    "V": {"edited_video"}, "D": {"ai_video"}, "E": {"live_test"}}[s.id[0]]
        assert set(s.outputs) == expected, s.id
    assert by_id["A1"].checkins == ("G1",)
    assert by_id["A3b"].checkins == ("G1b",)
    assert by_id["E2b"].checkins == ("E2b",)
    assert by_id["E3"].before == ("G11",) and by_id["E3"].checkins == ()
    assert by_id["E4"].measures and not any(s.measures for s in flow.steps() if s.id != "E4")
    assert {s.id for s in flow.steps() if s.spends} == {"V1", "V3", "V4", "VC", "CR5a", "CR5b", "D2", "D3",
                                                         "E3"}


# --- flow R, path C-R (handoff v03) ------------------------------------------------

def test_flow_r_steps_follow_c1_with_flow_v_between_cr4_and_cr5a():
    ids = [s.id for s in flow.steps()]
    r = [s.id for s in flow.steps() if s.flow == "R"]
    assert r == ["CR1", "CR2", "CR3", "CR4", "CR5a", "CR5b", "CR6", "CR7"]
    assert ids[ids.index("C1"):ids.index("C4") + 1] == [
        "C1", "CR1", "CR2", "CR3", "CR4", "V0", "V1", "V3", "V4", "V5", "VC",
        "CR5a", "CR5b", "CR6", "CR7", "C2", "C3", "C4"]
    by_id = {s.id: s for s in flow.steps()}
    for sid in r:
        assert by_id[sid].outputs == ("edited_video",)
        assert by_id[sid].ref == f"skills/refresh-ad/references/flow.md#{sid.lower()}"
    assert [sid for sid in r if by_id[sid].spends] == ["CR5a", "CR5b"]
    assert by_id["CR3"].checkins == ("G3r",) and by_id["CR7"].checkins == ("G5r",)
    assert by_id["CR5a"].before == ("RB",) and by_id["CR5a"].budget == "ai_usd"
    assert by_id["CR5b"].before == () and by_id["CR5b"].budget == "voice_credits"
    assert by_id["CR5a"].skip_when == by_id["CR5b"].skip_when == (("RB", "reject"),)
    assert all(not by_id[sid].skip_when for sid in ("CR1", "CR2", "CR3", "CR4", "CR6", "CR7"))
    for sid in ("C2", "C3", "C4"):
        assert by_id[sid].targets == ("hook", "promise_cta", "fatigue")
    assert all(not s.targets for s in flow.steps() if s.id not in ("C2", "C3", "C4"))


def test_g3r_chooses_the_variants_on_its_own():
    # not on the changes card: that card (G2, G3, G4) stays where v1 asks it (PR C review)
    c = checkins.load().checkins["G3r"]
    assert c.name == "Choose the re-cut variants" and c.card is None
    assert c.route == {"every_step": "own", "big_calls": "own", "hands_off": "rule"}
    assert not c.money


def test_g5r_is_own_in_big_calls_and_rule_in_hands_off():
    c = checkins.load().checkins["G5r"]
    assert c.name == "Approve each re-cut variant (listen to it)" and c.card is None
    assert c.route == {"every_step": "own", "big_calls": "own", "hands_off": "rule"}
    assert c.rule == "🔍 green"


def test_rb_is_money_and_on_the_spending_card():
    c = checkins.load().checkins["RB"]
    assert c.name == "Approve the re-cut budget"
    assert c.card == "approve_spending" and c.money
    assert c.choices == ("approve", "reject")
    assert c.route == {"every_step": "own", "big_calls": "card", "hands_off": "rule"}
    assert c.rule == "limit from the config (budget.ai_usd, budget.voice_credits)"
    assert "nothing" in c.on_choice["reject"]["skips"]


@pytest.mark.private_data
def test_recut_rules_are_verbatim_from_v03_flows_section_g():
    defaults = {}
    for line in _flows_section("G", FLOWS_V03).splitlines():
        cells = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0] not in ("Code", "---"):
            defaults[cells[0] if cells[0] != "—" else cells[1]] = cells[4]
    cat = checkins.load()
    assert defaults["G3r"] == 'variants for the causes marked "yes", L0–L2 first'
    assert cat.checkins["G3r"].rule == (defaults["G3r"] + "; never a new voiceover line (it waits: its "
                                        "voice match needs a person)")
    assert cat.checkins["G5r"].rule == defaults["G5r"]
    assert cat.checkins["RB"].rule.startswith(defaults["CR5"])


def test_every_checkin_belongs_to_exactly_one_step():
    listed = [cid for s in flow.steps() for cid in s.before + s.checkins]
    assert sorted(listed) == sorted(checkins.load().checkins)


def test_level_ids_validated():
    assert checkins.validate_level("big_calls") == "big_calls"
    with pytest.raises(ValueError, match="Check every step"):
        checkins.validate_level("auto")


def test_bad_catalogue_is_refused(tmp_path):
    bad = tmp_path / "checkins.yaml"
    bad.write_text(
        "levels: {every_step: a, big_calls: b, hands_off: c}\n"
        "cards: {}\n"
        "checkins:\n"
        "  - {id: G1, name: x, card: nope, rule: r,"
        " route: {every_step: own, big_calls: card, hands_off: rule}}\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="nope"):
        checkins.load(bad)
    bad.write_text(
        "levels: {every_step: a, big_calls: b, hands_off: c}\n"
        "cards: {}\n"
        "checkins:\n"
        "  - {id: G1, name: x, rule: r, route: {every_step: own, big_calls: ask, hands_off: rule}}\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="ask"):
        checkins.load(bad)
