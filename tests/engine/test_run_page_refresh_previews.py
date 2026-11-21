"""Issue #131 item 4: Refresh an ad's run page shows an edited video over 15 MB as its 720p preview, so the page
builds at G5 and every later check-in; the full video stays in the run."""

import json
import re
from datetime import date

import pytest

from tm import manifest, run_page, state
from tm.flow import set_level
from tm.organic_pages.gate import VIDEO_MAX_BYTES
from tm.runfolder import RunFolder
from tm.stops import Stop
from tm.tools import deliver


@pytest.fixture
def run(tmp_path):
    r = RunFolder.create(tmp_path, "Ad 3", date(2026, 11, 5))
    s = state.load(r)
    s.outputs = ["creative_brief", "edited_video"]
    state.save(r, s)
    set_level(r, "every_step")
    (r.path / "00_raw" / "orig.mp4").write_bytes(b"a small original")
    with open(r.path / "04_final" / "edited_v01.mp4", "wb") as fh:
        fh.truncate(VIDEO_MAX_BYTES + 1)                       # a 27 s edit at CRF 19 is about 24 MB
    manifest.record(r, "04_final/edited_v01.mp4", "04_final", "test", before_after="after (before: 00_raw/orig.mp4)")
    return r


def _ask(run):
    path = run.path / "03_wip" / "my_ask_G5.json"
    path.write_text(json.dumps({"checkin": "G5", "title": "The edited video", "question": "Approve it?",
                                "options": [{"choice": "accept", "label": "Approve", "recommended": True}]}),
                    encoding="utf-8")
    return path


def _fake_preview(size: int):
    made = []

    def preview(r, path):
        out = deliver.preview_of(r, path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "wb") as fh:
            fh.truncate(size)
        made.append(out.name)
        return out
    return made, preview


def test_a_big_edited_video_is_shown_as_its_720p_preview(run, monkeypatch):
    made, preview = _fake_preview(1000)
    monkeypatch.setattr(deliver, "make_preview", preview)
    built = run_page.build(run, _ask(run))
    html = (run.path / built["folder"] / "index.html").read_text(encoding="utf-8")
    srcs = re.findall(r'src="([^"]+)"', html)
    assert made == ["edited_v01_720p.mp4"] and any(s.endswith("edited_v01_720p.mp4") for s in srcs)
    assert not any(s.endswith("/edited_v01.mp4") for s in srcs)
    assert (run.path / "04_final" / "edited_v01.mp4").stat().st_size > VIDEO_MAX_BYTES   # the full file stays
    run_page.build(run, _ask(run))                                    # made once: the next build reuses it
    assert made == ["edited_v01_720p.mp4"]


def test_a_preview_still_over_the_limit_stops_with_why(run, monkeypatch):
    monkeypatch.setattr(deliver, "make_preview", _fake_preview(VIDEO_MAX_BYTES + 1)[1])
    with pytest.raises(Stop, match="even its 720p preview"):
        run_page.build(run, _ask(run))
