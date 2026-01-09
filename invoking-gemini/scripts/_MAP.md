# scripts/
*Files: 1*

## Files

### gemini_client.py
> Imports: `json, time, typing, pathlib`
- **get_google_api_key** (f) `()`
- **invoke_gemini** (f) `(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_output_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    image_path: Optional[str] = None,
)`
- **invoke_with_structured_output** (f) `(
    prompt: str,
    pydantic_model: Type[BaseModel],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    image_path: Optional[str] = None,
)`
- **invoke_parallel** (f) `(
    prompts: list[str],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_workers: int = 5,
)`
- **get_available_models** (f) `()`
- **verify_setup** (f) `()`

