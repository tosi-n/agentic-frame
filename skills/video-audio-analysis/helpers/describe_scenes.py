"""Sample frames from a video at a fixed interval and describe each via HybrIE VLM.

Pipeline:
  ffprobe -> total duration
  HybrieClient().health() (preflight -- fail before wasting any ffmpeg work)
  for each sample timestamp:
    ffmpeg -ss <t> -frames:v 1 -> temp PNG frame
    HybrieClient().vision(prompt=..., image_paths=[frame]) -> one-sentence description
  write [{"timestamp_s": t, "description": str}, ...] to --out
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from hybrie_client import HybrieClient, HybrieError

SCENE_PROMPT = (
    "Describe this scene factually in one sentence: setting, people/objects "
    "visible, any on-screen text."
)


def _check_tools() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise SystemExit(f"required tool missing: {tool} (brew install ffmpeg)")


def probe_duration(video: Path) -> float:
    """ffprobe -> total duration in seconds (float)."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    raw = result.stdout.strip()
    if not raw or raw.lower() == "n/a":
        raise SystemExit(
            f"describe_scenes: ffprobe returned no usable duration for {video} "
            f"(stdout={raw!r} stderr={result.stderr.strip()!r})"
        )
    try:
        return float(raw)
    except ValueError as e:
        raise SystemExit(
            f"describe_scenes: could not parse ffprobe duration output {raw!r} for {video}"
        ) from e


def extract_frame(video: Path, timestamp_s: float, dst: Path) -> Path:
    """ffmpeg -ss <t> -frames:v 1 -> a single PNG frame at dst."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", str(timestamp_s), "-i", str(video),
        "-frames:v", "1", "-q:v", "2", str(dst),
    ]
    subprocess.run(cmd, check=True)
    if not dst.is_file() or dst.stat().st_size == 0:
        raise SystemExit(
            f"describe_scenes: ffmpeg produced no frame at t={timestamp_s}s for {video}"
        )
    return dst


def describe_scenes(
    video: Path,
    *,
    interval_seconds: float = 30.0,
    client: HybrieClient | None = None,
) -> list[dict[str, object]]:
    """Sample frames every ``interval_seconds`` and describe each via HybrIE vision().

    Returns a list of ``{"timestamp_s": float, "description": str}``.
    """
    _check_tools()

    own_client = False
    if client is None:
        client = HybrieClient()
        own_client = True

    scenes: list[dict[str, object]] = []
    try:
        # Preflight: fail before sampling any frames if HybrIE is unreachable.
        try:
            client.health()
        except HybrieError as e:
            raise SystemExit(str(e)) from e

        duration = probe_duration(video)
        if interval_seconds <= 0:
            raise SystemExit("describe_scenes: --interval-seconds must be > 0")

        timestamps: list[float] = []
        t = 0.0
        while t < duration:
            timestamps.append(t)
            t += interval_seconds
        if not timestamps:
            timestamps = [0.0]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            for i, ts in enumerate(timestamps):
                frame_path = tmp_dir / f"frame_{i:04d}.png"
                extract_frame(video, ts, frame_path)
                description = client.vision(
                    prompt=SCENE_PROMPT,
                    image_paths=[frame_path],
                )
                scenes.append({"timestamp_s": ts, "description": description.strip()})
    finally:
        if own_client:
            client.close()

    return scenes


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("video", type=Path)
    p.add_argument("--out", type=Path, required=True, help="path to write JSON scene list")
    p.add_argument("--interval-seconds", type=float, default=30.0,
                   help="sample a frame every N seconds (default: 30)")
    args = p.parse_args()

    scenes = describe_scenes(args.video, interval_seconds=args.interval_seconds)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(scenes, indent=2))
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
