# Gemini Models Reference

Detailed information about available Gemini models.

## Model Comparison

### gemini-2.0-flash-exp

**Status:** Experimental (recommended)

**Strengths:**
- Fast response times (~1-2s)
- Native JSON Schema support
- Property ordering guarantees
- Cost-effective for batch processing

**Specifications:**
- Context window: ~1M tokens input
- Output limit: ~8K tokens
- Multimodal: Yes (text, image, video, audio)

**Best for:**
- Structured data extraction
- High-volume simple tasks
- JSON output requirements
- Budget-conscious projects

**Pricing (approximate):**
- Input: $0.15 / 1M tokens
- Output: $0.60 / 1M tokens

### gemini-1.5-pro

**Status:** Production

**Strengths:**
- Superior reasoning capabilities
- Larger context window (2M tokens)
- Better for complex tasks
- More nuanced understanding

**Specifications:**
- Context window: ~2M tokens input
- Output limit: ~8K tokens
- Multimodal: Yes (text, image, video, audio)

**Best for:**
- Complex analysis requiring reasoning
- Long document processing
- Tasks requiring deep understanding
- Quality-critical applications

**Pricing (approximate):**
- Input: $1.25 / 1M tokens
- Output: $5.00 / 1M tokens

### gemini-1.5-flash

**Status:** Production

**Strengths:**
- Balanced speed and quality
- Good general-purpose model
- Reliable for most tasks

**Specifications:**
- Context window: ~1M tokens input
- Output limit: ~8K tokens
- Multimodal: Yes (text, image, video, audio)

**Best for:**
- General-purpose tasks
- When 2.0-flash-exp feels too experimental
- Production stability required

**Pricing (approximate):**
- Input: $0.075 / 1M tokens
- Output: $0.30 / 1M tokens

## Model Selection Guide

```
Need structured JSON output? → gemini-2.0-flash-exp
Processing >1M tokens? → gemini-1.5-pro
Complex reasoning required? → gemini-1.5-pro
Cost is primary concern? → gemini-1.5-flash
Experimental OK, want latest? → gemini-2.0-flash-exp
Production stability critical? → gemini-1.5-flash
```

## Multimodal Capabilities

All models support:
- **Images:** JPEG, PNG, WebP, HEIC, HEIF
- **Video:** MP4, MPEG, MOV, AVI, FLV, MPG, WebM, WMV, 3GPP
- **Audio:** WAV, MP3, AIFF, AAC, OGG, FLAC

**Input limits:**
- Images: Up to 16 per request
- Video: Up to 1 hour total
- Audio: Up to 9.5 hours

## Context Windows

**Understanding token counts:**
- 1 token ≈ 4 characters
- 1 token ≈ 0.75 words
- 100 tokens ≈ 75 words

**Examples:**
- Short email: ~200 tokens
- Blog post: ~800 tokens
- Research paper: ~8,000 tokens
- Full book: ~100,000 tokens

## Rate Limits

Vary by API tier (default free tier):
- **Requests per minute:** 15
- **Tokens per minute:** 1M
- **Requests per day:** 1,500

Client automatically handles rate limiting with exponential backoff.

## Performance Characteristics

**Latency (typical):**
- gemini-2.0-flash-exp: 1-2s
- gemini-1.5-flash: 2-3s
- gemini-1.5-pro: 3-5s

**Throughput (parallel requests):**
- Rate limit is shared across parallel requests
- Optimal concurrency: 5-10 workers
- Use `max_workers` parameter in `invoke_parallel()`

## Versioning

**Model naming:**
- `-exp` suffix: Experimental, may change
- `-latest` suffix: Auto-updates to latest version
- Version numbers (e.g., `001`): Stable, frozen

**Recommendation:** Use explicit model names for reproducibility.

## Safety Settings

Default safety settings are moderate. Adjust if needed:

```python
import google.generativeai as genai

safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    # ... other categories
]

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    safety_settings=safety_settings
)
```

Categories:
- HARM_CATEGORY_HARASSMENT
- HARM_CATEGORY_HATE_SPEECH
- HARM_CATEGORY_SEXUALLY_EXPLICIT
- HARM_CATEGORY_DANGEROUS_CONTENT

Thresholds:
- BLOCK_NONE
- BLOCK_LOW_AND_ABOVE
- BLOCK_MEDIUM_AND_ABOVE
- BLOCK_ONLY_HIGH

## Experimental Features

**gemini-2.0-flash-exp only:**
- Native JSON Schema with property ordering
- Enhanced multimodal understanding
- Improved instruction following

**Note:** Experimental features may change without notice.
