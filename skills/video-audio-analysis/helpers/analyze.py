"""Orchestrator: transcript + visual scene analysis for one video/audio source.

<input> may be a local file path or a URL already sitting in remote/tenant
storage. Everything downstream (transcription, scene sampling) needs a local
path, so this module first resolves the source via ``fetch_source`` (imported
and called directly -- no subprocess), then calls into ``transcribe`` and
``describe_scenes`` the same way.

CLI:
    analyze.py <input> --out <json_path> [--interval-seconds 30] [--word-timestamps]

Output artifact:
    {
      "transcript": <HybrieClient.transcribe() payload, via transcribe.transcribe_video>,
      "scenes": [<describe_scenes.describe_scenes() list>],
      "source": <original input string>
    }
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from describe_scenes import describe_scenes
from fetch_source import fetch_source, is_url
from hybrie_client import HybrieClient, HybrieError
from transcribe import transcribe_video


def analyze(
    source: str,
    *,
    interval_seconds: float = 30.0,
    word_timestamps: bool = False,
    prompt: str | None = None,
    language: str | None = None,
    model: str | None = None,
    edit_dir: Path | None = None,
) -> dict[str, object]:
    """Resolve ``source`` locally, transcribe it, sample+describe scenes.

    Returns the merged JSON-able dict written to --out by ``main()``.
    """
    client = HybrieClient()
    try:
        try:
            client.health()
        except HybrieError as e:
            raise SystemExit(str(e)) from e

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)

            if is_url(source):
                local_path = fetch_source(source, tmp_dir / "source_input")
            else:
                local_path = Path(source)
                if not local_path.is_file():
                    raise SystemExit(
                        f"analyze: '{source}' is neither a reachable URL (http/https) "
                        "nor an existing local file."
                    )

            resolved_edit_dir = edit_dir or (tmp_dir / "edit")
            transcript_cache_path = transcribe_video(
                local_path,
                resolved_edit_dir,
                client=client,
                model=model,
                language=language,
                prompt=prompt,
                word_timestamps=word_timestamps,
            )
            transcript = json.loads(transcript_cache_path.read_text())

            scenes = describe_scenes(
                local_path,
                interval_seconds=interval_seconds,
                client=client,
            )
    finally:
        client.close()

    return {
        "transcript": transcript,
        "scenes": scenes,
        "source": source,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("input", help="URL (http/https) or local file path")
    p.add_argument("--out", type=Path, required=True, help="path to write merged JSON artifact")
    p.add_argument("--interval-seconds", type=float, default=30.0,
                   help="sample a frame every N seconds for scene description (default: 30)")
    p.add_argument("--word-timestamps", action="store_true",
                   help="request word-level timestamps (HybrIE v0.1.28+ DTW alignment)")
    p.add_argument("--prompt", default=None,
                   help="bias Whisper decoding toward these terms (proper nouns, jargon)")
    p.add_argument("--language", default=None)
    p.add_argument("--model", default=None, help="STT model override")
    args = p.parse_args()

    result = analyze(
        args.input,
        interval_seconds=args.interval_seconds,
        word_timestamps=args.word_timestamps,
        prompt=args.prompt,
        language=args.language,
        model=args.model,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
