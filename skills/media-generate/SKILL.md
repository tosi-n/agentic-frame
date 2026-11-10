---
name: media-generate
description: Generate speech, reference-voice speech, music, sound, or native video with ready Stimulir HybrIE deployments using scoped durable jobs.
---

# Stimulir media generation

Before using a route, read [media access and setup](references/access.md) and run the relevant local preflight. Its presence checks do not establish access; use the live catalog or ready deployment inventory to verify the selected model.

Use this skill when the task needs native Stimulir media models. `helpers/stimulir_media.py` is a standard-library client for the verified HybrIE durable job API. It requires an operator-provided HybrIE bearer key and exact business profile and pool IDs; it is not a customer Console gateway API. Never place that key in task artifacts or skill text. Discover deployments first and submit only to a ready deployment whose capabilities and limits fit the request. The table records verified resident examples, not the entire or permanent model inventory; use all currently accessible Stimulir models that fit the requested output and their documented routes.

| Output | Verified resident model | Job request |
|---|---|---|
| Reference voice speech | `openweight/mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit` on Metal | `kind:tts`, `input`, `reference_audio` data URL, `reference_text` or explicit `x_vector_only:true` |
| Music | `openweight/ACE-Step/acestep-v15-xl-turbo` | `kind:audio_generation`, `prompt`, `seconds`, optional `lyrics`/`seed` |
| Music or sound | `openweight/stabilityai/stable-audio-3-medium` | `kind:audio_generation`, `prompt`, `seconds`, optional `seed` |
| Native video | `openweight/Lightricks/LTX-2.5` | Follow the ready deployment's video capabilities and validated request limits |

The audio worker accepts ACE 10–60 seconds and Stable Audio 1–60 seconds. Validate the current deployment inventory because configured limits can be narrower. Qwen3-TTS Base requires an authorized reference recording even for its TTS path; it does not expose a named-voice list. Save the speech WAV and review the transcript and sound before use. Stable Audio editing/inpainting has extra parameters; read the worker contract before using them.

Use a stable UUID for each submitted job and retain it in the task artifact. Retrying the same UUID with the same body is idempotent. Poll the exact deployment, download the terminal artifact, then inspect it. A queued or running state is not a completed render. Keep generated WAV/MP4, prompt, model identity, deployment revision, and request ID in durable task artifacts. A missing ready deployment or scope is a blocked generation, not permission to switch to an unapproved vendor.

For Seedance 2.5 reference-driven video, `ugc-video` describes the supplemental Dreamina Canvas route; this native Stimulir video route has a verified LTX-2.5 worker.
