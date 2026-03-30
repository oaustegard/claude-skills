# Code Intelligence

Four skills form a dependency chain for understanding codebases: mapping-codebases extracts structure, exploring-codebases does semantic search, searching-codebases adds n-gram indexing, and generating-lattice produces cross-referenced documentation.

## AST Mapping

[[mapping-codebases/scripts/codemap.py#analyze_file]] extracts the API surface via tree-sitter — exports, classes, functions, signatures.

Language-specific extractors handle Python ([[mapping-codebases/scripts/codemap.py#extract_python]]), TypeScript/JavaScript ([[mapping-codebases/scripts/codemap.py#extract_typescript]]), Go ([[mapping-codebases/scripts/codemap.py#extract_go]]), Rust ([[mapping-codebases/scripts/codemap.py#extract_rust]]), Ruby ([[mapping-codebases/scripts/codemap.py#extract_ruby]]), Java ([[mapping-codebases/scripts/codemap.py#extract_java]]), and embedded JS ([[mapping-codebases/scripts/codemap.py#extract_html_javascript]]).

[[mapping-codebases/scripts/codemap.py#generate_maps]] walks the directory tree and produces `_MAP.md` files per directory. [[mapping-codebases/scripts/codemap.py#format_symbol]] renders each symbol with its type indicator (f=function, C=class, m=method), signature, and line number.

## Hybrid Code Search

[[exploring-codebases/scripts/search.py#HybridRetriever]] combines ripgrep pattern matching with tree-sitter context expansion. [[exploring-codebases/scripts/search.py#HybridRetriever#_run_ripgrep]] finds line-level matches, then [[exploring-codebases/scripts/search.py#HybridRetriever#_expand_context]] walks the AST to return the enclosing function or class — producing complete, syntactically valid code blocks rather than fragmented lines.

The retriever supports signature-only mode via [[exploring-codebases/scripts/search.py#HybridRetriever#_extract_signature]] which returns just the function declaration, saving tokens when full bodies aren't needed.

## N-gram Indexing

[[searching-codebases/scripts/ngram_index.py#NgramIndex]] builds a trigram index over source files for sub-millisecond regex search. [[searching-codebases/scripts/ngram_index.py#NgramIndex#build]] processes all files under a root, extracting trigrams weighted by [[searching-codebases/scripts/sparse_ngrams.py#FrequencyWeights]] which down-weight common ngrams to improve signal.

[[searching-codebases/scripts/ngram_index.py#extract_query_plan]] decomposes a regex pattern into a boolean query plan over trigram literals. [[searching-codebases/scripts/ngram_index.py#NgramIndex#search]] evaluates the plan to find candidate files, then [[searching-codebases/scripts/ngram_index.py#verify_candidates]] runs the actual regex against candidates for final verification.

The sparse ngram module provides [[searching-codebases/scripts/sparse_ngrams.py#build_covering]] for selecting a minimal set of ngrams that cover the frequency spectrum, and [[searching-codebases/scripts/sparse_ngrams.py#compute_weights]] for IDF-style weighting.

## Context Expansion

[[searching-codebases/scripts/context.py#expand_match]] takes a file path and line number and returns the enclosing code context by parsing `_MAP.md` files via [[searching-codebases/scripts/context.py#parse_map_file]]. [[searching-codebases/scripts/context.py#deduplicate_contexts]] removes overlapping results when multiple matches fall within the same function.

## Repository Resolution

[[searching-codebases/scripts/resolve.py#resolve]] handles source resolution — given a path, URL, or GitHub reference, it produces a local directory. Supports GitHub tarballs, local directories, and cloned repos. [[searching-codebases/scripts/resolve.py#count_files]] estimates indexing cost.

## Multi-Modal Search

[[searching-codebases/scripts/search.py#detect_mode]] classifies queries as regex or semantic based on metacharacter presence. [[searching-codebases/scripts/search.py#search_regex]] uses the n-gram index for fast regex matching. [[searching-codebases/scripts/search.py#search_semantic]] uses embedding-based retrieval. Both produce results formatted by [[searching-codebases/scripts/search.py#format_results]].

## Lattice Generation

[[generating-lattice/scripts/suggest_backlinks.py#parse_source_refs]] extracts all `[[src/...#symbol]]` wiki links from lat.md/ files. [[generating-lattice/scripts/suggest_backlinks.py#find_symbol_line]] locates the referenced symbol in source using regex. [[generating-lattice/scripts/suggest_backlinks.py#suggest_backlinks]] combines these to produce `@lat:` comment suggestions. [[generating-lattice/scripts/suggest_backlinks.py#apply_backlinks]] writes them into source files.
