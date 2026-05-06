# Lessons — agentic-frame

Patterns and corrections worth remembering across sessions.

## 1. Always verify load-bearing assumptions in source, not docs

When porting `video-use` to HybrIE, the README's STT description and the agent
report both implied word-level timestamps were available. Reading
`hybrie-server/src/audio/mod.rs:196` showed the native backend explicitly
rejects them. The whole skill design pivoted on that one runtime check.

**Rule for next time:** when adapting a system to a new backend, the first
30 minutes go to reading the backend's actual handler code for the
load-bearing capability. Schema fields existing in a struct (e.g.,
`words: Vec<SttWord>`) ≠ the feature being implemented.

## 2. Aliases route silently — check the enum

`x-hybrie-cloud-provider: hybrie` and `nebius` and `cloud` all resolve to the
same backend (`inference_api.rs:263`). The user said "Nebius" but the wire
value to send is `"hybrie"`. Without grepping the alias map I would have
shipped the wrong header value.

**Rule:** when a system accepts named values, search for the normalisation
function once and pin which form the wire actually wants.

## 3. Helpers stay dumb. Hard rules go in code, not prose

`render.py` enforces 13 invariants in ffmpeg argument construction (subs LAST,
overlay `setpts` math, output-timeline SRT offsets, etc.). The agent reading
SKILL.md sees the rules listed but cannot bypass them — they're baked into the
filter graph.

**Rule:** if a rule's violation produces silently wrong output (vs. an obvious
crash), put it in the code path that runs every time, not in the prose the
LLM might skim.

## 4. Plan before code, even when the path looks obvious

Started this session ready to scaffold immediately after reading video-use.
The 30-minute discovery (HybrIE source dive, naars-poc survey, plan write-up)
caught the word-timestamp mismatch before any helper was written. If I had
copied `pack_transcripts.py` from video-use first and then discovered the
mismatch, I would have rewritten the same file twice.

**Rule:** the plan-mode step from CLAUDE.md isn't ceremony. For any port /
adaptation, read the new substrate's actual contract before writing
substrate-shaped code.

## 5. Loudnorm silently upsamples — pin -ar in pass 2

`apply_loudnorm_two_pass` in `render.py` re-encoded audio without an explicit
`-ar`. The loudnorm filter internally operates at ~192 kHz for precision; the
output stream inherited that, so 48 kHz source became 96 kHz output. ffprobe
caught it; nothing crashed. The first real-render verification (Phase 1)
exposed it because no smoke test ever inspected the output sample rate.

**Rule:** when a filter is known to alter audio internals (loudnorm, aresample,
asetrate), explicitly pin the post-filter `-ar` to the intended output rate.
"It worked, mp4 plays" is not the same as "the output stream is correct."

**Rule (process):** verify foundations early. The 13 hard rules in `render.py`
were claims-in-code until Phase 1 produced the first real mp4. Three days of
v0.1.28 sidecar work would have been built on top of a silent audio-rate bug.
