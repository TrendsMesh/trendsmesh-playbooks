"""The organic-video skill (plan Tasks 10 and 18): it ships, so organic video is offered; every `tm` command
and flag its prose names exists (PB02 Task 15's test, `test_brief_flow.py`), a `tm tool` command's flags in that
tool's own parser; its step anchors, its declarations and its verbatim copies of the spec and of the model recipes
match the engine and the handoff. Tasks 19 to 21 extend it as they add prose."""

import argparse
import importlib
import json
import re
import pytest

from test_brief_flow import _leaf, _tm_commands
from test_frontmatter import front_matter
from tm import cli, flow, organic_config, organic_pack, paths, playbooks, state
from tm.organic_pages import CAPABILITIES
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder

PLUGIN = paths.bundled_data().parent
REPO = PLUGIN.parents[1]
SKILL = PLUGIN / "skills" / "organic-video"
SPEC = REPO / "handoff" / "organic-video_v02" / "playbook-03-organic-ai-video"
DESCRIPTION = ("Use when the user wants organic short videos for TikTok, Instagram Reels, YouTube Shorts or "
               "Facebook Reels built on rising trends: video ideas for a channel, a script to film, a ready AI "
               "video, or a weekly pack; also 'plan my week of videos'.")
SHIPPED_OUTPUTS = ("proposals", "script_to_film", "organic_video", "weekly_plan")   # an idea run; a script (PR B), an
# AI video (PR C), a week run (PR E)
RECIPES = PLUGIN / "references" / "model-prompting"
HANDOFF_RECIPES = REPO / "handoff" / "organic-video_v02" / "resources" / "model-prompting"
VERBATIM_RECIPES = ("README.md", "minimax-h3.md", "gpt-image-2.md", "veo-3.1.md")   # the handoff's, as they are
OWN_RECIPES = ("seedance-2.0.md", "kling-avatar-v2.md",   # the plugin's, from the handoff's pet-store research
               "seedance-1.5-pro.md", "seedance-2.5.md", "p-video-upscale.md")
ROUTED_RECIPES = {   # every model the engine itself sends a take to (a tier, a host image, a described person,
    "bytedance/seedance-1.5-pro": "seedance-1.5-pro.md",   # the upscaler) -> its recipe
    "minimax/h3": "minimax-h3.md",
    "bytedance/seedance-2.0": "seedance-2.0.md",
    "bytedance/seedance-2.5": "seedance-2.5.md",
    "prunaai/p-video-upscale": "p-video-upscale.md",
}
GATE_CAPABILITIES_AT = ("f1", "g4")   # the check-in pages (F1, F2) and the delivery page (G4) declare CAPABILITIES["gate"]


def _text(path) -> str:
    return path.read_text(encoding="utf-8").replace("\r", "")


def _unquoted(text: str) -> str:
    """The text with the line quoted in the "Last line (half-whisper)" note blanked: the plugin's is made up."""
    return re.sub(r'(\*\*Last line \(half-whisper\):\*\* [^(]*)\("[^"]*"\)', r'\1("")', text)


def _pinned_lf(pattern: str) -> bool:
    """`.gitattributes` keeps `pattern` LF on every checkout (Git for Windows' core.autocrlf=true would
    otherwise write CRLF): the LF the files are committed with is what reaches every system."""
    lines = (REPO / ".gitattributes").read_text(encoding="utf-8").splitlines()
    return f"{pattern} text eol=lf" in lines


def _section(text: str, anchor: str) -> str:
    """The text of flow.md's section `anchor`, up to the next anchor."""
    start = text.index(f'<a id="{anchor}"></a>')
    nxt = text.find('<a id="', start + 1)
    return text[start:nxt if nxt != -1 else len(text)]


# --- the skill ships, so organic video is offered ----------------------------------------------

def test_skill_front_matter():
    """Read as YAML, as Claude Code reads it (#9: the description's ': ' needs the quotes)."""
    head = front_matter(_text(SKILL / "SKILL.md"))
    assert head["name"] == "organic-video"
    assert head["description"] == DESCRIPTION


def test_run_new_offers_organic_video_now_its_skill_ships(tmp_path, monkeypatch, capsys):
    """No fixture: the plugin's own skills folder holds organic-video. An idea run starts, its config
    takes a script to film, an AI video (PR C) or the weekly pack (PR E); a root
    without the skill still refuses organic video as coming in a later version."""
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("TM_WORKSPACE", str(ws))
    assert playbooks.offered("organic-video").id == ORGANIC_VIDEO
    assert cli.main(["run", "new", "--playbook", "organic-video", "--name", "exampleedu", "--json"]) == 0
    run = RunFolder.open(json.loads(capsys.readouterr().out)["path"])
    assert run.path.parent == ws / "runs" / ORGANIC_VIDEO
    answers = json.loads(_text(SKILL / "templates" / "intake_answers_example.json"))
    organic_config.write_from_intake(run, answers)
    assert organic_config.validate(run) == []
    assert state.load(run).level == answers["level"] and state.load(run).outputs == ["proposals"]
    organic_config.config.save(run, {**organic_config.config.load(run), "output": "ai_video"})
    assert "output" not in {p.field for p in organic_config.validate(run)}
    organic_config.config.save(run, {**organic_config.config.load(run), "output": "weekly_pack"})
    assert "output" not in {p.field for p in organic_config.validate(run)}
    root = tmp_path / "skills"
    (root / "refresh-ad").mkdir(parents=True)
    (root / "refresh-ad" / "SKILL.md").write_text("---\nname: test\n---\n", encoding="utf-8")
    monkeypatch.setattr(playbooks, "skills_root", lambda: root)
    assert cli.main(["run", "new", "--playbook", "organic-video", "--name", "x", "--json"]) == 1
    assert "Organic AI video comes in a later version" in json.loads(capsys.readouterr().out)["message"]


# --- the prose names only what the engine has --------------------------------------------------

def test_every_shipped_step_has_its_anchor_in_flow_md():
    """flow.md's anchors are step refs, in step order, and every step of an idea run, of a script to film,
    of an AI video and of a week run has one."""
    every = flow.steps(ORGANIC_VIDEO)
    for st in every:
        assert st.ref == f"skills/organic-video/references/flow.md#{st.id.lower()}", st.ref
    anchors = re.findall(r'<a id="([a-z0-9]+)"></a>', _text(SKILL / "references" / "flow.md"))
    order = [st.id.lower() for st in every]
    assert anchors == [a for a in order if a in anchors], anchors
    shipped = [st.id.lower() for st in every if set(st.outputs) & set(SHIPPED_OUTPUTS)]
    assert shipped == ["a0", "a1", "b1", "b2", "b3", "c1", "c2", "c3", "i2", "i3", "i4", "i5", "d1", "d2", "e1", "e2",
                       "e3", "f1", "f2", "g1", "g2", "g4", "h1"]
    assert set(shipped) <= set(anchors)


def test_skill_names_only_commands_and_flags_tm_has():
    """Every `tm …` in the organic-video skill and the plugin's shared references (the model recipes too)
    is a real command path, and every --flag it writes is an option of that command; a tool's name is one
    of `tm tool`'s. `tm tool <name>` passes the rest to the tool unchanged (a remainder), so its flags are the
    tool's own: `test_tool_commands_use_the_tools_own_flags` checks them."""
    parser = cli.build_parser()
    seen = 0
    for f in _prose():
        for cmd in _tm_commands(f.read_text(encoding="utf-8")):
            words = cmd.split()[1:]
            path = [w for w in words if re.fullmatch(r"[a-z][a-z0-9_*-]*", w)]
            leaf, rest = _leaf(parser, path[:3])
            choices = [a.choices for a in leaf._actions if not a.option_strings and a.choices]
            if choices and rest:                     # `tm trends collect on`, `tm organic page proposals`
                assert rest[0] in choices[0], f"{f.name}: `{cmd}`: {rest[0]!r} is not one of {choices[0]}"
            seen += 1
            if any(a.nargs == argparse.REMAINDER for a in leaf._actions):   # `tm tool elevenlabs credits --run R`
                continue
            options = {o for a in leaf._actions for o in a.option_strings}
            for flag in re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", cmd):
                assert flag in options, f"{f.name}: `{cmd}`: {flag} is not an option ({sorted(options)})"
    assert seen > 100


def _prose():
    return sorted(SKILL.rglob("*.md")) + sorted((PLUGIN / "references").rglob("*.md"))


def _tool_parser(name: str) -> argparse.ArgumentParser:
    """The parser `tm.tools.<name>.main` builds, caught as it starts parsing (nothing runs; a BaseException, as
    SystemExit is, so a tool's own error handling lets it through)."""
    class Caught(BaseException):
        pass

    got = {}

    def catch(self, args=None, namespace=None):
        got["parser"] = self
        raise Caught

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(argparse.ArgumentParser, "parse_args", catch)
        with pytest.raises(Caught):
            importlib.import_module(f"tm.tools.{name}").main([])
    return got["parser"]


def test_tool_commands_use_the_tools_own_flags():
    """Task 10's ruling: `tm tool <name>` hands its arguments to the tool unchanged, so a tool command the
    prose writes is checked against that tool's own parser: its action (`tm tool elevenlabs voices`, `tm tool
    deliver finish`) and every --flag it writes."""
    seen = set()
    for f in _prose():
        for cmd in _tm_commands(f.read_text(encoding="utf-8")):
            words = cmd.split()
            if words[1:2] != ["tool"] or len(words) < 3:
                continue
            name, rest = words[2], words[3:]
            actions = []
            for w in rest:
                if not re.fullmatch(r"[a-z][a-z0-9-]*", w):
                    break
                actions.append(w)
            leaf, _ = _leaf(_tool_parser(name), actions[:1])
            options = {o for a in leaf._actions for o in a.option_strings}
            for flag in re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", " ".join(rest)):
                assert flag in options, f"{f.name}: `{cmd}`: {flag} is not an option of tm tool {name} ({sorted(options)})"
            seen.add(" ".join([name, *actions[:1]]))
    assert {"replicate_price", "replicate_run", "take_qa", "music_index", "elevenlabs credits", "elevenlabs voices",
            "elevenlabs tts", "deliver finish", "deliver measure", "deliver speed", "deliver upload", "deliver cover",
            "deliver preview", "deliver nosound"} <= seen, sorted(seen)


def test_flow_declares_what_the_engine_declares():
    """The capabilities flow.md tells the agent to declare are organic_pages.CAPABILITIES, verbatim."""
    flow_md = _text(SKILL / "references" / "flow.md")
    for page, anchor in (("proposals", "c2"), ("script", "e3"), *(("gate", a) for a in GATE_CAPABILITIES_AT)):
        found = re.search(r"`(\{.*?\})`", _section(flow_md, anchor).split("`capabilities` =", 1)[1], re.S)
        assert found, anchor
        assert json.loads(found.group(1)) == CAPABILITIES[page], anchor
    for anchor in ("c2", "e3", *GATE_CAPABILITIES_AT):
        section = re.sub(r"\s+", " ", _section(flow_md, anchor))
        assert "`Artifact` publish" in section and "declaration" in section, anchor   # declared in the publish, checked
        assert "read_declaration" in section, anchor                                 # and the older tools' way


def test_flow_a0_and_d1_mirror_the_doctor():
    """A0 checks the idea run's own output and records the stack; D1 checks the production run's: a script's
    base tools, or an AI video's media tools, then the ElevenLabs credits and the stack again, never unchecked
    (Task 4's carry, the `credits_recorded` check); commands/doctor.md says the same."""
    flow_md = _text(SKILL / "references" / "flow.md")
    doctor_md = _text(PLUGIN / "commands" / "doctor.md").split("**Organic video.**", 1)[1]
    a0, d1 = (re.sub(r"\s+", " ", _section(flow_md, a)) for a in ("a0", "d1"))
    assert "tm doctor --playbook organic-video --outputs proposals" in a0
    assert "`tm organic stack" in a0 and "--elevenlabs" in a0
    assert "--outputs script_to_film" in d1 and "tm doctor --playbook organic-video --outputs organic_video" in d1
    assert d1.index("--outputs organic_video") < d1.index("`tm tool elevenlabs credits") < d1.index("`tm organic stack")
    assert "Never `unchecked` here" in d1 and "--stage recipe" in d1
    for words in ("--outputs proposals", "script_to_film", "--outputs organic_video", "tm tool elevenlabs credits",
                  "tm organic stack"):
        assert words in re.sub(r"\s+", " ", doctor_md), words


def test_ai_video_steps_name_the_engine_commands():
    """Task 18: each step of an AI video says, where it is done, the commands the engine built for it (the
    carries of Tasks 4, 12, 13, 15 and 16)."""
    flow_md = _text(SKILL / "references" / "flow.md")
    named = {
        "d1": ["tm tool elevenlabs credits", "tm organic stack", "tm brand packshot", "tm organic pack check",
               "--stage recipe"],
        "d2": ["tm tool elevenlabs voices", "--language", "tm tool music_index", "Mixkit", "tm brand save"],
        "e1": ["model-prompting/", "tm tool replicate_price", "the date", "kling-avatar-v2"],
        "e2": ["tm organic pack check", "--stage pack", "pack_vNN.md", "the resolution question",
               "Approve the generation pack and its cost", "tm decide pack approve", "tm budget approve ai_usd",
               "tm budget approve voice_credits", "tm decide pack approve --change", "tm decide pack reject"],
        "f1": ["tm tool replicate_run --run R", "--cost", "--resume", "tm organic dashboard-checked",
               "tm tool elevenlabs tts", "--timestamps", "tm organic page gate --gate images", "tm page await",
               "gate_images", "tm organic decisions --run R --page gate_images", "tm organic pick", "tm organic redo",
               "input_images", "tm decide images accept"],
        "f2": ["timed shot list", "a brisk, energetic TikTok pace, no pauses between sentences", "ratio: \"9:16\"",
               "Seedance 2.0", "kwaivgi/kling-avatar-v2", "burned-in text", "tm tool take_qa", "--gate video",
               "tm organic pick --run R --stage takes", "fails_qa", "tm tool deliver speed"],
        "g1": ["OrganicCaptions", "keepAudio", "volume", "zoom", "audioTracks", "music", "word groups",
               "phrases", "tm tool deliver measure", "tm render video", "tm tool deliver finish",
               "tm tool deliver upload", "tm tool deliver cover", "before `tm done G1`"],
        "g2": ["audience language", "tm kit check", "tm kit md"],
        "g4": ["tm trends collect on --run R", "tm organic page delivery", "tm page published --run R --page delivery",
               "tm page await --run R --page delivery", "collection `gate_edit`", "tm organic decisions --run R --page "
               "delivery", "tm kit check", "tm decide final_edit"],
        "h1": ["upload copy", "AI label", "tm tool deliver nosound", "tm done H1"],
    }
    for anchor, words in named.items():
        section = re.sub(r"\s+", " ", _section(flow_md, anchor))
        for w in words:
            assert w in section, (anchor, w)
    g1 = re.sub(r"\s+", " ", _section(flow_md, "g1"))
    done = g1.rindex("`tm done G1")
    assert g1.index("tm tool deliver upload") < done and g1.index("tm tool deliver cover") < done
    gate = re.sub(r"\s+", " ", _section(flow_md, "f1"))
    assert gate.index("tm page await") < gate.index("`ArtifactData` list") < gate.index("tm organic decisions")


def test_week_steps_name_the_engine_commands():
    """Task 21: each step of a week run says the commands the engine built for it; the desktop task's prompt names
    the workspace, the skill, the channel and "plan my week of videos" (decisions §9), else the by-hand sentence."""
    flow_md = _text(SKILL / "references" / "flow.md")
    named = {
        "i2": ["pb3_week.schema.json", "`flexible`", "tm organic week check",
               "tm organic page week", "CAPABILITIES[\"week\"]", "tm page await --run R --page week",
               "collection `week`", "tm organic decisions --run R --page week", "--text", "tm decide week approve",
               "The week is over its budget: switch a video to a script, swap it for a cheaper idea, or skip it."],
        "i3": ["tm organic start --run R", "except the flexible day", "one after another", "--keep-carried",
               "One run per day", "tm organic drop-slot --run R --day", "tm decide week approve --run R --change",
               "budget.per_week_usd", "tm organic flexible --run R --file", "03_wip/flexible_v01.json",
               "the flexible day's video is due tomorrow", "\"due today\" on the day itself",
               "tm organic week budget --run R --usd", "tm decide week approve --run R --change"],
        "i4": ["tm organic deliver-week --run R", "week_delivery", "05_results/posting_plan_vNN.json",
               "tm page await --run R --page week_delivery", "collection `gate_edit`",
               "tm organic decisions --run R --page week_delivery", "in that day's own run",
               "CAPABILITIES[\"gate\"]", "tm done I4", "only when the channel profile already holds"],
        "i5": ["../../references/schedule.md", "create_scheduled_task", "weekly-pack-", "weekly.run_day",
               "tm schedule --run R --how desktop_task", "tm schedule --run R --how by_hand",
               "'plan my week of videos'", "**On `by_hand`**, as soon as the check-in is decided",
               "**The week's report**, on both paths"],
    }
    for anchor, words in named.items():
        section = re.sub(r"\s+", " ", _section(flow_md, anchor))
        for w in words:
            assert w in section, (anchor, w)
    prompt = re.sub(r"\s+", " ", _section(flow_md, "i5")).split("and the `prompt`: ", 1)[1].split(" Then ", 1)[0]
    for part in ("Plan my week of videos for <channel>", "organic-video skill", "The workspace is \"<workspace>\"",
                 "runs/03-organic-ai-video/"):
        assert part in prompt, part
    cards = re.sub(r"\s+", " ", _text(SKILL / "references" / "checkin-cards.md"))
    assert "| Approve the week (`week`) |" in cards and "| Set up the weekly pack (`schedule`) |" in cards
    skill = re.sub(r"\s+", " ", _text(SKILL / "SKILL.md"))
    assert "**\"Plan my week of videos\"**: a week run" in skill and "arrives in a later version" not in skill


def test_animation_steps_name_the_engine_commands():
    """Task 19: an animation's taste pick, storyboard check-in and full render name the engine's commands where they
    are done, in OV9's order: the voiceover and its word SRT, the prompt, the storyboard drawn, its pick; then the
    animation drawn only from the accepted storyboard."""
    flow_md = _text(SKILL / "references" / "flow.md")
    named = {
        "d1": ["tm env install animatic --yes", "animation-styles.md"],
        "d2": ["tm organic atlas-styles", "no posters", "taste.style"],
        "e2": ["An animation is drawn, not generated", "voiceover's credits"],
        "f1": ["--timestamps", "tm organic atlas-prompt --run R", "--voiceover --storyboard --aspect 9:16",
               "--srt <the word SRT>", "_progress.txt", "tm organic storyboard --run R", "--stage storyboard",
               "storyboard rubric", "accepted after the pack check"],
        "f2": ["tm organic animate --run R", "refused until the storyboard is accepted", "30 fps",
               "drawn from its accepted storyboard", "tm decide video accept --run R --by rule"],
    }
    for anchor, words in named.items():
        section = re.sub(r"\s+", " ", _section(flow_md, anchor))
        for w in words:
            assert w in section, (anchor, w)
    f1 = re.sub(r"\s+", " ", _section(flow_md, "f1"))
    assert f1.index("--timestamps") < f1.index("tm organic atlas-prompt") < f1.index("tm organic storyboard --run R")
    c3 = re.sub(r"\s+", " ", _section(flow_md, "c3"))
    assert "An animation as an AI video" in c3 and "tm env install animatic --yes" in c3
    assert "animation, stills" not in c3 and "Animation, quiz" not in _text(SKILL / "SKILL.md")


def test_stills_and_sections_steps_name_the_engine_commands():
    """Task 20: stills with motion graphics (the cards at F1, the free render at F2 with the handoff's compositions), a video
    in sections (one video model for the footage, the insert in 9:16 with the caption band, the edit in the sections'
    order at G1) and the copied look (the style spec's evidence URLs, a still beside them before the render) are said
    where they are done; none of them "arrives in a later version"."""
    flow_md = _text(SKILL / "references" / "flow.md")
    named = {
        "c3": ["Stills with motion graphics", "the user's own", "A video in sections"],
        "d1": ["stills with motion graphics (`stills_motion`)", "in sections", "A video in sections",
               "the same video model", "`model: null`", "The copied look", "`style_spec`", "\"evidence\": [<url>, <url>]",
               "tm organic videos --run R --trend <id>"],
        "e2": ["Stills with motion graphics", "`images: 1`", "`model: null`", "A video in sections"],
        "f1": ["An animation insert", "--item S2", "--aspect 9:16", "caption band", "stills with motion graphics",
               "tm render still --run R --comp QuizGrid", "the latest still of the composition"],
        "f2": ["`QuizGrid`", "`RankingSplit`", "`RankingList`", "tm render video --run R --comp QuizGrid",
               "motion-graphics renders", "the cards' current picks"],
        "g1": ["A video in sections", "in their order", "renders/anim_vNN.mp4", "each from its own outputs"],
    }
    for anchor, words in named.items():
        section = re.sub(r"\s+", " ", _section(flow_md, anchor))
        for w in words:
            assert w in section, (anchor, w)
    for path in (SKILL / "SKILL.md", SKILL / "references" / "flow.md", SKILL / "references" / "checkin-cards.md",
                 SKILL / "references" / "variants.md"):
        text = re.sub(r"\s+", " ", _text(path)).lower()
        for words in ("quiz, ranking and sections arrive", "sections (a later version)", "quiz and ranking (a later",
                      "stills with motion graphics or sections** arrives"):
            assert words not in text, (path.name, words)


def test_animation_styles_reference_holds_the_brief_and_the_page_contract():
    """references/animation-styles.md (Task 19): the taste card in words (Decision 13: no posters), the setting
    replaced and the rendering kept (lesson 17), text above y 1260, the voiceover timed from the word SRT, the
    subagents' briefs with _progress.txt and their times (FLOWS K), and the page contract storyboard.mjs and
    render.mjs read."""
    text = re.sub(r"\s+", " ", _text(PLUGIN / "references" / "animation-styles.md"))
    for words in ("2 to 3 styles by number, name and description", "No style posters are in the package",
                  "Never a poster", "setting", "replaced by the topic's", "rendering", "is kept", "above y 1260",
                  "timed from the word SRT", "_progress.txt", "about 15 minutes", "window.STORYBOARD_READY = true",
                  "`p1` to `p6`", "window.makeSheet()", "window.seek(t)", "window.DURATION", "licence",
                  "tm organic atlas-prompt", "tm organic storyboard", "tm organic animate", "--stage storyboard"):
        assert words in text, words
    assert "gate" not in text.lower()


def test_big_calls_card_decided_member_by_member():
    """PR A's I2 ruling: the plan card's check-ins share no answer, so it is decided with each one's own command,
    in order, then the money approved."""
    skill = re.sub(r"\s+", " ", _text(SKILL / "SKILL.md"))
    row = skill.split("| `ask` |", 1)[1].split("\n", 1)[0]
    assert "share no answer" in row and "each check-in's own command, in the order the message gives" in row
    assert row.index("tm decide taste accept") < row.index("tm decide pack approve") < row.index("tm budget approve")
    cards = re.sub(r"\s+", " ", _text(SKILL / "references" / "checkin-cards.md"))
    plan = cards.split("| Approve the plan for this video |", 1)[1]
    assert plan.index("tm decide taste accept") < plan.index("tm decide pack approve") < plan.index("tm budget approve")


def test_doctor_md_command_line_lists_every_organic_output():
    """Task 10 review M2: the `tm doctor` line in doctor.md's organic section offers each output the
    engine knows, the production run's script_to_film included."""
    doctor_md = _text(PLUGIN / "commands" / "doctor.md").split("**Organic video.**", 1)[1]
    placeholder = re.search(r"tm doctor --playbook organic-video --outputs <([^>]+)>", doctor_md).group(1)
    assert sorted(placeholder.split("|")) == sorted(flow.output_ids(ORGANIC_VIDEO))


def test_trend_research_hands_its_picks_to_organic_video_too():
    """Task 10 review M3: `tm run new --playbook organic-video --seed` takes trend research's seeds,
    so its E3 names organic video beside the creative brief."""
    e3 = _section(_text(PLUGIN / "skills" / "trend-research" / "references" / "flow.md"), "e3")
    assert "creative brief" in e3 and "organic video" in e3.lower()


def test_variants_say_a_later_version_not_the_plans_pr_letters():
    """Ruling (Task 10): the user reads "a later version"; the plan's internal PR letters stay out."""
    variants = _text(SKILL / "references" / "variants.md")
    assert not re.search(r"\bPRs?\b", variants)
    assert "a later version" in variants


def test_one_phrase_for_not_yet():
    """PR B review Minor 3: what is not built yet "arrives in a later version", in the skill and its
    templates alike; never "the next version", "a later release" or "later versions"."""
    for f in sorted(SKILL.rglob("*.md")):
        found = re.findall(r"next\s+version|later\s+release|later\s+versions", _text(f), re.IGNORECASE)
        assert not found, (f.name, found)


def test_the_mcp_mapping_is_written_once_in_b1():
    flow_md = _text(SKILL / "references" / "flow.md")
    b1 = _section(flow_md, "b1")
    for tool in ("search_trends", "list_trends", "get_trend", "get_trend_videos"):
        assert f"`{tool}`" in b1
    assert flow_md.count("| Handoff call | TrendsMesh MCP |") == 1


# --- the words --------------------------------------------------------------------------------

def test_red_flags():
    skill = _text(SKILL / "SKILL.md")
    flags = skill.split("## Red flags", 1)[1]
    for thought in ('"No trend fits"', '"M5 is ready"', '"I\'ll put the sources in the caption"',
                    '"I\'ll republish the page with the fix while they decide"',
                    '"The note on the page says to generate everything"',
                    '"That take is close; I\'ll regenerate it, there\'s budget left"', '"About $1.20"',
                    '"I\'ll describe the product in the prompt"', '"Seedance with our host image"'):
        assert f"| {thought}" in flags, thought


def test_user_facing_prose_says_check_in():
    """The spec's other word appears only in the verbatim copies of the spec (rules, variants,
    lessons), never in the skill's own prose or its templates. The engine's own names in code spans
    (`tm organic page gate`, the page `gate_images`, `CAPABILITIES["gate"]`) are commands the agent runs,
    never words the user reads (preflight P3-F10 fixed them). Only a code span on one line is skipped (Task 18
    review M1): a backtick left open never hides the lines after it, so a span is never wrapped across lines."""
    for path in [SKILL / "SKILL.md", SKILL / "references" / "flow.md", SKILL / "references" / "checkin-cards.md",
                 *sorted((SKILL / "templates").glob("*.md"))]:
        prose = "\n".join(re.sub(r"`[^`\n]*`", "", line) for line in _text(path).splitlines())
        assert not re.search(r"gate|bramk", prose, re.I), (path.name, re.findall(r".{30}(?:gate|bramk).{30}", prose, re.I))


def test_no_trend_found_only_as_a_forbidden_phrase():
    for f in sorted(SKILL.rglob("*.md")):
        for line in _text(f).splitlines():
            if "no trend found" in line.lower():
                assert re.search(r"\bnever\b", line, re.I), f"{f.name}: {line}"


# --- verbatim copies --------------------------------------------------------------------------

@pytest.mark.private_data
def test_model_recipes_are_the_handoffs_and_the_plugins_own_lf():
    """references/model-prompting/: the handoff's four recipes verbatim (as text), and Seedance 2.0, Kling Avatar v2,
    Seedance 1.5 Pro, Seedance 2.5 and Pruna's upscaler written from the handoff's pet-store research, each with its sources
    and dated; pinned LF. The pack check reads this folder (`organic_pack.RECIPES`)."""
    assert organic_pack.RECIPES == RECIPES
    assert sorted(p.name for p in RECIPES.iterdir()) == sorted(VERBATIM_RECIPES + OWN_RECIPES)
    for name in VERBATIM_RECIPES:   # the handoff's, but for the client's line quoted in MiniMax's: a made-up one in ours
        assert _unquoted(_text(RECIPES / name)) == _unquoted(_text(HANDOFF_RECIPES / name)), name
    assert sorted(p.name for p in HANDOFF_RECIPES.iterdir()) == sorted(VERBATIM_RECIPES)
    for name in OWN_RECIPES:
        text = _text(RECIPES / name)
        assert re.search(r"^# .+: prompting recipe \(checked \d{4}-\d{2}-\d{2}\)$", text, re.M), name
        assert "\nSources:\n" in text and "pet-store-proposals/02_research/models/" in text, name
        assert len(re.findall(r"\b2026-11-0\d\b", text)) >= 3, name
    assert _pinned_lf("plugins/trendsmesh-playbooks/references/model-prompting/*.md")


def test_every_model_the_engine_routes_to_has_its_recipe():
    """Task 12's recipe check refuses a model with no recipe ("Write its recipe first"); the models the engine
    itself sends a video to (the default tier, a host image, a person from a description), the image model and the
    lip-sync alternative have one, and so has every model of the fixture packs, so a live pack passes."""
    fixtures = PLUGIN / "engine" / "tests" / "fixtures" / "organic"
    routed = {*organic_pack.TIERS.values(), organic_pack.FACE_HOST, organic_pack.DESCRIBED_PERSON, organic_pack.UPSCALER}
    assert routed == set(ROUTED_RECIPES)   # every tier (budget and premium too) and the default upscaler
    for model, name in ROUTED_RECIPES.items():
        assert (RECIPES / name).is_file() and model in _text(RECIPES / name), (model, name)
    named = {"minimax-h3.md": organic_pack.TIERS["default"], "seedance-2.0.md": organic_pack.DESCRIBED_PERSON}
    assert organic_pack.FACE_HOST == organic_pack.TIERS["default"] and organic_pack.TIERS["top"] == named["seedance-2.0.md"]
    for f in sorted(fixtures.glob("*_pack.json")):
        for m in json.loads(_text(f))["models"]:
            assert m["recipe"].startswith(organic_pack.RECIPE_PREFIX), (f.name, m)
            assert (RECIPES / m["recipe"][len(organic_pack.RECIPE_PREFIX):]).is_file(), (f.name, m["recipe"])
    for name, model in {**named, "gpt-image-2.md": "openai/gpt-image-2", "kling-avatar-v2.md": "kwaivgi/kling-avatar-v2"}.items():
        assert model in _text(RECIPES / name), (name, model)

@pytest.mark.private_data
def test_rules_hold_ov1_to_ov14_verbatim():
    playbook = _text(SPEC / "PLAYBOOK.md")
    hard = playbook.split("## 4. Hard rules (OV1–OV14)\n", 1)[1].split("\n## 5. ", 1)[0].strip()
    rules = _text(SKILL / "references" / "rules.md")
    assert hard in rules
    for n in range(1, 15):
        assert f"### OV{n}." in rules


@pytest.mark.private_data
def test_posting_kit_reference_is_the_handoffs_verbatim_and_lf():
    source = REPO / "handoff" / "organic-video_v02" / "resources" / "posting-kit" / "best_practices_2026-11.md"
    kit = PLUGIN / "references" / "posting-kit.md"
    assert _text(kit) == _text(source)
    sources = _text(kit).split("## Sources", 1)[1]
    assert re.findall(r"^- S(\d+) ", sources, re.M) == [str(n) for n in range(1, 35)]   # 34 dated sources
    assert _pinned_lf("plugins/trendsmesh-playbooks/references/posting-kit.md")


@pytest.mark.private_data
def test_templates_are_the_handoffs_four_and_lf():
    """The handoff's four templates, pinned LF, with their sections in their order (only the pack's "Gates"
    heading reads "Check-ins"); the plugin's own intake example beside them."""
    def headings(text: str) -> list[str]:
        return [line for line in text.splitlines() if line.startswith("#")]
    for name in ("channel_profile_template.md", "pack_template.md", "script_template.md",
                 "posting_kit_template.md"):
        path = SKILL / "templates" / name
        ours = [h.replace("## Check-ins", "## Gates") for h in headings(_text(path))]
        assert ours == headings(_text(SPEC / "templates" / name)), name
    assert (SKILL / "templates" / "intake_answers_example.json").is_file()
    assert _pinned_lf("plugins/trendsmesh-playbooks/skills/organic-video/templates/**")


@pytest.mark.parametrize("name", ["brand-and-audience.md", "trend-collection.md"])
def test_shared_references_name_organic_video(name):
    text = _text(PLUGIN / "references" / name)
    assert "organic video" in text.lower()
    if name == "brand-and-audience.md":
        assert "## Channel profile" in text and "it is refused until then" not in text


def test_channel_profile_example_passes_the_check(tmp_path):
    """The `channel/1` example in brand-and-audience.md is one the engine saves as it is."""
    from tm import brand
    text = _text(PLUGIN / "references" / "brand-and-audience.md").split("## Channel profile", 1)[1]
    profile = json.loads(text.split("```json", 1)[1].split("```", 1)[0])
    assert brand.check(profile, workspace=tmp_path) == []
    assert profile["confirmed"] is None   # the user's date, set by tm brand save --confirmed
