"""Transcribe one source video via HybrIE.

Pipeline:
  ffmpeg → mono 16 kHz WAV (temp) → HybrIE /v1/audio/transcriptions
  (verbose_json, segment granularity) → cache to <edit>/transcripts/<stem>.json

HybrIE v0.1.28 additions exposed via flags:
  --prompt <str>       biases Whisper decoding toward proper nouns / jargon
  --word-timestamps    request word-level timestamps (DTW alignment)
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


def _check_tools() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise SystemExit(f"required tool missing: {tool} (brew install ffmpeg)")


def extract_audio(video: Path, dst: Path) -> Path:
    """ffmpeg → mono 16 kHz PCM WAV — Whisper's native rate."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst),
    ]
    subprocess.run(cmd, check=True)
    return dst


def transcribe_video(
    video: Path,
    edit_dir: Path,
    *,
    client: HybrieClient | None = None,
    model: str | None = None,
    language: str | None = None,
    force: bool = False,
    prompt: str | None = None,
    word_timestamps: bool = False,
) -> Path:
    """Returns the path to the cached transcript JSON."""
    _check_tools()
    cache_dir = edit_dir / "transcripts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{video.stem}.json"

    if cache_path.exists() and not force:
        return cache_path

    own_client = False
    if client is None:
        client = HybrieClient()
        own_client = True

    try:
        # Sanity-check HybrIE before doing the ffmpeg work — fail fast with a
        # useful message if the server isn't running.
        try:
            client.health()
        except HybrieError as e:
            raise SystemExit(str(e)) from e

        with tempfile.TemporaryDirectory() as tmp:
            wav = extract_audio(video, Path(tmp) / f"{video.stem}.wav")
            payload = client.transcribe(
                wav,
                model=model,
                language=language,
                response_format="verbose_json",
                prompt=prompt,
                word_timestamps=word_timestamps,
            )
    finally:
        if own_client:
            client.close()

    payload["_source"] = str(video.resolve())
    cache_path.write_text(json.dumps(payload, indent=2))
    return cache_path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("video", type=Path)
    p.add_argument("--edit-dir", type=Path, default=None,
                   help="defaults to <video parent>/edit")
    p.add_argument("--model", default=None)
    p.add_argument("--language", default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--prompt", default=None,
                   help="bias Whisper decoding toward these terms (proper nouns, jargon)")
    p.add_argument("--word-timestamps", action="store_true",
                   help="request word-level timestamps (HybrIE v0.1.28+ DTW alignment)")
    args = p.parse_args()

    edit_dir = args.edit_dir or args.video.parent / "edit"
    cache = transcribe_video(
        args.video,
        edit_dir,
        model=args.model,
        language=args.language,
        force=args.force,
        prompt=args.prompt,
        word_timestamps=args.word_timestamps,
    )
    print(cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())
