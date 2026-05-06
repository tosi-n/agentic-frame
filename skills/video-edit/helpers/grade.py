"""Color grading filter strings for ffmpeg.

Two modes:
  - preset: a small named library (subtle / neutral_punch / warm_cinematic / none)
  - auto:   sample the source, decide a gentle correction, clamp at +/-8 %

The agent picks the mode in the EDL. ``resolve_grade_filter`` is the entry
point used by render.py — it accepts a preset name, "auto", or a raw ffmpeg
filter string and returns the filter string to splice in.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

PRESETS: dict[str, str] = {
    "none": "",
    "subtle": "eq=contrast=1.03:saturation=0.98",
    "neutral_punch": "eq=contrast=1.06:saturation=1.02,curves=preset=medium_contrast",
    # Opt-in only. Strong look — the kind a human colourist would sign off on.
    "warm_cinematic": (
        "eq=contrast=1.12:saturation=0.88:gamma_r=1.04:gamma_b=0.94,"
        "curves=preset=medium_contrast"
    ),
}


@dataclass
class _Stats:
    luma: float        # 0..1
    dynamic_range: float  # 0..1
    saturation: float  # 0..1


def _ffmpeg_ok() -> bool:
    return shutil.which("ffmpeg") is not None


def _sample_frame_stats(video: Path, sample_seconds: float = 5.0) -> _Stats | None:
    """Run signalstats on a few seconds of frames and parse YAVG/SATAVG."""
    if not _ffmpeg_ok():
        return None
    with tempfile.TemporaryDirectory() as tmp:
        meta = Path(tmp) / "stats.txt"
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", "0", "-t", str(sample_seconds), "-i", str(video),
            "-vf", f"signalstats,metadata=print:file={meta}",
            "-an", "-f", "null", "-",
        ]
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError:
            return None
        if not meta.is_file():
            return None
        text = meta.read_text()

    yavg = _avg(re.findall(r"lavfi\.signalstats\.YAVG=(\S+)", text))
    ymin = _avg(re.findall(r"lavfi\.signalstats\.YMIN=(\S+)", text))
    ymax = _avg(re.findall(r"lavfi\.signalstats\.YMAX=(\S+)", text))
    satavg = _avg(re.findall(r"lavfi\.signalstats\.SATAVG=(\S+)", text))
    if yavg is None:
        return None
    # Detect bit depth by ceiling of observed luma. Most footage is 8-bit (255).
    scale = 1023.0 if (ymax or 0) > 260 else 255.0
    return _Stats(
        luma=(yavg or 0) / scale,
        dynamic_range=((ymax or 0) - (ymin or 0)) / scale,
        saturation=(satavg or 0) / scale,
    )


def _avg(values: list[str]) -> float | None:
    nums = []
    for v in values:
        try:
            nums.append(float(v))
        except ValueError:
            continue
    return sum(nums) / len(nums) if nums else None


def auto_grade_for_clip(video: Path) -> str:
    """Data-driven gentle correction. Empty string == passthrough.

    Samples the first 5 s of the source — not the EDL range. Two cuts from
    different lighting conditions in the same source therefore receive the
    same auto grade. For multi-condition sources, override per-range with
    an explicit preset in the EDL.
    """
    stats = _sample_frame_stats(video)
    if stats is None:
        return ""

    contrast = 1.0
    gamma = 1.0
    saturation = 1.0

    if stats.luma < 0.35:
        gamma = min(gamma + 0.06, 1.08)
    elif stats.luma > 0.65:
        gamma = max(gamma - 0.04, 0.96)

    if stats.dynamic_range < 0.45:
        contrast = min(contrast + 0.05, 1.08)

    if stats.saturation < 0.30:
        saturation = min(saturation + 0.05, 1.08)
    elif stats.saturation > 0.55:
        saturation = max(saturation - 0.04, 0.96)

    if contrast == 1.0 and gamma == 1.0 and saturation == 1.0:
        return ""

    return f"eq=contrast={contrast:.3f}:gamma={gamma:.3f}:saturation={saturation:.3f}"


_FFMPEG_FILTER_RE = re.compile(r"[a-z][a-z0-9_]*\s*=")


def resolve_grade_filter(value: str | None, video: Path | None = None) -> str:
    """Accept ``None`` / preset name / "auto" / raw ffmpeg filter string."""
    if not value:
        return ""
    value = value.strip()
    if value in PRESETS:
        return PRESETS[value]
    if value == "auto":
        if video is None:
            return ""
        return auto_grade_for_clip(video)
    # If it looks like a filter graph (e.g., "eq=contrast=1.05"), pass through.
    if _FFMPEG_FILTER_RE.search(value):
        return value
    raise ValueError(f"unknown grade: {value!r} (presets: {sorted(PRESETS)})")
