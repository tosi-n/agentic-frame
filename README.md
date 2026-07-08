# agentic-frame

Installable media-production skills for coding agents.

The repo currently ships five sibling skills:

- `video-edit` — transcript-first video editing powered by HybrIE, with `ffmpeg` for deterministic rendering
- `animate-manim` — Manim overlay rendering used by `video-edit` when an edit needs motion graphics
- `clip-capture` — bare-bone screen/webcam/mic recording and trim, `ffmpeg` only, no server or cloud dependency
- `video-audio-analysis` — transcript + visual scene analysis for a video/audio file already on disk or in remote storage; hosted-capable, no live-hardware dependency
- `evidence-clip` — extract a sub-range as a standalone artifact with chain-of-custody, plus optional de-identification (real hosted transcript-PII scrub; media redaction is agent-directed, not automatic — see the skill's `SKILL.md`)

## Install

### `npx skills add`

```bash
npx skills add tosi-n/agentic-frame
```

After the skill files are installed, bootstrap dependencies per skill from the
installed skill directory itself:

```bash
cd ~/.claude/skills/video-edit      # or ~/.codex/skills/video-edit
uv sync

cd ~/.claude/skills/animate-manim   # or ~/.codex/skills/animate-manim
uv sync
```

`animate-manim` also needs the system dependencies in
[`skills/animate-manim/install.md`](./skills/animate-manim/install.md), most
notably LaTeX for `MathTex`.

`clip-capture` needs no `uv sync` for runtime use — its helpers are pure
standard library, only `ffmpeg` on `PATH`. See
[`skills/clip-capture/install.md`](./skills/clip-capture/install.md) for the
one-time macOS Screen Recording permission grant.

```bash
cd ~/.claude/skills/video-audio-analysis
uv sync  # installs httpx

cd ~/.claude/skills/evidence-clip
uv sync  # installs httpx
```

`evidence-clip` also needs network access to a Stimulir gateway endpoint and
a `STIMULIR_API_KEY` for its transcript de-identification step — see
[`skills/evidence-clip/install.md`](./skills/evidence-clip/install.md).

### Local clone + symlink

```bash
git clone https://github.com/tosi-n/agentic-frame.git ~/Developer/agentic-frame

cd ~/Developer/agentic-frame/skills/video-edit
uv sync

cd ~/Developer/agentic-frame/skills/animate-manim
uv sync

cd ~/Developer/agentic-frame/skills/video-audio-analysis
uv sync

cd ~/Developer/agentic-frame/skills/evidence-clip
uv sync
```

Then point your host at the skill directories you want:

```bash
ln -s ~/Developer/agentic-frame/skills/video-edit ~/.codex/skills/video-edit
ln -s ~/Developer/agentic-frame/skills/animate-manim ~/.codex/skills/animate-manim
ln -s ~/Developer/agentic-frame/skills/clip-capture ~/.codex/skills/clip-capture
ln -s ~/Developer/agentic-frame/skills/video-audio-analysis ~/.codex/skills/video-audio-analysis
ln -s ~/Developer/agentic-frame/skills/evidence-clip ~/.codex/skills/evidence-clip
```

Or for Claude Code:

```bash
ln -s ~/Developer/agentic-frame/skills/video-edit ~/.claude/skills/video-edit
ln -s ~/Developer/agentic-frame/skills/animate-manim ~/.claude/skills/animate-manim
ln -s ~/Developer/agentic-frame/skills/clip-capture ~/.claude/skills/clip-capture
ln -s ~/Developer/agentic-frame/skills/video-audio-analysis ~/.claude/skills/video-audio-analysis
ln -s ~/Developer/agentic-frame/skills/evidence-clip ~/.claude/skills/evidence-clip
```

## Repo layout

```text
agentic-frame/
├── .codex-plugin/
├── .claude-plugin/
└── skills/
    ├── video-edit/
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── install.md
    │   ├── pyproject.toml
    │   └── helpers/
    ├── animate-manim/
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── install.md
    │   ├── pyproject.toml
    │   ├── references/
    │   └── scripts/
    ├── clip-capture/
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── install.md
    │   ├── pyproject.toml
    │   └── helpers/
    ├── video-audio-analysis/
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── install.md
    │   ├── pyproject.toml
    │   └── helpers/
    └── evidence-clip/
        ├── SKILL.md
        ├── README.md
        ├── install.md
        ├── pyproject.toml
        └── helpers/
```

Each skill owns its own `pyproject.toml`. There is intentionally no repo-root
`uv sync` entrypoint.
