"""Voiceover synthesis via HybrIE v0.1.32+ local TTS (VibeVoice-1.5B).

Converts text → 24 kHz WAV ready to drop into an EDL as an audio overlay
(or any other downstream pipeline that consumes mono PCM).

The HybrIE server applies the audible disclaimer tone and metadata
watermark before returning bytes; this helper is a thin wrapper that
(a) collects script text from CLI / file / stdin, (b) calls
``HybrieClient.speech``, and (c) writes the bytes to disk.

## Examples

Inline text → output.wav::

    python narrate.py "Welcome to the demo." --out narration.wav

Script file with multiple lines → one WAV per line concatenated::

    python narrate.py --script lines.txt --out narration.wav

Use a specific voice + cloud routing::

    python narrate.py "Hello" --voice cloud --cloud-provider runware --out hello.wav

## License-required mitigations

Every WAV that comes back from HybrIE v0.1.32+ already carries:

1. An audible 100 ms triple-tone tag at the start identifying the
   audio as AI-generated (license-required disclaimer).
2. A ``LIST INFO`` metadata chunk inside the WAV with ``IART``,
   ``ICMT``, ``ICRD``, ``ITCH`` fields.

These are applied server-side. Do NOT strip them when downstream
pipelines re-process — they're part of the redistribution license.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hybrie_client import DEFAULT_TTS_MODEL, HybrieClient, HybrieError


def synthesize_text(
    text: str,
    out: Path,
    *,
    model: str = DEFAULT_TTS_MODEL,
    response_format: str = "wav",
    execution_mode: str = "local",
    cloud_provider: str | None = None,
    base_url: str | None = None,
) -> Path:
    """Synthesize ``text`` and write the resulting bytes to ``out``."""
    if not text.strip():
        raise ValueError("text must not be empty after stripping whitespace")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with HybrieClient(base_url=base_url) as client:
        bytes_ = client.speech(
            text,
            model=model,
            response_format=response_format,
            execution_mode=execution_mode,
            cloud_provider=cloud_provider,
        )
    out.write_bytes(bytes_)
    return out


def _gather_text(args: argparse.Namespace) -> str:
    if args.script is not None:
        path = Path(args.script)
        if not path.is_file():
            raise FileNotFoundError(path)
        return path.read_text(encoding="utf-8").strip()
    if args.text is not None:
        return args.text
    # Last-resort: read stdin if available
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    raise SystemExit(
        "no input text — pass it as a positional arg, --script <file>, or pipe via stdin"
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument(
        "text",
        nargs="?",
        help="Inline narration text. Mutually exclusive with --script.",
    )
    p.add_argument(
        "--script",
        type=str,
        default=None,
        help="Path to a UTF-8 text file with the narration script. "
        "Replaces the positional text arg if provided.",
    )
    p.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output audio path. Suffix should match --format "
        "(.wav for wav, .pcm for raw PCM).",
    )
    p.add_argument(
        "--model",
        type=str,
        default=DEFAULT_TTS_MODEL,
        help=f"TTS model id (default: {DEFAULT_TTS_MODEL}).",
    )
    p.add_argument(
        "--format",
        type=str,
        default="wav",
        choices=["wav", "pcm"],
        help="Output audio format. WAV is recommended (carries the "
        "metadata watermark chunk).",
    )
    p.add_argument(
        "--execution-mode",
        type=str,
        default="local",
        choices=["local", "cloud"],
        help="Where TTS runs. 'local' = HybrIE native VibeVoice; 'cloud' "
        "= configured cloud provider (Runware default).",
    )
    p.add_argument(
        "--cloud-provider",
        type=str,
        default=None,
        help="Override the cloud TTS provider id (only meaningful with "
        "--execution-mode=cloud).",
    )
    p.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="HybrIE server base URL. Defaults to $HYBRIE_API_URL or "
        "http://127.0.0.1:8001.",
    )
    args = p.parse_args()

    text = _gather_text(args)
    try:
        out = synthesize_text(
            text,
            args.out,
            model=args.model,
            response_format=args.format,
            execution_mode=args.execution_mode,
            cloud_provider=args.cloud_provider,
            base_url=args.base_url,
        )
    except HybrieError as exc:
        print(f"narrate: HybrIE rejected the request: {exc}", file=sys.stderr)
        return 1
    except (FileNotFoundError, ValueError) as exc:
        print(f"narrate: {exc}", file=sys.stderr)
        return 2

    size = out.stat().st_size
    print(f"narrate: wrote {size:,} bytes to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
