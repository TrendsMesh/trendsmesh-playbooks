"""R2: which funnel stage is fading, from the peak window against the latest one.

A metric "drops" when it falls by at least `diagnosis.drop` (0.15) from the peak to the latest
window, and otherwise "holds". A peak of zero never counts as a drop.

The rules run in this order and the first that matches names the stage:
  1. account    the ad's results-per-spend ratio (latest / peak) is within +-`drop` of the
                account's own ratio, and the account itself dropped (a flat account is never
                the cause);
  2. landing    CTR holds and conversion drops;
  3. fatigue    hook rate, middle rate and CTR all drop and frequency rises by at least
                `diagnosis.frequency_rise` (0.20)
                (checked before the single-stage rules: "everything drops" contains a hook
                drop, so after them it could never be reached);
  4. hook       hook rate drops;
  5. middle     hook holds and a middle step of the retention ladder drops (below);
  6. promise_cta  hook and middle hold and CTR drops;
  7. auction    only CPM rises (by at least `drop`).
Middle (PLAYBOOK v0.3 R2, amendment 2026-11-06): the middle is read from the conditional
retention steps p50/p25, p75/p50 and p95/p75 (`tm.ladder`), not from ThruPlay/p25. A step drops
when its latest rate is lower than the peak's by at least `diagnosis.middle_step_drop_pp`
(3) percentage points and a two-proportion test says the difference is not chance
(p below `MIDDLE_STEP_P`, 0.1). The middle fades when any of the three drops. "Hook holds"
keeps v1's hook rate (p25 / impressions) with `diagnosis.drop`. Unless both windows carry ladder
counts (a window stored by 0.2.x has none) the rule falls back to v1's rule: ThruPlay/p25 with `diagnosis.drop`.
Each of the three steps is tested at p < 0.1, so when nothing changed there is about a 27% chance
that one of them shows as dropped; Meta's counts are view actions rather than unique people, so the
p-values are optimistic. The 3 pp threshold limits both. A step whose reached count exceeds its
out-of count in either window is no data for the comparison (never a drop).
Nothing matching gives "unclear" (no creative change is chosen on no evidence).

Every other symptom that is present goes to `also_seen`, named by the stage it would point to.
`refresh` is false for landing, account, auction and unclear.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

from tm import changes, cli, config, ladder, manifest, state
from tm.r1 import Window
from tm.runfolder import ReadOnlyError, RunFolder

Stage = Literal["hook", "middle", "promise_cta", "landing", "account", "fatigue", "auction", "unclear"]
NO_REFRESH = ("landing", "account", "auction", "unclear")
MIDDLE_STEP_P = 0.1  # a middle step must drop with p below this, not only by the points


@dataclass
class Diagnosis:
    stage: str
    refresh: bool
    evidence: dict[str, tuple[float, float]] = field(default_factory=dict)  # name: (peak, latest)
    also_seen: list[str] = field(default_factory=list)
    account_check: dict[str, float] = field(default_factory=dict)  # ad_rate_ratio, account_ratio
    target_stage: str | None = None  # the stage the refresh targets (see changes.resolve)
    note: str = ""
    ladder: dict = field(default_factory=dict)  # {"peak": {step: rate}, "latest": {...}, "dropped": [steps]}
    structural: dict | None = None  # R2b's answer across uploads of the same video (tm structural)

    def to_json(self) -> dict:
        return {"stage": self.stage, "refresh": self.refresh,
                "evidence": {k: [v[0], v[1]] for k, v in self.evidence.items()},
                "also_seen": list(self.also_seen), "account_check": dict(self.account_check),
                "target_stage": self.target_stage, "note": self.note, "ladder": self.ladder,
                "structural": self.structural}

    @classmethod
    def from_json(cls, data: dict) -> "Diagnosis":
        return cls(stage=data["stage"], refresh=bool(data["refresh"]),
                   evidence={k: (v[0], v[1]) for k, v in data.get("evidence", {}).items()},
                   also_seen=list(data.get("also_seen", [])),
                   account_check=dict(data.get("account_check", {})),
                   target_stage=data.get("target_stage"), note=data.get("note", ""),
                   ladder=dict(data.get("ladder", {})),
                   structural=data.get("structural"))


_FIELDS = ("start", "stop", "spend", "results", "impressions", "p25", "thruplay", "clicks_est",
           "frequency", "cpm", "weeks", "plays", "p50", "p75", "p95", "p100", "avg_time_s")
_OPTIONAL = ("weeks", "plays", "p50", "p75", "p95", "p100", "avg_time_s")  # absent in 0.2.x windows


def window_to_json(w: Window) -> dict:
    out = {k: getattr(w, k) for k in _FIELDS}
    out["start"], out["stop"] = w.start.isoformat(), w.stop.isoformat()
    return out


def window_from_json(data: dict) -> Window:
    """The full window (every Window field), as `window_to_json` writes it."""
    if not isinstance(data, dict):
        raise ValueError("A window must be a JSON object.")
    missing = [k for k in _FIELDS if k not in data and k not in _OPTIONAL]
    if missing:
        raise ValueError(f"The window lacks: {', '.join(missing)}.")
    try:
        return Window(
            start=date.fromisoformat(str(data["start"])), stop=date.fromisoformat(str(data["stop"])),
            spend=float(data["spend"]), results=float(data["results"]),
            impressions=int(data["impressions"]), p25=int(data["p25"]), thruplay=int(data["thruplay"]),
            clicks_est=float(data["clicks_est"]), frequency=float(data["frequency"]),
            cpm=float(data["cpm"]), weeks=int(data.get("weeks", 1)),
            plays=int(data.get("plays", 0)), p50=int(data.get("p50", 0)),
            p75=int(data.get("p75", 0)), p95=int(data.get("p95", 0)),
            p100=int(data.get("p100", 0)), avg_time_s=float(data.get("avg_time_s", 0.0)))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"The window has a value that is not a number or date: {exc}") from None


def _fell(peak: float, latest: float, drop: float) -> bool:
    return peak > 0 and (peak - latest) / peak >= drop - 1e-12


def _rose(peak: float, latest: float, rise: float) -> bool:
    return peak > 0 and (latest - peak) / peak >= rise - 1e-12


def _rate(w: Window) -> float:
    return w.results / w.spend if w.spend > 0 else 0.0


_LADDER_MARKS = ("plays", "p50", "p75", "p95", "p100")


def _has_ladder(w: Window) -> bool:
    """Plays or any of p50..p100 above 0; p25 alone is in v1 windows too."""
    return any(getattr(w, k) > 0 for k in _LADDER_MARKS)


def _ladder_read(peak: Window, latest: Window, pp: float) -> dict:
    pk, lt = ladder.steps(peak), ladder.steps(latest)
    pc, lc = ladder.counts(peak), ladder.counts(latest)
    dropped = []
    for step in ladder.MIDDLE:
        if pk[step] is None or lt[step] is None:
            continue
        if any(reached > out_of for reached, out_of in (pc[step], lc[step])):
            continue  # Meta's counts are view actions: reached above out of is no data, not a drop
        p = ladder.two_proportion_p(*pc[step], *lc[step])
        if pk[step] - lt[step] >= pp / 100 - 1e-12 and p < MIDDLE_STEP_P:
            dropped.append(step)
    return {"peak": pk, "latest": lt, "dropped": dropped}


def diagnose(peak: Window, latest: Window, account_ratio: float, cfg: dict | None) -> Diagnosis:
    drop = float(config.value(cfg, "diagnosis.drop"))
    metrics = {"hook_rate": (peak.hook_rate, latest.hook_rate),
               "middle_rate": (peak.middle_rate, latest.middle_rate),
               "ctr": (peak.ctr, latest.ctr),
               "conversion": (peak.conversion, latest.conversion),
               "frequency": (peak.frequency, latest.frequency),
               "cpm": (peak.cpm, latest.cpm)}
    hook = _fell(*metrics["hook_rate"], drop)
    if _has_ladder(peak) and _has_ladder(latest):
        lad = _ladder_read(peak, latest, float(config.value(cfg, "diagnosis.middle_step_drop_pp")))
        middle = bool(lad["dropped"])
    else:  # a v1 window pair: ThruPlay/p25
        lad = {}
        middle = _fell(*metrics["middle_rate"], drop)
    ctr = _fell(*metrics["ctr"], drop)
    conv = _fell(*metrics["conversion"], drop)
    freq = _rose(*metrics["frequency"], float(config.value(cfg, "diagnosis.frequency_rise")))
    cpm = _rose(*metrics["cpm"], drop)

    ad_ratio = _rate(latest) / _rate(peak) if _rate(peak) > 0 else 1.0
    account = (account_ratio <= 1 - drop + 1e-12
               and abs(ad_ratio - account_ratio) <= drop * account_ratio + 1e-12)

    seen = {"hook": hook, "middle": middle, "promise_cta": ctr,
            "landing": conv and not ctr, "fatigue": freq, "auction": cpm}
    if account:
        stage = "account"
    elif not ctr and conv:
        stage = "landing"
    elif hook and middle and ctr and freq:
        stage = "fatigue"
    elif hook:
        stage = "hook"
    elif middle:
        stage = "middle"
    elif ctr:
        stage = "promise_cta"
    elif cpm:
        stage = "auction"
    else:
        stage = "unclear"
    # the symptoms of the other stages, whether or not their own rule could have fired
    others = [name for name in ("hook", "middle", "promise_cta", "landing", "fatigue", "auction")
              if seen[name] and name != stage]
    if stage == "account":
        others = [n for n in others if n != "auction"]
    return Diagnosis(stage=stage, refresh=stage not in NO_REFRESH, evidence=metrics, also_seen=others,
                     account_check={"ad_rate_ratio": ad_ratio, "account_ratio": account_ratio},
                     ladder=lad)


def retarget(s: state.RunState) -> None:
    """Set target_stage and note in the stored diagnosis from the stage, also_seen and the material."""
    d = s.diagnosis
    res = changes.resolve(d["stage"], d.get("also_seen", []), d.get("refresh", False), s.material)
    d["target_stage"], d["note"] = res.target, res.note


def record(run: RunFolder, d: Diagnosis) -> Path:
    """Save the diagnosis in run state and as 04_final/diagnosis_vNN.json (R2's evidence).

    Diagnosing again before G1a is decided replaces the earlier diagnosis (a new versioned file
    and manifest row; the old file stays). A finished run refuses it.
    """
    if state.load(run).status == "done":
        raise ValueError("This run is done; the diagnosis can no longer be changed.")
    res = changes.resolve(d.stage, d.also_seen, d.refresh, state.load(run).material)
    d.target_stage, d.note = res.target, res.note
    target = run.next_version("04_final", "diagnosis", "json")
    run.assert_writable(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(d.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest.record(run, f"04_final/{target.name}", "04_final", "tm diagnose")
    s = state.load(run)
    s.diagnosis = d.to_json()
    state.save(run, s)
    return target


def _window_arg(value: str, run: RunFolder | None = None) -> Window:
    text = value.strip()
    path = run.given(text) if run is not None and not text.startswith("{") else Path(text)
    raw = text if text.startswith("{") else path.read_text(encoding="utf-8")
    return window_from_json(json.loads(raw))


def run_config(run: RunFolder) -> dict | None:
    return config.load(run) if (run.path / config.FILE).is_file() else None


def _setup(p: argparse.ArgumentParser) -> None:
    p.add_argument("--run", required=True, help="the run folder")
    p.add_argument("--peak", required=True, help="the peak window: a JSON file or a JSON object")
    p.add_argument("--latest", required=True, help="the latest window: a JSON file or a JSON object")
    p.add_argument("--account-ratio", required=True, type=float,
                   help="the rest of the account's results per spend, latest / peak (R1)")
    p.add_argument("--json", action="store_true")


def _run(args: argparse.Namespace) -> int:
    try:
        run = RunFolder.open(Path(args.run))
        d = diagnose(_window_arg(args.peak, run), _window_arg(args.latest, run), args.account_ratio, run_config(run))
        target = record(run, d)
    except (OSError, ValueError, ReadOnlyError) as exc:
        return cli.fail(args, str(exc))
    text = (f"Wrote 04_final/{target.name}: {d.stage} is fading"
            + ("" if d.refresh else " (do not refresh the creative)")
            + (f"; also seen: {', '.join(d.also_seen)}" if d.also_seen else "") + ".")
    cli.emit(args, {"status": "done", "file": f"04_final/{target.name}", **d.to_json()}, text)
    return 0


cli.register("diagnose", _setup, _run)
