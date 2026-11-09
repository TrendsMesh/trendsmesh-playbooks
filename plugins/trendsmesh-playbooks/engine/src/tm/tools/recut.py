"""recut: render a checked edit list (path C-R). A port of handoff v03 tools/recut.py.

    tm tool recut --run RUN EDIT.json --teardown T [--transcript X] [--json]

The edit list is the JSON `tm recut check` reads (see recut_plan's docstring for the header fields).
Its format is the handoff's, unchanged:

    {"fps": 30, "width": 720, "height": 1280,
     "video": [{"src": "a.mp4", "from": 0.0, "to": 11.146, "speed": 1.0,
                "seam": "cut" | "dissolve", "seam_frames": 6,
                "audio_src": ..., "audio_from": ..., "audio_head": s, "audio_tail": s}, ...],
     "audio": [{"src": "music.wav", "from": 0.0, "to": 11.146}, ...],   # the music edit
     "audio_mode": "sync", "sync_xfade_ms": 40,
     "audio_xfade_ms": 40, "audio_tail_fade_ms": 300,
     "extra_audio": [{"src": "vo.wav", "at": 3.2, "gain_db": 0}]}

Every `src` is relative to the edit list's own folder (or absolute), with either separator. `out` is
not used: the output goes to `04_final/<variant>_vNN.mp4` (never overwritten; the next free version)
with the sidecar `<same name>.recut.json` next to it (the spec, `joints_s`, `length_s`, the segment
frames, the picture and music lengths). Each gets a manifest row.

The tool runs `recut_plan.check` first (mode and approved budgets from the run, ruling R3), records
its verdict in run.json `recut.checked` as `tm recut check` does, and renders only an edit list whose
status is "ok"; otherwise it exits 2, lists the problems and writes nothing else. The picture follows
`recut_plan.timeline`, the same count `check` judged: each segment is forced to exactly its frames
(ffmpeg's fps filter can give one more), and the joints, the length and the sync sound follow from
them. `extra_audio` layers are the ones `recut_plan.extra_audio` validated, decoded through ffmpeg at
48 kHz (a mono layer keeps its level on both channels). Rendering is free: no budget kind. ffmpeg runs
as argv lists; audio is decoded through ffmpeg.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from tm import config, recut_plan, state
from tm.runfolder import slug
from tm.tools import _common as c

SR = 48000


def _channels(path: Path) -> int:
    out = subprocess.run([c.ffprobe_bin(), "-v", "error", "-select_streams", "a:0", "-show_entries",
                          "stream=channels", "-of", "csv=p=0", c.media(path)],
                         capture_output=True, text=True, check=True).stdout.strip().split(",")[0]
    return int(out) if out.isdigit() else 0


def load_audio(path: Path, a: float = 0.0, b: float | None = None, *, mono_level: bool = False):
    """Stereo float32 at SR from `a` to `b` seconds of `path` (to its end without `b`), decoded by
    ffmpeg. ffmpeg spreads a mono file over two channels at -3 dB; `mono_level` keeps its level."""
    import numpy as np

    span = ["-ss", f"{a:.4f}"] if a else []
    if b is not None:
        span += ["-t", f"{b - a:.4f}"]
    up = ["-af", "pan=stereo|c0=c0|c1=c0"] if mono_level and _channels(path) == 1 else ["-ac", "2"]
    raw = subprocess.run([c.ffmpeg_bin(), "-nostdin", "-v", "error", *span, "-i", c.media(path), "-vn", *up,
                          "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def join_audio(parts: list, xfade_ms: float):
    """Music segments joined with an equal-power crossfade at each joint; the joint times."""
    import numpy as np

    n = int(SR * xfade_ms / 1000)
    out = parts[0]
    joints = []
    for p in parts[1:]:
        joints.append(len(out) / SR)
        if n and len(out) > n and len(p) > n:
            t = np.linspace(0, np.pi / 2, n)[:, None]
            mixed = out[-n:] * np.cos(t) + p[:n] * np.sin(t)
            out = np.concatenate([out[:-n], mixed, p[n:]])
        else:
            out = np.concatenate([out, p])
    return out, joints


def _frames(path: Path) -> int:
    out = subprocess.run([c.ffprobe_bin(), "-v", "error", "-count_frames", "-select_streams", "v:0",
                          "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", c.media(path)],
                         capture_output=True, text=True, check=True).stdout.strip().split(",")[0]
    return int(out)


def _duration(path: Path) -> float:
    out = subprocess.run([c.ffprobe_bin(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          c.media(path)], capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def _picture(spec: dict, tl: recut_plan.Timeline, rp, work: Path) -> tuple[Path, float]:
    """Each segment to an intermediate of exactly its timeline frames, then joined with cuts or dissolves."""
    fps, w, h = tl.fps, spec.get("width", 720), spec.get("height", 1280)
    files = []
    for i, (s, n) in enumerate(zip(spec["video"], tl.frames)):
        sp = s.get("speed", 1.0)
        f = work / f"v{i:02d}.mp4"
        # tpad clones the last frame when ffmpeg gives fewer; -frames:v drops the one too many it can give
        vf = (f"setpts=(PTS-STARTPTS)/{sp},fps={fps:.10g},scale={w}:{h}:flags=lanczos,setsar=1,"
              f"tpad=stop_mode=clone:stop={n}")
        c.run_ffmpeg(["-ss", f"{s['from']:.4f}", "-t", f"{s['to'] - s['from']:.4f}", "-i", c.media(rp(s["src"])),
                      "-an", "-vf", vf, "-frames:v", str(n), "-c:v", "libx264", "-crf", "12", "-preset", "fast",
                      "-pix_fmt", "yuv420p", str(f)])
        made = _frames(f)
        if made != n:
            raise c.ToolError(f"Segment {i + 1} came out {made} frames long instead of the {n} the check counted, "
                              "so the joints would drift. Nothing was saved. Run it again; if it repeats, check "
                              f"{c.name_of(s['src'])} plays to {s['to']:g} s.")
        files.append(f)
    inputs, chain, cur = [], "", "[0:v]"
    for f in files:
        inputs += ["-i", str(f)]
    for i in range(1, len(files)):
        d, offset = tl.fades_s[i - 1], tl.starts_s[i]
        if d:
            chain += f"{cur}[{i}:v]xfade=transition=fade:duration={d:.4f}:offset={offset:.4f}[x{i}];"
        else:
            chain += f"{cur}[{i}:v]concat=n=2:v=1:a=0[x{i}];"
        cur = f"[x{i}]"
    pic = work / "pic.mp4"
    if len(files) == 1:
        c.run_ffmpeg(["-i", str(files[0]), "-c", "copy", str(pic)])
    else:
        c.run_ffmpeg([*inputs, "-filter_complex", chain.rstrip(";"), "-map", cur, "-c:v", "libx264", "-crf", "12",
                      "-preset", "fast", "-pix_fmt", "yuv420p", str(pic)])
    return pic, _duration(pic)


def _sync_audio(spec: dict, tl: recut_plan.Timeline, rp):
    """Each segment keeps its own sound, read with a little extra on both sides and overlap-added with
    an equal-power crossfade centred on the joint, so the length and the lips stay exact and the bed
    has no dropout. `audio_tail` lets a segment's sound run on under the next picture segment (L-cut),
    `audio_head` lets it start under the end of the previous one (J-cut)."""
    import numpy as np

    xf = spec.get("sync_xfade_ms", 40) / 1000
    x = xf / 2
    nx = int(round(x * SR))
    pad = int(round(1.0 * SR))
    last = len(tl.lens_s) - 1
    end = tl.starts_s[-1] + tl.lens_s[-1]  # check refuses a dissolve in sync mode: the segments abut
    mix = np.zeros((int(round(end * SR)) + 2 * pad, 2), np.float32)
    for k, (r, ln) in enumerate(zip(tl.sync_reads, tl.lens_s)):
        p = load_audio(rp(r["src"]), r["start"], r["end"])
        n = int(round((ln + r["head"] + r["tail"]) * SR))
        p = p[:n] if len(p) >= n else np.concatenate([p, np.zeros((n - len(p), 2), np.float32)])
        nh = int(round(r["head"] * SR))
        if k > 0 and nh:
            p[:2 * nx] *= np.sin(np.linspace(0, np.pi / 2, 2 * nx))[:, None]
        if k < last:
            p[-2 * nx:] *= np.cos(np.linspace(0, np.pi / 2, 2 * nx))[:, None]
        i0 = int(round(tl.starts_s[k] * SR)) - nh + pad
        mix[i0:i0 + len(p)] += p
    return mix[pad: pad + int(round(end * SR))], tl.starts_s[1:]


def render(spec: dict, base: Path, out: Path) -> dict:
    """Render a checked `spec` (paths relative to `base`) to `out`. Returns the lengths and joints."""
    import numpy as np
    import soundfile as sf

    def rp(p: str) -> Path:  # the same reading of a src as check's (a Windows-written edit list too)
        p = recut_plan.norm_src(p)
        return Path(p) if Path(p).is_absolute() else base / p

    tl = recut_plan.timeline(spec)
    layers, problems = recut_plan.extra_audio(spec, tl.length_s)
    if problems:  # check refuses these; never mix a layer it did not pass
        raise c.ToolError(" ".join(problems))
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        pic, pic_len = _picture(spec, tl, rp, work)
        if spec.get("audio_mode") == "sync":
            music, ajoints = _sync_audio(spec, tl, rp)
        else:
            parts = [load_audio(rp(a["src"]), a["from"], a["to"]) for a in spec["audio"]]
            music, ajoints = join_audio(parts, spec.get("audio_xfade_ms", 40))
        music_len = len(music) / SR
        n_pic = int(round(pic_len * SR))
        if len(music) >= n_pic:
            music = music[:n_pic].copy()
            nf = int(SR * spec.get("audio_tail_fade_ms", 300) / 1000)
            if nf and music_len - pic_len > 0.02:
                music[-nf:] *= np.linspace(1, 0, nf)[:, None]
        else:
            music = np.concatenate([music, np.zeros((n_pic - len(music), 2), np.float32)])
        for layer_spec in layers:
            layer = load_audio(rp(layer_spec["src"]), mono_level=True)
            gain = 10 ** (layer_spec["gain_db"] / 20)
            i0 = int(round(layer_spec["at"] * SR))
            i1 = min(len(music), i0 + len(layer))
            music[i0:i1] += layer[: i1 - i0] * gain
        wav = work / "mix.wav"
        sf.write(str(wav), music, SR)
        made = work / "final.mp4"
        c.run_ffmpeg(["-i", str(pic), "-i", str(wav), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                      str(made)])
        if out.exists():  # never move onto an existing file
            raise c.ToolError(f"{out.name} already exists, and files are never overwritten. Nothing was "
                              "rendered. Leave out --out to get the next version.")
        shutil.move(str(made), str(out))
    return {"picture_len_s": round(pic_len, 3), "music_len_before_trim_s": round(music_len, 3),
            "video_joints_s": tl.joints_s, "music_joints_s": [round(j, 3) for j in ajoints],
            "segment_lens_s": [round(v, 3) for v in tl.lens_s], "segment_frames": tl.frames,
            "length_s": tl.length_s}


def _precheck(spec: dict) -> None:
    if spec.get("audio_mode") == "sync":
        if any(s.get("speed", 1.0) != 1.0 for s in spec["video"]):
            raise c.ToolStop("audio_mode \"sync\" does not support speed changes (the sound would drift from "
                             "the lips). Nothing was rendered. Remove the \"speed\" from the segments or leave "
                             "sync mode, and run it again. The run continues from the same place.")
    elif not spec.get("audio"):
        raise c.ToolStop("The edit list has no \"audio\" segments and is not in sync mode, so there is no "
                         "sound to put under the picture. Nothing was rendered. Add them, then run it again. "
                         "The run continues from the same place.")


@c.guarded
def main(argv: list[str] | None = None) -> int:
    p = c.parser("recut", "Render a checked edit list (picture, music or speech in sync).")
    p.add_argument("edit", help="the edit list JSON (03_wip/recut/<variant>_vNN.json)")
    p.add_argument("--teardown", required=True, help="the teardown JSON of the source (tm tool teardown)")
    p.add_argument("--transcript", default=None, help="the transcript JSON (tm tool transcribe)")
    a = p.parse_args(argv)
    run = c.open_run(a.run)
    if state.load(run).status == "done":  # as tm recut check: nothing recorded, nothing rendered
        raise c.ToolError("This run is done; its edit lists are no longer checked or rendered. Nothing was "
                          "rendered.")
    edit_path = c.resolve(run, a.edit)
    spec = c.read_json(run, a.edit, "edit list")
    teardown = c.read_json(run, a.teardown, "teardown")
    transcript = c.read_json(run, a.transcript, "transcript")
    try:
        cfg = config.load(run)
    except ValueError:
        cfg = None
    mode, approved = recut_plan.run_context(run)
    try:
        verdict = recut_plan.check(spec, teardown, transcript, cfg, mode=mode, approved=approved,
                                   base=run.path, edit_dir=edit_path.parent,
                                   material=state.load(run).material)
    except ValueError as exc:
        raise c.ToolError(str(exc)) from None
    name = recut_plan.record(run, edit_path, spec, verdict)["edit"]  # as tm recut check records it
    name = c.name_of(name) if Path(name).is_absolute() else name  # an edit list outside the run: its name
    if verdict.status != "ok":
        listed = "\n".join(f"- {t}" for t in verdict.problems)
        todo = ("Fix the edit list in a new version and run it again." if verdict.status == "refused" else
                "Once the budget is approved or the level allowed, run it again.")
        word = "was refused" if verdict.status == "refused" else "is waiting"
        message = (f"{name} {word}, so nothing was rendered:\n{listed}\n{todo} "
                   "The run continues from the same place.")
        print(json.dumps({"status": verdict.status, "message": c.scrub(message), "problems": verdict.problems},
                         ensure_ascii=False) if a.json else c.scrub(message))
        return 2
    _precheck(spec)
    out = c.output(run, a.out, "final", slug(spec["variant"]), "mp4")
    side = Path(str(out) + ".recut.json")
    if side.exists():
        raise c.ToolError(f"{side.name} already exists next to the output, and files are never overwritten. "
                          "Nothing was rendered. Leave out --out to get the next version, or pick another name. "
                          "The run continues from the same place.")
    result = render(spec, edit_path.parent, out)
    sidecar = {"spec": spec, "joints_s": result["video_joints_s"], "checked": verdict.to_json(), **result}
    c.write_json(side, sidecar)
    parent = c.parent_ref(run, edit_path)
    params = {"variant": spec["variant"], "level": verdict.level, "length_s": result["picture_len_s"],
              "joints_s": result["video_joints_s"]}
    c.record(run, out, "tm tool recut (ffmpeg)", parent, params=params, before_after=f"after (edit list: {parent})",
             request={"edit": parent, "teardown": c.parent_ref(run, a.teardown)}, response=sidecar)
    c.record(run, side, "tm tool recut (ffmpeg)", c.rel(run, out), params={"variant": spec["variant"]})
    return c.finish(a, {"tool": "recut", "outputs": [c.rel(run, out), c.rel(run, side)], **sidecar},
                    f"Re-cut saved to {c.rel(run, out)}: {result['picture_len_s']:g} s, joints at "
                    f"{', '.join(f'{j:g}' for j in result['video_joints_s']) or 'none'} s.")


if __name__ == "__main__":
    raise SystemExit(main())
