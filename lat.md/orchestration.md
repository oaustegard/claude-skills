# Orchestration

Two skills handle parallel execution at different levels of abstraction: orchestrating-agents provides Claude API wrappers, and flowing provides a DAG workflow runner.

## Claude API Client

[[orchestrating-agents/scripts/claude_client.py#invoke_claude]] is the core single-call wrapper around the Anthropic messages API. It handles credential resolution via [[orchestrating-agents/scripts/claude_client.py#get_anthropic_api_key]], request construction, error handling, and response parsing.

[[orchestrating-agents/scripts/claude_client.py#invoke_claude_streaming]] adds streaming support with a callback interface. [[orchestrating-agents/scripts/claude_client.py#invoke_claude_json]] wraps invocation with JSON parsing and fence stripping for structured output.

## Parallel Execution

[[orchestrating-agents/scripts/claude_client.py#invoke_parallel]] runs multiple prompts concurrently using a thread pool. Each prompt gets its own API call, and results are collected in order. [[orchestrating-agents/scripts/claude_client.py#invoke_parallel_streaming]] extends this with per-prompt streaming callbacks.

[[orchestrating-agents/scripts/claude_client.py#invoke_parallel_interruptible]] adds cooperative cancellation via the [[orchestrating-agents/scripts/claude_client.py#InterruptToken]] mechanism — any thread can signal the others to stop early when a sufficient answer is found.

## Stall Detection

[[orchestrating-agents/scripts/claude_client.py#StallDetector]] monitors parallel tasks for timeouts. Tasks register, emit heartbeats, and the detector raises alerts when heartbeats stop. [[orchestrating-agents/scripts/claude_client.py#StallDetector#start_monitoring]] runs a background polling thread.

## Conversation Threads

[[orchestrating-agents/scripts/claude_client.py#ConversationThread]] manages multi-turn conversations with automatic history accumulation. [[orchestrating-agents/scripts/claude_client.py#ConversationThread#send]] appends to history and invokes the API. [[orchestrating-agents/scripts/claude_client.py#ConversationThread#send_continuation]] enables follow-up prompts within the same thread. Supports system prompt caching and configurable turn limits.

## Orchestration Layer

[[orchestrating-agents/scripts/orchestration.py#invoke_with_retry]] wraps API calls with exponential backoff via [[orchestrating-agents/scripts/orchestration.py#compute_backoff_delay]]. The `is_continuation` flag adjusts delay curves for follow-up calls that are more latency-sensitive.

[[orchestrating-agents/scripts/orchestration.py#invoke_parallel_with_reconciliation]] adds a reconciliation callback that can merge, filter, or re-dispatch results after parallel completion. Combined with the [[orchestrating-agents/scripts/orchestration.py#ConcurrencyLimiter]] which enforces global and per-category limits.

[[orchestrating-agents/scripts/orchestration.py#invoke_parallel_managed]] is the full-featured entry point combining retry, reconciliation, concurrency limiting, and stall detection.

## Task State Machine

[[orchestrating-agents/scripts/task_state.py#TaskState]] defines the state enum (pending, claimed, running, completed, failed, retrying, cancelled). [[orchestrating-agents/scripts/task_state.py#TaskTracker]] manages state transitions with validation — [[orchestrating-agents/scripts/task_state.py#TaskTracker#transition]] enforces the allowed transition graph and raises [[orchestrating-agents/scripts/task_state.py#InvalidTransitionError]] on illegal moves.

## DAG Workflow Runner

[[flowing/scripts/flowing.py#Flow]] is a lightweight DAG executor. Tasks declare dependencies via the [[flowing/scripts/flowing.py#task]] decorator's `depends_on` parameter. `Flow` topologically sorts tasks into layers and executes each layer in parallel.

[[flowing/scripts/flowing.py#Flow#run]] executes the full DAG. [[flowing/scripts/flowing.py#Flow#resume]] re-executes from the point of failure, skipping succeeded steps. [[flowing/scripts/flowing.py#Flow#override]] injects corrected values for failed tasks before resume.

Tasks decorated with `detached=True` run after the main DAG completes — useful for side effects like memory storage that shouldn't block the pipeline. Failures in detached tasks are collected but don't trigger fail_fast.

## Tiling Tree

[[tiling-tree/scripts/tiling_tree.py#build_tree]] implements MIT's exhaustive MECE exploration method.

It uses orchestrating-agents for parallel subagent invocation, recursively partitioning a problem into mutually exclusive subsets. [[tiling-tree/scripts/tiling_tree.py#evaluate_leaves]] scores leaf ideas against criteria. [[tiling-tree/scripts/tiling_tree.py#render_markdown]] formats the tree for human review.

## Gemini Client

[[invoking-gemini/scripts/gemini_client.py#invoke_gemini]] wraps the Google Generative AI API with Cloudflare gateway routing via [[invoking-gemini/scripts/gemini_client.py#get_cf_credentials]]. [[invoking-gemini/scripts/gemini_client.py#invoke_with_structured_output]] adds Pydantic schema enforcement. [[invoking-gemini/scripts/gemini_client.py#invoke_parallel]] mirrors the Claude parallel pattern for Gemini calls. [[invoking-gemini/scripts/gemini_client.py#generate_image]] handles image generation via Gemini's multimodal API.
