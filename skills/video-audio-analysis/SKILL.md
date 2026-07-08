---
name: video-audio-analysis
description: Analyze a video/audio file's transcript and visual scenes — full Whisper transcript plus timestamped, factual scene descriptions sampled across the runtime. The source may already be in remote/tenant storage (a signed URL is fetched and materialized locally first). Use when the user wants to understand what's in a video/audio file — searchable transcript, scene-by-scene summary, or both — without editing or rendering anything.
---

# Video / Audio Analysis (HybrIE)

Pure file-in/file-out analysis. No editorial decisions, no rendering, no
output video — you get a transcript and a list of timestamped scene
descriptions back as JSON. HybrIE does the inference (local Whisper for
STT, cloud VLM for scene descriptions); ffmpeg does the deterministic frame
sampling.

## Placement rationale

This skill is HOSTED-CAPABLE: unlike clip-capture (local hardware only),
this is pure file-in/file-out processing with no live-hardware dependency,
so it can run locally against a local path OR against a video already
sitting in remote/tenant storage (fetched via a signed URL). No server is
ever started by this skill.

## Self-contained by design

This skill vendors `hybrie_client.py` and `transcribe.py` from `video-edit`
rather than depending on that skill being installed alongside it. That's a
deliberate repo convention, not duplication by accident — every skill in
`agentic-frame` is fully independent: no shared package, no cross-skill
imports, no install-order coupling. If you've already read `video-edit`'s
copies of these files, the ones here are byte-identical.

## Capability tiers

| Capability | Status |
|---|---|
| Analyze a local file | Self-contained, works anywhere ffmpeg + HybrIE are reachable |
| Analyze a file from remote/tenant storage (signed URL) | Same analysis, one extra hop — network reachability to that storage endpoint is the only added external dependency |
| Transcript (local Whisper via HybrIE) | Runs on the HybrIE host, no per-minute API cost |
| Scene descriptions (VLM) | Cloud-only in current HybrIE (routes through Nebius by default) — this is the same trade-off `video-edit` documents for `vision()` |

Analysis itself has no hardware dependency and runs anywhere this skill's
Python environment and HybrIE are reachable. The only thing that changes
between a local file and a remote/tenant-storage URL is whether
`fetch_source.py` does a copy or a download — everything downstream is
identical.

## Preflight

Before analyzing anything, verify the runtime. Do not assume the host
installed the prerequisites correctly just because the skill is present.

1. Confirm Python deps import cleanly from this skill directory. If the
   check fails, stop and tell the user to run `uv sync` here (or run it
   yourself if your host permits local setup work).
2. Confirm `ffmpeg` is on `PATH` with `ffmpeg -version`.
3. Confirm HybrIE is reachable with `HybrieClient().health()`.

Suggested commands:

```bash
python -c "import httpx; print('python deps ok')"
ffmpeg -version
python -c "from helpers.hybrie_client import HybrieClient; print(HybrieClient().health())"
```

If any preflight step fails, do not start fetching, transcribing, or
sampling frames. Fix the environment first, then continue. Both
`describe_scenes.py` and `analyze.py` also run this health check
themselves before doing any ffmpeg work — the preflight above is so you
don't waste a round trip discovering that in the middle of a run.

## The pipeline

```
0. preflight              →  deps, ffmpeg, HybrIE
1. fetch_source.py        →  local path, regardless of whether <input> was
                              a URL or already local
2. transcribe.py          →  full transcript (verbose_json; word timestamps
                              opt-in via --word-timestamps)
3. describe_scenes.py     →  timestamped scene descriptions, sampled every
                              --interval-seconds
4. analyze.py             →  merges 2+3 into one JSON artifact
```

`analyze.py` is the orchestrator — it imports `fetch_source`,
`transcribe`, and `describe_scenes` as modules and calls their functions
directly (no subprocess fan-out), so a single run does the fetch, the
transcript, and the scene sampling in one process.

## CLI reference

```bash
# resolve a URL or local path to a known local file
python helpers/fetch_source.py <input> --out <local_path>

# transcript only (see video-edit's transcribe.py for full flag docs)
python helpers/transcribe.py <video_path> [--word-timestamps] [--prompt "..."]

# scene descriptions only
python helpers/describe_scenes.py <video_path> --out <json_path> \
    [--interval-seconds 30]

# both, merged, source may be a URL or local path
python helpers/analyze.py <input> --out <json_path> \
    [--interval-seconds 30] [--word-timestamps]
```

## Output contract

`analyze.py` writes one JSON artifact to `--out`:

```json
{
  "transcript": { "...": "HybrieClient.transcribe() verbose_json payload" },
  "scenes": [
    { "timestamp_s": 0.0, "description": "A studio desk with a laptop, presenter visible, no on-screen text." },
    { "timestamp_s": 30.0, "description": "Screen share of a code editor, terminal panel open at the bottom." }
  ],
  "source": "https://tenant-storage.example.com/signed/original-input.mp4"
}
```

- `transcript` is exactly what `HybrieClient.transcribe()` returns (the same
  payload `video-edit`'s `transcribe.py` caches), so anything that already
  knows how to read a HybrIE transcript JSON can read this field unchanged.
- `scenes` is ordered by `timestamp_s`, one entry per sampled frame.
- `source` is the original `<input>` string exactly as passed on the CLI —
  useful for tracing back to a URL when the fetched copy was a temp file.

## HybrIE configuration

| Env var | Default | Notes |
|---|---|---|
| `HYBRIE_API_URL` | `http://127.0.0.1:8001` | inference HTTP API |
| `HYBRIE_API_KEY` | `hybrie` | bearer token |

`hybrie_client.HybrieClient` reads these. STT runs locally — no network
calls beyond loopback. VLM (`vision()`) is cloud-only in HybrIE v0.1.27+
and routes through Nebius by default (`x-hybrie-cloud-provider: hybrie`).

## Anti-patterns (do NOT do)

- Subprocessing out to `fetch_source.py` / `describe_scenes.py` from
  `analyze.py` — import them as modules and call their functions directly.
  The whole point of the orchestrator is to avoid re-spawning a Python
  process (and re-opening an `HybrieClient`) per stage.
- Skipping the health check before sampling frames. Frame extraction via
  ffmpeg is cheap to waste but still wasteful — `describe_scenes.py` checks
  `HybrieClient().health()` before running a single `ffmpeg -ss` call.
- Assuming `<input>` is always a local path. Check for `http://` /
  `https://` first (see `fetch_source.is_url`) — treating a signed URL as
  a filesystem path fails confusingly deep in `Path.is_file()`.
- Re-implementing transcript extraction. `transcribe_video()` already does
  ffmpeg → mono 16 kHz WAV → HybrIE upload → cache; call it, don't
  reinvent it.
- Setting `--interval-seconds` so low that scene sampling dominates
  runtime cost. Each sampled frame is one cloud VLM call; for a long video,
  30–60s intervals are a reasonable default unless the user asks for finer
  granularity.
