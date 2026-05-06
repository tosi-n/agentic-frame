"""Render a single PNG that summarises a slice of video for the agent to read.

Three layers, top to bottom:
  1. Filmstrip — N evenly-spaced thumbnails from ffmpeg
  2. Waveform — RMS envelope of the audio in the slice (drawn symmetric)
  3. Segment labels — segment text floated above the waveform; gaps shaded

This is the agent's only "look" tool. Use it sparingly — at cut decisions, when
two takes are ambiguous, or for final self-eval at every cut boundary in the
rendered output. Never use it to scan a whole source.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Aesthetic — kept consistent with video-use (dark, retro-terminal)
BG = (18, 18, 22)
PANEL = (28, 28, 34)
ACCENT = (255, 145, 60)
LABEL_DIM = (170, 170, 175)
GAP_FILL = (60, 110, 180, 80)
WAVE = (255, 145, 60)

CANVAS_WIDTH = 1920
THUMB_HEIGHT = 240
WAVE_HEIGHT = 240
LABEL_BAND = 160
PADDING = 24


@dataclass
class Slice:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(self.end - self.start, 0.001)


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("Menlo.ttc", "Helvetica.ttc", "DejaVuSansMono.ttf",
                 "LiberationMono-Regular.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _check_tools() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise SystemExit(f"required tool missing: {tool}")


def _extract_thumb(video: Path, t: float, dst: Path, width: int) -> None:
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{t:.3f}", "-i", str(video),
        "-frames:v", "1", "-vf", f"scale={width}:-2", str(dst),
    ]
    subprocess.run(cmd, check=True)


def _extract_waveform_envelope(
    video: Path, sl: Slice, samples: int = CANVAS_WIDTH
) -> np.ndarray:
    """Return an envelope normalised to [0, 1] of length ``samples``."""
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "slice.wav"
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", f"{sl.start:.3f}", "-t", f"{sl.duration:.3f}",
            "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
            "-c:a", "pcm_s16le", str(wav),
        ]
        subprocess.run(cmd, check=True)
        try:
            import wave
            with wave.open(str(wav), "rb") as w:
                frames = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        except Exception:
            return np.zeros(samples)

    if len(frames) == 0:
        return np.zeros(samples)
    chunk = max(1, len(frames) // samples)
    trimmed = frames[: chunk * samples].reshape(samples, chunk).astype(np.float32)
    rms = np.sqrt(np.mean(trimmed ** 2, axis=1) + 1e-9)
    peak = float(rms.max())
    if peak <= 0:
        return np.zeros(samples)
    return rms / peak


def _filmstrip(video: Path, sl: Slice, count: int, work: Path) -> Image.Image:
    thumb_w = CANVAS_WIDTH // count
    strip = Image.new("RGB", (CANVAS_WIDTH, THUMB_HEIGHT), BG)
    for i in range(count):
        t = sl.start + (sl.duration * (i + 0.5) / count)
        thumb_path = work / f"thumb_{i:02d}.jpg"
        try:
            _extract_thumb(video, t, thumb_path, thumb_w)
            thumb = Image.open(thumb_path).convert("RGB")
            thumb = thumb.resize((thumb_w, THUMB_HEIGHT))
            strip.paste(thumb, (i * thumb_w, 0))
        except subprocess.CalledProcessError:
            continue
    return strip


def _draw_waveform(envelope: np.ndarray) -> Image.Image:
    img = Image.new("RGBA", (CANVAS_WIDTH, WAVE_HEIGHT), PANEL + (255,))
    draw = ImageDraw.Draw(img)
    mid = WAVE_HEIGHT // 2
    for x in range(min(CANVAS_WIDTH, len(envelope))):
        h = int(envelope[x] * (WAVE_HEIGHT * 0.45))
        if h <= 0:
            continue
        draw.line([(x, mid - h), (x, mid + h)], fill=WAVE)
    return img


def _draw_segments(
    img: Image.Image,
    segments: list[dict],
    sl: Slice,
    silence_threshold: float = 0.4,
) -> None:
    draw = ImageDraw.Draw(img, "RGBA")
    font = _font(20)
    label_y = 18
    last_end = sl.start
    for seg in segments:
        s = max(float(seg.get("start_seconds", seg.get("start", 0))), sl.start)
        e = min(float(seg.get("end_seconds", seg.get("end", 0))), sl.end)
        if e <= s:
            continue
        # Shade silences leading into this segment
        if s - last_end >= silence_threshold:
            x0 = int(_to_x(last_end, sl))
            x1 = int(_to_x(s, sl))
            draw.rectangle([(x0, 0), (x1, img.height)], fill=GAP_FILL)
        last_end = e

        x = int(_to_x(s, sl))
        text = (seg.get("text") or "").strip()
        if text:
            # Truncate so labels don't pile on each other
            shown = text if len(text) < 60 else text[:57] + "…"
            draw.text((x + 4, label_y), shown, fill=LABEL_DIM, font=font)


def _to_x(t: float, sl: Slice) -> float:
    return ((t - sl.start) / sl.duration) * CANVAS_WIDTH


def render_view(
    video: Path,
    start: float,
    end: float,
    out_path: Path,
    *,
    transcript_json: Path | None = None,
    thumbnail_count: int = 10,
) -> Path:
    _check_tools()
    sl = Slice(start=max(0.0, start), end=max(start + 0.05, end))

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        strip = _filmstrip(video, sl, thumbnail_count, work)
        envelope = _extract_waveform_envelope(video, sl)
        wave_img = _draw_waveform(envelope)

    # Compose full canvas: filmstrip / labels band / waveform
    total_h = THUMB_HEIGHT + LABEL_BAND + WAVE_HEIGHT + PADDING * 2
    canvas = Image.new("RGB", (CANVAS_WIDTH, total_h), BG)
    canvas.paste(strip, (0, PADDING))
    label_img = Image.new("RGBA", (CANVAS_WIDTH, LABEL_BAND + WAVE_HEIGHT), PANEL + (255,))
    if transcript_json and transcript_json.is_file():
        try:
            payload = json.loads(transcript_json.read_text())
            segments_in_range = [
                s for s in payload.get("segments", [])
                if float(s.get("end_seconds", s.get("end", 0))) > sl.start
                and float(s.get("start_seconds", s.get("start", 0))) < sl.end
            ]
            _draw_segments(label_img, segments_in_range, sl)
        except (json.JSONDecodeError, KeyError):
            pass
    label_img.alpha_composite(wave_img, (0, LABEL_BAND))
    canvas.paste(label_img.convert("RGB"), (0, PADDING + THUMB_HEIGHT))

    # Tick marks at start/midpoint/end
    draw = ImageDraw.Draw(canvas)
    font = _font(18)
    for label, t in (
        ("start", sl.start),
        ("mid", (sl.start + sl.end) / 2),
        ("end", sl.end),
    ):
        x = int(_to_x(t, sl))
        x = max(2, min(CANVAS_WIDTH - 80, x))
        draw.text((x + 6, total_h - 28), f"{label} {t:.2f}s", fill=ACCENT, font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, format="PNG")
    return out_path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("video", type=Path)
    p.add_argument("--start", type=float, required=True)
    p.add_argument("--end", type=float, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--transcript", type=Path, default=None)
    p.add_argument("--thumbnails", type=int, default=10)
    args = p.parse_args()

    out = render_view(
        args.video, args.start, args.end, args.out,
        transcript_json=args.transcript, thumbnail_count=args.thumbnails,
    )
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
