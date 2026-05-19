# animate-manim

Deterministic Manim overlay rendering for the sibling `video-edit` skill.

`video-edit` owns the editorial decisions and the EDL. `animate-manim` only
renders one overlay at a time: lower-thirds, progress bars, callouts,
equation reveals, architecture diagrams, and similar motion-graphics slots.

## Install

Run dependency setup from this directory itself, or from the installed skill
directory after `npx skills add`:

```bash
uv sync
```

Then follow [`install.md`](./install.md) for system dependencies, verification,
and a Manim smoke test.

## Contract

The parent skill hands this sub-skill:

- `output_path`
- `duration_s`
- `resolution`
- `transparent`
- `palette`
- `copy`
- `motion`
- `end_frame`

The output must land exactly at `output_path`, start at frame 0, and end on a
held still the parent can cut against cleanly.
