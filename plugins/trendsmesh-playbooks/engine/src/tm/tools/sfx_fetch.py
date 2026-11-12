"""Sound effects for the edit (Create an ad's G2, issue 96): a small set from Mixkit, fetched like organic video's
music (issue 89), with the licence shown.

    tm tool sfx_fetch --run RUN --list [--json]
    tm tool sfx_fetch --run RUN (--effect NAME [--effect NAME ...] | --all) [--yes] [--json]
    tm tool sfx_fetch --run RUN --search "<words>" [--json]
    tm tool sfx_fetch --run RUN --mixkit ID --page URL [--yes] [--json]

- `--list`: the set (`data/sfx.yaml`: whoosh, sweep, click, pop, notification), each with its title, Mixkit number,
  licence and whether this workspace has it already. Free, nothing is read from the network.
- `--effect` / `--all`: the effects copied into the run, `02_research/sfx/<file>` (the edit's sound cues name them
  there), each with its manifest row (the licence and the address it came from). An effect not yet in the workspace's
  sound-effects folder (`library/sfx/`) is checked on the Mixkit page that lists it (its title and length) and its
  file's size read; then it stops (exit 2) so the user is asked, nothing fetched. With `--yes`, after the user's yes,
  each file (Mixkit's fixed address, `assets.mixkit.co/active_storage/sfx/<id>/<id>.wav` or `.mp3`, as the effect's
  download page names it; no account) is fetched into `library/sfx/mixkit-<title>-<id>.<ext>`, beside it
  `<file>.json` with its title, number, licence and source, then
  copied into the run. An effect already there is never fetched again.
- `--search`: the effects Mixkit lists for the words (`https://mixkit.co/free-sound-effects/<words>/`): number,
  title, length. Free.
- `--mixkit ID --page URL`: one effect outside the set, by its number and the Mixkit page that lists it, fetched and
  copied the same way.

The Mixkit Sound Effects Free License (`data/sfx.yaml`, read on its `checked` date) allows the effects in commercial
projects and online marketing ads, with no credit, but not handed on by themselves: so the plugin ships none, and each
user fetches their own. An effect Mixkit does not have is made by ElevenLabs Sound Effects (`tm tool elevenlabs
sound-effect`), for credits, after the user's yes. Only mixkit.co is read and only its sound files are fetched.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from tm import __version__, paths, trend_spool
from tm.tools import _common as c

SET_FILE = "sfx.yaml"
DOWNLOAD = "https://mixkit.co/free-sound-effects/download/{id}/"     # names the effect's file, a .wav or an .mp3
FILE = re.compile(r"https://assets\.mixkit\.co/active_storage/sfx/(\d+)/\1\.(wav|mp3)")
SEARCH = "https://mixkit.co/free-sound-effects/{words}/"
RUN_SFX = "02_research/sfx"
LIBRARY = ("library", "sfx")
MAX_MB = 20
USER_AGENT = f"trendsmesh-playbooks/{__version__} (sound effects for an edit; after the user's yes)"
TIMEOUT = 60


def the_set() -> dict:
    """data/sfx.yaml: {licence, licence_url, checked, effects: {name: {id, title, page}}}."""
    return yaml.safe_load((paths.bundled_data() / SET_FILE).read_text(encoding="utf-8"))


def _get(url: str) -> str:
    import requests

    answer = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    if answer.status_code != 200:
        raise c.ToolError(f"Mixkit answered {answer.status_code} for {url}. Nothing was fetched.")
    return answer.text


def _size(url: str) -> int | None:
    import requests

    answer = requests.head(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, allow_redirects=True)
    if answer.status_code != 200 or not answer.headers.get("Content-Type", "").startswith("audio/"):
        raise c.ToolError(f"Mixkit has no sound file at {url} (it answered {answer.status_code}). Nothing was "
                          "fetched.")
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
                    raise c.ToolError(f"The effect is over {MAX_MB} MB, which no Mixkit effect is. Nothing was kept.")
                fh.write(chunk)


def _text(fragment: str) -> str:
    import html

    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def cards(page: str) -> list[dict]:
    """The sound-effect cards of a Mixkit page: [{id, title, length}]."""
    out = []
    for chunk in re.split(r'<div class="item-grid-card[ "]', page)[1:]:
        found = re.search(r'data-audio-player-item-id-value="(\d+)"', chunk)
        title = re.search(r'class="item-grid-card__title"[^>]*>(.*?)</h2>', chunk, re.S)
        if not (found and title):
            continue
        length = re.search(r'data-test-id="duration"[^>]*>\s*(\d{1,2}:\d{2})', chunk)
        out.append({"id": found.group(1), "title": _text(title.group(1)), "length": length.group(1) if length else ""})
    return out


def _page(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.netloc.lower() not in ("mixkit.co", "www.mixkit.co"):
        raise c.ToolError(f"--page must be a Mixkit page (https://mixkit.co/...), not {url}. Nothing was read.")
    return url


def _slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def library(run) -> Path:
    return trend_spool.workspace_of(run).joinpath(*LIBRARY)


def _file_name(title: str, sid: str, ext: str) -> str:
    return f"mixkit-{_slug(title) or 'effect'}-{sid}.{ext}"


def _in_library(run, sid: str) -> Path | None:
    found = sorted(p for ext in ("wav", "mp3") for p in library(run).glob(f"mixkit-*-{sid}.{ext}"))
    return found[0] if found else None


def file_url(sid: str) -> tuple[str, str]:
    """(the effect's file address, its extension), as its Mixkit download page names it."""
    found = next((m for m in FILE.finditer(_get(DOWNLOAD.format(id=sid))) if m.group(1) == sid), None)
    if found is None:
        raise c.ToolStop(f"Mixkit's download page for effect {sid} names no sound file. Nothing was fetched. Pick "
                         "another effect (--search <words>).")
    return found.group(0), found.group(2)


def _shown(run, path: Path) -> str:
    try:
        return path.resolve().relative_to(trend_spool.workspace_of(run).resolve()).as_posix()
    except ValueError:
        return str(path)


def _wanted(a, known: dict) -> list[tuple[str, dict]]:
    """[(name, {id, title, page})] for --effect / --all / --mixkit."""
    if a.mixkit:
        if not re.fullmatch(r"\d{1,7}", a.mixkit):
            raise c.ToolError(f"--mixkit takes the effect's number (e.g. 1490), not {a.mixkit!r}.")
        if not a.page:
            raise c.ToolError("--mixkit needs --page, the Mixkit page that lists the effect (as --search printed "
                              "it).")
        return [(f"mixkit-{a.mixkit}", {"id": int(a.mixkit), "title": None, "page": _page(a.page)})]
    names = list(known) if a.all else a.effect
    unknown = [n for n in names if n not in known]
    if unknown:
        raise c.ToolError(f"{', '.join(unknown)} is not in the set ({', '.join(known)}). For another effect: "
                          "--search <words>, then --mixkit <number> --page <its page>.")
    return [(n, known[n]) for n in names]


def _checked(name: str, effect: dict) -> dict:
    """The effect as its Mixkit page lists it now, with its file's address and size."""
    sid = str(effect["id"])
    card = next((x for x in cards(_get(effect["page"])) if x["id"] == sid), None)
    if card is None:
        raise c.ToolStop(f"Mixkit's page {effect['page']} no longer lists effect {sid} ({name}). Nothing was fetched. "
                         "Search for another (--search <words>) and use --mixkit <number> --page <its page>.")
    url, ext = file_url(sid)
    size = _size(url)
    return {"name": name, "id": sid, "title": card["title"], "length": card["length"], "page": effect["page"],
            "source": url, "ext": ext, "size_mb": round(size / 1_000_000, 2) if size is not None else None}


def _fetch(run, effect: dict, licence: dict) -> Path:
    folder = library(run)
    dest = folder / _file_name(effect["title"], effect["id"], effect["ext"])
    if dest.is_file():
        return dest
    folder.mkdir(parents=True, exist_ok=True)
    part = folder / f".{dest.name}.part"
    try:
        _download(effect["source"], part)
        argv = [c.ffmpeg_bin(), "-nostdin", "-v", "error", "-y", "-i", c.media(part), "-c", "copy"]
        for key, value in (("title", effect["title"]), ("artist", "Mixkit"),
                           ("copyright", f"{licence['licence']} ({licence['licence_url']})"),
                           ("comment", effect["source"])):
            argv += ["-metadata", f"{key}={value}"]
        subprocess.run([*argv, "-f", effect["ext"], c.media(dest)], capture_output=True, check=True)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    finally:
        part.unlink(missing_ok=True)
    side = {k: effect[k] for k in ("id", "title", "length", "page", "source")}
    c.write_json(dest.with_name(dest.name + ".json"), {**side, "licence": licence["licence"],
                                                        "licence_url": licence["licence_url"],
                                                        "fetched": date.today().isoformat()}, newline="\n")
    return dest


def _copy(run, src: Path, licence: dict) -> str:
    try:
        side = json.loads(src.with_name(src.name + ".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        side = {}
    dest = run.path / RUN_SFX / src.name
    if dest.is_file() and dest.read_bytes() != src.read_bytes():
        dest = run.unique_path(dest)
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(f".{dest.name}.part")
        shutil.copyfile(src, part)
        c.replace(part, dest)
        c.record(run, dest, "tm tool sfx_fetch", None, params={
            "title": side.get("title"), "licence": side.get("licence") or licence["licence"],
            "licence_url": side.get("licence_url") or licence["licence_url"], "source": side.get("source"),
            "from": _shown(run, src)}, cost="free")
    return c.rel(run, dest)


def effects(run, a) -> tuple[dict, str, int]:
    data = the_set()
    licence = {"licence": data["licence"], "licence_url": data["licence_url"]}
    wanted = _wanted(a, data["effects"])
    have = {name: _in_library(run, str(e["id"])) for name, e in wanted}
    missing = [(n, e) for n, e in wanted if have[n] is None]
    checked = [_checked(n, e) for n, e in missing]
    said_licence = f"{licence['licence']} ({licence['licence_url']}: free in commercial projects and ads, no credit)"
    if checked and not a.yes:
        lines = [f"{x['name']}: {x['title']}, {x['length']}, {x['size_mb']} MB ({x['source']})" for x in checked]
        return ({"fetch": checked, **licence, "folder": _shown(run, library(run))},
                f"To fetch from Mixkit, under the {said_licence}:\n" + "\n".join(lines) + "\nNothing was fetched. Ask "
                f"the user; after their yes run again with --yes: they go into {_shown(run, library(run))} and are "
                "copied into the run.", 2)
    for x in checked:
        have[x["name"]] = _fetch(run, x, licence)
    copied = {name: _copy(run, have[name], licence) for name, _ in wanted}
    return ({"outputs": list(copied.values()), "effects": copied, "fetched": [x["name"] for x in checked],
             **licence},
            f"In the run: {', '.join(f'{n} {p}' for n, p in copied.items())}. Licence: {said_licence}.", 0)


def listing(run) -> tuple[dict, str]:
    data = the_set()
    rows = [{"name": n, "id": e["id"], "title": e["title"], "page": e["page"],
             "here": _in_library(run, str(e["id"])) is not None} for n, e in data["effects"].items()]
    return ({"effects": rows, "licence": data["licence"], "licence_url": data["licence_url"],
             "checked": str(data["checked"])},
            "\n".join(f"{r['name']}: {r['title']} (Mixkit {r['id']}){' - in this workspace' if r['here'] else ''}"
                      for r in rows) + f"\nLicence: {data['licence']} ({data['licence_url']}).")


def search(words: str) -> tuple[dict, str]:
    slug = _slug(words)
    if not slug:
        raise c.ToolError(f"--search {words!r} needs words in Latin letters (Mixkit searches in English).")
    page = SEARCH.format(words=slug)
    found = cards(_get(page))
    return ({"page": page, "effects": found},
            f"{len(found)} Mixkit effect(s) for {words!r} on {page}:\n" +
            "\n".join(f"{x['id']}: {x['title']}, {x['length']}" for x in found) if found else
            f"Mixkit lists no effect for {words!r} ({page}): try other words in English.")


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("sfx_fetch", "Sound effects for the edit: the plugin's small Mixkit set, fetched after the user's "
                 "yes, with the licence shown, and copied into the run.")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list", action="store_true", help="the set, with the licence")
    mode.add_argument("--effect", action="append", help="an effect of the set (again for each)")
    mode.add_argument("--all", action="store_true", help="every effect of the set")
    mode.add_argument("--search", help="words to search Mixkit's sound effects for, in English")
    mode.add_argument("--mixkit", help="an effect outside the set: its Mixkit number (with --page)")
    p.add_argument("--page", help="the Mixkit page that lists the --mixkit effect")
    p.add_argument("--yes", action="store_true", help="the user said yes: fetch the effects")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    if a.list:
        payload, text = listing(run)
    elif a.search:
        payload, text = search(a.search)
    else:
        payload, text, code = effects(run, a)
        if code == 2:
            print(json.dumps({"status": "stop", "tool": "sfx_fetch", **payload, "message": text},
                             ensure_ascii=False) if a.json else text)
            return 2
    return c.finish(a, {"tool": "sfx_fetch", **payload}, text)


if __name__ == "__main__":
    raise SystemExit(main())
