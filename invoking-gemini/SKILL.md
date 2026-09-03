---
name: invoking-gemini
description: Invokes Google Gemini models for structured outputs, image generation, multi-modal tasks, and Google-specific features. Use when users request Gemini, image generation, structured JSON output, Google API integration, or cost-effective parallel processing.
metadata:
  version: 0.8.0
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
    model="flash",  # gemini-3.8-flash (default)
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

**Nested models are supported.** Gemini's `responseSchema` rejects `$ref`/`$defs`,
which pydantic emits for every nested model, so the client inlines them before
sending:

```python
class Finding(BaseModel):
    claim: str
    confidence: Literal["high", "medium", "low"]
    note: str | None = None

class Analysis(BaseModel):
    findings: list[Finding]     # nested — inlined for you
    gaps: list[str]
```

**Budget output generously.** Thinking tokens count against `max_output_tokens`
(default 32768). Too low and the JSON truncates mid-object, which surfaces as a
pydantic parse error rather than a length error — the client now detects
`finishReason=MAX_TOKENS` and says so explicitly.

## Parallel Invocation

```python
from gemini_client import invoke_parallel

results = invoke_parallel(
    prompts=["Summarize Hamlet", "Summarize Macbeth", "Summarize Othello"],
    model="lite",  # gemini-3.5-flash-lite — cheap/fast tier for batch
)
```

## Available Models

The current frontier Flash is **gemini-3.8-flash** (GA 2026-09-02), the
default and the `flash` alias. Google shipped three Flash generations in six
weeks: 3.6 (2026-07-21), 3.7 (2026-08-13), 3.8 (2026-09-02). Each stays
callable under a pinned alias (`flash-3.7`, `flash-3.6`, `flash-3.5`,
`flash-3`), and none has a shutdown date. `gemini-3.1-flash-lite-preview` from
earlier docs is gone (shut down 2026-05-25).

The Pro tier is off routing. `gemini-3.1-pro-preview` costs 2.7× the input and
3.2× the output of 3.8 Flash at today's rates and loses to the 3.5+ Flash line
on the coding and agentic benchmarks that matter here. Do not target it; the
`pro` alias now resolves to gemini-3.8-flash, and "maximum reasoning" means
`thinking_level='high'` on Flash.

### Text / Reasoning Models

| Model | Alias | Input/1M | Output/1M | Context | Notes |
|-------|-------|----------|-----------|---------|-------|
| gemini-3.8-flash | `flash` | $0.75 → $1.50 | $3.75 → $7.50 | 1M in / 64K out | **Default.** GA 2026-09-02. Current frontier Flash. Vs 3.7: Terminal-Bench 2.1 90.8% vs 81.6%, SWE-Bench Pro 61.6% vs 60.4%, SWE-Atlas 51.9% vs 48.0%, HLE flat (45.4% vs 45.7%). Google says it "works harder" at higher effort, so expect more thinking tokens per task. `thinking_level` is low/medium/high only — `minimal` returns HTTP 400 and the client downgrades it to `low`. Default `medium` spent 79 thinking tokens on a one-word reply (measured 2026-09-03); pass `low` for non-reasoning tasks. |
| gemini-3.7-flash | `flash-3.7` | $0.75 → $1.50 | $3.75 → $7.50 | 1M / 64K | GA 2026-08-13. DeepSWE v1.1 65.3% vs 49.0% on 3.6, Terminal-Bench 2.1 85.8%. Same `minimal` restriction as 3.8. Google keeps it "fully supported for efficiency-first workloads". |
| gemini-3.6-flash | `flash-3.6` | $0.75 → $1.50 | $3.75 → $7.50 | 1M / 64K | GA 2026-07-21. ~17% fewer output tokens than 3.5 Flash. Last Flash that accepts `thinking_level='minimal'` (verified 2026-09-03). |
| gemini-3.5-flash | `flash-3.5` | $1.50 | $9.00 | 1M | GA 2026-05-19. Google's model list now labels it "legacy". Accepts `minimal`. Costs more on output than 3.6–3.8. |
| gemini-3-flash-preview | `flash-3` | $0.30 | $2.50 | 1M | Older preview Flash, kept for back compat. Google's listed migration target for it is gemini-3.6-flash; no shutdown date. |
| ~~gemini-3.1-pro-preview~~ | — | $2.00 (≤200K) / $4.00 | $12.00 / $18.00 | 1M | **DEPRECATED from routing (2026-09-03).** Price/quality dominated by 3.6+ Flash; 3.5 Flash already beat it on most coding/agentic benchmarks. ID stays callable for pinned code. `pro` now resolves to gemini-3.8-flash. 3.5 Pro was announced at I/O 2026-05-19 for June and is still absent from the API as of 2026-09-03; it gets the same price/quality test before any alias points at it. |
| gemini-3.5-flash-lite | `lite` | $0.30 | $2.50 | 1M | **Cheap/bulk tier.** GA 2026-07-21. Fastest 3.5-class (350 output tok/sec); beats gemini-3-flash on SWE-Bench Pro and OSWorld-Verified. |
| ~~gemini-2.5-flash~~ | `stable-flash` | $0.30 | $2.50 | 1M | **DEPRECATED** — 2025-era generation, do not route here. |
| ~~gemini-2.5-flash-lite~~ | — | $0.10 | $0.40 | 1M | **DEPRECATED** — cheaper, but a 2025-era generation. `lite` now resolves to gemini-3.5-flash-lite. |
| ~~gemini-2.5-pro~~ | `stable-pro` | $1.25 (≤200K) / $2.50 | $10.00 / $20.00 | 1M | **DEPRECATED** — 2025-era generation, do not route here. |

`$0.75 → $1.50` means introductory pricing: Google's pricing page (fetched
2026-09-03) lists 3.6, 3.7 and 3.8 Flash at $0.75 in / $3.75 out through
2026-12-31 and $1.50 / $7.50 from 2027-01-01. Context caching is $0.075 → $0.15;
Batch is half of standard. Output prices include thinking tokens.

### Image Models

| Model | Alias | Input/1M | Per Image |
|-------|-------|----------|-----------|
| gemini-3.1-flash-image-preview | `image`, `nano-banana-2` | $0.25 | $0.067 |
| gemini-3-pro-image-preview | `image-pro`, `nano-banana-pro` | $2.00 | $0.134 |

See [references/models.md](references/models.md) for full details.

### Thinking Budget (Gemini 3.x)

Gemini 3.x models reason before responding. The parameter changed in
2026: integer `thinking_budget` is gone; use string `thinking_level`
∈ {`minimal`, `low`, `medium`, `high`}. Default for 3.5–3.8 Flash is
`medium`. For transcription / classification / extraction tasks, pass
`thinking_level='minimal'` or the model will silently spend output
tokens on reasoning (symptom: empty response with
`finishReason=MAX_TOKENS`).

**3.7 and 3.8 Flash reject `minimal`** with HTTP 400 (`Thinking level MINIMAL
is not supported for this model`); `low` is their floor. The client downgrades
`minimal` to `low` on those two models and prints a note to stderr, so existing
callers keep working. Measured on 3.8 (2026-09-03): `low` spent 0 thinking
tokens on a one-word reply, the default `medium` spent 79. On 3.7, `low` still
spent 45–88, and a `max_output_tokens=50` call at `low` hit MAX_TOKENS and
returned None, so budget output generously there. If a job needs a true
no-thinking pass, pin `flash-3.6` or `lite`, which still accept `minimal`.

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
    model="flash",                  # gemini-3.8-flash
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
