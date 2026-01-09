# scripts/
*Files: 1*

## Files

### gemini_client.py
> Imports: `json, time, typing, pathlib`
- **get_google_api_key** (f) `()` :25
- **invoke_gemini** (f) `(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_output_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    image_path: Optional[str] = None,
)` :107
- **invoke_with_structured_output** (f) `(
    prompt: str,
    pydantic_model: Type[BaseModel],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    image_path: Optional[str] = None,
)` :183
- **invoke_parallel** (f) `(
    prompts: list[str],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_workers: int = 5,
)` :249
- **get_available_models** (f) `()` :298
- **verify_setup** (f) `()` :308

