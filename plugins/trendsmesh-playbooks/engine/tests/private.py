"""The private test data: the playbook handoff packages (`handoff/` at the repository root) and the fixtures made from
them that carry real people's words (the EXCLUDE list of tools/public_export.py). They stay in the private
repository; the public copy leaves them out.

A test that needs any of it is marked `@pytest.mark.private_data` (or its module sets `pytestmark`). conftest.py
skips those tests when `handoff/` is missing, so the public copy's suite runs everything else; in the private
repository a missing `handoff/` is an error. `handoff/` stands for all the private data: the left-out fixtures are
in the private repository whenever it is. The CI job `public copy` runs the suite on the export, so a test that
needs the data but lacks the mark fails there (video and tool tests do not run in that job: test_public_export.py
checks their marks by reading the code).

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
PRIVATE_REPO = (REPO / "tools" / "public_export.py").is_file()   # left out of the public copy

ALIASES_FILE = REPO / "tools" / "client_aliases.json"


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
    (tools/client_aliases.json, private): the handoff's data, as the port would write it under the alias."""
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


SKIP_REASON = "needs the private test data (handoff/ and the fixtures made from it), not in the public copy"


def json_fixture(rel: str, empty):
    """The JSON fixture `fixtures/<rel>`, or `empty` in the public copy, where private fixtures are left out. In the
    private repository the file must exist."""
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

