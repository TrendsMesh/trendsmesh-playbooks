"""The private test data: the playbook handoff packages (`handoff/` at the repository root) and the fixtures made from
them that carry real people's words. They live in the private data repository, which a TrendsMesh machine clones as
`private/` inside this checkout; `private/tools/install-hooks.sh` links each path in `private/LINKS` into place here
(git-ignored), so tests and evals find them at their usual paths. Anyone else's clone has no `private/`.

A test that needs any of it is marked `@pytest.mark.private_data` (or its module sets `pytestmark`). conftest.py
skips those tests when `private/` is missing, so a public clone's suite runs everything else; when `private/` is
cloned but `handoff/` isn't linked in, it is an error, since a skip would hide the tests. `handoff/` stands for all
the private data: the other links are there whenever it is (test_private_links.py checks every one). CI runs the
suite without `private/`, so a test that needs the data but lacks the mark fails there.

The skip comes after collection, so a module must not read private data at import: read it inside the test or a
fixture, or through `json_fixture` (as test_voice.py's GOLDEN does).
"""

import functools
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
HANDOFF = REPO / "handoff"
AVAILABLE = HANDOFF.is_dir()
PRIVATE_REPO = (REPO / "private").is_dir()   # the private data repo, cloned on TrendsMesh machines only

ALIASES_FILE = REPO / "private" / "tools" / "client_aliases.json"


@functools.lru_cache(maxsize=1)
def _aliases() -> tuple[re.Pattern | None, dict[str, str]]:
    """One pattern for every real name (longest first, so a full name wins over its part; a short one only as a
    whole word), and the made-up one for each."""
    pairs = json.loads(ALIASES_FILE.read_text(encoding="utf-8"))["pairs"] if ALIASES_FILE.is_file() else []
    table = dict(pairs)
    if not table:
        return None, table
    def one(real: str) -> str:      # a short name only as a whole word ("Komisja" stays); a long one anywhere
        return rf"(?<![^\W\d_]){re.escape(real)}(?![^\W\d_])" if len(real) < 6 else re.escape(real)
    return re.compile("|".join(one(r) for r in sorted(table, key=len, reverse=True))), table


def alias(value):
    """`value` (text, bytes, or JSON data) with each client's real name replaced by the made-up one the plugin uses
    (private/tools/client_aliases.json): the handoff's data, as the port would write it under the alias."""
    if isinstance(value, bytes):
        return alias(value.decode("utf-8")).encode("utf-8")
    if isinstance(value, str):
        pattern, table = _aliases()
        return pattern.sub(lambda m: table[m.group(0)], value) if pattern else value
    if isinstance(value, dict):
        return {alias(k): alias(v) for k, v in value.items()}
    if isinstance(value, list):
        return [alias(v) for v in value]
    return value


SKIP_REASON = "needs the private test data (handoff/ and the fixtures made from it), not in a public clone"


def json_fixture(rel: str, empty):
    """The JSON fixture `fixtures/<rel>`, or `empty` in a public clone, where private fixtures are missing. Where
    private/ is linked in, the file must exist."""
    path = HERE / "fixtures" / rel
    if not AVAILABLE and not path.exists():
        return empty
    return json.loads(path.read_text(encoding="utf-8"))


def run_folder(package: str, suffix: str) -> Path:
    """The one example run in `handoff/<package>/examples/` whose folder name ends with `suffix`. Code never names a
    client: the folders keep the handoff's names, which are private."""
    found = sorted((HANDOFF / package / "examples").glob(f"*{suffix}"))
    if len(found) != 1:
        raise FileNotFoundError(f"one run ending in {suffix!r} in {HANDOFF / package / 'examples'}, found {len(found)}")
    return found[0]

