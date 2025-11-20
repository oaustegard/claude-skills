# Migration Guide: invoking-claude → orchestrating-agents

## Breaking Changes
None. All existing code remains compatible.

## New Features

### 1. Streaming Support
```python
# Old (still works)
response = invoke_claude("prompt")

# New (streaming)
response = invoke_claude_streaming("prompt", callback=print)
```

### 2. Parallel Streaming
```python
results = invoke_parallel_streaming(
    prompts,
    callbacks=[callback1, callback2]
)
```

### 3. Interrupt Support
```python
token = InterruptToken()
results = invoke_parallel_interruptible(prompts, interrupt_token=token)
# Later: token.interrupt()
```

## Renamed Skill
- Old path: `.../invoking-claude/...`
- New path: `.../orchestrating-agents/...`
- Update import paths accordingly

## What's New

### Enhanced Capabilities
1. **Streaming with callbacks**: Real-time feedback from API responses
2. **Parallel streaming**: Monitor multiple agents simultaneously
3. **Interrupt support**: Cancel long-running parallel operations
4. **Agent SDK delegation pattern**: Documentation for hybrid orchestration

### New Functions
- `invoke_claude_streaming()`: Single invocation with streaming callbacks
- `invoke_parallel_streaming()`: Parallel invocations with per-agent callbacks
- `invoke_parallel_interruptible()`: Parallel invocations with cancellation
- `InterruptToken`: Thread-safe interrupt flag class

### Backward Compatibility
All existing functions remain unchanged:
- `invoke_claude()` - works exactly as before
- `invoke_parallel()` - works exactly as before
- `ConversationThread` - works exactly as before

### Migration Steps

#### If using old skill name in code:
```python
# Old import path
sys.path.append('/home/user/claude-skills/invoking-claude/scripts')

# New import path
sys.path.append('/home/user/claude-skills/orchestrating-agents/scripts')
```

#### To adopt streaming:
```python
# Before
response = invoke_claude("Write analysis...")
print(response)  # Prints only after complete

# After
def show_progress(chunk):
    print(chunk, end='', flush=True)

response = invoke_claude_streaming(
    "Write analysis...",
    callback=show_progress  # Prints as it streams
)
```

#### To adopt interruption:
```python
# Before (no way to cancel)
results = invoke_parallel(long_prompts)

# After (can interrupt)
token = InterruptToken()
results = invoke_parallel_interruptible(
    long_prompts,
    interrupt_token=token
)
# In another thread or condition:
# token.interrupt()
```

## Timeline

This refactoring is effective immediately. No action required for existing code, but new features are available for adoption.

## Questions?

See:
- `SKILL.md` for full documentation
- `references/api-reference.md` for detailed API docs
- `scripts/test_streaming.py` for streaming examples
- `scripts/test_interrupt.py` for interrupt examples
