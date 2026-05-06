"""Pack HybrIE verbose_json transcripts into compact, LLM-readable markdown.

The packed file is the single artifact the model reads to plan an edit. For an
hour of footage the output is typically ~10-15 KB — orders of magnitude smaller
than the raw segment JSON, while keeping every timestamp the model needs to
quote into an EDL.

Format:
  ## <stem>  (duration: 43.0s, 8 segments, 2 scenes)
    [  0.00 -   5.36] Ninety percent of what a web agent does is completely wasted.
    [  6.08 -   6.74] We fixed this.

Adjacent segments separated by gaps >= ``scene_gap`` (default 2.0 s) are split
into "scene" blocks with a blank line between them.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Segment:
    start: float
    end: float
    text: str


def _segments_from_payload(payload: dict) -> list[Segment]:
    raw = payload.get("segments") or []
    out: list[Segment] = []
    for seg in raw:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        start = float(seg.get("start_seconds", seg.get("start", 0.0)))
        end = float(seg.get("end_seconds", seg.get("end", start)))
        out.append(Segment(start=start, end=end, text=text))
    return out


def _split_scenes(segments: list[Segment], scene_gap: float) -> list[list[Segment]]:
    if not segments:
        return []
    scenes: list[list[Segment]] = [[segments[0]]]
    for prev, curr in zip(segments, segments[1:]):
        if curr.start - prev.end >= scene_gap:
            scenes.append([curr])
        else:
            scenes[-1].append(curr)
    return scenes


def pack_one(transcript_json: Path, scene_gap: float = 2.0) -> str:
    payload = json.loads(transcript_json.read_text())
    segments = _segments_from_payload(payload)
    if not segments:
        return f"## {transcript_json.stem}  (empty transcript)\n"

    duration = payload.get("duration_seconds") or segments[-1].end
    scenes = _split_scenes(segments, scene_gap)
    header = (
        f"## {transcript_json.stem}  "
        f"(duration: {duration:.1f}s, {len(segments)} segments, {len(scenes)} scenes)\n"
    )
    lines: list[str] = [header]
    for i, scene in enumerate(scenes):
        if i > 0:
            lines.append("")
        for seg in scene:
            lines.append(f"  [{seg.start:7.2f} - {seg.end:7.2f}] {seg.text}")
    lines.append("")
    return "\n".join(lines)


def pack_directory(transcripts_dir: Path, scene_gap: float = 2.0) -> str:
    parts: list[str] = []
    for path in sorted(transcripts_dir.glob("*.json")):
        parts.append(pack_one(path, scene_gap=scene_gap))
    return "\n".join(parts)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("transcripts_dir", type=Path,
                   help="directory of HybrIE verbose_json transcripts (one .json per source)")
    p.add_argument("--out", type=Path, default=None,
                   help="defaults to <transcripts_dir>/../takes_packed.md")
    p.add_argument("--scene-gap", type=float, default=2.0,
                   help="seconds of silence between segments to start a new scene block")
    args = p.parse_args()

    out = args.out or args.transcripts_dir.parent / "takes_packed.md"
    out.write_text(pack_directory(args.transcripts_dir, scene_gap=args.scene_gap))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
