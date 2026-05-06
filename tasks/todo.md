# video-edit skill — implementation plan

A video-editing skill for Codex / Claude Code / future Stimulir code-runtime, powered by HybrIE v0.1.27.

Modeled on browser-use's `video-use` (the LLM is the editor, ffmpeg is the renderer, helpers are dumb), but rewired to call HybrIE's local OpenAI-compatible endpoints instead of ElevenLabs Scribe.

---

## Discovery summary (the pinned facts)

**HybrIE v0.1.27 endpoint surface (pinned by reading source, not docs):**

| Capability | Endpoint | Mode | Notes |
|---|---|---|---|
| STT (Whisper) | `POST /v1/audio/transcriptions` | local-only | multipart; `verbose_json` returns `segments[]` with `start_seconds`/`end_seconds` |
| LLM chat | `POST /v1/chat/completions` | local/cloud/hybrid | OpenAI-compatible, `response_format: json_object` supported |
| VLM (vision) | `POST /v1/chat/completions` (image content blocks) | **cloud-only in v0.1.27** | optional in skill |
| TTS | `POST /v1/audio/speech` | **cloud-only** | optional, for VO generation |
| Models list | `GET /v1/models` | any | for health/discovery |
| Health | `GET /v1/health` | any | startup precheck |

- Auth: `Authorization: Bearer <HYBRIE_API_KEY>` (default `"hybrie"` per naars-poc).
- Default base URL pattern: `http://127.0.0.1:8001` (naars-poc) — we'll honor `HYBRIE_API_URL` env var with a sensible fallback.
- Execution mode headers: `x-hybrie-execution-mode: local|cloud|hybrid|auto|dispatch`, `x-hybrie-cloud-provider: openai|anthropic|gemini|runware|hybrie`.

**The load-bearing constraint** (`hybrie-server/src/audio/mod.rs:196`):

> Native Whisper backend rejects `timestamp_granularities=word` with `UnsupportedFeature("word timestamps are not implemented for the native Whisper backend")`.

video-use is built on word-level cuts. We cannot copy that. We pivot to **segment-level cuts**, which Whisper anchors at natural pause/punctuation boundaries — meaning Hard Rule "never cut inside a word" is enforced *by construction* rather than by edge-padding.

**naars-poc patterns to copy:**
- `buildHeaders()` shape (Bearer + Content-Type) — port to Python.
- Env-var-with-default config (`HYBRIE_API_URL`, `HYBRIE_API_KEY`).
- Graceful fallback on chat failures.

**naars-poc patterns to drop:**
- Local `faster-whisper` Python subprocess. We use HybrIE's native STT instead.

---

## Proposed skill layout

```
agentic-frame/
├── skills/
│   └── video-edit/
│       ├── SKILL.md               (the agent's playbook — ~300-400 lines)
│       ├── install.md             (HybrIE bootstrap + skill install)
│       ├── README.md              (positioning + quick-start)
│       ├── pyproject.toml         (httpx, librosa, pillow, numpy, matplotlib)
│       └── helpers/
│           ├── hybrie_client.py        [NEW] thin HTTP client (chat, stt, vlm, tts, health)
│           ├── transcribe.py           ports video-use, calls hybrie_client.transcribe()
│           ├── transcribe_batch.py     ports video-use (parallel, cached)
│           ├── pack_transcripts.py     [REWORKED] segment-level → packed markdown
│           ├── timeline_view.py        ports video-use (filmstrip + waveform + segment shading)
│           ├── grade.py                ports video-use unchanged (deterministic ffmpeg)
│           └── render.py               ports video-use (12 hard rules preserved/adapted)
├── .codex-plugin/plugin.json      manifest pointing at skills/
├── .claude-plugin/plugin.json     manifest pointing at skills/
└── tasks/
    └── todo.md                    (this file)
```

The Hyperframes-style multi-manifest pattern (`.codex-plugin`, `.claude-plugin`) ships the same skill dir to multiple hosts.

---

## Hard rules — adapted from video-use for HybrIE

12 invariants `render.py` enforces in code (not in prose):

1. **Subtitles applied LAST** in filter chain (overlays don't cover them).
2. **Per-segment extract → lossless `-c copy` concat** (never double re-encode).
3. **30 ms audio fades at every cut boundary** (no audible pops).
4. **Overlays use `setpts=PTS-STARTPTS+T/TB`** (don't see the middle of an animation).
5. **Master SRT uses output-timeline offsets** (captions don't drift after concat).
6. **Cuts only at HybrIE segment boundaries** (no mid-segment cuts).  *[was: "never cut inside a word" — now stronger by construction]*
7. **Pad cut edges 100–300 ms** (segment timestamps drift; pad heavier than word-level since granularity is coarser).  *[was: 30–200ms]*
8. **HybrIE STT with `response_format=verbose_json`, `timestamp_granularities=[segment]`** only.  *[was: "word-level verbatim ASR only"]*
9. **Cache transcripts per source** — `<edit>/transcripts/<stem>.json`.
10. **Parallel sub-agents for multiple animations** (the renderer doesn't care).
11. **Strategy confirmation before execution** (the model proposes EDL, user gates).
12. **All session outputs in `<videos_dir>/edit/`**.

Plus one new HybrIE-specific rule:

13. **Health check before any work** — `hybrie_client.health()` must return ok before transcription starts. Fail loudly with install hint if HybrIE isn't running.

---

## hybrie_client.py — the thin client (new)

Single ~150-line module exposing:

```python
class HybrieClient:
    def __init__(self, base_url=None, api_key=None, timeout=300):
        # base_url: env HYBRIE_API_URL || http://127.0.0.1:8001
        # api_key:  env HYBRIE_API_KEY || "hybrie"

    def health(self) -> dict
    def list_models(self) -> list[dict]

    def transcribe(self, audio_path: Path, *, model="openai/whisper-large-v3-turbo",
                   language=None, response_format="verbose_json") -> dict
        # multipart POST /v1/audio/transcriptions
        # returns {task, language, duration_seconds, text, segments[], words=[]}

    def chat(self, messages: list, *, model: str, response_format=None,
             temperature=0.2, execution_mode="local", cloud_provider=None) -> dict
        # POST /v1/chat/completions, OpenAI-compatible

    def vision(self, prompt: str, image_paths: list[Path], *, model: str) -> str
        # cloud-only; convenience wrapper that base64-encodes images and calls chat()
        # raises if execution_mode=local — or auto-routes to cloud with a warning

    def speak(self, text: str, *, voice: str, model="tts-1",
              response_format="mp3") -> bytes
        # cloud-only; POST /v1/audio/speech
```

Design decisions:
- **No SDK dependency** — naars-poc proves you can use raw HTTP. Avoids dragging in `hybrie-py` (which is gRPC-only, image-gen-only).
- **Sync `httpx.Client`** (not `requests`) — better timeouts, h2 if needed, type-safe.
- **VLM/TTS gated** — they only work in cloud mode in v0.1.27. Client raises a clear error in local mode rather than silently failing.

---

## What changes structurally vs. video-use

1. **`pack_transcripts.py` rewritten.** Drops word-walking + silence-detection + speaker-change phrase grouping. Whisper segments are already phrases. Output format keeps the same packed-markdown shape (~12 KB for an hour) so the LLM reads it identically. Segments cluster into "scenes" by gap > 2 s.

2. **`build_master_srt()` in `render.py`** walks segments, not words. Same output-timeline offset math. Same 2-segment chunking → uppercase → bold-overlay style.

3. **`timeline_view.py`** loses word-label overlays (no word timestamps). Gains segment-boundary shading + segment-text labels above the waveform. PIL composites are still the primary "look" tool.

4. **No ElevenLabs API key in install.md** — replace with HybrIE bootstrap (clone, `cargo run`, port check). For optional TTS, document HybrIE's cloud-mode routing instead.

5. **VLM optional self-eval.** When HybrIE is configured for cloud mode, `timeline_view` PNGs can be sent to a VLM via `hybrie_client.vision()` for verification. Falls back to "agent looks at PNG itself" when local-only.

---

## Plugin manifests

`.codex-plugin/plugin.json`:
```json
{
  "name": "video-edit",
  "skills": "./skills/",
  "interface": {
    "displayName": "Video Edit (HybrIE)",
    "category": "Media",
    "capabilities": ["Read", "Write"],
    "defaultPrompt": [
      "Cut these takes into a 60-second product demo",
      "Build a launch video from this folder of footage",
      "Add captions to this voiceover and color-grade it"
    ]
  }
}
```

`.claude-plugin/plugin.json` — sibling manifest pointing at the same `./skills/`. Claude Code auto-discovers `skills/<name>/SKILL.md`, but a manifest lets us pin metadata and version.

Stimulir code-runtime: not built yet — leave a `# stimulir-runtime: see plugin.json shape` placeholder comment in SKILL.md so the contract is obvious when that runtime arrives.

---

## Implementation checklist

- [x] **Step 1.** Create `skills/video-edit/` skeleton (dirs only).
- [x] **Step 2.** Write `helpers/hybrie_client.py` (~210 lines, httpx-based).
- [x] **Step 3.** Write `helpers/transcribe.py` + `helpers/transcribe_batch.py`.
- [x] **Step 4.** Write `helpers/pack_transcripts.py` for segment-level packing.
- [x] **Step 5.** Write `helpers/timeline_view.py` (filmstrip + waveform + segment overlays).
- [x] **Step 6.** Write `helpers/grade.py` (presets + auto + raw passthrough).
- [x] **Step 7.** Write `helpers/render.py` enforcing all 13 hard rules.
- [x] **Step 8.** Write `SKILL.md` with the playbook, hard rules, EDL contract, anti-patterns.
- [x] **Step 9.** Write `install.md` — HybrIE prereq check, server bootstrap, skill symlink.
- [x] **Step 10.** Write `README.md` and `pyproject.toml`.
- [x] **Step 11.** Write `.codex-plugin/plugin.json` and `.claude-plugin/plugin.json`.
- [x] **Step 12.** Smoke test (HybrIE not running locally — graceful failure verified; helper CLIs, JSON manifests, segment-level pack all pass).
- [x] **Step 13.** Add review section + capture lessons.

---

## Review

**Final layout:**

```
agentic-frame/
├── .codex-plugin/plugin.json        (host manifest)
├── .claude-plugin/plugin.json       (host manifest, sibling)
├── skills/video-edit/
│   ├── SKILL.md                     7 principles + 13 hard rules + EDL contract
│   ├── install.md                   HybrIE bootstrap + symlink runbook
│   ├── README.md                    pitch + delta vs. video-use
│   ├── pyproject.toml               httpx, pillow, numpy, librosa
│   └── helpers/
│       ├── hybrie_client.py         ~210 lines — health/list/STT/chat/vision
│       ├── transcribe.py            single-file ffmpeg→/v1/audio/transcriptions, cached
│       ├── transcribe_batch.py      ThreadPoolExecutor, 4 workers default
│       ├── pack_transcripts.py      segment-level → packed markdown
│       ├── timeline_view.py         filmstrip + waveform + segment labels (PIL)
│       ├── grade.py                 4 presets + auto signalstats + raw passthrough
│       └── render.py                13 hard rules in code, ~360 lines
└── tasks/
    ├── todo.md                      this file
    └── lessons.md                   captured below
```

**Verifications run:**
- AST parse: 7/7 helper files clean.
- JSON validate: both plugin manifests parse.
- `--help` on every CLI helper: 5/5 print expected usage.
- HybrIE-down failure path: `HybrieClient().health()` raises `HybrieError` with
  the install hint baked into the message — confirmed verbatim.
- `grade.resolve_grade_filter`: preset / "none" / `None` / raw filter / unknown
  all return / raise as designed.
- `pack_transcripts.py` against a synthetic 3-segment transcript with a 3.8 s
  gap: produced the expected 2-scene block with correct timestamps.

**Not verified end-to-end (out of scope for this session):**
- Running HybrIE STT against real footage (requires `cargo run` of hybrie-server
  and Whisper weights download). install.md walks the user through this.
- VLM cloud fallback (requires a Nebius API key on the HybrIE server).

**Decisions baked into the design:**
- Segment-level cuts only. Word timestamps were the load-bearing assumption in
  video-use; HybrIE rejects them in v0.1.27. Pivoting to segments turned out
  cleaner — Hard Rule "never cut inside a word" becomes a structural property
  rather than a runtime check.
- No HybrIE Python SDK dependency. The `hybrie-py` package is gRPC-only and
  scoped to image generation. Raw HTTP via httpx is simpler and matches
  naars-poc's proven shape.
- VLM is a fallback, not the primary path. Host-agent native vision wins when
  available; `vision()` only fires for text-only runtimes.

**Open / future work** (not blocking v1):
- v2: TTS narration helper (`narrate.py`) using `/v1/audio/speech`.
- v2: VLM-driven self-eval option flag — currently the agent reads PNGs itself.
- Stimulir code-runtime manifest once that runtime is defined.
- A `static/` banner + `poster.html` explainer if we want the same visual
  artifact video-use ships with. Cosmetic; defer.

---

## Decisions (confirmed by user)

1. **Skill name**: `video-edit`.
2. **STT**: HybrIE local Whisper only (`POST /v1/audio/transcriptions`, `verbose_json`, segment granularity).
3. **VLM strategy**: agent's own vision is the primary path — `timeline_view.py` writes PNGs to disk, the agent reads them natively. **Fallback** to HybrIE cloud VLM via `hybrie_client.vision()` with `x-hybrie-execution-mode: cloud, x-hybrie-cloud-provider: hybrie` (resolved as Nebius by default — confirmed in `hybrie-server/src/inference_api.rs:61` where `DEFAULT_CLOUD_BASE_URL = "https://api.studio.nebius.ai/v1"` and the `"hybrie"`/`"nebius"`/`"cloud"` aliases all route there).
4. **TTS**: deferred to v2.
5. **Stimulir code-runtime**: leave a TODO comment; no manifest target yet.

---

# Phase 2 — v0.1.28 + parity completion

**Goal:** finish agentic-frame to functional parity with `video-use`, ship HybrIE v0.1.28 with the sidecar that unblocks word-level cuts, land everything on `main`.

**Realistic scope:** 3-5 focused sessions. We checkpoint at the end of each phase and you sign off before the next one.

**Two open decisions blocking Phase 5** (asked at end of plan):
- D1. Animation runtime: Manim verbatim, Remotion (you have the best-practices skill loaded), or HTML+headless (Hyperframes-style)?
- D2. Confirm scope: A + B-safe (prompt + segment confidence). Drop B's VAD pre-filter (changes Whisper input in subtle ways) unless you want it.

Default if you don't answer: D1 = Manim verbatim (fastest, ~2 days, cleanest provenance), D2 = drop VAD.

---

## Phase 1 — Verify the v1 foundation (~30 min, blocked on HybrIE running locally)

**Why first:** the 13 hard rules in `render.py` are claims-in-code, not evidence. If `render.py` has an ffmpeg bug, every later phase builds on sand. Fix it now, cheaply.

- [ ] **1.1** Confirm HybrIE up: `curl http://127.0.0.1:8001/v1/health` returns ok.
  - If down: user starts it per `skills/video-edit/install.md` — `cargo run --release -p hybrie-server` from `../hybrie/`.
- [ ] **1.2** Drop a 30-60 s test clip in a fresh dir (`/tmp/ve-test/clip.mp4`).
- [ ] **1.3** `python skills/video-edit/helpers/transcribe.py /tmp/ve-test/clip.mp4` — verify `<dir>/edit/transcripts/clip.json` has segments with non-zero durations.
- [ ] **1.4** Hand-write a single-range EDL covering ~5 s (`/tmp/ve-test/edit/edl.json`).
- [ ] **1.5** `python skills/video-edit/helpers/render.py /tmp/ve-test/edit/edl.json --out-dir /tmp/ve-test/edit` — should produce `final.mp4`.
- [ ] **1.6** Play `final.mp4`, confirm: clean cuts, no audio pops, subtitles last (if added), no double-encode artifacts.
- [ ] **1.7** Fix any ffmpeg-side bugs found. (Unknown unknowns.)

**Exit criterion:** one mp4 produced, plays clean. THEN we proceed.

---

## Phase 2 — Lock in agentic-frame v1 on `main` (~10 min)

- [ ] **2.1** Rename `master` → `main`: `git branch -m master main`.
- [ ] **2.2** Initial commit: skill + plugin manifests + tasks dir. Use a clear scope-setting message ("Initial: video-edit skill v1 (HybrIE-powered)").
- [ ] **2.3** Push: `git push -u origin main`. (You authorize, I run.)

**Exit criterion:** `agentic-frame` exists on GitHub `main` with v1 reproducible.

---

## Phase 3 — HybrIE v0.1.28 (~2-3 days, isolated branch)

**Branch:** `feature/v0.1.28-word-alignment` off `main` in `../hybrie/`.

**A — Sidecar word-alignment endpoint** (the parity unlock):
- [ ] **3A.1** Add `POST /v1/audio/transcriptions/align` route in `hybrie-server`. Multipart: audio + JSON transcript (segments).
- [ ] **3A.2** Python sidecar: `whisper-timestamped` (more battle-tested than `stable-ts` for this) running as a managed subprocess. `aligner/` directory in repo root, with `pyproject.toml` and a `main.py`.
- [ ] **3A.3** Wire subprocess management — venv path, lazy boot, stdout/stderr capture, timeout.
- [ ] **3A.4** Response shape matches existing transcription response with `words[]` populated on each segment.
- [ ] **3A.5** Update `docs/STT_V1.md` — flip the "no word timestamps" note to "available via /align endpoint, requires Python sidecar".
- [ ] **3A.6** Update root `README.md` install section: Python 3.10+ now required for full STT capabilities.

**B-safe — quality wins** (cheap, low risk):
- [ ] **3B.1** `prompt` (initial_prompt) support — currently rejected at `audio/mod.rs:254`. Thread through to Candle decoder. ~50 lines.
- [ ] **3B.2** Surface segment confidence in `SttSegment` — already computed by chunks (`avg_logprob`, `no_speech_prob`), just thread to the JSON response. ~30 lines.
- [ ] **3B.3** *DROP* VAD pre-filter (changes input in subtle ways, separate release).

**Release prep:**
- [ ] **3.7** Bump `VERSION`: `0.1.27` → `0.1.28`.
- [ ] **3.8** Bump workspace `Cargo.toml` versions, sync `Cargo.lock`.
- [ ] **3.9** Smoke tests: `cargo test`, `cargo build --release`, manual curl against /align.
- [ ] **3.10** Write release notes (`docs/RELEASE_NOTES.md` or commit message).

**HARD GATE: Do NOT push, do NOT tag, until user reviews the diff.** I'll produce a `git diff main..feature/v0.1.28-word-alignment` for review before any remote operation.

---

## Phase 4 — agentic-frame upgrade to use align endpoint (~half day)

- [ ] **4.1** Add `align()` method to `hybrie_client.py` calling `POST /v1/audio/transcriptions/align`.
- [ ] **4.2** New optional flag in `transcribe.py`: `--word-align` triggers a second pass against /align after the segment pass.
- [ ] **4.3** Extend `pack_transcripts.py` with a word-level mode (preserve segment-level as default; word-level is opt-in).
- [ ] **4.4** Update `render.py` Hard Rule 7: cut padding drops back to 30-200 ms when word timestamps are available; remains 100-300 ms in segment-only mode.
- [ ] **4.5** Update Hard Rule 6 in SKILL.md prose: "Cuts at word OR segment boundaries depending on transcript granularity."
- [ ] **4.6** Smoke tests pass: synthetic word-level transcript packs correctly.
- [ ] **4.7** Optional: re-render the Phase 1 test clip in word-aligned mode and compare cut quality.

---

## Phase 5 — Animation sub-skill (~2 days, blocked on D1)

**If D1 = Manim verbatim** (recommended default):
- [ ] **5.1** Vendor `video-use/skills/manim-video/` into `agentic-frame/skills/animate-manim/` with attribution.
- [ ] **5.2** Adjust references to point at HybrIE for any LLM-side prompts.
- [ ] **5.3** Update `video-edit/SKILL.md` — animation overlay sub-agents reference the new `animate-manim` skill.

**If D1 = Remotion** (you have `remotion-best-practices`):
- [ ] Larger scope. ~3-4 days. Different runtime, different determinism story (browser-headless render). Not vendored, written native.

**If D1 = HTML+headless** (Hyperframes-style):
- [ ] Largest scope. ~5+ days. Most modern but new infrastructure (headless Chrome rendering, frame-adapter pattern).

---

## Phase 6 — Final commits + PR (~30 min)

- [ ] **6.1** agentic-frame: commit Phases 4 + 5 work on `main`. Push.
- [ ] **6.2** hybrie: confirm diff with user. If green, push `feature/v0.1.28-word-alignment`, open PR to `main`. User merges. Tag `v0.1.28`.
- [ ] **6.3** Update `tasks/lessons.md` with anything new.
- [ ] **6.4** Mark this plan complete with a Phase 2 review section.

---

## Risks I'm flagging up front

- **Phase 1 may surface ffmpeg bugs in render.py** that need real fixing. Estimate could blow up.
- **Phase 3A adds a Python dep to HybrIE's install story.** Not "native runtime stays cheap" anymore — `cargo run` is no longer the only requirement. User-visible change. We need this in install docs.
- **`whisper-timestamped` vs `stable-ts`** — picking one. `whisper-timestamped` has DTW + better silence handling; `stable-ts` is simpler. I'll go with `whisper-timestamped` unless you object.
- **Remote pushes** are gated on your review at every step. No `git push --force`, no `git tag` without sign-off.
