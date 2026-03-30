# Patterns

Cross-cutting design decisions that recur across unrelated skills, anchored to the implementations where they appear.

## Progressive Disclosure

The universal response to context window limits. Structure information so consumers see the overview first and drill into details on demand.

[[mapping-codebases/scripts/codemap.py#generate_maps]] produces `_MAP.md` files showing only exports and signatures — the API surface without implementation. [[building-github-index-v2/scripts/github_index.py#generate_index]] creates layered repo indexes with one-line summaries linking to full content. The lattice itself (lat.md/) follows this pattern: index → concept files → source code links.

## Declarative Spec, Deterministic Render

The LLM generates structured data; a deterministic runtime renders it. This separates creativity from correctness and makes output validatable.

The `lat check` CLI validates wiki links and back-references in lat.md/ files — the spec is markdown with `[[src/...#symbol]]` anchors. The flowing skill's [[flowing/scripts/flowing.py#task]] decorator declares a DAG spec that [[flowing/scripts/flowing.py#Flow#run]] executes deterministically. The json-render-ui skill extends this to UI generation.

## AST-First Analysis

Tree-sitter parsing produces structure without reading full source, saving tokens and enabling machine-verifiable operations.

[[mapping-codebases/scripts/codemap.py#analyze_file]] extracts symbols via AST. [[exploring-codebases/scripts/search.py#HybridRetriever#_expand_context]] walks the AST to find enclosing nodes. [[inspecting-skills/scripts/index.py#extract_symbols]] uses Python's `ast` module for symbol extraction. [[searching-codebases/scripts/ngram_index.py#NgramIndex#build]] indexes at the byte level but [[searching-codebases/scripts/context.py#expand_match]] returns AST-bounded results.

## Container Awareness

Claude.ai containers are ephemeral, network-restricted, and lack persistent state. Skills must handle tool installation, credential loading, and filesystem resets on every session.

[[configuring/scripts/getting_env.py#detect_environment]] identifies which container type is running. [[remembering/scripts/utilities.py#install_utilities]] materializes runtime code from memory on every boot. The boot.sh script installs skills from GitHub on every session because nothing persists.

Despite this shared concern, most skills solve it independently. configuring exists as a universal loader, but only a few skills actually reference it — the collection's most obvious missed abstraction.

## Retry with Backoff

Network calls fail. Every skill that makes HTTP requests implements retry, but the patterns vary.

[[orchestrating-agents/scripts/orchestration.py#compute_backoff_delay]] provides a shared implementation with jitter and continuation-awareness. [[orchestrating-agents/scripts/orchestration.py#invoke_with_retry]] wraps it for Claude API calls. The flowing skill's [[flowing/scripts/flowing.py#task]] decorator supports `retry` and `retry_backoff_base_ms` parameters for DAG steps.

The Turso database layer in [[remembering/scripts/turso.py]] has its own retry logic. The browsing-bluesky scripts handle rate limiting from the ATProto API independently.

## Parallel-Then-Reconcile

Fan out work to multiple workers, then merge results.

[[orchestrating-agents/scripts/orchestration.py#invoke_parallel_with_reconciliation]] is the explicit implementation — it runs prompts in parallel, then applies a reconciliation callback. [[orchestrating-agents/scripts/claude_client.py#invoke_parallel]] is the simpler variant without reconciliation. [[tiling-tree/scripts/tiling_tree.py#build_tree]] uses parallelism for recursive MECE decomposition. [[invoking-gemini/scripts/gemini_client.py#invoke_parallel]] mirrors the pattern for Gemini calls.

## Knowledge vs. Code Skills

Some skills contain only a SKILL.md — the markdown IS the implementation. They work because Claude already has the capabilities; the skill provides decision frameworks and workflow patterns.

Code skills can enforce behavior (generating-lattice uses `lat check`, [[remembering/scripts/task.py#Task#complete]] gates completion on storage). Knowledge skills rely on Claude following instructions, which is inherently less reliable. The tradeoff is maintenance cost: knowledge skills have zero dependencies and zero installation overhead.
