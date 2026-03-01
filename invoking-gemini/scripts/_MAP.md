# scripts/
*Files: 1*

## Files

### gemini_client.py
> Imports: `json, os, time, pathlib, typing`
- **get_cf_credentials** (f) `()` :106
- **get_google_api_key** (f) `()` :139
- **invoke_gemini** (f) `(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_output_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    image_path: Optional[str] = None,
)` :346
- **invoke_with_structured_output** (f) `(
    prompt: str,
    pydantic_model: Type,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    image_path: Optional[str] = None,
)` :427
- **invoke_parallel** (f) `(
    prompts: list,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_workers: int = 5,
)` :503
- **get_available_models** (f) `()` :546
- **verify_setup** (f) `()` :559

