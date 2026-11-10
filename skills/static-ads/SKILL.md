---
name: static-ads
description: Create on-brand static ads with catalogued Stimulir image models, using Dreamina Canvas as a supplement for reference editing and iteration.
---

# Static ads with Stimulir

Read [media access and setup](../media-generate/references/access.md). Use Stimulir image models by default and run the gateway preflight before generating with its helper. If the user explicitly requests Codex image generation in a Codex host, use its available image generation skill/tool instead, following its instructions and saving the resulting images with the ad artifacts. If using Dreamina Canvas, run its optional check and follow the separately installed companion skill for installation and login. Stimulir CLI OAuth login does not supply the generator's gateway API key.

Adapted from [Graphed marketing-skills static-ads](https://github.com/graphed-inc/marketing-skills/tree/main/skills/static-ads), MIT license. This port uses the Stimulir workspace project and its catalogued image model.

1. Get the brand URL and any approved brand assets. Inspect the site and supplied examples; distinguish observed brand rules from guesses. If the agent has an attached AdRadar connector, use it for public Meta Ad Library evidence. Otherwise use supplied ad examples or explicitly proceed without competitor evidence. Do not claim spend, impressions, or conversion performance from public ads.
2. Write a short style guide and five distinct ad concepts. Each concept needs a visual, headline, supporting line, and CTA. Show concepts if the user requested ideas only; generate files when they requested finished ads.
3. For the default Stimulir route, discover the live image catalog and select an enabled model for each concept. Put one JSON request per image in a directory, each with `prompt` and `model` (or set `STIMULIR_IMAGE_MODEL`). GPT Image models support `size` and `quality`; Gemini image models support `aspect_ratio` and `image_size`. Keep exact ad copy in the prompt. The gateway supports text-to-image, without image references on this route. For a user-requested Codex image route, follow the host tool's input and output contract instead of these JSON requests.
4. For the Stimulir route, run `python3 <skill-dir>/scripts/generate.py <request-dir> <output-dir> --dry-run`, review requests, then run without `--dry-run`. Set `STIMULIR_API_KEY`; optional `STIMULIR_API_BASE` and `STIMULIR_PROJECT_ID` select the workspace. A 404 indicates the selected model is unavailable to the workspace.
5. For approved reference images, image editing, or Canvas-led iteration, follow the separately installed `dreamina-canvas-cli` skill. Check authentication and the live Dreamina image catalog/schema; create or reuse a Canvas and keep the model identity and exported result with the ad artifacts. Dreamina supplements Stimulir generation and has its own model IDs and access. If unavailable, use a compatible Stimulir text-to-image workflow or report the missing editing capability.
6. Inspect each image at final size. Check spelling, invented URLs, logos, claims, and legibility. Correct failures before delivery. Keep the source request JSON or Canvas record beside the output so each image is reproducible. Upload to durable task artifacts using the host's artifact mechanism when available.

The Stimulir image route is `POST /api/v1/inference/images/generations`; it returns base64 raster data and records an `image_generation` trace according to project capture policy. No Graphed login, credits, project database, or storage key is used.
