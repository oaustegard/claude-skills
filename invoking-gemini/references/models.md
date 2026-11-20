# Gemini Models Reference

Detailed information about available Gemini models (verified against Google's model, pricing and deprecation pages on 2026-11-20).

## Model Comparison

### Gemini 4 — current generation (default: Hydrogen)

All four share a 1M unified context window (input + output), 64K default
output (up to 1M with long decode), text/image/audio/video/PDF input, text
output, and the same request schema. Google's routing guide
(`/docs/choosing-a-model`, fetched 2026-11-20): Hydrogen by default, Neon for
complex high-frequency work, Carbon for the hardest problems, 3.5 Flash-Lite
for high-volume text. Implicit caching only; explicit caching is not supported.

| Model | Alias | Released | Input/1M | Output/1M | Thinking levels (default) | Free tier |
|---|---|---|---|---|---|---|
| gemini-4-hydrogen | `flash`, `pro`, `hydrogen` | 2026-11-12 | $1.50 | $7.50 | low, medium, high (default), xhigh | yes |
| gemini-4-neon | `neon` | 2026-11-18 | $3.00 | $15.00 | low, medium, high (default), xhigh | no |
| gemini-4-carbon | `carbon` | 2026-11-10 | $2.00 → $4.00 | $10.00 → $20.00 | low, medium (default), high | no |
| gemini-4-argon | `argon` | 2026-10-13 | $2.00 → $4.00 | $10.00 → $20.00 | low, medium, high | no |

`$2.00 → $4.00` is introductory pricing through 2026-11-30; the higher price
starts 2026-12-01. Output prices include thinking tokens. Verified live through
the CF gateway on 2026-11-20: all four reject `minimal` with HTTP 400; Carbon
and Argon also reject `xhigh`. The client downgrades both and says so on stderr.

- **Hydrogen** — everyday coding, interactive apps, tool-using agents,
  multimodal documents. Google reports >5x fewer fabricated claims than 3.8
  Flash and parallel batching of read/search tool calls. Same sticker price as
  3.8 Flash from 2027-01-01; 2x during 3.8's intro pricing.
- **Neon** — between Hydrogen and Carbon: deeper reasoning than Hydrogen, faster
  and fewer output tokens than Carbon. Multi-file coding, dense knowledge work.
- **Carbon** — strongest reasoning; spends the most thinking tokens to verify
  edge cases. Architecture, multi-file debugging, proofs, security audits.
- **Argon** — the efficient Gemini 4 reasoning model: faster, lower token spend
  per turn than Carbon, same price. Listed on the models page but absent from
  Google's choosing guide.

The Pro-tier stance (Oskar, 2026-09-03: Pareto efficiency) carries over:
`pro` resolves to Hydrogen, and "maximum reasoning" means Hydrogen with
`thinking_level='xhigh'`. Neon and Carbon are opt-in by name.

### Gemini 3.x — kept models

| Model | Alias | Input/1M | Output/1M | Notes |
|---|---|---|---|---|
| gemini-3.8-flash | `flash-3.8` | $0.75 → $1.50 | $3.75 → $7.50 | Previous-generation Flash (GA 2026-09-02); the one pinned fallback. Intro price through 2026-12-31. No `minimal`. Google's replacement target for 3.7 and 2.5 Pro. |
| gemini-3.5-flash-lite | `lite` | $0.30 | $2.50 | **Bulk tier.** GA 2026-07-21. Lowest-cost general model, 350 output tok/s, accepts `minimal` (the only text model here that does). Google's replacement for 2.5 Flash and 3.1 Flash-Lite. Free tier. |

### Speech Generation Models (TTS)

**Released 2026-09-23, GA** on the Gemini API and AI Studio (Gemini Enterprise
in preview). Google's announcement claims #1 on Hume AI's Voice Design
Benchmark (71.4) and the #1 and #2 spots on its Overall Quality Index.

#### gemini-3.8-flash-tts

- Flagship expressive TTS: acting, regional accents, long-form multi-turn
  stability. 130 languages, auto-detected.
- Limits: 8,192 input tokens / 16,384 output tokens per request; up to two
  speakers.
- Pricing: $0.50 in (text) / $9.00 out (audio) per 1M through 2026-12-31, then
  $1.00 / $18.00. Batch half. About 32 audio tokens per second of speech
  (measured 2026-09-24), so ~$0.02 per minute.

#### gemini-3.8-flash-lite-tts

- Cheaper workhorse for bulk narration, voice-agent cascades and read-aloud;
  101 languages. $0.50 / $6.00 per 1M through 2026-12-31, then $1.00 / $12.00.
- Google's named replacement for `gemini-3.1-flash-tts-preview` ($1 / $20).

#### API shape (verified through the CF gateway, 2026-09-24)

- Use the **Interactions API**: `POST v1beta/interactions` with
  `{"model", "input": [{"type": "user_input", "content": [{"type": "text",
  "text", "annotations": [{"type": "speech_metadata", "style"}]}]}],
  "response_format": {"type": "audio", "mime_type": "audio/wav",
  "sample_rate": 24000}, "generation_config": {"speech_config": [{"voice"}]}}`.
  Audio is base64 at `steps[].content[]` where `type == "audio"`.
- `generateContent` with `responseModalities: ["AUDIO"]` also returns audio,
  but a "Style: text" prefix is spoken aloud and `systemInstruction` returns
  HTTP 400 "Developer instruction is not enabled for this model".
- Voices: 30 studio voices plus 2,059 persona voices (`GET v1beta/voices`,
  paged by `next_page_token`, max 1,000 per page). Designed voices come from
  `POST v1beta/voices` with `{"store": true, "voice": {"type": "prompted",
  "prompted": {"input": "<description>"}, ...}}` and return a `voice_...` id
  (1-year expiry, 200 per project) plus a `sample_audio` preview.
- Output is watermarked with SynthID.
- The model can paraphrase: it added "Hmm," and swapped pronouns in a scripted
  narration. Check scripted output with ASR.

### Image Generation Models

**Updated 2026-05-28:** Nano Banana 2 and Nano Banana Pro reached general
availability — announced GA on Vertex AI / Gemini Enterprise Agent Platform,
where the GA model IDs drop the suffix (`gemini-3.1-flash-image`,
`gemini-3-pro-image`).

⚠️ **Corrected 2026-07-21 (the previous note here was wrong).** The GA IDs
`gemini-3.1-flash-image` and `gemini-3-pro-image` are **NOT** Vertex-only and do
**NOT** 404 on the Developer API — they were released on this surface on
2026-05-28 and were live-tested working through the CF gateway on 2026-07-21.
The `-preview` IDs also still resolve (their announced 2026-06-25 shutdown
appears to redirect rather than fail), so nothing is broken either way — but
**new code should target the GA IDs**.

Also available and not yet wired into this client: `gemini-3.1-flash-lite-image`
(Nano Banana 2 Lite, GA) — the cheapest image tier, ~$0.034/image.

#### nano-banana-2.1

**API Model ID:** `gemini-nano-banana-2.1` (alias: `image`, default)

Update to Nano Banana 2, released with the Gemini 4 line. Flash-level speed and
cost with better visual quality, text rendering and infographic layout,
multi-turn character consistency (up to 4 characters / 10 objects across 14
reference images), no tiling artifacts on wide aspect ratios, grounding with
Web and Image Search, and configurable thinking (`minimal`, `medium` default,
`high`). 1K/2K/4K output. Input limit 131K, output limit 32K.

**Pricing:** $1.50 / 1M input, $7.50 / 1M text output, $30 / 1M image output.
About $0.034 per 1K image, $0.050 per 2K, $0.113 per 4K. Verified live through
the CF gateway on 2026-11-20 (`generate_image(model="image")`).

#### nano-banana-2

**Status:** GA on Vertex; Developer API still serves it as `-preview` (this client's surface)
**API Model ID:** `gemini-3.1-flash-image-preview`
**Alias:** `image`

Fast generation/editing on the Gemini 3.1 Flash Image platform. Default image
model in `generate_image()`. Capabilities on the Developer API:
- Output resolutions: 512 (0.5K), 1K, 2K generally available; 4K in preview.
  512 is 3.1-Flash-only.
- Up to 14 reference images (up to 10 high-fidelity objects + up to 4 characters).
- Grounding with Google Search, plus Image Search grounding (3.1-Flash-only) —
  cannot search for images of people.
- Thinking: `thinking_level` is {`minimal` (default), `high`}; thinking cannot be
  fully disabled and thinking tokens are billed.
- Extra aspect ratios over 2.5 Flash Image: 1:4, 4:1, 1:8, 8:1.

Note: the GA announcement's "video file as input prompt" capability is a Vertex
preview feature. The Developer API does NOT accept video or audio input for
image generation — don't route video here.

#### nano-banana-pro

**Status:** GA on Vertex; Developer API still serves it as `-preview` (this client's surface)
**API Model ID:** `gemini-3-pro-image-preview`
**Alias:** `image-pro`

High-fidelity generation on the Gemini 3 Pro Image platform — legible stylized
text rendering and professional asset production via advanced "thinking."
Capabilities:
- Output resolutions: 1K, 2K generally available; 4K in preview.
- Up to 14 reference images (up to 6 high-fidelity objects + up to 5 characters).
- Thinking always on (cannot be disabled).

---

## Model Selection Guide

```
Default (everyday coding, agents, docs)?   → gemini-4-hydrogen (alias: flash)
Maximum reasoning on a budget?             → gemini-4-hydrogen, thinking_level='xhigh' (alias: pro)
Harder / multi-file, still fast?           → gemini-4-neon (alias: neon)
Hardest problems, verification-heavy?      → gemini-4-carbon (alias: carbon)
Carbon-class, fewer tokens per turn?       → gemini-4-argon (alias: argon)
Routine / bulk / cheap / fastest?          → gemini-3.5-flash-lite (alias: lite)
True no-thinking pass (minimal)?           → gemini-3.5-flash-lite
Pin to previous-generation Flash?          → gemini-3.8-flash (alias: flash-3.8)
Label / route / score for code to branch on? → Gemini Decision 1 (Decisions API; not wired into this client)
Image generation?                          → nano-banana-2.1 (alias: image)
Image generation (high-fidelity)?          → nano-banana-pro (alias: image-pro)
Speech?                                    → gemini-3.8-flash-tts (alias: tts)
```

## Thinking Configuration (Gemini 3.x and 4)

Gemini 3.x and 4 models reason before responding, spending output tokens on
thinking before the visible answer. The parameter is the string enum
`thinking_level` ∈ {`minimal`, `low`, `medium`, `high`, `xhigh`}; the old
integer `thinking_budget` is gone. Which levels each model takes (verified live
2026-11-20):

| Model | `minimal` | `xhigh` | Default |
|---|---|---|---|
| gemini-4-hydrogen | HTTP 400 → `low` | accepted | high |
| gemini-4-neon | HTTP 400 → `low` | accepted | high |
| gemini-4-carbon | HTTP 400 → `low` | HTTP 400 → `high` | medium |
| gemini-4-argon | HTTP 400 → `low` | HTTP 400 → `high` | medium |
| gemini-3.8-flash | HTTP 400 → `low` | not tested | medium |
| gemini-3.5-flash-lite | accepted | not tested | minimal |

`→` is the client's automatic downgrade; it prints a note to stderr.

The Python client exposes this as `invoke_gemini(..., thinking_level="...")`.
Pass `None` (default) to let the model use its built-in default.

**When to set `thinking_level='minimal'`:**
- Transcription, OCR, image-to-text
- Classification, tagging, extraction with a fixed schema
- Any task where the LLM doesn't need to reason — it just needs to emit

**When to leave it as default or set higher:**
- Code generation, debugging
- Multi-step planning
- Math, complex analysis

**Why it matters:** A `max_output_tokens=50` request can return empty if
thinking_level (default `high` on Hydrogen and Neon) consumes all 50 tokens before
emitting visible output. Symptom: response text is empty, `finishReason`
is `MAX_TOKENS`. Fix: raise `max_output_tokens` substantially, or set
`thinking_level='low'` (`'minimal'` on `lite`).

## Multimodal Capabilities

All text models support:
- **Images:** JPEG, PNG, WebP, HEIC, HEIF
- **Video:** MP4, MPEG, MOV, AVI, FLV, MPG, WebM, WMV, 3GPP
- **Audio:** WAV, MP3, AIFF, AAC, OGG, FLAC

**Audio input pricing:** Higher than text, typically ~$1.00 / 1M tokens
on Flash-tier models.

## Deprecated / Retired Models

The client keeps every ID below callable by rewriting it to the replacement and
printing a note to stderr (`RETIRED_MODELS`, `RETIRED_IMAGE_MODELS`). Retired
2026-11-20 unless noted.

| Model | Google status (2026-11-20) | Client routes to |
|---|---|---|
| gemini-3.7-flash | Not in AI Studio; API auto-routes to 3.8 Flash | gemini-3.8-flash |
| gemini-3.6-flash | Retired on Google Cloud 2026-11-19; Gemini API: no date | gemini-4-hydrogen |
| gemini-3.5-flash | Not in AI Studio; API auto-routes to 3.6 Flash | gemini-4-hydrogen |
| gemini-3-flash-preview | No shutdown date; Google names 3.6 Flash | gemini-4-hydrogen |
| gemini-3.1-pro-preview | No shutdown date; off routing since 2026-09-03 | gemini-4-neon |
| gemini-3.1-flash-lite | Shutdown 2027-05-07 | gemini-3.5-flash-lite |
| gemini-2.5-pro | Deprecated; auto-routes to 3.8 Flash on 2026-12-01 | gemini-4-neon |
| gemini-2.5-flash | Deprecated; auto-routes to 3.5 Flash-Lite on 2026-12-01 | gemini-3.5-flash-lite |
| gemini-2.5-flash-lite | Not deprecated, but a 2025-era model | gemini-3.5-flash-lite |
| `nano-banana` (gemini-2.5-flash-image) | Shutdown 2026-10-02 | nano-banana-2.1 |
| gemini-3-pro-preview | Retired 2026-03-09 | gemini-3.1-pro-preview → gemini-4-neon |
| gemini-3.1-flash-lite-preview | Retired 2026-05-25 | gemini-3.5-flash-lite |
| gemini-2.0-flash(-lite)(-exp) | Retired 2026-06-01 | gemini-3.5-flash-lite |
| gemini-1.5-*, gemini-1.0-* | Retired (404) | — |

Old aliases `flash-3.7`, `flash-3.6`, `flash-3.5`, `flash-3`, `stable-flash`
and `stable-pro` reroute the same way. Speech previews
`gemini-3.1-flash-tts-preview`, `gemini-2.5-*-preview-tts` shut down
2026-12-18 (replacement: `gemini-3.8-flash-tts` / `-lite-tts`).
`gemini-3.1-flash-image-preview` and `gemini-3-pro-image-preview` (the
`nano-banana-2` and `nano-banana-pro` IDs) are still served; Google's docs list
GA IDs `gemini-3.1-flash-image` and `gemini-3-pro-image`, not yet probed here.

## Cost Optimization Tips

- **Batch API:** 50% discount on all paid models for async (≤24h) processing
- **Context caching:** Up to 75–90% savings for repeated large prompts
- **Long context:** Pro models charge 2× above 200K tokens — keep prompts concise
- **Free tier:** Gemini app + AI Studio offer free access to Flash and Lite
  models with daily quotas; Pro is paid-only as of April 2026

## Rate Limits

Vary by API tier (default free tier):
- **Requests per minute:** 15
- **Tokens per minute:** 1M
- **Requests per day:** 1,500

Client automatically handles rate limiting with exponential backoff.
