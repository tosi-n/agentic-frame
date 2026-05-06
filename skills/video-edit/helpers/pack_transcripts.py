"""Pack HybrIE verbose_json transcripts into compact, LLM-readable markdown.

The packed file is the single artifact the model reads to plan an edit. For an
hour of footage the output is typically ~10-15 KB — orders of magnitude smaller
than the raw segment JSON, while keeping every timestamp the model needs to
quote into an EDL.

Format:
  ## <stem>  (duration: 43.0s, 8 segments, 2 scenes)
    [  0.00 -   5.36] Ninety percent of what a web agent does is completely wasted.
    [  6.08 -   6.74] We fixed this.
   ?[ 12.40 -  18.10] (low confidence — verify before quoting)

Adjacent segments separated by gaps >= ``scene_gap`` (default 2.0 s) are split
into "scene" blocks with a blank line between them.

HybrIE v0.1.28 surface area:
  - When segments carry word-level timing (``words: [{word, start, end}]``),
    a second indented line under each phrase shows word boundaries. To stay
    under the ~12 KB / hour budget, the word line is only emitted for phrases
    shorter than ~2 s when the per-source word density would otherwise blow
    the budget.
  - Low-confidence segments are flagged with a ``?`` prefix on the phrase
    line. Trigger:
        no_speech_prob > 0.6 AND avg_logprob < -1.0   (likely hallucination)
        OR compression_ratio > 2.4                    (repetitive-token failure)
    Agents should verify (e.g. via timeline_view.py) before quoting a
    flagged segment in an EDL.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word]
    flagged: bool


# Confidence thresholds (see module docstring).
_HALLUCINATION_NO_SPEECH = 0.6
_HALLUCINATION_AVG_LOGPROB = -1.0
_REPETITIVE_COMPRESSION = 2.4

# Budget guard: emit per-word lines only for short phrases when the source
# would otherwise overshoot ~12 KB. ~2 seconds matches the existing prose.
_SHORT_PHRASE_S = 2.0
_BUDGET_BYTES = 12_000


def _word_start(word: dict) -> float:
    return float(word.get("start_seconds", word.get("start", 0.0)))


def _word_end(word: dict, fallback: float) -> float:
    return float(word.get("end_seconds", word.get("end", fallback)))


def _is_flagged(seg: dict) -> bool:
    no_speech = seg.get("no_speech_prob")
    avg_logprob = seg.get("avg_logprob")
    compression = seg.get("compression_ratio")
    if (
        isinstance(no_speech, (int, float))
        and isinstance(avg_logprob, (int, float))
        and no_speech > _HALLUCINATION_NO_SPEECH
        and avg_logprob < _HALLUCINATION_AVG_LOGPROB
    ):
        return True
    if isinstance(compression, (int, float)) and compression > _REPETITIVE_COMPRESSION:
        return True
    return False


def _words_from_segment(seg: dict, payload_words_by_seg: list[dict] | None) -> list[Word]:
    raw = seg.get("words") or payload_words_by_seg or []
    out: list[Word] = []
    for w in raw:
        text = (w.get("word") or w.get("text") or "").strip()
        if not text:
            continue
        start = _word_start(w)
        end = _word_end(w, start)
        out.append(Word(start=start, end=end, text=text))
    return out


def _segments_from_payload(payload: dict) -> list[Segment]:
    raw = payload.get("segments") or []
    # Top-level words[] (some Whisper variants emit a flat list keyed by seg index).
    flat_words = payload.get("words") or []
    out: list[Segment] = []
    for seg in raw:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        start = float(seg.get("start_seconds", seg.get("start", 0.0)))
        end = float(seg.get("end_seconds", seg.get("end", start)))
        # Filter flat top-level words[] to those falling inside this segment's window.
        per_seg_words: list[dict] = []
        if not seg.get("words") and flat_words:
            for w in flat_words:
                ws = _word_start(w)
                if start - 1e-3 <= ws <= end + 1e-3:
                    per_seg_words.append(w)
        words = _words_from_segment(seg, per_seg_words or None)
        out.append(
            Segment(
                start=start,
                end=end,
                text=text,
                words=words,
                flagged=_is_flagged(seg),
            )
        )
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


def _format_word_line(seg: Segment) -> str:
    parts = [f"{w.text}@{w.start:.2f}" for w in seg.words]
    return "      · " + " ".join(parts)


def _phrase_line(seg: Segment) -> str:
    prefix = " ?" if seg.flagged else "  "
    return f"{prefix}[{seg.start:7.2f} - {seg.end:7.2f}] {seg.text}"


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

    # First pass: phrase lines only — establish the floor budget.
    phrase_lines: list[str] = [header]
    for i, scene in enumerate(scenes):
        if i > 0:
            phrase_lines.append("")
        for seg in scene:
            phrase_lines.append(_phrase_line(seg))
    phrase_lines.append("")
    base = "\n".join(phrase_lines)

    has_words = any(seg.words for seg in segments)
    if not has_words:
        return base

    # Second pass: try to inject word lines under every segment that has words.
    full_lines: list[str] = [header]
    for i, scene in enumerate(scenes):
        if i > 0:
            full_lines.append("")
        for seg in scene:
            full_lines.append(_phrase_line(seg))
            if seg.words:
                full_lines.append(_format_word_line(seg))
    full_lines.append("")
    full = "\n".join(full_lines)

    if len(full.encode("utf-8")) <= _BUDGET_BYTES:
        return full

    # Budget exceeded — downgrade gracefully: emit word lines only for short
    # phrases (< _SHORT_PHRASE_S) where the micro-timing matters most.
    trimmed_lines: list[str] = [header]
    for i, scene in enumerate(scenes):
        if i > 0:
            trimmed_lines.append("")
        for seg in scene:
            trimmed_lines.append(_phrase_line(seg))
            if seg.words and (seg.end - seg.start) < _SHORT_PHRASE_S:
                trimmed_lines.append(_format_word_line(seg))
    trimmed_lines.append("")
    return "\n".join(trimmed_lines)


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
