#!/usr/bin/env python3
"""Paint over face/plate regions and mute audio ranges in a media file.

THIS HELPER DETECTS NOTHING. There is no face detection, plate detection, or
voice/speaker diarization anywhere in HybrIE or Stimulir today (verified
directly against the HybrIE source). --face-regions and --mute-ranges are
pixel-coordinate boxes and time ranges the AGENT supplies explicitly -- this
helper is a pure paint/mute EXECUTOR, nothing more. It never looks at pixels
or waveforms to decide where to blur or mute; the caller must already know.

Getting the coordinates is the agent's job, not this helper's:
  - face/plate boxes: the agent's own vision reasoning (or a describe_scenes
    -style pass) over sampled frames.
  - mute ranges: diff the transcript text before/after deid_transcript.py,
    then map the changed spans onto Whisper word-level timestamps (if
    available) to get seconds.

Calling this helper with empty --face-regions and empty --mute-ranges is
almost certainly a mistake (there is nothing to do), so it fails loudly
rather than silently no-op-ing.
"""
import argparse
import json
import subprocess
import sys

try:
    from _ffbin import ffmpeg_exe
except ImportError:
    from helpers._ffbin import ffmpeg_exe


def build_video_filter_complex(face_regions):
    """One overlay stage per region, chained onto the previous overlay's output.
    Returns (filter_complex_string, final_video_label).
    """
    stages = []
    for i, region in enumerate(face_regions):
        x, y, w, h = region["x"], region["y"], region["w"], region["h"]
        t_start, t_end = region["t_start"], region["t_end"]

        stages.append(
            f"[0:v]crop={w}:{h}:{x}:{y},boxblur=10:2,setpts=PTS-STARTPTS[b{i}]"
        )

        base = "[0:v]" if i == 0 else f"[v{i - 1}]"
        out_label = f"[v{i}]"
        stages.append(
            f"{base}[b{i}]overlay={x}:{y}:enable='between(t,{t_start},{t_end})'{out_label}"
        )

    final_label = f"v{len(face_regions) - 1}"
    return ";\n".join(stages), final_label


def build_audio_filter(mute_ranges):
    """One volume=0 gate per range, comma-chained in sequence."""
    parts = [
        f"volume=enable='between(t,{t_start},{t_end})':volume=0"
        for t_start, t_end in mute_ranges
    ]
    return ",".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="source video/audio file")
    parser.add_argument("--out", required=True, help="output file path")
    parser.add_argument(
        "--face-regions", default=None,
        help='JSON array of {"t_start","t_end","x","y","w","h"} objects (agent-supplied)',
    )
    parser.add_argument(
        "--mute-ranges", default=None,
        help='JSON array of [t_start, t_end] pairs in seconds (agent-supplied)',
    )
    args = parser.parse_args()

    face_regions = json.loads(args.face_regions) if args.face_regions else []
    mute_ranges = json.loads(args.mute_ranges) if args.mute_ranges else []

    if not face_regions and not mute_ranges:
        raise SystemExit(
            "deid_media.py: neither --face-regions nor --mute-ranges given -- "
            "nothing to do. This is almost certainly a mistake, not a no-op; "
            "pass at least one region or range."
        )

    cmd = [ffmpeg_exe(), "-y", "-i", args.input]

    if face_regions:
        filter_complex, final_label = build_video_filter_complex(face_regions)
        cmd += ["-filter_complex", filter_complex, "-map", f"[{final_label}]", "-map", "0:a"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast"]
    else:
        cmd += ["-c:v", "copy"]

    if mute_ranges:
        audio_filter = build_audio_filter(mute_ranges)
        cmd += ["-af", audio_filter, "-c:a", "aac"]
    else:
        cmd += ["-c:a", "copy"]

    cmd += [args.out]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-4000:])
        raise SystemExit(
            "deid_media.py: ffmpeg failed. Check that --face-regions coordinates "
            "fall within the frame and --mute-ranges fall within the clip's duration."
        )

    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
