"""`tm tool <name>`: the engine side. Runs the tool in its tier's pixi environment, keys in env only."""

import json
import subprocess
from pathlib import Path

import pytest

import tm.tools as tools
from tm import flow, state
from tm.cli import main

TOKEN = "r8_TEST_token_never_printed_0123456789"
XI = "xi_TEST_key_never_printed_0123456789"


@pytest.fixture
def engine(tmp_path, monkeypatch):
    root = tmp_path / "plugin root" / "Łukasz"
    data = tmp_path / "plugin data"
    (root / "env").mkdir(parents=True)
    data.mkdir()
    (data / "secrets.env").write_text(f"REPLICATE_API_TOKEN={TOKEN}\nELEVENLABS_API_KEY={XI}\n")
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(root))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(data))
    monkeypatch.setenv("REPLICATE_API_TOKEN", "stale-token-from-the-shell")
    monkeypatch.setattr(tools.paths, "pixi_bin", lambda: tmp_path / "pixi")
    monkeypatch.setattr(tools.paths, "pixi_env", lambda: {"PIXI_HOME": "h", "PIXI_NO_PATH_UPDATE": "1"})
    installed = {"base", "breakdown", "voice", "ai"}
    monkeypatch.setattr(tools.envtiers, "installed", lambda tier: tier in installed)
    calls = []
    child = {"code": 0, "report": None}

    def fake_run(argv, **kw):
        calls.append((argv, kw))
        if child["report"] is not None:  # what the tool tells the engine about money
            Path(kw["env"]["TM_COST_REPORT"]).write_text(json.dumps(child["report"]))
        return subprocess.CompletedProcess(argv, child["code"])

    monkeypatch.setattr(tools.subprocess, "run", fake_run)
    return {"root": root, "data": data, "calls": calls, "installed": installed, "child": child}


def _budget(run, kind, amount):
    """An approved budget, as the user's yes at the spending check-in leaves it."""
    s = state.load(run)
    s.budgets[kind] = amount
    state.save(run, s)


@pytest.fixture
def run(tmp_path):
    from datetime import date

    from tm.runfolder import RunFolder

    return RunFolder.create(tmp_path / "Moje reklamy", "ad", date(2026, 11, 5))


def test_runs_tool_in_its_tier_env_with_argv_list(engine):
    video = "C:\\Users\\Łukasz Nowak\\Desktop\\Moje reklamy\\ad 1.mp4"
    assert main(["tool", "teardown", "--run", "runs/x y", video, "--every-s", "0.5"]) == 0
    (argv, kw), = engine["calls"]
    assert argv == [str(engine["root"].parent.parent / "pixi"), "run", "--as-is", "--manifest-path",
                    str(engine["root"] / "env" / "pixi.toml"), "-e", "breakdown",
                    "python", "-m", "tm.tools.teardown", "--run", "runs/x y", video, "--every-s", "0.5"]
    assert not kw.get("shell")
    assert kw["env"]["PIXI_HOME"] == "h"


def test_key_goes_to_child_env_from_secrets_never_argv(engine, run):
    _budget(run, "ai_usd", 5)
    assert main(["tool", "replicate_run", "--run", str(run.path), "spec.json", "--cost", "0.5"]) == 0
    (argv, kw), = engine["calls"]
    assert "-e" in argv and argv[argv.index("-e") + 1] == "ai"
    assert kw["env"]["REPLICATE_API_TOKEN"] == TOKEN  # from secrets.get, not the shell
    assert "ELEVENLABS_API_KEY" not in kw["env"]  # only the key this tool needs
    assert all(TOKEN not in a for a in argv)


def test_elevenlabs_gets_only_its_key(engine, monkeypatch, run):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "stale")
    _budget(run, "voice_credits", 2000)
    args = ["isolate", "--run", str(run.path), "in.wav", "--cost", "1000"]
    assert main(["tool", "elevenlabs", *args]) == 0
    (argv, kw), = engine["calls"]
    assert kw["env"]["ELEVENLABS_API_KEY"] == XI
    assert "REPLICATE_API_TOKEN" not in kw["env"]
    assert argv[argv.index("-m") + 1:] == ["tm.tools.elevenlabs", *args]


def test_missing_key_stops_before_running(engine, capsys):
    (engine["data"] / "secrets.env").write_text("ELEVENLABS_API_KEY=x\n")
    assert main(["tool", "replicate_run", "--run", "r", "spec.json"]) == 2
    assert engine["calls"] == []
    out = capsys.readouterr().out
    assert "Replicate" in out and "continues from the same place" in out


def test_tier_not_installed_stops_and_installs_nothing(engine, capsys):
    engine["installed"].discard("voice")
    assert main(["tool", "vo_qa", "--run", "r", "a.wav", "b.wav"]) == 2
    assert engine["calls"] == []
    out = capsys.readouterr().out
    assert "tm env install voice" in out and "continues from the same place" in out


# --- paid tools: the budget guard (ruling 2) -------------------------------------------------

def test_paid_tool_without_approval_stops_and_runs_nothing(engine, run, capsys):
    assert main(["tool", "replicate_run", "--run", str(run.path), "spec.json", "--cost", "0.5", "--json"]) == 2
    assert engine["calls"] == []
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "stop" and "no budget is approved" in out["message"]
    assert state.load(run).spend == {}


def test_paid_tool_on_a_stopped_run_runs_nothing(engine, run, capsys):
    """Final review I1: an open stop (a red R8 item, a file to upload) holds every paid call."""
    _budget(run, "ai_usd", 5)
    flow.stop(run, "upload_by_hand", "The videos could not be sent to Meta.", "Upload them by hand.")
    assert main(["tool", "replicate_run", "--run", str(run.path), "spec.json", "--cost", "0.5", "--json"]) == 2
    assert engine["calls"] == []
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "stop" and "nothing was spent" in out["message"]
    assert state.load(run).spend == {}


def test_paid_tool_needs_run_and_a_numeric_cost(engine, run, capsys):
    _budget(run, "ai_usd", 5)
    for args in (["--run", str(run.path), "spec.json"], ["--run", str(run.path), "spec.json", "--cost", "cheap"],
                 ["--run", str(run.path), "spec.json", "--cost", "0"], ["spec.json", "--cost", "1"]):
        assert main(["tool", "replicate_run", *args, "--json"]) == 1
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "error" and "--cost" in out["message"]
    assert engine["calls"] == [] and state.load(run).spend == {}


def test_approved_spend_is_recorded_before_the_tool_runs(engine, run):
    _budget(run, "ai_usd", 5)
    seen = []
    engine["child"]["report"] = {"spent": True, "actual": None}  # Replicate: actual unknown
    original = tools.subprocess.run

    def check(argv, **kw):
        seen.append(state.load(run).spend.get("ai_usd"))  # what was recorded when the child started
        return original(argv, **kw)

    tools.subprocess.run = check
    try:
        assert main(["tool", "replicate_run", "--run", str(run.path), "spec.json", "--cost", "0.5"]) == 0
    finally:
        tools.subprocess.run = original
    assert seen == [0.5] and state.load(run).spend == {"ai_usd": 0.5}


def test_actual_credits_reconcile(engine, run):
    _budget(run, "voice_credits", 2000)
    engine["child"]["report"] = {"spent": True, "actual": 640}
    assert main(["tool", "elevenlabs", "tts", "--run", str(run.path), "--voice-id", "v", "--text", "x",
                 "--cost", "900"]) == 0
    assert state.load(run).spend == {"voice_credits": 640}


def test_nothing_spent_gives_the_estimate_back(engine, run):
    _budget(run, "voice_credits", 2000)
    engine["child"].update(code=2, report={"spent": False, "actual": None})
    assert main(["tool", "elevenlabs", "isolate", "--run", str(run.path), "a.wav", "--cost", "900"]) == 2
    assert state.load(run).spend == {"voice_credits": 0.0}


def test_no_word_from_the_tool_keeps_the_estimate(engine, run):
    _budget(run, "ai_usd", 5)
    engine["child"]["code"] = 1  # crashed without a report
    assert main(["tool", "replicate_run", "--run", str(run.path), "spec.json", "--cost", "0.5"]) == 1
    assert state.load(run).spend == {"ai_usd": 0.5}


def test_overrun_after_the_fact_is_recorded_and_stops_the_run(engine, run, capsys):
    _budget(run, "voice_credits", 1000)
    engine["child"]["report"] = {"spent": True, "actual": 1300}
    assert main(["tool", "elevenlabs", "tts", "--run", str(run.path), "--voice-id", "v", "--text", "x",
                 "--cost", "900"]) == 2
    s = state.load(run)
    assert s.spend == {"voice_credits": 1300} and s.status == "stopped"
    assert "more than the estimated" in capsys.readouterr().out


def test_free_actions_need_no_budget(engine, run):
    assert main(["tool", "elevenlabs", "history-search", "--run", str(run.path), "Zimowa"]) == 0
    assert main(["tool", "replicate_run", "--run", str(run.path), "--resume", "03_wip/x_v01.run.json"]) == 0
    assert len(engine["calls"]) == 2 and state.load(run).spend == {}


@pytest.mark.parametrize("resume", [["--resume", ""], ["--resume", "  "], ["--resume="], ["--res", "x.run.json"]])
def test_an_empty_or_abbreviated_resume_is_paid(engine, run, resume, capsys):
    # the bypass from review round 2: a literal --resume token used to make any call free
    assert main(["tool", "replicate_run", "--run", str(run.path), "spec.json", *resume, "--cost", "0.5",
                 "--json"]) == 2
    assert engine["calls"] == [] and json.loads(capsys.readouterr().out)["status"] == "stop"


@pytest.mark.parametrize("resume", ["", " "])
def test_an_empty_resume_as_the_first_argument_is_paid(engine, run, resume, capsys):
    assert main(["tool", "replicate_run", "--resume", resume, "--run", str(run.path), "spec.json",
                 "--cost", "0.5", "--json"]) == 2
    assert engine["calls"] == [] and json.loads(capsys.readouterr().out)["status"] == "stop"


@pytest.mark.parametrize("args", [["--resume", "x", "isolate"], ["--run", "R", "isolate"], ["nope"], []])
def test_an_option_or_unknown_action_is_never_free_for_elevenlabs(args):
    assert tools.TOOLS["elevenlabs"].kind_for(args) == "voice_credits"
    assert tools.TOOLS["elevenlabs"].kind_for(["history-search", "x"]) is None


def test_overrun_after_the_fact_is_a_stop_with_one_json_object(engine, run, capsys):
    _budget(run, "voice_credits", 1000)
    engine["child"]["report"] = {"spent": True, "actual": 1300}
    original = tools.subprocess.run

    def child_answers(argv, **kw):
        original(argv, **kw)  # writes the cost report
        assert kw.get("stdout") == subprocess.PIPE  # a paid tool's answer is held back
        return subprocess.CompletedProcess(argv, 0, stdout='{"status": "done", "credits_used": 1300}\n')

    tools.subprocess.run = child_answers
    try:
        assert main(["tool", "elevenlabs", "tts", "--run", str(run.path), "--voice-id", "v", "--text", "x",
                     "--cost", "900", "--json"]) == 2
    finally:
        tools.subprocess.run = original
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    answer = json.loads(out[0])
    assert answer["status"] == "stop" and "more than the estimated" in answer["message"]
    assert answer["result"] == {"status": "done", "credits_used": 1300}


@pytest.mark.parametrize("actual", [-250, "lots", float("inf"), True])
def test_an_unusable_actual_cost_keeps_the_estimate(engine, run, actual, capsys):
    _budget(run, "voice_credits", 2000)
    engine["child"]["report"] = {"spent": True, "actual": actual}
    assert main(["tool", "elevenlabs", "tts", "--run", str(run.path), "--voice-id", "v", "--text", "x",
                 "--cost", "900"]) == 0
    assert state.load(run).spend == {"voice_credits": 900}
    assert "unusable cost" in capsys.readouterr().err


# --- one JSON object with --json (finding 4) -------------------------------------------------

def test_engine_stops_print_one_json_object(engine, capsys, monkeypatch):
    engine["installed"].discard("voice")
    assert main(["tool", "vo_qa", "--run", "r", "a", "b", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "stop"
    (engine["data"] / "secrets.env").write_text("")
    assert main(["tool", "replicate_run", "--run", "r", "s.json", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "stop"

    def boom(argv, **kw):
        raise OSError("pixi is missing")

    monkeypatch.setattr(tools.subprocess, "run", boom)
    assert main(["tool", "teardown", "--run", "r", "v.mp4", "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "error" and "pixi is missing" in out["message"]


def test_child_exit_code_is_relayed(engine, monkeypatch):
    monkeypatch.setattr(tools.subprocess, "run", lambda argv, **kw: subprocess.CompletedProcess(argv, 2))
    assert main(["tool", "transcribe", "--run", "r", "a.mp4"]) == 2


def test_unknown_tool_is_an_error(engine):
    assert main(["tool", "nope"]) == 1
    assert engine["calls"] == []


def test_every_tool_has_a_tier():
    assert set(tools.TOOLS) == {"transcribe", "speaker_sim", "inpaint_mode", "inpaint", "replicate_run",
                                "elevenlabs", "teardown", "reframe", "vo_qa", "ffmpeg", "recut",
                                "recut_qa", "segment_map", "replicate_price", "music_index", "take_qa", "deliver",
                                "music_fetch", "cover_fit", "layer_check", "site", "sfx_fetch"}
    assert {n: t.tier for n, t in tools.TOOLS.items()} == {
        "transcribe": "breakdown", "teardown": "breakdown", "inpaint_mode": "breakdown", "inpaint": "breakdown",
        "recut": "breakdown",
        "recut_qa": "breakdown", "segment_map": "breakdown", "music_index": "breakdown",
        "music_fetch": "breakdown", "cover_fit": "breakdown",
        "take_qa": "breakdown", "layer_check": "breakdown",
        "site": "base", "sfx_fetch": "base",
        "reframe": "base", "ffmpeg": "base", "replicate_price": "base", "deliver": "base", "speaker_sim": "voice", "vo_qa": "voice", "elevenlabs": "voice",
        "replicate_run": "ai"}


# --- issue #66 and #54: the estimate in the child, the credits read on the base tier, the empty cert dir --------

def test_a_paid_call_tells_the_tool_its_approved_estimate(engine, run):
    """#66 point 4: the tool compares what is left with the estimate before paying, and names it in a refusal."""
    _budget(run, "voice_credits", 2000)
    assert main(["tool", "elevenlabs", "tts", "--run", str(run.path), "--voice-id", "v", "--text", "t",
                 "--cost", "1200"]) == 0
    (argv, kw), = engine["calls"]
    assert kw["env"]["TM_COST_ESTIMATE"] == "1200"


def test_a_free_call_has_no_estimate(engine, monkeypatch, run):
    monkeypatch.setenv("TM_COST_ESTIMATE", "999")   # never inherited from the shell
    assert main(["tool", "elevenlabs", "credits", "--run", str(run.path)]) == 0
    (argv, kw), = engine["calls"]
    assert "TM_COST_ESTIMATE" not in kw["env"]


def test_the_credits_read_runs_without_the_voice_tier(engine, run):
    """#54: one free read of the subscription does not need the ~1 GB voice tier: it runs in the base tier."""
    engine["installed"].discard("voice")
    assert main(["tool", "elevenlabs", "credits", "--run", str(run.path), "--json"]) == 0
    (argv, kw), = engine["calls"]
    assert argv[argv.index("-e") + 1] == "base"
    assert kw["env"]["ELEVENLABS_API_KEY"] == XI


def test_a_paid_elevenlabs_call_still_needs_the_voice_tier(engine, run, capsys):
    engine["installed"].discard("voice")
    _budget(run, "voice_credits", 2000)
    assert main(["tool", "elevenlabs", "tts", "--run", str(run.path), "--voice-id", "v", "--text", "t",
                 "--cost", "100"]) == 2
    assert engine["calls"] == [] and "tm env install voice" in capsys.readouterr().out


def test_an_empty_cert_dir_is_not_handed_to_pixi(engine, tmp_path, monkeypatch):
    """#54: the activated environment's SSL_CERT_DIR names a folder with no certificates (conda-forge's openssl on
    Windows), and the nested pixi says "ignoring SSL_CERT_DIR" on stderr. A folder with certificates is kept."""
    empty = tmp_path / "certs"
    empty.mkdir()
    monkeypatch.setenv("SSL_CERT_DIR", str(empty))
    assert main(["tool", "teardown", "--run", "r", "a.mp4"]) == 0
    assert "SSL_CERT_DIR" not in engine["calls"][-1][1]["env"]
    (empty / "ca.pem").write_text("-----BEGIN CERTIFICATE-----\n")
    assert main(["tool", "teardown", "--run", "r", "a.mp4"]) == 0
    assert engine["calls"][-1][1]["env"]["SSL_CERT_DIR"] == str(empty)


# --- #88: help is free, and a voice refusal asks instead of stopping -----------------------------

@pytest.mark.parametrize("name,args", [("elevenlabs", ["--help"]), ("elevenlabs", ["tts", "--help"]),
                                       ("elevenlabs", ["-h"]), ("replicate_run", ["--help"]),
                                       ("replicate_run", ["spec.json", "-h"])])
def test_help_is_free_needs_no_run_cost_key_or_tier(engine, capsys, name, args):
    """#88 point 5: `tm tool elevenlabs --help` showed "costs money, so it needs --run … and --cost …"; the help
    of any tool, paid or not, runs with no run, no cost and no key, in the base tier (every tool module imports
    there), and nothing is spent."""
    (engine["data"] / "secrets.env").write_text("")          # no key at all
    engine["installed"].discard("voice")
    engine["installed"].discard("ai")
    assert tools.TOOLS[name].kind_for(args) is None
    assert main(["tool", name, *args]) == 0
    (argv, kw), = engine["calls"]
    assert argv[argv.index("-e") + 1] == "base" and argv[-len(args):] == args
    assert "ELEVENLABS_API_KEY" not in kw["env"] and "REPLICATE_API_TOKEN" not in kw["env"]
    assert "TM_COST_ESTIMATE" not in kw["env"]
    assert "costs money" not in capsys.readouterr().out


def test_a_help_word_as_an_option_value_is_still_paid():
    """Only a bare -h/--help is the help: `--text=--help` is a line to say."""
    assert tools.TOOLS["elevenlabs"].kind_for(["tts", "--text=--help"]) == "voice_credits"


def test_a_voice_refusal_asks_for_the_difference_and_never_stops_the_run(engine, run, capsys):
    """#88 point 3: a re-record the approved voice budget no longer covers is refused before anything runs, and the
    run is not stopped: the message names the total to approve (what is spent plus this estimate) and the
    command; once approved, the same call runs."""
    _budget(run, "voice_credits", 107)
    s = state.load(run)
    s.spend["voice_credits"] = 105                             # the first take
    state.save(run, s)
    tts = ["tts", "--run", str(run.path), "--voice-id", "v", "--text", "t", "--cost", "107", "--json"]
    assert main(["tool", "elevenlabs", *tts]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "stop" and engine["calls"] == []
    assert "212" in out["message"] and "105" in out["message"] and "tm budget approve voice_credits 212" in out["message"]
    s = state.load(run)
    assert s.status != "stopped" and not flow.open_stop(run) and s.spend["voice_credits"] == 105
    _budget(run, "voice_credits", 212)
    assert main(["tool", "elevenlabs", *tts]) == 0
    assert len(engine["calls"]) == 1 and state.load(run).spend["voice_credits"] == 212
