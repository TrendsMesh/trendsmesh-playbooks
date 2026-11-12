"""Every engine module loads when it is the first one loaded.

Each `tm ...` command and each tool (`python -m tm.tools.deliver`) starts with a different module, so an import
cycle shows only for some commands: the test suite loads most modules early, in its own order, and never sees
it. Wave 6 had one: research_report imported the run page at its top, the run page loads every playbook's page
code, and Organic AI video's engine loads research_report, so `tm tool deliver`, `tm kit` and ten other modules
stopped with "partially initialized module". This loads each module first, alone, in a fresh interpreter's
module table, and names those that fail."""

import json
import os
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

PROBE = r"""
import importlib, json, pkgutil, sys
import tm
names = sorted(m.name for m in pkgutil.walk_packages(tm.__path__, "tm.") if not m.name.endswith("__main__"))
bad = {}
for name in names:
    for k in [k for k in sys.modules if k == "tm" or k.startswith("tm.")]:
        del sys.modules[k]
    try:
        importlib.import_module(name)
    except BaseException as e:
        bad[name] = f"{type(e).__name__}: {e}"
print(json.dumps({"names": names, "bad": bad}))
"""


def test_every_module_loads_when_it_is_loaded_first(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(SRC), "TM_PLUGIN_ROOT": str(SRC.parents[1]),
           "TM_PLUGIN_DATA": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, encoding="utf-8", env=env,
                       cwd=tmp_path, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    got = json.loads(r.stdout.strip().splitlines()[-1])
    assert len(got["names"]) > 100
    assert not got["bad"], ("These modules fail when a command loads them first (an import cycle: import the "
                            "heavier module inside the function that needs it):\n"
                            + "\n".join(f"{n}: {e}" for n, e in got["bad"].items()))
