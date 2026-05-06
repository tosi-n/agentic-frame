"""Transcribe a directory of source videos in parallel.

Skips anything already cached. Reports failures at the end so one bad
file doesn't sink a whole batch.
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from hybrie_client import HybrieClient
from transcribe import transcribe_video

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("video_dir", type=Path)
    p.add_argument("--edit-dir", type=Path, default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--language", default=None)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    sources = sorted(
        path for path in args.video_dir.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_EXTS
    )
    if not sources:
        print(f"no videos in {args.video_dir}", file=sys.stderr)
        return 1

    edit_dir = args.edit_dir or args.video_dir / "edit"
    edit_dir.mkdir(parents=True, exist_ok=True)

    failures: list[tuple[Path, Exception]] = []
    with HybrieClient() as client, ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                transcribe_video, src, edit_dir,
                client=client, model=args.model, language=args.language, force=args.force,
            ): src
            for src in sources
        }
        for fut in as_completed(futures):
            src = futures[fut]
            try:
                cache = fut.result()
                print(f"[ok]   {src.name} → {cache.relative_to(edit_dir)}")
            except Exception as e:
                failures.append((src, e))
                print(f"[fail] {src.name}: {e}", file=sys.stderr)

    if failures:
        print(f"\n{len(failures)} file(s) failed to transcribe", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
