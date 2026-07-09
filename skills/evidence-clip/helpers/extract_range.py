#!/usr/bin/env python3
"""Cut a sub-range out of an existing video/audio file as a standalone evidence artifact.

Unlike clip-capture's trim.py (lossless `-c copy` default), this helper ALWAYS
re-encodes, because it applies 30 ms audio fades at both cut boundaries --
mirrors video-edit's R3 hard rule (no audible pops at cut boundaries). That
rule matters more here than anywhere else in this repo: an evidence clip is
often played standalone with no surrounding context to mask a pop at the
in/out point, so the fade is not optional polish -- it's part of what makes
the clip credible as evidence.

No transcript/EDL machinery, no de-identification here -- this is the
extraction step only. Run provenance.py after this to record the operation in
the chain-of-custody sidecar; run deid_transcript.py / deid_media.py after
that if the clip needs to be scrubbed before sharing.
"""
import argparse
import subprocess
import sys

try:
    from _ffbin import ffmpeg_exe
except ImportError:
    from helpers._ffbin import ffmpeg_exe

FADE_S = 0.03  # 30 ms, mirrors video-edit's R3 hard rule


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="source video/audio file")
    parser.add_argument("--start", type=float, required=True, help="start time in seconds")
    parser.add_argument("--end", type=float, required=True, help="end time in seconds")
    parser.add_argument("--out", required=True, help="output file path")
    args = parser.parse_args()

    if args.end <= args.start:
        raise SystemExit("extract_range.py: --end must be greater than --start")

    duration = args.end - args.start

    if duration >= FADE_S:
        fade_out_st = duration - FADE_S
        afade = f"afade=t=in:st=0:d={FADE_S},afade=t=out:st={fade_out_st:.6f}:d={FADE_S}"
    else:
        sys.stderr.write(
            f"extract_range.py: duration {duration:.4f}s < {FADE_S}s fade window -- "
            "skipping fade-out, applying fade-in only\n"
        )
        afade = f"afade=t=in:st=0:d={FADE_S}"

    cmd = [
        ffmpeg_exe(), "-y",
        "-ss", str(args.start),
        "-i", args.input,
        "-t", str(duration),
        "-af", afade,
        "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "aac",
        args.out,
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-4000:])
        raise SystemExit(
            "extract_range.py: ffmpeg failed. Check that --start/--end fall within "
            "the source's duration and the input file is readable."
        )

    print(f"wrote {args.out} ({duration:.2f}s, faded)")


if __name__ == "__main__":
    main()
