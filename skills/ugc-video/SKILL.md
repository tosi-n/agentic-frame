---
name: ugc-video
description: Turn an approved script and avatar assets into a vertical UGC video using Stimulir speech and Dreamina Seedance 2.5, then inspect and edit the result.
---

# UGC video

Adapted from [Graphed marketing-skills ugc-video](https://github.com/graphed-inc/marketing-skills/tree/main/skills/ugc-video), MIT license. Its Graphed, fal, and kie calls are not part of this port.

## Inputs

Require an approved script and a reference image or video for the presenter. Use only an authorized likeness and voice. Preserve the exact spoken wording in a text file. Estimate the duration from the actual recorded speech before choosing a video duration. Dreamina Seedance 2.5 accepts 4–30 seconds per generation in the installed CLI; split longer scripts into shot-sized segments and edit them together.

## Speech through Stimulir

For ordinary speech, use `POST /api/v1/inference/audio/speech` with the workspace gateway key and project scope, and choose an enabled model from the live catalog. For a reference voice, Stimulir's resident HybrIE audio worker supports `openweight/mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit` on Apple Silicon through a scoped `kind:tts` audio job. It requires `input`, an authorized `reference_audio` data URL, and `reference_text` (or an explicit `x_vector_only:true` mode). Discover a ready deployment and its fingerprint/revision before submitting; use the operator-scoped `media-generate` helper when available. This is not a public Console inference route. If that worker is not ready or the required scope is unavailable, use an already approved recording or report the blocked voice step. Save the resulting audio and listen to the entire file before using it as a video reference.

## Video through Dreamina

Follow the installed `dreamina-canvas-cli` skill for authentication, canvas, reference upload, quote, generation, recovery, and delivery. Run `dreamina-canvas model find 'Seedance 2.5' --type video` for live discovery. The verified CLI v1.3.0 canonical model is `seedance_2.5` and its `m2v` mode accepts image and audio references. Use the current model result and `schema` to form actual commands; do not use Graphed's `kie:bytedance/seedance-2-5` ID or a BytePlus API ID with this CLI. Use 9:16 and a duration that covers the spoken audio, within the current model limits. Use an audio reference for sync, and compare the generated speech against the approved script.

## Finish

Use `video-edit` for cuts and deterministic ffmpeg finishing. Review lip sync, word accuracy, likeness, logos, and unsupported claims. If a word is wrong, fix the audio or edit the affected shot; do not claim automatic correction without checking the final full-file transcription. Deliver the rendered MP4, exact script, source assets, and a concise record of the selected Stimulir TTS model and Dreamina model. Save durable project artifacts through the available host mechanism.
