"""Every eval case loads: its case.yaml is one YAML mapping, and its prompt.md is a front matter block and the prompt.

`claude plugin eval` refuses a case.yaml that holds more than one YAML document ("case.yaml must be a YAML
object"), and it stops before running anything, so a broken case is found only when the evals are run. Five
cases had their front matter and prompt pasted into case.yaml (behind a `---`) and failed that way. This
reads the committed cases, so it runs with the rest of the suite. The private cases (git-ignored links) are
left out."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[4]
EVALS = "plugins/trendsmesh-playbooks/evals/"


def _cases() -> list[Path]:
    if shutil.which("git") is None or not (REPO / ".git").exists():
        pytest.skip("not a git checkout")
    r = subprocess.run(["git", "-C", str(REPO), "ls-files", "--cached", "--others", "--exclude-standard", "-z",
                        EVALS], capture_output=True, text=True, encoding="utf-8", check=True)
    names = sorted({Path(p).parent for p in r.stdout.split("\0") if p.endswith("/case.yaml")})
    return [REPO / n for n in names if n.parent == Path(EVALS.rstrip("/"))]


def front_matter(text: str) -> tuple[dict | None, str]:
    """A prompt.md's front matter (None without one) and the prompt after it."""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return None, text
    return yaml.safe_load(text[4:end]), text[end + 5:].strip()


def problems(case: Path) -> list[str]:
    out = []
    try:
        loaded = yaml.safe_load((case / "case.yaml").read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        loaded = None
        out.append(f"{case.name}/case.yaml is not one YAML document ({str(e).splitlines()[0]})")
    else:
        if not isinstance(loaded, dict):
            out.append(f"{case.name}/case.yaml is not a YAML mapping")
    if isinstance(loaded, dict) and loaded.get("name") != case.name:
        out.append(f"{case.name}/case.yaml names the case {loaded.get('name')!r}")
    prompt = case / "prompt.md"
    if not prompt.is_file():
        out.append(f"{case.name} has no prompt.md")
        return out
    meta, body = front_matter(prompt.read_text(encoding="utf-8"))
    if not isinstance(meta, dict) or not meta.get("description"):
        out.append(f"{case.name}/prompt.md has no front matter with a description")
    if not body:
        out.append(f"{case.name}/prompt.md has no prompt after its front matter")
    return out


INLINE_FLAGS = re.compile(r"\(\?[imsux]+[):]?")   # Python's (?i), (?s): JavaScript's RegExp refuses them


def grader_problems(case: Path) -> list[str]:
    """A regex grader's pattern and a tool grader's input_match are JavaScript regular expressions: no inline
    flags (a regex grader takes `flags: 'i'`; for "dot matches newline" write [\\s\\S])."""
    out = []
    for g in sorted((case / "graders").glob("*.md")) if (case / "graders").is_dir() else []:
        meta, _ = front_matter(g.read_text(encoding="utf-8"))
        for key in ("pattern", "input_match"):
            value = (meta or {}).get(key)
            if isinstance(value, str) and INLINE_FLAGS.search(value):
                out.append(f"{case.name}/graders/{g.name}: {key} uses an inline flag ({value!r}), which the eval "
                           "runner's JavaScript regex refuses")
    return out


def test_every_eval_case_loads():
    cases = _cases()
    assert len(cases) > 50
    found = [p for c in cases for p in problems(c) + grader_problems(c)]
    assert not found, ("Eval cases `claude plugin eval` would refuse before running anything (case.yaml: the "
                       "context only; prompt.md: the front matter between --- lines, then the prompt):\n"
                       + "\n".join(found))


def test_a_case_with_its_prompt_pasted_into_case_yaml_is_named(tmp_path):
    case = tmp_path / "pasted"
    case.mkdir()
    (case / "case.yaml").write_text('schema_version: "1.1"\nname: pasted\n---\ndescription: "x"\n---\n\nHi\n',
                                    encoding="utf-8")
    found = problems(case)
    assert any("not one YAML document" in p for p in found) and any("no prompt.md" in p for p in found)


def test_a_grader_with_a_python_inline_flag_is_named(tmp_path):
    case = tmp_path / "flagged"
    (case / "graders").mkdir(parents=True)
    (case / "graders" / "g.md").write_text("---\ntype: regex\ntarget: last_message\npattern: '(?i)hello'\n---\n",
                                           encoding="utf-8")
    (case / "graders" / "ok.md").write_text("---\ntype: regex\ntarget: last_message\npattern: 'hello'\nflags: 'i'\n"
                                            "---\n", encoding="utf-8")
    found = grader_problems(case)
    assert len(found) == 1 and "g.md" in found[0] and "inline flag" in found[0]
