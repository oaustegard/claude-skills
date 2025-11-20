# Quick Reference: Implementation Checklist

## Pre-Flight Check
```bash
# Verify environment
cd /tmp
ls invoking-claude/  # Should exist
python3 -c "import anthropic; print(anthropic.__version__)"  # Should work
```

## Phase 1: Rename (5 min)
```bash
cd /tmp
mv invoking-claude multi-agent-coordination
cd multi-agent-coordination
```

**Files to update:**
- `SKILL.md` line 2: `name: multi-agent-coordination`
- `SKILL.md` line 3: Update description
- `SKILL.md` all: Replace path references

## Phase 2: Streaming (20 min)

### Add to claude_client.py after invoke_claude() (~line 200)
- [ ] `invoke_claude_streaming()` function (50 lines)
- [ ] `_build_messages()` helper (10 lines)
- [ ] `invoke_parallel_streaming()` function (60 lines)

**Test immediately:**
```python
python3 -c "
from scripts.claude_client import invoke_claude_streaming
result = invoke_claude_streaming('Say hello', callback=print)
"
```

## Phase 3: Interrupt (15 min)

### Add to claude_client.py after streaming functions
- [ ] `InterruptToken` class (15 lines)
- [ ] `invoke_parallel_interruptible()` function (50 lines)

**Test immediately:**
```python
python3 scripts/test_interrupt.py
```

## Phase 4: Documentation (15 min)

### SKILL.md updates
- [ ] After line 67: Add streaming examples (30 lines)
- [ ] After line 123: Add new function docs (40 lines)
- [ ] After line 290: Add Agent SDK section (80 lines)

## Phase 5: Tests (20 min)

**Create new files:**
- [ ] `scripts/test_streaming.py` (50 lines)
- [ ] `scripts/test_interrupt.py` (40 lines)

**Update existing:**
- [ ] `scripts/test_integration.py`: Add 3 test functions

**Run tests:**
```bash
python3 scripts/test_streaming.py
python3 scripts/test_interrupt.py
python3 scripts/test_integration.py
```

## Phase 6: Final (10 min)
- [ ] Create `MIGRATION.md`
- [ ] Verify all imports work
- [ ] Run all tests one final time

## Critical Code Snippets

### Streaming Function Template
```python
def invoke_claude_streaming(prompt, callback=None, **kwargs):
    client = anthropic.Anthropic(api_key=get_anthropic_api_key())
    accumulated = ""
    
    with client.messages.stream(model=model, messages=messages, **kwargs) as stream:
        for text in stream.text_stream:
            accumulated += text
            if callback:
                callback(text)
    
    return accumulated
```

### Interrupt Token Template
```python
class InterruptToken:
    def __init__(self):
        self._interrupted = threading.Event()
    
    def interrupt(self):
        self._interrupted.set()
    
    def is_interrupted(self):
        return self._interrupted.is_set()
```

### Parallel with Interrupt Template
```python
def invoke_parallel_interruptible(prompts, interrupt_token=None, **kwargs):
    if interrupt_token is None:
        interrupt_token = InterruptToken()
    
    def process_with_check(idx, config):
        if interrupt_token.is_interrupted():
            return (idx, None)
        result = invoke_claude(config['prompt'], **kwargs)
        return (idx, result)
    
    # Use ThreadPoolExecutor as in invoke_parallel
    # Check interrupt_token after each completion
```

## Common Pitfalls

### ❌ Don't
- Forget to import `threading` for InterruptToken
- Call `callback()` without checking if it's None
- Forget to accumulate text in streaming functions
- Use `invoke_claude` instead of `invoke_claude_streaming` in parallel streaming

### ✅ Do
- Copy existing error handling patterns
- Test each function immediately after adding
- Use the same parameter defaults as existing functions
- Keep backward compatibility (don't modify existing functions)

## Verification Commands

```bash
# Check syntax
python3 -m py_compile scripts/claude_client.py

# Quick functional test
python3 -c "
import sys
sys.path.append('scripts')
from claude_client import (
    invoke_claude_streaming,
    invoke_parallel_streaming,
    InterruptToken,
    invoke_parallel_interruptible
)
print('✓ All imports successful')
"

# Run test suite
python3 scripts/test_streaming.py && \
python3 scripts/test_interrupt.py && \
python3 scripts/test_integration.py && \
echo "✓ All tests passed"
```

## Time Estimate
- **Total:** 85 minutes
- **Critical path:** Streaming implementation (Phase 2)
- **Can parallelize:** Documentation while testing

## Success Criteria
1. ✅ All imports work
2. ✅ All tests pass
3. ✅ Backward compatible (existing code unchanged)
4. ✅ Streaming returns same result as non-streaming
5. ✅ Interrupt actually stops parallel execution

## If Something Goes Wrong

### Streaming doesn't work
```python
# Check anthropic library version
import anthropic
print(anthropic.__version__)  # Should be >= 0.8.0

# Verify stream API
with anthropic.Anthropic().messages.stream(...) as stream:
    for text in stream.text_stream:
        print(text)
```

### Threading issues
```python
# Verify threading module
import threading
event = threading.Event()
event.set()
assert event.is_set()  # Should be True
```

### Import errors
```bash
# Check Python path
python3 -c "import sys; print('\n'.join(sys.path))"

# Verify api-credentials skill
ls -la ../api-credentials/scripts/credentials.py
```

## Rollback Plan
If critical issues arise:
```bash
cd /tmp
rm -rf multi-agent-coordination
# Re-extract original invoking-claude.zip
```

Original skill works perfectly - enhancements are purely additive.
