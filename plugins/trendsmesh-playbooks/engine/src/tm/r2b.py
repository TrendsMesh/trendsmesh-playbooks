"""R2b: is the middle fading in the file itself, across every ad that uses the same video?

R2 reads one ad's own history. When the same video file runs in several ads (uploads), the
retention ladder (`tm.ladder`) of each upload says whether the same step is weakest everywhere.
If it is, the weak part belongs to the file, not to an audience or a campaign, and it is
reported as structural: the segment of the video where viewers leave, in seconds.

Each upload is read over its whole history (all its rows). An upload with fewer than `min_plays`
plays (1,000) is skipped, not counted. The weakest step is the lowest rate among `ladder.MIDDLE`
(a step with no data never wins; a tie goes to the earlier step). The file is structural when at
least two uploads are counted and all of them have the same weakest step. This is reported next
to the diagnosis; it never changes its stage or `refresh` (PLAYBOOK v0.3 RC3).
Note: the p95/p75 segment covers 20% of the length, against 25% for the other steps.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

from tm import cli, ladder, manifest, meta_rows, state
from tm.meta_rows import Row, normalise
from tm.r1 import aggregate
from tm.runfolder import ReadOnlyError, RunFolder

MIN_PLAYS = 1000
MIN_UPLOADS = 2


@dataclass
class Structural:
    structural: bool
    step: str | None = None
    segment_s: tuple[float, float] | None = None
    uploads: list[dict] = field(default_factory=list)  # {ad_id, plays, ladder, weakest}
    skipped: list[dict] = field(default_factory=list)  # {ad_id, plays, why}

    def to_json(self) -> dict:
        return {"structural": self.structural, "step": self.step,
                "segment_s": list(self.segment_s) if self.segment_s else None,
                "uploads": list(self.uploads), "skipped": list(self.skipped)}


def _weakest(rates: dict[str, float | None]) -> str | None:
    best: str | None = None
    for step in ladder.MIDDLE:  # in order, so a tie keeps the earlier step
        v = rates[step]
        if v is not None and (best is None or v < rates[best]):  # type: ignore[operator]
            best = step
    return best


def check(uploads: dict[str, list[Row]], length_s: float, min_plays: int = MIN_PLAYS) -> Structural:
    counted: list[dict] = []
    skipped: list[dict] = []
    for ad_id, rows in uploads.items():
        if not rows:
            skipped.append({"ad_id": ad_id, "plays": 0, "why": f"fewer than {min_plays:,} plays"})
            continue
        w = aggregate(rows, min(r.start for r in rows), max(r.stop for r in rows))
        if w.plays <= 0:
            skipped.append({"ad_id": ad_id, "plays": 0, "why": "no video play data"})
            continue
        if w.plays < min_plays:
            skipped.append({"ad_id": ad_id, "plays": w.plays, "why": f"fewer than {min_plays:,} plays"})
            continue
        rates = ladder.steps(w)
        counted.append({"ad_id": ad_id, "plays": w.plays, "ladder": rates, "weakest": _weakest(rates)})
    weakest = {u["weakest"] for u in counted}
    if len(counted) >= MIN_UPLOADS and len(weakest) == 1 and None not in weakest:
        step = weakest.pop()
        lo, hi = ladder.SEGMENT[step]
        return Structural(True, step, (round(lo * length_s, 2), round(hi * length_s, 2)),
                          counted, skipped)
    return Structural(False, None, None, counted, skipped)


def uploads_from_json(data: object) -> dict[str, list[Row]]:
    """{ad_id: Meta rows} as the skill passes it: each upload's rows as a list, or as the Meta answer
    they came in (`meta_rows.answer_rows`). The whole Meta answer is not an uploads file (its keys
    are not ad ids), and an upload with rows none of which can be read is an error, not "too few
    plays"."""
    if meta_rows.answer_rows(data) is not None:
        raise ValueError("The uploads file is a Meta answer, not a map of uploads: write one JSON object of ad id "
                         "to that ad's rows, for each ad that runs the same video (flow.md, A1a).")
    if not isinstance(data, dict):
        raise ValueError("The uploads file must be a JSON object of ad id to a list of Meta rows.")
    out: dict[str, list[Row]] = {}
    for k, v in data.items():
        rows = v if isinstance(v, list) else meta_rows.answer_rows(v)
        if rows is None:
            raise ValueError(f"The rows of upload {str(k)[:40]!r} are not a list of Meta rows or a Meta answer: "
                             "the uploads file must be a JSON object of ad id to a list of Meta rows.")
        normed = normalise(rows)
        if rows and not normed:
            raise ValueError(f"No row of upload {str(k)[:40]!r} can be read (none has a date_start or date_stop); "
                             "copy the rows unchanged from the saved Meta answer.")
        out[str(k)] = normed
    return out


def record(run: RunFolder, s: Structural) -> Path:
    """Add `structural` to the stored diagnosis and write 04_final/structural_vNN.json.

    Only the `structural` key changes: the stage, refresh and target stay as R2 left them.
    """
    st = state.load(run)
    if st.status == "done":
        raise ValueError("This run is done; the diagnosis can no longer be changed.")
    target = run.next_version("04_final", "structural", "json")
    run.assert_writable(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(s.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest.record(run, f"04_final/{target.name}", "04_final", "tm structural")
    st = state.load(run)
    st.diagnosis = {**st.diagnosis, "structural": s.to_json()}
    state.save(run, st)
    return target


def _setup(p: argparse.ArgumentParser) -> None:
    p.add_argument("--run", required=True, help="the run folder")
    p.add_argument("--uploads", required=True,
                   help="a JSON file (or object) of ad id to the Meta rows of that upload")
    p.add_argument("--length-s", required=True, type=float, help="the video's length in seconds")
    p.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        if not state.load(run).diagnosis:
            cli.emit(args, {"status": "stop", "message": "no diagnosis yet"},
                     "There is no diagnosis in this run yet, so nothing was checked. Run the "
                     "diagnosis first (tm diagnose), then run this again. The run continues from "
                     "the same place.")
            return 2
        if not args.length_s > 0:
            raise ValueError("The video length must be more than 0 seconds.")
        s = check(uploads_from_json(cli.json_arg(args.uploads, run)), args.length_s)
        target = record(run, s)
    except (OSError, ValueError, ReadOnlyError) as exc:
        return cli.fail(args, str(exc))
    if s.structural:
        text = (f"Wrote 04_final/{target.name}: the file itself is weak at {s.step}, "
                f"{s.segment_s[0]} to {s.segment_s[1]} s of the video, in {len(s.uploads)} uploads.")
    else:
        text = (f"Wrote 04_final/{target.name}: the weak step is not shared across uploads "
                f"({len(s.uploads)} counted, {len(s.skipped)} skipped).")
    cli.emit(args, {"status": "done", "file": f"04_final/{target.name}", **s.to_json()}, text)
    return 0


cli.register("structural", _setup, _run)
