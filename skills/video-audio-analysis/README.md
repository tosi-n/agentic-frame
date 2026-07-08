# video-audio-analysis

A video/audio analysis skill for Codex / Claude Code / future Stimulir
code-runtime, powered by [HybrIE](https://github.com/tosi-n/HybrIE) v0.1.28.

Pure file-in/file-out: give it a local path or a signed URL, get back a
transcript and a list of timestamped scene descriptions as one JSON
artifact. No editing, no rendering, no output video.

## Why

- Hosted-capable: the source can be a local file OR a video already sitting
  in remote/tenant storage (fetched via a signed URL) — no live-hardware
  dependency, so this runs the same way in a local dev loop or in a
  server-side job.
- Local-first STT: HybrIE runs Whisper locally, no per-minute API cost for
  the transcript.
- Self-contained: vendors `hybrie_client.py` and `transcribe.py` rather than
  depending on `video-edit` being installed alongside it — every skill in
  this repo stands alone.

## Quick start

```bash
# 1. start HybrIE on :8001 (see install.md)

# 2. analyze a local file
python helpers/analyze.py /path/to/video.mp4 --out analysis.json

# 3. or analyze a file already in remote/tenant storage
python helpers/analyze.py "https://tenant-storage.example.com/signed/clip.mp4" \
    --out analysis.json

# 4. word-level timestamps + finer scene sampling
python helpers/analyze.py /path/to/video.mp4 --out analysis.json \
    --word-timestamps --interval-seconds 15
```

Output is one JSON file: `{"transcript": {...}, "scenes": [...], "source": "..."}`.
See [`SKILL.md`](./SKILL.md) for the full output contract.

## Architecture

```
<input> (local path or URL)
    → fetch_source.py    (materializes a local path either way)
    → transcribe.py       (HybrIE local Whisper, verbose_json)
    → describe_scenes.py  (ffmpeg frame sampling + HybrIE VLM per frame)
    → analyze.py           (merges transcript + scenes → one JSON artifact)
```

`analyze.py` imports the other helpers as modules and calls their functions
directly — one process, one `HybrieClient`, no subprocess fan-out.

See [`SKILL.md`](./SKILL.md) for the full playbook the agent reads, and
[`install.md`](./install.md) for setup.

## What's different from `video-edit`

| | `video-edit` | `video-audio-analysis` (this skill) |
|---|---|---|
| Output | rendered `.mp4` (a finished cut) | JSON (transcript + scene descriptions) |
| Editorial reasoning | yes (EDL, cuts, grade, overlays) | none — analysis only |
| Input origin | local footage folder | local path OR remote/tenant-storage URL |
| Rendering | ffmpeg extract/concat/composite | none |
| Shared helpers | — | vendors `hybrie_client.py` + `transcribe.py` verbatim |
