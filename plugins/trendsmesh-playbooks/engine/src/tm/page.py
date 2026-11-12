"""Pages: built locally in a versioned folder, published as an artifact when the tool is there.

    tm page files --run RUN --page PAGE [--json]          the latest folder's files, for the Artifact tool
    tm page published --run RUN --page PAGE (--url U | --slug S) --version V [--json]
    tm page link --run RUN --page PAGE [--json]           where the page was last published
    tm page await --run RUN --page PAGE --version V [--clear] [--json]   people decide on the page now
    tm page fetch --run RUN --url URL --name SHORT [--kind landing|voice] [--found-in F] [--json]
                                                          a web page's literal text in 00_raw (tm.page_text)
    tm page build --run RUN [--ask FILE] [--local] [--json]   the run page from the run state (tm.run_page)
    tm page decision --run RUN CHECKIN [--record] [--json]    the choice saved on it (tm.run_page)

A page lives in `04_final/<page>_vNN/` (`index.html` and `assets/`), never overwritten: each build
is a new folder; media file names go through `asset_name` (Windows-safe). Where it was published
(decisions §5) is kept in `run.json` under `pages[<page>] = {slug, version, url, folder, published_at}`, and a later run (`tm run new --after`)
finds it along `previous_run`, so a weekly page republishes under the same link. Shared by PB02,
PB03 and PB04: keep the interfaces exact.

The publishing tool is the Claude desktop app's built-in `Artifact` tool, which names a page by its
claude.ai URL (the slug is the URL's id, `artifact_id`), and `ArtifactData`, which reads its db. Some
hosts still have the older artifacts MCP tools (`publish_files` with a slug, `db_list`): their
records and saved answers are read the same way.

Decisions taken on a page (plan Decision 11, lifted from PB02's brief page). The page saves them in
its artifact's db, one collection; the collector saves each `ArtifactData` list/query (or older
`db_list`/`db_query`) answer in `03_wip/decisions/` (`mcp_saves`).
- `await_(run, page, version)` marks that people decide on the published page
  (`pages[page]["awaiting"]`); `new_folder` refuses to build that page (`Deciding`) until it is
  cleared (`clear_await`, done when the decisions are read).
- `saved_answer` finds the newest saved answer on the page's slug and collection; `whole_answer`
  refuses one that may hold part of the decisions (a cursor, a filter, a sort, another artifact or
  collection) or was saved before the page was published or awaited; `db_docs` reads its documents,
  refusing an error answer, one page of several, a document without data, a line that does not
  parse or a count that differs.
- `mark_carried` marks a row equal to the one an earlier page build's decisions file recorded for
  it (`earlier_decisions`): the page pre-fills the earlier choice, so it may not be a new look.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

import requests

from tm import cli, manifest, mcp_saves, page_text, state, trends
from tm.runfolder import RunFolder
from tm.stops import AGAIN, Stop

FINAL = "04_final"
SOURCE = "claude.ai artifacts publish"
# The Artifact tool's limits for one publish (255 files, 15 MB a binary file, 64 MB in all), in
# decimal MB to stay under them; the older publish_files took a little more.
MAX_FILES = 255
MAX_FILE_BYTES = 15 * 10**6
MAX_TOTAL_BYTES = 64 * 10**6
_ARTIFACT_URL = re.compile(r"^https://claude\.ai/(?:code/)?artifact/([A-Za-z0-9_-]+)/?(?:[?#].*)?$")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
_UNSAFE = re.compile(r'[<>:"|?*/\\\x00-\x1f]')


def asset_name(text: str) -> str:
    """A file name every OS takes: `<>:"|?*`, path separators and control characters become `_`
    (`tiktok:123.jpg` -> `tiktok_123.jpg`)."""
    return _UNSAFE.sub("_", str(text))


def _check_name(page: str) -> str:
    if not isinstance(page, str) or not _NAME.fullmatch(page):
        raise ValueError(f"{page!r} is not a page name: use letters, digits, '-' and '_' (e.g. report).")
    return page


def _versions(run: RunFolder, page: str) -> list[tuple[int, Path]]:
    """Every entry `04_final/<page>_vNN` with its NN, folder or not."""
    folder = run.path / FINAL
    pattern = re.compile(rf"^{re.escape(_check_name(page))}_v(\d+)$")
    if not folder.is_dir():
        return []
    return [(int(m.group(1)), e) for e in folder.iterdir() if (m := pattern.match(e.name))]


DECIDING = ("People are deciding on the {page} page now. A new version would change it under them. Read their "
            "decisions first{read}, then build again. If the team decided another way (in chat, say), record it "
            "and stop waiting with `tm page await --run <run> --page {page} --clear`. The run continues from the "
            "same place.")


class Deciding(Stop):
    """A page is not built again while people decide on it (`await_`): exit 2, as any Stop."""

    def __init__(self, page: str, words: str | None = None, *, read: str | None = None):
        self.page = page
        super().__init__(words or DECIDING.format(page=page, read=f" ({read})" if read else ""))


def new_folder(run: RunFolder, page: str) -> Path:
    """A new `04_final/<page>_vNN/` with `assets/`, NN = the highest existing + 1 (gaps are never
    filled, an earlier build is never written over). `Deciding` while people decide on the page."""
    if awaiting(run, page) is not None:
        raise Deciding(page)
    n = max((v for v, _ in _versions(run, page)), default=0)
    while True:
        n += 1
        folder = run.path / FINAL / f"{page}_v{n:02d}"
        try:
            folder.mkdir(parents=True)
        except FileExistsError:            # made since we looked: take the next one
            continue
        (folder / "assets").mkdir()
        return folder


def latest_folder(run: RunFolder, page: str) -> Path | None:
    """The highest `04_final/<page>_vNN/` folder, or None."""
    found = [(v, len(e.name), e) for v, e in _versions(run, page) if e.is_dir()]
    return max(found)[2] if found else None


def fetch_image(url: str | None, dest: Path, *, timeout: float = 30) -> bool:
    """Download an image to `dest`, its file name passed through `asset_name` (build `dest` with
    `asset_name` to know where it lands); True once it is there. It never raises: a URL that is not
    http(s), an answer that is not `image/*` (or over 20 MiB), a download that takes longer than
    `timeout` in all, a network or disk error give False and leave no file. An existing file is
    reused without a request."""
    dest = Path(dest)
    dest = dest.with_name(asset_name(dest.name))
    if dest.is_file():
        return True
    if not isinstance(url, str):
        return False
    tmp = dest.with_name(f".{dest.name}.{os.getpid()}.tmp")
    try:
        parts = urlsplit(url)                  # raises ValueError on a malformed host
        if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
            return False
        deadline = time.monotonic() + timeout   # `timeout` alone bounds each read, not the whole
        answer = requests.get(url, timeout=timeout, stream=True)
        try:
            answer.raise_for_status()
            if not str(answer.headers.get("Content-Type", "")).lower().startswith("image/"):
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            size = 0
            with open(tmp, "wb") as fh:
                for chunk in answer.iter_content(chunk_size=65536):
                    size += len(chunk)
                    if size > MAX_FILE_BYTES:
                        raise ValueError(f"{url} is larger than {MAX_FILE_BYTES} bytes")
                    if time.monotonic() > deadline:
                        raise TimeoutError(f"{url} took longer than {timeout} s")
                    fh.write(chunk)
            os.replace(tmp, dest)
            return True
        finally:
            answer.close()
    except (requests.RequestException, OSError, ValueError):
        return False
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)


def _mb(size: int) -> str:
    return f"{size / 10**6:.1f} MB" if size >= 10**5 else f"{size} bytes"


def over_limits(sizes: dict[str, int]) -> str:
    """What puts a page's files (`{served path: bytes}`) over the Artifact tool's limits, in words
    that follow "it is too big to publish as one artifact:"; "" when it fits. A page builder checks
    its planned files with it before writing any."""
    big = [name for name, size in sizes.items() if size > MAX_FILE_BYTES]
    if len(sizes) > MAX_FILES:
        return f"it has {len(sizes)} files and the Artifact tool takes at most {MAX_FILES} in one publish"
    if big:
        return (f"{', '.join(big)} {'is' if len(big) == 1 else 'are'} over the Artifact tool's "
                f"{_mb(MAX_FILE_BYTES)} a file")
    if sum(sizes.values()) > MAX_TOTAL_BYTES:
        return (f"its files come to {_mb(sum(sizes.values()))} and the Artifact tool takes at most "
                f"{_mb(MAX_TOTAL_BYTES)} in all")
    return ""


# An artifact's stored file is referenced as `/_blob/<id>`. Git Bash on Windows rewrites such a path given through
# the shell into `C:/Program Files/Git/_blob/<id>`, and the open page then cannot find it (issue #19).
_BLOB_REF = re.compile(r"""([^"'()\s,\[\]=<>]*)([/\\])_blob[/\\]([A-Za-z0-9_.-]+)""")
MANGLED = ("The page refers to an artifact file by a path the shell rewrote ({refs}): every such reference must start "
           "with /_blob/. Git Bash on Windows rewrites /_blob/<id> into C:/Program Files/Git/_blob/<id>: write the JSON "
           "with the Write tool, or run the command with MSYS_NO_PATHCONV=1, then build the page again. The run "
           "continues from the same place.")


def mangled_blob_refs(text: str) -> list[str]:
    """The references to an artifact file (`_blob/<id>`) in `text` that do not start with `/_blob/`."""
    return [f"{m.group(1)}{m.group(2)}_blob{m.group(2)}{m.group(3)}" for m in _BLOB_REF.finditer(text)
            if m.group(1) or m.group(2) != "/"]


def files(folder: Path) -> list[dict]:
    """The folder's files, `{"as": <served path>, "path": <absolute>}` (as the older `publish_files`
    takes them; `artifact_args` gives the Artifact tool's), `index.html` first, then the rest by
    served path. Hidden and temporary files are left out. A page over the limits (MAX_FILES,
    MAX_FILE_BYTES each, MAX_TOTAL_BYTES in all) is refused."""
    folder = Path(folder)
    if not (folder / "index.html").is_file():
        raise ValueError(f"{folder} has no index.html, so there is no page to publish: build the page first. "
                         "The run continues from the same place.")
    out = []
    for f in folder.rglob("*"):
        rel = f.relative_to(folder)
        if f.is_file() and not any(part.startswith(".") for part in rel.parts):
            out.append({"as": rel.as_posix(), "path": str(f.resolve())})
    out.sort(key=lambda f: (f["as"] != "index.html", f["as"]))
    bad = mangled_blob_refs((folder / "index.html").read_text(encoding="utf-8", errors="replace"))
    if bad:
        raise ValueError(MANGLED.format(refs=", ".join(bad[:3])))
    over = over_limits({f["as"]: Path(f["path"]).stat().st_size for f in out})
    if over:
        raise ValueError(f"{folder.name} is too big to publish as one artifact: {over}. Make the images "
                         "smaller or fewer and build the page again, or give the local index.html. The run "
                         "continues from the same place.")
    return out


def artifact_args(listed: list[dict]) -> dict:
    """The Artifact tool's publish arguments for `files`' list: `file_path` (the local index.html)
    and `files` (every other served path -> its local file)."""
    return {"file_path": listed[0]["path"], "files": {f["as"]: f["path"] for f in listed[1:]}}


def artifact_id(url: object) -> str | None:
    """The id in a claude.ai artifact URL (`https://claude.ai/artifact/<id>`, or
    `https://claude.ai/code/artifact/<uuid>`), else None."""
    m = _ARTIFACT_URL.match(url.strip()) if isinstance(url, str) else None
    return m.group(1) if m else None


def _built(run: RunFolder, page: str) -> Path:
    folder = latest_folder(run, page)
    if folder is None:
        raise ValueError(f"This run has no {FINAL}/{page}_vNN folder yet: build the page first. "
                         "The run continues from the same place.")
    return folder


def record_published(run: RunFolder, page: str, slug: str | None, version: str, url: str | None = None) -> dict:
    """Store where the latest build of `page` was published (`state.pages[page]`) and add a manifest
    row. Returns the record. The Artifact tool's page has no slug of its own: it is the URL's id
    (`artifact_id`). A wait for decisions on the page (`awaiting`) is kept."""
    slug = slug or artifact_id(url)
    if not all(isinstance(v, str) and v.strip() for v in (slug, version)):
        raise ValueError("A published page needs the artifact's slug and version: the claude.ai URL (--url) and "
                         "the version id the Artifact tool's publish returned, or the slug and version the older "
                         "publish_files returned.")
    folder = _built(run, page).relative_to(run.path).as_posix()
    record = {"slug": slug, "version": version, "url": url or None, "folder": folder,
              "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    s = state.load(run)
    waiting = (s.pages.get(page) or {}).get("awaiting")
    s.pages[page] = record if waiting is None else {**record, "awaiting": waiting}
    state.save(run, s)
    manifest.record(run, folder, FINAL, SOURCE, params={"slug": slug, "version": version, "url": record["url"]})
    return record


def published(run: RunFolder, page: str) -> dict | None:
    """This run's publish record of `page`, else the nearest along `previous_run`, else None. A run
    in the chain that cannot be read is said (ValueError), never skipped into a new link."""
    _check_name(page)
    run = RunFolder(run.path.resolve())        # `--run .` has no parents or name until resolved
    workspace = run.path.parents[2]            # runs/<playbook>/<run>
    current, s = run, state.load(run)
    seen = {run.path.resolve()}
    while page not in s.pages:
        if not s.previous_run:
            return None
        try:
            before = RunFolder.open(workspace / s.previous_run)
            if before.path.resolve() in seen:  # a loop in the chain: nothing further back
                return None
            before_state = state.load(before)
        except (OSError, ValueError) as exc:
            raise ValueError(
                f"{current.path.name} follows {s.previous_run}, which cannot be read ({exc}), so the link its "
                f"{page} page was published to is unknown. Restore that run folder, or publish this page as a "
                "new artifact if a new link is wanted. The run continues from the same place.") from None
        seen.add(before.path.resolve())
        current, s = before, before_state
    return s.pages[page]


# --- decisions taken on a page ------------------------------------------------------------------

READ_AGAIN = ("Read the decisions again with one unfiltered ArtifactData list (the page's url, collection {collection}, "
              "query.limit 1000, and no cursor, where, order_by or as_level, nor out_dir; with the older tools, one "
              "db_list on its slug, limit 1000), so every saved decision is in one answer. When the run does not save "
              "that read by itself (a Refresh an ad run, or when a note says it was not saved), save it with tm trends "
              "ingest --run <run> --tool ArtifactData --input <a file with the call's input> --file <a file with its "
              "whole answer>. Then run this again. The run continues from the same place.")
_PARTIAL = ("cursor", "where", "orderBy", "order_by", "out_dir", "as_level")   # a db read that holds part of the decisions
_JSON_START = re.compile(r'\{\s*"')
# ArtifactData's text answer: its summary line, and the line it adds when more pages exist
_COUNT_LINE = re.compile(r'^(\d+) documents? from collection "', re.M)
_CURSOR_LINE = re.compile(r'^next_cursor: "([^"]+)"', re.M)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def awaiting(run: RunFolder, page: str) -> dict | None:
    """The wait for decisions on this run's `page` (`{version, at[, stage]}`), or None."""
    found = (state.load(run).pages.get(page) or {}).get("awaiting")
    return found if isinstance(found, dict) else None


def await_(run: RunFolder, page: str, version: str, stage: str | None = None) -> dict:
    """Mark that people decide on the published `page` (artifact version `version`) from now on. Stop
    when its publish is not recorded in this run."""
    _check_name(page)
    if not (isinstance(version, str) and version.strip()):
        raise ValueError("--version is the artifact version people decide on, the version id the last publish returned.")
    s = state.load(run)
    if not (s.pages.get(page) or {}).get("slug"):
        raise Stop(f"The page's publish is not recorded: publish it, then record it with tm page published --page "
                   f"{page}, before waiting for decisions on it. The run continues from the same place.")
    waiting = {"version": version, "at": _now()}
    if stage is not None:
        waiting = {"stage": stage, **waiting}
    s.pages[page] = {**s.pages[page], "awaiting": waiting}
    state.save(run, s)
    return waiting


def clear_await(run: RunFolder, page: str) -> None:
    """Stop waiting for decisions on `page` (nothing when it is not awaited)."""
    s = state.load(run)
    record = s.pages.get(page)
    if isinstance(record, dict) and "awaiting" in record:
        s.pages[page] = {k: v for k, v in record.items() if k != "awaiting"}
        state.save(run, s)


def _objects(text: str, read_again: str) -> Iterable[Any]:
    """Every JSON value that starts at a `{` in the text, outermost first: the documents of a db
    answer, one per line, still found when its text blocks were joined without a newline. Stop for
    a JSON object that is cut or broken (a line that does not parse)."""
    decoder, i = json.JSONDecoder(), 0
    while (i := text.find("{", i)) >= 0:
        try:
            value, end = decoder.raw_decode(text, i)
        except ValueError:
            if _JSON_START.match(text, i):
                raise Stop(f"A line of the saved answer does not parse ({text[i:i + 60]!r}…), so a decision may be "
                           f"missing. {read_again}") from None
            i += 1
            continue
        yield value
        i = end


def _text(text: str, found: dict, read_again: str, chat: str) -> None:
    """The documents in an answer's text, with ArtifactData's summary count and next page."""
    found["counts"] += [int(n) for n in _COUNT_LINE.findall(text)]
    found["pages"] += _CURSOR_LINE.findall(text)
    for value in _objects(text, read_again):
        _walk(value, found, read_again, chat)


def _walk(value: Any, found: dict, read_again: str, chat: str) -> None:
    """Collect the documents (objects with an `id`), the summaries' counts and any next page; a text
    in the answer (a built-in tool's answer inside an object) is read as a text answer."""
    if isinstance(value, dict):
        if "id" in value:
            if value.get("tooLarge") or not isinstance(value.get("data"), dict) or not isinstance(value["id"], str):
                raise Stop(f"The saved answer holds a decision without its data (document {value.get('id')!r}"
                           f"{', tooLarge' if value.get('tooLarge') else ''}), so it cannot be read. {read_again} "
                           f"{chat}")
            found["docs"].append((value["id"], value["data"]))
            return
        if value.get("nextCursor"):
            found["pages"].append(value["nextCursor"])
        if isinstance(value.get("count"), int) and not isinstance(value["count"], bool):
            found["counts"].append(value["count"])
        for inner in value.values():
            _walk(inner, found, read_again, chat)
    elif isinstance(value, list):
        for inner in value:
            _walk(inner, found, read_again, chat)
    elif isinstance(value, str) and "{" in value:
        _text(value, found, read_again, chat)


def db_docs(saved: dict | str, *, collection: str = "decisions", chat: str | None = None) -> list[tuple[str, dict]]:
    """The documents `(id, data)` of a saved ArtifactData list/query (or `db_list`/`db_query`) answer
    (an envelope or its answer: every JSON object with an `id` in its text, or in its JSON; a str is
    the answer's text), in the answer's order. A read that may hold part of the decisions is a Stop:
    an error answer, one page of several (nextCursor, or ArtifactData's `next_cursor:` line), a
    document without data (tooLarge; `chat` says what to do if it stays so), a line that does not
    parse, a summary count that differs from the documents read."""
    read_again = READ_AGAIN.format(collection=collection)
    chat = chat or "If it says tooLarge again, ask for that decision in chat."
    answer = {"raw": saved} if isinstance(saved, str) else trends.unwrap(saved)
    if isinstance(answer, dict) and "error" in answer:
        raise Stop(f"The saved answer is an error ({json.dumps(answer['error'], ensure_ascii=False)[:200]}), not the "
                   f"page's decisions. {read_again}")
    found: dict = {"docs": [], "pages": [], "counts": []}
    if isinstance(answer, dict) and isinstance(answer.get("raw"), str):
        _text(answer["raw"], found, read_again, chat)
    else:
        _walk(answer, found, read_again, chat)
    if found["pages"]:
        raise Stop(f"The saved answer is one page of several (its nextCursor is set), so some decisions are not in "
                   f"it. {read_again}")
    if found["counts"] and sum(found["counts"]) != len(found["docs"]):
        raise Stop(f"The saved answer says it holds {sum(found['counts'])} decisions, and {len(found['docs'])} were "
                   f"read from it, so some are missing. {read_again}")
    return found["docs"]


def _when(value: object) -> datetime | None:
    """An ISO time as an aware datetime (a naive one taken as UTC), else None."""
    try:
        at = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
    return at.replace(tzinfo=timezone.utc) if at is not None and at.tzinfo is None else at


def _slug(run: RunFolder, page: str) -> str | None:
    return (state.load(run).pages.get(page) or {}).get("slug") or None


def _artifact_of(given: dict) -> str | None:
    """The artifact a saved read was on: the older tools' `slug`, or the id in ArtifactData's `url`."""
    return given.get("slug") or artifact_id(given.get("url"))


def _partial(given: dict) -> list[str]:
    """What in a saved read's input may leave decisions out: a cursor, a filter, a sort (at the top,
    as the older tools take them, or in ArtifactData's `query`), or out_dir (the documents went to
    files, not into the answer)."""
    query = given.get("query") if isinstance(given.get("query"), dict) else {}
    return [k for k in _PARTIAL if given.get(k) not in (None, "", [], {}) or query.get(k) not in (None, "", [], {})]


def saved_answer(run: RunFolder, page: str, collection: str) -> Path | None:
    """The newest saved db_list/db_query answer on this run's `page` (its slug) and `collection`, by
    its `_at`; None when there is none (or the page's publish is not recorded). A read made as a viewer
    (`as_level`) is never one: it shows what a viewer sees, not the decisions. A saved answer that
    cannot be read and is newer than it (by the file's time) is a Stop: it may be this page's newest
    read, and an older one is never read in its place."""
    slug = _slug(run, page)
    folder = run.path / mcp_saves.DECISIONS
    found, damaged = [], []
    for stem in ("db_list", "db_query"):
        name = re.compile(rf"^{stem}_v(\d+)\.json$")
        for f in folder.glob(f"{stem}_v*.json") if folder.is_dir() else ():
            m = name.match(f.name)
            if not m:
                continue
            try:
                data = trends.read(f)
            except ValueError:
                damaged.append(f)
                continue
            given = data.get("_input") if isinstance(data, dict) else None
            if isinstance(given, dict) and mcp_saves.viewer_check(given):
                continue                              # a viewer's check (as_level, saved by 0.11.0), never the decisions
            if (slug is not None and isinstance(given, dict) and _artifact_of(given) == slug
                    and str(given.get("collection", "")).strip("/") == collection):
                at = _when(data.get("_at"))
                if at is None:
                    damaged.append(f)
                else:
                    found.append((at, int(m.group(1)), stem, f))
    newest = max(found)[3] if found else None
    late = [f.name for f in damaged if newest is None or f.stat().st_mtime > newest.stat().st_mtime]
    if late:
        raise Stop(f"{', '.join(sorted(late))} in {mcp_saves.DECISIONS} cannot be read (not JSON, or no time it was "
                   f"saved), and it may be this page's newest read of the decisions. "
                   f"{READ_AGAIN.format(collection=collection)}")
    return newest


def whole_answer(run: RunFolder, page: str, source: Path, collection: str) -> dict:
    """The saved db answer `source` when it holds this page's whole `collection`, read after the page
    was published and after people were asked to decide (`await_`); else a Stop. The page is this
    run's `page` (its slug)."""
    read_again = READ_AGAIN.format(collection=collection)
    slug = _slug(run, page)
    try:
        saved = trends.read(source)
    except ValueError as exc:
        raise Stop(f"{exc} {read_again}") from None
    given = saved.get("_input") if isinstance(saved, dict) and "_tool" in saved else None
    if not isinstance(given, dict):
        raise Stop(f"{source.name} is not an answer the collector saved (no _tool and _input), so it cannot be tied "
                   f"to this page. {read_again}")
    if _artifact_of(given) != slug:
        raise Stop(f"{source.name} is an answer on the artifact {_artifact_of(given)!r}, not this page "
                   f"({slug}). Read this page's decisions with an ArtifactData list on its url (or db_list on its "
                   "slug), then run this again. The run continues from the same place.")
    if str(given.get("collection", "")).strip("/") != collection:
        raise Stop(f"{source.name} reads the collection {given.get('collection')!r}, not {collection}. {read_again}")
    partial = _partial(given)
    if partial:
        raise Stop(f"{source.name} was read with {', '.join(partial)}, so it may hold only part of the decisions. "
                   f"{read_again}")
    record = state.load(run).pages.get(page) or {}
    bounds = [("this page was published", _when(record.get("published_at"))),
              ("people were asked to decide on it (tm page await)", _when((awaiting(run, page) or {}).get("at")))]
    bounds = [(why, at) for why, at in bounds if at is not None]
    at = _when(saved.get("_at"))
    if at is None:
        raise Stop(f"{source.name} has no time it was saved (_at), so it is unknown which page its decisions were "
                   f"taken on. {read_again}")
    late = max(bounds, key=lambda b: b[1]) if bounds else None
    if late is not None and at < late[1]:
        raise Stop(f"{source.name} was saved at {saved['_at']}, before {late[0]} ({late[1].isoformat()}), so it "
                   f"holds the decisions on an earlier page. {read_again}")
    return saved


def _plain_row(row: object) -> object:
    return {k: v for k, v in row.items() if k != "carried"} if isinstance(row, dict) else row


def mark_carried(rows: dict, earlier: dict) -> list:
    """Mark each row (`{key: dict}`) equal to the earlier decisions file's row for that key (the
    `carried` flag aside) as `carried: true`, in place: the page pre-fills the earlier choice and the
    db keeps it across versions, so it may not be a new look. Returns the carried keys, in order."""
    carried = []
    for key, row in rows.items():
        if key in earlier and isinstance(earlier[key], dict) and _plain_row(row) == _plain_row(earlier[key]):
            row["carried"] = True
            carried.append(key)
    return carried


def earlier_decisions(run: RunFolder, files: list[Path], build: str, *, built: str, rows: str,
                      command: str, shape: type) -> Any:
    """The rows (`read[rows]`) of the latest decisions file (`files`, oldest first) read on another
    page build than `build` (`read[built]`), else None. A re-read of the same page ("Anna has voted
    now") is not a new page: it compares with the same earlier page, so a row taken on this page is
    never carried and a carried one stays carried. Stop for a file `command` did not write: one
    whose rows are not the `shape` that command keeps (PB02's a list, organic video's a dict)."""
    for path in reversed(files):
        try:
            read = trends.read(path)
            found = read.get(rows)
        except (ValueError, AttributeError):
            read, found = None, None
        if not isinstance(found, shape):
            rel = path.relative_to(run.path).as_posix()
            raise Stop(f"{rel} is not a decisions file of {command}, so the decisions carried over from it cannot be "
                       f"told apart. Restore it, or move it out of {path.parent.relative_to(run.path).as_posix()}; "
                       f"{AGAIN}.")
        if read.get(built) != build:
            return found
    return None


# --- command line -----------------------------------------------------------------------------

def _setup(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)
    fl = sub.add_parser("files", help="the latest page folder's files, for the Artifact tool")
    pu = sub.add_parser("published", help="record the artifact the latest page folder was published to")
    pu.add_argument("--slug", help="the older publish_files' slug (the Artifact tool's comes from --url)")
    pu.add_argument("--version", required=True, help="the version id the publish returned")
    pu.add_argument("--url", help="the artifact's claude.ai URL")
    li = sub.add_parser("link", help="where the page was last published, in this run or the runs it follows")
    aw = sub.add_parser("await", help="people decide on the published page now: no new version until read")
    aw.add_argument("--version", help="the artifact version people decide on")
    aw.add_argument("--clear", action="store_true", help="stop waiting without reading decisions")
    for sp in (fl, pu, li, aw):
        sp.add_argument("--run", required=True, help="the run folder")
        sp.add_argument("--page", required=True, help="the page name, e.g. report")
        sp.add_argument("--json", action="store_true")
    bu = sub.add_parser("build", help="the run page (tm.run_page) from the run state, at a check-in")
    bu.add_argument("--ask", help="this check-in's words (a JSON file the agent wrote), saved before the build")
    bu.add_argument("--local", action="store_true", help="no publishing tool: the page says to answer in chat")
    de = sub.add_parser("decision", help="the choice saved on the published run page for a check-in")
    de.add_argument("checkin", help="the check-in (or card) id the page asked, e.g. G1a")
    de.add_argument("--record", action="store_true", help="record it (tm decide, the note marked from the page)")
    for sp in (bu, de):
        sp.add_argument("--run", required=True, help="the run folder")
        sp.add_argument("--json", action="store_true")
    page_text.add_parser(sub)


def _files(args: argparse.Namespace, run: RunFolder) -> int:
    folder = _built(run, args.page)
    listed = files(folder)
    rel = folder.relative_to(run.path).as_posix()
    cli.emit(args, {"status": "done", "folder": rel, "files": listed, "artifact": artifact_args(listed)},
             "\n".join([f"{rel}:"] + [f"  {f['as']}  {f['path']}" for f in listed]))
    return 0


def _published(args: argparse.Namespace, run: RunFolder) -> int:
    record = record_published(run, args.page, args.slug, args.version, args.url)
    where = f" at {record['url']}" if record["url"] else ""
    cli.emit(args, {"status": "done", **record},
             f"Recorded: the {args.page} page ({record['folder']}) is published as {record['slug']}, "
             f"version {record['version']}{where}.")
    return 0


def _link(args: argparse.Namespace, run: RunFolder) -> int:
    record = published(run, args.page)
    if record is None:
        cli.emit(args, {"status": "none"},
                 f"The {args.page} page has not been published in this run or the runs it follows: publish it "
                 "as a new artifact, or give the local index.html.")
        return 0
    older = f"with the older publish_files, to the same slug with base_version {record['version']}"
    if record.get("url"):
        again = (f"Republish it to the same link: with the Artifact tool, to the same url (list its files first); "
                 f"{older}.")
        said = f"{record['url']}, version {record['version']}"
    else:
        again = f"Republish it {older}."
        said = f"{record['slug']}, version {record['version']}"
    cli.emit(args, {"status": "done", **record},
             f"The {args.page} page was last published as {said}, on {record['published_at'][:10]}. {again}")
    return 0


def _await(args: argparse.Namespace, run: RunFolder) -> int:
    if args.clear:
        _check_name(args.page)
        clear_await(run, args.page)
        message = f"Not waiting for decisions on the {args.page} page any more: a new version can be built."
        cli.emit(args, {"status": "done", "awaiting": None, "message": message}, message)
        return 0
    got = await_(run, args.page, args.version)
    message = (f"Waiting for decisions on the {args.page} page (version {got['version']}): a new version of it is "
               "refused until they are read.")
    cli.emit(args, {"status": "done", "awaiting": got, "message": message}, message)
    return 0


def _build(args: argparse.Namespace, run: RunFolder) -> int:
    from tm import run_page

    got = run_page.build(run, run.given(args.ask) if args.ask else None, local=args.local)
    now = ", ".join(got["open"]) or "nothing open"
    if got["local"]:
        then = (f"No publishing tool: give the user the local page, {got['index']}; its decisions are answered in "
                "chat.")
    elif got["published"]:
        then = (f"Republish it to the same link ({got['published'].get('url') or got['published']['slug']}): list its "
                f"files first, then the Artifact tool with that url, the artifact arguments and the capabilities; "
                f"record it with tm page published --page {run_page.PAGE}.")
    else:
        then = (f"Publish it with the Artifact tool (the artifact arguments and the capabilities), then record it with "
                f"tm page published --page {run_page.PAGE}.")
    if got.get("language_warning"):
        then = f"{got['language_warning']} {then}"
    cli.emit(args, {"status": "done", **got, "message": then},
             f"Built {got['folder']} (now: {now}; {got['settled']} settled). {then}")
    return 0


def _decision(args: argparse.Namespace, run: RunFolder) -> int:
    from tm import flow, run_page

    try:
        got = run_page.record(run, args.checkin) if args.record else run_page.decision(run, args.checkin)
    except flow.Held as exc:
        raise Stop(str(exc)) from None
    note = f' Note: "{got["note"]}"' if got["note"] else ""
    if args.record:
        text = f"Recorded {args.checkin}: {got['choice']} ({got['label']}), from the page.{note}"
    else:
        text = (f"Saved on the page for {args.checkin}: {got['choice']} ({got['label']}) at {got['saved_at']}.{note} "
                f"Record it with tm page decision --run <run> {args.checkin} --record.")
    cli.emit(args, {"status": "done", **got, "message": text}, text)
    return 0


def _run(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        return {"files": _files, "published": _published, "link": _link, "await": _await, "build": _build,
                "decision": _decision, "fetch": page_text.run_fetch}[args.action](args, run)
    except Stop as exc:   # a Stop is a ValueError: caught first, it exits 2
        cli.emit(args, {"status": "stop", "message": str(exc)}, str(exc))
        return 2
    except (OSError, ValueError) as exc:
        return cli.fail(args, str(exc))


cli.register("page", _setup, _run)
