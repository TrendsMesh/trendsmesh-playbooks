"""The model of OpenCV's YuNet face detector (issue #167), which `tm tool cover_fit` and `tm tool layer_check` find
faces with.

The model file (`face_detection_yunet_2023mar.onnx`, about 230 KB, MIT, from the OpenCV model zoo) is not in the
plugin: `tm env install video` downloads it once, after the video tools are set up, into the plugin's data folder
(`<data>/models/`), and keeps it only when its SHA-256 is the one pinned here. A data folder is shared by the plugin's
versions, so a later version finds it there. While the file is missing or fails its checksum, the faces are found
with OpenCV's Haar detectors instead, and the tools say which detector ran (`cover_fit.detector_used`).
"""

from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
from pathlib import Path

from tm import __version__, paths

NAME = "face_detection_yunet_2023mar.onnx"
# The model zoo's commit that added this version ("update yunet to v2"), so the address never moves.
URL = ("https://github.com/opencv/opencv_zoo/raw/f12e12798e8314f7c074a6656816c048dcc95b7a/models/"
       "face_detection_yunet/face_detection_yunet_2023mar.onnx")
SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
MAX_BYTES = 2_000_000
TIMEOUT = 60
SCORE = 0.8           # a detection under this score is no face (a hoodie, a hand, a site capture)

_checked: dict[tuple[str, int, int], bool] = {}


def path() -> Path | None:
    """Where the model is kept, `<data>/models/<NAME>`; None when the data folder is not known."""
    try:
        return paths.data_dir() / "models" / NAME
    except (RuntimeError, OSError):
        return None


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def usable() -> Path | None:
    """The model file when it is there and its SHA-256 is the pinned one, else None (checked once per file state)."""
    where = path()
    try:
        st = where.stat() if where is not None else None
    except OSError:
        return None
    if st is None:
        return None
    key = (str(where), st.st_size, st.st_mtime_ns)
    if key not in _checked:
        try:
            _checked[key] = _sha(where.read_bytes()) == SHA256
        except OSError:
            return None
    return where if _checked[key] else None


def fetch(timeout: float = TIMEOUT) -> str | None:
    """Download the model once into the data folder (the module docstring). None when it is in place; else, in
    words, why it is not (the faces are then found with the Haar detectors). Never raises."""
    if usable() is not None:
        return None
    where = path()
    if where is None:
        return "the face detector's model was not downloaded: the plugin's data folder is not known"
    request = urllib.request.Request(URL, headers={"User-Agent": f"trendsmesh-playbooks/{__version__}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - the fixed https URL
            data = response.read(MAX_BYTES + 1)
    except Exception as exc:  # network error, timeout, an answer that is not 200
        return f"the face detector's model could not be downloaded ({type(exc).__name__}: {exc})"
    if len(data) > MAX_BYTES or _sha(data) != SHA256:
        return "the face detector's model that was downloaded is not the expected file (its checksum differs): not kept"
    try:
        where.parent.mkdir(parents=True, exist_ok=True)
        part = where.with_name(where.name + ".part")
        part.write_bytes(data)
        os.replace(part, where)
    except OSError as exc:
        return f"the face detector's model could not be saved ({exc})"
    return None


def fetch_for_install() -> None:
    """`tm env install video`'s step: download the model, and say on stderr when it could not be (the install still
    succeeds: the faces are found with the Haar detectors until a later install fetches it)."""
    why = fetch()
    if why:
        print(f"Note: {why}. Faces are found with the older Haar detector until `tm env install video` runs again.",
              file=sys.stderr)
