"""Build a page from a style module, the way `tm organic atlas-page` does (lib/page.html + the three libraries inlined).
Usage: python make_page.py <module.js> <out.html> [--aspect 9:16] [--storyboard] [--panels 6]
Without --aspect the frame is 1280x720. For working on the style library; nothing is written but <out.html>."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine" / "src"))
from tm import atlas_prompt  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("module")
ap.add_argument("out")
ap.add_argument("--aspect", default=None)
ap.add_argument("--storyboard", action="store_true")
ap.add_argument("--panels", type=int, default=6)
a = ap.parse_args()
module = Path(a.module).read_text(encoding="utf-8")
html = atlas_prompt.module_page(module, Path(a.module).stem, a.aspect, a.storyboard, a.panels)
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(html, encoding="utf-8")
print(a.out, f"lib from {atlas_prompt.ROOT}")
