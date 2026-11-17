"""Follow-up to issue 21: VC's free way has its own tool, free and with no approval, and the playbook says so.
The tool itself is tested in tools/test_inpaint.py (it needs OpenCV)."""

from tm import paths, tools


def test_the_free_caption_removal_is_a_free_tool():
    tool = tools.TOOLS["inpaint"]
    assert tool.tier == "breakdown" and tool.keys == ()
    assert tool.kind_for(["--run", "r", "ad.mp4", "--teardown", "t.json"]) is None   # free: no --cost, no budget


def test_vc_makes_the_free_plate_first_and_asks_only_for_pro():
    flow = (paths.bundled_data().parent / "skills/refresh-ad/references/flow.md").read_text(encoding="utf-8")
    vc = " ".join(flow[flow.index('<a id="vc"></a>'):flow.index('<a id="cr5a"></a>')].split())
    assert "has no tool" not in vc
    assert vc.index("tm tool inpaint --run R") < vc.index("tm tool inpaint_mode --run R")
    assert "`pro_wanted`" in vc and "tm budget approve --run R ai_usd" in vc
