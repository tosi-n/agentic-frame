"""Resolve an input (URL or local path) to a known local file path.

This skill is hosted-capable: the source video/audio may already live in
remote/tenant storage (fetched via a signed URL) rather than on local disk.
Every downstream helper (transcribe, describe_scenes) should read a plain
local path regardless of where the bytes actually came from -- this module
is the single place that normalizes that.

CLI:
    fetch_source.py <input> --out <local_path>

- If <input> starts with "http://" or "https://": stream-download it via
  httpx (chunked GET, raise_for_status) to --out.
- Otherwise <input> is treated as a local file path: verified to exist,
  then copied to --out so downstream steps always see the same layout.
- Fails loudly (SystemExit) if the input is neither a reachable URL nor an
  existing local file.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import httpx


def is_url(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


def fetch_source(source: str, out_path: Path) -> Path:
    """Materialize ``source`` (URL or local path) at ``out_path``.

    Returns ``out_path`` on success. Raises ``SystemExit`` with a clear
    message if ``source`` is neither a reachable URL nor an existing local
    file.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if is_url(source):
        try:
            with httpx.stream("GET", source, follow_redirects=True, timeout=600.0) as response:
                response.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=1 << 20):
                        f.write(chunk)
        except httpx.HTTPError as e:
            raise SystemExit(
                f"fetch_source: could not download '{source}': {e}"
            ) from e
        return out_path

    local_path = Path(source)
    if not local_path.is_file():
        raise SystemExit(
            f"fetch_source: '{source}' is neither a reachable URL (http/https) "
            "nor an existing local file."
        )
    shutil.copy(local_path, out_path)
    return out_path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("input", help="URL (http/https) or local file path")
    p.add_argument("--out", type=Path, required=True, help="resolved local output path")
    args = p.parse_args()

    resolved = fetch_source(args.input, args.out)
    print(resolved)
    return 0


if __name__ == "__main__":
    sys.exit(main())
