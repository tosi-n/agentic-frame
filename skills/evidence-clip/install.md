# Install — evidence-clip

No local hardware permissions needed (unlike `clip-capture`) -- but the
de-identification step needs network access and an API key. ~5 minutes.

## 0. Prereqs

```bash
brew install ffmpeg
ffmpeg -version  # should print 6.x, 7.x, or 8.x

# if the environment uses uv:
uv sync
# otherwise, just install the one runtime dependency:
python3 -m venv .venv && source .venv/bin/activate
pip install "httpx>=0.27"
```

The extraction and provenance helpers (`extract_range.py`, `provenance.py`,
`deid_media.py`) use only ffmpeg and the Python standard library.
`deid_transcript.py` additionally needs `httpx` (installed via `pyproject.toml`).

## 1. Skill install

### Local clone + symlink

```bash
git clone https://github.com/tosi-n/agentic-frame.git ~/Developer/agentic-frame
```

For Codex:
```bash
ln -s ~/Developer/agentic-frame/skills/evidence-clip ~/.codex/skills/evidence-clip
```

For Claude Code:
```bash
ln -s ~/Developer/agentic-frame/skills/evidence-clip ~/.claude/skills/evidence-clip
```

### `npx skills add`

```bash
npx skills add tosi-n/agentic-frame
```

## 2. Network access + API key (only needed for `deid_transcript.py`)

`extract_range.py`, `provenance.py`, and `deid_media.py` are fully local --
no network, no account, no key. `deid_transcript.py` makes a real call to a
hosted Stimulir endpoint and needs both of the following:

```bash
export STIMULIR_API_URL=https://api.stimulir.com   # default, override for self-hosted/staging
export STIMULIR_API_KEY=hyb_...                     # REQUIRED, no default
```

Outbound HTTPS access to `STIMULIR_API_URL` must be reachable from wherever
this skill runs (corporate proxies / egress allowlists that block arbitrary
outbound hosts will need `api.stimulir.com` added explicitly).

### Where to get a `STIMULIR_API_KEY`

This is the same credential plane the Codex App gateway integration uses --
a `hyb_*` key issued from the Stimulir console under your business's API
keys settings (the same place inference/runtime keys for HybrIE-backed
skills come from). If you already have a `hyb_*` key provisioned for
another HybrIE/Stimulir-integrated skill in this repo (e.g. `video-edit`'s
cloud VLM calls), that key works here too -- this endpoint sits on the same
plane, not a separate one. If you don't have one yet, generate it from the
Stimulir console (API Keys section) and store it in your shell profile or
secrets manager -- do not commit it to the repo.

## 3. Verify

```bash
cd ~/Developer/agentic-frame/skills/evidence-clip
ffmpeg -version
python3 -c "import httpx; print('httpx ok')"

# local-only smoke test (no key needed)
ffmpeg -y -f lavfi -i testsrc=duration=2:size=320x240 \
  -f lavfi -i sine=frequency=440:duration=2 -shortest /tmp/ec_smoke.mp4
python3 helpers/extract_range.py /tmp/ec_smoke.mp4 --start 0.2 --end 1.5 --out /tmp/ec_smoke_clip.mp4
python3 helpers/provenance.py /tmp/ec_smoke.provenance.json --op extract --tool extract_range.py \
  --at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --input /tmp/ec_smoke.mp4 --output /tmp/ec_smoke_clip.mp4

# only if STIMULIR_API_KEY is set
echo "test transcript with a fake email test@example.com" > /tmp/ec_smoke.txt
python3 helpers/deid_transcript.py /tmp/ec_smoke.txt --out /tmp/ec_smoke_redacted.txt
```

If `deid_transcript.py` fails with "STIMULIR_API_KEY is not set", go back
to step 2 -- there is no local fallback for this call.

## 4. Notes

- `deid_media.py` needs no key and no network -- it's pure ffmpeg. But it
  also does no detection of any kind (see `SKILL.md`); don't expect it to
  find faces or speakers on its own.
- Corporate/offline environments that cannot reach `STIMULIR_API_URL` can
  still use extraction, provenance, and media painting/muting fully --
  only the transcript PII scrub step is blocked without network access.
