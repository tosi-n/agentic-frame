#!/usr/bin/env python3
"""Record a timed screen/camera/mic clip to an mp4 file via ffmpeg.

Deterministic and explicit: --duration is required -- no open-ended
background recording from a skill helper. Fails loudly (with an install/
permission hint) rather than silently producing a black or empty clip.

This helper never asks "should I record" -- that judgment call belongs to
the agent. It only does the one thing it's told, exactly once.
"""
import argparse
import platform
import subprocess
import sys


def build_macos_command(args):
    cmd = ["ffmpeg", "-y"]

    if args.screen_index is not None and args.camera_index is not None:
        # Picture-in-picture: two avfoundation inputs, camera overlaid on screen.
        mic_part = str(args.mic_index) if args.mic_index is not None else "none"
        cmd += [
            "-framerate", str(args.fps), "-f", "avfoundation",
            "-i", f"{args.screen_index}:{mic_part}",
        ]
        cmd += [
            "-framerate", str(args.fps), "-f", "avfoundation",
            "-i", f"{args.camera_index}:none",
        ]
        filter_complex = (
            "[1:v]scale=320:-1[cam];"
            "[0:v][cam]overlay=main_w-overlay_w-20:main_h-overlay_h-20[v]"
        )
        cmd += ["-filter_complex", filter_complex, "-map", "[v]"]
        if args.mic_index is not None:
            cmd += ["-map", "0:a"]
    else:
        video_index = args.screen_index if args.screen_index is not None else args.camera_index
        if video_index is None:
            raise SystemExit("capture.py: pass --screen-index and/or --camera-index")
        audio_part = str(args.mic_index) if args.mic_index is not None else "none"
        cmd += [
            "-framerate", str(args.fps), "-f", "avfoundation",
            "-i", f"{video_index}:{audio_part}",
        ]

    cmd += ["-t", str(args.duration)]
    cmd += ["-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast"]
    cmd += ["-c:a", "aac", "-b:a", "128k"] if args.mic_index is not None else ["-an"]
    cmd += [args.out]
    return cmd


def build_linux_command(args):
    import os

    display = os.environ.get("DISPLAY")
    if not display:
        raise SystemExit(
            "capture.py: $DISPLAY is not set -- x11grab needs an X11 session "
            "and does not work under Wayland."
        )
    cmd = ["ffmpeg", "-y", "-f", "x11grab", "-framerate", str(args.fps), "-i", display]
    if args.mic_index is not None:
        cmd += ["-f", "pulse", "-i", str(args.mic_index)]
    cmd += ["-t", str(args.duration), "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast"]
    cmd += ["-c:a", "aac", "-b:a", "128k"] if args.mic_index is not None else ["-an"]
    cmd += [args.out]
    return cmd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--duration", type=float,
        help="recording length in seconds (required unless --selftest)",
    )
    parser.add_argument(
        "--screen-index", type=int, default=None,
        help="display/screen device index from list_devices.py",
    )
    parser.add_argument(
        "--camera-index", type=int, default=None,
        help="webcam device index; combine with --screen-index for picture-in-picture",
    )
    parser.add_argument(
        "--mic-index", type=int, default=None,
        help="audio input device index; omit for a silent recording",
    )
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--out", required=True, help="output .mp4 path")
    parser.add_argument(
        "--selftest", action="store_true",
        help="run a 2s dry-run capture of the first screen device and validate it with ffprobe",
    )
    args = parser.parse_args()

    if args.selftest:
        args.duration = 2.0
        if args.screen_index is None and args.camera_index is None:
            args.screen_index = 0
    elif args.duration is None:
        raise SystemExit("capture.py: --duration is required (pass --selftest for a quick check)")

    system = platform.system()
    if system == "Darwin":
        cmd = build_macos_command(args)
    elif system == "Linux":
        cmd = build_linux_command(args)
    else:
        raise SystemExit(f"capture.py: unsupported platform {system}")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-4000:])
        raise SystemExit(
            "capture.py: ffmpeg failed. On macOS, check System Settings -> "
            "Privacy & Security -> Screen Recording (and Camera/Microphone) has "
            "granted access to this terminal/app -- ffmpeg cannot capture without "
            "it, and this permission can only be granted manually, not scripted."
        )

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", args.out,
        ],
        capture_output=True,
        text=True,
    )
    duration = probe.stdout.strip()
    if not duration:
        raise SystemExit(
            f"capture.py: ffmpeg exited 0 but {args.out} isn't a readable video -- "
            "capture likely produced an empty/black file (common when screen "
            "recording permission is missing but the process doesn't hard-fail)."
        )
    print(f"wrote {args.out} (duration={duration}s)")


if __name__ == "__main__":
    main()
