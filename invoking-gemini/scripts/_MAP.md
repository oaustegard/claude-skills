# scripts/
*Files: 1*

## Files

### gemini_client.py
> Imports: `json, os, time, pathlib, typing`
- **get_cf_credentials** (f) `()` :109
- **get_google_api_key** (f) `()` :142
- **invoke_gemini** (f) `(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_output_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    image_path: Optional[str] = None,
)` :351
- **generate_image** (f) `(
    prompt: str,
    output_path: Optional[str] = None,
    model: str = "nano-banana-2",
    temperature: float = 0.7,
)` :432
- **invoke_with_structured_output** (f) `(
    prompt: str,
    pydantic_model: Type,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    image_path: Optional[str] = None,
)` :583
- **invoke_parallel** (f) `(
    prompts: list,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_workers: int = 5,
)` :659
- **get_available_models** (f) `()` :702
- **verify_setup** (f) `()` :715

