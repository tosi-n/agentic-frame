# clip-capture

A bare-bone screen/webcam/mic capture and trim skill for Codex / Claude Code.
No server, no cloud, no HybrIE dependency -- just `ffmpeg`.

## Why

- Local-first: recording and trimming both run entirely on your machine.
- Deliberately narrow: this is the minimal "make a clip" loop -- record a
  timed clip, cut a range out of one. Sharing, view analytics, and
  transcription are explicit non-goals here, not missing pieces (see
  "Capability tiers" in [`SKILL.md`](./SKILL.md)) -- they need infrastructure
  (storage, a persistent server) that doesn't belong inside a skill.
- Composable: hand a captured or trimmed clip to the sibling `video-edit`
  skill for transcription, multi-take editing, subtitles, or color grade.

## Quick start

```bash
# 1. see what's available to record from
python helpers/list_devices.py

# 2. record a 10s screen clip with mic audio
python helpers/capture.py --screen-index 1 --mic-index 0 --duration 10 --out demo_raw.mp4

# 3. trim it down to the good part
python helpers/trim.py demo_raw.mp4 --start 2.4 --end 8.1 --out demo_clip.mp4
```

See [`SKILL.md`](./SKILL.md) for the full playbook and [`install.md`](./install.md)
for setup, including the one-time macOS Screen Recording permission grant.
