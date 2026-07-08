#!/usr/bin/env python3
"""Cut a sub-range out of an existing video file.

Default: lossless `-c copy` extraction, snapped to the nearest keyframe (fast,
no re-encode -- same technique as video-edit's per-segment extract). Pass
--exact when the caller needs frame-accurate cut points instead of
keyframe-snapped ones (forces a re-encode).

No transcript/EDL machinery here -- this is the bare-bone trim only. For
multi-take editing, subtitles, color grade, or overlays, hand off to the
sibling video-edit skill.
"""
import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="source video file")
    parser.add_argument("--start", type=float, required=True, help="start time in seconds")
    parser.add_argument("--end", type=float, required=True, help="end time in seconds")
    parser.add_argument("--out", required=True, help="output file path")
    parser.add_argument(
        "--exact", action="store_true",
        help="re-encode for frame-accurate cuts instead of keyframe-snapped -c copy",
    )
    args = parser.parse_args()

    if args.end <= args.start:
        raise SystemExit("trim.py: --end must be greater than --start")

    duration = args.end - args.start
    cmd = ["ffmpeg", "-y", "-ss", str(args.start), "-i", args.input, "-t", str(duration)]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac"] if args.exact else ["-c", "copy"]
    cmd += [args.out]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-4000:])
        raise SystemExit(
            "trim.py: ffmpeg failed. If the cut looks off by a fraction of a "
            "second, the source may not have a keyframe near --start -- retry with --exact."
        )

    print(f"wrote {args.out} ({duration:.2f}s, {'exact' if args.exact else 'keyframe-snapped'})")


if __name__ == "__main__":
    main()
