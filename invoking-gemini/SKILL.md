---
name: invoking-gemini
description: Invokes Google Gemini models for structured outputs, image generation, multi-modal tasks, and Google-specific features. Use when users request Gemini, image generation, structured JSON output, Google API integration, or cost-effective parallel processing.
metadata:
  version: 0.5.0
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
    model="gemini-3-flash-preview"
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
    model="gemini-3-flash-preview"
)
```

## Available Models

All Gemini 3 models are currently in preview. Use only these — no Gemini 2.x.

### Text / Reasoning Models

| Model | Alias | Input/1M | Output/1M | Context |
|-------|-------|----------|-----------|---------|
| gemini-3-flash-preview | `flash` | $0.50 | $3.00 | 1M |
| gemini-3.1-pro-preview | `pro` | $2.00 | $12.00 | 1M |
| gemini-3.1-flash-lite-preview | `lite` | $0.25 | $1.50 | 1M |

### Image Models

| Model | Alias | Input/1M | Per Image |
|-------|-------|----------|-----------|
| gemini-3.1-flash-image-preview | `image`, `nano-banana-2` | $0.25 | $0.067 |
| gemini-3-pro-image-preview | `image-pro`, `nano-banana-pro` | $2.00 | $0.134 |

See [references/models.md](references/models.md) for full details.

## Error Handling

```python
response = invoke_gemini(prompt="...", model="gemini-3-flash-preview")
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
    model="gemini-3-flash-preview",
    temperature=0.9,
    max_output_tokens=100,
    top_p=0.95
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
