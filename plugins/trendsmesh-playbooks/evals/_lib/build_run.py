#!/usr/bin/env python3
"""Builds a case's workspace: a run folder made by the engine itself, advanced to the step the
case starts at. Nothing here talks to Meta or TrendsMesh.

    build_run.py <scenario> <workspace>        (env: TM_PY, TM_PLUGIN_ROOT, TM_PLUGIN_DATA)

Scenarios (every one of them: a run `2026-11-05_ad`, Hands-off unless said, answers for a Polish account):
  at_a1          the creative brief only, run at A1 (fetch the fading winners)
  at_a2_hook     ranking, diagnosis (hook) and check-in done, run at A2 (no video in the brand folder)
  at_d2_no_budget  brief + AI video, Check every step, no AI budget; every step before D2 done, run at D2
  plans_offer    no run; TrendsMesh's public plans answer with the Agent plan's first month free
                 (./.plans.json, which ./tm.sh hands to `tm offer`)
  at_a5_hook     the creative brief only, Check every step; ranking, diagnosis (hook) and every step
                 before A5 done, run at A5 (the trends), with nothing recorded about TrendsMesh yet

Re-cut scenarios (handoff v03 HANDOFF.md 9b and 9b-2: decisions on the engine's recorded data, no
media; the original files are placeholders, the teardown, transcript and segment map JSON are in the run):
  at_a1a_middle_ladder  brief + edited video, Check every step; ranking made from rows with the
                 retention ladder, where the hook holds and p75/p50 drops 6 points (RC4); run at A1a
  at_a1a_ad3_structural  brief + edited video, Hands-off with diagnosis.structural_recut false and
                 recut.max_level 2; ranking from Ad 3-shaped rows (the hook fades, the ladder's steps
                 hold: RC1); run at A1a. The account's Meta answers (mocked per case) hold the same
                 file in 4 ads (RC2, RC3)
  at_a1a_ad3_structural_ask  the same at Check every step (RC19)
  at_cr4_ad3     edited video, Check every step, Ad 3 (text cards, music only, two continuous shots):
                 hook diagnosis + the structural weakness taken at G1a (flow R), teardown, segment
                 map, middle diagnosis, a saved method-E music take of 14.55 s; G3r chose R1-15s
                 (L0), R7-6s (L1) and R4-newshot (L4); run at CR4 (edit lists)
  at_cr4_ad2     edited video, Check every step, ad_2 (talking head, word captions): middle
                 diagnosis, teardown and transcript, segment map; G3r chose U-J1 (sentence and pause
                 cuts) and U-coldopen (the strongest line first); run at CR4
  at_cr3_exampletravel  edited video, Check every step, ExampleTravel (voiceover, captions, music): middle
                 diagnosis, teardown and transcript, segment map, causes (CR2) written; run at CR3
                 (variants), G3r not asked yet
  at_e1_shorter  edited video + live test, Check every step, Ad 3's file with a middle diagnosis;
                 the 15 s cut R1-15s checked and accepted (G5r); run at E1 (test design)

Trend research scenarios (playbook 04, `runs/04-trend-research/2026-11-04_beauty`, "beauty, US",
English): the beauty dry run, anonymised (gen_mocks.py --pb04), built with the engine's own
commands and no MCP; the saved answers are written as the collector writes them. Outputs the category
report and the paid view unless said:
  tr_at_b3       Check every step; searches saved, the map built, no review yet; run at B3
  tr_at_d2       Check every step; the dry run's review, the hooks path, growth, backtests and the evidence
                 dumps done; run at D2 (the Ad Library)
  tr_at_d3       the same, with the Ad Library not read (Meta not connected: `checked: false`, the
                 hooks' not_checkable rows) and checked; run at D3 (the picks). Not the dry run's summary: it has
                 the eyelash trend crowded in paid, a reason the review may move it out of the picks,
                 and the case is about the eyelash pick's card
  tr_at_e2       Hands-off; the dry run's picks (with a score table) checked and the page built; run at G3
                 (decided by rule: the agent decides it)
  tr_weekly_at_d1  run 1 (29 Oct, report + weekly digest, Hands-off) done, its page published as
                 art_mock_1; run 2 (4 Nov) after it (`--after`, `--from-previous`: Hands-off) with
                 everything before the digest done (ruling F11); run at F2

Creative brief scenarios (playbook 02, `runs/02-creative-brief/2026-11-07_nightschool`, the Night School
e-book, Canada, English, the account spends PLN): the LD dry run, anonymised (gen_mocks.py
--pb02), built with the engine's own commands; Check every step, all four outputs unless said:
  cb_at_a1       the run made, the landing page in 00_raw; run at A1 (product and intake card)
  cb_at_b1       the intake done (Meta's A1 reads saved, brand profile, config); run at B1
  cb_at_b2       the persona done (hypothesis, then the age x gender and placement reads, the pick)
  cb_at_b3_guess the voice checked (the dry run's archive answers and Goodreads texts, its themes); run at B3,
                 nothing recorded about TrendsMesh yet
  cb_at_c1       TrendsMesh evidence, the dry run's searches, cards and video pages, the shortlist; the scores
                 and the saturation checked; run at C1
  cb_at_c1_page_built  the same, with the dry run's brief (no animatics yet) evidenced, checked at the concepts
                 stage and the page v01 built, not published
  cb_at_c1_no_artifacts  the same for a review-pack run (outputs review_pack and page)
  cb_seed_expired  one full seed/1 row in library/seeds.jsonl (valid until 2026-10-30) and a run
                 started from it (--seed), driven to B3

Organic video scenarios (playbook 03, `runs/03-organic-ai-video/2026-11-06_exampleedu`, the Polish parenting
channel ExampleEdu): the ExampleEdu walkthrough, anonymised (gen_mocks.py --pb03), built with the engine's own
commands (the walkthrough's 17 searches, a shortlist, the cards and video pages of its top 12, made-up proposals checked);
Check every step and Polish pages unless said. A production run is started by `tm organic start` from the
proposals page's decisions and renamed `2026-11-07_exampleedu-m5`; its price file is dated the fixture's own day:
  ov_at_a1       a new workspace: no run (the agent makes it at A0)
  ov_at_c2_published  the page v01 built, published as art_mock_3 and awaited; at the proposals check-in
  ov_at_c2_no_artifacts  the stack without artifacts tools; the page v01 built locally; run at C2
  ov_no_replicate  English pages, the stack without Replicate and artifacts tools; run at C1
  ov_week_at_i2  a week run (Just the big calls, $5 a week): a made-up week plan with the plugin blocks, dated the
                 coming week, the reserve r2 priced $3.26, checked, its page built, published as art_mock_5 and
                 awaited; run at I2
  ov_at_e3_script  the ChatGPT age-limit idea (m5) as a script to film, Check every step: a made-up English script
                 written at D1; run at E3
  ov_at_e2_m5    m5 as an AI video, Hands-off: D1 (stack, recipe checked), taste by rule, E1 (today's prices);
                 the pack v02 written (its take sized to 13 s, $1.30 in all), not checked; run at E2
  ov_at_f2_failed_take  the same, the pack approved ($5), the host image made ($0.26) and picked by rule, the
                 13 s take made ($1.04) with its QA (match 0.72, 2.4 words a second), transcript and contact
                 sheet; run at F2
  ov_at_g2_kit   the same with a take that passes, picked by rule, and G1's final, upload copy and cover
                 (`tm.tools.deliver` with the host's ffmpeg on a 2 s test-pattern clip), then the chat English
                 (config page_lang en: the brief's "English chat"; the pack stays Polish); run at G2
A Replicate record is written as the guard writes it, its manifest rows marked as the fixture's (never "Replicate
run record", which the cases' graders look for); the spend through `tm budget spend`.

Steps the fixture finishes past A5 and A7 are a TrendsMesh run: a saved trend answer and a checked
change register, as the engine asks.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen_mocks  # noqa: E402  (the organic cases' shared shapes: OV_ALL, the db_list text)
import meta_data as m  # noqa: E402

PY = os.environ.get("TM_PY", sys.executable)
ROOT = os.environ["TM_PLUGIN_ROOT"]
RUN_NAME = "2026-11-05_ad"  # the engine names a run after the real date; the case renames it
RECUT_FIX = Path(ROOT) / "engine" / "tests" / "fixtures" / "recut"  # Ad 3 and ad_2 (engine tests)
LIB_FIX = HERE / "fixtures"                                          # ExampleTravel (these evals)

ANSWERS = {
    "account": {"id": m.ACCOUNT_ID, "market": "PL", "language": "Polish"},
    "product": {"name": "Example ebook", "landing_url": "https://example.com/ebook"},
    "brand": {"assets_dir": "brand", "rules": "calm tone", "compliance": "no health claims"},
    "intake": {"voice_rights_confirmed": True},
    "level": "hands_off",
}


def tm(ws: Path, *args: str, ok=(0,)) -> dict:
    env = {**os.environ, "PYTHONPATH": f"{ROOT}/engine/src", "PYTHONDONTWRITEBYTECODE": "1",
           "TM_WORKSPACE": str(ws)}
    p = subprocess.run([PY, "-m", "tm", *args, "--json"], env=env, cwd=ws, capture_output=True,
                       text=True, encoding="utf-8")
    if p.returncode not in ok:
        raise SystemExit(f"tm {' '.join(args)} -> {p.returncode}\n{p.stdout}\n{p.stderr}")
    return json.loads(p.stdout.strip().splitlines()[-1])


def new_run(ws: Path, outputs: list[str], budget: dict | None = None, level: str = "hands_off",
            extra: dict | None = None) -> Path:
    (ws / "brand").mkdir(parents=True, exist_ok=True)
    made = Path(tm(ws, "run", "new", "--name", "ad")["path"])
    run = made.with_name(RUN_NAME)
    if made != run:
        made.rename(run)
    answers = json.loads(json.dumps(ANSWERS))
    answers["brand"]["assets_dir"] = str(ws / "brand")
    answers["outputs"] = outputs
    answers["level"] = level
    if budget:
        answers["budget"] = budget
    answers.update(extra or {})
    f = ws / ".answers.json"
    f.write_text(json.dumps(answers), encoding="utf-8")
    tm(ws, "config", "write", "--run", str(run), "--answers", str(f))
    f.unlink()
    return run


def place(ws: Path, run: Path, rel: str, data, source: str, stage: str | None = None) -> Path:
    """Write a file into the run (JSON, text or bytes) and record it in the manifest."""
    target = run / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        target.write_bytes(data)
    elif isinstance(data, str):
        target.write_text(data, encoding="utf-8")
    else:
        target.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    tm(ws, "record", "--run", str(run), "--file", rel, "--stage", stage or rel.split("/")[0],
       "--source", source)
    return target


def write_ranking(ws: Path, run: Path, scn: str) -> dict:
    """Seed 01_base the way A1 leaves it (weekly files, daily rows) and run the engine's R1."""
    a = m.answers(scn)
    base = run / "01_base"
    files = {"meta_weekly_ads_p01.json": a["ad_7"], "meta_weekly_account.json": a["account_7"],
             f"{m.AD_A}_meta_daily.json": m.mcp_answer([r for r in m.rows_of(a["ad_1"]) if r["id"] == m.AD_A])}
    for name, data in files.items():
        (base / name).write_text(json.dumps(data), encoding="utf-8")
        tm(ws, "record", "--run", str(run), "--file", f"01_base/{name}", "--stage", "01_base",
           "--source", "Meta Ads MCP ads_get_ad_entities (eval fixture)")
    tm(ws, "r1", "--run", str(run), "--ads", str(base / "meta_weekly_ads_p01.json"), "--account",
       str(base / "meta_weekly_account.json"), "--today", m.TODAY.isoformat())
    ranking = json.loads((base / "winner_ranking_v01.json").read_text(encoding="utf-8"))
    return next(c for c in ranking["candidates"] if c["ad_id"] == m.AD_A)


def diagnose(ws: Path, run: Path, cand: dict) -> None:
    tm(ws, "diagnose", "--run", str(run), "--peak", json.dumps(cand["peak"]), "--latest",
       json.dumps(cand["latest"]), "--account-ratio", str(cand["account_ratio"]))


def structural(ws: Path, run: Path, scn: str) -> None:
    """R2b as A1a leaves it: the whole-life rows of every ad that runs the file, then `tm structural`."""
    life = {r["id"]: [r] for r in m.rows_of(m.lifetime(scn))}
    uploads = {ad: life[ad] for ad in m.same_file(scn)}
    f = place(ws, run, "03_wip/retention/uploads_v01.json", uploads,
              "copied from 01_base: Meta Ads MCP ads_get_ad_entities, whole life (eval fixture)")
    tm(ws, "structural", "--run", str(run), "--uploads", str(f), "--length-s", str(m.LENGTHS[scn]))


def drive(ws: Path, run: Path, stop_at: str | None, scn: str | None = None, ai_stop: bool = False,
          hooks: dict | None = None, notes: dict | None = None) -> dict:
    """Answer the engine as a user would, up to `stop_at` (a step, as work) or any stop.

    `hooks` maps a step to a function(ws, run) that does the step's work before `tm done` (for A1a:
    after the ranking and the diagnosis, before G1a); `notes` maps a check-in to its note."""
    choice = {"G1": m.AD_A, "G1a": "refresh", "G11": "keep_paused"}
    hooks, notes = hooks or {}, notes or {}
    cand = None
    for _ in range(300):
        n = tm(ws, "next", "--run", str(run), ok=(0, 2))
        if n["action"] == "work":
            if n["step"] == "A1a" and scn and cand is None:
                cand = write_ranking(ws, run, scn)
                if stop_at == "A1a":
                    return n
                diagnose(ws, run, cand)
                if "A1a" in hooks:
                    hooks["A1a"](ws, run)
                continue
            if n["step"] == stop_at:
                return n
            if n["step"] == "A5":  # what the run rests on, and a saved trend (issue #9)
                (run / "02_research" / "trend_fixture.json").write_text('{"id": "fixture"}', encoding="utf-8")
                tm(ws, "evidence", "trendsmesh", "--run", str(run), "--why", "set by the eval fixture")
            if n["step"] == "A7":  # a checked change register
                reg = run / "04_final" / "change_register_v01.json"
                reg.write_text(json.dumps({"items": [{"change": "new opening card", "basis": "proof",
                                                      "sources": ["02_research/trend_fixture.json"]}]}),
                               encoding="utf-8")
                tm(ws, "register", "check", "--run", str(run), "--file", str(reg))
            if n["step"] in hooks and n["step"] != "A1a":
                hooks[n["step"]](ws, run)
            tm(ws, "done", n["step"], "--run", str(run))
        elif n["action"] in ("ask", "auto"):
            for cid in n["checkin"]["ids"]:
                extra = ["--by", "rule"] if n["action"] == "auto" else []
                note = notes.get(cid) or ("set by the eval fixture" if n["action"] == "auto" else None)
                extra += ["--note", note] if note else []
                tm(ws, "decide", cid, choice.get(cid, "approve"), "--run", str(run), *extra)
        else:
            return n
    raise SystemExit(f"never reached {stop_at}")


# --- re-cut runs (path C-R) ----------------------------------------------------------------------

# The ad files, by the teardown they come with. `video` is the original's name in 01_base; `visual`
# the mean frame change per stretch of seconds (the segment map's measure), from the reference runs.
ADS = {
    "ad3": {"teardown": RECUT_FIX / "ad3_teardown.json", "transcript": None, "video": "ad3_original.mp4",
            "material": "text_cards", "loudness": -16.0,
            "visual": [(0.0, 6.0, 22.2), (6.0, 12.1, 20.6), (12.1, 18.1, 11.6), (18.1, 24.2, 11.3)]},
    "ad2": {"teardown": RECUT_FIX / "ad2_teardown.json", "transcript": RECUT_FIX / "ad2_transcript.json",
            "video": "ad_2.mp4", "material": "talking_head", "loudness": -19.0,
            "visual": [(0.0, 7.4, 6.1), (7.4, 14.8, 4.2), (14.8, 22.3, 3.1), (22.3, 29.7, 3.4)]},
    "exampletravel": {"teardown": LIB_FIX / "exampletravel_teardown.json", "transcript": LIB_FIX / "exampletravel_transcript.json",
               "video": "exampletravel_original.mp4", "material": "vo_captions", "loudness": -17.5,
               "visual": [(0.0, 6.7, 14.0), (6.7, 13.4, 12.2), (13.4, 20.2, 7.9), (20.2, 26.9, 6.5)]},
}

MIDDLE_DIAGNOSIS = {
    "ad3": """# Middle diagnosis (re-cut), {version}

## 1. The retention steps
The diagnosis points at the hook (p25 per impression fell); the middle steps held (ladder in
04_final/diagnosis_v01.json). The structural check (04_final/structural_v01.json): p75/p50 is the
weakest step in all 4 ads that use this file, 12.07 to 18.11 s. Taken as an extra re-cut at the
diagnosis check-in.

## 2. The segment map (03_wip/retention/segment_map_v01.json)
| Step | Seconds | Cards on screen | Visual change |
|---|---|---|---|
| p25/play | 0 to 6.04 | the hook card (0.2 to 6.4 s) | 22.2 |
| p50/p25 | 6.04 to 12.07 | the promise card (7.4 to 13.5 s) | 20.6 |
| p75/p50 | 12.07 to 18.11 | blank 13.5 to 14.2 s, then the CTA card | 11.6 (-44%) |
| p95/p75 | 18.11 to 22.94 | the same CTA card | 11.3 |

## 3. What happens on screen
Two continuous shots: the flight to 12.12 s, then a calm, near-static flight along the river to the
end. The last new information (the CTA card) at 14.19 s; the last 10 s show one card over a
near-identical image. The product is never shown. Music only, no speech.

## 4. Causes
2 pacing: yes (visual change -44% after 12 s). 3 longer than its content: yes (nothing new after
14.19 s). 5 no proof: hypothesis. 6 visual monotony: yes. 11 "this is an ad" moment: yes, with 3
(the CTA at 14.19 s). 1, 4, 7, 8, 9, 10: no.
""",
    "ad2": """# Middle diagnosis (re-cut), {version}

## 1. The retention steps
p75/p50 dropped (04_final/diagnosis_v01.json, ladder): the third quarter of the video loses viewers.

## 2. The segment map (03_wip/retention/segment_map_v01.json)
A talking head on camera with word captions, 29.68 s, six shots (the shot changes in
02_research/teardown_v01.json). The weak step p75/p50 is 14.84 to 22.26 s.

## 3. What happens on screen
The presenter tells her story: last night's dream, the first time she knew she was dreaming, the
one book behind it, her love of dreams since childhood, the apps and journals that did nothing,
flying off a roof in the dream, a set-up question to the viewers, then the strongest line, ten
minutes of practice before sleep that works from the first night (21.18 to 25.52 s), where most
viewers have already left; the call to action from 25.64 s. A pause of 1.38 s at 8.42 to 9.80 s.

## 4. Causes
2 pacing, dead air: yes (the 1.38 s pause, slow sentences). 3 longer than its content: yes. 1 the
hook promises, the middle does not deliver: yes (the strongest line comes at 21 s). 5 no proof:
hypothesis. 4, 6, 7, 8, 9, 10, 11: no.
""",
    "exampletravel": """# Middle diagnosis (re-cut), {version}

## 1. The retention steps
p75/p50 dropped (04_final/diagnosis_v01.json, ladder): the third quarter of the video loses viewers.

## 2. The segment map (03_wip/retention/segment_map_v01.json)
A voiceover ad with word captions and music, 26.87 s, three shots (0 to 14.9 s, 14.9 to 22.6 s,
the end card from 22.6 s). The weak step p75/p50 is 13.43 to 20.15 s.

## 3. What happens on screen
The voiceover (02_research/transcript_v01.json) sells a sailing week for small groups over calm
footage; the captions follow the words. From about 13 s the footage barely changes, and the script
piles up holiday pictures before the offer ("Jacht, skipper i trzy porty do wyboru.").

## 4. Causes
3 the ad longer than its content: yes (the offer at 17.96 s, a slow build before it). 2 pacing:
yes (visual change falls after 13 s). 6 visual monotony: yes. 5 no proof: hypothesis. 1, 4, 7, 8,
9, 10, 11: no.
""",
}

G3R_NOTES = {
    "ad3": ("Variants kept, each one change: R1-15s (change recut_shorter, level 0): a 15 s cut that "
            "keeps the hook and the promise up to 11.146 s, then the CTA from 20.735 s to the end, "
            "dropping the static flight (causes 3, 6, 11); R7-6s (change bumper_6s, level 1): a 6 s "
            "bumper, the hook card and the CTA (for a 6 s placement); R4-newshot (change "
            "recut_new_shot, level 4): a new Veo shot (first + last frame, 8 s) in the weak window "
            "showing the moment from the primary text (causes 5, 6)."),
    "ad2": ("Variants kept, each one change: U-J1 (change recut_shorter, level 0, jump hard): the slow "
            "sentences and the 1.38 s pause cut out (causes 2, 3); U-coldopen (change recut_reorder, "
            "level 0): a cold open with the strongest line first (cause 1)."),
}


def place_ad(ws: Path, run: Path, ad: str) -> None:
    """A2 and A3 as they leave the run: the original (a placeholder: no media in the evals), its
    teardown and transcript (the engine's own test fixtures), and the material."""
    spec = ADS[ad]
    video = f"01_base/{spec['video']}"
    place(ws, run, video, b"placeholder: the eval sandbox has no media; see 02_research/teardown_v01.json\n",
          "the user's original file from the brand folder (eval placeholder)")
    teardown = json.loads(Path(spec["teardown"]).read_text(encoding="utf-8"))
    teardown["video"] = video
    place(ws, run, "02_research/teardown_v01.json", teardown,
          f"tm tool teardown {video} (eval fixture: {Path(spec['teardown']).name})")
    if spec["transcript"]:
        place(ws, run, "02_research/transcript_v01.json",
              json.loads(Path(spec["transcript"]).read_text(encoding="utf-8")),
              f"tm tool transcribe {video} (eval fixture: {Path(spec['transcript']).name})")
    tm(ws, "material", spec["material"], "--run", str(run))


def segment_map(ws: Path, run: Path, ad: str) -> None:
    """CR1's file, made by the tool's own `build` from the reference runs' measures."""
    sys.path.insert(0, f"{ROOT}/engine/src")
    from tm.tools import segment_map as sm  # noqa: E402

    spec = ADS[ad]
    teardown = json.loads((run / "02_research" / "teardown_v01.json").read_text(encoding="utf-8"))
    transcript = run / "02_research" / "transcript_v01.json"
    words = sm._word_starts(json.loads(transcript.read_text(encoding="utf-8"))) if transcript.is_file() else None
    duration = float(teardown["duration_s"])
    times = [i * 0.5 for i in range(int(duration / 0.5) + 1)]
    visual = [[t, next((v for a, b, v in spec["visual"] if a <= t < b), spec["visual"][-1][2])] for t in times]
    loud = [[t, spec["loudness"]] for t in times]
    diagnosis = json.loads((run / "run.json").read_text(encoding="utf-8"))["diagnosis"]
    body = sm.build(duration, diagnosis, sm._overlays(teardown), words, visual, loud)
    result = {"video": teardown["video"], "duration_s": round(duration, 3), "fps": teardown["fps"], **body,
              "visual_change_0p5s": visual, "loudness_0p5s": loud}
    place(ws, run, "03_wip/retention/segment_map_v01.json", result,
          "tm tool segment_map (eval fixture: measures from the reference run)")


def middle_diagnosis(ws: Path, run: Path, ad: str, version: str) -> None:
    """Sections 1-4 (CR1, CR2); from v02 on, section 5 with the variants chosen at CR3 too."""
    text = MIDDLE_DIAGNOSIS[ad].format(version=version)
    if version != "v01" and ad in G3R_NOTES:
        text += f"\n## 5. Variants\n{G3R_NOTES[ad]}\n"
    place(ws, run, f"04_final/middle_diagnosis_{version}.md", text,
          "written at CR1-CR3 from templates/middle_diagnosis_template.md (eval fixture)")


def music_take(ws: Path, run: Path) -> None:
    """A method-E take of Ad 3's track already in the run, 14.55 s long (RC17: one that fits is reused)."""
    place(ws, run, "03_wip/audio/music_take_v01.mp3", b"placeholder: a 14.55 s music take (eval fixture)\n",
          "ElevenLabs Music method E take of the ad's own track, made earlier (eval placeholder)")
    record = {"kind": "music_take", "file": "music_take_v01.mp3", "length_s": 14.55, "model": "music_v2_5",
              "plan": {"chunks": [{"song_id": "example-song", "range": {"start_ms": 0, "end_ms": 10000}},
                                  {"text": "[Main Theme]", "duration_ms": 10000}]},
              "credits_used": None}
    place(ws, run, "03_wip/audio/music_take_v01.mp3.json", record,
          "tm tool elevenlabs music-compose record (eval fixture)")


def recut_run(ws: Path, ad: str, scn: str, stop_at: str, *, outputs: list[str], budget: dict | None = None,
              take_structural: bool = False, g3r: str | None = None, extra_hooks: dict | None = None) -> tuple[Path, dict]:
    """A Check every step run on `ad`'s file, Meta rows of scenario `scn`, driven to `stop_at`."""
    run = new_run(ws, outputs, budget=budget, level="every_step")

    def at_a1a(ws: Path, run: Path) -> None:
        structural(ws, run, scn)
        if take_structural:  # the user took the re-cut of the structural weakness at G1a
            tm(ws, "flow", "R", "--run", str(run))

    hooks = {"A1a": at_a1a,
             "A2": lambda ws, run: None,
             "A3": lambda ws, run: place_ad(ws, run, ad),
             "CR1": lambda ws, run: segment_map(ws, run, ad),
             "CR2": lambda ws, run: middle_diagnosis(ws, run, ad, "v01"),
             **(extra_hooks or {})}
    notes = {"G1a": "refresh" + (" plus the re-cut of the structural weakness" if take_structural else "")}
    if g3r:
        notes["G3r"] = g3r
    n = drive(ws, run, stop_at, scn=scn, hooks=hooks, notes=notes)
    return run, n


def r1_15s_checked(ws: Path, run: Path) -> None:
    """CR4 to CR7 of the 15 s cut, as a run that made and accepted it leaves them."""
    edit = {"variant": "R1-15s", "change_id": "recut_shorter", "level": 0,
            "cause": "the ad is longer than its content: nothing new after 14.19 s",
            "music_source": "elevenlabs_continuation", "fps": 30, "width": 720, "height": 1280,
            "video": [{"src": "../../01_base/ad3_original.mp4", "from": 0.0, "to": 11.146},
                      {"src": "../../01_base/ad3_original.mp4", "from": 20.735, "to": 24.149}],
            "audio": [{"src": "../audio/music_take_v01.mp3", "from": 0.0, "to": 14.55}],
            "audio_xfade_ms": 40, "audio_tail_fade_ms": 300}
    place(ws, run, "03_wip/recut/R1-15s_v01.json", edit, "edit list for R1-15s")
    tm(ws, "recut", "check", "--run", str(run), str(run / "03_wip/recut/R1-15s_v01.json"),
       "--teardown", str(run / "02_research/teardown_v01.json"))


# --- trend research runs (PB04): the beauty dry run, anonymised ---------------------------------

BEAUTY_FIX = HERE / "fixtures" / "beauty"                                        # gen_mocks.py --pb04
TM_MOCKS = HERE.parent / "mocks" / "trendsmesh" / "fixtures"                     # the same video pages the mock serves
TR_AT = "2026-11-04T10:00:00+00:00"
TR_OUTPUTS = ["category_report", "paid_view"]
PAGE_SLUG, PAGE_VERSION = "art_mock_1", "ver_mock_1"     # run 1's published page (tr_weekly_at_d1)


def _beauty_helpers():
    """engine/tests/beauty.py's pure helpers (the derived searches, the split, the hook cards): the same
    derivation the engine's own tests rebuild the dry run's files with."""
    for p in (f"{ROOT}/engine/src", f"{ROOT}/engine/tests"):
        if p not in sys.path:
            sys.path.insert(0, p)
    import beauty  # noqa: E402
    from tm import trends  # noqa: E402
    from tm.runfolder import RunFolder  # noqa: E402
    return beauty, trends, RunFolder


def _fix(name: str) -> dict:
    return json.loads((BEAUTY_FIX / name).read_text(encoding="utf-8"))


def tr_run(ws: Path, created: str, level: str, outputs: list[str], after: Path | None = None) -> Path:
    """A trend research run made by `tm run new`, named and dated `<created>_beauty` (the engine dates
    a run by the real day; the beauty data are fixed-date), with its config written by `tm config write`
    (the intake answers, or --from-previous after `after`)."""
    args = ["run", "new", "--playbook", "trend-research", "--name", "beauty"]
    if after is not None:
        args += ["--after", str(after.relative_to(ws))]
    made = Path(tm(ws, *args)["path"])
    run = made.with_name(f"{created}_beauty")
    if made != run:
        made.rename(run)
    state = json.loads((run / "run.json").read_text(encoding="utf-8"))
    state.update(run_id=run.name, created=created)
    (run / "run.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    man = run / "manifest.md"
    man.write_text(man.read_text(encoding="utf-8").replace(made.name, run.name), encoding="utf-8")
    if after is not None:
        tm(ws, "config", "write", "--run", str(run), "--from-previous")
        if level != "hands_off":
            tm(ws, "level", level, "--run", str(run))
    else:
        f = ws / ".answers.json"
        f.write_text(json.dumps({"level": level, "category": {"inputs": ["beauty"], "phrase": "beauty", "seeds": []},
                                 "market": "US", "language": "English", "market_lang": "en", "currency": "USD",
                                 "outputs": outputs}), encoding="utf-8")
        tm(ws, "config", "write", "--run", str(run), "--answers", str(f))
        f.unlink()
    tm(ws, "config", "check", "--run", str(run))
    return run


def tr_save(run: Path, tool: str, tool_input: dict, answer) -> None:
    """One MCP answer saved into the run as the collector saves it (tm.trends.save_answer)."""
    _, trends, RunFolder = _beauty_helpers()
    trends.save_answer(RunFolder.open(run), tool, tool_input, answer, at=TR_AT)


def tr_videos(run: Path, trend_ids) -> None:
    for tid in trend_ids:
        page = TM_MOCKS / f"videos_{tid}.json"
        if page.is_file():
            tr_save(run, "get_trend_videos", {"trend_id": tid, "order": "recent", "limit": 50, "page": 1},
                    json.loads(page.read_text(encoding="utf-8")))


def tr_b1(ws: Path, run: Path) -> None:
    beauty, _, _ = _beauty_helpers()
    cmap = _fix("category_map.json")
    for query, cards in beauty.search_answers(cmap).items():
        tr_save(run, "search_trends", {"about": query, "limit": 50}, {"data": cards, "page": 1, "has_more": False})
    place(ws, run, "03_wip/split_v01.json", beauty.split_of(cmap), "the seed and the sub-categories searched (eval fixture)")
    tm(ws, "research", "search-status", "--run", str(run))


def tr_b4(ws: Path, run: Path) -> None:
    beauty, _, _ = _beauty_helpers()
    hooks = _fix("hooks_in_category.json")
    cards = beauty.hook_cards(hooks)
    tr_save(run, "list_trends", {"sort": "rising", "trend_type": "hook_trend", "limit": 50, "page": 1},
            {"data": cards, "page": 1, "has_more": False})
    if json.loads((run / "run.json").read_text(encoding="utf-8")).get("previous_run"):
        tm(ws, "research", "map-change", "--run", str(run))
    # issue #8: the hooks ranked by fit (the dry run's kept hooks first), only the shortlist fetched
    place(ws, run, "03_wip/hook_fit_v01.json", beauty.fit_scores(hooks),
          "the hooks' fit scores, the dry run's kept hooks first (eval fixture)")
    tm(ws, "research", "hook-fit", "--run", str(run), "--file", "03_wip/hook_fit_v01.json")
    plan = tm(ws, "research", "fetch-plan", "--run", str(run))
    tr_videos(run, plan.get("fetch") or [])
    tm(ws, "research", "hooks", "--run", str(run), "--terms", ",".join(hooks["terms"]))


def tr_c3(ws: Path, run: Path) -> None:
    from datetime import date, timedelta
    if json.loads((run / "run.json").read_text(encoding="utf-8")).get("previous_run"):
        return                                                   # a weekly run: no backtest (flow.md#c3)
    created = date.fromisoformat(run.name[:10])
    for back in (42, 28, 14):
        tm(ws, "research", "backtest", "--run", str(run), "--as-of", (created - timedelta(days=back)).isoformat())


def tr_f2(ws: Path, run: Path) -> None:
    """A first run with the weekly digest: the previous week rebuilt from the evidence dates (V24)."""
    from datetime import date, timedelta
    created = date.fromisoformat(run.name[:10])
    tm(ws, "research", "rebuild-previous", "--run", str(run), "--as-of", (created - timedelta(days=7)).isoformat())
    tm(ws, "research", "digest", "--run", str(run))


def _growth_ids(run: Path, bucket: str) -> list[str]:
    growth = sorted((run / "02_research").glob("growth_v*.json"))[-1]
    return [r["id"] for r in json.loads(growth.read_text(encoding="utf-8"))["trends"] if r["bucket"] == bucket]


def tr_d1(ws: Path, run: Path) -> None:
    for tid in _growth_ids(run, "act_now") + _growth_ids(run, "still_rising")[:5]:
        tm(ws, "research", "evidence", "--run", str(run), "--trend", tid)


def tr_d2(ws: Path, run: Path) -> None:
    """The dry run's Ad Library summary (v02, anonymised), each query's answer saved as the collector saves it.
    Without the paid view nothing: the check would need the picks first (flow.md#d2), and the page then
    says the Ad Library was not checked."""
    if "paid_view" not in json.loads((run / "run.json").read_text(encoding="utf-8"))["outputs"]:
        return
    summary = {**_fix("ad_library_summary_v02.json"), "checked": True}
    if not TR_META["connected"]:   # Meta failed at D2 (V22): checked false, only the hooks' rows
        summary = {"checked": False, "checks": [c for c in summary["checks"] if c["level"] == "not_checkable"]}
        f = place(ws, run, "02_research/ad_library_summary_v01.json", summary,
                  "the Ad Library could not be read: the Meta Ads MCP is not connected (eval fixture)")
        tm(ws, "research", "paid", "check", "--run", str(run), "--file", str(f))
        return
    queries = sorted({re.sub(r"\s*\(same check\)\s*$", "", c["query"]).strip()
                      for c in summary["checks"] if c.get("query")})
    for q in queries:
        tr_save(run, "ads_library_search", {"search_terms": q, "ad_reached_countries": ["US"]}, {"data": []})
    f = place(ws, run, "02_research/ad_library_summary_v01.json", summary,
              "your reading of the Meta Ads MCP ads_library_search answers in 02_research/ad_library/ (eval fixture)")
    tm(ws, "research", "paid", "check", "--run", str(run), "--file", str(f))


TR_META = {"connected": True}   # tr_at_d3: False
VIEWS = {"category_report": "report", "weekly_digest": "digest", "paid_view": "paid"}


def tr_d3(ws: Path, run: Path) -> None:
    """The dry run's picks_v04 (anonymised) with a score table (the dry run wrote none: decision 13), for this
    run's outputs and date."""
    _beauty_helpers()                                            # the engine on sys.path, once
    from tm import research_config  # noqa: E402
    picks = _fix("picks_v04.json")
    outputs = json.loads((run / "run.json").read_text(encoding="utf-8"))["outputs"]
    picks["outputs"] = [VIEWS[o] for o in outputs]
    picks["as_of"] = run.name[:10]
    if "weekly_digest" not in outputs:
        picks.pop("digest_reading", None)
    if "paid_view" not in outputs:
        picks.pop("paid_reading", None)
    picks["scores"] = {p["id"]: {c: 3 for c in research_config.CRITERIA}
                       for p in picks["act_now"] + picks["still_rising"]}
    place(ws, run, "03_wip/picks_v01.json", picks, "the review of the picks (eval fixture: the dry run's picks_v04)")
    if run.name.startswith("2026-11-04"):                       # the picks are the 4 Nov run's
        tm(ws, "research", "picks", "check", "--run", str(run), "--file", str(run / "03_wip/picks_v01.json"))


def tr_e1(ws: Path, run: Path) -> None:
    backtests = sorted(str(p) for p in (run / "03_wip").glob("backtest_*_rule_v3_v*.json"))
    tm(ws, "research", "report", "--run", str(run), "--picks", str(run / "03_wip/picks_v01.json"),
       *(["--backtest", *backtests] if backtests else []))


def tr_e2(ws: Path, run: Path) -> None:
    tm(ws, "page", "published", "--run", str(run), "--page", "report", "--slug", PAGE_SLUG, "--version", PAGE_VERSION,
       "--url", f"https://claude.ai/artifact/{PAGE_SLUG}")


TR_HOOKS = {
    "A2": lambda ws, run: tm(ws, "research", "previous", "--run", str(run)),
    "B1": tr_b1,
    "B2": lambda ws, run: tm(ws, "research", "map", "--run", str(run), "--split", str(run / "03_wip/split_v01.json")),
    "B3": lambda ws, run: (place(ws, run, "03_wip/map_review_v01.json", _fix("map_review_v01.json"),
                                 "the relevance review (eval fixture: the dry run's map_review_v01)"),
                           tm(ws, "research", "map", "--run", str(run), "--split", str(run / "03_wip/split_v01.json"),
                              "--review", str(run / "03_wip/map_review_v01.json"))),
    "B4": tr_b4,
    "C2": lambda ws, run: tm(ws, "research", "growth", "--run", str(run)),
    "C3": tr_c3,
    "F2": tr_f2,
    "D1": tr_d1,
    "D2": tr_d2,
    "D3": tr_d3,
    "E1": tr_e1,
    "E2": tr_e2,
    "E3": lambda ws, run: tm(ws, "research", "seeds", "--run", str(run)),
}
TR_CHOICES = {"G3": "publish", "GS": "by_hand"}


def tr_drive(ws: Path, run: Path, stop_at: str | None = None, stop_checkin: str | None = None) -> dict:
    """Do each step's work (TR_HOOKS) and answer each check-in as a user would, until `stop_at` is the
    step to work on, `stop_checkin` is asked or decided by rule, or the run is done."""
    for _ in range(100):
        n = tm(ws, "next", "--run", str(run), ok=(0, 2))
        if n["action"] == "work":
            if n["step"] == stop_at:
                return n
            if n["step"] in TR_HOOKS:
                TR_HOOKS[n["step"]](ws, run)
            tm(ws, "done", n["step"], "--run", str(run))
        elif n["action"] in ("ask", "auto"):
            if stop_checkin in n["checkin"]["ids"]:
                return n
            for cid in n["checkin"]["ids"]:
                extra = ["--by", "rule", "--note", "set by the eval fixture"] if n["action"] == "auto" else []
                tm(ws, "decide", cid, TR_CHOICES.get(cid, "accept"), "--run", str(run), *extra)
        else:
            return n
    raise SystemExit(f"never reached {stop_at or stop_checkin}")


def tr_main(scn: str, ws: Path) -> tuple[Path, dict]:
    if scn == "tr_weekly_at_d1":
        # The name is the brief's; the run stops at F2, the step before D1 (ruling F11). Run 1 (29 Oct, the weekly digest chosen) done, its page published as art_mock_1; run 2 (4 Nov)
        # after it, Hands-off, everything before the digest done (ruling F11: the agent runs the digest).
        first = tr_run(ws, "2026-10-29", "hands_off", ["category_report", "weekly_digest"])
        end = tr_drive(ws, first)
        if end["action"] != "done":
            raise SystemExit(f"run 1 did not finish: {end}")
        run = tr_run(ws, "2026-11-04", "hands_off", [], after=first)
        return run, tr_drive(ws, run, stop_at="F2")
    level, stop = {"tr_at_b3": ("every_step", {"stop_at": "B3"}),
                   "tr_at_d2": ("every_step", {"stop_at": "D2"}),
                   "tr_at_d3": ("every_step", {"stop_at": "D3"}),
                   "tr_at_e2": ("hands_off", {"stop_checkin": "G3"})}[scn]
    TR_META["connected"] = scn != "tr_at_d3"
    run = tr_run(ws, "2026-11-04", level, TR_OUTPUTS)
    return run, tr_drive(ws, run, **stop)


# --- creative brief (PB02) -----------------------------------------------------------------------
# The LD dry run, anonymised (gen_mocks.py --pb02): a run `runs/02-creative-brief/2026-11-07_nightschool`
# for "Night School e-book" (Canada, English, the account spends PLN), built with the engine's own commands.
# The MCP answers are saved as the collector saves them (trends.save_answer, mcp_saves.save).

LD_FIX = HERE / "fixtures" / "ld"
CB_CREATED = "2026-11-07"
CB_NAME = "nightschool"
CB_AT = "2026-11-07T09:00:00+00:00"      # when the fixture's TrendsMesh and Ad Library answers were saved
CB_TERMS = "lucid dream,dream,sleep,night,journal,wake up,4am,consciousness"    # engine/tests/test_shortlist.py
CB_BRAND = {
    "schema": "brand/1", "kind": "brand", "brand": "Night School",
    "stands_for": "A first lucid dream, with a plain plan built on published sleep research.",
    "tone": ["curious", "plain", "confident"],
    "off_limits": ["medical or sleep-disorder claims", "drug references"], "off_limits_asked": True,
    "claims": [{"claim": "A night-by-night plan", "wording": "Your first lucid dream, planned night by night",
                "source": "00_raw/landing_nightschool_2026-11-04.txt"}],
    "competitors": [], "guide": {"source": "none", "where": ""},
    "drafted_from": ["landing", "ads", "user"], "confirmed": CB_CREATED,
}
CB_ANSWERS = {
    "account": {"id": "act_000000", "market": "CA", "language": "English", "currency": "PLN"},
    "product": {"name": "Night School e-book", "landing_url": "https://nightschool.example.com/",
                "category_phrase": "lucid dreaming"},
    "voice": {"links": []},
    "trends": {"terms": CB_TERMS.split(","), "exclude_terms": ["halloween"]},
    "brief": {"recipients": ["decision", "strategy", "creator", "editor", "media-buyer"], "currency": "USD",
              "fx_rate": 3.70},
    "concepts": {"count": 3},
    "delivery": {"channel": "artifact"},
    "intake": {"budget": None, "deadline": None, "approver": None, "rights": None, "fee": None},
}
CB_HYPOTHESIS = ("# Audience hypothesis (from the product, before data)\n\nMen 25–45 into consciousness and "
                 "self-experiment content, gaming and the mind (the landing page's picture of its reader).\n")


def cb_account_context() -> str:
    """01_base/account_context.md as the dry run's CB1 notes put it, every figure read from the age x gender and
    placement rows the run saves (fixtures/ld/meta_breakdowns.json), so the notes always match the persona the
    engine picks from those rows, and no account figure is written here."""
    rows = json.loads((LD_FIX / "meta_breakdowns.json").read_text(encoding="utf-8"))
    ages, places = rows["age_gender"]["data"], rows["placements"]["data"]

    def res(r: dict) -> int:
        return int(r["results"]["values"][0]["value"])

    def spend(rs: list[dict]) -> float:
        return sum(float(r["spend"]["value"]) for r in rs)

    total, most = sum(map(res, ages)), max(map(res, ages))
    old = [r for r in ages if r["age"] == "65+"]
    men = sum(res(r) for r in ages if r["gender"] == "male" and r["age"] in ("25-34", "35-44", "45-54"))
    feed = sum(res(r) for r in places if (r["publisher_platform"], r["platform_position"]) == ("facebook", "feed"))
    short = sum(res(r) for r in places if any(k in r["platform_position"] for k in ("reels", "stories")))
    every = sum(map(res, places))
    share = lambda n, of: f"{round(100 * n / of)}%"  # noqa: E731
    return ("# Account context (CB1), Night School e-book, market CA\n\n"
            "All numbers from the Meta Ads MCP (01_base/meta/), account act_000000, all time, the [CA] campaigns.\n\n"
            f"- {total} checkouts started: {'below' if most < 10 else 'at least'} 10 results per segment, so the "
            f"persona is {'directional' if most < 10 else 'firm'}.\n"
            f"- 65+ (both genders): {sum(map(res, old))} of {total} checkouts on {share(spend(old), spend(ages))} of "
            f"spend; men 25–54: {men} checkouts.\n"
            f"- Placements: Facebook feed {feed} of {every} checkouts ({share(feed, every)}), Reels and Stories "
            f"together {share(short, every)}: both formats.\n"
            "- Divergence (a finding): the buyers are older than the hypothesis (men 25–45).\n")


# The dry run's Ad Library reading (02_research/ad_library_summary.md), as answers: the advertisers it named under
# their aliases, the rest noise. Candidate -> (query, verdict, advertisers): the dry run's C1 to C3 (C1's query
# made up, as in fixtures/ld/brief_pack_v01.json).
CB_AD_LIBRARY = {
    "dream diary": [{"page_name": "Paper & Ink Diaries", "ad_creative_link_titles": ["Hand-bound diaries for 2027"]},
                    {"page_name": "Little Diary App", "ad_creative_link_titles": ["A safe diary app for kids"]}],
    "lucid dreaming research": [{"page_name": "Drama Shorts", "ad_creative_link_titles": ["Watch episode 1 free"]}],
    "lucid dream": [{"page_name": "Advertiser 1", "ad_creative_link_titles": ["Lucid Dreaming On Command"],
                     "ad_delivery_start_time": "2026-11-01"},
                    {"page_name": "Advertiser 3", "ad_creative_link_titles": ["Vivid Dreams Start Tonight"],
                     "ad_delivery_start_time": "2026-11-01"},
                    {"page_name": "Advertiser 4",
                     "ad_creative_link_titles": ["Dreams Don't Retire When You Do."],
                     "ad_delivery_start_time": "2026-11-02"},
                    {"page_name": "Advertiser 5", "ad_creative_link_titles": ["Lucid"]},
                    {"page_name": "Novel Hub", "ad_creative_link_titles": ["Read the first chapter free"]}],
}
CB_SATURATION = [("C1", "dream diary", "none_found", [], "all noise (stationery and kids' apps)"),
                 ("C2", "lucid dreaming research", "none_found", [], None),
                 ("C3", "lucid dream", "competitor_found", ["Advertiser 4"], "a wellness page that speaks to age")]


def _ld_brief() -> dict:
    return json.loads((LD_FIX / "brief_pack_v01.json").read_text(encoding="utf-8"))


def _cb_candidates() -> dict[str, str]:
    """Concept id -> its trend's alias, in the brief's order."""
    return {c["id"]: c["plugin"]["trend"]["trend_id"] for c in _ld_brief()["concepts"]}


def cb_run(ws: Path, level: str, outputs: list[str], seed: str | None = None) -> Path:
    """A creative brief run made by `tm run new`, renamed and dated 2026-11-07 (the engine dates a run
    by the real day)."""
    args = ["run", "new", "--playbook", "creative-brief", "--name", CB_NAME] + (["--seed", seed] if seed else [])
    made = Path(tm(ws, *args)["path"])
    run = made.with_name(f"{CB_CREATED}_{CB_NAME}")
    if made != run:
        made.rename(run)
        state = json.loads((run / "run.json").read_text(encoding="utf-8"))
        state.update(run_id=run.name, created=CB_CREATED)
        (run / "run.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        man = run / "manifest.md"
        man.write_text(man.read_text(encoding="utf-8").replace(made.name, run.name), encoding="utf-8")
    CB_RUN.update(level=level, outputs=outputs)
    return run


CB_RUN: dict = {"level": "every_step", "outputs": ["review_pack", "briefs", "animatics", "page"]}


def _engine():
    if f"{ROOT}/engine/src" not in sys.path:
        sys.path.insert(0, f"{ROOT}/engine/src")
    from tm import mcp_saves, trends, voice  # noqa: E402
    from tm.runfolder import RunFolder  # noqa: E402
    return mcp_saves, trends, voice, RunFolder


def cb_landing(ws: Path, run: Path) -> None:
    name = "landing_nightschool_2026-11-04.txt"
    place(ws, run, f"00_raw/{name}", (LD_FIX / name).read_text(encoding="utf-8"),
          "WebFetch https://nightschool.example.com/ (eval fixture: the dry run's landing page, anonymised)")


def cb_a1(ws: Path, run: Path) -> None:
    """The A1 Meta reads (saved as the collector saves them), the brand profile and the intake."""
    mcp_saves, _, _, RunFolder = _engine()
    folder = RunFolder.open(run)
    mcp_saves.save(folder, "ads_get_ad_accounts", {},
                   {"data": [{"id": "act_000000", "name": "Night School", "currency": "PLN", "account_status": 1}]})
    mcp_saves.save(folder, "ads_get_ad_entities", {"ad_account_id": "act_000000", "level": "adset",
                                                   "fields": ["name", "targeting", "campaign_name", "amount_spent"]},
                   json.loads((LD_FIX / "targeting.json").read_text(encoding="utf-8")))
    mcp_saves.save(folder, "ads_get_creatives", {"ad_account_id": "act_000000"},
                   json.loads((LD_FIX / "creatives.json").read_text(encoding="utf-8")))
    f = place(ws, run, "03_wip/brand_v01.json", CB_BRAND, "the landing page and the running ads; off-limits from the user (eval fixture)")
    tm(ws, "brand", "check", "--file", str(f))
    profile = tm(ws, "brand", "save", "--run", str(run), "--file", str(f))["file"]
    answers = {**json.loads(json.dumps(CB_ANSWERS)), "level": CB_RUN["level"], "outputs": CB_RUN["outputs"],
               "brand": {"profile": profile, "guide": None}}
    f = place(ws, run, "03_wip/intake_answers_v01.json", answers, "the intake card, confirmed by the user (eval fixture)")
    tm(ws, "config", "write", "--run", str(run), "--answers", str(f))
    tm(ws, "config", "check", "--run", str(run))


def cb_b1(ws: Path, run: Path) -> None:
    """The hypothesis first, then the age x gender and placement reads (saved after it), the pick."""
    mcp_saves, _, _, RunFolder = _engine()
    folder = RunFolder.open(run)
    f = place(ws, run, "02_research/audience/hypothesis_v01.md", CB_HYPOTHESIS, "the product and the landing page (eval fixture)")
    tm(ws, "audience", "hypothesis", "--run", str(run), "--file", str(f))
    rows = json.loads((LD_FIX / "meta_breakdowns.json").read_text(encoding="utf-8"))
    age = mcp_saves.save(folder, "ads_get_ad_entities",
                         {"ad_account_id": "act_000000", "level": "campaign", "date_preset": "maximum",
                          "breakdowns": ["age", "gender"], "fields": ["spend", "results", "cost_per_result"]},
                         rows["age_gender"])
    where = mcp_saves.save(folder, "ads_get_ad_entities",
                           {"ad_account_id": "act_000000", "level": "campaign", "date_preset": "maximum",
                            "breakdowns": ["publisher_platform", "platform_position"], "fields": ["spend", "results"]},
                           rows["placements"])
    tm(ws, "audience", "pick", "--run", str(run), "--breakdown", str(age), "--placements", str(where))
    place(ws, run, "01_base/account_context.md", cb_account_context(), "Meta Ads reads in 01_base/meta (eval fixture)")


def _archive_query(raw: dict) -> tuple[str, str]:
    """engine/tests/ld.py's: the kind and the keyword of a saved archive answer, from its `_query_url`."""
    from urllib.parse import parse_qs, urlparse
    url = urlparse(raw["_query_url"])
    kind = "posts" if url.path.endswith("/posts/search") else "comments"
    qs = parse_qs(url.query)
    return kind, next((qs[k][0] for k in ("title", "selftext", "query", "body") if k in qs), "")


def cb_b2(ws: Path, run: Path) -> None:
    """The category's voice: the archive answers the dry run saved (as `tm voice reddit-*` logs them) and the two
    Goodreads texts (`tm voice import`, tier B), then its themes (`tm voice check`)."""
    _, _, voice, RunFolder = _engine()
    items = []
    for f in sorted((LD_FIX / "voice").glob("reddit_*.json")):
        raw = json.loads(f.read_text(encoding="utf-8"))
        items += voice.items_from_archive(raw, *_archive_query(raw))
    voice.append_items(RunFolder.open(run), items)
    for source, name in (("goodreads_laberge", "goodreads_laberge_exploring_reviews.txt"),
                         ("goodreads_love", "goodreads_love_are_you_dreaming_reviews.txt")):
        tm(ws, "voice", "import", "--run", str(run), "--file", str(LD_FIX / "voice" / name), "--format", "text",
           "--source", source, "--tier", "B")
    f = place(ws, run, "02_research/voice/voice_themes_v01.json",
              json.loads((LD_FIX / "voice_themes.json").read_text(encoding="utf-8")),
              "the items in 02_research/voice/items.jsonl (eval fixture: the dry run's themes)")
    tm(ws, "voice", "check", "--run", str(run), "--file", str(f))


def cb_b3(ws: Path, run: Path) -> None:
    """TrendsMesh: the dry run's searches, cards and video pages saved as the collector saves them, the shortlist."""
    _, trends, _, RunFolder = _engine()
    folder = RunFolder.open(run)
    tm(ws, "evidence", "trendsmesh", "--run", str(run), "--why", "TrendsMesh answers with trend data (eval fixture)")
    for f in sorted((LD_FIX / "trends").glob("*.json")):          # the dry run's searches and rising lists
        data = json.loads(f.read_text(encoding="utf-8"))
        if f.stem.startswith("search_"):
            trends.save_answer(folder, "search_trends", {"about": f.stem[len("search_"):].replace("_", " "), "limit": 20},
                               data, at=CB_AT)
        elif f.stem.startswith("rising_"):
            trends.save_answer(folder, "list_trends", {"sort": "rising", "trend_type": f.stem.split("_", 1)[1]},
                               data, at=CB_AT)
    for f in sorted((LD_FIX / "cards").glob("*.json")):
        trends.save_answer(folder, "get_trend", {"trend_id": f.stem}, json.loads(f.read_text(encoding="utf-8")), at=CB_AT)
    for f in sorted((LD_FIX / "videos").glob("*.json")):          # in two pages, as engine/tests/ld.py saves them
        videos = json.loads(f.read_text(encoding="utf-8"))["videos"]
        half = len(videos) // 2
        trends.save_answer(folder, "get_trend_videos", {"trend_id": f.stem},
                           {"data": videos[:half], "page": 1, "has_more": True}, at=CB_AT)
        trends.save_answer(folder, "get_trend_videos", {"trend_id": f.stem, "page": 2},
                           {"data": videos[half:], "page": 2, "has_more": False}, at=CB_AT)
    tm(ws, "trends", "shortlist", "--run", str(run), "--terms", CB_TERMS, "--today", "2026-11-04")


def cb_b4(ws: Path, run: Path) -> None:
    """The dry run's three concepts' trends scored, each one's Ad Library query saved, the saturation checked."""
    _, trends, _, RunFolder = _engine()
    folder = RunFolder.open(run)
    cand = _cb_candidates()
    scores = {cand["C1"]: {"brand_fit": 4, "persona_fit": 4, "bridge": 5, "lifecycle": 4, "transfer": 4,
                           "sensitivity": 5, "feasibility": 5},
              cand["C2"]: {"brand_fit": 5, "persona_fit": 5, "bridge": 4, "lifecycle": 4, "transfer": 4,
                           "sensitivity": 5, "feasibility": 4},
              cand["C3"]: {"brand_fit": 4, "persona_fit": 5, "bridge": 4, "lifecycle": 3, "transfer": 4,
                           "sensitivity": 4, "feasibility": 5}}
    f = place(ws, run, "03_wip/scores_v01.json", scores, "the trend cards, the persona and the brand profile (eval fixture)")
    tm(ws, "brief", "scores", "--run", str(run), "--file", str(f))
    for query, answer in CB_AD_LIBRARY.items():
        trends.save_answer(folder, "ads_library_search", {"search_terms": query, "ad_reached_countries": ["CA"],
                                                          "ad_active_status": "ACTIVE"}, {"data": answer}, at=CB_AT)
    sat = {"checks": [{"candidate": cand[c], "query": q, "country": "CA", "verdict": v, "advertisers": adv,
                       "own_ads": False, "note": note} for c, q, v, adv, note in CB_SATURATION]}
    f = place(ws, run, "02_research/saturation_v01.json", sat,
              "the ads_library_search answers in 02_research/ad_library/ (eval fixture: the dry run's reading)")
    tm(ws, "brief", "saturation", "--run", str(run), "--file", str(f))


def cb_c1(ws: Path, run: Path) -> None:
    """The dry run's brief (anonymised, with the plugin blocks) as the review pack: no animatics yet (they come at
    D2), then the evidence, the concepts check and the page."""
    brief = _ld_brief()
    for c in brief["concepts"]:
        c.pop("animatic", None)
    place(ws, run, "04_final/brief_pack_v01.json", brief, "the concepts (eval fixture: the dry run's brief)")
    tm(ws, "brief", "evidence", "--run", str(run))
    latest = sorted((run / "04_final").glob("brief_pack_v*.json"))[-1]
    tm(ws, "brief", "check", "--run", str(run), "--file", str(latest), "--stage", "concepts")
    tm(ws, "brief", "page", "--run", str(run))


CB_HOOKS = {"A1": lambda ws, run: (cb_landing(ws, run), cb_a1(ws, run)), "B1": cb_b1, "B2": cb_b2,
            "B3": cb_b3, "B4": cb_b4, "C1": cb_c1}


def cb_drive(ws: Path, run: Path, stop_at: str) -> dict:
    """Do each step's work (CB_HOOKS) and accept each check-in, until `stop_at` is the step to work on."""
    for _ in range(60):
        n = tm(ws, "next", "--run", str(run), ok=(0, 2))
        if n["action"] == "work":
            if n["step"] == stop_at:
                return n
            if n["step"] in CB_HOOKS:
                CB_HOOKS[n["step"]](ws, run)
            tm(ws, "done", n["step"], "--run", str(run))
        elif n["action"] in ("ask", "auto"):
            for cid in n["checkin"]["ids"]:
                extra = ["--by", "rule", "--note", "set by the eval fixture"] if n["action"] == "auto" else []
                tm(ws, "decide", cid, "accept", "--run", str(run), *extra)
        else:
            raise SystemExit(f"never reached {stop_at}: {n}")
    raise SystemExit(f"never reached {stop_at}")


def cb_seed(ws: Path) -> str:
    """One full seed/1 row (every key of seeds.REQUIRED) from a trend research run of 16 October: the
    dry run's "Day _ of _" hook (C1's trend), not checked in paid, valid until 2026-10-30, written with
    seeds.add (today is 2026-11-07, so it has expired)."""
    if f"{ROOT}/engine/src" not in sys.path:
        sys.path.insert(0, f"{ROOT}/engine/src")
    from tm import seeds  # noqa: E402
    tid = _cb_candidates()["C1"]
    card = json.loads((LD_FIX / "cards" / f"{tid}.json").read_text(encoding="utf-8"))
    source_run = "2026-10-16_lucid"
    row = {"schema": "seed/1", "seed_id": f"{source_run}:{tid}", "source": seeds.PB4, "run": source_run,
           "created": "2026-10-16", "category": "lucid dreaming", "sub_category": "dream journals", "market": "CA",
           "trend_id": tid, "kind": card["kind"], "trend_name": card["name"], "bucket": "act_now",
           "band": "top 25%", "paid_level": seeds.NOT_CHECKED,
           "angle": "A numbered diary of a first week of trying: the attempt in the first frame.",
           "risk": "A diary needs a real person on camera every night.", "valid_until": "2026-10-30",
           "report": None, "evidence": f"runs/04-trend-research/{source_run}/02_research/videos/{tid}*.json"}
    seeds.add(ws, {k: row[k] for k in seeds.REQUIRED})
    return row["seed_id"]


CB_PRIVATE = ("voice", "voice_themes.json", "brief_pack_v01.json")   # real people's words: not in the public copy


def cb_main(scn: str, ws: Path) -> tuple[Path, dict]:
    missing = [name for name in CB_PRIVATE if not (LD_FIX / name).exists()]
    if missing:
        raise SystemExit(f"The creative brief evals need the private LD fixtures ({', '.join(missing)} in "
                         f"{LD_FIX}), which the public copy leaves out: they hold real Reddit and Goodreads texts.")
    if scn == "cb_seed_expired":
        seed = cb_seed(ws)
        run = cb_run(ws, "every_step", CB_RUN_ALL, seed=seed)
        return run, cb_drive(ws, run, "B3")
    level, outputs, stop = {
        "cb_at_a1": ("every_step", CB_RUN_ALL, "A1"),
        "cb_at_b1": ("every_step", CB_RUN_ALL, "B1"),
        "cb_at_b2": ("every_step", CB_RUN_ALL, "B2"),
        "cb_at_b3_guess": ("every_step", CB_RUN_ALL, "B3"),
        "cb_at_c1": ("every_step", CB_RUN_ALL, "C1"),
        "cb_at_c1_page_built": ("every_step", CB_RUN_ALL, "C1"),
        "cb_at_c1_no_artifacts": ("every_step", ["review_pack", "page"], "C1"),
    }[scn]
    run = cb_run(ws, level, outputs)
    if scn == "cb_at_a1":
        n = cb_drive(ws, run, "A1")
        cb_landing(ws, run)
        return run, n
    n = cb_drive(ws, run, stop)
    if scn in ("cb_at_c1_page_built", "cb_at_c1_no_artifacts"):
        cb_c1(ws, run)
    return run, n


CB_RUN_ALL = ["review_pack", "briefs", "animatics", "page"]


# --- organic video (PB03) ------------------------------------------------------------------------
# The ExampleEdu walkthrough, anonymised (gen_mocks.py --pb03): an idea run
# `runs/03-organic-ai-video/2026-11-06_exampleedu` for the Polish parenting channel ExampleEdu, built with the
# engine's own commands; its production runs are started by `tm organic start` and renamed
# `2026-11-07_exampleedu-<idea>`. The MCP answers are saved as the collector saves them (trends.save_answer,
# mcp_saves.save); a Replicate record is written as the guard writes it (the sandbox has no key).

OV_FIX = HERE / "fixtures" / "organic"
OV_CREATED = "2026-11-06"                 # the walkthrough's day
OV_PROD_CREATED = "2026-11-07"            # its production runs' day
OV_NAME = "exampleedu"
OV_IDEA = f"{OV_CREATED}_{OV_NAME}"
OV_AT = "2026-11-06T09:00:00+00:00"       # when the walkthrough's TrendsMesh answers were saved
# a made-up channel profile of the walkthrough's shape (00_raw/channel_profile_v02.md typed as channel/1)
OV_PROFILE = {
    "schema": "channel/1", "kind": "channel", "channel": "ExampleEdu", "store": None,
    "platforms": ["tiktok", "youtube", "instagram", "facebook"], "account_type": "creator",
    "audience_language": "pl",
    "context": {"films": "quick videos that turn studies about play and screens into plain advice",
                "topic": "helping parents make sense of their kids' gaming: limits, online safety, picking games, "
                         "what play builds",
                "audience": "mums and dads of school-age kids who play video games",
                "style": "warm, calm, down to earth; cites studies without jargon; never alarmist",
                "performed_links": []},
    "product_role": "not_shown",
    "content_rules": ["no identifiable children on screen", "a source for every claim", "no health claims"],
    "voice": {"narrator_elevenlabs_id": None, "host_description": None, "host_image": None},
    "music": {"folder": None, "index": None},
    "assumptions": ["the audience speaks Polish", "mostly parents aged 30 to 50",
                    "warm, calm, down to earth; never alarmist",
                    "a children's niche that needs care: no identifiable children, a source for every claim, "
                    "no health claims"],
    "confirmed": None,
}
# B2: the bubble's terms and its niche anchors (FLOWS B, lesson 2), in Polish and English
OV_TERMS = "kids,children,parents,parenting,games,gaming,screen time,school,homework,dzieci,rodzice,gry"
OV_ANCHORS = "kids,children,parents,parent,dzieci,rodzice,dziecko"
OV_STACK = {"replicate": "ok", "elevenlabs": "ok", "artifacts": "ok", "browser": "ok"}


def _ov(rel: str):
    return json.loads((OV_FIX / rel).read_text(encoding="utf-8"))


def _redate(run: Path, made: Path, run_id: str, created: str) -> Path:
    """Rename a run the engine dated by the real day to `run_id`, as cb_run does (run.json and the manifest)."""
    if made == run:
        return run
    made.rename(run)
    s = json.loads((run / "run.json").read_text(encoding="utf-8"))
    s.update(run_id=run.name, created=created)
    (run / "run.json").write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")
    man = run / "manifest.md"
    man.write_text(man.read_text(encoding="utf-8").replace(made.name, run.name), encoding="utf-8")
    return run


def ov_run(ws: Path, level: str, outputs: list[str], *, stack: dict | None = None, chat: str = "pl",
           extra: dict | None = None) -> Path:
    """An organic video idea (or week) run made by `tm run new`, dated 2026-11-06, its intake written and
    checked and its stack recorded (A0's work)."""
    made = Path(tm(ws, "run", "new", "--playbook", "organic-video", "--name", OV_NAME)["path"])
    run = _redate(made.with_name(OV_IDEA), made, OV_IDEA, OV_CREATED)
    answers = {"level": level, "outputs": outputs, "chat_language": chat, "audience_language": "pl",
               "channels": ["ExampleEdu"], "output": "script",
               "generation": {"quality_tier": "default", "resolution": "768p", "upscale": "none"},
               "budget": {"per_run_usd": 5, "per_week_usd": 5}, "currency": "USD", **(extra or {})}
    f = place(ws, run, "03_wip/intake_answers_v01.json", answers, "the intake batch, answered by the user (eval fixture)")
    tm(ws, "config", "write", "--run", str(run), "--answers", str(f))
    tm(ws, "config", "check", "--run", str(run))
    st = {**OV_STACK, **(stack or {})}
    tm(ws, "organic", "stack", "--run", str(run), *[x for k in ("replicate", "elevenlabs", "artifacts", "browser")
                                                     for x in (f"--{k}", st[k])])
    return run


def ov_a1(ws: Path, run: Path) -> None:
    f = place(ws, run, "03_wip/channel_exampleedu_v01.json", OV_PROFILE, "the intake answers (eval fixture: "
              "the walkthrough's channel profile v02)")
    tm(ws, "brand", "check", "--run", str(run), "--file", str(f))
    tm(ws, "brand", "save", "--run", str(run), "--file", str(f))


def ov_b1(ws: Path, run: Path) -> None:
    """The walkthrough's 17 searches, saved as the collector saves them."""
    _, trends, _, RunFolder = _engine()
    folder = RunFolder.open(run)
    for n, query in enumerate(_ov("queries.json"), 1):
        cards = _ov(f"trends/search_{n:02d}.json")
        trends.save_answer(folder, "search_trends", {"about": query, "limit": len(cards)}, cards, at=OV_AT)


def ov_b2(ws: Path, run: Path) -> None:
    tm(ws, "trends", "shortlist", "--run", str(run), "--terms", OV_TERMS, "--anchor-terms", OV_ANCHORS,
       "--sound-relevance", "--market-language", "pl", "--recent-days", "7", "--today", OV_CREATED)


def _search_card(tid: str) -> dict | None:
    for f in sorted((OV_FIX / "trends").glob("search_*.json")):
        for c in json.loads(f.read_text(encoding="utf-8")):
            if c["id"] == tid:
                return {k: v for k, v in c.items() if k not in ("rank", "match")}
    return None


def ov_b3(ws: Path, run: Path) -> None:
    """The cards and video pages: the walkthrough's 12 pulled cards and pages, and each of the shortlist's top trends it did
    not pull from its search answer (the card, and its example videos as one page)."""
    _, trends, _, RunFolder = _engine()
    from tm import organic_research  # noqa: E402
    folder = RunFolder.open(run)
    for f in sorted((OV_FIX / "cards").glob("*.json")):
        trends.save_answer(folder, "get_trend", {"trend_id": f.stem}, json.loads(f.read_text(encoding="utf-8")), at=OV_AT)
    for f in sorted((OV_FIX / "videos").glob("*.json")):
        trends.save_answer(folder, "get_trend_videos", {"trend_id": f.stem, "order": "views", "limit": 20},
                           json.loads(f.read_text(encoding="utf-8")), at=OV_AT)
    shortlist = json.loads(sorted((run / "03_wip").glob("trend_shortlist_v*.json"))[-1].read_text(encoding="utf-8"))
    pulled = {f.stem for f in (OV_FIX / "cards").glob("*.json")}
    for row in organic_research.top_trends(shortlist, 12):
        if row["id"] in pulled:
            continue
        card = _search_card(row["id"])
        trends.save_answer(folder, "get_trend", {"trend_id": row["id"]}, card, at=OV_AT)
        trends.save_answer(folder, "get_trend_videos", {"trend_id": row["id"], "order": "views", "limit": 20},
                           {"videos": card.get("examples") or [], "page": 1, "limit": 20,
                            "total": len(card.get("examples") or []), "pages": 1}, at=OV_AT)


def ov_proposals() -> dict:
    """Made-up proposals in the shape of the walkthrough's proposals_v02.json, with the plugin's block on each proposal
    (written by hand: gen_mocks.py --pb03 would bring its texts back)."""
    return _ov("proposals.json")


def ov_c1(ws: Path, run: Path, data: dict | None = None) -> None:
    f = place(ws, run, "03_wip/proposals_v01.json", data or ov_proposals(),
              "the shortlist, the cards and their videos (eval fixture: made-up proposals of the walkthrough's shape)")
    tm(ws, "organic", "proposals", "check", "--run", str(run), "--file", str(f))


def ov_c2(ws: Path, run: Path) -> None:
    tm(ws, "organic", "page", "proposals", "--run", str(run))


OV_BUILT = lambda ws, run: None  # noqa: E731  (C2: the page is already built and published)
OV_HOOKS = {"A1": ov_a1, "B1": ov_b1, "B2": ov_b2, "B3": ov_b3, "C1": ov_c1, "C2": ov_c2}


def ov_drive(ws: Path, run: Path, stop_at: str, hooks: dict | None = None, choices: dict | None = None,
             stop_checkin: str | None = None) -> dict:
    """Do each step's work (OV_HOOKS, then `hooks`) and answer each check-in (`choices`, else accept), until
    `stop_at` is the step to work on, or `stop_checkin` is asked."""
    hooks = {**OV_HOOKS, **(hooks or {})}
    choices = {"reuse_profile": "new", **(choices or {})}
    for _ in range(60):
        n = tm(ws, "next", "--run", str(run), ok=(0, 2))
        if n["action"] == "work":
            if n["step"] == stop_at:
                return n
            if n["step"] in hooks:
                hooks[n["step"]](ws, run)
            tm(ws, "done", n["step"], "--run", str(run))
        elif n["action"] in ("ask", "auto"):
            ids = n["checkin"]["ids"]
            if stop_checkin in ids:
                return n
            for cid in ids:
                extra = ["--by", "rule", "--note", "set by the eval fixture"] if n["action"] == "auto" else []
                tm(ws, "decide", cid, choices.get(cid, "accept"), "--run", str(run), *extra)
                if cid == "profile":
                    tm(ws, "brand", "save", "--run", str(run), "--file", "03_wip/channel_exampleedu_v01.json",
                       "--confirmed")
        else:
            raise SystemExit(f"never reached {stop_at or stop_checkin}: {n}")
    raise SystemExit(f"never reached {stop_at or stop_checkin}")


OV_ALL = gen_mocks.OV_ALL


def ov_published(ws: Path, run: Path, page: str, slug: str, title: str) -> None:
    """A page published as the agent publishes it (pages.md): publish_files' answer saved by the collector,
    then `tm page published` with the version declare_capabilities returned, and `tm page await`."""
    mcp_saves, _, _, RunFolder = _engine()
    folder = RunFolder.open(run)
    built = sorted((run / "04_final").glob(f"{page}_v*"))[-1].name
    mcp_saves.save(folder, "publish_files", {"files": [{"as": "index.html", "path": f"04_final/{built}/index.html"}],
                                             "title": title, "icon": "document"},
                   {"slug": slug, "version": "ver_mock_1", "url": f"https://claude.ai/artifact/{slug}", "read": "owner"},
                   server="claude-artifacts")
    tm(ws, "page", "published", "--run", str(run), "--page", page, "--slug", slug, "--version", "ver_mock_2",
       "--url", f"https://claude.ai/artifact/{slug}")
    tm(ws, "page", "await", "--run", str(run), "--page", page, "--version", "ver_mock_2")


def ov_db(ws: Path, run: Path, slug: str, collection: str, docs: list[dict]) -> None:
    """One person's documents on the page, read with one unfiltered db_list (the cases' mocks' shape,
    gen_mocks._ov_db_text) and saved by the collector."""
    mcp_saves, _, _, RunFolder = _engine()
    text = gen_mocks._ov_db_text("5d", docs)
    mcp_saves.save(RunFolder.open(run), "db_list", {"slug": slug, "collection": collection, "limit": 1000},
                   {"raw": text}, server="claude-artifacts")


def _rename_everywhere(ws: Path, old: str, new: str) -> None:
    """A run renamed from `old` to `new`: its folder, and its name in every text file of the workspace (the idea
    run's starts, the run's own run.json and manifest, the channel's used trends and decisions)."""
    for f in [*ws.glob("runs/*/*/run.json"), *ws.glob("runs/*/*/manifest.md"), *ws.glob("runs/*/*/00_raw/*.json"),
              *ws.rglob("library/**/*.jsonl")]:
        text = f.read_text(encoding="utf-8")
        if old in text:
            f.write_text(text.replace(old, new), encoding="utf-8")
    prod = next(ws.glob(f"runs/*/{old}"))
    prod.rename(prod.with_name(new))
    s = json.loads((prod.with_name(new) / "run.json").read_text(encoding="utf-8"))
    s["created"] = new[:10]
    (prod.with_name(new) / "run.json").write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")


def ov_production(ws: Path, pid: str, level: str, output: str) -> Path:
    """The idea run published, decided on its page (`pid` produce at `level` as `output`, every other idea
    later) and started: the production run of `pid`, renamed 2026-11-07_exampleedu-<pid>."""
    run = ov_run(ws, "every_step", ["proposals"])
    ov_drive(ws, run, "C2")
    ov_c2(ws, run)
    ov_published(ws, run, "proposals", "art_mock_3", "Video ideas: ExampleEdu")
    n = ov_drive(ws, run, "C3", {"C2": OV_BUILT}, stop_checkin="proposals")
    docs = [{"id": p["id"], "data": {"proposal": p["id"], "decision": "produce" if p["id"] == pid else "later",
                                     "level": level, "output": output if p["id"] == pid else "script",
                                     "platforms": OV_ALL, "answers": {}, "note": "",
                                     "updated_at": "2026-11-06T15:00:00.000Z"}, "version": 1}
            for p in ov_proposals()["proposals"]]
    ov_db(ws, run, "art_mock_3", "decisions", docs)
    tm(ws, "organic", "decisions", "--run", str(run), "--page", "proposals")
    tm(ws, "decide", "proposals", "accept", "--run", str(run), "--note", f"{pid} produce (eval fixture)")
    started = tm(ws, "organic", "start", "--run", str(run))["started"]
    tm(ws, "trends", "collect", "off", "--run", str(run), ok=(0, 1, 2))
    tm(ws, "done", "C3", "--run", str(run))
    old = started[0]["run"]
    new = f"{OV_PROD_CREATED}_{old.split('_', 1)[1]}"
    _rename_everywhere(ws, old, new)
    return run.parent / new


def ov_chat(ws: Path, run: Path, lang: str) -> None:
    """The user talks `lang` from here on: the run's chat language, its config's page_lang (as `tm config write`
    sets it from the intake's chat_language). The idea run and the pack stay Polish: the proposals are, and
    `tm organic proposals check` and the pack check want the page language."""
    _, _, _, RunFolder = _engine()
    from tm import config  # noqa: E402
    folder = RunFolder.open(run)
    cfg = config.load(folder)
    cfg.update(page_lang=lang, page_lang_note=None)
    config.save(folder, cfg)
    tm(ws, "config", "check", "--run", str(run))


def _today() -> str:
    from datetime import date
    return date.today().isoformat()


def ov_prices(ws: Path, run: Path) -> str:
    """E1's live prices as `tm tool replicate_price` writes them, checked today (the fixture's day): the
    pet store's price entries for the M5 pack's models."""
    rel = f"02_research/models/prices_{_today()}_v01.json"
    place(ws, run, rel, [{**e, "checked": _today()} for e in _ov("prices.json")],
          "tm tool replicate_price openai/gpt-image-2 minimax/h3 prunaai/p-video-upscale (eval fixture: the pet "
          "store's saved prices, dated today)")
    return rel


def ov_m5_pack(prices: str) -> dict:
    """The M5 pack (the engine tests' typing of the walkthrough, its texts made up) with its price lines on today's
    price file and its rankings read today."""
    pack = _ov("m5_pack.json")
    pack["id"] = "m5"
    for line in pack["cost"]["lines"]:
        line.update(price_file=prices, checked=_today())
    for m in pack["models"]:
        m["ranking"]["date"] = _today()
    return pack


def ov_d1(ws: Path, run: Path) -> None:
    """D1 of an AI video: this run's stack with the ElevenLabs credits read, and the recipe checked."""
    tm(ws, "organic", "stack", "--run", str(run), "--replicate", "ok", "--elevenlabs", "ok", "--artifacts", "ok",
       "--browser", "ok")
    pack = ov_m5_pack(f"02_research/models/prices_{_today()}_v01.json")
    recipe = {k: pack[k] for k in ("schema", "id", "lang", "title", "channel", "production", "sound_led", "sections",
                                   "product", "host", "script", "taste", "style_spec")}
    f = place(ws, run, "03_wip/pack_v01.json", recipe, "00_raw/proposal.json and the channel profile (eval fixture)")
    tm(ws, "organic", "pack", "check", "--run", str(run), "--file", str(f), "--stage", "recipe")


def ov_e1(ws: Path, run: Path) -> None:
    ov_prices(ws, run)


def ov_m5_pack_sized(prices: str) -> dict:
    """The M5 pack with its take sized as flow.md D1 says: 33 words at about 2.9 words a second (11.5 s) and 1.5 s
    after the last line, one 13 s take (the 15 s take of the walkthrough came out slow, at 2.47 words a second:
    an agent that reads the sizing rule re-plans the 15 s pack before showing it, as one run of
    ov_pack_cost_with_dates did). The take's line, the totals and the resolution options are priced from the
    same price file: 13 s at $0.08 (768P), $0.13 (2K), and Pruna's 1080p upscale at $0.02 a second."""
    pack = ov_m5_pack(prices)
    seconds = 13
    for line, at in zip(pack["script"]["lines"], ([0, 3], [3, 6], [6, 9.5], [9.5, 11.5])):
        line["at"] = at
    pack["script"]["seconds"] = seconds
    pack["sections"][0]["to"] = seconds
    pack["stages"][1]["items"][0]["seconds"] = seconds
    take = next(line for line in pack["cost"]["lines"] if line["item"] == "take")
    take.update(units=seconds, cost=round(0.08 * seconds, 2), what=take["what"].replace("15 s", f"{seconds} s"))
    pack["cost"]["totals"]["ai_usd"] = round(sum(line["cost"] for line in pack["cost"]["lines"]), 2)
    costs = {"768p": round(0.08 * seconds, 2), "1080p": round(0.13 * seconds, 2),
             "768p_pruna": round((0.08 + 0.02) * seconds, 2)}
    for option in pack["resolution"]["options"]:
        option["cost"] = costs[option["id"]]
    return json.loads(json.dumps(pack, ensure_ascii=False).replace("ujęcie 15 s", f"ujęcie {seconds} s")
                      .replace("mową (15 s)", f"mową ({seconds} s)"))


def ov_e2(ws: Path, run: Path) -> None:
    """E2 as the agent leaves it: the pack sized as D1 says (`ov_m5_pack_sized`, 13 s: the pack check refuses the
    walkthrough's 15 s take as slow since Task 21's fix round 2), checked."""
    f = place(ws, run, "03_wip/pack_v02.json", ov_m5_pack_sized(f"02_research/models/prices_{_today()}_v01.json"),
              "the recipe, the models' recipes and rankings, 02_research/models/ prices (eval fixture: the M5 pack, "
              "its take sized at 2.9 words a second)")
    tm(ws, "organic", "pack", "check", "--run", str(run), "--file", str(f), "--stage", "pack")


PNG_1PX = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/58BAwAI/AL+hc2rNAAAAABJRU5ErkJggg==")


def ov_record(ws: Path, run: Path, stem: str, model: str, outputs: dict[str, bytes], cost: float) -> None:
    """A paid item run as the guard leaves it (tm tool replicate_run: the record, its outputs, the spend); the
    sandbox has no Replicate key, so the record is written here, its manifest rows marked as the fixture's."""
    record = {"model": model, "input": {}, "file_encoding": "url", "status": "succeeded",
              "prediction_id": f"pred_mock_{stem}", "outputs": list(outputs)}
    place(ws, run, f"03_wip/{stem}.run.json", record, f"eval fixture: the record the guard wrote for {stem}")
    for name, data in outputs.items():
        place(ws, run, f"03_wip/{name}", data, f"eval fixture: {model}'s output for {stem}")
    tm(ws, "budget", "spend", "ai_usd", str(cost), "--run", str(run), "--what", f"{model} {stem} (eval fixture)")


def ov_f1(ws: Path, run: Path) -> None:
    ov_record(ws, run, "host_v01", "openai/gpt-image-2", {"host_v01_0.png": PNG_1PX, "host_v01_1.png": PNG_1PX}, 0.26)
    tm(ws, "organic", "pick", "--run", str(run), "--stage", "images", "--name", "host", "--file", "03_wip/host_v01_0.png",
       "--reason", "realism, one face, no text, inside the safe zone (eval fixture)")


def ov_take_qa(match: float, wps: float) -> dict:
    """take_qa's answer for the 13 s take (engine/tests/test_organic_qa.py QA_PASS, its speech 11.74 s), with `match` and
    `wps`; its cuts sit at the 13 s pack's brackets, lines 3 and 4 (6 and 9.5 s, `ov_m5_pack_sized`; PR E r4)."""
    return {"take": "03_wip/take_v01_0.mp4", "transcript": "03_wip/qa/take_v01_0_transcript_v01.json",
            "match": match, "words": round(11.74 * wps), "speech_seconds": 11.74, "wps": wps, "tail_silence": 1.26,
            "cuts": [5.8, 9.54], "cut_offsets": [{"bracket": 6.0, "cut": 5.8, "offset": -0.2},
                                                 {"bracket": 9.5, "cut": 9.54, "offset": 0.04}],
            "lufs": -9.9, "peak": 0.1, "contact_sheet": "03_wip/qa/take_v01_0_contact_v01.png"}


def _heard(match: float) -> dict:
    """take_qa's transcript (tm.tools.transcribe's shape): the pack's script, word by word over 11.74 s, with
    every word past the share `match` of them heard as another word (Whisper mishearing the Polish)."""
    words = " ".join(line["text"] for line in _ov("m5_pack.json")["script"]["lines"]).split()
    keep = round(len(words) * match)
    step = 11.74 / len(words)
    heard = [{"word": w if i < keep else "yyy", "start": round(i * step, 2), "end": round((i + 1) * step, 2)}
             for i, w in enumerate(words)]
    return {"language": "pl", "segments": [{"start": 0.0, "end": 11.74, "text": " ".join(h["word"] for h in heard),
                                            "words": heard}]}


def _contact(ws: Path) -> bytes:
    """take_qa's contact sheet: 6 frames of the clip, 3x2 (ffmpeg)."""
    out = ws / ".contact.png"
    _clip(ws)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ws / ".clip.mp4"), "-vf",
                    "fps=3,scale=360:640,tile=3x2", "-frames:v", "1", str(out)], check=True, capture_output=True)
    return out.read_bytes()


def ov_take(ws: Path, run: Path, match: float, wps: float) -> None:
    ov_record(ws, run, "take_v01", "minimax/h3", {"take_v01_0.mp4": _clip(ws)}, 1.04)
    place(ws, run, "03_wip/qa/take_v01_0_transcript_v01.json", _heard(match),
          "tm tool take_qa (eval fixture: the take's transcript)")
    place(ws, run, "03_wip/qa/take_v01_0_contact_v01.png", _contact(ws), "tm tool take_qa (eval fixture: the contact sheet)")
    place(ws, run, "03_wip/qa/take_v01_0_qa_v01.json", ov_take_qa(match, wps),
          "tm tool take_qa 03_wip/take_v01_0.mp4 --lang pl --script 03_wip/pack_v02.json --brackets 6,9.5 (eval fixture)")


def _clip(ws: Path) -> bytes:
    """A 2 s 1080x1920 H.264 + AAC 48 kHz clip made with ffmpeg (a stand-in for a take: its pixels are a test
    pattern). The production scenarios need ffmpeg on the host: without it the fixture stops here."""
    out = ws / ".clip.mp4"
    if not out.exists():
        try:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=2",
                            "-f", "lavfi", "-i", "sine=f=440:r=48000:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-ar", "48000", "-shortest", str(out)], check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise SystemExit(f"scaffold: the production scenarios need ffmpeg on the host to make a stand-in take "
                             f"({exc})") from None
    return out.read_bytes()


def _cover_png(ws: Path) -> bytes:
    """A 1080x1920 PNG, the clip's first frame (ffmpeg), for the cover."""
    out = ws / ".cover.png"
    clip = ws / ".clip.mp4"
    _clip(ws)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-frames:v", "1", str(out)], check=True,
                   capture_output=True)
    return out.read_bytes()


def ov_f2_pass(ws: Path, run: Path) -> None:
    ov_take(ws, run, 0.909, 2.9)
    tm(ws, "organic", "pick", "--run", str(run), "--stage", "takes", "--name", "take", "--file", "03_wip/take_v01_0.mp4",
       "--reason", "transcript 91% of the script, cuts on time, one face, no text, usable loudness (eval fixture)")


def _deliver(ws: Path, run: Path, *args: str) -> dict:
    """`tm tool deliver`, run as the base tier runs it (python -m tm.tools.deliver), with the host's ffmpeg: the
    sandbox has no tier environment."""
    env = {**os.environ, "PYTHONPATH": f"{ROOT}/engine/src", "PYTHONDONTWRITEBYTECODE": "1", "TM_WORKSPACE": str(ws)}
    p = subprocess.run([PY, "-m", "tm.tools.deliver", args[0], "--run", str(run), *args[1:], "--json"], env=env,
                       cwd=ws, capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit(f"deliver {' '.join(args)} -> {p.returncode}\n{p.stdout}\n{p.stderr}")
    return json.loads(p.stdout.strip().splitlines()[-1])


def ov_g1(ws: Path, run: Path) -> None:
    """The edit's render (the take as it is), the final at -14 LUFS, its upload copy and its cover JPG."""
    place(ws, run, "03_wip/renders/edit_v01.mp4", (run / "03_wip" / "take_v01_0.mp4").read_bytes(),
          "tm render video --comp OrganicCaptions --props 03_wip/edit_v01.props.json (eval fixture: the take)")
    final = _deliver(ws, run, "finish", "03_wip/renders/edit_v01.mp4", "--id", "m5")
    if not final.get("outputs"):
        raise SystemExit(f"deliver finish named no final: {final}")
    _deliver(ws, run, "upload", final["outputs"][0])
    place(ws, run, "04_final/kits/cover_m5_v01.png", _cover_png(ws),
          "tm render still --comp OrganicCaptions --props 03_wip/cover_m5_v01.props.json (eval fixture)")
    _deliver(ws, run, "cover", "04_final/kits/cover_m5_v01.png")


def ov_prod_drive(ws: Path, run: Path, stop_at: str, hooks: dict) -> dict:
    """A production run: each step's work (`hooks`) and each check-in answered (the pack approved with the run's
    budget, by rule where the engine says so), until `stop_at` is the step to work on."""
    for _ in range(40):
        n = tm(ws, "next", "--run", str(run), ok=(0, 2))
        if n["action"] == "work":
            if n["step"] == stop_at:
                return n
            if n["step"] in hooks:
                hooks[n["step"]](ws, run)
            tm(ws, "done", n["step"], "--run", str(run))
        elif n["action"] in ("ask", "auto"):
            for cid in n["checkin"]["ids"]:
                extra = ["--by", "rule", "--note", "set by the eval fixture"] if n["action"] == "auto" else []
                tm(ws, "decide", cid, "approve" if cid == "pack" else "accept", "--run", str(run), *extra)
                if cid == "pack":
                    tm(ws, "budget", "approve", "ai_usd", "5", "--run", str(run))
        else:
            raise SystemExit(f"never reached {stop_at}: {n}")
    raise SystemExit(f"never reached {stop_at}")


OV_VIDEO_HOOKS = {"D1": ov_d1, "E1": ov_e1, "E2": ov_e2, "F1": ov_f1, "F2": ov_f2_pass, "G1": ov_g1}


def ov_script_d1(ws: Path, run: Path) -> None:
    place(ws, run, "03_wip/script_m5_en_v01.json", {**_ov("m5_script_en.json"), "id": "m5"},
          "00_raw/proposal.json, the cards and their videos; the user asked for the English version (eval "
          "fixture: a made-up M5 script to film)")


def ov_week_plan() -> dict:
    """A made-up week plan in the shape of the walkthrough's week_v01.json, with the plugin blocks, its week the one after the
    fixture's day (the check wants the coming week) and the reserve r2 (the Switch 2 host video) priced at 1080p
    with two takes, $3.26: swapped in for Monday it makes the week $6.20 of $5."""
    from datetime import date, timedelta
    week = _ov("week.json")
    today = date.today()
    monday = today + timedelta(days=7 - today.weekday())
    week["week"] = f"{monday.isoformat()}/{(monday + timedelta(days=6)).isoformat()}"
    offsets = {"pon": 0, "wt": 1, "śr": 2, "czw": 3, "pt": 4, "sob": 5, "niedz": 6}
    for slot in week["slots"]:
        d = monday + timedelta(days=offsets[slot["day"]])
        slot["date"] = f"{d.day}.{d.month:02d}"
    week["reserves"][1]["cost_video"] = 3.26
    return week


def ov_week_i2(ws: Path, run: Path) -> None:
    _, trends, _, RunFolder = _engine()
    folder = RunFolder.open(run)
    for tid in {t["id"] for i in [*ov_week_plan()["slots"], *ov_week_plan()["reserves"]] for t in i["plugin"]["trends"]}:
        if not (OV_FIX / "cards" / f"{tid}.json").is_file():
            trends.save_answer(folder, "get_trend", {"trend_id": tid}, _search_card(tid), at=OV_AT)
    f = place(ws, run, "03_wip/week_v01.json", ov_week_plan(), "the shortlist and the cards (eval fixture: a "
              "made-up week plan of the walkthrough's shape, dated the coming week)")
    tm(ws, "organic", "week", "check", "--run", str(run), "--file", str(f))
    tm(ws, "organic", "page", "week", "--run", str(run))
    ov_published(ws, run, "week", "art_mock_5", "Week plan: ExampleEdu")


def ov_main(scn: str, ws: Path) -> tuple[Path | None, dict | None]:
    if scn == "ov_at_a1":
        return None, None
    if scn == "ov_no_replicate":
        run = ov_run(ws, "every_step", ["proposals"], stack={"replicate": "missing", "artifacts": "missing"}, chat="en")
        return run, ov_drive(ws, run, "C1")
    if scn == "ov_at_c2_published":
        run = ov_run(ws, "every_step", ["proposals"])
        ov_drive(ws, run, "C2")
        ov_c2(ws, run)
        ov_published(ws, run, "proposals", "art_mock_3", "Video ideas: ExampleEdu")
        return run, ov_drive(ws, run, "C3", {"C2": OV_BUILT}, stop_checkin="proposals")
    if scn == "ov_at_c2_no_artifacts":
        run = ov_run(ws, "every_step", ["proposals"], stack={"artifacts": "missing"})
        n = ov_drive(ws, run, "C2")
        ov_c2(ws, run)
        return run, n
    if scn == "ov_week_at_i2":
        run = ov_run(ws, "big_calls", ["weekly_plan"], extra={"output": "weekly_pack", "weekly": {"contents": "mix"}})
        n = ov_drive(ws, run, "I2")
        ov_week_i2(ws, run)
        return run, n
    if scn == "ov_at_e3_script":
        prod = ov_production(ws, "m5", "every_step", "script")
        return prod, ov_prod_drive(ws, prod, "E3", {"D1": ov_script_d1})
    if scn == "ov_at_g2_kit":   # the brief's "English chat": the user talks English from G2 on
        prod = ov_production(ws, "m5", "hands_off", "video")
        n = ov_prod_drive(ws, prod, "G2", OV_VIDEO_HOOKS)
        ov_chat(ws, prod, "en")
        return prod, n
    prod = ov_production(ws, "m5", "hands_off", "video")
    if scn == "ov_at_e2_m5":
        n = ov_prod_drive(ws, prod, "E2", OV_VIDEO_HOOKS)
        place(ws, prod, "03_wip/pack_v02.json", ov_m5_pack_sized(f"02_research/models/prices_{_today()}_v01.json"),
              "the recipe, the models' recipes and rankings, 02_research/models/ prices (eval fixture: the M5 pack, "
              "its take sized at 2.9 words a second)")
        return prod, n
    if scn == "ov_at_f2_failed_take":
        n = ov_prod_drive(ws, prod, "F2", OV_VIDEO_HOOKS)
        ov_take(ws, prod, 0.72, 2.4)
        return prod, n
    raise SystemExit(f"unknown scenario {scn}")


# --- main ------------------------------------------------------------------------------------------

PLANS_OFFER = {"plans": [{"code": "human", "name": "Human", "monthlyPriceUsd": 0},
                         {"code": "agent", "name": "Agent", "monthlyPriceUsd": 99},
                         {"code": "swarm", "name": "AI Swarm", "monthlyPriceUsd": 2000}],
               "offer": {"plans": ["agent", "swarm"], "freeMonths": 1}}

RECUT_LIMITS = {"recut": {"max_level": 2}, "diagnosis": {"structural_recut": False}}


def main(scn: str, ws: Path) -> int:
    if scn == "plans_offer":
        (ws / ".plans.json").write_text(json.dumps(PLANS_OFFER), encoding="utf-8")
        return 0
    if scn == "at_a1":
        run = new_run(ws, ["creative_brief"])
        n = drive(ws, run, "A1")
    elif scn == "at_a2_hook":
        run = new_run(ws, ["creative_brief"])
        n = drive(ws, run, "A2", scn="hook")
    elif scn == "at_d2_no_budget":
        # Hands-off cannot be chosen at intake without the AI budget (tm config check says so), so the
        # run starts at Check every step and the user switches level later, as the case's prompt says.
        run = new_run(ws, ["creative_brief", "ai_video"], level="every_step")
        n = drive(ws, run, "D2", scn="hook")
    elif scn == "at_a5_hook":
        run = new_run(ws, ["creative_brief"], level="every_step")
        n = drive(ws, run, "A5", scn="hook")
    elif scn == "at_a1a_middle_ladder":
        run = new_run(ws, ["creative_brief", "edited_video"], level="every_step")
        n = drive(ws, run, "A1a", scn="middle_ladder")
    elif scn in ("at_a1a_ad3_structural", "at_a1a_ad3_structural_ask"):
        level = "hands_off" if scn == "at_a1a_ad3_structural" else "every_step"
        run = new_run(ws, ["creative_brief", "edited_video"], level=level, extra=RECUT_LIMITS)
        n = drive(ws, run, "A1a", scn="ad3")
    elif scn == "at_cr4_ad3":
        run, n = recut_run(ws, "ad3", "ad3", "CR4", outputs=["edited_video"], take_structural=True,
                           g3r=G3R_NOTES["ad3"],
                           extra_hooks={"CR3": lambda ws, run: (middle_diagnosis(ws, run, "ad3", "v02"),
                                                                music_take(ws, run))})
    elif scn == "at_cr4_ad2":
        run, n = recut_run(ws, "ad2", "middle_ladder", "CR4", outputs=["edited_video"], g3r=G3R_NOTES["ad2"],
                           extra_hooks={"CR3": lambda ws, run: middle_diagnosis(ws, run, "ad2", "v02")})
    elif scn == "at_cr3_exampletravel":
        run, n = recut_run(ws, "exampletravel", "middle_ladder", "CR3", outputs=["edited_video"])
    elif scn == "at_e1_shorter":
        def cr4(ws: Path, run: Path) -> None:
            music_take(ws, run)
            r1_15s_checked(ws, run)
        run, n = recut_run(ws, "ad3", "middle_ladder", "E1", outputs=["edited_video", "live_test"],
                           budget={"test_per_day": 2500, "test_days": 14},
                           g3r="Variant kept: R1-15s (change recut_shorter, level 0): the 15 s cut (causes 3, 6).",
                           extra_hooks={"CR4": cr4})
    elif scn.startswith("tr_"):
        run, n = tr_main(scn, ws)
    elif scn.startswith("cb_"):
        run, n = cb_main(scn, ws)
    elif scn.startswith("ov_"):
        run, n = ov_main(scn, ws)
        if run is None:
            return 0
    else:
        raise SystemExit(f"unknown scenario {scn}")
    print(json.dumps({"run": str(run.relative_to(ws)), "next": n}, indent=1), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], Path(sys.argv[2]).resolve()))
