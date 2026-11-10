---
name: static-ads
description: Create on-brand static ad concepts and image files using the Stimulir image-generation gateway. Use for static ad concepts, brand style guides, and production-ready ad images.
---

# Static ads with Stimulir

Adapted from [Graphed marketing-skills static-ads](https://github.com/graphed-inc/marketing-skills/tree/main/skills/static-ads), MIT license. This port uses the Stimulir workspace project and its catalogued image model.

1. Get the brand URL and any approved brand assets. Inspect the site and supplied examples; distinguish observed brand rules from guesses. If the agent has an attached AdRadar connector, use it for public Meta Ad Library evidence. Otherwise use supplied ad examples or explicitly proceed without competitor evidence. Do not claim spend, impressions, or conversion performance from public ads.
2. Write a short style guide and five distinct ad concepts. Each concept needs a visual, headline, supporting line, and CTA. Show concepts if the user requested ideas only; generate files when they requested finished ads.
3. Put one JSON request per image in a directory, each with `prompt` and optional `model`, `size`, `quality`. Keep exact ad copy in the prompt. The gateway supports text-to-image; it does not accept image references on this route, so describe approved reference assets rather than pretending to attach them.
4. Run `python3 <skill-dir>/scripts/generate.py <request-dir> <output-dir> --dry-run`, review requests, then run without `--dry-run`. Set `STIMULIR_API_KEY`; optional `STIMULIR_API_BASE`, `STIMULIR_PROJECT_ID`, and `STIMULIR_IMAGE_MODEL` select the workspace and catalogued model. The default model is `gpt-image-2`; a 404 means the workspace has not enabled that model.
5. Inspect each image at final size. Check spelling, invented URLs, logos, claims, and legibility. Correct failures before delivery. Keep the source request JSON beside the output so each image is reproducible. Upload to durable task artifacts using the host's artifact mechanism when available.

The Stimulir image route is `POST /api/v1/inference/images/generations`; it returns base64 raster data and records an `image_generation` trace according to project capture policy. No Graphed login, credits, project database, or storage key is used.
