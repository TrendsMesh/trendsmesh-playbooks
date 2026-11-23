"""Claude Code substitutes a skill's and a command's arguments into its text: `$0`, `$1`... are the arguments, so
"$0" or "$1.20" there reach the agent as something else (issue #170, item 3). Amounts are written as "0 USD"."""

import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "trendsmesh-playbooks"
ARGUMENT = re.compile(r"\$\d")


def test_no_skill_or_command_text_holds_an_argument_by_mistake():
    files = sorted(PLUGIN.glob("skills/*/SKILL.md")) + sorted(PLUGIN.glob("commands/*.md"))
    assert len(files) >= 6
    found = [f"{p.relative_to(PLUGIN)}:{n}: {line.strip()[:80]}"
             for p in files for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
             if ARGUMENT.search(line)]
    assert found == [], "write amounts as '1.20 USD', not with a $ before the digits:\n" + "\n".join(found)


def test_the_amounts_read_in_usd():
    organic = (PLUGIN / "skills" / "organic-video" / "SKILL.md").read_text(encoding="utf-8")
    assert "**a script to film** (0 USD" in organic and "recorded as 0 USD" in organic
    assert '"About 1.20 USD"' in organic and "0.08 USD a second" in organic
    brief = (PLUGIN / "skills" / "creative-brief" / "SKILL.md").read_text(encoding="utf-8")
    assert '"The budget is probably 500 USD"' in brief
