"""Pick the inpainting mode for removing burned-in captions: free OpenCV vs paid ProPainter.

    tm tool inpaint_mode --run RUN MASK.mp4 COMPOSITE.mp4 --crop X0 Y0 X1 Y1 [--band Y0 Y1]
                         [--max-share 0.003] [--max-seconds 1.5] [--min-pixels 2000] [--out PATH] [--json]

The old-caption mask only matters where the new captions do not cover it. Render the new captions
over the free (OpenCV Telea) base first, then measure how much of the inpainted area stays visible.

Decision (`measured`): "budget" (OpenCV) when, in every frame, visible residue <= max-share of the
frame area and the frames with residue add up to <= max-seconds; otherwise "pro" (ProPainter).
`mode` is what can run now: "pro" only while some AI budget (`ai_usd`) is approved and not spent;
with none, "budget" (the free `tm tool inpaint`) and `pro_wanted` true, so the agent shows both
ways and asks before any money is approved (follow-up to issue 21). A mode set by hand in the run
config (`generation.caption_removal`) always wins over this; the caller applies it.
Ported from handoff/refresh-ad_v02/tools/inpaint_mode.py (VARIANTS 4a). Frames are decoded with
ffmpeg so any path works.
"""

from __future__ import annotations

from pathlib import Path

from tm import state
from tm.tools import _common as c


def decide(mask: Path | str, composite: Path | str, crop: tuple[int, int, int, int],
           band: tuple[int, int] | None = None, max_share: float = 0.003, max_seconds: float = 1.5,
           min_pixels: int = 2000) -> dict:
    import cv2
    import numpy as np

    x0, y0, x1, y1 = crop
    b0, b1 = band or (y0, y1)
    info = c.probe(composite)
    m_info = c.probe(mask)
    if (m_info.get("width"), m_info.get("height")) != (info["width"], info["height"]):
        raise c.ToolError("The mask and the composite must have the same size.")
    w, h, fps = info["width"], info["height"], info["fps"]
    shares, visible_frames = [], 0
    for m, fr in zip(c.decode(mask, w, h, "gray"), c.decode(composite, w, h, "bgr24")):
        old = np.zeros(fr.shape[:2], bool)
        old[y0:y1, x0:x1] = m[y0:y1, x0:x1] > 127
        if not old.any():
            continue
        # new captions: white glyphs and their dark stroke inside the caption band
        hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
        cap = ((hsv[..., 2] > 200) & (hsv[..., 1] < 60)) | (hsv[..., 2] < 50)
        cap = cv2.dilate(cap.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        cap[:b0] = False
        cap[b1:] = False
        vis = int((old & ~cap).sum())
        shares.append(vis / old.size)
        if vis > min_pixels:
            visible_frames += 1
    top = max(shares) if shares else 0.0
    seconds = visible_frames / fps if fps else 0.0
    mode = "budget" if top <= max_share and seconds <= max_seconds else "pro"
    return {"mode": mode, "max_visible_share": round(top, 5), "visible_seconds": round(seconds, 2),
            "thresholds": {"max_share": max_share, "max_seconds": max_seconds, "min_pixels": min_pixels},
            "frames_with_old_caption": len(shares)}


def ai_usd_left(run) -> float:
    """The AI budget approved and not yet spent (0 when the run has none)."""
    try:
        s = state.load(run)
    except (OSError, ValueError):
        return 0.0
    return max(0.0, float(s.budgets.get("ai_usd") or 0) - float(s.spend.get("ai_usd") or 0))


def choose(res: dict, left: float) -> dict:
    """`res` from decide() with the mode that can run now (module docstring)."""
    measured = res["mode"]
    mode = "budget" if measured == "pro" and left <= 1e-9 else measured
    return {**res, "mode": mode, "measured": measured, "ai_usd_left": round(left, 4),
            "pro_wanted": measured == "pro" and mode == "budget"}


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("inpaint_mode", "Budget (OpenCV) or pro (ProPainter) caption removal.")
    p.add_argument("mask")
    p.add_argument("composite")
    p.add_argument("--crop", type=int, nargs=4, required=True, metavar=("X0", "Y0", "X1", "Y1"))
    p.add_argument("--band", type=int, nargs=2, default=None, help="y range of the caption band (default: crop)")
    p.add_argument("--max-share", type=float, default=0.003)
    p.add_argument("--max-seconds", type=float, default=1.5)
    p.add_argument("--min-pixels", type=int, default=2000, help="residue below this per frame is ignored")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    c.inputs(run, a, "mask", "composite")   # a run-relative input, whatever the working folder
    out = c.output(run, a.out, "wip", "inpaint_mode", "json")
    res = choose(decide(a.mask, a.composite, tuple(a.crop), tuple(a.band) if a.band else None,
                        a.max_share, a.max_seconds, a.min_pixels), ai_usd_left(run))
    c.write_json(out, res)
    parents = [c.parent_ref(run, a.mask), c.parent_ref(run, a.composite)]
    c.record(run, out, "tm tool inpaint_mode (OpenCV)", ", ".join(parents),
             params={"crop": a.crop, "band": a.band, **res["thresholds"]}, cost="0 (local)",
             request={"mask": parents[0], "composite": parents[1], "crop": a.crop, "band": a.band}, response=res)
    return c.finish(a, {"tool": "inpaint_mode", "outputs": [c.rel(run, out)], **res},
                    f"Mode: {res['mode']} (largest visible residue {res['max_visible_share']:.3%} of the frame, "
                    f"{res['visible_seconds']} s with residue)"
                    + (". ProPainter would do better, but no AI budget is approved: show both ways and ask"
                       if res["pro_wanted"] else "") + f". Saved to {c.rel(run, out)}.")


if __name__ == "__main__":
    raise SystemExit(main())
