# Gemini Models Reference

Detailed information about available Gemini models (as of March 2026).

## Model Comparison

### Gemini 3.x — Frontier (Preview)

#### gemini-3-flash-preview

**Status:** Preview (Default)
**Alias:** `flash`

**Strengths:**
- Frontier-class performance rivaling larger models at flash-tier cost
- Upgraded visual and spatial reasoning
- Agentic coding capabilities
- Computer Use support (built-in)

**Specifications:**
- Context window: ~1M tokens input
- Multimodal: Yes (text, image, video, audio)

**Best for:**
- Default choice for most tasks
- Structured data extraction
- High-volume tasks needing strong reasoning
- Agentic workflows

**Pricing:**
- Input: $0.50 / 1M tokens
- Output: $3.00 / 1M tokens

#### gemini-3.1-pro-preview

**Status:** Preview
**Alias:** `pro`

**Strengths:**
- Most capable Gemini model available
- Advanced intelligence and complex problem-solving
- Powerful agentic and vibe coding capabilities
- Computer Use support (built-in)

**Specifications:**
- Context window: ~1M tokens input
- Long context surcharge: 2x above 200K tokens
- Multimodal: Yes (text, image, video, audio)

**Best for:**
- Complex analysis requiring deep reasoning
- Tasks where quality matters more than cost
- Advanced coding tasks

**Pricing:**
- Input: $2.00 / 1M tokens (≤200K), $4.00 (>200K)
- Output: $12.00 / 1M tokens (≤200K), $24.00 (>200K)

**Note:** Replaces the deprecated `gemini-3-pro-preview` (shutting down March 9, 2026).

---

### Gemini 2.5 — Stable Production

#### gemini-2.5-flash

**Status:** Stable
**Alias:** `stable-flash`

**Strengths:**
- Best price-performance for reasoning tasks
- Production-grade stability
- Large context window

**Specifications:**
- Context window: ~1M tokens input
- Multimodal: Yes (text, image, video, audio)

**Best for:**
- Production workloads needing stability
- High-volume tasks with budget constraints
- When preview models are too volatile

**Pricing:**
- Input: $0.30 / 1M tokens
- Output: $2.50 / 1M tokens

#### gemini-2.5-flash-lite

**Status:** Stable
**Alias:** `lite`

**Strengths:**
- Cheapest model in the lineup
- Fast response times
- Good quality for straightforward tasks

**Specifications:**
- Context window: ~1M tokens input
- Multimodal: Yes (text, image, video, audio)

**Best for:**
- Ultra-budget batch processing
- Simple classification and extraction
- Maximum throughput at minimum cost

**Pricing:**
- Input: $0.10 / 1M tokens
- Output: $0.40 / 1M tokens

#### gemini-2.5-pro

**Status:** Stable
**Alias:** `stable-pro`

**Strengths:**
- Advanced reasoning with production stability
- Deep reasoning and coding capabilities
- Well-documented behavior

**Specifications:**
- Context window: ~1M tokens input
- Long context surcharge: 2x above 200K tokens
- Multimodal: Yes (text, image, video, audio)

**Best for:**
- Complex tasks requiring production stability
- Long document processing
- Quality-critical applications

**Pricing:**
- Input: $1.25 / 1M tokens (≤200K), $2.50 (>200K)
- Output: $10.00 / 1M tokens (≤200K), $20.00 (>200K)

---

### Image Generation Models

#### gemini-3-pro-image

**Status:** Production

High-fidelity image generation with reasoning-enhanced composition:
- Legible text rendering in images
- Complex multi-turn editing workflows
- Character consistency using up to 14 reference inputs

**Note:** Image models require different API parameters than text models.

#### nano-banana-2

**Status:** Preview (Feb 2026)

Updated image generation built on Gemini 3.1 Flash Image platform:
- Faster performance than previous generation
- Sharper image-editing capabilities
- Optimized for speed over maximum quality

---

## Model Selection Guide

```
Default / general purpose?        → gemini-3-flash-preview (alias: flash)
Need maximum reasoning quality?   → gemini-3.1-pro-preview (alias: pro)
Production stability required?    → gemini-2.5-flash (alias: stable-flash)
Ultra-budget batch processing?    → gemini-2.5-flash-lite (alias: lite)
Complex + stable production?      → gemini-2.5-pro (alias: stable-pro)
Image generation?                 → gemini-3-pro-image or nano-banana-2
```

## Multimodal Capabilities

All text models support:
- **Images:** JPEG, PNG, WebP, HEIC, HEIF
- **Video:** MP4, MPEG, MOV, AVI, FLV, MPG, WebM, WMV, 3GPP
- **Audio:** WAV, MP3, AIFF, AAC, OGG, FLAC

**Audio input pricing:**
- Audio input is priced higher than text (e.g., $1.00/1M tokens for Flash models)

## Deprecated / Retired Models

| Model | Status | Migration Target |
|---|---|---|
| gemini-3-pro-preview | Deprecated (shutdown March 9, 2026) | gemini-3.1-pro-preview |
| gemini-2.0-flash-exp | Retiring June 1, 2026 | gemini-3-flash-preview |
| gemini-2.0-flash | Retiring June 1, 2026 | gemini-2.5-flash |
| gemini-2.0-flash-lite | Retiring June 1, 2026 | gemini-2.5-flash-lite |
| gemini-1.5-pro | Retired (404) | gemini-2.5-pro |
| gemini-1.5-flash | Retired (404) | gemini-2.5-flash |
| gemini-1.0-* | Retired (404) | — |

## Cost Optimization Tips

- **Batch API:** 50% discount on all paid models for async processing
- **Context caching:** Up to 75-90% savings for repeated large prompts
- **Long context:** Pro models charge 2x above 200K tokens — keep prompts concise
- **Free tier:** All models include up to 1,000 daily requests on the free tier

## Rate Limits

Vary by API tier (default free tier):
- **Requests per minute:** 15
- **Tokens per minute:** 1M
- **Requests per day:** 1,500

Client automatically handles rate limiting with exponential backoff.
