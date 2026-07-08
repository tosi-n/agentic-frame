---
name: clip-capture
description: Record a short screen, webcam, or mic clip, and trim an existing clip to a sub-range. Use when the user wants to capture their screen, record a quick webcam/audio clip, or cut a range out of an existing video file. Bare-bone and local-only -- ffmpeg, no server, no cloud, no HybrIE dependency.
---

# Clip Capture (bare-bone)

Two jobs, nothing else: **record** a clip from local hardware, and **trim** a
range out of any video file. No sharing, no analytics, no upload, no server.
That is a deliberate scope boundary, not a missing feature -- see
"Capability tiers" below.

## Preflight

Before recording or trimming, confirm the runtime:

```bash
ffmpeg -version
python helpers/list_devices.py
```

`list_devices.py` must return real device entries (not an empty list) before
`capture.py` is called. On macOS, listing devices always succeeds even
without permission -- capture is what actually needs the OS grant (see
Capability tiers).

## Capability tiers

| Capability | Status |
|---|---|
| List displays / cameras / mics | Self-contained, works today |
| Record a full display / camera / mic | Self-contained, but needs a one-time OS permission grant (see below) -- cannot be scripted |
| Record a single window/app (not the whole display) | Not supported -- ffmpeg's avfoundation only sees whole displays; window-level picking needs Apple's ScreenCaptureKit, out of scope here |
| Trim an existing clip | Self-contained, works today |
| Linux capture | X11 only (`x11grab`); does not work under Wayland |
| Share a link / view analytics | Out of scope for this skill -- needs external storage and a persistent server; see Anti-patterns |

## The two workflows

### Record

1. `python helpers/list_devices.py` -- get device indices.
2. `python helpers/capture.py --screen-index <n> [--camera-index <n>] [--mic-index <n>] --duration <seconds> --out <path.mp4>`
3. Optionally hand the output file to the sibling `video-edit` skill for
   transcription, multi-take editing, subtitles, or color grade -- this
   skill does not duplicate that pipeline.

Picture-in-picture (screen + webcam overlay) works when both
`--screen-index` and `--camera-index` are given -- the camera is composited
into the bottom-right corner.

`--duration` is always required. There is no open-ended background
recording from this helper -- if the user wants "record until I say stop",
pick a duration up front or re-invoke the helper; don't try to make it a
long-running process.

### Trim

```bash
python helpers/trim.py <in.mp4> --start <s> --end <s> --out <out.mp4>
```

Default is lossless (`-c copy`, keyframe-snapped). Pass `--exact` when the
cut needs to land on the precise frame rather than the nearest keyframe --
this forces a re-encode.

## Preflight self-check

`capture.py --selftest` runs a 2-second dry-run capture of the first screen
device and validates the output with `ffprobe` before trusting a real
recording. Run this once per environment (or whenever capture output looks
suspiciously black/empty) rather than discovering a permission problem
mid-task:

```bash
python helpers/capture.py --selftest --out /tmp/clip-capture-selftest.mp4
```

## macOS screen recording permission

`ffmpeg` cannot capture the screen, camera, or microphone until the
terminal/app running it has been granted access under **System Settings ->
Privacy & Security -> Screen Recording** (and Camera / Microphone for those
inputs). This is a one-time, manual grant -- there is no command that grants
it, and `capture.py` fails loudly rather than silently writing a black clip
if it's missing.

## Anti-patterns (do NOT do)

- Recording with no `--duration` cap, or looping `capture.py` to fake
  "record until stopped" -- pick a duration and re-invoke if more is needed.
- Building a share link, upload step, or view-tracking endpoint inside this
  skill. That needs a persistent, publicly-reachable service and a storage
  account -- infrastructure this skill deliberately does not become. If the
  user wants sharing, that's a separate, explicit, opt-in capability with
  its own dependencies -- not something this skill defaults to.
- Assuming `list_devices.py` succeeding means capture will work -- listing
  devices requires no permission; capturing does.
- Re-implementing `video-edit`'s transcription/EDL/render pipeline here.
  `trim.py` is a single cut, not a multi-segment renderer -- hand off to
  `video-edit` for anything beyond that.
- Treating `--exact` as the default. Keyframe-snapped `-c copy` is faster
  and lossless; only re-encode when frame-accuracy actually matters.
