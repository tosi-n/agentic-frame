# agentic-frame

Installable media-production skills for coding agents.

The repo currently ships two sibling skills:

- `video-edit` — transcript-first video editing powered by HybrIE, with `ffmpeg` for deterministic rendering
- `animate-manim` — Manim overlay rendering used by `video-edit` when an edit needs motion graphics

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

### Local clone + symlink

```bash
git clone https://github.com/tosi-n/agentic-frame.git ~/Developer/agentic-frame

cd ~/Developer/agentic-frame/skills/video-edit
uv sync

cd ~/Developer/agentic-frame/skills/animate-manim
uv sync
```

Then point your host at the skill directories you want:

```bash
ln -s ~/Developer/agentic-frame/skills/video-edit ~/.codex/skills/video-edit
ln -s ~/Developer/agentic-frame/skills/animate-manim ~/.codex/skills/animate-manim
```

Or for Claude Code:

```bash
ln -s ~/Developer/agentic-frame/skills/video-edit ~/.claude/skills/video-edit
ln -s ~/Developer/agentic-frame/skills/animate-manim ~/.claude/skills/animate-manim
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
    └── animate-manim/
        ├── SKILL.md
        ├── README.md
        ├── install.md
        ├── pyproject.toml
        ├── references/
        └── scripts/
```

Each skill owns its own `pyproject.toml`. There is intentionally no repo-root
`uv sync` entrypoint.
