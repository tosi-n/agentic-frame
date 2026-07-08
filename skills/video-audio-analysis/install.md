# Install — video-audio-analysis

First-time setup runbook. ~5 minutes if HybrIE is already running, ~15 if not.
No prerequisites beyond what `video-edit` already documents.

## 0. Prereqs

```bash
brew install ffmpeg
ffmpeg -version  # should print 6.x or 7.x
```

Python 3.10+ with `uv` recommended:
```bash
brew install uv
```

## 1. HybrIE server (v0.1.28 or later)

This skill calls HybrIE for STT (locally) and for VLM scene descriptions
(cloud). You need the server running before any helper will work.

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
bootstrap point is the `video-audio-analysis` directory itself, not the repo
root.

### Local clone + symlink

Clone agentic-frame, install `video-audio-analysis`'s Python deps, then
point your agent host at the skill directory:

```bash
git clone https://github.com/tosi-n/agentic-frame.git ~/Developer/agentic-frame
cd ~/Developer/agentic-frame/skills/video-audio-analysis
uv sync  # installs httpx
```

For Codex:
```bash
ln -s ~/Developer/agentic-frame/skills/video-audio-analysis ~/.codex/skills/video-audio-analysis
```

For Claude Code:
```bash
ln -s ~/Developer/agentic-frame/skills/video-audio-analysis ~/.claude/skills/video-audio-analysis
```

### `npx skills add`

If you install the skill files through a skill installer, run the same
dependency bootstrap from the installed skill directory afterwards:

```bash
npx skills add tosi-n/agentic-frame

cd ~/.claude/skills/video-audio-analysis   # or ~/.codex/skills/video-audio-analysis
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
scene-description path), set:
```bash
export NEBIUS_API_KEY="..."     # or HYBRIE_CLOUD_API_KEY
```

## 4. Verify

```bash
cd ~/Developer/agentic-frame/skills/video-audio-analysis
python -c "from helpers.hybrie_client import HybrieClient; print(HybrieClient().health())"
# {'status': 'ok', ...}

python helpers/analyze.py /path/to/some/short/clip.mp4 --out /tmp/analysis.json
# prints /tmp/analysis.json on success
```

If `health()` raises `Cannot reach HybrIE at ...`, the server isn't running —
go back to step 1.

## 5. Storage layout

`analyze.py` writes its merged output wherever `--out` points — there is no
fixed session directory the way `video-edit` uses `edit/`, since this skill
has no rendering pipeline and no intermediate artifacts worth persisting
beyond the final JSON. A run looks like:

```
/path/to/video.mp4          (your source, untouched — or fetched to a temp
                              file first if the input was a URL)
analysis.json               (wherever --out points — transcript + scenes)
```

If you want transcript caching the way `video-edit` gets it for free (R9),
pass `--edit-dir` semantics yourself by calling `helpers/transcribe.py`
directly against a persistent directory instead of going through
`analyze.py`'s temp-directory default.
