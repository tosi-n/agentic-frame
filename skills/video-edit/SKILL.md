---
name: video-edit
description: Edit videos with the agent doing the editorial reasoning and HybrIE doing the heavy inference. Local Whisper STT for transcripts, ffmpeg for everything deterministic. Use when the user has a folder of footage and wants to assemble a finished cut — launch videos, demos, talking heads, tutorials, social clips.
---

# Video Edit (HybrIE)

You are the editor. HybrIE is your inference engine. ffmpeg is your renderer.
The helpers in `helpers/` are dumb on purpose — they enforce the hard rules so
your decisions can be about the cut, not the plumbing.

## Principles

1. **You never watch the video — you read it.** A packed transcript (~10–15 KB
   per hour of footage) is your primary input. Pull a `timeline_view.py` PNG
   only at decision points: ambiguous cuts, retake comparisons, final
   self-eval at every cut boundary.
2. **Audio is primary, visuals follow.** Cuts come from speech boundaries and
   silence gaps. Whisper segments are already phrase-shaped; respect them.
3. **Confirm strategy before rendering.** Propose the EDL, get the user's nod,
   then run `render.py`. Never render speculatively.
4. **Layout before motion.** When you compose overlays, decide the static
   end-state first; animate INTO it. Never tween from "wherever it lands."
5. **Determinism is non-negotiable.** Same EDL → identical output. No clocks,
   no random seeds, no stateful side effects in helpers.
6. **One self-eval pass, then ship.** Sample three timestamps in the rendered
   output (start, mid, end of each cut boundary) via `timeline_view.py`, look
   for jumps, hidden subs, audio pops, misaligned overlays. Stop at one pass
   unless something is materially broken.
7. **Hard rules in code, taste in prose.** The 13 hard rules below are
   enforced by `render.py`. Everything aesthetic — pacing, music, palette,
   subtitle style — is your call, shaped by the conversation.

## Preflight

Before touching footage, verify the runtime. Do not assume the host installed
the prerequisites correctly just because the skill is present.

1. Confirm Python deps import cleanly from this skill directory. If the check
   fails, stop and tell the user to run `uv sync` here (or run it yourself if
   your host permits local setup work).
2. Confirm `ffmpeg` is on `PATH` with `ffmpeg -version`.
3. Confirm HybrIE is reachable with `HybrieClient().health()`.
4. If the job will use Manim overlays, confirm the sibling skill is ready
   before delegating. Run `bash ../animate-manim/scripts/setup.sh` when that
   relative path exists; otherwise stop and point the user at
   `skills/animate-manim/install.md`.

Suggested commands:

```bash
python -c "import httpx, PIL, numpy; print('python deps ok')"
ffmpeg -version
python -c "from helpers.hybrie_client import HybrieClient; print(HybrieClient().health())"
```

If any preflight step fails, do not start transcription or rendering. Fix the
environment first, then continue.

## Hard Rules

Code-enforced rules can't be bypassed — they're baked into `render.py` /
`hybrie_client.py` and apply on every run. Agent-enforced rules are your job:
nothing checks them at runtime, so a sloppy EDL silently produces a sloppy
cut.

**Code-enforced** (the renderer / client guarantee these):
```
R1  Subtitles applied LAST in the filter chain (overlays don't cover them).
R2  Per-segment extract → lossless `-c copy` concat (never double re-encode).
R3  30 ms audio fades at every cut boundary (no audible pops).
R4  Overlays use setpts=PTS-STARTPTS+T/TB (don't show middle of an animation).
R5  Master SRT uses output-timeline offsets (captions don't drift after concat).
R7  Pad cut edges 100–300 ms (default 150 ms; Whisper segment timestamps drift).
    Drops to 30–200 ms when the source was transcribed with `--word-timestamps`
    (HybrIE v0.1.28 DTW alignment is tighter than segment endpoints).
R8  HybrIE STT request always sends `response_format=verbose_json`. Segment
    granularity is the default; word-level timestamps are opt-in via
    `transcribe.py --word-timestamps` (HybrIE v0.1.28+ pure-Rust DTW).
R9  Cache transcripts per source — `<edit>/transcripts/<stem>.json`.
R12 All session outputs in `<videos_dir>/edit/`.
R13 `hybrie_client.health()` before any work; fail loudly with install hint if
    HybrIE isn't running.
```

**Agent-enforced** (you check these — nothing else will):
```
R6  Cuts at word boundaries when the source was transcribed with
    `--word-timestamps`; otherwise segment boundaries. Never propose a cut at a
    time the transcript doesn't anchor. The renderer accepts any (start, end)
    you give it; landing on a transcript-anchored edge is your discipline.
R10 Run animation generation in parallel sub-agents — the renderer is agnostic.
R11 Confirm strategy with the user before invoking render.py.
```

## The pipeline

```
0. preflight              →  deps, ffmpeg, HybrIE, optional Manim ready
1. transcribe_batch.py    →  edit/transcripts/*.json      (cached, R9, R13)
2. pack_transcripts.py    →  edit/takes_packed.md         (you read this)
3. You propose strategy   →  user confirms                (R11)
4. You write EDL JSON     →  edit/edl.json                (transcript-anchored cuts, R6)
5. timeline_view.py       →  PNGs at decision points      (use sparingly)
6. (optional) animation
   sub-agents in parallel  →  edit/animations/slot_*/*.mp4 (R10)
7. render.py edit/edl.json  →  edit/final.mp4
   ├── extract_segment×N (HDR tonemap + grade + 30 ms fades)
   ├── concat (lossless, R2)
   ├── build_master_srt (output-timeline offsets, R5)
   ├── build_final_composite (overlays first, subs LAST — R1)
   └── apply_loudnorm_two_pass (-14 LUFS / -1 dBTP / LRA 11)
8. Self-eval via timeline_view.py at each cut boundary, then deliver.
```

## EDL contract

The single artifact between you and `render.py`. JSON, written to `edit/edl.json`.

```json
{
  "version": 1,
  "sources": {
    "C0103": "/abs/path/C0103.MP4",
    "C0104": "/abs/path/C0104.MP4"
  },
  "ranges": [
    {
      "source": "C0103",
      "start": 2.42,
      "end": 6.85,
      "beat": "HOOK",
      "quote": "Ninety percent of what a web agent does is completely wasted.",
      "reason": "Strongest delivery; clean head and tail.",
      "grade": "auto"
    }
  ],
  "grade": "auto",
  "overlays": [
    {
      "file": "edit/animations/slot_1/render.mp4",
      "start_in_output": 0.0,
      "duration": 5.0
    }
  ],
  "subtitles": "edit/master.srt",
  "total_duration_s": 87.4
}
```

- `start` / `end` MUST land on a boundary present in the packed transcript:
  word boundaries when the source was transcribed with `--word-timestamps`,
  segment boundaries otherwise (R6).
- `grade` per range overrides the EDL-level `grade`. Accepts a preset name,
  `"auto"`, or a raw ffmpeg filter string. Presets: `none`, `subtle`,
  `neutral_punch`, `warm_cinematic`.
- `subtitles` is optional. If omitted and `--transcripts-dir` is passed to
  render.py, a `master.srt` is generated automatically.
- `overlays[*].start_in_output` is **output-timeline** seconds, not source.

### Confidence flags (HybrIE v0.1.28+)

`pack_transcripts.py` prefixes a phrase line with `?` when HybrIE's
verbose_json reports `no_speech_prob > 0.6` AND `avg_logprob < -1.0` (likely
hallucination), or `compression_ratio > 2.4` (repetitive-token failure).
Before quoting a `?`-flagged segment in an EDL, sample it with
`timeline_view.py` (or your native vision) and confirm the speech is real and
the text matches. Flagged ranges are not forbidden — just verify.

### Prompt conditioning (HybrIE v0.1.28+)

For technical or proper-noun-heavy footage, pass `--prompt` to
`transcribe.py` to bias Whisper decoding toward the right spelling.
Example: `transcribe.py demo.mp4 --prompt "HybrIE, Nebius, Qwen, ffmpeg"`.
Cuts and quotes downstream then read cleanly without manual fix-up.

### Narration / voiceover (HybrIE v0.1.33+)

Local TTS via VibeVoice-1.5B is now part of the skill. `narrate.py`
turns a script into a 24 kHz mono WAV ready to drop into an EDL as an
audio overlay (or to mix under existing audio).

```bash
narrate.py "Welcome to the demo." --out narration.wav
# or from a multi-line script:
narrate.py --script narration.md --out vo.wav
```

The returned WAV is wrapped with the license-required mitigations
already applied server-side:

- An audible 100 ms triple-tone marker prepended to the audio
  (identifies the file as AI-generated; required by VibeVoice's MIT
  carve-out)
- A `LIST INFO` metadata chunk inside the WAV (`IART`/`ICMT`/`ICRD`/`ITCH`)

Do **not** strip these when post-processing. They're part of the
redistribution license. If a downstream tool re-encodes, re-apply the
disclaimer marker (the metadata chunk will not survive re-encode).

## HybrIE configuration

| Env var | Default | Notes |
|---|---|---|
| `HYBRIE_API_URL` | `http://127.0.0.1:8001` | inference HTTP API |
| `HYBRIE_API_KEY` | `hybrie` | bearer token |

`hybrie_client.HybrieClient` reads these. STT runs locally — no network calls
beyond loopback. VLM (`vision()`) is cloud-only in HybrIE v0.1.27 and routes
through Nebius by default (`x-hybrie-cloud-provider: hybrie`).

**Vision strategy:** if the host agent has native vision (Claude, GPT-5),
read `timeline_view.py` PNGs directly with your own multimodal capability —
no `vision()` call needed. Only fall back to `hybrie_client.vision()` from
text-only runtimes.

> stimulir-runtime: see `.codex-plugin/plugin.json` for the manifest shape;
> the contract is identical, only the manifest filename differs.

## Editor sub-agent brief — template

When you have many takes and need to produce the EDL, spawn a focused sub-agent
with this brief:

> You are an editor working on a {DURATION}-second {GENRE} video.
> The packed transcript is below. Pick the best take of each beat. Output ONLY
> a valid EDL JSON. Hard requirements:
> - cuts must land on a transcript-anchored boundary (segment edges by default;
>   word edges if the packed transcript shows per-word lines)
> - never repeat content unless intentional
> - reason field on every range, ≤ 12 words
> - `total_duration_s` must match `sum(end - start)` to within 0.5 s
> Beats: {BEAT_LIST}
> Packed transcript:
> {takes_packed.md content}

## Animation sub-agents

When the EDL has overlays, run them in parallel sub-agents — one per slot.
Each sub-agent gets:
- the slot's start time in the output (for context only — overlay timing is
  enforced by R4 in the renderer; the animation file just starts at frame 0)
- the duration in seconds
- the visual brief (palette, motion direction, copy)
- a hard rule that the animation MUST end on a still frame matching the
  next scene's first frame, otherwise the cut will pop

The renderer is agnostic to the tool the sub-agent uses (Manim, Remotion,
After Effects export, Hyperframes, plain CSS). It just consumes an .mp4.

For Manim overlays specifically, delegate to the sibling `animate-manim`
sub-skill (`skills/animate-manim/`). Hand it a brief — `output_path`,
`duration_s`, `resolution`, `transparent` flag, palette, copy, motion, and
the required `end_frame` — and it returns a deterministic render at that
path. You then register the file as an `EdlOverlay`
(`file=output_path, start_in_output=..., duration=duration_s`).

## Subtitle style

`render.py` uses one fixed style by default — bold-overlay, MarginV=90 (which
keeps text out of the bottom 25–30 % of the frame where TikTok / Reels /
Shorts show their UI chrome). 5-word chunks, ALL CAPS. Don't change this
unless the user asks for a different platform.

## Color grade — when to reach for what

- `none` — material is already graded (sub-agents passing finished overlays).
- `subtle` — default for clean, well-lit talking head from a phone.
- `neutral_punch` — slight contrast lift; good for product B-roll.
- `warm_cinematic` — opt-in only. Strong look. Use when the user explicitly
  asks for "cinematic" or you've confirmed the warmth fits the brand.
- `auto` — gentle, data-driven. Reaches for it by default when mixing
  sources from different cameras/conditions.

## Anti-patterns (do NOT do)

- Cutting at times not present in the transcript (R6, R8).
- Using `timeline_view.py` to scan a whole source — that defeats the
  token-efficiency point. It's for decisions, not surveys.
- Calling `hybrie_client.vision()` when the host agent already has native
  vision — burns cloud credits for nothing.
- Hard-coding `start_in_output` values that overlap range boundaries by more
  than a few hundred ms — overlay extends past the cut, R4 won't save you.
- Editing audio in the composite (`build_final_composite`). Audio is locked
  in at the per-segment extract step. R3 fades are the only audio touchups.
- Skipping the health check. R13 fails fast for a reason — without it, every
  helper hangs at the first STT call until the multipart upload times out.
- Re-running `render.py` after a tiny copy edit and re-transcribing. R9 says
  the transcript is cached. The expensive step is STT; the EDL is cheap.
- Quoting a `?`-flagged segment from `takes_packed.md` without verifying.
  The flag means HybrIE's own confidence metrics suspect a hallucination or
  repetitive-token failure — sample the timestamp before trusting the text.
- Skipping `--prompt` on jargon-heavy footage and then hand-correcting every
  proper-noun typo in the EDL `quote` fields. One prompt at transcribe time
  fixes the whole batch.

## Worked example — 60-second product demo from a folder

```bash
# 0. preflight
python -c "import httpx, PIL, numpy; print('python deps ok')"
ffmpeg -version
python -c "from helpers.hybrie_client import HybrieClient; HybrieClient().health()"

# 1. transcribe everything in parallel (cached on second run)
python helpers/transcribe_batch.py /path/to/footage --workers 4

# 2. pack into the LLM-readable artifact
python helpers/pack_transcripts.py /path/to/footage/edit/transcripts

# 3. (you read takes_packed.md, propose an EDL, user confirms)

# 4. (optional) sample a contested cut to disambiguate two takes
python helpers/timeline_view.py /path/to/footage/C0104.MP4 \
    --start 12.4 --end 18.1 \
    --transcript /path/to/footage/edit/transcripts/C0104.json \
    --out /path/to/footage/edit/views/c0104_takeA.png

# 5. write edit/edl.json (segment-aligned cuts, see EDL contract)

# 6. render
python helpers/render.py /path/to/footage/edit/edl.json \
    --out-dir /path/to/footage/edit \
    --transcripts-dir /path/to/footage/edit/transcripts \
    --quality final
```

## Recovery

If the cache claims a transcript exists but is empty / malformed, delete that
one JSON and rerun `transcribe.py --force <source>`. Don't nuke the whole
transcripts directory unless a HybrIE upgrade requires it (Whisper schema
changes are rare; segment shape has been stable since v0.1.27).
