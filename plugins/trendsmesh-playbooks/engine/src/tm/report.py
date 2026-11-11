"""`tm report`: helpers for the report-issue skill.

`check` finds private data left in a draft (an account id, an email, a key, a home folder, an amount
of money, a name from the user's workspace) before it is filed. `findings` and `workspace_values`
are also what `send` and `github` use to refuse a draft that is not clean.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Tuple

from tm import __version__, cli, paths

Finding = Tuple[int, str, str]   # (line, kind, value)

_KEYS = ("account_id", "account_name", "ad_account_id", "ad_account_name", "page_id", "page_name", "brand",
         "business_name", "handle", "campaign_name", "adset_name", "ad_name")
_SKIP_DIRS = {".pixi", "node_modules", ".git", ".venv", "__pycache__"}
_SUFFIXES = {".json", ".jsonl", ".yaml", ".yml"}
_MAX_FILE = 5 * 1024 * 1024        # a bigger file is skipped
_MAX_FILES = 2000                  # the walk stops after reading this many files
_MAX_TOTAL = 50 * 1024 * 1024      # or before reading more than this in all
# Where the plugin saves in a workspace: the run folders (runfolder: <workspace>/runs/) and the library
# (brand.DIR library/brands, brand.CHANNEL_DIR library/channels, library.FILE library/results.jsonl). A workspace
# that is the home folder is read only there.
_PLUGIN_DIRS = ("runs", "library")
_META_FILE = re.compile(r"(?:^|_)meta(?:_|\.|$)", re.IGNORECASE)   # meta_weekly_ads_p01.json, <ad>_meta_daily.json
_MIN_VALUE = 3
_ALLOWED_MAIL = {"contact@trendsmesh.com"}
_ALLOWED_DOMAINS = {"example.com", "example.org", "example.net"}

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_KEY = re.compile(r"(?<![A-Za-z0-9])(?:r8_[A-Za-z0-9]{20,}|sk_[a-f0-9]{40,}|EAA[A-Za-z0-9]{20,}"
                  r"|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_\w{20,})")
_ACT = re.compile(r"(?<![A-Za-z0-9])act_\d{5,}")
_DIGITS = re.compile(r"(?<!\w)\d{13,}(?!\w)")
_PATH = re.compile(r"(?<![\w.-])(?:/(?i:Users|home)/|(?i:c):(?:\\{1,2}|/)(?i:Users)(?:\\{1,2}|/))([^/\\\s\"']+)")
_NUM = r"\d(?:[\d ,.]*\d)?"
_CUR = r"(?:[$€£]|zł|(?<![A-Za-z])(?i:USD|EUR|GBP|PLN)(?![A-Za-z]))"
_AMOUNT = re.compile(rf"(?:{_CUR} ?(?P<a>{_NUM})|(?P<b>{_NUM}) ?{_CUR})")

# When two matches overlap, the more specific kind wins.
_PRIORITY = ["key", "account_id", "email", "home_path", "amount", "workspace_value"]


def _candidates(line: str, known_re: "re.Pattern[str] | None"):
    for m in _KEY.finditer(line):
        yield m.start(), m.end(), "key"
    for m in _ACT.finditer(line):
        yield m.start(), m.end(), "account_id"
    for m in _DIGITS.finditer(line):
        yield m.start(), m.end(), "account_id"
    for m in _EMAIL.finditer(line):
        addr = m.group(0)
        if addr.lower() in _ALLOWED_MAIL or addr.rsplit("@", 1)[1].lower() in _ALLOWED_DOMAINS:
            continue
        yield m.start(), m.end(), "email"
    for m in _PATH.finditer(line):
        if m.group(1) != "<user>":
            yield m.start(), m.end(), "home_path"
    for m in _AMOUNT.finditer(line):
        digits = re.sub(r"\D", "", m.group("a") or m.group("b"))
        if 1 <= len(digits) <= 9:
            yield m.start(), m.end(), "amount"
    if known_re is not None:
        for m in known_re.finditer(line):
            yield m.start(), m.end(), "workspace_value"


def findings(text: str, known: set[str]) -> list[Finding]:
    """The private data in `text`, as (line, kind, value) sorted by line then column. A value that
    several kinds match is reported once, as the most specific kind."""
    values = sorted({v for v in known if v and v.strip()}, key=len, reverse=True)
    known_re = (re.compile(r"(?<!\w)(?:" + "|".join(re.escape(v) for v in values) + r")(?!\w)", re.IGNORECASE)
                if values else None)
    out: list[tuple[int, int, str, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        taken: list[tuple[int, int]] = []
        found = sorted(_candidates(line, known_re), key=lambda c: (_PRIORITY.index(c[2]), c[0]))
        for start, end, kind in found:
            if any(start < e and s < end for s, e in taken):
                continue
            taken.append((start, end))
            out.append((number, start, kind, line[start:end]))
    out.sort(key=lambda f: (f[0], f[1]))
    return [(n, kind, value) for n, _, kind, value in out]


def _collect(node: object, into: set[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _KEYS and isinstance(value, (str, int, float)) and not isinstance(value, bool):
                if len(str(value)) >= _MIN_VALUE:
                    into.add(str(value))
            _collect(value, into)
    elif isinstance(node, list):
        for item in node:
            _collect(item, into)


def _value(node: object) -> "str | None":
    """A saved scalar as text, when it is long enough to be a name or an id."""
    if isinstance(node, (str, int, float)) and not isinstance(node, bool) and len(str(node).strip()) >= _MIN_VALUE:
        return str(node).strip()
    return None


def _at(node: object, *keys: str) -> object:
    for key in keys:
        node = node.get(key) if isinstance(node, dict) else None
    return node


def _add(into: set[str], *nodes: object) -> None:
    """Each of `nodes` that is a value (or a list of values)."""
    for node in nodes:
        for item in node if isinstance(node, list) else [node]:
            value = _value(item)
            if value:
                into.add(value)


def _names(node: object, into: set[str]) -> None:
    """Every `name` and `id` in a Meta answer: the ad account's, each campaign's, ad set's, ad's and creative's."""
    if isinstance(node, dict):
        _add(into, *(node.get(k) for k in ("name", "id") if not isinstance(node.get(k), list)))
        for value in node.values():
            _names(value, into)
    elif isinstance(node, list):
        for item in node:
            _names(item, into)


def _host(url: object) -> "str | None":
    if not isinstance(url, str):
        return None
    host = (urllib.parse.urlsplit(url.strip()).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host or None


def _collect_saved(path: Path, doc: object, into: set[str]) -> None:
    """The names and ids in one saved file `doc`, read as what the plugin saves at `path`."""
    _collect(doc, into)                                  # the watched keys, in any file
    name = path.name.lower()
    tool = _at(doc, "_tool")
    if _META_FILE.search(path.stem) or "meta" in (part.lower() for part in path.parent.parts) or (
            isinstance(tool, str) and tool.startswith("ads_")):
        _names(doc, into)                                # Meta's answers, saved verbatim or in the envelope
    if not isinstance(doc, dict):
        return
    schema = doc.get("schema")
    if schema == "brand/1" or doc.get("kind") == "brand":          # library/brands/<slug>/brand_vNN.json
        products = _at(doc, "catalog", "products")
        _add(into, doc.get("brand"), *(p.get("name") for p in products if isinstance(p, dict))
             if isinstance(products, list) else [])
    if schema == "channel/1" or doc.get("kind") == "channel":      # library/channels/<slug>/channel_vNN.json
        _add(into, doc.get("channel"), doc.get("store"), _at(doc, "voice", "narrator_elevenlabs_id"))
    if name.endswith(("config.yaml", "config.yml")):                 # a run's config.yaml (tm config write)
        _add(into, _at(doc, "account", "id"), _at(doc, "account", "name"), _at(doc, "product", "name"),
             _host(_at(doc, "product", "landing_url")), doc.get("channels"), _at(doc, "intake", "approver"))
    if name == "run.json":
        _add(into, _at(doc, "organic", "channel"))
    if name.endswith(".jsonl") or path.parent.name == "library":    # library/results.jsonl rows
        _add(into, doc.get("account"), doc.get("product"))


def _read_saved(path: Path) -> list:
    """The documents in one saved file: a JSON file's value, each line of a JSONL file, a YAML file's documents."""
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix == ".json":
        return [json.loads(text)]
    if path.suffix == ".jsonl":
        docs = []
        for line in text.splitlines():
            try:
                docs.append(json.loads(line))
            except ValueError:
                continue
        return docs
    import yaml                                          # the engine's own dependency (tm config)
    return list(yaml.safe_load_all(text))


def _secret_values() -> set[str]:
    try:
        text = (paths.data_dir() / "secrets.env").read_text(encoding="utf-8")
    except (OSError, RuntimeError):
        return set()
    values = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        _, sep, value = line.partition("=")
        value = value.strip().strip("'\"")
        if sep and len(value) >= _MIN_VALUE:
            values.add(value)
    return values


def _walk(top: Path):
    """The saved files under `top` (any depth), folder by folder in name order."""
    for folder, dirs, files in os.walk(top):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
        for name in sorted(files):
            path = Path(folder) / name
            if path.suffix.lower() in _SUFFIXES:
                yield path


def _in_reading_order(root: Path, at_home: bool):
    """The files to read, most likely private first: the library, then the runs newest first (a run folder is named
    <date>_<name>, so by name descending, across playbooks), then everything else. A file comes up once."""
    seen: set[Path] = set()

    def fresh(paths_):
        for path in paths_:
            if path not in seen:
                seen.add(path)
                yield path

    yield from fresh(_walk(root / "library"))
    runs = root / "runs"
    try:
        found = [run for pb in sorted(runs.iterdir()) if pb.is_dir() and pb.name not in _SKIP_DIRS
                 for run in sorted(pb.iterdir()) if run.is_dir() and run.name not in _SKIP_DIRS]
    except OSError:
        found = []
    for run in sorted(found, key=lambda r: (r.name, r.parent.name), reverse=True):
        yield from fresh(_walk(run))
    for top in [runs] if at_home else [root]:
        yield from fresh(_walk(top))


def _read_workspace(root: Path) -> "tuple[set[str], int | None]":
    """workspace_values, and the number of files read when a cap stopped the walk (else None)."""
    import yaml

    values: set[str] = set()
    root = Path(root)
    try:
        at_home = root.resolve() == Path.home().resolve()
    except (OSError, RuntimeError):
        at_home = False
    count = total = 0
    for path in _in_reading_order(root, at_home):
        try:
            size = path.stat().st_size
            if size > _MAX_FILE:
                continue
            if count >= _MAX_FILES or total + size > _MAX_TOTAL:
                return values | _secret_values(), count
            count, total = count + 1, total + size
            for doc in _read_saved(path):
                _collect_saved(path, doc, values)
        except (OSError, ValueError, RecursionError, yaml.YAMLError):
            continue
    return values | _secret_values(), None


def workspace_values(root: Path) -> set[str]:
    """Names and ids from what the user's workspace `root` saved (any depth): the watched keys in any JSON, JSONL or
    YAML file, a run's config.yaml (the ad account, the product and its site, the channels, the approver), Meta's
    answers (every name), brand and channel profiles (the brand, its products, the channel, its store, its narrator)
    and the results library; plus the plugin's secrets. A file over _MAX_FILE is skipped; the walk stops after
    _MAX_FILES files or before reading more than _MAX_TOTAL bytes, so it reads the library first, then the runs
    newest first, then the rest: what a cap leaves unread is the oldest. In the home folder only the plugin's own
    folders (_PLUGIN_DIRS) are read."""
    return _read_workspace(root)[0]


# --- command line ------------------------------------------------------------------------------

_SUBCOMMANDS: dict[str, tuple[Callable[[argparse.ArgumentParser], None], Callable[[argparse.Namespace], int]]] = {}


def subcommand(name: str, setup: Callable[[argparse.ArgumentParser], None],
               run: Callable[[argparse.Namespace], int]) -> None:
    """Add `tm report <name>` (send and github register theirs here)."""
    _SUBCOMMANDS[name] = (setup, run)


def _setup(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="report_command", metavar="command")
    for name, (setup, _run) in _SUBCOMMANDS.items():
        setup(sub.add_parser(name))


def _run(args: argparse.Namespace) -> int:
    name = getattr(args, "report_command", None)
    if name is None:
        print("usage: tm report {" + ",".join(_SUBCOMMANDS) + "} ...", file=sys.stderr)
        return 1
    return _SUBCOMMANDS[name][1](args)


def _check_setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("file")
    parser.add_argument("--workspace", default=None)


def _check_run(args: argparse.Namespace) -> int:
    try:
        text = Path(args.file).read_text(encoding="utf-8-sig")
    except (OSError, ValueError) as exc:
        print(f"Cannot read {args.file}: {exc}", file=sys.stderr)
        return 2
    root = Path(args.workspace) if args.workspace else paths.workspace()
    known, stopped = _read_workspace(root)
    if stopped is not None:
        print(f"tm report check: stopped reading the workspace after {stopped} files; values in older runs "
              "were not checked", file=sys.stderr)
    found = findings(text, known)
    if not found:
        print("clean")
        return 0
    for line, kind, value in found:
        print(f"{line}\t{kind}\t{value}")
    return 1


subcommand("check", _check_setup, _check_run)
# --- send: the TrendsMesh inbox --------------------------------------------------------------

DEFAULT_URL = "https://trendsmesh.com/v1/issue-reports"


def _os_name() -> str:
    platform = sys.platform
    if platform == "darwin":
        return "macos"
    if platform.startswith("linux"):
        return "linux"
    if platform in ("win32", "cygwin"):
        return "windows"
    return "other"


def _json(raw: bytes) -> object:
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        return None


def _field(payload: object) -> "str | None":
    try:
        field = payload["error"]["data"]["field"]  # type: ignore[index]
    except (KeyError, TypeError):
        return None
    return field if isinstance(field, str) else None


def _retry_after(headers) -> "int | None":
    value = (headers.get("retry-after") or "").strip() if headers is not None else ""
    return int(value) if value.isdigit() else None


def _unavailable(reason: str) -> dict:
    return {"outcome": "unavailable", "reason": reason[:200]}


def _answer(status: int, raw: bytes, headers) -> dict:
    payload = _json(raw)
    if status == 201:
        try:
            report_id = payload["data"]["reportId"]  # type: ignore[index]
        except (KeyError, TypeError):
            return _unavailable("201 without a report id")
        return {"outcome": "received", "reportId": report_id}
    if status == 400:
        return {"outcome": "invalid", "field": _field(payload)}
    if status == 413:
        return {"outcome": "too_large"}
    if status == 429:
        return {"outcome": "rate_limited", "retryAfter": _retry_after(headers)}
    return _unavailable(str(status))


def _not_clean(body: str, title: str) -> "dict | None":
    """`not_clean` with the findings if the body or the title holds private data, else None."""
    known = workspace_values(paths.workspace())
    found = findings(body, known) + findings(title, known)
    if not found:
        return None
    return {"outcome": "not_clean", "findings": [{"line": n, "kind": k, "value": v} for n, k, v in found]}


def send(body_file: Path, kind: str, title: str, contact: "str | None", url: str,
         timeout: float = 15.0) -> dict:
    """File a report with TrendsMesh. Never raises for a network or server problem: that is
    `unavailable`, so the skill can fall back."""
    body = Path(body_file).read_text(encoding="utf-8-sig")
    unclean = _not_clean(body, title)
    if unclean:
        return unclean
    payload = {"kind": kind, "title": title, "body": body,
               "source": {"name": "trendsmesh-playbooks", "version": __version__}, "os": _os_name()}
    if contact:
        payload["contact"] = contact
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": f"trendsmesh-playbooks/{__version__}"})
    try:
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return _answer(response.status, response.read(), response.headers)
        except urllib.error.HTTPError as exc:
            return _answer(exc.code, exc.read(), exc.headers)
    except Exception as exc:  # network error, timeout, bad URL: the inbox is simply unavailable
        return _unavailable(f"{type(exc).__name__}: {exc}")


def _title_args(parser: argparse.ArgumentParser) -> None:
    title = parser.add_mutually_exclusive_group(required=True)
    title.add_argument("--title")
    title.add_argument("--title-file", help="read the title from this file (one line): no shell quoting")


def _title(args: argparse.Namespace) -> str:
    """The title given, or read from --title-file (ValueError unless it is one line)."""
    if args.title_file is None:
        return args.title
    text = Path(args.title_file).read_text(encoding="utf-8-sig").strip()
    if "\n" in text:
        raise ValueError("the title file must hold one line")
    return text


def _send_setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("file")
    parser.add_argument("--kind", required=True, choices=["bug", "change"])
    _title_args(parser)
    parser.add_argument("--contact", default=None)


def _send_run(args: argparse.Namespace) -> int:
    try:
        result = send(Path(args.file), args.kind, _title(args), args.contact or None,
                      os.environ.get("TM_REPORT_URL") or DEFAULT_URL)
    except (OSError, ValueError) as exc:
        print(f"Cannot read {args.file}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0 if result["outcome"] == "received" else 1


subcommand("send", _send_setup, _send_run)


# --- github: a public issue under the user's own name ----------------------------------------

REPO = "github.com/TrendsMesh/trendsmesh-playbooks"
_AUTH_TIMEOUT = 15
_CREATE_TIMEOUT = 30
_LABELS = {"bug": "bug", "change": "enhancement"}


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1][:200] if lines else ""


def github(body_file: Path, kind: str, title: str) -> dict:
    """File the report as a public issue with the user's own `gh`. `no_gh` when gh is missing or
    signed out, so the skill can fall back to the inbox. Never raises for a gh problem."""
    body = Path(body_file).read_text(encoding="utf-8-sig")
    unclean = _not_clean(body, title)
    if unclean:
        return unclean
    gh = shutil.which("gh")
    if not gh:
        return {"outcome": "no_gh"}
    env = {k: v for k, v in os.environ.items() if k not in ("GH_HOST", "GH_REPO")}
    env["GH_PROMPT_DISABLED"] = "1"
    try:
        if subprocess.run([gh, "auth", "status", "--hostname", "github.com"], capture_output=True,
                           env=env, timeout=_AUTH_TIMEOUT).returncode != 0:
            return {"outcome": "no_gh"}
    except (OSError, subprocess.TimeoutExpired):
        return {"outcome": "no_gh"}
    base = [gh, "issue", "create", "-R", REPO, "--title", title, "--body-file", "-"]
    command = base + ["--label", _LABELS[kind]]
    for attempt in (1, 2):
        try:
            done = subprocess.run(command, input=body.encode("utf-8"), capture_output=True, env=env,
                                  timeout=_CREATE_TIMEOUT)
        except subprocess.TimeoutExpired:
            return {"outcome": "failed", "reason": "gh issue create timed out"}
        except OSError as exc:
            return {"outcome": "failed", "reason": f"{type(exc).__name__}: {exc}"[:200]}
        out = done.stdout.decode("utf-8", "replace")
        err = done.stderr.decode("utf-8", "replace")
        if done.returncode == 0:
            for line in reversed(out.splitlines()):
                if line.strip().startswith("https://"):
                    return {"outcome": "filed", "url": line.strip()}
            return {"outcome": "failed", "reason": "gh printed no issue URL"}
        if attempt == 1 and "label" in (err + out).lower():
            command = base
            continue
        return {"outcome": "failed", "reason": _last_line(err) or f"gh exited {done.returncode}"}
    return {"outcome": "failed", "reason": "unreachable"}  # pragma: no cover


def _github_setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("file")
    parser.add_argument("--kind", required=True, choices=["bug", "change"])
    _title_args(parser)


def _github_run(args: argparse.Namespace) -> int:
    try:
        result = github(Path(args.file), args.kind, _title(args))
    except (OSError, ValueError) as exc:
        print(f"Cannot read {args.file}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0 if result["outcome"] == "filed" else 1


subcommand("github", _github_setup, _github_run)
cli.register("report", _setup, _run)
