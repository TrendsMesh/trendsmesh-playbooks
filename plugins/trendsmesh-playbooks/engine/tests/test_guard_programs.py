"""The key guard never blocks what the plugin itself asks for, and it knows every program the engine runs (issue 62).

The guard (bootstrap/guard-secrets.sh and .ps1) lets a call name the plugin's data folder only for the programs
bootstrap/guard-programs.txt lists. These tests catch a blocked call while we build, not in a user's run:

- every command the playbooks, the commands and the engine tell Claude to run (the `tm ...` and `gh ...` lines in each
  SKILL.md, references/flow.md and commands/*.md, and the `tm ...` commands in the engine's messages) goes through the
  real guard, under sh and under PowerShell where they are on this computer, in a TrendsMesh workspace that keeps
  keys in .secrets/ (where the guard is strictest); a blocked one fails, named with its file;
- every program the engine starts (read from its subprocess calls) must be on the list, and every program on the
  list must still be started by the engine or named by a playbook.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
from collections import defaultdict
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
BOOT = PLUGIN / "bootstrap"
PROGRAMS = BOOT / "guard-programs.txt"
ENGINE = PLUGIN / "engine" / "src" / "tm"

# --- the list ------------------------------------------------------------------------------------


def listed() -> tuple[list[str], list[str]]:
    """(paths in the data folder, programs outside it) as guard-programs.txt lists them."""
    paths, outside = [], []
    for line in PROGRAMS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("outside:"):
            outside += line[len("outside:"):].split()
        else:
            paths.append(line)
    return paths, outside


def program_name(path: str) -> str:
    name = path.rsplit("/", 1)[-1].lower()
    return re.sub(r"\.(exe|cmd)$", "", name)


def listed_names() -> set[str]:
    paths, outside = listed()
    return {program_name(p) for p in paths} | set(outside)


def test_the_list_names_paths_in_the_data_folder_only():
    paths, outside = listed()
    assert paths and outside
    for p in paths:
        assert not p.startswith(("/", "~", "$")) and ".." not in p.split("/") and "\\" not in p, p
        assert re.fullmatch(r"[A-Za-z0-9_.*/+-]+", p), f"{p}: only letters, digits, _ . - + * and / in a path"


# --- what Claude is told to run ------------------------------------------------------------------

FIRST_WORDS = {"tm", "gh", "pixi", "python", "python3", "node", "npm", "npx", "ffmpeg", "ffprobe"}
DATA_WORDS = ("TM_PLUGIN_DATA", "CLAUDE_PLUGIN_DATA", "TM_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT", "plugins/data")


def _is_command(text: str) -> bool:
    words = text.split()
    return bool(words) and (words[0] in FIRST_WORDS or any(w in text for w in DATA_WORDS))


def _spans(text: str) -> list[str]:
    """Inline code spans and the lines of fenced code blocks."""
    found, block = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            block = not block
            continue
        if block:
            found.append(line.strip())
        else:
            found += re.findall(r"`([^`]+)`", line)
    return found


def _sources() -> list[Path]:
    docs = [*sorted(PLUGIN.glob("skills/*/SKILL.md")), *sorted(PLUGIN.glob("skills/*/references/flow.md")),
            *sorted(PLUGIN.glob("commands/*.md"))]
    engine = [*sorted(ENGINE.rglob("*.py")), *sorted((PLUGIN / "data").rglob("*.yaml"))]
    return docs + engine


def told_to_run() -> dict[str, list[str]]:
    """Each command -> the files (relative to the plugin) that tell Claude to run it."""
    commands: dict[str, list[str]] = defaultdict(list)
    for path in _sources():
        for span in _spans(path.read_text(encoding="utf-8")):
            span = span.strip()
            if _is_command(span):
                where = path.relative_to(PLUGIN).as_posix()
                if where not in commands[span]:
                    commands[span].append(where)
    return dict(commands)


def test_the_playbooks_and_the_engine_give_commands_to_check():
    commands = told_to_run()
    files = {f for where in commands.values() for f in where}
    assert len(commands) > 200
    for playbook in ("create-ad", "creative-brief", "organic-video", "refresh-ad", "trend-research"):
        assert f"skills/{playbook}/SKILL.md" in files and f"skills/{playbook}/references/flow.md" in files
    assert "commands/doctor.md" in files and any(f.startswith("engine/src/tm/") for f in files)


def _hook_command() -> str:
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    return command.replace("${CLAUDE_PLUGIN_ROOT}", PLUGIN.as_posix())


def _call(cwd: Path, command: str) -> str:
    return json.dumps({"session_id": "s", "transcript_path": "/t.jsonl", "cwd": cwd.as_posix(),
                       "hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}},
                      ensure_ascii=False)


@pytest.fixture
def workspace(tmp_path):
    """A TrendsMesh workspace that keeps its keys in .secrets/, and a data folder, as the guard reads them."""
    ws = tmp_path / "ws"
    (ws / ".secrets").mkdir(parents=True)
    (ws / ".secrets" / "api_keys.env").write_text("", encoding="utf-8")
    (ws / "runs" / "01-refresh-ad").mkdir(parents=True)
    data = tmp_path / "home" / ".claude" / "plugins" / "data" / "trendsmesh-playbooks-x"
    data.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_PLUGIN_", "TM_PLUGIN_"))}
    env.update(CLAUDE_PLUGIN_DATA=data.as_posix(), CLAUDE_PLUGIN_ROOT=PLUGIN.as_posix())
    return ws, env


def _run_sh(calls: list[str], env: dict) -> list[str]:
    sh = shutil.which("sh")
    if sh is None:
        pytest.skip("no sh on this computer (the Git Bash job runs the sh guard on Windows)")
    command = _hook_command()

    def one(call: str) -> str:
        done = subprocess.run([sh, "-c", command], input=call.encode("utf-8"), capture_output=True, env=env,
                              timeout=60)
        assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
        return done.stdout.decode("utf-8", "replace").strip()

    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 2)) as pool:
        return list(pool.map(one, calls))


# One PowerShell runs the guard for every call, each in a fresh PowerShell instance of its own (where the guard's
# exit ends only that instance), with the call put where the guard reads its stdin.
_PS_BATCH = r"""
$ErrorActionPreference = 'Stop'
$text = [IO.File]::ReadAllText($env:TM_GUARD_PS1)
$from = '[Console]::OpenStandardInput()'
if (([regex]::Matches($text, [regex]::Escape($from))).Count -ne 1) { throw "guard-secrets.ps1 no longer reads its stdin with $from" }
$text = $text.Replace($from, '([IO.MemoryStream]::new([Text.Encoding]::UTF8.GetBytes($GuardCall)))')
$calls = [IO.File]::ReadAllText($env:TM_GUARD_CALLS, [Text.Encoding]::UTF8) | ConvertFrom-Json
$out = foreach ($c in $calls) {
    $ps = [powershell]::Create()
    $null = $ps.AddScript('$GuardCall = ''' + $c.Replace("'", "''") + "'`n" + $text)
    (@($ps.Invoke() | ForEach-Object { [string]$_ }) -join "`n")
    $ps.Dispose()
}
[IO.File]::WriteAllText($env:TM_GUARD_OUT, (ConvertTo-Json -InputObject @($out) -Compress), (New-Object Text.UTF8Encoding $false))
"""


def _run_ps(calls: list[str], env: dict, tmp: Path) -> list[str]:
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if pwsh is None:
        pytest.skip("no PowerShell on this computer")
    (tmp / "calls.json").write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")
    env = {**env, "TM_GUARD_PS1": str(BOOT / "guard-secrets.ps1"), "TM_GUARD_CALLS": str(tmp / "calls.json"),
           "TM_GUARD_OUT": str(tmp / "out.json")}
    done = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", _PS_BATCH], capture_output=True,
                          env=env, timeout=900)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    out = json.loads((tmp / "out.json").read_text(encoding="utf-8-sig"))
    out = [out] if isinstance(out, str) else out
    assert len(out) == len(calls)
    return [(o or "").strip() for o in out]


def blocked(commands: dict[str, list[str]], outputs: list[str]) -> list[str]:
    """`command (files): the guard's reason` for each command whose output is a denial."""
    lines = []
    for (command, where), out in zip(commands.items(), outputs):
        if '"deny"' in out:
            reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
            lines.append(f"{command}  ({', '.join(where)}): {reason}")
    return lines


@pytest.mark.parametrize("shell", ["sh", "powershell"])
def test_the_guard_lets_through_every_command_the_plugin_gives(shell, workspace, tmp_path):
    ws, env = workspace
    commands = told_to_run()
    calls = [_call(ws, c) for c in commands]
    outputs = _run_sh(calls, env) if shell == "sh" else _run_ps(calls, env, tmp_path)
    stopped = blocked(commands, outputs)
    assert not stopped, (f"The key guard ({shell}) blocks {len(stopped)} command(s) the plugin tells Claude to run. "
                         f"Rephrase the command in its file, or, if the guard is wrong, fix the guard (both "
                         f"bootstrap/guard-secrets.sh and .ps1):\n" + "\n".join(stopped))


def test_a_blocked_command_is_named_with_its_file():
    out = json.dumps({"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "rule: x"}})
    lines = blocked({"tm next --json": ["skills/a/SKILL.md"], "tm doctor": ["commands/doctor.md"]}, [out, ""])
    assert lines == ["tm next --json  (skills/a/SKILL.md): rule: x"]


# --- what the engine starts ----------------------------------------------------------------------

SUBPROCESS = {"run", "Popen", "call", "check_call", "check_output"}
# The browser the engine starts: the user's Chrome or Edge (outside), or Remotion's headless shell (in the data folder).
BROWSER = ("browser", "chrome-headless-shell")


class Unresolved(Exception):
    pass


def _name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


class Engine:
    """The engine's subprocess calls, and the programs they start, read from its source."""

    def __init__(self, root: Path = ENGINE):
        self.root = root
        self.defs: dict[str, list[tuple[Path, ast.AST]]] = defaultdict(list)
        self.calls: list[tuple[Path, ast.AST, ast.Call]] = []   # (file, enclosing function or module, call)
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            self._walk(path, tree, tree)

    def _walk(self, path: Path, node: ast.AST, scope: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.defs[child.name].append((path, child))
                self._walk(path, child, child)
                continue
            if isinstance(child, ast.Call):
                self.calls.append((path, scope, child))
            self._walk(path, child, scope)

    def where(self, path: Path, node: ast.AST) -> str:
        return f"{path.relative_to(PLUGIN).as_posix()}:{getattr(node, 'lineno', '?')}"

    @staticmethod
    def _own(scope: ast.AST):
        """The nodes of `scope` outside its nested functions."""
        stack = list(ast.iter_child_nodes(scope))
        while stack:
            node = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            yield node
            stack.extend(ast.iter_child_nodes(node))

    def _assigned(self, scope: ast.AST, name: str) -> list[ast.expr]:
        values = []
        for node in self._own(scope):
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                values.append(node.value)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name \
                    and node.value is not None:
                values.append(node.value)
            elif isinstance(node, ast.NamedExpr) and node.target.id == name:
                values.append(node.value)
        return values

    def _passed(self, path: Path, scope: ast.AST, name: str) -> list[tuple[Path, ast.AST, ast.expr]]:
        """What the callers of function `scope` pass for its parameter `name`."""
        if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return []
        params = [a.arg for a in (*scope.args.posonlyargs, *scope.args.args)]
        if name not in params:
            return []
        index, found = params.index(name), []
        for cpath, cscope, call in self.calls:
            # a call by its bare name is to this module's function; module.name(...) can come from anywhere
            if _name(call.func) != scope.name or (isinstance(call.func, ast.Name) and cpath != path):
                continue
            if index < len(call.args):
                found.append((cpath, cscope, call.args[index]))
            found += [(cpath, cscope, k.value) for k in call.keywords if k.arg == name]
        return found

    def argvs(self, path: Path, scope: ast.AST, node: ast.expr, depth: int = 0) -> list[list[tuple]]:
        """Every argv `node` can be, as lists of (file, scope, element)."""
        if depth > 12:
            raise Unresolved(self.where(path, node))
        if isinstance(node, (ast.List, ast.Tuple)):
            ways: list[list[tuple]] = [[]]
            for elt in node.elts:
                if isinstance(elt, ast.Starred):
                    try:
                        subs = self.argvs(path, scope, elt.value, depth + 1)
                    except Unresolved:   # arguments only, as long as the program comes before them
                        return [w + [(path, scope, None)] for w in ways]
                    ways = [w + s for w in ways for s in subs]
                else:
                    ways = [w + [(path, scope, elt)] for w in ways]
            return ways
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            lefts = self.argvs(path, scope, node.left, depth + 1)
            rights = self.argvs(path, scope, node.right, depth + 1)
            return [a + b for a in lefts for b in rights]
        if isinstance(node, ast.Name):
            values = self._assigned(scope, node.id)
            if values:
                return [w for v in values for w in self.argvs(path, scope, v, depth + 1)]
            passed = self._passed(path, scope, node.id)
            if passed:
                return [w for p, s, v in passed for w in self.argvs(p, s, v, depth + 1)]
        if isinstance(node, ast.Call) and _name(node.func) in self.defs:
            ways = []
            for dpath, fn in self.defs[_name(node.func)]:
                if isinstance(node.func, ast.Name) and dpath != path:
                    continue
                for ret in self._own(fn):
                    if isinstance(ret, ast.Return) and ret.value is not None:
                        ways += self.argvs(dpath, fn, ret.value, depth + 1)
            if ways:
                return ways
        raise Unresolved(self.where(path, node))

    def program(self, path: Path, scope: ast.AST, node: ast.expr, depth: int = 0) -> tuple[str, ...]:
        """The program(s) an argv element names."""
        if node is None or depth > 12:
            raise Unresolved(self.where(path, node))
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return (node.value,)
        if isinstance(node, ast.Call):
            name = _name(node.func) or ""
            if name == "str" and node.args:
                return self.program(path, scope, node.args[0], depth + 1)
            if name.endswith("_bin"):
                return (name[:-len("_bin")],)
            if name in ("_node_tool", "which") and node.args and isinstance(node.args[0], ast.Constant):
                return (node.args[0].value,)
            if name in ("find_browser", "need"):
                return BROWSER
        if isinstance(node, ast.Name):
            if "browser" in node.id:
                return BROWSER
            values = self._assigned(scope, node.id)
            if values:
                return tuple(p for v in values for p in self.program(path, scope, v, depth + 1))
            passed = self._passed(path, scope, node.id)
            if passed:
                return tuple(p for cp, cs, v in passed for p in self.program(cp, cs, v, depth + 1))
        raise Unresolved(self.where(path, node))

    def started(self) -> tuple[dict[str, list[str]], list[str]]:
        """(program -> the subprocess calls that start it, the calls whose program can't be read)."""
        found: dict[str, list[str]] = defaultdict(list)
        unknown = []
        for path, scope, call in self.calls:
            func = call.func
            if not (isinstance(func, ast.Attribute) and func.attr in SUBPROCESS and isinstance(func.value, ast.Name)
                    and func.value.id == "subprocess"):
                continue
            argv = call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == "args"), None)
            here = self.where(path, call)
            try:
                for way in self.argvs(path, scope, argv):
                    if not way:
                        raise Unresolved(here)
                    first = self.program(*way[0])
                    names = list(first)
                    values = [e.value if isinstance(e, ast.Constant) else None for _, _, e in way]
                    if "pixi" in first and "run" in values:   # a program inside a pixi environment
                        if "-e" not in values or values.index("-e") + 2 >= len(way):
                            raise Unresolved(here)
                        names += self.program(*way[values.index("-e") + 2])
                    for n in names:
                        if here not in found[program_name(n)]:
                            found[program_name(n)].append(here)
            except Unresolved as exc:
                unknown.append(f"{here} (at {exc})")
        return dict(found), unknown


@lru_cache(maxsize=1)
def engine_programs() -> tuple[dict[str, list[str]], list[str]]:
    return Engine().started()


def test_the_engine_reads_its_programs():
    found, _ = engine_programs()
    for name in ("pixi", "python", "ffmpeg", "ffprobe", "node", "npm", "npx", "gh"):
        assert name in found, name


def test_every_program_the_engine_starts_is_on_the_list():
    found, unknown = engine_programs()
    assert not unknown, ("These subprocess calls start a program this test cannot read. Name the program in the "
                         "argv (a string, a *_bin() helper, _node_tool(...) or shutil.which(...)), or teach "
                         "Engine.program in this test to read it:\n" + "\n".join(unknown))
    missing = {n: where for n, where in found.items() if n not in listed_names()}
    assert not missing, ("The engine starts program(s) bootstrap/guard-programs.txt does not list. Add each: its "
                         "path in the plugin's data folder when it is installed there, else an `outside:` name:\n"
                         + "\n".join(f"{n}: {', '.join(w)}" for n, w in sorted(missing.items())))


def test_every_program_on_the_list_is_still_used():
    found, _ = engine_programs()
    told = {c.split()[0] for c in told_to_run()}
    stale = sorted(n for n in listed_names() if n not in found and n not in told)
    assert not stale, f"guard-programs.txt lists program(s) nothing in the plugin starts any more: {stale}"


def test_a_new_program_in_the_engine_is_named(tmp_path):
    (tmp_path / "x.py").write_text(
        "import subprocess\n"
        "def go(argv):\n    subprocess.run(argv)\n"
        "def a():\n    go(['whisper-cli', '-f', 'a.wav'])\n"
        "def b():\n    subprocess.run([str(paths.pixi_bin()), 'run', '-e', 'base', 'uv', 'sync'])\n"
        "def c(x):\n    subprocess.run(x.argv)\n", encoding="utf-8")
    engine = Engine.__new__(Engine)
    engine.root, engine.defs, engine.calls = tmp_path, defaultdict(list), []
    tree = ast.parse((tmp_path / "x.py").read_text(encoding="utf-8"))
    engine._walk(tmp_path / "x.py", tree, tree)
    engine.where = lambda path, node: f"x.py:{getattr(node, 'lineno', '?')}"
    found, unknown = engine.started()
    assert set(found) == {"whisper-cli", "pixi", "uv"}
    assert unknown == ["x.py:9 (at x.py:9)"]
