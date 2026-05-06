"""Deterministic video renderer enforcing the skill's hard rules.

Pipeline (executed in order):
  1. extract_segment(...) per EDL range
       - HDR detection + tonemap (HLG / PQ → Rec.709 SDR)
       - scale to 1080p / 720p
       - apply per-segment grade (preset / auto / raw)
       - 30 ms audio fade in + fade out at every cut boundary
  2. concat_segments(...)  → lossless `-c copy`, no re-encode
  3. build_master_srt(...) → output-timeline offsets, segment-level
  4. build_final_composite(...) → overlays first, subtitles LAST
  5. apply_loudnorm_two_pass(...) → -14 LUFS / -1 dBTP / LRA 11

Hard rules enforced here in code (the model can't accidentally bypass them):
  R1  Subtitles applied LAST in the filter chain.
  R2  Per-segment extract → lossless concat (no double re-encode).
  R3  30 ms audio fades at every cut boundary.
  R4  Overlays use setpts=PTS-STARTPTS+T/TB.
  R5  Master SRT uses output-timeline offsets.
  R6  Cuts only at HybrIE segment boundaries (enforced by the EDL contract).
  R7  Pad cut edges 100-300 ms.
  R8  HybrIE STT verbose_json + segment granularity only.
  R9  Cache transcripts per source.
  R10 Parallel sub-agents for multiple animations (renderer is agnostic).
  R11 Strategy confirmation before execution (agent gates this).
  R12 All session outputs in <videos_dir>/edit/.
  R13 Health check before any work (transcribe.py enforces this).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from grade import resolve_grade_filter

# ---- Quality presets ------------------------------------------------------

QUALITY_PRESETS: dict[str, dict[str, str | int]] = {
    "final":   {"x264_preset": "fast",      "crf": 20, "scale": 1080},
    "preview": {"x264_preset": "medium",    "crf": 22, "scale": 1080},
    "draft":   {"x264_preset": "ultrafast", "crf": 28, "scale": 720},
}

# Subtitle force_style — bold-overlay, MarginV=90 keeps text inside the safe
# zone for vertical-video platforms (TikTok / Reels / Shorts) which obscure the
# bottom 25-30 %. Same look as video-use.
SUB_FORCE_STYLE = (
    "FontName=Helvetica,FontSize=18,PrimaryColour=&H00FFFFFF&,"
    "OutlineColour=&H00000000&,Outline=2,BorderStyle=1,"
    "Alignment=2,MarginV=90,Bold=1"
)

FADE_DURATION = 0.030  # R3
DEFAULT_PAD = 0.150    # R7 (between 100 and 300 ms)


# ---- EDL types -----------------------------------------------------------

@dataclass
class EdlRange:
    source: str
    start: float
    end: float
    grade: str | None = None  # overrides EDL-level grade
    quote: str = ""
    reason: str = ""


@dataclass
class EdlOverlay:
    file: Path
    start_in_output: float
    duration: float


@dataclass
class Edl:
    sources: dict[str, Path]
    ranges: list[EdlRange]
    grade: str | None = None
    overlays: list[EdlOverlay] = field(default_factory=list)
    subtitles: Path | None = None
    total_duration_s: float | None = None

    @classmethod
    def load(cls, path: Path) -> "Edl":
        data = json.loads(path.read_text())
        sources = {k: Path(v) for k, v in data.get("sources", {}).items()}
        ranges = [
            EdlRange(
                source=r["source"],
                start=float(r["start"]),
                end=float(r["end"]),
                grade=r.get("grade"),
                quote=r.get("quote", ""),
                reason=r.get("reason", ""),
            )
            for r in data["ranges"]
        ]
        overlays = [
            EdlOverlay(
                file=Path(o["file"]),
                start_in_output=float(o["start_in_output"]),
                duration=float(o["duration"]),
            )
            for o in data.get("overlays", [])
        ]
        return cls(
            sources=sources,
            ranges=ranges,
            grade=data.get("grade"),
            overlays=overlays,
            subtitles=Path(data["subtitles"]) if data.get("subtitles") else None,
            total_duration_s=data.get("total_duration_s"),
        )


# ---- ffprobe / ffmpeg helpers --------------------------------------------

def _check_tools() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise SystemExit(f"required tool missing: {tool}")


def _ffprobe_json(args: list[str]) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", *args],
        check=True, capture_output=True, text=True,
    )
    return json.loads(out.stdout)


def is_hdr_source(video: Path) -> bool:
    """HLG / PQ detection — matches video-use behaviour for iPhone footage."""
    try:
        info = _ffprobe_json(["-show_streams", "-select_streams", "v:0", str(video)])
    except subprocess.CalledProcessError:
        return False
    for stream in info.get("streams", []):
        transfer = (stream.get("color_transfer") or "").lower()
        if transfer in {"arib-std-b67", "smpte2084", "bt2020-10", "bt2020-12"}:
            return True
    return False


# ---- Stage 1: extract per-segment ----------------------------------------

def extract_segment(
    src: Path,
    sl: EdlRange,
    grade_value: str | None,
    quality: dict,
    dst: Path,
    *,
    pad: float = DEFAULT_PAD,
) -> None:
    """One ffmpeg call per cut. Bakes in HDR-tonemap, scale, grade and audio fades."""
    start = max(0.0, sl.start - pad)
    end = sl.end + pad
    duration = max(0.05, end - start)

    filters: list[str] = []
    if is_hdr_source(src):
        filters.append("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
                       "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,"
                       "format=yuv420p")
    scale = int(quality.get("scale", 1080))
    filters.append(f"scale=-2:{scale}:flags=lanczos")

    grade_filter = resolve_grade_filter(grade_value, src)
    if grade_filter:
        filters.append(grade_filter)

    vf = ",".join(filters)

    # R3 — 30 ms fade at both edges of every cut.
    af = (
        f"afade=t=in:st=0:d={FADE_DURATION:.3f},"
        f"afade=t=out:st={max(0.0, duration - FADE_DURATION):.3f}:d={FADE_DURATION:.3f}"
    )

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(src),
        "-vf", vf, "-af", af,
        "-r", "24",
        "-c:v", "libx264", "-preset", str(quality["x264_preset"]),
        "-crf", str(quality["crf"]),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        str(dst),
    ]
    subprocess.run(cmd, check=True)


# ---- Stage 2: lossless concat -------------------------------------------

def concat_segments(segment_files: list[Path], dst: Path) -> None:
    """R2 — `-c copy`, no re-encode."""
    list_path = dst.with_suffix(".concat.txt")
    list_path.write_text("".join(f"file '{p.resolve()}'\n" for p in segment_files))
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-c", "copy", "-movflags", "+faststart",
        str(dst),
    ]
    subprocess.run(cmd, check=True)
    list_path.unlink(missing_ok=True)


# ---- Stage 3: master SRT in OUTPUT timeline ------------------------------

def _segments_for_source(transcripts_dir: Path, source: str) -> list[dict]:
    cache = transcripts_dir / f"{Path(source).stem}.json"
    if not cache.is_file():
        return []
    payload = json.loads(cache.read_text())
    return payload.get("segments") or []


def _format_srt_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    ms = int(round((s - int(s)) * 1000))
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{ms:03d}"


def build_master_srt(
    edl: Edl,
    transcripts_dir: Path,
    dst: Path,
    *,
    chunk_words: int = 5,
    pad: float = DEFAULT_PAD,
) -> Path | None:
    """Walk EDL ranges; emit one SRT cue per chunk, in OUTPUT timeline (R5)."""
    cues: list[tuple[float, float, str]] = []
    seg_offset = 0.0
    for r in edl.ranges:
        src_path = edl.sources[r.source]
        segments = _segments_for_source(transcripts_dir, src_path.name) \
            or _segments_for_source(transcripts_dir, r.source)
        seg_duration = (r.end + pad) - max(0.0, r.start - pad)
        for seg in segments:
            ss = float(seg.get("start_seconds", seg.get("start", 0)))
            ee = float(seg.get("end_seconds", seg.get("end", ss)))
            if ee <= r.start or ss >= r.end:
                continue
            ss = max(ss, r.start)
            ee = min(ee, r.end)
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            words = text.split()
            if not words:
                continue
            n_chunks = max(1, (len(words) + chunk_words - 1) // chunk_words)
            chunk_dur = (ee - ss) / n_chunks
            for i in range(n_chunks):
                chunk = " ".join(words[i * chunk_words : (i + 1) * chunk_words])
                cs = (ss - max(0.0, r.start - pad)) + seg_offset + i * chunk_dur
                ce = cs + chunk_dur
                cues.append((cs, ce, chunk.upper()))
        seg_offset += seg_duration

    if not cues:
        return None

    lines: list[str] = []
    for i, (cs, ce, text) in enumerate(cues, 1):
        lines.append(str(i))
        lines.append(f"{_format_srt_time(cs)} --> {_format_srt_time(ce)}")
        lines.append(text)
        lines.append("")
    dst.write_text("\n".join(lines))
    return dst


# ---- Stage 4: composite (overlays + subs LAST) ---------------------------

def build_final_composite(
    base: Path,
    overlays: list[EdlOverlay],
    subtitles: Path | None,
    dst: Path,
) -> None:
    """R1: subtitles LAST. R4: overlays use setpts=PTS-STARTPTS+T/TB."""
    has_subs = subtitles is not None and subtitles.is_file()

    # Fast path: nothing to composite — straight stream copy.
    if not overlays and not has_subs:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(base),
             "-c", "copy", "-movflags", "+faststart", str(dst)],
            check=True,
        )
        return

    # Composite path: build the filter graph, then re-encode.
    inputs: list[str] = ["-i", str(base)]
    for ov in overlays:
        inputs += ["-i", str(ov.file)]

    filter_parts: list[str] = []
    last_label = "[0:v]"
    for idx, ov in enumerate(overlays, start=1):
        # R4 — shift overlay timeline so its frame 0 lands at start_in_output.
        filter_parts.append(
            f"[{idx}:v]setpts=PTS-STARTPTS+{ov.start_in_output:.3f}/TB[ov{idx}]"
        )
        next_label = f"[v{idx}]" if (idx < len(overlays) or has_subs) else "[vout]"
        filter_parts.append(
            f"{last_label}[ov{idx}]overlay=enable='between(t,"
            f"{ov.start_in_output:.3f},{ov.start_in_output + ov.duration:.3f})'"
            f"{next_label}"
        )
        last_label = next_label

    # R1 — subtitles always last in the filter chain.
    if has_subs:
        sub_path = str(subtitles).replace("'", r"\'")
        filter_parts.append(
            f"{last_label}subtitles='{sub_path}':"
            f"force_style='{SUB_FORCE_STYLE}'[vout]"
        )

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", *inputs,
        "-filter_complex", ";".join(filter_parts),
        "-map", "[vout]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        str(dst),
    ]
    subprocess.run(cmd, check=True)


# ---- Stage 5: two-pass loudnorm -----------------------------------------

_LOUDNORM_TARGET = "I=-14:TP=-1:LRA=11"


def apply_loudnorm_two_pass(src: Path, dst: Path) -> None:
    """Broadcast-loudness target — same number every major upload platform expects."""
    pass1 = subprocess.run(
        ["ffmpeg", "-i", str(src), "-af",
         f"loudnorm={_LOUDNORM_TARGET}:print_format=json",
         "-f", "null", "-"],
        check=True, capture_output=True, text=True,
    )
    # loudnorm internally upsamples to ~192 kHz; pin output -ar so the final
    # mp4 stays at 48 kHz (matches what extract_segment emits).
    match = re.search(r"\{[\s\S]*\}", pass1.stderr)
    if not match:
        # Fall back to single-pass approximation if measurement failed.
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
             "-af", f"loudnorm={_LOUDNORM_TARGET}",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
             "-movflags", "+faststart", str(dst)],
            check=True,
        )
        return
    measured = json.loads(match.group(0))
    measured_str = (
        f"measured_I={measured['input_i']}:"
        f"measured_LRA={measured['input_lra']}:"
        f"measured_TP={measured['input_tp']}:"
        f"measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:linear=true"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
         "-af", f"loudnorm={_LOUDNORM_TARGET}:{measured_str}",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", str(dst)],
        check=True,
    )


# ---- Top-level pipeline --------------------------------------------------

def render(
    edl_path: Path,
    out_dir: Path,
    *,
    quality: str = "final",
    transcripts_dir: Path | None = None,
    no_loudnorm: bool = False,
    pad: float = DEFAULT_PAD,
) -> Path:
    _check_tools()
    edl = Edl.load(edl_path)
    qcfg = QUALITY_PRESETS[quality]
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        seg_files: list[Path] = []
        for i, r in enumerate(edl.ranges):
            src = edl.sources[r.source]
            grade_value = r.grade or edl.grade
            seg_dst = work / f"seg_{i:03d}.mp4"
            extract_segment(src, r, grade_value, qcfg, seg_dst, pad=pad)
            seg_files.append(seg_dst)

        base = work / "base.mp4"
        concat_segments(seg_files, base)

        srt = edl.subtitles
        if srt is None and transcripts_dir is not None:
            srt = build_master_srt(edl, transcripts_dir, out_dir / "master.srt", pad=pad)

        composite = work / "composite.mp4"
        build_final_composite(base, edl.overlays, srt, composite)

        final = out_dir / "final.mp4"
        if no_loudnorm:
            shutil.copy2(composite, final)
        else:
            apply_loudnorm_two_pass(composite, final)

    return final


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("edl", type=Path)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--quality", choices=list(QUALITY_PRESETS), default="final")
    p.add_argument("--transcripts-dir", type=Path, default=None,
                   help="if set and EDL omits subtitles, build a master.srt from these")
    p.add_argument("--no-loudnorm", action="store_true")
    p.add_argument("--pad", type=float, default=DEFAULT_PAD,
                   help="seconds of padding on each cut edge (R7)")
    args = p.parse_args()

    final = render(
        args.edl,
        args.out_dir,
        quality=args.quality,
        transcripts_dir=args.transcripts_dir,
        no_loudnorm=args.no_loudnorm,
        pad=args.pad,
    )
    print(final)
    return 0


if __name__ == "__main__":
    sys.exit(main())
