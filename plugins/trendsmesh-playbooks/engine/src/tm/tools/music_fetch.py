"""Music for the edit (organic video's D2 and G1, issue 89): a Mixkit track found, fetched and indexed, and the tracks
offered copied into the run.

    tm tool music_fetch --run RUN --search "<words>" [--json]
    tm tool music_fetch --run RUN --mixkit ID [--page URL] [--yes] [--json]
    tm tool music_fetch --run RUN --copy TRACK [--copy TRACK ...] [--json]

- `--search`: the tracks Mixkit's search lists for the words (`https://mixkit.co/free-stock-music/discover/<words>/`):
  id, title, author, length, tags (its moods among them) and the preview, which is the track's own file. Free.
- `--mixkit ID`: the track's card on the Mixkit page that lists it (`--page`, a mixkit.co address; default the search
  page the track was found on, or Mixkit's music front page) and its file's size: title, author, length, size and
  licence (the Mixkit Stock Music Free License, which allows commercial use without credit). Nothing is downloaded:
  it stops (exit 2) so the user is asked. With `--yes`, after the user's yes, the file (Mixkit's fixed address,
  `assets.mixkit.co/music/<id>/<id>.mp3`, no account) is downloaded into the channel's music folder as
  `mixkit-<title>-<id>.mp3`, tagged with its title, author, moods, licence and source, and the folder is indexed
  (`tm tool music_index`: the run's next `02_research/music_index_vNN.csv`, every field filled). A track already
  there is never downloaded again.
- `--copy TRACK`: tracks of the channel's music folder (each by its name, or a path) copied into the run,
  `02_research/music/<name>` (the same file again is reused, never overwritten): the 2 to 3 offered at D2, which the
  style, voice and music page plays (a page plays only the run's own files), and so the edit's `music.src` names the
  picked one in the run.

The channel's music folder is the channel profile's `music.folder` (a path, or one inside the workspace), else
`library/channels/<channel>/music/`. Only mixkit.co is read; only the track's mp3 on assets.mixkit.co is downloaded.
"""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

from tm import __version__, brand, config, state, trend_spool
from tm.tools import _common as c
from tm.tools import music_index

FRONT = "https://mixkit.co/free-stock-music/"
SEARCH = "https://mixkit.co/free-stock-music/discover/{words}/"
FILE = "https://assets.mixkit.co/music/{id}/{id}.mp3"
LICENCE = "Mixkit Stock Music Free License"
LICENCE_URL = "https://mixkit.co/license/#musicFree"
RUN_MUSIC = "02_research/music"
MAX_MB = 60
USER_AGENT = f"trendsmesh-playbooks/{__version__} (music for an edit; one track after the user's yes)"
TIMEOUT = 60


def _get(url: str) -> str:
    import requests

    answer = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    if answer.status_code != 200:
        raise c.ToolError(f"Mixkit answered {answer.status_code} for {url}. Nothing was downloaded.")
    return answer.text


def _size(url: str) -> int | None:
    import requests

    answer = requests.head(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, allow_redirects=True)
    if answer.status_code != 200 or not answer.headers.get("Content-Type", "").startswith("audio/"):
        raise c.ToolError(f"Mixkit has no track file at {url} (it answered {answer.status_code}). Nothing was "
                          "downloaded.")
    size = answer.headers.get("Content-Length")
    return int(size) if size and size.isdigit() else None


def _download(url: str, dest: Path) -> None:
    import requests

    with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, stream=True) as answer:
        if answer.status_code != 200 or not answer.headers.get("Content-Type", "").startswith("audio/"):
            raise c.ToolError(f"Mixkit answered {answer.status_code} for {url}. Nothing was kept.")
        got = 0
        with dest.open("wb") as fh:
            for chunk in answer.iter_content(1 << 16):
                got += len(chunk)
                if got > MAX_MB * 1_000_000:
                    raise c.ToolError(f"The track is over {MAX_MB} MB, which no Mixkit track is. Nothing was kept.")
                fh.write(chunk)


def _text(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def cards(page: str) -> list[dict]:
    """The music cards of a Mixkit page: [{id, title, author, length, tags, moods, preview}]."""
    out = []
    for chunk in re.split(r'<div class="item-grid-card[ "]', page)[1:]:
        found = re.search(r'data-audio-player-item-id-value="(\d+)"', chunk)
        title = re.search(r'class="item-grid-card__title"[^>]*>(.*?)</h2>', chunk, re.S)
        if not (found and title):
            continue
        author = re.search(r'class="item-grid-music-preview__author"[^>]*>(.*?)</p>', chunk, re.S)
        links = re.findall(r'<a class="meta-links__link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', chunk, re.S)
        length = re.search(r">\s*(\d{1,2}:\d{2})\s*<", chunk)
        preview = re.search(r'data-audio-player-preview-url-value="([^"]+)"', chunk)
        tid = found.group(1)
        out.append({"id": tid, "title": _text(title.group(1)),
                    "author": re.sub(r"^by\s+", "", _text(author.group(1))) if author else "",
                    "length": length.group(1) if length else "", "tags": [_text(t) for _, t in links],
                    "moods": [_text(t) for href, t in links if "/mood/" in href],
                    "preview": preview.group(1) if preview else FILE.format(id=tid)})
    return out


def _mixkit_page(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.netloc.lower() not in ("mixkit.co", "www.mixkit.co"):
        raise c.ToolError(f"--page must be a Mixkit page (https://mixkit.co/...), not {url}. Nothing was read.")
    return url


def _words_slug(words: str) -> str:
    plain = unicodedata.normalize("NFKD", words).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", plain).strip("-")
    if not slug:
        raise c.ToolError(f"--search {words!r} needs words in Latin letters (Mixkit searches in English).")
    return slug


def _channel(run) -> str | None:
    import json

    found = (state.load(run).organic or {}).get("channel")
    try:
        said = json.loads((run.path / "00_raw" / "proposal.json").read_text(encoding="utf-8-sig"))
        found = said.get("channel") or found
    except (OSError, ValueError, AttributeError):
        pass
    if not found:
        channels = config.load(run).get("channels") if (run.path / config.FILE).is_file() else None
        found = channels[0] if isinstance(channels, list) and channels else None
    return found if isinstance(found, str) and found.strip() else None


def channel_folder(run) -> Path:
    """The channel's music folder (the module docstring)."""
    workspace = trend_spool.workspace_of(run)
    name = _channel(run)
    if name is None:
        raise c.ToolError("This run names no channel (config.yaml channels), so there is no music folder to use.")
    try:
        profile = brand.latest(workspace, name, kind="channel") or {}
    except ValueError as exc:
        raise c.ToolError(str(exc)) from None
    folder = (profile.get("music") or {}).get("folder") if isinstance(profile.get("music"), dict) else None
    if isinstance(folder, str) and folder.strip():
        path = Path(folder).expanduser()
        return path if path.is_absolute() else workspace / path
    return workspace / "library" / "channels" / brand.channel_key(name) / "music"


def _shown(path: Path, run) -> str:
    """A path as the user knows it: inside the workspace relative to it, else as it is."""
    try:
        return path.resolve().relative_to(trend_spool.workspace_of(run).resolve()).as_posix()
    except ValueError:
        return str(path)


def _track(card: dict, size: int | None) -> dict:
    return {"id": card["id"], "title": card["title"], "author": card["author"], "length": card["length"],
            "moods": card["moods"], "tags": card["tags"],
            "size_mb": round(size / 1_000_000, 1) if size is not None else None,
            "licence": LICENCE, "licence_url": LICENCE_URL, "source": FILE.format(id=card["id"])}


def _file_name(card: dict) -> str:
    plain = unicodedata.normalize("NFKD", card["title"]).encode("ascii", "ignore").decode("ascii").lower()
    return f"mixkit-{re.sub(r'[^a-z0-9]+', '-', plain).strip('-') or 'track'}-{card['id']}.mp3"


def _tag(src: Path, dest: Path, track: dict) -> None:
    meta = {"title": track["title"], "artist": track["author"], "genre": ", ".join(track["moods"] or track["tags"]),
            "licence": track["licence"], "copyright": f"{LICENCE} ({LICENCE_URL})", "source": track["source"]}
    argv = [c.ffmpeg_bin(), "-nostdin", "-v", "error", "-i", c.media(src), "-map", "0:a", "-c", "copy",
            "-id3v2_version", "3"]
    for key, value in meta.items():
        argv += ["-metadata", f"{key}={value}"]
    subprocess.run([*argv, "-f", "mp3", c.media(dest)], capture_output=True, check=True)


def search(run, words: str) -> tuple[dict, str]:
    page = SEARCH.format(words=_words_slug(words))
    found = [_track(card, None) for card in cards(_get(page))]
    lines = [f"{t['id']}: {t['title']} by {t['author']}, {t['length']} ({', '.join(t['tags'])}) {t['source']}"
             for t in found]
    return ({"page": page, "tracks": found},
            f"{len(found)} Mixkit track(s) for {words!r} on {page}:\n" + "\n".join(lines) if found
            else f"Mixkit lists no track for {words!r} ({page}): try other words in English.")


def fetch(run, tid: str, page: str | None, yes: bool) -> tuple[dict, str, int]:
    if not re.fullmatch(r"\d{1,7}", tid):
        raise c.ToolError(f"--mixkit takes the track's number (e.g. 580), not {tid!r}.")
    page = _mixkit_page(page) if page else FRONT
    card = next((x for x in cards(_get(page)) if x["id"] == tid), None)
    if card is None:
        raise c.ToolStop(f"Track {tid} is not on {page}: give --page, the Mixkit page that lists it (the search page "
                         "--search printed, or a mood page). Nothing was downloaded.")
    track = _track(card, _size(FILE.format(id=tid)))
    folder = channel_folder(run)
    dest = folder / _file_name(card)
    said = (f"{track['title']} by {track['author']}, {track['length']}, {track['size_mb']} MB, {LICENCE} "
            f"({LICENCE_URL}: free for commercial use, no credit needed)")
    if not yes:
        return ({"track": track, "folder": _shown(folder, run)},
                f"{said}. Nothing was downloaded. Ask the user; after their yes run again with --yes: it goes into "
                f"{_shown(folder, run)} and the folder is indexed.", 2)
    if not dest.is_file():
        folder.mkdir(parents=True, exist_ok=True)
        part = folder / f".{dest.name}.part"
        try:
            _download(track["source"], part)
            _tag(part, dest, track)
        except BaseException:
            dest.unlink(missing_ok=True)
            raise
        finally:
            part.unlink(missing_ok=True)
    out, rows, _ = music_index.index(run, folder)
    payload = {"track": track, "file": _shown(dest, run), "folder": _shown(folder, run), "index": c.rel(run, out),
               "outputs": [c.rel(run, out)]}
    return payload, (f"Fetched {said} into {_shown(dest, run)} and indexed the folder ({len(rows)} tracks) into "
                     f"{c.rel(run, out)}. To offer it: tm tool music_fetch --run <run> --copy {dest.name}."), 0


def copy(run, track: str) -> str:
    """One track of the channel's music folder copied into the run; its run-relative path."""
    folder = channel_folder(run)
    given = Path(track).expanduser()
    src = given if given.is_absolute() else (folder / given if (folder / given).is_file()
                                              else trend_spool.workspace_of(run) / given)
    if not src.is_file():
        raise c.ToolError(f"There is no track {track} in the channel's music folder {_shown(folder, run)}: give its "
                          "name as the index lists it, or fetch one first (tm tool music_fetch --mixkit <id>).")
    dest = run.path / RUN_MUSIC / src.name
    if dest.is_file() and dest.read_bytes() != src.read_bytes():
        dest = run.unique_path(dest)
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(f".{dest.name}.part")
        shutil.copyfile(src, part)
        c.replace(part, dest)
        c.record(run, dest, "tm tool music_fetch --copy", src.name, params={"from": _shown(src, run)}, cost="free")
    return c.rel(run, dest)


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("music_fetch", "Music for the edit: a Mixkit track found, fetched after the user's yes, indexed; "
                 "the offered tracks copied into the run.")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--search", help="words to search Mixkit's music for, in English")
    mode.add_argument("--mixkit", help="a Mixkit track's number: shown, and with --yes fetched")
    mode.add_argument("--copy", action="append", help="a track of the channel's music folder to copy into the run "
                      "(again for each track offered)")
    p.add_argument("--page", help="the Mixkit page that lists the track (default: Mixkit's music front page)")
    p.add_argument("--yes", action="store_true", help="the user said yes: download the track")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    if a.search:
        payload, text = search(run, a.search)
    elif a.copy:
        done = [copy(run, track) for track in a.copy]
        payload, text = ({"outputs": done}, f"Copied into the run: {', '.join(done)}. The page offers them; the edit's "
                                            "music.src is the picked one.")
    else:
        payload, text, code = fetch(run, a.mixkit, a.page, a.yes)
        if code == 2:
            import json

            print(json.dumps({"status": "stop", **payload, "message": text}, ensure_ascii=False) if a.json else text)
            return 2
    return c.finish(a, {"tool": "music_fetch", **payload}, text)


if __name__ == "__main__":
    raise SystemExit(main())
