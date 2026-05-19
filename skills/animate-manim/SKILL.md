---
name: animate-manim
description: Author Manim animation overlays for the video-edit parent skill. Spawned in parallel sub-agents — one per overlay slot — when an EDL has overlay entries. Renders a deterministic .mp4 (or .mov for alpha) at the path the parent supplies. Use for progress bars, callouts, equation reveals, architecture diagrams, lower-thirds, data counters, and any geometric / typographic motion the parent's editor can describe in a brief.
---

> **Attribution.** The 14 reference docs under `references/` and `scripts/setup.sh` are vendored verbatim from the `manim-video` sub-skill of [browser-use/video-use](https://github.com/browser-use/video-use). They are intact educational references about Manim itself; ignore mentions of ElevenLabs, Qwen3-TTS, or other video-use-specific tooling — your context is HybrIE-powered. See `LICENSE.upstream` for the full attribution and licensing note.

# animate-manim

You are the animation overlay author for the `video-edit` parent skill. The parent owns the cut, the timing, and the EDL. You own one overlay file. You receive a brief, you produce a deterministic Manim render at the absolute path the parent supplied, and you exit.

## Contract with `video-edit`

The parent invokes you in parallel — one sub-agent per overlay slot — and hands you a brief:

| Field | Meaning |
|-------|---------|
| `output_path` | Absolute path the rendered file must end up at, e.g. `/Users/.../footage/edit/animations/slot_1/render.mp4`. The parent will register this verbatim as the `file` on an `EdlOverlay`. |
| `duration_s` | Exact duration in seconds. The parent's renderer trims to this, but a render that is shorter than `duration_s` will leave a hole — make it match. |
| `resolution` | `1080p` (the default), `720p`, or specific `WxH`. Render at `-qh` for 1080p, `-qm` for 720p. |
| `transparent` | If true, render with alpha to a `.mov` (`qtrle` or ProRes 4444). Otherwise `.mp4` over the palette background. |
| `palette` / `copy` / `motion` | Creative direction. Use the parent's stated palette over the upstream defaults. |
| `end_frame` | What the last frame must look like — usually a still that matches the next scene's first frame, so the cut into post-overlay footage doesn't pop. |

The integration point is `skills/video-edit/helpers/render.py`'s `EdlOverlay`:

```python
@dataclass
class EdlOverlay:
    file: Path
    start_in_output: float
    duration: float
```

You write the file. The parent decides `start_in_output`. Don't try to influence parent timing — your render starts at frame 0, plays for `duration_s`, ends on the still the parent asked for. R4 in the parent's renderer aligns the rest.

## Preflight

Before writing `script.py`, verify the render toolchain from this skill
directory. Do not assume `manim`, `ffmpeg`, or `pdflatex` exist just because
the skill was installed.

1. Run `bash scripts/setup.sh`.
2. If any check fails, stop and follow `install.md` before attempting a render.
3. If the brief needs `MathTex` / `Tex`, treat a missing `pdflatex` as a hard
   blocker, not a warning.
4. If the output needs transparency, make sure your render command and output
   container match (`.mov` with alpha), then verify the final file with
   `ffprobe`.

Suggested commands:

```bash
bash scripts/setup.sh
python -c "import manim; print('manim ok')"
ffprobe -version
```

If preflight is red, do not render speculatively and hope it works.

## Hard rules (the 5 that bite first)

The references hold the full craft manual. Internalise these five before writing a line of code:

1. **First-render excellence.** No iteration rounds. The parent renders this overlay once and composites. If it looks like "AI-generated slides," it's wrong. (`references/production-quality.md`)
2. **Geometry before algebra.** Show the shape, then the symbol. Visual memory encodes faster than symbolic memory. (`references/animation-design-thinking.md`)
3. **Opacity layering directs attention.** Primary at 1.0, contextual at 0.4, structural (axes, grids) at 0.15. Never everything full-bright. (`references/visual-design.md`)
4. **Breathing room.** Every `self.play(...)` is followed by `self.wait(...)`. A 2-second pause after an "aha" reveal is never wasted. (`references/animations.md`)
5. **End on the still the parent asked for.** The final frame must match `end_frame` in the brief; if the brief omits it, end on a held composition that fades cleanly. The parent's R4 placement assumes a held tail. (`references/scene-planning.md`)

LaTeX trap: always raw-string MathTex literals (`MathTex(r"\frac{1}{2}")`). Mobject trap: never animate a mobject you haven't `add`'d or `play(Create(...))`'d. Both eat hours.

## References (load on demand)

| File | Use when |
|------|----------|
| `references/scene-planning.md` | Writing the `plan.md` for a multi-beat overlay |
| `references/animation-design-thinking.md` | Deciding whether to animate or hold static |
| `references/animations.md` | Picking `Write` vs `FadeIn` vs `Create`, rate functions, run_time |
| `references/mobjects.md` | Text, shapes, VGroup, positioning |
| `references/visual-design.md` | Palettes, opacity layering, layout templates |
| `references/equations.md` | LaTeX equations, `TransformMatchingTex`, derivation patterns |
| `references/graphs-and-data.md` | Axes, plots, BarChart, animated counters |
| `references/camera-and-3d.md` | `MovingCameraScene`, `ThreeDScene`, parametric surfaces |
| `references/updaters-and-trackers.md` | `ValueTracker`, `add_updater`, `always_redraw` |
| `references/decorations.md` | `Brace`, `SurroundingRectangle`, arrows, dashed lines |
| `references/paper-explainer.md` | Turning a paper into an animated explanation |
| `references/rendering.md` | CLI flags, transparent output (`-t`), GIF export, ffmpeg muxing |
| `references/troubleshooting.md` | LaTeX errors, animation errors, common mistakes |
| `references/production-quality.md` | Pre-code, pre-render, post-render checklists |

## Workflow

```
preflight  →  brief from parent  →  plan.md  →  script.py  →  manim -qh script.py SceneName -o <output_path>  →  done
```

1. Run preflight from this directory. If `scripts/setup.sh` fails, stop and fix the environment first.
2. Read the brief. Note `output_path`, `duration_s`, `resolution`, `transparent`, `end_frame`.
3. (Optional, for multi-beat overlays) Write `plan.md` next to the script — narrative arc, mobjects, color, timing per beat. See `references/scene-planning.md`.
4. Write `script.py` with **one Scene class**. Sum of all `play(run_time=...)` plus `wait(...)` must equal `duration_s` to within ~50 ms. End on the held still.
5. Render directly to `output_path`. `manim` writes to `media/videos/script/<quality>/SceneName.mp4` by default; pass `-o` and `--media_dir` (or move the result) so the deliverable lands at the brief's path.
6. Verify duration with `ffprobe -v error -show_entries format=duration -of csv=p=0 <output_path>`. Re-render if off by more than 100 ms.

## Invocation examples

The parent agent supplies these as a brief; you execute:

1. **Progress bar fill, 4 s, opaque, 1080p.**
   Brief: `output_path=/.../edit/animations/slot_1/progress.mp4, duration_s=4.0, resolution=1080p, transparent=false, palette={bg:#1C1C1C, fg:#58C4DD}, copy="30% → 80%", motion="bar fills left-to-right with monospace label tracking the value"`. End on the bar held at 80% for the last 0.5 s.
2. **Equation reveal, 6 s, transparent overlay over talking head, 1080p.**
   Brief: `output_path=/.../edit/animations/slot_2/eq.mov, duration_s=6.0, resolution=1080p, transparent=true, copy="L = -E[log p(y|x)]", motion="MathTex Write, then Brace under the cross-entropy term, then FadeOut Brace"`. Use `manim -qh -t script.py Eq` and `qtrle` codec; reference `references/rendering.md`.
3. **Lower-third name plate, 3 s, opaque, 1080p.**
   Brief: `output_path=/.../edit/animations/slot_3/lower_third.mp4, duration_s=3.0, palette=neon-tech, copy="Toxin Daniels — Founder", motion="bar slides in from left, name writes on, hold, FadeOut last 0.3 s"`. End on the empty palette background so it dissolves cleanly into the next cut.

## Deviations from upstream

The reference docs assume a standalone Manim film: full scenes, multi-scene stitching, voiceover. You are emitting one short overlay clip per invocation. Treat the docs as Manim craft knowledge — the workflow above (one Scene, one file, one `manim` invocation, exit) is the contract that matters.

When in doubt, render at `-ql` first to check composition, then re-render at `-qh` for the deliverable.
