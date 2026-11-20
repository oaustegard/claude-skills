---
name: invoking-gemini
description: Invokes Google Gemini models for structured outputs, image generation, text-to-speech narration, multi-modal tasks, and Google-specific features. Use when users request Gemini, image generation, Gemini TTS or a synthesized voice, structured JSON output, Google API integration, or cost-effective parallel processing.
metadata:
  version: 0.10.0
---

# Invoking Gemini

Delegate tasks to Google's Gemini models when they offer advantages over Claude.

## When to Use Gemini

**Image generation:**
- Blog header images, illustrations, diagrams
- Style-guided image creation (risograph, editorial, etc.)
- Text rendering in images

**Speech (TTS):**
- Narration, voice-over, read-aloud with style direction per line
- A custom voice designed from a written description
- Two-speaker dialogue

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
| `"nano-banana-2.1"` or `"image"` | gemini-nano-banana-2.1 | Fast iteration, drafts, text rendering (default) | $0.034 (1K) – $0.113 (4K) |
| `"nano-banana-2"` | gemini-3.1-flash-image-preview | Pinned previous generation | $0.067 |
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

## Speech Generation (TTS)

Gemini 3.8 Flash TTS and Flash-Lite TTS went GA on 2026-09-23. Output is WAV,
24 kHz mono 16-bit, SynthID-watermarked.

```python
from gemini_client import generate_speech, design_voice, list_voices

r = generate_speech("Odin kept two ravens. <short pause> Huginn was thought.",
                    output_path="/tmp/line.wav", voice="Algenib",
                    style="quiet and dry, unhurried")
# {'path': '/tmp/line.wav', 'seconds': 4.2, 'audio_tokens': 135} or None

v = design_voice("A low, dry, quietly amused male voice with a faint rasp. "
                 "Soft southern British accent.", "narrator", gender="male",
                 language_code="en-GB")      # {'id': 'voice_...', 'sample_path': ...}
generate_speech("...", voice=v["id"])

lows = list_voices(gender="male", pitch="low")   # library of 2,089 prebuilt voices
```

- **Voices:** 30 studio voices (`Charon`, `Kore`, `Algenib` "gravelly",
  `Enceladus` "breathy", ...) plus 2,059 persona voices with ids like
  `en-gb-storyteller-4`. `list_voices()` returns accent, pitch, gender and a
  description for each; the `accent` filter needs the exact string ("Winchester
  English"), so filter accents on the returned field.
- **Style:** pass `style=` (a `speech_metadata` annotation). Do not prefix the
  text with "Style: ..." — the 3.8 models read the prefix aloud, and
  `systemInstruction` is rejected. Inline events go in the text: `<laugh>`,
  `<sigh>`, `<breath>`, `<short pause>`; CAPITALS stress a word.
- **Designed voices** are stored (1-year expiry, 200 per project). The
  description sets baseline delivery too: "thoughtful pauses" in it produced
  1–1.8 s mid-line pauses that no per-line style removed.
- **The model can change words.** Seen in a 29-line narration: "Hmm, I get
  things wrong", "tell them" for "tell him". Anything with subtitles or a
  fixed script needs an ASR check (faster-whisper `medium.en`) and a retake.
- **Cost:** about 32 audio tokens per second of speech, $9/M through
  2026-12-31 on 3.8 Flash TTS ($6/M Lite), so a minute is about $0.02.
- Voice replication (cloning from a 30 s sample plus a recorded consent clip) is
  not wired in, and is unavailable in the EEA, UK, Switzerland, India, Illinois
  and Texas.

## Basic Text Usage

```python
import sys
sys.path.append('/mnt/skills/user/invoking-gemini/scripts')
from gemini_client import invoke_gemini

response = invoke_gemini(
    prompt="Explain quantum computing in 3 bullet points",
    model="flash",  # gemini-4-hydrogen (default)
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

The current generation is **Gemini 4** (Argon 2026-10-13, Carbon 2026-11-10,
Hydrogen 2026-11-12, Neon 2026-11-18). **gemini-4-hydrogen** is the default and
the `flash` alias, following Google's own routing guide: Hydrogen for everyday
work, Neon for harder high-frequency work, Carbon for the hardest problems,
3.5 Flash-Lite for bulk text.

The Pro tier stays off routing (Oskar, 2026-09-03: Pareto efficiency). `pro`
resolves to Hydrogen, and "maximum reasoning" means `thinking_level='xhigh'` on
Hydrogen. Neon costs 2x Hydrogen's output price; Carbon 1.3x through 2026-11-30 and
2.7x from 2026-12-01. Ask for them by name when a task earns it.

Retired IDs (`gemini-3.7/3.6/3.5-flash`, `gemini-3-flash-preview`,
`gemini-3.1-pro-preview`, `gemini-2.5-*`, `nano-banana`) and the aliases
`flash-3.7`, `flash-3.6`, `flash-3.5`, `flash-3`, `stable-flash`, `stable-pro`
still work: the client rewrites them to the replacement and prints a note to
stderr. See the table in [references/models.md](references/models.md).

### Text / Reasoning Models

| Model | Alias | Input/1M | Output/1M | Thinking levels (default) | Notes |
|-------|-------|----------|-----------|---------------------------|-------|
| gemini-4-hydrogen | `flash`, `pro`, `hydrogen` | $1.50 | $7.50 | low, medium, high (default), xhigh | **Default.** Released 2026-11-12. Fast, free tier. Google reports >5x fewer fabricated claims than 3.8 Flash and parallel tool-call batching. |
| gemini-4-neon | `neon` | $3.00 | $15.00 | low, medium, high (default), xhigh | Released 2026-11-18. Between Hydrogen and Carbon: deeper reasoning than Hydrogen, faster than Carbon. Paid tier only. |
| gemini-4-carbon | `carbon` | $2.00 → $4.00 | $10.00 → $20.00 | low, medium (default), high | Released 2026-11-10. Strongest reasoning; for hard debugging, architecture, proofs, security. Price doubles on 2026-12-01. Rejects `xhigh`. |
| gemini-4-argon | `argon` | $2.00 → $4.00 | $10.00 → $20.00 | low, medium, high | Released 2026-10-13. Carbon-class with lower token spend per turn. Rejects `xhigh`. |
| gemini-3.8-flash | `flash-3.8` | $0.75 → $1.50 | $3.75 → $7.50 | low, medium (default), high | Previous-generation Flash, the one pinned fallback. Intro price runs through 2026-12-31. |
| gemini-3.5-flash-lite | `lite` | $0.30 | $2.50 | minimal (default), low, medium, high | **Bulk tier.** Lowest-cost general model; only text model here that accepts `minimal`. |

All Gemini 4 models: 1M unified context, 64K default output (up to 1M with long
decode), implicit caching only. `→` marks Carbon/Argon's introductory price
through 2026-11-30 and 3.8 Flash's through 2026-12-31. Output prices include
thinking tokens; Batch is half of standard.

### Image Models

| Model | Alias | Input/1M | Per Image |
|-------|-------|----------|-----------|
| gemini-nano-banana-2.1 | `image`, `nano-banana-2.1` | $1.50 | $0.034 (1K) / $0.050 (2K) / $0.113 (4K) |
| gemini-3.1-flash-image-preview | `nano-banana-2` | $0.25 | $0.067 |
| gemini-3-pro-image-preview | `image-pro`, `nano-banana-pro` | $2.00 | $0.134 |

### Speech Models

| Model | Alias | Input/1M | Output/1M (audio) | Notes |
|-------|-------|----------|-------------------|-------|
| gemini-3.8-flash-tts | `tts` | $0.50 → $1.00 | $9.00 → $18.00 | GA 2026-09-23. Expressive, 130 languages, 2 speakers. Use `generate_speech()`, not `invoke_gemini()`. |
| gemini-3.8-flash-lite-tts | `tts-lite` | $0.50 → $1.00 | $6.00 → $12.00 | GA 2026-09-23. Bulk / read-aloud, 101 languages. Replaces gemini-3.1-flash-tts-preview ($1 / $20). |

Speech aliases live in `SPEECH_ALIASES`, not `MODEL_ALIASES`, so a text call can
never resolve to an audio model.

See [references/models.md](references/models.md) for full details.

### Thinking Budget (Gemini 3.x and 4)

Gemini 3.x and 4 models reason before responding. Use the string
`thinking_level` ∈ {`minimal`, `low`, `medium`, `high`, `xhigh`}; the integer
`thinking_budget` is gone. Defaults: `high` on Hydrogen and Neon, `medium` on
Carbon, Argon and 3.8 Flash, `minimal` on 3.5 Flash-Lite. A model that thinks
by default will silently spend output tokens on reasoning (symptom: empty
response with `finishReason=MAX_TOKENS`), so budget `max_output_tokens`
generously or lower the level.

**Only `lite` accepts `minimal`.** Every Gemini 4 model and 3.8 Flash return
HTTP 400 (`Thinking level MINIMAL is not supported for this model`), so `low` is
their floor. **Carbon and Argon also reject `xhigh`.** The client downgrades
`minimal` to `low` and `xhigh` to `high` on those models and prints a note to
stderr, so existing callers keep working (verified live 2026-11-20). For a true
no-thinking pass, use `lite`.

```python
response = invoke_gemini(
    prompt="Transcribe this image.",
    model="lite",              # only lite takes 'minimal'
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
    model="flash",                  # gemini-4-hydrogen
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
