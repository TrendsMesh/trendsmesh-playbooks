"""The handoff's ExampleEdu walkthrough (handoff/organic-video_v02, its walkthrough run) as an organic
video run.

This module is the one loader of the ExampleEdu files (PB02's `ld.py` pattern): no test reads them on its
own. Its trend files are saved through `trends.save_answer` as the collector saves them, so the names
are the collector's:
- `card_<id8>.json` -> `get_trend` of the card's full id -> `02_research/trend_<full id>.json`;
- `videos_<id8>.json` -> `get_trend_videos` of that id, as it is (one REST page) ->
  `02_research/videos/<full id>_p01.json`, so a proposal's `pick` index is into `trends.load_videos`;
- `search_<n>.json` -> `search_trends` with `about` = its query -> `02_research/search/search_<about>.json`.
  The files keep no query: `QUERIES` are the 17 the manifest names, in its order (the manifest's
  row for `02_research/trends/search_1–17.json`); each file's cards fit its query.

The channel profile (`PROFILE`, a made-up `channel/1` in the shape of `00_raw/channel_profile_v02.md`, none of
its words) goes into the library, and `03_wip/proposals/proposals_v02.json` is copied unchanged into the run's `03_wip`
for Task 6. `proposals()` is that file with the plugin's block on each proposal
(`fixtures/organic/exampleedu_plugin_blocks.json`: M1 animation, M2 talking_character, M3 ai_footage,
M4 animation, M5 talking_character, M6 stills_motion), as the agent writes it at C1.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
from datetime import date
from pathlib import Path

import private
from tm import brand, config, organic_config, trends
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder

REPO = Path(__file__).resolve().parents[4]
WALKTHROUGH = private.run_folder("organic-video_v02", "-walkthrough") if private.AVAILABLE else REPO / "handoff"
TRENDS = WALKTHROUGH / "02_research" / "trends"
PROPOSALS = WALKTHROUGH / "03_wip" / "proposals" / "proposals_v02.json"
PLUGIN_BLOCKS = Path(__file__).resolve().parent / "fixtures" / "organic" / "exampleedu_plugin_blocks.json"
CREATED = date(2026, 11, 6)   # the walkthrough's day (manifest.md)
NAME = "exampleedu"
CHANNEL = "exampleedu"
# The shortlisted trends whose cards and evidence videos were pulled (manifest.md, in its order).
TREND_IDS = ("c20bfd65", "0112ede8", "8f8de71e", "e54e5955", "829ecf9b", "9a17a078", "5f1691dd",
             "abf9ffed", "3abc109a", "7d60086a", "8db205e0", "250013b0")
# search_1.json … search_17.json, in the manifest's order ("17 queries EN/PL").
QUERIES = ("parents kids video games", "screen time", "Roblox", "Minecraft", "gaming addiction",
           "parenting tips", "kids phone", "dzieci gry", "rodzice", "gamer kid", "brainrot", "kids slang",
           "Fortnite", "Grow a Garden", "school", "explaining to parents", "research")

# A made-up channel/1 profile, of the shape of 00_raw/channel_profile_v02.md (not its words)
PROFILE = {
    "schema": "channel/1", "kind": "channel", "channel": "ExampleEdu", "store": None,
    "platforms": ["tiktok", "youtube", "instagram", "facebook"], "account_type": "creator",
    "audience_language": "pl",
    "context": {
        "films": "quick explainers that turn studies on kids and play into tips",
        "topic": "gaming help for mums and dads: playtime limits, online safety, picking games, what play builds",
        "audience": "mums and dads whose kids play games",
        "style": "warm, upbeat, useful; grounded in studies yet plain; never alarmist",
        "performed_links": [],
    },
    "product_role": "not_shown",
    "content_rules": ["no real children's faces", "sources for claims", "no medical claims"],
    "voice": {"narrator_elevenlabs_id": None, "host_description": None, "host_image": None},
    "music": {"folder": None, "index": None},
    "assumptions": ["the channel speaks Polish", "mostly parents in their thirties and forties",
                    "warm, upbeat, useful; never alarmist",
                    "a children's niche: no real children's faces, sources for claims, "
                    "no medical claims"],
    "confirmed": None,
    "type": "howto_education", "type_note": None,
}


KITS = WALKTHROUGH / "04_final" / "kits"
# The plugin block the agent writes with a kit (kit.py): M1 is a cartoon animation, M5 a photoreal AI host.
KIT_PLUGIN = {"M1": {"ai_label": False, "trending_sound": None, "business_alternative": None,
                     "platforms": ["tiktok", "instagram", "youtube", "facebook"], "youtube_thumbnail": False},
              "M5_pl": {"ai_label": True, "trending_sound": None, "business_alternative": None,
                        "platforms": ["tiktok", "instagram", "youtube", "facebook"], "youtube_thumbnail": False}}


def _json(path: Path):
    """A JSON file of the walkthrough (or a fixture), with the client's name as the plugin's alias (private.alias)."""
    return private.alias(json.loads(path.read_text(encoding="utf-8")))


def full_ids() -> dict[str, str]:
    """Each shortlisted trend's 8-character id -> its full id (from its card)."""
    return {short: _json(TRENDS / f"card_{short}.json")["id"] for short in TREND_IDS}


def proposals() -> dict:
    """proposals_v02.json with the plugin's block on each proposal."""
    data = _json(PROPOSALS)
    blocks = _json(PLUGIN_BLOCKS)
    for p in data["proposals"]:
        p["plugin"] = blocks[p["id"]]
    return data


def save_trends(run: RunFolder) -> None:
    """The walkthrough's searches, cards and video pages, saved as the collector saves them."""
    for n, query in enumerate(QUERIES, 1):
        cards = _json(TRENDS / f"search_{n}.json")
        trends.save_answer(run, "search_trends", {"about": query, "limit": len(cards)}, cards)
    for short, tid in full_ids().items():
        trends.save_answer(run, "get_trend", {"trend_id": tid}, _json(TRENDS / f"card_{short}.json"))
        trends.save_answer(run, "get_trend_videos", {"trend_id": tid}, _json(TRENDS / f"videos_{short}.json"))


def build(workspace: Path) -> RunFolder:
    """An organic video run `exampleedu` (created 2026-11-06) for the channel exampleedu: its config, the
    channel profile in the library, the walkthrough's trend files, and proposals_v02.json."""
    workspace = Path(workspace)
    run = RunFolder.create(workspace, NAME, CREATED, playbook=ORGANIC_VIDEO)
    config.save(run, {**organic_config.defaults(), "channels": [CHANNEL], "page_lang": "pl"})
    brand.save(workspace, PROFILE, run=run)
    save_trends(run)
    shutil.copyfile(PROPOSALS, run.path / "03_wip" / PROPOSALS.name)
    return run


def kit(stem: str) -> dict:
    """The reference kit `stem` (M1_kit_v01, M1_kit_v02 or M5_pl_kit_v01) with the plugin block of its video."""
    data = _json(KITS / f"{stem}.json")
    data["plugin"] = copy.deepcopy(KIT_PLUGIN[stem.split("_kit")[0]])
    return data


EDIT_GATE = WALKTHROUGH / "03_wip" / "gates" / "edit_gate_v02.json"


def edit_gate() -> dict:
    """M1's delivery page data (03_wip/gates/edit_gate_v02.json, the original's "edit gate"), as the handoff has it."""
    return _json(EDIT_GATE)


def place_edit_gate_files(run: RunFolder) -> list[str]:
    """A small placeholder at each run path edit_gate_v02.json shows or offers for download; the paths, in order."""
    out = []
    for item in edit_gate()["items"]:
        for entry in [*item.get("options", []), *item.get("refs", [])]:
            for src in (entry["src"], (entry.get("download") or {}).get("src")):
                if src and src not in out:
                    path = run.path / src
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"placeholder " + Path(src).name.encode("utf-8"))
                    out.append(src)
    return out


SCRIPT = WALKTHROUGH / "03_wip" / "M5" / "script_M5_en_v01.json"
SCRIPT_PAGE = WALKTHROUGH / "04_final" / "M5_script_en_v01"


def script() -> dict:
    """M5's English script to film (script_M5_en_v01.json) with the plugin block the agent writes: the
    user's words for the English version of a Polish channel's script."""
    data = _json(SCRIPT)
    data["plugin"] = {"lang_request": "English version"}
    return data


def script_package() -> tuple[str, str]:
    """The handoff's own page and Markdown for it (04_final/M5_script_en_v01/), their `\\r` stripped."""
    def read(name: str) -> str:
        return private.alias((SCRIPT_PAGE / name).read_text(encoding="utf-8").replace("\r", ""))
    return read("index.html"), read("M5_script_v01.md")


M5_PL = WALKTHROUGH / "03_wip" / "M5_pl"
# Whisper's transcripts of two H3 takes of the same four lines: M5 PL's take (word for word, manifest row
# "first native Polish speech on H3") and round 46's take with a Polish voice reference (garbled names and
# numbers, plus a sentence that was never written).
TRANSCRIPTS = {"take": M5_PL / "qa" / "transcript.json",
               "voiceref": WALKTHROUGH / "03_wip" / "voiceref" / "qa" / "transcript_pl.json"}


def take_lines() -> list[str]:
    """The lines M5 PL's take speaks: those quoted in take_v01.json's prompt, in their order."""
    prompt = _json(M5_PL / "take_v01.json")["input"]["prompt"]
    return re.findall(r'"([^"]+)"', prompt)


def take_script() -> str:
    """The script M5 PL's take speaks: `take_lines`, joined."""
    return " ".join(take_lines())


def transcript(which: str) -> dict:
    """A take's Whisper transcript (`TRANSCRIPTS`: "take" or "voiceref")."""
    return _json(TRANSCRIPTS[which])


EDIT_PROPS = M5_PL / "edit_v02.props.json"


def edit_props() -> dict:
    """M5 PL's edit (03_wip/M5_pl/edit_v02.props.json): the OrganicCaptions props of its final v01, the take
    with its own sound, four hook lines at the top and the spoken words at the bottom. Its paths are relative
    to the reference run's public folder, 03_wip (`M5_pl/take_v01_0.mp4`)."""
    return _json(EDIT_PROPS)


def kit_template() -> str:
    """templates/posting_kit_template.md of the handoff, as text (the file is CRLF)."""
    path = REPO / "handoff" / "organic-video_v02" / "playbook-03-organic-ai-video" / "templates" / "posting_kit_template.md"
    return private.alias(path.read_text(encoding="utf-8").replace("\r\n", "\n"))


WEEK = WALKTHROUGH / "03_wip" / "weekly" / "week_v01.json"
WEEK_BLOCKS = Path(__file__).resolve().parent / "fixtures" / "organic" / "exampleedu_week_plugin_blocks.json"
# The weekly pack dry cycle (manifest.md, round 48): the page's meter at $2.94, $1.48 once the Wednesday video
# ("dad, why is _", $1.46) is a script, $2.81 once Monday's idea is swapped for the reserve r2 ($1.33).
WEEK_TOTALS = (2.94, 1.48, 2.81)
# r2's trend ("Nintendo Switch 2 game and preorder news"): the walkthrough pulled no card of it, only the search
# answers name it (search_1, search_5, search_10); `save_week_cards` saves that search card as get_trend's answer.
SWITCH = "c5d7527b3d0149399145c3bd7b7a04be"


def week() -> dict:
    """03_wip/weekly/week_v01.json with the plugin's block on every slot and reserve
    (`fixtures/organic/exampleedu_week_plugin_blocks.json`: each idea's trends among the walkthrough's cards, its
    production type, approach and product level; w5, Sunday's brainrot part 2, is the series `brainrot` and the
    flexible day), as the agent writes it at I2."""
    data = _json(WEEK)
    blocks = _json(WEEK_BLOCKS)
    for idea in [*data["slots"], *data["reserves"]]:
        idea["plugin"] = copy.deepcopy(blocks[idea["id"]])
    return data


def save_week_cards(run: RunFolder) -> None:
    """The card of r2's trend, as the agent fetches it at B3 (the walkthrough's search answer's card)."""
    card = next(c for c in _json(TRENDS / "search_1.json") if c["id"] == SWITCH)
    trends.save_answer(run, "get_trend", {"trend_id": SWITCH}, card)


M1 = WALKTHROUGH / "03_wip" / "M1"


def m1_file(name: str) -> Path:
    """One of M1's animation files (03_wip/M1/): content_v01.txt (the animation brief's content) or vo_words_v01.srt
    (the voiceover's word SRT). The original prompt and pages were built on a third-party style library and are gone (#75)."""
    if name not in ("content_v01.txt", "vo_words_v01.srt"):
        raise ValueError(f"{name} is not one of M1's animation files")
    return M1 / name


def m1_text(name: str) -> str:
    """An M1 animation file as text, its `\\r` stripped (the handoff's files are CRLF)."""
    return private.alias(m1_file(name).read_text(encoding="utf-8").replace("\r", ""))
