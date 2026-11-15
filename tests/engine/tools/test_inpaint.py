"""inpaint (free caption removal, follow-up to issue 21): OpenCV Telea from the teardown's overlay boxes and times,
on a synthetic ad with burned-in word-by-word captions."""

import json
import subprocess

import pytest

pytestmark = pytest.mark.tools
cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from _media import ffmpeg  # noqa: E402
from tm import manifest  # noqa: E402
from tm.tools import _common as c  # noqa: E402
from tm.tools import inpaint, inpaint_mode  # noqa: E402

W, H, FPS, SECONDS = 360, 640, 25, 2.0
BAND = (40, 440, 320, 500)            # where the captions are drawn (x0, y0, x1, y1)
WORDS = [("FREE", 0.2, 0.6, 70), ("WINTER", 0.7, 1.1, 50), ("SALE", 1.2, 1.6, 110)]   # word, from, to (s), x


def _background(t: float):
    """A smooth gradient with a square moving across the top: the picture without captions."""
    y, x = np.mgrid[0:H, 0:W]
    img = np.dstack([(60 + 120 * x / W), (80 + 100 * y / H), (140 - 60 * x / W)]).astype(np.uint8)
    sx = int(20 + 200 * t / SECONDS)
    img[60:140, sx:sx + 80] = (30, 200, 230)
    return img


def _word_at(t: float):
    return next(((w, x) for w, a, b, x in WORDS if a <= t < b), None)


def _frame(f: int, captions: bool = True):
    t = f / FPS
    img = _background(t)
    word = _word_at(t)
    if captions and word:
        text, x = word
        for color, thick in (((20, 20, 26), 9), ((255, 255, 255), 3)):   # dark outline, white glyphs
            cv2.putText(img, text, (x, 485), cv2.FONT_HERSHEY_DUPLEX, 1.5, color, thick, cv2.LINE_AA)
    return img


def _encode(path, frames, audio: bool = True):
    argv = [ffmpeg(), "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
            "-r", str(FPS), "-i", "-"]
    if audio:
        argv += ["-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=44100:duration={SECONDS}"]
    argv += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv420p"]
    argv += (["-c:a", "aac", "-shortest"] if audio else []) + [str(path)]
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE)
    for img in frames:
        proc.stdin.write(img.tobytes())
    proc.stdin.close()
    assert proc.wait() == 0
    return path


def _teardown():
    """What the wave-1 teardown says about this ad: one word_captions overlay, its box and the words' spans."""
    return {"width": W, "height": H, "fps": FPS, "frame_count": int(SECONDS * FPS),
            "scenes": [{"start_s": 0, "end_s": SECONDS, "start_frame": 0, "end_frame": int(SECONDS * FPS) - 1}],
            "overlays": [
                {"kind": "word_captions", "bbox": list(BAND), "start_s": 0.2, "end_s": 1.6,
                 "spans_s": [[a, b] for _, a, b, _ in WORDS]},
                {"kind": "graphic", "bbox": [0, 0, 40, 40], "start_s": 0, "end_s": 2.0, "spans_s": [[0, 2.0]]}]}


@pytest.fixture(scope="module")
def ad(tmp_path_factory):
    folder = tmp_path_factory.mktemp("inpaint")
    n = int(SECONDS * FPS)
    video = _encode(folder / "ad.mp4", [_frame(f) for f in range(n)])
    clean = _encode(folder / "clean.mp4", [_frame(f, captions=False) for f in range(n)], audio=False)
    return video, clean


def _frames(path):
    info = c.probe(path)
    return [f.astype(np.int16) for f in c.decode(path, info["width"], info["height"], "bgr24")]


def _box(img, box=BAND):
    x0, y0, x1, y1 = box
    return img[y0:y1, x0:x1]


def test_regions_follow_the_overlays_spans_and_the_window():
    regs = inpaint.regions(_teardown(), FPS, 50, W, H)
    assert [r["from"] for r in regs] == [0]            # text overlays only: the graphic is left alone
    assert regs[0]["box"] == (24, 424, 336, 516)       # padded by 16 px
    assert regs[0]["spans"] == [(5, 14), (17, 27), (30, 39)]   # the gaps between words stay untouched
    regs = inpaint.regions(_teardown(), FPS, 50, W, H, start=0.7, end=1.2, boxes=[(0, 0, 10, 10)], pad=0)
    assert regs[0]["spans"] == [(17, 27)] and regs[1] == {"box": (0, 0, 10, 10), "spans": [(17, 29)], "from": "box"}
    with pytest.raises(c.ToolError, match="--overlay 5"):
        inpaint.regions(_teardown(), FPS, 50, W, H, overlays=[5])


def test_the_captions_go_without_a_flickering_patch(ad, tmp_path):
    video, clean_ref = ad
    plate, mask = tmp_path / "plate.mp4", tmp_path / "plate_mask.mp4"
    res = inpaint.clean(video, _teardown(), plate, mask)
    assert res["mode"] == "budget" and res["frames"] == 50 and 0 < res["frames_painted"] < 50
    src, out, ref = _frames(video), _frames(plate), _frames(clean_ref)
    assert len(out) == len(src) == 50
    assert c.probe(plate)["has_audio"]
    words = [f for f in range(50) if _word_at(f / FPS)]
    before = np.mean([np.abs(_box(src[f]) - _box(ref[f])).mean() for f in words])
    after = np.mean([np.abs(_box(out[f]) - _box(ref[f])).mean() for f in words])
    assert before > 8 and after < 2.5 and after < before / 5          # the text is gone
    worst = max(np.abs(_box(out[f]) - _box(ref[f])).max(axis=2).mean() for f in words)
    assert worst < 4
    # outside the mask the picture is untouched (codec noise only), the moving square included
    top = (0, 0, W, 300)
    assert max(np.abs(_box(out[f], top) - _box(src[f], top)).mean() for f in range(50)) < 1.5
    # no flicker: frame to frame, the patch changes about as much as the clean picture does
    steps = lambda fr: [np.abs(_box(fr[f]) - _box(fr[f - 1])).mean() for f in range(1, 50)]   # noqa: E731
    assert max(steps(out)) < max(steps(ref)) + 1.5 and max(steps(src)) > 10
    # the mask: white over the words (held a little longer), black far from them
    m = _frames(mask)
    assert _box(m[10]).mean() > 20 and m[10][:300].max() == 0
    assert m[45].max() == 0                                            # after the last word


def test_cli_records_a_free_plate_and_its_mask(ad, run, capsys):
    video, _ = ad
    td = run.path / "02_research" / "teardown_v01.json"
    td.parent.mkdir(parents=True, exist_ok=True)
    td.write_text(json.dumps(_teardown()), encoding="utf-8")
    code = inpaint.main(["--run", str(run.path), str(video), "--teardown", str(td), "--from", "0.5", "--json"])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert code == 0 and out["status"] == "done" and out["cost"] == 0 and out["mode"] == "budget"
    assert out["outputs"] == ["03_wip/inpaint_v01.mp4", "03_wip/inpaint_v01_mask.mp4"]
    assert out["crop"] == [24, 424, 336, 516]
    assert out["regions"][0]["spans_s"][0] == [0.48, 0.6]               # from the frame on screen at 0.5 s
    rows = {r["file"]: r for r in manifest.rows(run)}
    assert rows["03_wip/inpaint_v01.mp4"]["cost"] == "0 (local)"
    assert rows["03_wip/inpaint_v01.mp4"]["source"] == inpaint.SOURCE and "opencv-telea" in inpaint.SOURCE
    assert "03_wip/inpaint_v01_mask.mp4" in rows
    # the mask goes straight into the residue check
    assert inpaint_mode.decide(run.path / out["outputs"][1], run.path / out["outputs"][0], tuple(out["crop"]))[
        "frames_with_old_caption"] > 0


def test_nothing_to_paint_is_an_error(ad, run, capsys):
    video, _ = ad
    td = run.path / "td.json"
    td.write_text(json.dumps({**_teardown(), "overlays": []}), encoding="utf-8")
    code = inpaint.main(["--run", str(run.path), str(video), "--teardown", str(td), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 1 and "--box" in out["message"]
    assert not (run.path / "03_wip" / "inpaint_v01.mp4").exists()


def test_a_teardown_of_another_video_is_refused(ad, tmp_path):
    video, _ = ad
    with pytest.raises(c.ToolError, match="teardown of this video"):
        inpaint.clean(video, {**_teardown(), "width": 1080, "height": 1920}, tmp_path / "p.mp4", tmp_path / "m.mp4")


def test_a_failed_run_leaves_nothing_half_made(ad, tmp_path, monkeypatch):
    """Files are never overwritten, so a left-over mask would block the next try."""
    video, _ = ad
    plate, mask = tmp_path / "plate.mp4", tmp_path / "plate_mask.mp4"

    def fails(args):
        raise subprocess.CalledProcessError(1, "ffmpeg")

    monkeypatch.setattr(c, "run_ffmpeg", fails)
    with pytest.raises(subprocess.CalledProcessError):
        inpaint.clean(video, _teardown(), plate, mask)
    assert sorted(p.name for p in tmp_path.iterdir()) == []
