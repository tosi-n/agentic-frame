"""Resolve the ffmpeg / ffprobe binaries, preferring a pip-provisioned bundle.

On a normal dev machine ffmpeg is on PATH (see install.md). In a bare
code-runtime sandbox it is not -- so the skill declares `imageio-ffmpeg` in
pyproject.toml, and the platform pip-installs a skill's declared dependencies
before running it. `imageio-ffmpeg` ships a static ffmpeg binary; this module
finds it. That makes the skill self-provisioning: no system ffmpeg required,
nothing to install by hand.

Note: imageio-ffmpeg bundles ffmpeg but NOT ffprobe. The core extract/redact
helpers (extract_range.py, deid_media.py) use ffmpeg only and work anywhere.
sample_frames.py's dimension/duration probing uses ffprobe and therefore still
needs a full ffmpeg install (dev machine); in a bundle-only sandbox it degrades
to the bare `ffprobe` name.
"""
from __future__ import annotations

import shutil


def ffmpeg_exe() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def ffprobe_exe() -> str:
    found = shutil.which("ffprobe")
    if found:
        return found
    return "ffprobe"
