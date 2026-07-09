#!/usr/bin/env python3
"""Extract candidate frames from a video for the agent to review directly.

THIS HELPER DETECTS NOTHING. It samples frames -- at a fixed interval or at
explicit timestamps -- and writes them to disk plus a JSON manifest that
includes the source's pixel width/height. The agent looks at the frames
with its own vision (e.g. reading the JPEG directly) and decides what
--face-regions to pass to deid_media.py. This is the same render-review-
adjust loop real video-edit usage already relies on for placement
decisions (see SKILL.md's "Redaction region review" section) -- there is
still no face/plate detector anywhere in this skill, HybrIE, or Stimulir.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _check_tools() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise SystemExit(f"sample_frames: required tool missing: {tool}")


def probe_duration(video: Path) -> float:
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
            f"sample_frames: ffprobe returned no usable duration for {video} "
            f"(stdout={raw!r} stderr={result.stderr.strip()!r})"
        )
    try:
        return float(raw)
    except ValueError as e:
        raise SystemExit(
            f"sample_frames: could not parse ffprobe duration output {raw!r} for {video}"
        ) from e


def probe_dimensions(video: Path) -> tuple[int, int]:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        str(video),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    raw = result.stdout.strip()
    try:
        w_str, h_str = raw.split("x")
        return int(w_str), int(h_str)
    except ValueError as e:
        raise SystemExit(
            f"sample_frames: could not parse ffprobe dimensions {raw!r} for {video}"
        ) from e


def extract_frame(video: Path, timestamp_s: float, dst: Path) -> Path:
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", str(timestamp_s), "-i", str(video),
        "-frames:v", "1", "-q:v", "2", str(dst),
    ]
    subprocess.run(cmd, check=True)
    if not dst.is_file() or dst.stat().st_size == 0:
        raise SystemExit(
            f"sample_frames: ffmpeg produced no frame at t={timestamp_s}s for {video}"
        )
    return dst


def sample_frames(
    video: Path,
    out_dir: Path,
    *,
    interval_seconds: float | None = None,
    timestamps: list[float] | None = None,
) -> dict[str, object]:
    """Extract frames to out_dir, return a manifest dict.

    Exactly one of interval_seconds / timestamps is expected -- interval
    does uniform sampling across the whole clip; timestamps re-samples
    exact seconds the agent already cares about (e.g. checking one moment
    at finer granularity after a first pass).
    """
    _check_tools()
    width, height = probe_dimensions(video)

    if timestamps is not None:
        ts_list = list(timestamps)
    else:
        duration = probe_duration(video)
        if interval_seconds is None or interval_seconds <= 0:
            raise SystemExit("sample_frames: --interval-seconds must be > 0")
        ts_list = []
        t = 0.0
        while t < duration:
            ts_list.append(t)
            t += interval_seconds
        if not ts_list:
            ts_list = [0.0]

    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for i, ts in enumerate(ts_list):
        frame_path = out_dir / f"frame_{i:04d}_t{ts:.2f}.jpg"
        extract_frame(video, ts, frame_path)
        frames.append({"timestamp_s": ts, "path": str(frame_path)})

    return {"source": str(video), "width": width, "height": height, "frames": frames}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--out-dir", type=Path, required=True,
        help="directory to write sampled JPEG frames into",
    )
    parser.add_argument(
        "--manifest-out", type=Path, default=None,
        help="path to write the JSON manifest (default: print to stdout)",
    )
    parser.add_argument(
        "--interval-seconds", type=float, default=None,
        help="sample uniformly every N seconds across the clip",
    )
    parser.add_argument(
        "--timestamps", default=None,
        help="comma-separated list of exact seconds to sample instead of --interval-seconds",
    )
    args = parser.parse_args()

    if args.interval_seconds is None and args.timestamps is None:
        raise SystemExit(
            "sample_frames: pass one of --interval-seconds or --timestamps"
        )
    if args.interval_seconds is not None and args.timestamps is not None:
        raise SystemExit(
            "sample_frames: pass only one of --interval-seconds or --timestamps, not both"
        )

    timestamps = None
    if args.timestamps:
        timestamps = [float(x) for x in args.timestamps.split(",")]

    manifest = sample_frames(
        args.input, args.out_dir,
        interval_seconds=args.interval_seconds,
        timestamps=timestamps,
    )

    if args.manifest_out:
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_out.write_text(json.dumps(manifest, indent=2))
        print(args.manifest_out)
    else:
        print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
