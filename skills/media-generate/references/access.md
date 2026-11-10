# Media access and setup

Run `python3 <agentic-frame>/skills/media-generate/scripts/preflight.py --gateway` before Console image or ordinary speech calls, `--native` before scoped audio/video jobs, `--dreamina` before optional Canvas work, and `--tesseract` before editing motion. Combine only checks needed by the task. This local check reports missing settings; it does not prove workspace authorization, model entitlement, or a ready deployment.

| Path | Credential and check | Setup |
|---|---|---|
| Stimulir Console image and speech | `STIMULIR_API_KEY`; optional `STIMULIR_API_BASE`, `STIMULIR_PROJECT_ID`. Check the enabled workspace model catalog. | Obtain a project-authorized gateway key through the Console's approved credential flow and set it in the process environment. Do not paste it into chat or save it with ad assets. The `stimulir` CLI OAuth login is a separate connection and does not automatically populate this API key. |
| Stimulir native audio and video | Operator-supplied `HYBRIE_BASE_URL`, `HYBRIE_BEARER_KEY`, `HYBRIE_BUSINESS_PROFILE_ID`, `HYBRIE_POOL_ID`; optional `HYBRIE_PROJECT_ID`. Discover a ready deployment using `MediaClient.deployments()`. | These are scoped operator credentials, not a public Console API key or user OAuth token. Obtain them through the approved operator channel. Never print or persist the bearer key. |
| Optional Dreamina Canvas | Installed `dreamina-canvas-cli` skill and `dreamina-canvas` binary; run `auth status` then `auth account` for the intended profile. | Follow the companion skill's current installer and device login instructions. If `auth login` returns an authorization challenge, open its official URL and run `auth wait` using the challenge device code. Do not treat opening the URL as completed login. |
| Tesseract motion | Pinned `tsrct` CLI version. | Follow [the Tesseract installer](../../tesseract-motion/references/installation.md), including checksum and exact version verification. No OAuth or API key is required for local Tesseract editing. |

The Agent's host may grant these tools and credentials through its own secret manager. Check the actual execution environment instead of assuming a local shell setting is inherited. A missing authorization or deployment is a setup blocker; never substitute an unrelated credential.
