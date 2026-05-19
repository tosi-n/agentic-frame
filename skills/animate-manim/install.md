---
name: animate-manim-install
description: Install Manim Community Edition and its system dependencies so the animate-manim sub-skill can render overlays for video-edit.
---

# animate-manim install

This sub-skill renders overlay videos with [Manim Community Edition](https://www.manim.community/). The parent `video-edit` skill already requires `ffmpeg`; this file only adds Manim and LaTeX.

Run the commands below from the `animate-manim` skill directory itself:

- cloned repo: `~/Developer/agentic-frame/skills/animate-manim`
- installed skill: `~/.claude/skills/animate-manim` or `~/.codex/skills/animate-manim`

## Prerequisites

- Python 3.10+ (the parent skill already needs this)
- `ffmpeg` on `$PATH` (already installed for `video-edit`)
- LaTeX (for `MathTex` / equation rendering)

## Steps

### 1. Install Python dependencies

```bash
uv sync
```

Reference docs in `references/` were tested against Manim CE v0.20.x. No version is pinned in `pyproject.toml` so the latest stable release is fine; if you hit an API regression, drop to `manim==0.20.1`.

### 2. Install LaTeX

`MathTex` and `Tex` mobjects shell out to `pdflatex`. Skip this only if you are certain no overlay will contain math.

```bash
# macOS (full distribution; ~5 GB but no surprises later)
brew install --cask mactex-no-gui

# Debian / Ubuntu
sudo apt-get install -y texlive-full

# Fedora
sudo dnf install -y texlive-scheme-full
```

A minimal install (`texlive-latex-extra` plus `dvisvgm`) works for most cases but bites later when a reference doc reaches for an unusual package — go full unless disk is tight.

### 3. Verify

Run the bundled setup check:

```bash
bash scripts/setup.sh
```

It checks Python, Manim, `pdflatex`, and `ffmpeg`, printing a green plus or red x for each. All four must pass.

### 4. Smoke test

Write a one-scene file and render it at draft quality:

```bash
cat > /tmp/animate_smoke.py <<'PY'
from manim import *
class Smoke(Scene):
    def construct(self):
        self.add(Text("animate-manim ok", font="Menlo"))
        self.wait(0.5)
PY
manim -ql -p /tmp/animate_smoke.py Smoke
```

`-ql` (480p15 draft) renders in a few seconds. `-p` opens the result. If the file plays, the install is good.

## Notes

- Animation engines are installed lazily — only run this once the parent `video-edit` agent first delegates an overlay brief to `animate-manim`.
- This sub-skill writes `.mp4` output by default. Transparent overlays use the `qtrle` codec or ProRes 4444 in a `.mov` container; see `references/rendering.md`.
- Daily usage lives in `SKILL.md`. The 14 docs in `references/` are the deep manual — the agent loads them on demand.
