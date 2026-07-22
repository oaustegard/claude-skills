---
name: invoking-gemini
description: Invokes Google Gemini models for structured outputs, image generation, multi-modal tasks, and Google-specific features. Use when users request Gemini, image generation, structured JSON output, Google API integration, or cost-effective parallel processing.
metadata:
  version: 0.6.0
---

# Invoking Gemini

Delegate tasks to Google's Gemini models when they offer advantages over Claude.

## When to Use Gemini

**Image generation:**
- Blog header images, illustrations, diagrams
- Style-guided image creation (risograph, editorial, etc.)
- Text rendering in images

**Structured outputs:**
- JSON Schema validation with property ordering guarantees
- Pydantic model compliance
- Strict schema adherence (enum values, required fields)

**Cost optimization:**
- Parallel batch processing (Gemini 3 Flash is lightweight)
- High-volume simple tasks

**Multi-modal tasks:**
- Image analysis with JSON output
- Video processing
- Audio transcription with structure

## Setup

```bash
uv pip install requests pydantic
```

**Credentials — Option A (recommended): Cloudflare AI Gateway**

Source `/mnt/project/proxy.env` with `CF_ACCOUNT_ID`, `CF_GATEWAY_ID`, `CF_API_TOKEN`.
Requests route through Cloudflare AI Gateway, bypassing IP blocks. Google API key stored in gateway via BYOK.

**Credentials — Option B: Direct Google API**

If no `proxy.env`, falls back to direct: `GOOGLE_API_KEY.txt` or `API_CREDENTIALS.json`.

## Image Generation

Generate images using Gemini's native image models. This is the primary way to create illustrations, blog headers, diagrams, and visual content.

### Quick Start

```python
import sys
sys.path.append('/mnt/skills/user/invoking-gemini/scripts')
from gemini_client import generate_image

# One call — returns {"path": "...", "caption": "..."} or None
result = generate_image("A watercolor painting of a mountain lake at sunset")
print(result["path"])  # /mnt/user-data/outputs/gemini_image_1740000000.png
```

### Function Signature

```python
generate_image(
    prompt: str,                    # The image description
    output_path: str = None,        # Auto-generates if omitted
    model: str = "nano-banana-2",   # Default: fast. Use "image-pro" for quality
    temperature: float = 0.7,       # 0.5-0.7 for diagrams, 0.7-0.8 for illustrations
) -> dict | None
# Returns: {"path": "/mnt/user-data/outputs/gemini_image_*.png", "caption": str|None}
# Returns None on failure
```

### Model Selection

| Alias | Model | Best For | Cost/image |
|-------|-------|----------|------------|
| `"nano-banana-2"` or `"image"` | gemini-3.1-flash-image-preview | Fast iteration, drafts | $0.067 |
| `"image-pro"` or `"nano-banana-pro"` | gemini-3-pro-image-preview | Published content, text rendering | $0.134 |

### Complete Blog Header Example

```python
import sys
sys.path.append('/mnt/skills/user/invoking-gemini/scripts')
from gemini_client import generate_image

# 1. Compose prompt with style prefix + subject
style_prefix = (
    "Style: Risograph-inspired editorial illustration. "
    "Visible halftone dot texture and slight color misregistration between layers. "
    "Limited ink palette: deep indigo, warm coral, and sage green on off-white paper. "
    "Layered transparency where colors overlap creates rich secondary tones. "
    "Modern and professional — the aesthetic of an indie design studio, not a fantasy novel. "
    "Generous whitespace. No photorealism, no glow effects, no cyberpunk. No text or labels."
)
subject = "A raven perched on a stack of books, observing a network graph"
prompt = f"{style_prefix}\n\nSubject: {subject}. Wide landscape format, suitable as a blog header."

# 2. Generate (use image-pro for published content)
result = generate_image(prompt, model="image-pro", temperature=0.75)

if result:
    print(f"Saved: {result['path']}")
    # 3. Present to user
    # present_files([result["path"]])
```

### Prompt Patterns

- **Style prefix + subject**: Prepend a style description, then describe the subject
- **Be specific about style**: "Risograph-inspired editorial illustration" not "a nice picture"
- **Include composition**: "Wide landscape format" / "centered, high contrast"
- **Text rendering**: "A poster with the text 'SALE' in bold red letters" (works well with image-pro)
- **Negative constraints**: "No photorealism, no glow effects" to avoid defaults

### Custom Output Path

```python
result = generate_image(
    "A logo for a coffee shop called 'Bean There'",
    output_path="/mnt/user-data/outputs/coffee_logo.png"
)
```

## Basic Text Usage

```python
import sys
sys.path.append('/mnt/skills/user/invoking-gemini/scripts')
from gemini_client import invoke_gemini

response = invoke_gemini(
    prompt="Explain quantum computing in 3 bullet points",
    model="flash",  # gemini-3.6-flash (default)
)
print(response)
```

## Structured Output

Use Pydantic models for guaranteed JSON Schema compliance:

```python
from gemini_client import invoke_with_structured_output
from pydantic import BaseModel, Field

class BookAnalysis(BaseModel):
    title: str
    genre: str = Field(description="Primary genre")
    key_themes: list[str] = Field(max_length=5)
    rating: int = Field(ge=1, le=5)

result = invoke_with_structured_output(
    prompt="Analyze the book '1984' by George Orwell",
    pydantic_model=BookAnalysis
)
print(result.title)  # "1984"
```

## Parallel Invocation

```python
from gemini_client import invoke_parallel

results = invoke_parallel(
    prompts=["Summarize Hamlet", "Summarize Macbeth", "Summarize Othello"],
    model="lite",  # gemini-3.5-flash-lite — cheap/fast tier for batch
)
```

## Available Models

The current frontier Flash is **gemini-3.6-flash** (GA 2026-07-21), the
default and the `flash` alias. Prior-gen `gemini-3.5-flash` (GA May 2026)
remains callable as `flash-3.5`. `gemini-3-flash-preview` and
`gemini-3.1-flash-lite-preview` from earlier docs are out of date.

### Text / Reasoning Models

| Model | Alias | Input/1M | Output/1M | Context | Notes |
|-------|-------|----------|-----------|---------|-------|
| gemini-3.6-flash | `flash` | $1.50 | $7.50 | 1M in / 64K out | **Default.** GA 2026-07-21. Current frontier Flash: ~17% fewer output tokens than 3.5 Flash, better coding/agentic (DeepSWE 49% vs 37%, OSWorld 83% vs 78%). Default `thinking_level=medium` — set `minimal` for non-reasoning tasks. Model card notes a slight tone regression vs 3.5. |
| gemini-3.5-flash | `flash-3.5` | $1.50 | $9.00 | 1M | Prior frontier Flash (GA May 2026). Beats 3.1 Pro on most coding/agentic benchmarks. |
| gemini-3-flash-preview | `flash-3` | $0.30 | $2.50 | 1M | Older preview Flash, kept for back compat |
| gemini-3.1-pro-preview | `pro` | $2.00 (≤200K) / $4.00 | $12.00 / $24.00 | 1M | Current Pro tier; 3.5 Pro slated for June 2026 |
| gemini-3.5-flash-lite | `lite` | $0.30 | $2.50 | 1M | **Cheap/bulk tier.** GA 2026-07-21. Fastest 3.5-class (350 output tok/sec); beats gemini-3-flash on SWE-Bench Pro and OSWorld-Verified. |
| ~~gemini-2.5-flash~~ | `stable-flash` | $0.30 | $2.50 | 1M | **DEPRECATED** — 2025-era generation, do not route here. |
| ~~gemini-2.5-flash-lite~~ | — | $0.10 | $0.40 | 1M | **DEPRECATED** — cheaper, but a 2025-era generation. `lite` now resolves to gemini-3.5-flash-lite. |
| ~~gemini-2.5-pro~~ | `stable-pro` | $1.25 (≤200K) / $2.50 | $10.00 / $20.00 | 1M | **DEPRECATED** — 2025-era generation, do not route here. |

### Image Models

| Model | Alias | Input/1M | Per Image |
|-------|-------|----------|-----------|
| gemini-3.1-flash-image-preview | `image`, `nano-banana-2` | $0.25 | $0.067 |
| gemini-3-pro-image-preview | `image-pro`, `nano-banana-pro` | $2.00 | $0.134 |

See [references/models.md](references/models.md) for full details.

### Thinking Budget (Gemini 3.x)

Gemini 3.x models reason before responding. The parameter changed in
2026: integer `thinking_budget` is gone; use string `thinking_level`
∈ {`minimal`, `low`, `medium`, `high`}. Default for 3.5 Flash is
`medium`. For transcription / classification / extraction tasks, pass
`thinking_level='minimal'` or the model will silently spend output
tokens on reasoning (symptom: empty response with
`finishReason=MAX_TOKENS`).

```python
response = invoke_gemini(
    prompt="Transcribe this image.",
    model="flash",
    image_path="/tmp/screenshot.png",
    max_output_tokens=4000,
    thinking_level="minimal",  # don't burn output budget on reasoning
)
```

## Error Handling

```python
response = invoke_gemini(prompt="...", model="flash")
if response is None:
    print("API call failed — check credentials")

result = generate_image("...")
if result is None:
    print("Image generation failed — check credentials or try again")
```

Common issues: Missing API key → see Setup. Rate limit → auto-retries with backoff. Network error → returns None.

## Advanced Features

### Custom Generation Config

```python
response = invoke_gemini(
    prompt="Write a haiku",
    model="flash",                  # gemini-3.6-flash
    temperature=0.9,
    max_output_tokens=200,
    top_p=0.95,
    thinking_level="low",           # haiku is short; modest reasoning is fine
)
```

### Multi-modal Input

```python
from pydantic import BaseModel
from gemini_client import invoke_with_structured_output

class ImageDescription(BaseModel):
    objects: list[str]
    scene: str
    colors: list[str]

result = invoke_with_structured_output(
    prompt="Describe this image",
    pydantic_model=ImageDescription,
    image_path="/mnt/user-data/uploads/photo.jpg"
)
```

See [references/advanced.md](references/advanced.md) for more patterns.

## Troubleshooting

**"No credentials configured":** Create `/mnt/project/proxy.env` with CF credentials, or add `GOOGLE_API_KEY.txt`.

**CF Gateway 401/403:** Verify `CF_API_TOKEN` has AI Gateway permissions. If not using BYOK, add `GOOGLE_API_KEY` to `proxy.env`.

**Import errors:** `uv pip install requests pydantic`

**Image generation returns None:** Check credentials. If persistent, try `model="nano-banana-2"` (more reliable than image-pro). Check for content policy blocks in error output.
