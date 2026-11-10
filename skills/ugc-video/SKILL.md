---
name: ugc-video
description: Turn an approved script and presenter assets into a vertical UGC video using available Stimulir speech, audio, image, and video models, with Dreamina Canvas as a supplement.
---

# UGC video

Before generation, read [media access and setup](../media-generate/references/access.md) and run its preflight for the gateway and any native, Dreamina, or Tesseract paths this job uses. Stimulir CLI OAuth login does not replace a gateway API key or scoped native bearer credential. Use the companion Dreamina skill's installer and device login flow when Dreamina is needed.

Adapted from [Graphed marketing-skills ugc-video](https://github.com/graphed-inc/marketing-skills/tree/main/skills/ugc-video), MIT license. Its Graphed, fal, and kie calls are not part of this port.

## Inputs

Require an approved script and a reference image or video for the presenter. Use only an authorized likeness and voice. Preserve the exact spoken wording in a text file. Estimate duration from the actual recorded speech before choosing a video duration. Split longer scripts into shot-sized segments and edit them together.

## Speech through Stimulir

For ordinary speech, use `POST /api/v1/inference/audio/speech` with the workspace gateway key and project scope, and choose an enabled model from the live catalog. For a reference voice, Stimulir's resident HybrIE audio worker supports `openweight/mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit` on Apple Silicon through a scoped `kind:tts` audio job. It requires `input`, an authorized `reference_audio` data URL, and `reference_text` (or an explicit `x_vector_only:true` mode). Discover a ready deployment and its fingerprint/revision before submitting; use the operator-scoped `media-generate` helper when available. This is not a public Console inference route. If that worker is not ready or the required scope is unavailable, use an already approved recording or report the blocked voice step. Save the resulting audio and listen to the entire file before using it as a video reference.

## Visuals, music, and video through Stimulir

Use the live Stimulir catalog and ready scoped deployments, rather than a fixed model list. The Console image gateway supports catalogued GPT Image and Gemini image models for text-to-image assets. For native video, use [media-generate](../media-generate/SKILL.md) to discover a ready video deployment and its validated modes; the verified resident option is LTX-2.5. Stimulir's native ACE-Step and Stable Audio deployments can provide music or sound when the edit calls for it. Choose only a model whose current capabilities fit the shot, and inspect the generated media. Do not assume a native video model supports audio-conditioned lip sync merely because it can generate audio and video.

## Dreamina Canvas supplement

If a shot needs image/audio reference conditioning or Canvas iteration that the ready Stimulir deployment cannot provide, use the separately installed `dreamina-canvas-cli` skill and authenticated CLI. Follow that skill for canvas creation, reference upload, live model discovery, schema, quote, generation, recovery, and delivery. Seedance 2.5 is a verified Dreamina option for reference-driven video; check its current limits and mode before use. Dreamina can also supplement image or audio work when its live catalog offers a needed capability. Keep Dreamina model IDs separate from Stimulir IDs. If the companion skill or CLI is unavailable, continue with compatible Stimulir paths or identify the missing capability.

## Finish

Use `video-edit` for cuts and deterministic ffmpeg finishing; use `tesseract-motion` for editable overlays. Review lip sync, word accuracy, likeness, logos, and unsupported claims. If a word is wrong, fix the audio or edit the affected shot; check the final full-file transcription. Deliver the rendered MP4, exact script, source assets, and a record of the Stimulir and any supplemental Dreamina models used. Save durable project artifacts through the available host mechanism.
