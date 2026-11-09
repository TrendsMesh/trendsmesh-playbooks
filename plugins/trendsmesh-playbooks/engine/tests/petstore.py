"""The handoff's pet-store examples (handoff/organic-video_v02/examples/pet-store-proposals, and the price file
of its dry run) as an organic video run.

This module is the one loader of the pet-store files (PB02's `ld.py` pattern): no test reads them on its
own. `build` makes the run `pet-dtc` (created 2026-11-05, the proposals run's day) with:
- the store Brushwell Pets (`STORE`, typed from `00_raw/scenario_v01.md` as `brand/1`) and its catalogue in
  the library, with placeholder PNG packshots of the deshedding brush and the lick mat (the two the dry run
  made), saved through `brand.save_packshot` as `tm brand packshot` saves them (`PACKSHOTS`);
- its three channels (`CHANNELS`, typed from the scenario as `channel/1`), keyed as config.yaml names them;
- the trend cards and evidence videos of `02_research/trends/`, saved through `trends.save_answer` as the
  collector saves them (`card_<id8>.json` -> `get_trend`, `videos_<id8>.json` -> `get_trend_videos`), the
  videos the fixtures name under made-up creator handles (`CREATORS`);
- the price files, named as `tm tool replicate_price` names them (`PRICE_FILES`): the 2026-11-06 files of
  `02_research/models/` and the dry run's `03_wip/packs/prices_2026-11-04.json`, the only one that prices
  `openai/gpt-image-2`;
- `03_wip/proposals/proposals_v01.json`, copied unchanged into the run's `03_wip`.
"""

from __future__ import annotations

import base64
import json
import shutil
from datetime import date
from pathlib import Path

from tm import brand, config, organic_config, trends
from tm.playbooks import ORGANIC_VIDEO
from tm.runfolder import RunFolder

REPO = Path(__file__).resolve().parents[4]
EXAMPLES = REPO / "handoff" / "organic-video_v02" / "examples"
PROPOSALS_RUN = EXAMPLES / "pet-store-proposals"
DRY_RUN = EXAMPLES / "pet-store-dry-run"
TRENDS = PROPOSALS_RUN / "02_research" / "trends"
MODELS = PROPOSALS_RUN / "02_research" / "models"
PROPOSALS = PROPOSALS_RUN / "03_wip" / "proposals" / "proposals_v01.json"
CREATED = date(2026, 11, 5)   # the proposals run's day (manifest.md)
NAME = "pet-dtc"

# Each price file of the examples -> its name in the run (02_research/models/prices_<checked>_vNN.json).
PRICE_FILES = ((MODELS / "prices_2026-11-06.json", "prices_2026-11-06_v01.json"),
               (MODELS / "prices_seedance_tiers_2026-11-06.json", "prices_2026-11-06_v02.json"),
               (MODELS / "prices_upscale_2026-11-06.json", "prices_2026-11-06_v03.json"),
               (DRY_RUN / "03_wip" / "packs" / "prices_2026-11-04.json", "prices_2026-11-04_v01.json"))

STORE_NAME = "Brushwell Pets"
# 00_raw/scenario_v01.md, "The store", typed as brand/1 with its catalogue.
STORE = {
    "schema": "brand/1", "kind": "brand", "brand": STORE_NAME,
    "stands_for": "Dog products that solve shedding, dry paws, bath stress and boredom at home.",
    "tone": ["friendly", "practical", "light"], "off_limits": ["direct product promotion"], "off_limits_asked": True,
    "claims": [], "competitors": [], "guide": {"source": "none", "where": ""}, "drafted_from": ["user"],
    "confirmed": None,
    "catalog": {"products": [
        {"name": "deshedding brush", "packshot": None, "problems": ["shedding and hair on furniture"]},
        {"name": "paw balm", "packshot": None, "problems": ["dry, cracked paws"]},
        {"name": "oatmeal dog shampoo", "packshot": None, "problems": ["bath time stress"]},
        {"name": "lick mat", "packshot": None, "problems": ["boredom and anxiety at home"]}]},
}
# The two packshots the dry run made (01_base/brush_packshot.png, lickmat_packshot.png): product -> file in 00_raw.
PACKSHOTS = {"deshedding brush": "brush_packshot.png", "lick mat": "lickmat_packshot.png"}
# A 1x1 PNG: the packshots are placeholders (the handoff leaves the images out).
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/58BAwAI/AL+hc2rNAAAAABJRU5ErkJggg==")


def _channel(name: str, films: str, topic: str, platforms: list[str], role: str) -> dict:
    return {
        "schema": "channel/1", "kind": "channel", "channel": name, "store": STORE_NAME, "platforms": platforms,
        "account_type": "creator", "audience_language": "en",
        "context": {"films": films, "topic": topic, "audience": "US dog owners", "style": "faceless, friendly, quick",
                    "performed_links": []},
        "product_role": role, "content_rules": ["no direct product promotion", "no logos on screen"],
        "voice": {"narrator_elevenlabs_id": None, "host_description": None, "host_image": None},
        "music": {"folder": None, "index": None},
        "assumptions": ["fictional channel of the dry-run scenario", "owned by the store, not branded"],
        "confirmed": None,
    }


# 00_raw/scenario_v01.md, "The channels", typed as channel/1; the proposals' channel ids -> their profiles.
CHANNELS = {
    "shed": _channel("Shed Happens", "grooming tips over AI video", "grooming: shedding, baths, paws",
                     ["tiktok", "instagram", "youtube"], "incidental"),
    "why": _channel("Why Dogs Do That", "dog behaviour explained with a voiceover", "dog behaviour explained",
                    ["tiktok", "youtube"], "not_shown"),
    "hacks": _channel("Good Boy Hacks", "quick DIY tricks for dogs", "homemade chew toys, stress-free nail trims",
                      ["tiktok", "instagram"], "soft_mention"),
}
KEYS = {cid: brand.channel_key(p["channel"]) for cid, p in CHANNELS.items()}   # shed -> shed-happens, ...


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def proposals() -> dict:
    """proposals_v01.json as it is."""
    return _json(PROPOSALS)


def proposal(pid: str) -> dict:
    """One proposal of proposals_v01.json (p1 … p6)."""
    return next(p for p in proposals()["proposals"] if p["id"] == pid)


# The evidence videos that the P4 pack's style spec names (fixtures/organic/p4_host_pack.json, made up after the
# reference pack), by TikTok video id -> the made-up creator handle the fixtures and tests use. As `private.alias` does for the
# clients' names, the saved videos carry the made-up handle, so nothing public names the real creator.
CREATORS = {"7681503578850069790": "creator_0101", "7703033505646742817": "creator_0102"}


def _made_up_creators(page: dict) -> dict:
    """A videos page with each `CREATORS` video's URL and creator under its made-up handle."""
    for video in page.get("videos") or []:
        vid = str(video.get("asset_id") or "").removeprefix("tiktok:")
        if vid in CREATORS:
            handle = CREATORS[vid]
            video.update(url=f"https://www.tiktok.com/@{handle}/video/{vid}", creator=handle, creator_id=handle)
    return page


def save_trends(run: RunFolder) -> None:
    """The proposals run's cards and evidence videos, saved as the collector saves them."""
    for card_file in sorted(TRENDS.glob("card_*.json")):
        short = card_file.stem.removeprefix("card_")
        card = _json(card_file)
        trends.save_answer(run, "get_trend", {"trend_id": card["id"]}, card)
        trends.save_answer(run, "get_trend_videos", {"trend_id": card["id"]},
                           _made_up_creators(_json(TRENDS / f"videos_{short}.json")))


def save_prices(run: RunFolder) -> list[str]:
    """The price files in the run's 02_research/models/, as `tm tool replicate_price` names them; their
    run-relative paths."""
    folder = run.path / "02_research" / "models"
    folder.mkdir(parents=True, exist_ok=True)
    for source, name in PRICE_FILES:
        shutil.copyfile(source, folder / name)
    return [f"02_research/models/{name}" for _, name in PRICE_FILES]


def build(workspace: Path) -> RunFolder:
    """An organic video run `pet-dtc` (created 2026-11-05) for the store's three channels: its config, the
    store with its catalogue and packshots, the channel profiles, the trend files, the price files and
    proposals_v01.json."""
    workspace = Path(workspace)
    run = RunFolder.create(workspace, NAME, CREATED, playbook=ORGANIC_VIDEO)
    config.save(run, {**organic_config.defaults(), "channels": list(KEYS.values()), "page_lang": "en"})
    brand.save(workspace, STORE, run=run)
    for product, name in PACKSHOTS.items():
        source = run.path / "00_raw" / name
        source.write_bytes(PNG)
        brand.save_packshot(workspace, STORE_NAME, product, source, run=run)
    for profile in CHANNELS.values():
        brand.save(workspace, profile, run=run)
    save_trends(run)
    save_prices(run)
    shutil.copyfile(PROPOSALS, run.path / "03_wip" / PROPOSALS.name)
    return run


# The edits of the reference motion-graphics videos (Task 20): their public folder was 03_wip, so a file they name is
# relative to that folder (R1/take5_v01_0.mp4, P6/donut_v02_0.png, music/...); the media are not in the handoff.
R1_PROPS = DRY_RUN / "03_wip" / "R1" / "edit_v02.props.json"          # the R1 ranking v02, RankingSplit
P6_PROPS = PROPOSALS_RUN / "03_wip" / "P6" / "edit_v01.props.json"    # the P6 quiz, QuizGrid


def r1_props() -> dict:
    """The dry run's R1 ranking edit (RankingSplit, the look copied from the evidence, lesson 21) as it is."""
    return _json(R1_PROPS)


def p6_props() -> dict:
    """The P6 quiz edit (QuizGrid: four cards, a countdown, the reveal, music) as it is."""
    return _json(P6_PROPS)


def packshot(workspace: Path, product: str) -> str:
    """The workspace-relative library path of a product's packshot, as the store's catalogue names it."""
    products = brand.latest(Path(workspace), STORE_NAME)["catalog"]["products"]
    return next(p["packshot"] for p in products if p["name"] == product)
