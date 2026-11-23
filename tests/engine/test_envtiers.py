import json
import os
import shutil
import subprocess
import time

import pytest

from tm import envtiers
from tm.cli import main
from tm.envtiers import TIERS, install, installed, tiers_for


def test_brief_needs_base_and_breakdown():
    assert tiers_for({"creative_brief"}, voice=False) == ["base", "breakdown"]


def test_edited_video_with_voice_adds_video_voice_and_ai():
    assert tiers_for({"edited_video"}, voice=True) == ["base", "breakdown", "video", "voice", "ai"]


def test_install_without_yes_stops_with_size(capsys):
    assert install("breakdown", yes=False) == 2
    assert "GB" in capsys.readouterr().out


def test_tier_sizes():
    assert {n: t.approx_mb for n, t in TIERS.items()} == {
        "base": 500, "breakdown": 2500, "video": 500, "voice": 1000, "ai": 20, "animatic": 150, "ocr": 350}


def test_the_ocr_tier_is_never_asked_for_by_a_route():
    """Issue 57: OCR is optional. No output needs it, so no playbook's route (and no doctor card) asks for it; the
    teardown says when it would help, and the playbook offers it once."""
    from tm import doctor, playbooks

    every = {"creative_brief", "edited_video", "ai_video", "live_test", "organic_video", "video_ad",
             "review_pack", "briefs", "page", "proposals", "weekly_plan", "script_to_film", "category_report",
             "weekly_digest", "paid_view"}
    assert "ocr" not in tiers_for(every, voice=True)
    for pb in playbooks.all_playbooks():
        assert "ocr" not in doctor.route_tiers(pb.id, every, voice=True)
    assert TIERS["ocr"].env == "ocr" and TIERS["ocr"].needs == ["base"]


def test_the_ocr_environment_pins_rapidocr_and_stays_out_of_the_others():
    import tomllib
    from pathlib import Path

    manifest = tomllib.loads(((Path(__file__).resolve().parents[2] / "plugins" / "trendsmesh-playbooks") / "env" / "pixi.toml").read_text(encoding="utf-8"))
    deps = manifest["feature"]["ocr"]["target"]["unix"]["pypi-dependencies"]   # Windows: env/win-64/ocr.txt (#123)
    assert deps["rapidocr"].startswith("==") and deps["onnxruntime"].startswith("==")
    envs = manifest["environments"]
    assert "ocr" in envs["ocr"]["features"]
    assert not any("ocr" in (e.get("features") or []) for name, e in envs.items() if name != "ocr")


@pytest.fixture
def fake_pixi(tmp_path, monkeypatch):
    root = tmp_path / "root with space" / "Łukasz"
    (root / "env").mkdir(parents=True)
    monkeypatch.setattr(envtiers.paths, "plugin_root", lambda: root)
    monkeypatch.setattr(envtiers.paths, "pixi_bin", lambda: tmp_path / "pixi")
    monkeypatch.setattr(envtiers.paths, "data_dir", lambda: tmp_path)   # the install's log: never the real data folder
    monkeypatch.setattr(envtiers.paths, "pixi_env", lambda: {"PIXI_HOME": "h", "PIXI_NO_PATH_UPDATE": "1"})
    calls = []
    monkeypatch.setattr(envtiers.subprocess, "run", lambda *a, **k: calls.append((a, k)) or _result.pop())
    return calls, root


_result = []


def _proc(code=0, out=""):
    return subprocess.CompletedProcess([], code, stdout=out, stderr="")


def test_install_runs_pixi_with_argv_and_env(fake_pixi):
    calls, root = fake_pixi
    _result.append(_proc())
    assert install("voice", yes=True) == 0
    argv = calls[0][0][0]
    assert argv[1:] == ["install", "--frozen", "-e", "voice", "--manifest-path", str(root / "env" / "pixi.toml")]
    assert isinstance(argv, list) and "shell" not in calls[0][1]
    assert calls[0][1]["env"]["PIXI_NO_PATH_UPDATE"] == "1"


def test_install_failure_returns_one(fake_pixi):
    _result.append(_proc(1))
    assert install("ai", yes=True) == 1


def test_installed_reads_marker_in_prefix(fake_pixi, tmp_path):
    prefix = tmp_path / "envs" / "voice"
    info = json.dumps({"environments_info": [{"name": "voice", "prefix": str(prefix)}]})
    _result.append(_proc(0, info))
    assert installed("voice") is False
    (prefix / "conda-meta").mkdir(parents=True)
    (prefix / "conda-meta" / "pixi").write_text("{}")
    _result.append(_proc(0, info))
    assert installed("voice") is True


def test_video_counts_as_installed_only_with_the_remotion_setup(monkeypatch):
    """#4: render needs the Remotion packages and headless browser for this lock file (`render.setup_done`), which
    `tm env install video` sets up; the pixi environment alone is not the video tier."""
    from tm import render
    monkeypatch.setattr(envtiers, "_env_installed", lambda env: True)
    monkeypatch.setattr(render, "setup_done", lambda: False)
    assert installed("video") is False and installed("base") is True
    monkeypatch.setattr(render, "setup_done", lambda: True)
    assert installed("video") is True
    monkeypatch.setattr(envtiers, "_env_installed", lambda env: False)
    assert installed("video") is False


def test_installed_false_when_pixi_fails(fake_pixi):
    _result.append(_proc(1))
    assert installed("ai") is False


def test_status_json(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(envtiers, "installed", lambda t: t == "base")
    monkeypatch.setattr(envtiers.paths, "data_dir", lambda: tmp_path)   # never the real data folder
    assert main(["env", "status", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["tiers"]["base"]["installed"] is True and data["tiers"]["ai"]["installed"] is False


def test_cli_install_without_yes_exits_two(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(envtiers.paths, "data_dir", lambda: tmp_path)   # never the real data folder
    assert main(["env", "install", "video"]) == 2


def _env_folder(data, name, manifest):
    """A detached pixi environment folder as pixi lays it out, with its conda-meta/pixi marker."""
    meta = data / "envs" / name / "envs" / "base" / "conda-meta"
    meta.mkdir(parents=True)
    (meta / "pixi").write_text(json.dumps({"manifest_path": str(manifest), "environment_name": "base"}),
                               encoding="utf-8")
    (meta / "python-3.11.json").write_text("{}", encoding="utf-8")
    return data / "envs" / name


def test_environments_of_removed_plugin_versions_are_cleaned(tmp_path, monkeypatch):
    """Final review I9 (Ruling 25): pixi keys a detached environment on the manifest's path, so
    every plugin version installs its own. Folders whose manifest is gone are removed."""
    data = tmp_path / "plugin data Łukasz"
    current = tmp_path / "cache" / "0.2.0" / "env" / "pixi.toml"
    current.parent.mkdir(parents=True)
    current.write_text("", encoding="utf-8")
    old = _env_folder(data, "trendsmesh-playbooks-111", tmp_path / "cache" / "0.1.0" / "env" / "pixi.toml")
    live = _env_folder(data, "trendsmesh-playbooks-222", current)
    partial = data / "envs" / "trendsmesh-playbooks-333" / "envs" / "base"
    partial.mkdir(parents=True)                                    # no marker: an install under way
    (data / "envs" / "stray.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(envtiers.paths, "data_dir", lambda: data)
    assert envtiers.clean_stale() == [old]
    assert not old.exists() and live.is_dir() and partial.is_dir()
    assert envtiers.clean_stale() == []
    monkeypatch.setattr(envtiers.paths, "data_dir", lambda: tmp_path / "nothing here")
    assert envtiers.clean_stale() == []


def test_env_status_cleans_old_versions_first(tmp_path, monkeypatch, capsys):
    data = tmp_path / "data"
    old = _env_folder(data, "trendsmesh-playbooks-111", tmp_path / "gone" / "pixi.toml")
    monkeypatch.setattr(envtiers.paths, "data_dir", lambda: data)
    monkeypatch.setattr(envtiers, "installed", lambda tier: False)
    assert main(["env", "status", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert not old.exists() and out["removed_old_environments"] == 1


def _video_install(monkeypatch, tmp_path, *, done_before: bool, probes: list):
    """`tm env install video --yes` with pixi's install a pass and the Remotion steps recorded."""
    monkeypatch.setenv("TM_PLUGIN_ROOT", str(tmp_path / "plugin"))   # CI has no ~/.trendsmesh/paths.json
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    from tm import render
    from tm.tools import _common
    steps = []
    monkeypatch.setattr(envtiers.subprocess, "run", lambda *a, **k: _proc(0))
    monkeypatch.setattr(render, "setup_done", lambda: done_before)
    monkeypatch.setattr(render, "setup", lambda force=False: steps.append(("setup", force)))

    def probe():
        steps.append("probe")
        if probes.pop(0):
            raise _common.ToolError("Remotion test render failed: npm error could not determine executable to run")
    monkeypatch.setattr(render, "probe", probe)
    monkeypatch.setattr("tm.face_model.fetch", lambda timeout=60: None)   # no network (test_face_model.py)
    return steps


def test_video_install_runs_the_probe_and_fails_when_it_fails(monkeypatch, capsys, tmp_path):
    """Issue #124: the install tests a render; a failed one is exit 1 with the reason."""
    steps = _video_install(monkeypatch, tmp_path, done_before=False, probes=[True])
    assert envtiers.install("video", True) == 1
    assert steps == [("setup", False), "probe"]
    assert "test render failed" in capsys.readouterr().out
    steps = _video_install(monkeypatch, tmp_path, done_before=False, probes=[False])
    assert envtiers.install("video", True) == 0 and steps == [("setup", False), "probe"]


def test_video_install_sets_up_again_when_files_in_place_do_not_render(monkeypatch, tmp_path):
    """The files of an earlier setup are in place (its marker, the headless shell) but a render fails: the install
    sets Remotion up again from scratch, then tests once more."""
    steps = _video_install(monkeypatch, tmp_path, done_before=True, probes=[True, False])
    assert envtiers.install("video", True) == 0
    assert steps == [("setup", False), "probe", ("setup", True), "probe"]


# --- issue #161: an update installs the tiers again; the earlier version's are removed, pixi's words go to a log -------

REAL_EARLIER = envtiers.earlier_install   # conftest stubs it (`_no_real_earlier_install`)
OLD = 3600 * 24   # seconds: an earlier version's folder, last changed a day ago


def _tier_env(data, folder, env, manifest):
    """A finished pixi environment `env` in `<data>/envs/<folder>`, made for `manifest`, with a 1000-byte file."""
    prefix = data / "envs" / folder / "envs" / env
    (prefix / "conda-meta").mkdir(parents=True)
    (prefix / "conda-meta" / "pixi").write_text(json.dumps({"manifest_path": str(manifest), "environment_name": env}),
                                                encoding="utf-8")
    (prefix / "lib.bin").write_bytes(b"x" * 1000)
    return prefix


def _plugin(tmp_path, version, age=OLD):
    """A plugin root as Claude Code's cache keeps it, last changed `age` seconds ago."""
    root = tmp_path / "cache" / version
    (root / "env").mkdir(parents=True)
    (root / "env" / "pixi.toml").write_text("", encoding="utf-8")
    then = time.time() - age
    os.utime(root, (then, then))
    return root


@pytest.fixture
def update(tmp_path, monkeypatch):
    """0.14.0 installed base and breakdown; 0.14.1 (the current root) base only. Both roots are still in the cache."""
    data = tmp_path / "data Łukasz"
    old, new = _plugin(tmp_path, "0.14.0"), _plugin(tmp_path, "0.14.1")
    monkeypatch.setattr(envtiers.paths, "data_dir", lambda: data)
    monkeypatch.setattr(envtiers.paths, "plugin_root", lambda: new)
    monkeypatch.setattr(envtiers.paths, "is_windows", lambda: False)
    envs = {"old_base": _tier_env(data, "trendsmesh-playbooks-111", "base", old / "env" / "pixi.toml"),
            "old_breakdown": _tier_env(data, "trendsmesh-playbooks-111", "breakdown", old / "env" / "pixi.toml"),
            "new_base": _tier_env(data, "trendsmesh-playbooks-222", "base", new / "env" / "pixi.toml")}
    return data, old, new, envs


def test_a_tier_installed_for_an_earlier_version_is_known(update):
    """161.1: the doctor says why a tier downloads again when an earlier plugin version had it."""
    data, old, new, envs = update
    assert REAL_EARLIER("breakdown") is True
    assert REAL_EARLIER("voice") is False
    assert REAL_EARLIER("base") is True          # 0.14.0's base is still there too
    shutil.rmtree(data / "envs" / "trendsmesh-playbooks-111")
    assert REAL_EARLIER("base") is False         # this version's own environment is no earlier one
    (envs["new_base"].parent / "voice").mkdir()  # an install under way (no marker) is none either
    assert REAL_EARLIER("voice") is False


def test_once_a_tier_is_installed_the_earlier_versions_copy_is_removed(update):
    """161.2: right after an update the old version's folder is still in Claude Code's cache, so the old rule (its
    manifest is gone) removes nothing. Once this version has a tier, the earlier versions' copies of it go, and the
    space freed is said. A tier this version has not installed yet keeps the earlier copy."""
    data, old, new, envs = update
    got = envtiers.clean()
    assert not envs["old_base"].exists() and envs["old_breakdown"].is_dir() and envs["new_base"].is_dir()
    assert got.removed == [envs["old_base"]] and got.freed_bytes >= 1000 and got.freed_mb == 0
    _tier_env(data, "trendsmesh-playbooks-222", "breakdown", new / "env" / "pixi.toml")
    got = envtiers.clean()
    assert got.removed == [envs["old_breakdown"]]
    assert not (data / "envs" / "trendsmesh-playbooks-111").exists()   # its last environment went: the folder too
    assert envtiers.clean().removed == [] and envtiers.clean_stale() == []
    assert not [p for p in (data / "envs").iterdir() if p.name.startswith(".")]   # nothing half-removed is left


def test_a_version_changed_in_the_last_ten_minutes_is_kept(update):
    """Another session may still run the version it was just updated from: its copies wait for a later clean."""
    data, old, new, envs = update
    os.utime(old, (time.time() - 60, time.time() - 60))
    assert envtiers.clean().removed == [] and envs["old_base"].is_dir()
    os.utime(old, (time.time() - 601, time.time() - 601))
    assert envtiers.clean().removed == [envs["old_base"]]


def test_the_space_freed_counts_a_hard_linked_file_once_all_its_links_go(update, tmp_path):
    """pixi links package files from its cache: a file linked from outside the folder frees nothing."""
    data, old, new, envs = update
    (tmp_path / "pkgs").mkdir()
    big = tmp_path / "pkgs" / "big.bin"
    big.write_bytes(b"y" * 3_000_000)
    os.link(big, envs["old_base"] / "big.bin")
    got = envtiers.clean()
    assert got.removed == [envs["old_base"]] and got.freed_mb == 0 and big.is_file()
    _tier_env(data, "trendsmesh-playbooks-222", "breakdown", new / "env" / "pixi.toml")
    (envs["old_breakdown"] / "own.bin").write_bytes(b"z" * 2_000_000)
    os.link(envs["old_breakdown"] / "own.bin", envs["old_breakdown"] / "twin.bin")
    assert envtiers.clean().freed_mb == 2


def test_nothing_outside_the_data_folder_is_removed(update, tmp_path):
    """A folder under <data>/envs that links elsewhere is never followed or removed."""
    data, old, new, envs = update
    outside = tmp_path / "elsewhere"
    _tier_env(outside, "x", "base", old / "env" / "pixi.toml")
    (data / "envs" / "linked").symlink_to(outside / "envs" / "x", target_is_directory=True)
    envtiers.clean()
    assert (outside / "envs" / "x" / "envs" / "base" / "lib.bin").is_file()


def test_env_status_and_install_say_the_space_freed(update, monkeypatch, capsys):
    data, old, new, envs = update
    monkeypatch.setattr(envtiers, "installed", lambda tier: tier == "base")
    assert main(["env", "status", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["removed_old_environments"] == 1 and out["freed_mb"] == 0 and not envs["old_base"].exists()

    def pixi(argv, **kw):   # installs breakdown for this version
        _tier_env(data, "trendsmesh-playbooks-222", "breakdown", new / "env" / "pixi.toml")
        return _proc(0)
    monkeypatch.setattr(envtiers.subprocess, "run", pixi)
    (envs["old_breakdown"] / "big.bin").write_bytes(b"z" * 3_000_000)
    assert main(["env", "install", "breakdown", "--yes", "--json"]) == 0
    said = json.loads(capsys.readouterr().out)
    assert said["status"] == "done" and said["freed_mb"] == 3 and not envs["old_breakdown"].exists()
    assert "3 MB" in said["message"]
    monkeypatch.setattr(envtiers.subprocess, "run", lambda argv, **kw: _proc(0))
    assert main(["env", "install", "voice", "--yes"]) == 0
    assert "freed" not in capsys.readouterr().out   # nothing removed: nothing said


def test_pixis_words_go_to_a_log_and_only_a_failures_tail_is_shown(update, monkeypatch, capsys):
    """161.3: pixi's warnings (post-link scripts, SSL_CERT_DIR, the data folder's full path) never reach the
    screen; a failure shows the log's last lines and where the log is."""
    data, old, new, envs = update
    seen = {"code": 0}

    def pixi(argv, stdout=None, stderr=None, **kw):
        seen["stderr"] = stderr
        stdout.write("WARN Skipped running the post-link scripts\n" + "".join(f"line {n}\n" for n in range(30)))
        stdout.write("\x1b[31merror\x1b[0m: could not reach conda.anaconda.org\n")
        return _proc(seen["code"])
    monkeypatch.setattr(envtiers.subprocess, "run", pixi)
    assert install("voice", yes=True, as_json=True) == 0
    out = capsys.readouterr()
    assert "post-link" not in out.out + out.err and seen["stderr"] == subprocess.STDOUT
    assert not (data / "install-env-voice.log").exists()   # removed again when all went well
    seen["code"] = 1
    assert install("voice", yes=True, as_json=True) == 1
    said = json.loads(capsys.readouterr().out)["message"]
    assert "error: could not reach conda.anaconda.org" in said and "\x1b" not in said
    assert "line 29" in said and "line 5\n" not in said and "post-link" not in said
    assert str(data / "install-env-voice.log") in said
    assert "post-link" in (data / "install-env-voice.log").read_text(encoding="utf-8")


def test_a_cert_folder_with_no_certificate_is_not_handed_to_pixi(tmp_path):
    """161.3: conda-forge's openssl ships its certs folder with an empty .keep file, so "holds a file" kept it and
    pixi still said "ignoring SSL_CERT_DIR: no certificates found". Only a folder with a PEM certificate is kept."""
    certs = tmp_path / "ssl" / "certs"
    certs.mkdir(parents=True)
    (certs / ".keep").write_bytes(b"")
    (certs / "README").write_text("not a certificate", encoding="utf-8")
    env = {"SSL_CERT_DIR": str(certs), "OTHER": "1"}
    assert envtiers.paths.child_environ(env) == {"OTHER": "1"}
    assert envtiers.paths.child_environ({"SSL_CERT_DIR": "", "OTHER": "1"}) == {"OTHER": "1"}
    proxy = tmp_path / "proxy certs"
    proxy.mkdir()
    (proxy / "corp.crt").write_text("-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n", encoding="utf-8")
    both = os.pathsep.join([str(certs), str(proxy)])
    assert envtiers.paths.child_environ({"SSL_CERT_DIR": both}) == {"SSL_CERT_DIR": both}
    assert envtiers.paths.child_environ({"SSL_CERT_DIR": str(proxy)}) == {"SSL_CERT_DIR": str(proxy)}
