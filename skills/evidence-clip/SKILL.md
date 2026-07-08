---
name: evidence-clip
description: Extract a sub-range of a video/audio file as a standalone evidence artifact with a chain-of-custody sidecar, and optionally de-identify it before sharing. Use when the user needs a clip cut out of existing footage for a bug report, dispute, or incident record, with provenance tracking and optional PII/face/audio scrubbing.
---

# Evidence Clip

This skill extracts a sub-range of an existing video/audio file as a
standalone "evidence" artifact (e.g. for a bug report or dispute), with a
chain-of-custody sidecar, and optional de-identification before sharing.
Hosted-capable for extraction (file-in/file-out, no hardware dependency).
De-identification splits into two genuinely different capabilities -- be
precise about this split, it is the most important design fact in this
skill:

- **Transcript PII scrub (`deid_transcript.py`) is REAL** and calls a
  genuine hosted endpoint today (`STIMULIR_API_URL`'s
  `/api/v1/privacy/deidentify`).
- **Media de-identification (`deid_media.py`: face/plate blur, audio mute)
  does NOT have any upstream detector.** No face detection, plate
  detection, or voice/speaker diarization exists anywhere in HybrIE or
  Stimulir today (verified directly against the HybrIE source). This
  helper only PAINTS OVER regions / MUTES ranges the AGENT supplies
  explicitly -- it never detects anything itself. An agent using this
  skill must get face/mute coordinates from its own vision reasoning (or a
  `describe_scenes`-style pass) and from diffing transcript text
  before/after `deid_transcript.py`, mapped onto Whisper word-level
  timestamps if available.

## Preflight

```bash
ffmpeg -version
python -c "import httpx; print('httpx ok')"
echo "${STIMULIR_API_KEY:+STIMULIR_API_KEY is set}"
```

`ffmpeg` is required for every step. `STIMULIR_API_KEY` is only required
when calling `deid_transcript.py` -- `extract_range.py`, `provenance.py`,
and `deid_media.py` are fully self-contained and need no network access or
API key.

## Capability tiers

| Capability | Status |
|---|---|
| Extract a sub-range with fades | Self-contained, works today, no hardware dependency |
| Chain-of-custody sidecar | Self-contained, pure function of file bytes + caller-supplied timestamp |
| Transcript PII redaction | Real hosted call to Stimulir's `/api/v1/privacy/deidentify` -- needs `STIMULIR_API_KEY` and network access |
| Face/plate blur, audio mute | Self-contained ffmpeg execution -- but **zero detection**. Coordinates/ranges must come from the agent, not this skill |
| Face detection / plate detection / speaker diarization | **Does not exist anywhere in this skill, HybrIE, or Stimulir.** Not a missing flag -- there is no upstream model to call |

## The workflow

### 1. Extract

```bash
python helpers/extract_range.py <input> --start <s> --end <s> --out <clip.mp4>
```

Always re-encodes (`libx264`/`aac`), never `-c copy` -- because it applies
30 ms audio fades at both cut boundaries (mirrors `video-edit`'s R3 hard
rule: no audible pops at cut boundaries). This matters more here than in
`clip-capture`'s `trim.py`: an evidence clip is frequently played standalone
with no surrounding footage to mask a pop at the in/out point.

If the requested range is shorter than the 30 ms fade window, the fade-out
is skipped (with a clear stderr note) rather than producing a negative or
zero-length fade.

### 2. Record provenance

```bash
python helpers/provenance.py <clip>.provenance.json \
  --op extract --tool extract_range.py \
  --at 2026-07-08T12:00:00Z \
  --input <source> --output <clip.mp4> \
  --params '{"start": 12.4, "end": 18.1}'
```

Call this after **every** step (capture, extract, each de-id pass) so the
sidecar accumulates a full chain-of-custody record: sha256 of input (and
output, if given), the ISO 8601 timestamp the caller supplies, and the
params used. `--at` is a required argument -- this helper never reads the
system clock; the agent (or the tool orchestrating the agent) supplies the
timestamp. sha256 hashing is a pure function of file bytes, so it's exempt
from the repo's "no clocks in helpers" rule.

The other three helpers (`extract_range.py`, `deid_transcript.py`,
`deid_media.py`) never write to the sidecar themselves. They stay dumb on
purpose -- the agent is the one who decides when a step is worth recording,
and calls `provenance.py` explicitly.

### 3. (Optional) De-identify the transcript

```bash
python helpers/deid_transcript.py <transcript.json|.txt> --out <redacted.txt>
```

Requires `STIMULIR_API_URL` (defaults to `https://api.stimulir.com`) and
`STIMULIR_API_KEY` (a `hyb_*` key -- see `install.md` for where to get one;
no default, fails loudly if unset since this is a real authenticated call).
Accepts a plain `.txt` file or a JSON transcript (Whisper `verbose_json`
shape with a top-level `"text"` field, or a `"segments"` list) -- detected
automatically.

**Hard limitation, not a caveat:** this endpoint never returns match
offsets or original matched values. It produces a redacted text artifact
only -- it cannot drive a downstream audio bleep/mute step on its own. If
audio needs muting to match the redacted transcript, the agent must diff
the original text against the redacted text to find what changed, then map
those spans onto Whisper word-level timestamps (if the transcript has
them) to get seconds, and pass that to `--mute-ranges` below.

### 4. (Optional) De-identify the media

```bash
python helpers/deid_media.py <input> --out <deid.mp4> \
  --face-regions '[{"t_start":1.2,"t_end":4.0,"x":120,"y":80,"w":150,"h":150}]' \
  --mute-ranges '[[8.4, 9.1]]'
```

**This helper detects nothing.** `--face-regions` (pixel boxes with time
windows) and `--mute-ranges` (second pairs) must come from the agent's own
reasoning -- native vision over sampled frames for face/plate boxes, and a
transcript diff (step 3) mapped onto word timestamps for mute ranges. There
is no face detector, plate detector, or speaker diarization model anywhere
in this skill, HybrIE, or Stimulir to call instead. Calling this helper
with both flags empty is treated as a mistake and fails loudly rather than
silently no-op-ing.

Internally: each face region becomes a `crop` -> `boxblur` -> `overlay`
filter_complex stage, chained onto the previous stage's output, with
`enable='between(t,...)'` gating so the blur only applies during that
region's time window. Each mute range becomes a `volume=0` gate,
comma-chained for multiple ranges. Video is only re-encoded when
`--face-regions` is given (`-c:v copy` otherwise); audio is only re-encoded
when `--mute-ranges` is given (`-c:a copy` otherwise) -- and when video is
filtered, `-map 0:a` is added explicitly so the audio stream isn't dropped
by the filter_complex `-map`.

## Anti-patterns (do NOT do)

- **Claiming or implying `deid_media.py` performs its own face/speaker
  detection.** It does not, and cannot -- there is no detector to call. It
  is purely a paint/mute executor for agent-supplied coordinates. Any
  language suggesting otherwise (to a user, in a commit message, in a
  generated report) is factually wrong and must not be used.
- Treating `deid_transcript.py`'s response as if it carried timing
  information. It doesn't -- the endpoint's response has no offsets, so
  don't wire its output directly into `--mute-ranges` without an explicit
  diff-and-align step in between.
- Skipping `provenance.py` between steps because "it's just an extract."
  The sidecar's value is a complete, unbroken chain -- a missing link
  defeats the purpose of using this skill over a bare ffmpeg command.
- Using `-c copy` in `extract_range.py`. This skill always re-encodes to
  guarantee the 30 ms boundary fades; if lossless keyframe-snapped trimming
  is what's actually needed (no evidentiary fade requirement), use
  `clip-capture`'s `trim.py` instead.
- Calling `deid_transcript.py` without `STIMULIR_API_KEY` set and expecting
  a local fallback. There isn't one -- this is a real hosted call, not an
  optional enhancement.
- Passing overlapping or out-of-frame `--face-regions` coordinates without
  checking them against the source resolution first (`ffprobe` the input).
  ffmpeg will either error or silently blur the wrong area.
