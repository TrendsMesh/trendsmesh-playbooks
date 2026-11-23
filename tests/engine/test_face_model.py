"""The faces of cover_fit and layer_check (issue #167): OpenCV's YuNet detector, a detection scored 0.8 or more, when
its model (downloaded once at `tm env install video`, pinned by its SHA-256) is in the data folder, else the Haar
detectors, and the result says which ran. Nothing here touches the network or needs OpenCV: the download and the
detectors are stand-ins (a picture where Haar finds a false face, a hand, and YuNet scores it low)."""

from __future__ import annotations

import hashlib
import io
import sys
import types

import pytest

from tm import envtiers, face_model
from tm.tools import cover_fit

MODEL = b"a stand-in for the YuNet model"


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    monkeypatch.setattr(face_model, "SHA256", hashlib.sha256(MODEL).hexdigest())
    monkeypatch.setattr(cover_fit, "_last", [])
    return tmp_path / "data"


def _model(data, content=MODEL):
    (data / "models").mkdir(parents=True, exist_ok=True)
    (data / "models" / face_model.NAME).write_bytes(content)


# --- the detectors, stand-ins ----------------------------------------------------------------------

FACE = [200, 300, 300, 360]     # in YuNet's picture (the frame at half size): 400, 600, 600, 720 in the frame's
HAND = [60, 760, 120, 120]      # the frame's 120, 1520, 240, 240: Haar takes it for a face


class _Img:
    def __init__(self, width, height, channels):
        self.shape = (height, width, 3) if channels == 3 else (height, width)


@pytest.fixture
def opencv(monkeypatch):
    """cv2 and numpy as stand-ins: a 1080×1920 frame; Haar's frontal detector finds the face and the hand; YuNet
    scores the face 0.93 and the hand 0.42."""
    calls: list = []
    cv2 = types.ModuleType("cv2")
    cv2.IMREAD_COLOR, cv2.IMREAD_GRAYSCALE = 1, 0
    cv2.error = type("error", (Exception,), {})
    cv2.imdecode = lambda raw, flag: _Img(1080, 1920, 3 if flag == cv2.IMREAD_COLOR else 1)
    cv2.resize = lambda img, size: _Img(size[0], size[1], 3)
    cv2.flip = lambda img, code: img
    cv2.data = types.SimpleNamespace(haarcascades="/opencv/haar")

    class Cascade:
        def __init__(self, path):
            self.frontal = "frontal" in path

        def detectMultiScale(self, pic, **kw):
            calls.append("haar")
            return [(400, 600, 600, 720), (120, 1520, 240, 240)] if self.frontal else []

    class Net:
        def __init__(self, model, config, size, score, nms, top):
            calls.append(("yunet", model, size, score))

        def setInputSize(self, size):
            pass

        def detect(self, pic):
            return 1, [FACE + [0.0] * 10 + [0.93], HAND + [0.0] * 10 + [0.42]]

    cv2.CascadeClassifier = Cascade
    cv2.FaceDetectorYN = types.SimpleNamespace(create=lambda *a: Net(*a))
    numpy = types.ModuleType("numpy")
    numpy.uint8 = "uint8"
    numpy.fromfile = lambda path, dtype=None: b"png"
    monkeypatch.setitem(sys.modules, "cv2", cv2)
    monkeypatch.setitem(sys.modules, "numpy", numpy)
    return calls


def test_yunet_with_its_model_finds_the_face_and_not_the_hand_haar_finds(data, opencv, tmp_path):
    _model(data)
    rejected: list = []
    found = cover_fit.faces(tmp_path / "frame.png", rejected)
    assert found == [(400, 600, 600, 720)] and rejected == []        # the hand (0.42) is under the 0.8 threshold
    assert cover_fit.detector_used() == "yunet" and "haar" not in opencv
    created = next(x for x in opencv if isinstance(x, tuple))
    assert created[1].endswith(face_model.NAME) and created[2] == (540, 960) and created[3] == 0.8


def test_without_the_model_haar_runs_and_says_so(data, opencv, tmp_path):
    found = cover_fit.faces(tmp_path / "frame.png")
    assert found == [(400, 600, 600, 720), (120, 1520, 240, 240)]     # the hand too: why YuNet replaced it
    assert cover_fit.detector_used() == "haar" and "OpenCV Haar" in cover_fit.DETECTORS["haar"]


def test_a_model_that_fails_its_checksum_falls_back_to_haar(data, opencv, tmp_path):
    _model(data, b"not the model")
    assert face_model.usable() is None
    assert len(cover_fit.faces(tmp_path / "frame.png")) == 2 and cover_fit.detector_used() == "haar"


def test_an_opencv_without_yunet_falls_back_to_haar(data, opencv, tmp_path, monkeypatch):
    _model(data)
    del sys.modules["cv2"].FaceDetectorYN
    assert len(cover_fit.faces(tmp_path / "frame.png")) == 2 and cover_fit.detector_used() == "haar"


def test_yunets_detection_covering_the_whole_frame_is_still_no_face(data, opencv, tmp_path, monkeypatch):
    _model(data)
    whole = [0, 100, 540, 860] + [0.0] * 10 + [0.95]
    monkeypatch.setattr(sys.modules["cv2"].FaceDetectorYN, "create",
                        lambda *a: types.SimpleNamespace(setInputSize=lambda s: None, detect=lambda p: (1, [whole])))
    rejected: list = []
    assert cover_fit.faces(tmp_path / "frame.png", rejected) == []
    assert rejected == [{"face": [0, 200, 1080, 1720], "reason": cover_fit.NOT_A_FACE}]


# --- the download ---------------------------------------------------------------------------------

class _Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_the_model_is_downloaded_once_and_kept_only_with_its_checksum(data, monkeypatch):
    asked = []

    def urlopen(request, timeout):
        asked.append(request.full_url)
        return _Answer(MODEL)

    monkeypatch.setattr(face_model.urllib.request, "urlopen", urlopen)
    assert face_model.fetch() is None and face_model.usable() == data / "models" / face_model.NAME
    assert asked == [face_model.URL] and "opencv_zoo/raw/f12e127" in face_model.URL
    assert face_model.fetch() is None and len(asked) == 1                       # in place: not again


def test_a_wrong_file_or_no_network_keeps_nothing_and_says_why(data, monkeypatch, capsys):
    monkeypatch.setattr(face_model.urllib.request, "urlopen", lambda request, timeout: _Answer(b"an error page"))
    assert "checksum" in face_model.fetch()
    assert not (data / "models" / face_model.NAME).exists()

    def offline(request, timeout):
        raise OSError("no network")

    monkeypatch.setattr(face_model.urllib.request, "urlopen", offline)
    assert "could not be downloaded (OSError: no network)" in face_model.fetch()
    face_model.fetch_for_install()                                               # never raises
    assert "Haar detector" in capsys.readouterr().err


def test_the_real_models_checksum_is_pinned():
    assert face_model.SHA256 == "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
    assert face_model.NAME == "face_detection_yunet_2023mar.onnx" and face_model.SCORE == 0.8


def test_the_video_install_fetches_the_model_after_the_test_render(monkeypatch, tmp_path):
    from tm import render

    monkeypatch.setenv("TM_PLUGIN_ROOT", str(tmp_path / "plugin"))
    monkeypatch.setenv("TM_PLUGIN_DATA", str(tmp_path / "data"))
    steps = []
    monkeypatch.setattr(envtiers.subprocess, "run", lambda *a, **k: types.SimpleNamespace(returncode=0))
    monkeypatch.setattr(render, "setup_done", lambda: False)
    monkeypatch.setattr(render, "setup", lambda force=False: steps.append("setup"))
    monkeypatch.setattr(render, "probe", lambda: steps.append("probe"))
    monkeypatch.setattr(face_model, "fetch", lambda timeout=60: steps.append("model") or "offline")
    assert envtiers.install("video", True) == 0                    # a model that could not be fetched fails nothing
    assert steps == ["setup", "probe", "model"]
    steps.clear()
    assert envtiers.install("base", True) == 0 and steps == []
