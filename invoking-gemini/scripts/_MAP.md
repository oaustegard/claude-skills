# scripts/
*Files: 1*

## Files

### gemini_client.py
> Imports: `json, os, time, pathlib, typing`
- **get_cf_credentials** (f) `()` :87
- **get_google_api_key** (f) `()` :120
- **invoke_gemini** (f) `(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_output_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    image_path: Optional[str] = None,
)` :301
- **invoke_with_structured_output** (f) `(
    prompt: str,
    pydantic_model: Type,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    image_path: Optional[str] = None,
)` :384
- **invoke_parallel** (f) `(
    prompts: list,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_workers: int = 5,
)` :462
- **get_available_models** (f) `()` :504
- **verify_setup** (f) `()` :509

