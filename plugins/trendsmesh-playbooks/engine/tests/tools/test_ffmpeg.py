"""tm tool ffmpeg: the plugin's own ffmpeg, run inside the run folder, never overwriting."""

import json

from _media import make_clip
from tm.tools import TOOLS
from tm.tools import ffmpeg as tool


def test_last_frame_goes_to_the_next_version_and_the_manifest(run, capsys):
    make_clip(run.path / "03_wip" / "clip 1 — Łódź.mp4", vf="null", seconds=1.0, tone=False)
    argv = ["--run", str(run.path), "--name", "clip1_last_frame", "--ext", "png",
            "--parent", "03_wip/clip 1 — Łódź.mp4", "--json", "--",
            "-sseof", "-0.1", "-i", "03_wip/clip 1 — Łódź.mp4", "-frames:v", "1", "-update", "1"]
    assert tool.main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "done" and out["outputs"] == ["03_wip/clip1-last-frame_v01.png"]
    assert (run.path / "03_wip" / "clip1-last-frame_v01.png").is_file()
    manifest = (run.path / "manifest.md").read_text(encoding="utf-8")
    assert "03_wip/clip1-last-frame_v01.png" in manifest and "-sseof" in manifest
    assert tool.main(argv) == 0                       # never overwrite: the next call makes _v02
    assert (run.path / "03_wip" / "clip1-last-frame_v02.png").is_file()


def test_refuses_overwrite_flags_and_existing_outputs(run, capsys):
    (run.path / "04_final" / "a_v01.mp4").write_bytes(b"x")
    base = ["--run", str(run.path), "--json"]
    assert tool.main([*base, "--out", "04_final/a_v01.mp4", "--", "-f", "lavfi", "-i", "nullsrc"]) == 1
    assert "never overwritten" in capsys.readouterr().out
    assert tool.main([*base, "--name", "b", "--ext", "mp4", "--", "-y", "-f", "lavfi", "-i", "nullsrc"]) == 1
    assert "-y" in capsys.readouterr().out
    assert tool.main([*base, "--out", "../outside.mp4", "--", "-f", "lavfi", "-i", "nullsrc"]) == 1
    assert "inside the run folder" in capsys.readouterr().out
    assert tool.main([*base, "--", "-i", "x.mp4"]) == 1   # neither --out nor --name/--ext


def test_ffmpeg_is_a_free_base_tool():
    assert TOOLS["ffmpeg"].tier == "base" and TOOLS["ffmpeg"].kind_for(["--run", "r"]) is None


def test_refuses_network_addresses_and_unknown_stages(run, capsys):
    base = ["--run", str(run.path), "--name", "x", "--ext", "mp4", "--json"]
    assert tool.main([*base, "--", "-i", "https://example.com/a.mp4"]) == 1
    assert "://" in capsys.readouterr().out
    assert tool.main([*base, "--", "-i", "in.mp4", "-f", "mpegts", "udp://10.0.0.1:1234"]) == 1
    capsys.readouterr()
    assert tool.main([*base, "--stage", "../elsewhere", "--", "-f", "lavfi", "-i", "nullsrc"]) == 1
    assert not list(run.path.parent.glob("elsewhere*"))


def test_one_output_only(run, tmp_path, capsys):
    outside = tmp_path / "elsewhere.mp4"
    base = ["--run", str(run.path), "--name", "y", "--ext", "mp4", "--json", "--"]
    nullsrc = ["-f", "lavfi", "-i", "nullsrc=d=0.1"]
    assert tool.main([*base, *nullsrc, str(outside)]) == 1               # a second output, absolute
    assert "outside the run folder" in capsys.readouterr().out
    assert tool.main([*base, *nullsrc, "../../elsewhere.mp4"]) == 1      # a second output, relative
    capsys.readouterr()
    for opt in (["-report"], ["-vstats_file", "v.txt"], ["-passlogfile", "p"]):
        assert tool.main([*base, *opt, *nullsrc]) == 1
        assert "one output only" in capsys.readouterr().out
    assert not outside.exists()
    make_clip(tmp_path / "brand clip.mp4", vf="null", seconds=0.5, tone=False)   # an input outside is fine
    assert tool.main([*base, "-i", str(tmp_path / "brand clip.mp4"), "-frames:v", "1"]) == 0
