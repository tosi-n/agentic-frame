# video-edit

A video-editing skill for Codex / Claude Code / future Stimulir code-runtime,
powered by [HybrIE](https://github.com/tosi-n/HybrIE) v0.1.27.

The agent does the editorial reasoning. HybrIE runs Whisper locally for
transcripts. ffmpeg does the deterministic work. You get a finished `.mp4`.

## Why

- Local-first: STT runs on your machine, no API costs per source.
- Token-efficient: the agent reads a packed phrase-level transcript
  (~10–15 KB per hour of footage), looks at PNG composites only at decision
  points. Same architecture as `browser-use/video-use`, rewired for HybrIE.
- 13 hard rules baked into `render.py`. The agent can't accidentally produce
  unwatchable output (subtitle drift, audio pops, overlays mid-animation,
  HDR-blown iPhone footage).

## Quick start

```bash
# 1. start HybrIE on :8001 (see install.md)
# 2. transcribe a folder of footage
python helpers/transcribe_batch.py /path/to/footage

# 3. pack for the LLM
python helpers/pack_transcripts.py /path/to/footage/edit/transcripts

# 4. (the agent) reads takes_packed.md → proposes EDL → user confirms

# 5. render
python helpers/render.py /path/to/footage/edit/edl.json \
    --out-dir /path/to/footage/edit \
    --transcripts-dir /path/to/footage/edit/transcripts
```

## Architecture

```
sources → HybrIE STT (local Whisper, segment timestamps)
       → packed transcript (markdown, ~12 KB/hour)
       → agent reads, proposes EDL JSON (segment-aligned cuts)
       → render.py: extract → concat → SRT → composite → loudnorm
       → final.mp4
```

See [`SKILL.md`](./SKILL.md) for the full playbook the agent reads, and
[`install.md`](./install.md) for setup.

## What's different from `video-use`

| | `video-use` | `video-edit` (this skill) |
|---|---|---|
| STT provider | ElevenLabs Scribe (cloud) | HybrIE Whisper (local) |
| Timestamp granularity | word-level | segment-level (HybrIE rejects word-level in v0.1.27) |
| Cuts | mid-segment cuts allowed (word-aware) | segment boundaries only — R6 |
| Edge padding | 30–200 ms | 100–300 ms (segments are coarser) |
| API costs | per-minute scribe + LLM | local (LLM is your agent host) |

## Attribution

The vendored Manim reference material used by the sibling `animate-manim`
sub-skill keeps its attribution note in
[`../animate-manim/LICENSE.upstream`](../animate-manim/LICENSE.upstream).
