"""Our style library is ours (issue #75): no text or code of the third-party style atlas the plugin used to ship
(Futurepedia's "AI Style Atlas", HubSpot's content) comes back into the tree.

`fixtures/futurepedia_fingerprints.json` holds fingerprints of distinctive passages of the originals, never their
text: each is `[anchor, hash, where]`, where `anchor` is the passage's first 6 characters, `hash` the first 16 hex
digits of the SHA-256 of its first 40 characters (whitespace runs folded to one space) and `where` the part of the
original it came from (a style's description, motion or explainer note, its reference code, the helper library,
the sound kit, the prompt header, the prompt book). A file fails when a 40-character window starting at an anchor
hashes to a fingerprint. The scan covers every file git knows (tracked or untracked, not ignored) when the plugin
sits in its repository, else the plugin folder."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path

import pytest

from tm import paths

PLUGIN = paths.bundled_data().parent
REPO = PLUGIN.parents[1]
FINGERPRINTS = Path(__file__).resolve().parent / "fixtures" / "futurepedia_fingerprints.json"
WINDOW = 40
SKIP_DIRS = {".git", "node_modules", ".pixi", "__pycache__", ".pytest_cache", ".claude", ".worktrees"}
MAX_BYTES = 20 * 1024 * 1024


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _trie(words) -> str:
    """One regex for many literal anchors, their common prefixes shared (much faster than a plain alternation)."""
    root: dict = {}
    for word in words:
        node = root
        for ch in word:
            node = node.setdefault(ch, {})
        node[""] = {}

    def rx(node: dict) -> str:
        alts = [re.escape(ch) + rx(sub) for ch, sub in sorted(node.items()) if ch]
        if "" in node or not alts:
            return ""
        return alts[0] if len(alts) == 1 else "(?:" + "|".join(alts) + ")"
    return rx(root)


def _matcher(fingerprints):
    by_anchor = defaultdict(set)
    for anchor, digest, _where in fingerprints:
        by_anchor[anchor].add(digest)
    where = {digest: w for _a, digest, w in fingerprints}
    rx = re.compile("(?=(" + _trie(by_anchor) + "))")

    def found(text: str) -> list[str]:
        text = re.sub(r"\s+", " ", text)
        hits = []
        for m in rx.finditer(text):
            digest = _digest(text[m.start():m.start() + WINDOW])
            if digest in by_anchor[m.group(1)]:
                hits.append(where[digest])
        return hits
    return found


def _files() -> list[Path]:
    if (REPO / ".git").exists() and (REPO / "plugins" / PLUGIN.name) == PLUGIN:
        try:
            out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=REPO,
                                 capture_output=True, check=True).stdout.decode("utf-8", "replace")
            return [REPO / name for name in out.split("\0") if name
                    and not SKIP_DIRS.intersection(Path(name).parts)]
        except (OSError, subprocess.CalledProcessError):
            pass
    found = []
    for root, dirs, files in os.walk(PLUGIN):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        found += [Path(root) / f for f in files]
    return found


def _text(path: Path) -> str | None:
    try:
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:4096]:
        return None
    return data.decode("utf-8", "replace")


def test_the_matcher_finds_a_fingerprinted_passage_anywhere_in_a_file():
    passage = "a made-up passage, long enough to fingerprint it here"
    found = _matcher([[passage[:6], _digest(passage[:WINDOW]), "test"]])
    assert found("x = 1\n// " + passage.replace(" ", "\n   ", 3)) == ["test"]
    assert found(passage[:WINDOW - 1]) == [] and found("nothing like it") == []


def test_fingerprints_are_hashes_not_text():
    fingerprints = json.loads(FINGERPRINTS.read_text(encoding="utf-8"))
    assert len(fingerprints) > 400
    assert all(len(a) == 6 and re.fullmatch(r"[0-9a-f]{16}", h) for a, h, _w in fingerprints)


def test_no_third_party_style_text_or_code_in_the_tree():
    found = _matcher(json.loads(FINGERPRINTS.read_text(encoding="utf-8")))
    bad = {}
    for path in _files():
        if path == FINGERPRINTS:
            continue
        text = _text(path)
        if text is not None and (hits := found(text)):
            bad[path.relative_to(REPO if REPO in path.parents else PLUGIN).as_posix()] = sorted(set(hits))[:4]
    assert not bad, f"passages of the third-party style atlas are back (issue #75): {bad}"


def test_the_old_catalogue_is_gone():
    assert not (PLUGIN / "data" / "ai-style-atlas").exists()
    if (REPO / "handoff").is_dir():
        assert not (REPO / "handoff" / "organic-video_v02" / "resources" / "ai-style-atlas").exists()


@pytest.mark.parametrize("name", ["brush.js", "sound.js", "player.js"])
def test_our_library_has_no_global_h(name):
    """Our helpers live on `window.Brush`, never on a global `H`."""
    text = (PLUGIN / "data" / "styles" / "lib" / name).read_text(encoding="utf-8")
    assert not re.search(r"\bwindow\.H\b|\bconst H\s*=", text)
