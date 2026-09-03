# Gemini Models Reference

Detailed information about available Gemini models (as of September 2026).

## Model Comparison

### Gemini 3.8 — Frontier Flash (GA, current default)

#### gemini-3.8-flash

**Status:** Generally available (released September 2, 2026)
**Alias:** `flash` (the current default Flash)

**Strengths:**
- Google's "most intelligent Flash model", positioned for long-horizon
  software engineering, autonomous agents, and multi-step enterprise work
- Vs 3.7 Flash (Google's own numbers): Terminal-Bench 2.1 90.8% vs 81.6%,
  SWE-Bench Pro 61.6% vs 60.4%, SWE-Atlas 51.9% vs 48.0%, τ³-bench Banking
  38.1% vs 30.9%, CharXiv 86.2% vs 84.5%; HLE-Verified 54.9%
- Humanity's Last Exam is flat (45.4% vs 45.7%) — the gains are agentic and
  tool-use, not open-ended reasoning
- Artificial Analysis Intelligence Index: 57 at `medium` (3.7 Flash 56,
  3.6 Flash 52); ~310 output tok/sec
- Prompt-injection robustness improved (Gray Swan); CBRN and cyber-offense
  safeguards carried forward

**Specifications:**
- Context window: 1,048,576 tokens input / 65,536 tokens output
- Multimodal input: text, image, video, audio, PDF; text output only
- `thinking_level`: `low`, `medium` (default), `high`. **`minimal` is not
  supported and returns HTTP 400** ("Thinking level MINIMAL is not supported
  for this model", verified 2026-09-03). The client downgrades `minimal` to
  `low` on this model.
- Google's release note: the model "works harder" on complex tasks — extra
  reasoning steps, iterative tool calls — so higher effort levels cost more
  tokens. Measured 2026-09-03: `low` spent 0 thinking tokens on a one-word
  reply; the default `medium` spent 79.
- Supports caching, code execution, computer use (preview), file search,
  function calling, Maps and Search grounding, structured outputs, URL
  context, Batch / Flex / Priority inference. No audio generation, image
  generation, or Live API.
- Google's migration notes for the 3.x line: `thinking_budget` is gone
  (use `thinking_level`); `temperature` / `top_p` / `top_k` /
  `candidate_count` are deprecated sampling params on this model.

**Best for:**
- Default Flash / sub-agent-delegation choice for most tasks
- Agentic coding loops, terminal automation, multi-file projects
- Finance/legal agent workflows (Vals Finance Agent V2, Harvey's Legal
  Agent Benchmark lead their Flash class)

**Pricing:**
- Input: $0.75 / 1M tokens through 2026-12-31; $1.50 from 2027-01-01
- Output: $3.75 / 1M tokens through 2026-12-31; $7.50 from 2027-01-01
  (includes thinking tokens)
- Context caching $0.075 → $0.15; Batch 50% off
- 1M context window at base price (no surcharge tier)

Shipped alongside **`gemini-3.8-flash-cyber`** — vulnerability discovery and
patching (>70% on Google's internal 20-language vuln benchmark, 47.2% pass@1
on CWE-Bench patching). Access is limited to Google's Fairwind Program
(government authorities, critical-infrastructure operators, software
maintainers), so this client cannot alias it.

---

### Gemini 3.7 — Prior Frontier Flash (GA)

#### gemini-3.7-flash

**Status:** Generally available (released August 13, 2026)
**Alias:** `flash-3.7` (was `flash` for three weeks until 3.8 shipped)

**Strengths:**
- The coding jump in the 3.x Flash line: DeepSWE v1.1 65.3% vs 49.0% on
  3.6 Flash, FrontierCode 1.1 43.6% vs 34.4%, AutomationBench 30.4% vs
  17.0%, WebDev Arena Elo 1588 vs 1538
- Terminal-Bench 2.1 85.8%, OSWorld-2.0 47.9%, GDM-MRCR v2 (128k) 97.0%
- Google keeps it "fully supported for efficiency-first workloads". Measured
  2026-09-03 on a one-word prompt, though, `low` on 3.7 still spent 45–88
  thinking tokens where `low` on 3.8 spent 0, and a `max_output_tokens=50`
  call at `low` hit MAX_TOKENS. Budget output generously on this model.

**Specifications:**
- Context window: 1,048,576 tokens input / 65,536 tokens output
- Multimodal input: text, image, video, audio, PDF
- `thinking_level`: `low`, `medium` (default), `high`; **`minimal` returns
  HTTP 400** (verified 2026-09-03), same as 3.8

**Pricing:**
- Same schedule as 3.8: $0.75 / $3.75 through 2026-12-31, then $1.50 / $7.50

---

### Gemini 3.6 — Older Flash (GA)

#### gemini-3.6-flash

**Status:** Generally available (released July 21, 2026)
**Alias:** `flash-3.6` (was `flash` until 3.7 shipped)

**Strengths:**
- Builds on 3.5 Flash for coding, knowledge work, and multimodal tasks
- The last Flash that accepts `thinking_level='minimal'` (verified
  2026-09-03) — pin here for true no-thinking transcription/extraction
- ~17% fewer output tokens than 3.5 Flash on the Artificial Analysis index
  (the headline efficiency win — addresses 3.5's verbosity)
- Quality gains alongside efficiency: DeepSWE 49% vs 37%, MLE-Bench 63.9%
  vs 49.7%, OSWorld-Verified 83.0% vs 78.4%, GDPval-AA v2 1421 vs 1349
- Built-in client-side Computer Use tool via the Gemini API (Preview)
- Dynamic thinking on by default (configurable via `thinking_level`)

**Specifications:**
- Context window: ~1M tokens input / 65,536 tokens output
- Multimodal: text, image, audio, video
- Default `thinking_level`: `medium` — set explicitly to `minimal` for
  transcription/classification/extraction or the model will silently spend
  output tokens on reasoning
- Enhanced Frontier Safety safeguards (CBRN, cyber-offense); model card
  notes a slight tone regression vs 3.5 Flash

**Best for:**
- Pinning prior-gen behavior, and `minimal`-thinking bulk work
- Cost-sensitive high-volume agentic work (cheaper output than 3.5)

**Pricing:**
- Same schedule as 3.7 and 3.8 on Google's pricing page (fetched
  2026-09-03): $0.75 / $3.75 through 2026-12-31, then $1.50 / $7.50. The
  July table here said $1.50 / $7.50 flat; the intro rate now covers all three.
- 1M context window at base price (no surcharge tier)

Shipped alongside two sibling models, neither wired into this client's alias
table:

- `gemini-3.5-flash-lite` — GA. Fastest 3.5-class model (350 output tok/sec),
  $0.30 / $2.50. **This is now the `lite` alias target** (repointed 2026-07-21
  from gemini-2.5-flash-lite). It costs ~6x more on output than the 2.5 model it
  replaces; that was accepted deliberately — the 2.5 generation is retired
  regardless of price.
- `gemini-3.5-flash-cyber` — vuln-finding, fine-tuned on 3.5 Flash; powers
  CodeMender. **NOT generally available**: access is limited to governments
  and trusted partners under a pilot program due to dual-use risk. It cannot
  simply be added as an alias.

---

### Gemini 3.5 — Legacy Flash (GA)

#### gemini-3.5-flash

**Status:** Generally available (released May 19, 2026 at Google I/O);
Google's model list now labels it "legacy". No shutdown date.
**Alias:** `flash-3.5` (was `flash` until 3.6 shipped)

**Strengths:**
- Frontier-class performance — beats Gemini 3.1 Pro on most coding and
  agentic benchmarks
- Runs ~4× faster on output tokens than other frontier models
- Frontier intelligence at sub-Pro pricing
- Dynamic thinking on by default (configurable via `thinking_level`)

**Specifications:**
- Context window: ~1M tokens input
- Multimodal: text, image, audio, video
- Knowledge cutoff: January 2026
- Default `thinking_level`: `medium` (was `high` on prior 3.x — set
  explicitly to `minimal` for transcription/classification/extraction or
  the model will silently spend output tokens on reasoning)

**Best for:**
- Pinning to prior-gen Flash behavior when 3.6–3.8 output differs
- Agentic coding loops, terminal automation, multi-file projects
- Multimodal document analysis where structure must be preserved

**Pricing:**
- Input: $1.50 / 1M tokens
- Output: $9.00 / 1M tokens
- 1M context window at base price (no surcharge tier)

---

### Gemini 3.x — Prior Preview Generation

#### gemini-3-flash-preview

**Status:** Preview (still callable — kept for back compat)
**Alias:** `flash-3`

The previous-generation Flash. Use when you need to pin behavior
established before the 3.5 cutover. Google's deprecation page lists
gemini-3.6-flash as its replacement, with no shutdown date. New code should
target `flash` (gemini-3.8-flash) instead.

**Pricing:**
- Input: $0.30 / 1M tokens
- Output: $2.50 / 1M tokens

#### gemini-3.1-pro-preview

**Status:** Preview. **DEPRECATED from routing 2026-09-03** (Oskar): "its
Pareto efficiency is too poor compared to the later Flash models." At today's
rates it costs 2.7× the input and 3.2× the output of 3.8 Flash (1.3× / 1.6× once
the Flash intro pricing ends), and 3.5 Flash already beat it on most coding and
agentic benchmarks. The ID stays callable for pinned code.
**Alias:** none — `pro` now resolves to gemini-3.8-flash. For maximum
reasoning use Flash with `thinking_level='high'`.

**Strengths:**
- Was the most capable Gemini Pro in the API
- 1M context with tiered pricing above 200K

**Specifications:**
- Context window: ~1M tokens input
- Long context surcharge: 2× above 200K input tokens
- Multimodal: text, image, video, audio

**Best for:**
- Nothing in new code. Pinned callers only.

**Pricing:**
- Input: $2.00 / 1M tokens (≤200K), $4.00 (>200K)
- Output: $12.00 / 1M tokens (≤200K), $18.00 (>200K) — the July table here
  said $24.00; Google's pricing page says $18.00 (fetched 2026-09-03)

**Note:** Google announced `gemini-3.5-pro` at I/O on 2026-05-19 for June.
As of 2026-09-03 it is not in the API model list or on the pricing page;
DeepMind still lists it as "coming soon". When it ships it gets the same
price/quality test against the current Flash before any alias points at it.

---

### Gemini 2.5 — DEPRECATED (retired 2026-07-21)

⚠️ The Gemini 2.5 text generation is **retired from routing**. A 2025-era
generation; the cost saving does not justify the quality gap. Model IDs remain
callable so pinned code does not hard-break, but do not target them in new work.
The `lite` alias now resolves to `gemini-3.5-flash-lite`.

#### gemini-2.5-flash

**Status:** Stable, generally available
**Alias:** `stable-flash`

**Strengths:**
- Production stability without preview-tier volatility
- Solid price-performance for reasoning tasks
- Empirically token-perfect on dense transcription benchmarks (May 2026)

**Specifications:**
- Context window: ~1M tokens input
- Multimodal: text, image, video, audio

**Best for:**
- Production workloads where preview models are too volatile
- High-volume tasks with a quality floor
- Multimodal extraction when cost matters but accuracy can't slip

**Pricing:**
- Input: $0.30 / 1M tokens
- Output: $2.50 / 1M tokens

#### gemini-2.5-flash-lite

**Status:** DEPRECATED (retired from routing 2026-07-21)
**Alias:** none — `lite` now points at gemini-3.5-flash-lite

**Strengths:**
- **Cheapest major-provider production model** ($0.10 / $0.40)
- Surprisingly capable on multimodal extraction — empirically transcribes
  dense tables on par with much pricier models
- Fast: typically lowest latency in the lineup

**Specifications:**
- Context window: ~1M tokens input
- Multimodal: text, image, video, audio

**Best for:**
- Ultra-budget batch processing
- Routine triage tasks (zeitgeist runs, inbox review, bsky image
  transcription, classification, simple extraction)
- Maximum throughput at minimum cost

**Pricing:**
- Input: $0.10 / 1M tokens
- Output: $0.40 / 1M tokens

#### gemini-2.5-pro

**Status:** Stable, generally available
**Alias:** `stable-pro`

**Strengths:**
- Pro-tier reasoning with production stability
- Well-documented behavior across long-running deployments

**Specifications:**
- Context window: ~1M tokens input
- Long context surcharge: 2× above 200K tokens
- Multimodal: text, image, video, audio

**Best for:**
- Complex tasks requiring production stability
- Long-document processing
- Quality-critical workloads

**Pricing:**
- Input: $1.25 / 1M tokens (≤200K), $2.50 (>200K)
- Output: $10.00 / 1M tokens (≤200K), $20.00 (>200K)

---

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

#### nano-banana

**Status:** Stable, GA (unchanged)
**API Model ID:** `gemini-2.5-flash-image`

Production-grade stability on the Gemini 2.5 Flash Image platform. Works best
with up to 3 input images.

---

## Model Selection Guide

```
Default Flash (frontier)?              → gemini-3.8-flash (alias: flash)
Maximum reasoning?                     → gemini-3.8-flash, thinking_level='high' (alias: pro)
Pro tier?                              → off routing since 2026-09-03; see gemini-3.1-pro-preview
Routine / bulk / cheap / fastest?      → gemini-3.5-flash-lite (alias: lite)
No-thinking pass (minimal) on Flash?   → gemini-3.6-flash (alias: flash-3.6)
Pin to prior frontier Flash (3.7)?     → gemini-3.7-flash (alias: flash-3.7)
Pin to legacy Flash (3.5)?             → gemini-3.5-flash (alias: flash-3.5)
Pin to older preview Flash?            → gemini-3-flash-preview (alias: flash-3)
Image generation (fast)?               → nano-banana-2 (alias: image)
Image generation (high-fidelity)?      → nano-banana-pro (alias: image-pro)
```

## Thinking Configuration (Gemini 3.x family)

Gemini 3.x models reason before responding. By default, the model spends
output tokens on reasoning, then on the visible answer. From Gemini 3.5
Flash on, the default is `medium` — down from `high` on prior 3.x — and the
parameter shape changed:

- **Old:** integer `thinking_budget`
- **New:** string enum `thinking_level` ∈ {`minimal`, `low`, `medium`, `high`}

Which models take `minimal` (all verified live 2026-09-03):

| Model | `minimal` |
|---|---|
| gemini-3.8-flash | HTTP 400 — client downgrades to `low` |
| gemini-3.7-flash | HTTP 400 — client downgrades to `low` |
| gemini-3.6-flash | accepted |
| gemini-3.5-flash | accepted |
| gemini-3.5-flash-lite | accepted |

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
thinking_level (default `medium` on 3.5–3.8) consumes all 50 tokens before
emitting visible output. Symptom: response text is empty, `finishReason`
is `MAX_TOKENS`. Fix: either raise `max_output_tokens` substantially or
set `thinking_level='minimal'`.

## Multimodal Capabilities

All text models support:
- **Images:** JPEG, PNG, WebP, HEIC, HEIF
- **Video:** MP4, MPEG, MOV, AVI, FLV, MPG, WebM, WMV, 3GPP
- **Audio:** WAV, MP3, AIFF, AAC, OGG, FLAC

**Audio input pricing:** Higher than text, typically ~$1.00 / 1M tokens
on Flash-tier models.

## Deprecated / Retired Models

| Model | Status | Migration Target |
|---|---|---|
| gemini-3-pro-preview | Retired (March 9, 2026) | gemini-3.1-pro-preview |
| gemini-3-flash-preview | Callable, no shutdown date | gemini-3.6-flash (Google's listed target) |
| gemini-3.1-flash-lite-preview | Retired (May 25, 2026) | gemini-3.1-flash-lite |
| gemini-3.1-flash-lite | Shutdown May 7, 2027 | gemini-3.5-flash-lite |
| gemini-3.1-flash-image-preview | Shutdown listed June 25, 2026 (still resolves) | gemini-3.1-flash-image |
| gemini-3-pro-image-preview | Shutdown listed June 25, 2026 (still resolves) | gemini-3-pro-image |
| gemini-2.5-flash-image (`nano-banana`) | Shutdown October 2, 2026 | gemini-3.1-flash-image |
| gemini-2.0-flash-exp | Retired June 1, 2026 | gemini-3.6-flash |
| gemini-2.0-flash | Retired June 1, 2026 | gemini-3.6-flash |
| gemini-2.0-flash-lite | Retired June 1, 2026 | gemini-3.5-flash-lite |
| gemini-1.5-pro | Retired (404) | gemini-2.5-pro |
| gemini-1.5-flash | Retired (404) | gemini-3.6-flash |
| gemini-1.0-* | Retired (404) | — |

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
