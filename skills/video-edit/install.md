# Install — video-edit

First-time setup runbook. ~5 minutes if HybrIE is already running, ~15 if not.

## 0. Prereqs

```bash
brew install ffmpeg
ffmpeg -version  # should print 6.x or 7.x
```

Python 3.10+ with `uv` recommended:
```bash
brew install uv
```

## 1. HybrIE server (v0.1.27 or later)

This skill calls HybrIE for STT (locally) and optionally for VLM (cloud).
You need the server running before any helper will work.

If you don't already have it cloned:
```bash
git clone https://github.com/tosi-n/HybrIE ~/Developer/HybrIE
cd ~/Developer/HybrIE
```

Start the server with the inference HTTP API enabled on port 8001:
```bash
HYBRIE_INFERENCE_API_BIND=0.0.0.0:8001 \
HYBRIE_INFERENCE_API_ENABLED=true \
cargo run --release --bin hybrie-server -- --config hybrie-config.toml
```

Confirm it's healthy:
```bash
curl -s http://127.0.0.1:8001/v1/health | jq
# expected: {"status":"ok", "backends": {...}}
```

The first call to `/v1/audio/transcriptions` will download the Whisper weights
to the configured cache (default `~/.hybrie-models`). Budget a minute or two
for the first run.

## 2. Skill install

Each skill in `agentic-frame` owns its own Python environment. The correct
bootstrap point is the `video-edit` directory itself, not the repo root.

### Local clone + symlink

Clone agentic-frame, install `video-edit`'s Python deps, then point your agent
host at the skill directory:

```bash
git clone https://github.com/tosi-n/agentic-frame.git ~/Developer/agentic-frame
cd ~/Developer/agentic-frame/skills/video-edit
uv sync  # installs httpx, pillow, numpy, librosa
```

For Codex:
```bash
ln -s ~/Developer/agentic-frame/skills/video-edit ~/.codex/skills/video-edit
```

For Claude Code:
```bash
ln -s ~/Developer/agentic-frame/skills/video-edit ~/.claude/skills/video-edit
```

### `npx skills add`

If you install the skill files through a skill installer, run the same
dependency bootstrap from the installed skill directory afterwards:

```bash
npx skills add tosi-n/agentic-frame

cd ~/.claude/skills/video-edit   # or ~/.codex/skills/video-edit
uv sync
```

If you also plan to render Manim overlays, bootstrap the sibling installed
skill as well:

```bash
cd ~/.claude/skills/animate-manim   # or ~/.codex/skills/animate-manim
uv sync
```

### Optional plugin marketplace flow

```bash
codex plugin marketplace add https://github.com/tosi-n/agentic-frame --sparse .codex-plugin --sparse skills
```

## 3. Configure HybrIE access

Two env vars, both with sensible defaults:

```bash
export HYBRIE_API_URL="http://127.0.0.1:8001"   # default
export HYBRIE_API_KEY="hybrie"                   # default
```

If you've configured Nebius access on the HybrIE server (for the cloud VLM
fallback path), set:
```bash
export NEBIUS_API_KEY="..."     # or HYBRIE_CLOUD_API_KEY
```

## 4. Verify

```bash
cd ~/Developer/agentic-frame/skills/video-edit
python -c "from helpers.hybrie_client import HybrieClient; print(HybrieClient().health())"
# {'status': 'ok', ...}

python helpers/transcribe.py /path/to/some/short/clip.mp4
# prints the path of the cached transcript
```

If `health()` raises `Cannot reach HybrIE at ...`, the server isn't running —
go back to step 1.

## 5. Storage layout

A first run on `/path/to/footage/` produces:

```
/path/to/footage/
├── C0103.MP4           (your sources, untouched)
├── C0104.MP4
└── edit/                       (everything the skill writes — R12)
    ├── transcripts/
    │   ├── C0103.json
    │   └── C0104.json
    ├── takes_packed.md         (you read this)
    ├── views/
    │   └── *.png               (timeline_view outputs, on demand)
    ├── animations/
    │   └── slot_*/render.mp4   (sub-agent overlays)
    ├── edl.json                (you write this)
    ├── master.srt              (auto-generated from segments)
    └── final.mp4               (the deliverable)
```

R9 — once `transcripts/` is populated, re-runs are free. Delete a single JSON
and pass `--force` to retranscribe just that source.
