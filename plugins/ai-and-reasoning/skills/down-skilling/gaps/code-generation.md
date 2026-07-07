# Code Generation

**Opus**: Generates well-structured code with appropriate error handling,
edge cases, naming conventions, and documentation. Infers architectural
patterns from context.

**Haiku**: Generates functional code for straightforward tasks. Common
issues:
- Omits error handling unless explicitly requested
- May use inconsistent naming conventions
- Documentation/comments sparse unless requested
- Edge cases rarely handled proactively
- May not match the existing codebase style

**Mitigation**: Specify every non-obvious quality requirement.

```
Write a Python function that [task].

Requirements:
- Function signature: def process_data(input: list[dict]) -> dict
- Handle these edge cases: empty list, missing keys, non-string values
- Include type hints on all parameters and return value
- Add a docstring with Args, Returns, and Raises sections
- Use snake_case for variables
- Raise ValueError (not return None) for invalid input
- Include inline comments for non-obvious logic only
```

For code that must match existing style:
```
Match the coding style of this example:
[paste 10-20 lines of existing code]

Specifically match: indentation, naming convention, comment style,
error handling pattern, import style.
```

For complex code, decompose into functions:
"Write function A first. Then write function B that calls A.
Do not write a single monolithic function."
