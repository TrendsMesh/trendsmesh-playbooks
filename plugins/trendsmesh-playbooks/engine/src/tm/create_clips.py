"""The model ads' clips for the concepts page (issue #97): each model ad's thumbnail and its first ~15 s, saved into
the run from its saved answer (the Ad Library's, or TrendsMesh's), so they play on the page.

    tm ad clips --run R --file <the concepts file> [--json]

For each model ad of the concepts file with a saved answer (`saved`) and no `clip` of its own, the ad is found in that
answer by its id, and the first video file and preview image it names are downloaded:

    02_research/clips/<id>_15s.mp4     the first CLIP_S seconds, H.264 / AAC, at most MAX_W wide
    02_research/clips/<id>_thumb.jpg   its preview image (page.fetch_image)

The concepts page shows a model ad's `clip` and `thumb` when the concepts file names them, else these files. A file
already there is kept (no new download). An ad whose answer names no video file (an image ad, or an answer with only
the Ad Library's snapshot page) gets its thumbnail alone, and says so. Only http(s) URLs of a video (or an image) are
fetched, never the snapshot page, whose URL carries an access token. Nothing here spends money.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

from tm import create_plan, manifest, page
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop
from tm.tools import _common as tools_common

FOLDER = f"{create_plan.RESEARCH}/clips"
CLIP_S = 15
MAX_W = 720
MAX_BYTES = 300 * 10**6        # the whole ad, before it is cut
TIMEOUT_S = 120
SOURCE = "tm ad clips"
# where an answer names an ad's video file and its preview image, best first (the Ad Library's ad snapshot, and
# TrendsMesh's videos)
VIDEO_KEYS = ("video_hd_url", "video_sd_url", "watermarked_video_hd_url", "watermarked_video_sd_url", "video_url",
              "download_url")
IMAGE_KEYS = ("video_preview_image_url", "thumbnail_url", "preview_image_url", "original_image_url",
              "resized_image_url", "image_url")
ID_KEYS = ("id", "ad_archive_id", "ad_id", "video_id")
_SAFE = re.compile(r"[^A-Za-z0-9_-]+")


def stem(ad_id: object) -> str:
    """A model ad's id as a file name."""
    return _SAFE.sub("_", str(ad_id)).strip("_")[:60] or "ad"


def clip_path(run: RunFolder, ad_id: object) -> Path:
    return run.path / FOLDER / f"{stem(ad_id)}_{CLIP_S}s.mp4"


def thumb_path(run: RunFolder, ad_id: object) -> Path:
    return run.path / FOLDER / f"{stem(ad_id)}_thumb.jpg"


def _record_of(answer: object, ad_id: str) -> dict | None:
    """The object in the answer whose id is the model ad's id (anywhere in it)."""
    stack = [answer]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if any(str(node.get(k)) == ad_id for k in ID_KEYS if node.get(k) is not None):
                return node
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(reversed(node))
    return None


def _url(node: object, keys: tuple[str, ...]) -> str | None:
    """The first http(s) URL under one of `keys` (in their order), anywhere in `node`."""
    found: dict[str, str] = {}
    stack = [node]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for k, v in item.items():
                if k in keys and k not in found and isinstance(v, str) and urlsplit(v).scheme in ("http", "https"):
                    found[k] = v
                elif isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(item, list):
            stack.extend(reversed(item))
    return next((found[k] for k in keys if k in found), None)


def _download(url: str, dest: Path) -> str | None:
    """The video at `url` saved to `dest`; None when done, else what went wrong (in words)."""
    try:
        answer = requests.get(url, timeout=30, stream=True)
    except requests.RequestException as exc:
        return f"the download failed ({exc.__class__.__name__})"
    try:
        if answer.status_code >= 400:
            return f"the video's address answered HTTP {answer.status_code} (an Ad Library link expires: search again)"
        kind = str(answer.headers.get("Content-Type", "")).split(";")[0].strip().lower()
        if not (kind.startswith("video/") or kind == "application/octet-stream"):
            return f"the address is not a video ({kind or 'no type'})"
        deadline, size = time.monotonic() + TIMEOUT_S, 0
        with open(dest, "wb") as fh:
            for chunk in answer.iter_content(chunk_size=1 << 16):
                size += len(chunk)
                if size > MAX_BYTES or time.monotonic() > deadline:
                    return "the video is too big or too slow to download"
                fh.write(chunk)
        return None
    except (requests.RequestException, OSError) as exc:
        return f"the download failed ({exc.__class__.__name__})"
    finally:
        answer.close()


def _cut(source: Path, target: Path) -> str | None:
    """The first CLIP_S seconds of `source` as `target` (H.264 / AAC, at most MAX_W wide, fast start)."""
    tmp = target.with_name(f".{target.stem}.{os.getpid()}.mp4")
    try:
        tools_common.run_ffmpeg(["-i", tools_common.media(source), "-t", str(CLIP_S), "-map", "0:v:0", "-map", "0:a:0?",
                                 "-vf", f"scale='min({MAX_W},iw)':-2", "-c:v", "libx264", "-preset", "veryfast",
                                 "-crf", "26", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
                                 "-movflags", "+faststart", tools_common.media(tmp)])
        os.replace(tmp, target)
        return None
    except (OSError, subprocess.CalledProcessError):
        return "ffmpeg could not read the downloaded video"
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)


def _rel(run: RunFolder, path: Path) -> str:
    return path.relative_to(run.path).as_posix()


def _answer(run: RunFolder, rel: object) -> object:
    path = (run.path / str(rel)).resolve() if isinstance(rel, str) and rel.strip() else None
    try:
        if path is None:
            return None
        path.relative_to(run.path.resolve())
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def fetch(run: RunFolder, file: str | Path) -> dict:
    """Save each model ad's clip and thumbnail into the run (above): `{"ads": [{id, clip, thumb, problem}]}`."""
    path = Path(file) if Path(file).is_absolute() else run.path / file
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise Stop(f"The concepts file {file} cannot be read ({exc}). Write it as JSON with the Write tool; {AGAIN}.") \
            from None
    ads = [a for a in (data.get("model_ads") if isinstance(data, dict) else None) or []
           if isinstance(a, dict) and a.get("id") not in (None, "")]
    out = []
    for ad in ads:
        ad_id = str(ad["id"])
        row: dict = {"id": ad_id, "clip": None, "thumb": None, "problem": None}
        out.append(row)
        clip, thumb = clip_path(run, ad_id), thumb_path(run, ad_id)
        if isinstance(ad.get("clip"), str) and (run.path / ad["clip"]).is_file():
            row["clip"] = ad["clip"]                   # its own clip, saved before
        record = _record_of(_answer(run, ad.get("saved")), ad_id) if ad.get("saved") else None
        if row["clip"] is None and not clip.is_file() and record is None:
            row["problem"] = ("no saved answer names it (saved)" if ad.get("saved") else
                              "it has no saved answer: save its clip (the first ~15 s) in the run and name it in clip")
            continue
        clip.parent.mkdir(parents=True, exist_ok=True)
        if row["clip"] is None and clip.is_file():
            row["clip"] = _rel(run, clip)
        elif row["clip"] is None:
            url = _url(record, VIDEO_KEYS)
            if url is None:
                row["problem"] = "its saved answer names no video file (an image ad, or only the snapshot page)"
            else:
                whole = clip.with_name(f".{clip.stem}.{os.getpid()}.download")
                try:
                    row["problem"] = _download(url, whole) or _cut(whole, clip)
                finally:
                    with contextlib.suppress(OSError):
                        whole.unlink(missing_ok=True)
                if row["problem"] is None:
                    row["clip"] = _rel(run, clip)
                    manifest.record(run, row["clip"], create_plan.RESEARCH, SOURCE, parent=str(ad.get("saved")),
                                    params={"seconds": CLIP_S})
        if isinstance(ad.get("thumb"), str) and (run.path / ad["thumb"]).is_file():
            row["thumb"] = ad["thumb"]
        elif thumb.is_file():
            row["thumb"] = _rel(run, thumb)
        elif record is not None and page.fetch_image(_url(record, IMAGE_KEYS), thumb):
            row["thumb"] = _rel(run, thumb)
            manifest.record(run, row["thumb"], create_plan.RESEARCH, SOURCE, parent=str(ad.get("saved")))
    return {"ads": out}


def words(result: dict) -> str:
    """What `tm ad clips` says: each model ad's clip and thumbnail, or why it has none."""
    lines = []
    for r in result["ads"]:
        got = ", ".join(x for x in (r["clip"], r["thumb"]) if x) or "nothing saved"
        lines.append(f"- {r['id']}: {got}" + (f" ({r['problem']})" if r["problem"] else ""))
    missing = [r["id"] for r in result["ads"] if not r["clip"]]
    tail = (" A model ad without a clip shows its thumbnail, or its link alone: say so to the user at the check-in."
            if missing else "")
    return "The model ads' clips for the concepts page:\n" + "\n".join(lines) + "\n" + \
        "The page shows them by themselves (no need to name them in the concepts file)." + tail
