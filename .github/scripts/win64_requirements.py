"""Writes plugins/trendsmesh-playbooks/env/win-64/<tier>.txt, each tier's Python packages on Windows (issue #123).

    python3 .github/scripts/win64_requirements.py

On Windows tm runs on python.org's Python 3.11.9 in one venv per tier (bootstrap/install-python.ps1 and
tm/winpython.py), filled with `pip install --require-hashes --no-deps --only-binary :all: -r <tier>.txt`. This script
writes those files with uv (`uv pip compile`, on PATH), solved for CPython 3.11.9 on win_amd64:

- what a tier asks for is what env/pixi.toml asks of its environment on macOS and Linux (`target.unix`; a
  `target.linux-64` entry wins, so torch comes from the PyTorch index there and here), except Python and the engine
  itself (the venv's tm.pth points at the engine);
- every version is held to the one pixi.lock has for that environment on linux-64, so Windows runs what CI tests;
  a package only Windows needs (colorama, for one) takes the newest;
- pixi.toml's dependency overrides apply (scenedetect's opencv-python is dropped);
- only wheels (`--only-binary :all:`): no user machine builds a package;
- every file gets its SHA-256, so pip refuses anything else.

Run it after a change to a Python package in env/pixi.toml and `pixi lock`. tests/engine/test_win64_requirements.py
checks that the files still follow pixi.toml and pixi.lock.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import tomllib
import urllib.request
from pathlib import Path

import yaml  # the dev environment has it: pixi run -e dev python .github/scripts/win64_requirements.py

ENV = Path(__file__).resolve().parents[2] / "plugins" / "trendsmesh-playbooks" / "env"
OUT = ENV / "win-64"
# The tiers whose tools run Python (tm/envtiers.py): video and animatic run only node.
TIERS = ("base", "breakdown", "voice", "ai", "ocr")
PYTHON = "3.11.9"
PLATFORM = "x86_64-pc-windows-msvc"
NOT_PACKAGES = {"python", "tm"}
# Installed as their pure-Python wheel (the hash of only that file is kept): requests needs charset-normalizer, so tm
# itself imports it, and its compiled wheel is unsigned .pyd files Smart App Control could block. PyYAML has no pure
# wheel, but falls back to pure Python by itself when its _yaml.pyd cannot load.
PURE = {"charset-normalizer"}
HEADER = ("# The {tier} tier's Python packages on Windows (issue #123): python.org's Python {python}, win_amd64.\n"
          "# Written by .github/scripts/win64_requirements.py from env/pixi.toml and pixi.lock (linux-64 versions).\n"
          "# Do not edit by hand. Installed with: pip install --require-hashes --no-deps --only-binary :all: -r\n")


def _spec(name: str, value) -> tuple[str, str | None]:
    """A pixi.toml pypi dependency as a requirement line, and its index when it names one."""
    if isinstance(value, dict):
        version, index = value.get("version", "*"), value.get("index")
    else:
        version, index = value, None
    return (name if version in ("*", "") else f"{name}{version}"), index


def wanted(manifest: dict, env: str) -> tuple[list[str], list[str], list[str]]:
    """(requirements, overrides, extra indexes) for one pixi environment on Windows, from what it asks on Linux."""
    features = [None, *manifest["environments"][env].get("features", [])]
    reqs: dict[str, str] = {}
    indexes: list[str] = []
    overrides: list[str] = []
    for f in features:
        table = manifest if f is None else manifest.get("feature", {}).get(f, {})
        target = table.get("target", {})
        conda = {**target.get("unix", {}).get("dependencies", {})} if f is None else {}
        for name in conda:
            if name not in NOT_PACKAGES:
                reqs[name] = name
        pypi = {**table.get("pypi-dependencies", {}), **target.get("unix", {}).get("pypi-dependencies", {}),
                **target.get("linux-64", {}).get("pypi-dependencies", {})}
        for name, value in pypi.items():
            if name in NOT_PACKAGES:
                continue
            line, index = _spec(name, value)
            reqs[name] = line
            if index and index not in indexes:
                indexes.append(index)
        for name, value in table.get("pypi-options", {}).get("dependency-overrides", {}).items():
            markers = value.get("env-markers") if isinstance(value, dict) else None
            version = value.get("version", "*") if isinstance(value, dict) else value
            line = name if version in ("*", "") else f"{name}{version}"
            overrides.append(f"{line} ; {markers}" if markers else line)
    return sorted(reqs.values(), key=str.lower), overrides, indexes


def locked(lock: dict, env: str) -> dict[str, str]:
    """name -> version of every Python package pixi.lock installs in `env` on linux-64: its pypi packages, and the
    conda packages that depend on Python (pyyaml, requests and theirs)."""
    pypi = {p["pypi"]: p for p in lock["packages"] if "pypi" in p}
    conda = {p["conda"]: p for p in lock["packages"] if "conda" in p}
    found: dict[str, str] = {}
    for entry in lock["environments"][env]["packages"].get("linux-64", []):
        if "pypi" in entry:
            p = pypi.get(entry["pypi"], {})
            if p.get("name") and p.get("version") and p["name"] not in NOT_PACKAGES:
                found[_norm(p["name"])] = str(p["version"])
        elif "conda" in entry:
            p = conda.get(entry["conda"], {})
            if any(str(d).split()[0] == "python" for d in p.get("depends", [])):
                name, version, _build = entry["conda"].rsplit("/", 1)[-1].rsplit("-", 2)
                if name not in NOT_PACKAGES:
                    found[_norm(name)] = version
    return found


def _norm(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


def compile_tier(tier: str, manifest: dict, lock: dict, out: Path) -> None:
    reqs, overrides, indexes = wanted(manifest, tier)
    pins = locked(lock, tier)
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / "in.txt").write_text("\n".join(reqs) + "\n", encoding="utf-8")
        (t / "constraints.txt").write_text("".join(f"{n}=={v}\n" for n, v in sorted(pins.items())), encoding="utf-8")
        (t / "overrides.txt").write_text("".join(f"{o}\n" for o in overrides), encoding="utf-8")
        argv = ["uv", "pip", "compile", str(t / "in.txt"), "-o", str(t / "out.txt"), "--quiet", "--no-header",
                "--python-version", PYTHON, "--python-platform", PLATFORM, "--generate-hashes",
                "--only-binary", ":all:", "--emit-index-url", "--index-strategy", "unsafe-best-match",
                "--constraint", str(t / "constraints.txt"), "--override", str(t / "overrides.txt"),
                *[a for i in indexes for a in ("--extra-index-url", i)]]
        done = subprocess.run(argv, capture_output=True, text=True)
        if done.returncode != 0:
            raise SystemExit(f"{tier}: uv pip compile failed:\n{done.stderr}")
        body = (t / "out.txt").read_text(encoding="utf-8")
    body = body.replace(str(t / "in.txt"), f"env/pixi.toml ({tier})").replace(str(t / "constraints.txt"), "pixi.lock")
    body = body.replace(str(t / "overrides.txt"), "pixi.toml's overrides")
    out.write_text(HEADER.format(tier=tier, python=PYTHON) + pure(body), encoding="utf-8", newline="\n")


def pure(body: str) -> str:
    """Each PURE package keeps only the hash of its pure-Python wheel, so pip installs that one (it takes only a file
    whose hash is listed)."""
    blocks = re.split(r"(?m)^(?=[A-Za-z0-9])", body)
    for i, block in enumerate(blocks):
        m = re.match(r"([A-Za-z0-9._-]+)==(\S+)", block)
        if not m or _norm(m[1]) not in PURE:
            continue
        with urllib.request.urlopen(f"https://pypi.org/pypi/{m[1]}/{m[2]}/json", timeout=60) as r:
            files = json.load(r)["urls"]
        digest = next(f["digests"]["sha256"] for f in files if f["filename"].endswith("-py3-none-any.whl"))
        if f"sha256:{digest}" not in block:
            raise SystemExit(f"{m[1]} {m[2]}: its pure-Python wheel is not among the hashes uv wrote")
        lines = block.splitlines(keepends=True)
        hashes = [ln for ln in lines if ln.strip().startswith("--hash=")]
        rest = [ln for ln in lines if ln not in hashes]
        rest[0] = f"{m[1]}=={m[2]} \\\n"
        blocks[i] = rest[0] + f"    --hash=sha256:{digest}\n" + "".join(rest[1:])
    return "".join(blocks)


def main() -> int:
    manifest = tomllib.loads((ENV / "pixi.toml").read_text(encoding="utf-8"))
    lock = yaml.safe_load((ENV / "pixi.lock").read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)
    for tier in TIERS:
        compile_tier(tier, manifest, lock, OUT / f"{tier}.txt")
        print(f"wrote {OUT / f'{tier}.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
