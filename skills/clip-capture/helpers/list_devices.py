#!/usr/bin/env python3
"""Enumerate screen/camera/mic capture devices as JSON.

macOS: parses `ffmpeg -f avfoundation -list_devices true -i ""` stderr output.
Linux: reports the x11grab display target and PulseAudio sources (best-effort;
x11grab only supports the whole X11 display, not a single window, and does not
work under Wayland).
"""
import argparse
import json
import os
import platform
import re
import subprocess
import sys


def list_macos_devices():
    proc = subprocess.run(
        ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True,
        text=True,
    )
    video, audio = [], []
    section = None
    device_re = re.compile(r"\[(\d+)\]\s+(.+)$")
    for line in proc.stderr.splitlines():
        if "AVFoundation video devices" in line:
            section = video
            continue
        if "AVFoundation audio devices" in line:
            section = audio
            continue
        match = device_re.search(line)
        if match and section is not None:
            section.append({"index": int(match.group(1)), "name": match.group(2).strip()})
    return {"platform": "darwin", "video": video, "audio": audio}


def list_linux_devices():
    display = os.environ.get("DISPLAY", ":0")
    audio = []
    try:
        proc = subprocess.run(
            ["pactl", "list", "short", "sources"], capture_output=True, text=True
        )
        for line in proc.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                audio.append({"index": parts[0], "name": parts[1]})
    except FileNotFoundError:
        pass
    return {
        "platform": "linux",
        "video": [
            {
                "index": display,
                "name": f"X11 display {display} (x11grab captures the whole display only)",
            }
        ],
        "audio": audio,
        "note": "x11grab does not work under Wayland sessions.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    system = platform.system()
    if system == "Darwin":
        devices = list_macos_devices()
    elif system == "Linux":
        devices = list_linux_devices()
    else:
        print(json.dumps({"error": f"unsupported platform: {system}"}), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(devices, indent=2))


if __name__ == "__main__":
    main()
