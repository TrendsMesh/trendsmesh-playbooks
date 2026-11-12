"""The recorded voiceover against the plan (#88 point 4): line times, the take's cuts and the pace, free.

    tm organic vo-sync --run R --words 03_wip/<take>.words.json [--spec 03_wip/<item>_vNN.json] [--offset S] [--json]

F1 records an ElevenLabs voiceover with its word times (`tm tool elevenlabs tts --timestamps` writes
`<stem>.words.json`) before any take is paid for. Real voices run 2.5 to 3.8 words a second, so the lines rarely land
on the pack's `script.lines[].at`: in the owner's run the pack planned 0–3.5 / 3.5–7.5 / 7.5–13.5 s and the voice said
0–3.16 / 3.28–6.72 / 6.76–11.84 s, while the take's prompt still cut at 3.5 and 7.5 s.

- The said lines (speaker not `none`, in order) are matched to the recorded words by their word counts (both split on
  spaces, as `organic_audio.words_from_alignment` splits the alignment): line k's times are its first word's start
  and its last word's end. Counts that do not add up mean the take was not recorded from the pack's lines: nothing is
  compared, and the answer says so.
- A line whose recorded start or end is more than `TOLERANCE_S` (about 0.3 s, the owner's figure) from its planned
  `at` gets a proposed `at`, its recorded [start, end].
- `--spec`: the take's timed shot list, its brackets `[a to b seconds]` (MiniMax H3, Seedance) or `[mm:ss-mm:ss]`
  (Veo) read from `input.prompt`; `--offset` is the take's start in the video (a later section's take). Each cut (a
  bracket's start after 0) is paired with the line that starts nearest to it, within `PAIR_S`; a cut more than
  `TOLERANCE_S` from its line's recorded start gets a proposed time, the middle of the pause before that line, so the
  line starts over its own scene. A cut no line starts near (a cut inside a line) is left alone.
- Pace: each line's and the whole voiceover's words a second (`organic_audio.pace`), against `qa.wps_min`: the pace
  check the take QA holds a video model's speech to, now on the ElevenLabs voice too.
- A voice whose last word ends after the pack's `script.seconds` is longer than the takes: re-plan the pack (E2).

It reads only, writes nothing and spends nothing. `take_gap` is the same comparison for the paid take's guard
(`organic_specs.guard`): a pack read by an ElevenLabs narrator over one take (no sections), whose spec cuts away from
the latest recorded voiceover, is refused before anything is paid, with the proposed cuts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tm import config, i18n, organic_audio, organic_config
from tm.runfolder import RunFolder

TOLERANCE_S = 0.3   # "more than about 0.3 s" (#88)
PAIR_S = 1.5        # a prompt cut belongs to the line that starts within this of it (planned or recorded)
_BRACKET = re.compile(r"\[\s*(\d+(?:\.\d+)?)\s*(?:to|-|–|—)\s*(\d+(?:\.\d+)?)\s*(?:s|sec|secs|seconds?)?\s*\]", re.I)
_CLOCK = re.compile(r"\[\s*(\d{1,2}):(\d{2}(?:\.\d+)?)\s*[-–—]\s*(\d{1,2}):(\d{2}(?:\.\d+)?)\s*\]")


def said_lines(pack: dict) -> list[dict]:
    return [line for line in pack["script"]["lines"] if line.get("speaker") != "none"]


def brackets(prompt: str) -> list[tuple[float, float]]:
    """The timed shot list's brackets, in seconds, in time order."""
    found = [(float(a), float(b)) for a, b in _BRACKET.findall(prompt or "")]
    found += [(int(m1) * 60 + float(s1), int(m2) * 60 + float(s2)) for m1, s1, m2, s2 in _CLOCK.findall(prompt or "")]
    return sorted(found)


def line_times(lines: list[dict], words: list[dict]) -> list[tuple[float, float, int]] | None:
    """(start, end, words) of each line from the recorded words, or None when the counts do not add up."""
    counts = [len(str(line["text"]).split()) for line in lines]
    if not lines or sum(counts) != len(words) or 0 in counts:
        return None
    out, k = [], 0
    for n in counts:
        out.append((float(words[k]["start"]), float(words[k + n - 1]["end"]), n))
        k += n
    return out


def compare(pack: dict, words: list[dict], cfg: dict, prompt: str | None = None, offset: float = 0.0) -> dict:
    """The comparison (see the module docstring) -> {matched, lines, cuts, slow, longer, in_sync, proposed}."""
    lines = said_lines(pack)
    times = line_times(lines, words)
    if times is None:
        return {"matched": False, "said_words": sum(len(str(x["text"]).split()) for x in lines),
                "recorded_words": len(words), "in_sync": False}
    least = config.get(cfg, "qa.wps_min") if cfg else None
    least = least if least is not None else organic_config.DEFAULTS["qa"]["wps_min"]
    rows, slow = [], []
    for line, (start, end, n) in zip(lines, times):
        planned = [float(v) for v in line["at"]]
        off = max(abs(start - planned[0]), abs(end - planned[1]))
        wps = round(n / (end - start), 2) if end > start else 0.0
        row = {"n": line["n"], "planned": planned, "recorded": [round(start, 2), round(end, 2)], "words": n,
               "wps": wps, "off_s": round(off, 2), "moved": off > TOLERANCE_S}
        rows.append(row)
        if least is not None and 0 < wps < least:
            slow.append({"n": line["n"], "wps": wps})
    whole = round(organic_audio.pace(words), 2)
    if least is not None and 0 < whole < least:
        slow.append({"n": None, "wps": whole})
    cuts = []
    for a, _ in brackets(prompt or ""):
        if a <= 0:
            continue
        at = a + offset
        best = None
        for i, (row, (start, _end, _n)) in enumerate(zip(rows, times)):
            if i == 0:
                continue
            near = min(abs(at - row["planned"][0]), abs(at - start))
            if near <= PAIR_S and (best is None or near < best[0]):
                best = (near, i)
        if best is None:
            continue
        i = best[1]
        start, prev_end = times[i][0], times[i - 1][1]
        proposed = round((prev_end + start) / 2, 2)
        off = abs(at - start)
        cuts.append({"prompt_s": round(a, 2), "line": rows[i]["n"], "line_starts": round(start, 2),
                     "off_s": round(off, 2), "moved": off > TOLERANCE_S, "proposed_s": round(proposed - offset, 2)})
    last_end = times[-1][1]
    longer = last_end > float(pack["script"]["seconds"]) + 1e-9
    in_sync = not any(r["moved"] for r in rows) and not any(c["moved"] for c in cuts) and not longer
    return {"matched": True, "lines": rows, "cuts": cuts, "slow": slow, "pace": whole, "voice_s": round(last_end, 2),
            "seconds": pack["script"]["seconds"], "longer": longer, "in_sync": in_sync,
            "proposed": {"at": {str(r["n"]): r["recorded"] for r in rows if r["moved"]},
                         "cuts": [c["proposed_s"] for c in cuts if c["moved"]]}}


def words_of(path: Path) -> list[dict]:
    try:
        words = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(i18n.t("vo_sync.bad_words", file=path.name, why=str(exc))) from None
    if not (isinstance(words, list) and all(isinstance(w, dict) and {"start", "end"} <= set(w) for w in words)):
        raise ValueError(i18n.t("vo_sync.bad_words", file=path.name, why="not a list of {word, start, end}"))
    return words


def summary(res: dict, words_rel: str) -> str:
    """The answer in words, for the agent and the user."""
    if not res["matched"]:
        return i18n.t("vo_sync.unmatched", file=words_rel, recorded=res["recorded_words"], said=res["said_words"])
    parts = []
    moved = [r for r in res["lines"] if r["moved"]]
    if moved:
        parts.append(i18n.t("vo_sync.lines_moved", lines="; ".join(
            f"{r['n']}: {r['planned'][0]:g}–{r['planned'][1]:g} s → {r['recorded'][0]:g}–{r['recorded'][1]:g} s"
            for r in moved)))
    cuts = [c for c in res["cuts"] if c["moved"]]
    if cuts:
        parts.append(i18n.t("vo_sync.cuts_moved", cuts="; ".join(
            f"{c['prompt_s']:g} s → {c['proposed_s']:g} s (line {c['line']} starts at {c['line_starts']:g} s)"
            for c in cuts)))
    if res["longer"]:
        parts.append(i18n.t("vo_sync.longer", voice=f"{res['voice_s']:g}", seconds=f"{res['seconds']:g}"))
    if res["slow"]:
        parts.append(i18n.t("vo_sync.slow", lines="; ".join(
            (f"line {x['n']}" if x["n"] is not None else "the whole voiceover") + f" {x['wps']:g}" for x in res["slow"])))
    if not parts:
        return i18n.t("vo_sync.in_sync", pace=f"{res['pace']:g}")
    return " ".join(parts) + " " + i18n.t("vo_sync.todo")


def _cfg(run: RunFolder) -> dict:
    try:
        return config.load(run)
    except ValueError:
        return {}


def latest_words(run: RunFolder) -> Path | None:
    """The latest recorded word times in 03_wip (`<stem>.words.json`), or None."""
    found = [p for p in (run.path / "03_wip").rglob("*.words.json") if p.is_file()]
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


def take_gap(run: RunFolder, pack: dict | None, spec: dict, stem: str) -> str | None:
    """The paid take's guard (`organic_specs.guard`): why the take may not run yet, or None. Only for a pack read by
    an ElevenLabs narrator over a single video take with no sections, whose recorded voiceover matches the pack's
    lines, and whose spec's prompt has a timed shot list: a cut more than `TOLERANCE_S` from the line it opens is
    refused with the proposed cuts (free, before anything is paid)."""
    if not pack or pack.get("speech", {}).get("route") != "elevenlabs_narrator" or pack.get("sections"):
        return None
    video = [item for st in pack.get("stages") or [] if st.get("stage") == "video" for item in st.get("items") or []
             if item.get("model")]
    if len(video) != 1 or Path(str(video[0].get("name"))).stem.lower() != stem.lower():
        return None
    prompt = (spec.get("input") or {}).get("prompt")
    words_path = latest_words(run)
    if not isinstance(prompt, str) or not brackets(prompt) or words_path is None:
        return None
    try:
        words = words_of(words_path)
        res = compare(pack, words, _cfg(run), prompt)
    except (ValueError, KeyError, TypeError):
        return None
    cuts = [c for c in res.get("cuts") or [] if c["moved"]] if res["matched"] else []
    if not cuts:
        return None
    rel = words_path.relative_to(run.path).as_posix()
    return i18n.t("vo_sync.take_refused", words=rel, cuts="; ".join(
        f"{c['prompt_s']:g} s → {c['proposed_s']:g} s (line {c['line']} starts at {c['line_starts']:g} s)" for c in cuts))


def run_cli(args) -> int:
    """`tm organic vo-sync`."""
    from tm import cli, organic_pack

    run = RunFolder.open(Path(args.run))
    pack = organic_pack.checked_pack(run)
    if pack is None:
        raise ValueError(i18n.t("vo_sync.no_pack"))
    words_path = run.given(args.words)
    words = words_of(words_path)
    prompt = None
    if args.spec:
        spec_path = run.given(args.spec)
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise ValueError(i18n.t("vo_sync.bad_spec", file=spec_path.name, why=str(exc))) from None
        prompt = (spec.get("input") or {}).get("prompt") if isinstance(spec, dict) else None
        if not isinstance(prompt, str) or not brackets(prompt):
            raise ValueError(i18n.t("vo_sync.no_brackets", file=spec_path.name))
    res = compare(pack, words, _cfg(run), prompt, args.offset)
    try:
        rel = words_path.resolve().relative_to(run.path.resolve()).as_posix()
    except ValueError:
        rel = words_path.name
    text = summary(res, rel)
    cli.emit(args, {"status": "done", "words": rel, **res, "message": text}, text)
    return 0
