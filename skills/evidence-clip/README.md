# evidence-clip

Extract a sub-range of an existing video/audio file as a standalone
"evidence" artifact -- with a chain-of-custody sidecar and optional
de-identification before sharing -- for Codex / Claude Code.

## Why

- Hosted-capable extraction: file-in/file-out, no hardware dependency,
  unlike `clip-capture` which needs local screen/camera/mic access.
- Always applies 30 ms audio fades at cut boundaries (mirrors
  `video-edit`'s R3 hard rule) -- evidence clips are often played standalone
  with no surrounding footage to mask a pop.
- A chain-of-custody sidecar (`<clip>.provenance.json`) records sha256
  hashes and the operation history across capture -> extract -> deid.
- **De-identification is honestly split in two, not oversold as one
  feature:**
  - `deid_transcript.py` is a real call to Stimulir's hosted
    `/api/v1/privacy/deidentify` endpoint -- it works today.
  - `deid_media.py` (face/plate blur, audio mute) has **no detector
    anywhere behind it**. It paints over regions and mutes ranges the
    agent supplies explicitly. There is no face detection, plate
    detection, or speaker diarization in HybrIE or Stimulir today -- see
    [`SKILL.md`](./SKILL.md) for exactly what that means for how you use
    this helper.

## Quick start

```bash
# 1. cut a sub-range with 30ms boundary fades
python helpers/extract_range.py source.mp4 --start 12.4 --end 18.1 --out clip.mp4

# 2. record the extraction in a chain-of-custody sidecar
python helpers/provenance.py clip.provenance.json \
  --op extract --tool extract_range.py \
  --at 2026-07-08T12:00:00Z \
  --input source.mp4 --output clip.mp4 \
  --params '{"start": 12.4, "end": 18.1}'

# 3. (optional) redact PII in a transcript of the clip
export STIMULIR_API_KEY=hyb_...
python helpers/deid_transcript.py clip_transcript.json --out clip_transcript.redacted.txt

# 4. (optional) sample frames for the agent to look at and pick regions from --
#    this produces frames, not regions; there is no detector behind it
python helpers/sample_frames.py clip.mp4 --out-dir clip_frames/ --interval-seconds 5

# 5. (optional) blur agent-identified faces / mute agent-identified ranges
python helpers/deid_media.py clip.mp4 --out clip.deid.mp4 \
  --face-regions '[{"t_start":1.2,"t_end":4.0,"x":120,"y":80,"w":150,"h":150}]' \
  --mute-ranges '[[8.4, 9.1]]'

# 6. record the deid step too
python helpers/provenance.py clip.provenance.json \
  --op deid_media --tool deid_media.py \
  --at 2026-07-08T12:05:00Z \
  --input clip.mp4 --output clip.deid.mp4
```

See [`SKILL.md`](./SKILL.md) for the full playbook (including the hard
detection-vs-execution split for de-identification) and
[`install.md`](./install.md) for setup, including where to get a
`STIMULIR_API_KEY`.
