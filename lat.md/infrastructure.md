# Infrastructure

The connective tissue: environment detection, credential loading, GitHub access, and the boot sequence that wires everything together.

## Environment Detection

[[configuring/scripts/getting_env.py#detect_environment]] identifies the runtime context — Claude.ai, Claude Code, Codex, Jules, or shell.

Each environment stores credentials differently. [[configuring/scripts/getting_env.py#load_all]] iterates through all known credential locations for the detected environment.

[[configuring/scripts/getting_env.py#get_env]] retrieves a single variable with optional validation and required enforcement. [[configuring/scripts/getting_env.py#load_env]] loads a specific `.env` file. [[configuring/scripts/getting_env.py#mask_secret]] redacts values for safe display. [[configuring/scripts/getting_env.py#debug_info]] dumps the full resolution chain for troubleshooting.

## GitHub Repository Access

Two skills provide GitHub access at different levels. The building-github-index-v2 skill generates progressive disclosure indexes for use as Claude project knowledge.

[[building-github-index-v2/scripts/github_index.py#process_repo]] fetches repository metadata and file listings via [[building-github-index-v2/scripts/github_index.py#api_request]], then selectively fetches content via [[building-github-index-v2/scripts/github_index.py#fetch_file]]. It extracts structure from markdown ([[building-github-index-v2/scripts/github_index.py#extract_headings]]), frontmatter ([[building-github-index-v2/scripts/github_index.py#extract_frontmatter]]), and code ([[building-github-index-v2/scripts/github_index.py#extract_code_symbols]]).

[[building-github-index-v2/scripts/github_index.py#generate_index]] assembles the multi-file progressive disclosure output: a root index with one-line summaries, category groupings, and drill-down links.

[[building-github-index-v2/scripts/pk_index.py#process_repo]] is the project-knowledge variant — it fetches the repo tarball via [[building-github-index-v2/scripts/pk_index.py#fetch_tarball]] and uses tree-sitter for symbol extraction ([[building-github-index-v2/scripts/pk_index.py#extract_py_symbols]], [[building-github-index-v2/scripts/pk_index.py#extract_js_symbols]]) to produce a compact index.

## Boot Sequence

The boot script (boot.sh) ensures core skills are installed, sources credentials from project env files, sets up Python paths, and invokes [[remembering/scripts/boot.py#boot]] which handles the full memory system initialization. See [[memory#Boot Sequence]] for details.

## Utility Materialization

[[remembering/scripts/utilities.py#install_utilities]] bridges persistent storage and runtime code.

Utility modules (blog_publish, strava, therapy, etc.) are stored as memories tagged `utility-code`. At boot, `install_utilities()` retrieves these and writes them to `~/muninn_utils/` as importable Python modules. New tools ship as memory writes without touching the repository.
