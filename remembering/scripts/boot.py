"""
Boot, journal, therapy, handoff, and export/import operations for remembering skill.

This module handles:
- Boot sequence (boot, profile, ops, _warm_cache)
- GitHub access detection and configuration
- Journal operations (journal, journal_recent, journal_prune)
- Therapy helpers (therapy_scope, therapy_session_count, decisions_recent)
- Analysis helpers (group_by_type, group_by_tag)
- Handoff workflow (handoff_pending, handoff_complete)
- Export/Import (muninn_export, muninn_import)

Imports from: state, turso, cache, memory, config
"""

import json
import os
import shutil
import subprocess
import threading
from datetime import datetime, UTC
from pathlib import Path

from . import state
from .state import get_session_id
from .turso import _exec, _exec_batch
from .cache import _init_local_cache, _cache_available, _cache_config, _cache_populate_index, _cache_populate_full
from .memory import recall, recall_since, remember, supersede
from .config import config_list, config_set, config_delete
from .utilities import install_utilities


# --- Ops Topic Classification ---
# This mapping organizes operational configs by cognitive domain for boot output.
# v3.6.0: Loaded dynamically from config('ops-topics'), with fallback to defaults.

_DEFAULT_OPS_TOPICS = {
    'Core Boot & Behavior': [
        'boot-behavior', 'boot-output-hygiene', 'dev-workflow'
    ],
    'Memory Operations': [
        # v3.8.0 (#265): Consolidated recall-fields and recall-discipline into remembering-api
        'remembering-api', 'memory-types', 'memory-backup',
        'storage-rules', 'storage-initiative', 'think-then-store',
        'recall-before-speculation', 'recall-fields', 'recall-discipline'
    ],
    'Communication & Voice': [
        'communication-patterns', 'question-style', 'language-precision',
        'anti-psychogenic-behavior', 'voice'
    ],
    'Handoff Workflow': [
        'handoff-pattern', 'handoff-discipline', 'self_improvement_handoffs'
    ],
    'Development & Technical': [
        'skill-workflow', 'python-path-setup', 'heredoc-for-multiline',
        'token-efficiency', 'token_conservation', 'error-handling',
        'batch-processing-drift', 'cache-testing-lesson'
    ],
    'Environment & Infrastructure': [
        # v3.8.0 (#265): Removed stale muninn-env-loading (now handled by auto-credential
        # loading in turso.py #263). Consolidated python-remembering-setup into env-file-handling.
        'env-file-handling', 'python-remembering-setup', 'austegard-com-hosting'
    ],
    'Commands & Shortcuts': [
        'fly-command', 'rem-command'
    ],
    'Therapy & Self-Improvement': [
        'therapy'
    ]
}


def _load_ops_topics() -> dict:
    """Load OPS_TOPICS from config, with fallback to defaults.

    Returns:
        Dict mapping topic names to lists of ops keys.

    The config entry 'ops-topics' should be a JSON object where:
    - Keys are topic names (e.g., "Core Boot & Behavior")
    - Values are lists of ops keys (e.g., ["boot-behavior", "dev-workflow"])

    Example config value:
        {"Core Boot & Behavior": ["boot-behavior"], "Memory Operations": ["remembering-api"]}

    If config is missing or invalid, returns _DEFAULT_OPS_TOPICS.
    """
    try:
        from .config import config_get
        raw = config_get('ops-topics')
        if raw:
            topics = json.loads(raw)
            if isinstance(topics, dict):
                # Validate structure: all values should be lists
                for key, value in topics.items():
                    if not isinstance(value, list):
                        raise ValueError(f"Topic '{key}' value must be a list")
                return topics
    except Exception:
        pass  # Fall back to defaults on any error
    return _DEFAULT_OPS_TOPICS.copy()


def _build_key_to_topic_map(ops_topics: dict) -> dict:
    """Build reverse lookup from ops key to topic name.

    Args:
        ops_topics: Dict from _load_ops_topics()

    Returns:
        Dict mapping ops key -> topic name
    """
    key_to_topic = {}
    for topic, keys in ops_topics.items():
        for key in keys:
            key_to_topic[key] = topic
    return key_to_topic


# Module-level cache for loaded topics (refreshed each boot)
OPS_TOPICS = None
_OPS_KEY_TO_TOPIC = None


def _ensure_ops_topics_loaded():
    """Ensure OPS_TOPICS is loaded (lazy initialization)."""
    global OPS_TOPICS, _OPS_KEY_TO_TOPIC
    if OPS_TOPICS is None:
        OPS_TOPICS = _load_ops_topics()
        _OPS_KEY_TO_TOPIC = _build_key_to_topic_map(OPS_TOPICS)


def classify_ops_key(key: str) -> str | None:
    """Classify an ops key into its topic category.

    Args:
        key: The ops config key (e.g., 'boot-behavior', 'voice')

    Returns:
        Topic name if classified, None if uncategorized.
        Uncategorized keys appear under 'Other' in boot output.

    Note:
        Topics are loaded from config('ops-topics') or use defaults.
        To add a key to a topic, update the ops-topics config entry.
    """
    _ensure_ops_topics_loaded()
    return _OPS_KEY_TO_TOPIC.get(key)


# --- GitHub Access Detection ---

def detect_github_access() -> dict:
    """Detect available GitHub access mechanisms.

    Checks for:
    - gh CLI availability and authentication status
    - GITHUB_TOKEN environment variable
    - GH_TOKEN environment variable (alternative)

    Returns:
        Dict with:
        - 'available': bool - whether any GitHub access is configured
        - 'methods': list - available access methods
        - 'recommended': str - recommended method to use
        - 'gh_cli': dict|None - gh CLI details if available
        - 'api_token': bool - whether API token is available
    """
    result = {
        'available': False,
        'methods': [],
        'recommended': None,
        'gh_cli': None,
        'api_token': False
    }

    # Check for gh CLI
    gh_path = shutil.which('gh')
    if gh_path:
        gh_info = {'path': gh_path, 'authenticated': False, 'user': None}

        # Check authentication status
        try:
            auth_check = subprocess.run(
                ['gh', 'auth', 'status'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if auth_check.returncode == 0:
                gh_info['authenticated'] = True
                # Try to extract username
                try:
                    user_check = subprocess.run(
                        ['gh', 'api', 'user', '--jq', '.login'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if user_check.returncode == 0:
                        gh_info['user'] = user_check.stdout.strip()
                except Exception:
                    pass  # Username extraction is optional
        except Exception:
            pass  # Auth check failed, gh exists but not authenticated

        result['gh_cli'] = gh_info
        if gh_info['authenticated']:
            result['methods'].append('gh-cli')

    # Check for API token
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if token:
        result['api_token'] = True
        result['methods'].append('api-token')

    # Determine availability and recommendation
    result['available'] = len(result['methods']) > 0

    if result['available']:
        # Prefer gh CLI when authenticated (more capable)
        if 'gh-cli' in result['methods']:
            result['recommended'] = 'gh-cli'
        else:
            result['recommended'] = 'api-token'

    return result


def github_api(endpoint: str, *, method: str = "GET", body: dict = None,
               accept: str = "application/vnd.github+json") -> dict:
    """Unified GitHub API interface that works across environments (#240).

    Automatically selects the best available access method:
    - gh CLI (preferred when authenticated)
    - Direct HTTP via GITHUB_TOKEN/GH_TOKEN

    Args:
        endpoint: GitHub API path (e.g., 'repos/owner/repo/issues')
                  Can be a full URL or relative path.
        method: HTTP method (GET, POST, PUT, PATCH, DELETE)
        body: Optional request body dict (for POST/PUT/PATCH)
        accept: Accept header value

    Returns:
        Dict with parsed JSON response

    Raises:
        RuntimeError: If no GitHub access is configured or request fails

    Example:
        >>> from remembering import github_api
        >>> issues = github_api('repos/oaustegard/claude-skills/issues')
        >>> pr = github_api('repos/owner/repo/pulls', method='POST',
        ...                 body={'title': 'Fix', 'head': 'fix-branch', 'base': 'main'})
    """
    import urllib.request
    import urllib.error

    access = detect_github_access()
    if not access['available']:
        raise RuntimeError(
            "No GitHub access configured. Set GITHUB_TOKEN or authenticate gh CLI."
        )

    # Normalize endpoint - strip leading slash and api prefix
    endpoint = endpoint.lstrip('/')
    if endpoint.startswith('https://api.github.com/'):
        endpoint = endpoint[len('https://api.github.com/'):]

    # Try gh CLI first (more capable, handles auth automatically)
    if access['recommended'] == 'gh-cli':
        try:
            cmd = ['gh', 'api', endpoint, '--method', method]
            if body:
                for k, v in body.items():
                    cmd.extend(['-f', f'{k}={v}' if isinstance(v, str) else '-F', f'{k}={v}'])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return json.loads(result.stdout) if result.stdout.strip() else {}
            # Fall through to HTTP on gh CLI failure
        except Exception:
            pass  # Fall through to HTTP

    # Direct HTTP with token
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not token:
        raise RuntimeError("GitHub API token not available and gh CLI failed.")

    url = f"https://api.github.com/{endpoint}"
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': accept,
        'User-Agent': 'muninn-memory-system',
    }

    data = json.dumps(body).encode('utf-8') if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    if data:
        req.add_header('Content-Type', 'application/json')

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            response_data = resp.read().decode('utf-8')
            return json.loads(response_data) if response_data.strip() else {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(f"GitHub API error {e.code}: {error_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"GitHub API connection error: {e}") from e


def group_ops_by_topic(ops_entries: list) -> tuple[dict, list]:
    """Group ops entries by topic for organized output.

    v3.6.0: Entries within each topic are sorted by priority (descending),
    so critical entries appear first. Entries with equal priority are
    sorted alphabetically by key.

    Args:
        ops_entries: List of ops config dicts with 'key' and optional 'priority' fields

    Returns:
        Tuple of (ops_by_topic dict, uncategorized list)
        - ops_by_topic: {topic_name: [entries...]} in OPS_TOPICS order, sorted by priority
        - uncategorized: entries with keys not in any topic, sorted by priority
    """
    _ensure_ops_topics_loaded()
    ops_by_topic = {}
    uncategorized = []

    for o in ops_entries:
        key = o['key']
        topic = classify_ops_key(key)
        if topic:
            if topic not in ops_by_topic:
                ops_by_topic[topic] = []
            ops_by_topic[topic].append(o)
        else:
            uncategorized.append(o)

    # Sort entries within each topic by priority (descending), then by key (ascending)
    # Priority can be int or string from Turso, so convert to int for comparison
    def sort_key(entry):
        priority = entry.get('priority', 0)
        # Handle string/None types from Turso
        if priority is None:
            priority = 0
        elif isinstance(priority, str):
            try:
                priority = int(priority)
            except ValueError:
                priority = 0
        return (-priority, entry['key'])  # Negative for descending priority

    for topic in ops_by_topic:
        ops_by_topic[topic].sort(key=sort_key)

    uncategorized.sort(key=sort_key)

    return ops_by_topic, uncategorized


def profile() -> list:
    """Load profile config for conversation start."""
    return config_list("profile")


def ops(include_reference: bool = False) -> list:
    """Load operational config for conversation start.

    Args:
        include_reference: If True, include reference-only entries.
                          If False (default), only return entries marked for boot loading.

    Returns:
        List of config dicts with ops entries
    """
    entries = config_list("ops")

    # Filter by boot_load unless include_reference=True
    # Note: Turso returns boot_load as string ('0' or '1')
    if not include_reference:
        entries = [e for e in entries if e.get('boot_load', 1) in (1, '1')]

    return entries


def _warm_cache():
    """Background cache population - fetches all memories from Turso.

    v2.0.0: Uses priority instead of importance.
    v2.0.1: Sets state._cache_warmed flag when complete to fix race condition.
    """
    try:
        results = _exec_batch([
            """SELECT * FROM memories
               WHERE deleted_at IS NULL
               ORDER BY t DESC LIMIT 500"""
        ])
        full_memories = results[0]

        if _cache_available():
            memory_index = []
            for m in full_memories:
                memory_index.append({
                    'id': m.get('id'),
                    'type': m.get('type'),
                    't': m.get('t'),
                    'tags': m.get('tags'),
                    'summary_preview': m.get('summary', '')[:100],
                    'confidence': m.get('confidence'),
                    'priority': m.get('priority', 0),
                    'session_id': m.get('session_id'),  # v3.8.0: cache session_id (#237)
                })
            _cache_populate_index(memory_index)
            _cache_populate_full(full_memories)
            state._cache_warmed = True  # Mark as complete
    except Exception:
        pass  # Cache warming is best-effort


def _load_repo_defaults() -> tuple[list, list]:
    """Load profile and ops defaults from version-controlled JSON files (#239).

    Used as a last-resort fallback when both Turso and cache are unavailable
    (e.g., fresh install with no prior sessions, network outage).

    Returns:
        Tuple of (profile_data, ops_data) as lists of config dicts
    """
    defaults_dir = Path(__file__).parent / "defaults"
    profile_data = []
    ops_data = []

    # Load profile defaults
    profile_path = defaults_dir / "profile.json"
    if profile_path.exists():
        try:
            raw = json.loads(profile_path.read_text())
            for key, entry in raw.items():
                profile_data.append({
                    'key': key,
                    'value': entry.get('value', ''),
                    'category': 'profile',
                    'boot_load': 1,
                })
        except Exception:
            pass

    # Load ops defaults
    ops_path = defaults_dir / "ops.json"
    if ops_path.exists():
        try:
            raw = json.loads(ops_path.read_text())
            for key, entry in raw.items():
                ops_data.append({
                    'key': key,
                    'value': entry.get('value', ''),
                    'category': 'ops',
                    'boot_load': entry.get('boot_load', 1),
                })
        except Exception:
            pass

    return profile_data, ops_data


def boot() -> str:
    """Boot sequence: load profile + ops, start async cache population.

    Returns formatted string with complete profile and ops values.
    Spawns background thread to populate memory cache for fast recall().

    Filters reference-only ops from output to reduce token usage at boot.
    Reference material (API docs, container limits, etc.) can be queried via config_get().

    Organizes ops by topic for better cognitive navigation.

    Resilience: Retries transient errors (SSL, 503, 429) with exponential backoff.
    Falls back to cached config if remote fetch fails after retries.
    """
    # Initialize cache
    _init_local_cache()

    # Refresh OPS_TOPICS from config (v3.6.0: dynamic loading)
    global OPS_TOPICS, _OPS_KEY_TO_TOPIC
    OPS_TOPICS = _load_ops_topics()
    _OPS_KEY_TO_TOPIC = _build_key_to_topic_map(OPS_TOPICS)

    # Fetch profile + ops with retry logic for transient errors
    try:
        from .turso import _retry_with_backoff

        def _fetch_config():
            return _exec_batch([
                "SELECT * FROM config WHERE category = 'profile' ORDER BY key",
                "SELECT * FROM config WHERE category = 'ops' ORDER BY key",
            ])

        results = _retry_with_backoff(_fetch_config, max_retries=3, base_delay=1.0)
        profile_data = results[0]
        ops_data = results[1]

        # Cache config immediately (cache ALL config, even reference material)
        if _cache_available():
            _cache_config(profile_data + ops_data)

    except Exception as e:
        # Fallback to PREVIOUS SESSION's cached config if remote fetch fails
        # Note: The cache file persists on disk between sessions. This fallback
        # only works if a prior session successfully populated config_cache.
        # On a fresh install with no prior cache, this will fail gracefully.
        if _cache_available():
            # Check if previous session cached any config
            cached_count = state._cache_conn.execute(
                "SELECT COUNT(*) FROM config_cache"
            ).fetchone()[0]

            if cached_count > 0:
                print(f"Warning: Remote config fetch failed, using previous session's cache: {e}")
                profile_data = state._cache_conn.execute(
                    "SELECT * FROM config_cache WHERE category = 'profile' ORDER BY key"
                ).fetchall()
                profile_data = [dict(row) for row in profile_data]

                ops_data = state._cache_conn.execute(
                    "SELECT * FROM config_cache WHERE category = 'ops' ORDER BY key"
                ).fetchall()
                ops_data = [dict(row) for row in ops_data]
            else:
                # Cache exists but is empty (fresh session) - try repo defaults (#239)
                profile_data, ops_data = _load_repo_defaults()
                if profile_data or ops_data:
                    print(f"Warning: Remote config fetch failed, using repo defaults: {e}")
                else:
                    return f"ERROR: Unable to load config (remote failed: {e}, cache empty, no defaults)"
        else:
            # No cache file at all - try repo defaults (#239)
            profile_data, ops_data = _load_repo_defaults()
            if profile_data or ops_data:
                print(f"Warning: Remote config fetch failed, using repo defaults: {e}")
            else:
                return f"ERROR: Unable to load config (remote failed: {e}, no cache or defaults available)"

    # Start async cache warming
    threading.Thread(target=_warm_cache, daemon=True).start()

    # Detect GitHub access methods
    github_access = detect_github_access()

    # Install utility code memories to disk
    installed_utils = install_utilities()

    # Filter ops by boot_load flag (progressive disclosure)
    # Reference-only entries (boot_load=0) excluded from boot output but accessible via config_get()
    # Note: Turso returns boot_load as string ('0' or '1')
    core_ops = [o for o in ops_data if o.get('boot_load', 1) in (1, '1')]
    reference_ops = [o for o in ops_data if o.get('boot_load', 1) in (0, '0')]

    # Group ops by topic and sort by priority within each topic (v3.6.0)
    ops_by_topic, uncategorized = group_ops_by_topic(core_ops)

    # Format output with markdown headings
    return _format_boot_output(profile_data, ops_by_topic, uncategorized, reference_ops, installed_utils, github_access)


def _format_entry(entry: dict) -> str:
    """Format a single config entry with markdown heading.

    Args:
        entry: Config dict with 'key' and 'value' fields

    Returns:
        Formatted string with key as heading and value as content
    """
    return f"### {entry['key']}\n{entry['value']}"


def _format_boot_output(profile_data: list, ops_by_topic: dict,
                        uncategorized: list, reference_ops: list,
                        installed_utils: dict, github_access: dict = None) -> str:
    """Format boot output with organized sections.

    v3.6.0: Entries within each topic are pre-sorted by priority (descending)
    by group_ops_by_topic(), so critical entries appear first.

    Args:
        profile_data: List of profile config entries
        ops_by_topic: Dict of {topic: [entries]} from group_ops_by_topic(), sorted by priority
        uncategorized: List of ops entries not in any topic, sorted by priority
        reference_ops: List of reference-only ops (boot_load=0)
        installed_utils: Dict of {name: path} from install_utilities()
        github_access: Dict from detect_github_access() with GitHub capabilities

    Returns:
        Formatted boot output string with markdown headings
    """
    output = []

    # Profile section
    if profile_data:
        output.append("# PROFILE")
        output.extend(_format_entry(p) for p in profile_data)

    # Ops section
    if ops_by_topic or uncategorized:
        output.append("\n# OPS")

        # Output ops by topic in defined order
        for topic in OPS_TOPICS.keys():
            if topic in ops_by_topic:
                output.append(f"\n## {topic}")
                output.extend(_format_entry(o) for o in ops_by_topic[topic])

        # Output uncategorized ops last (already sorted by priority in group_ops_by_topic)
        if uncategorized:
            output.append("\n## Other")
            output.extend(_format_entry(o) for o in uncategorized)

        # Reference index: show what's available but not loaded
        if reference_ops:
            output.append("\n## Reference Entries (load via config_get)")
            ref_keys = sorted([o['key'] for o in reference_ops])
            output.append(", ".join(ref_keys))

    # Capabilities section (GitHub and utilities)
    output.append("\n# CAPABILITIES")

    # GitHub access section
    if github_access:
        output.append("\n## GitHub Access")
        if github_access.get('available'):
            methods = github_access.get('methods', [])
            recommended = github_access.get('recommended')
            output.append(f"  Status: Available")
            output.append(f"  Methods: {', '.join(methods)}")
            output.append(f"  Recommended: {recommended}")

            # Add gh CLI details if authenticated
            gh_cli = github_access.get('gh_cli')
            if gh_cli and gh_cli.get('authenticated'):
                user = gh_cli.get('user')
                if user:
                    output.append(f"  gh user: {user}")
                output.append("  Usage: gh pr view, gh issue list, gh api repos/...")
        else:
            output.append("  Status: Not configured")
            output.append("  Note: Set GITHUB_TOKEN or authenticate gh CLI")

    # Utilities section
    if installed_utils:
        output.append(f"\n## Utilities ({len(installed_utils)})")
        for name in sorted(installed_utils.keys()):
            output.append(f"  from muninn_utils import {name}")
    else:
        output.append("\n## Utilities")
        output.append("  None installed (tag memories with 'utility-code' to add)")

    return '\n'.join(output)


def journal(topics: list = None, user_stated: str = None, my_intent: str = None) -> str:
    """Record a journal entry. Returns the entry key."""
    now = datetime.now(UTC)
    # Use microsecond precision to prevent key collisions from rapid successive calls
    key = f"j-{now.strftime('%Y%m%d-%H%M%S%f')}"
    entry = {
        "t": now.isoformat().replace("+00:00", "Z"),
        "topics": topics or [],
        "user_stated": user_stated,
        "my_intent": my_intent
    }
    # Remove None values for cleaner storage
    entry = {k: v for k, v in entry.items() if v is not None}
    config_set(key, json.dumps(entry), "journal")
    return key


def journal_recent(n: int = 10) -> list:
    """Get recent journal entries for boot context. Returns list of parsed entries."""
    entries = config_list("journal")
    # Sort by key (timestamp-based) descending, take last n
    entries.sort(key=lambda x: x["key"], reverse=True)
    result = []
    for e in entries[:n]:
        try:
            parsed = json.loads(e["value"])
            parsed["_key"] = e["key"]
            result.append(parsed)
        except json.JSONDecodeError:
            continue
    return result


def journal_prune(keep: int = 40) -> int:
    """Prune old journal entries, keeping the most recent `keep` entries. Returns count deleted."""
    entries = config_list("journal")
    if len(entries) <= keep:
        return 0
    entries.sort(key=lambda x: x["key"], reverse=True)
    to_delete = entries[keep:]
    for e in to_delete:
        config_delete(e["key"])
    return len(to_delete)


# --- Therapy session helpers ---

def therapy_scope() -> tuple[str | None, list]:
    """Get cutoff timestamp and unprocessed memories for therapy session.

    Returns:
        Tuple of (cutoff_timestamp, memories_list)
        - cutoff_timestamp: Latest therapy session timestamp, or None if no sessions exist
        - memories_list: Memories since last therapy session (or all if no sessions)
    """
    # v0.12.1: Use strict=True to get newest session by timestamp, not by relevance ranking
    sessions = recall(type="experience", tags=["therapy"], n=1, strict=True)
    cutoff = sessions[0]['t'] if sessions else None
    memories = recall_since(cutoff, n=100) if cutoff else recall(n=100)
    return cutoff, memories


def therapy_session_count() -> int:
    """Count existing therapy sessions.

    Returns:
        Number of therapy session memories found
    """
    return len(recall(search="Therapy Session", type="experience", tags=["therapy"], n=100))


def decisions_recent(n: int = 10, conf: float = 0.7) -> list:
    """Return recent decisions above confidence threshold for boot loading.

    Args:
        n: Maximum number of decisions to return (default 10)
        conf: Minimum confidence threshold (default 0.7)

    Returns:
        List of decision memories sorted by timestamp (newest first)
    """
    return recall(type="decision", conf=conf, n=n, strict=True)


# --- Analysis helpers ---

def group_by_type(memories: list) -> dict:
    """Group memories by type.

    Args:
        memories: List of memory dicts from recall()

    Returns:
        Dict mapping type -> list of memories: {type: [memories]}
    """
    by_type = {}
    for m in memories:
        t = m.get('type', 'unknown')
        by_type.setdefault(t, []).append(m)
    return by_type


def group_by_tag(memories: list) -> dict:
    """Group memories by tags.

    Args:
        memories: List of memory dicts from recall()

    Returns:
        Dict mapping tag -> list of memories: {tag: [memories]}
        Note: A memory with multiple tags will appear under each tag
    """
    by_tag = {}
    for m in memories:
        tags = json.loads(m.get('tags', '[]')) if isinstance(m.get('tags'), str) else m.get('tags', [])
        for tag in tags:
            by_tag.setdefault(tag, []).append(m)
    return by_tag


# --- Export/Import for portability ---

def muninn_export() -> dict:
    """Export all Muninn state as portable JSON.

    Returns:
        Dict with version, timestamp, config, and memories
    """
    return {
        "version": "1.0",
        "exported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "config": config_list(),
        "memories": _exec("SELECT * FROM memories WHERE deleted_at IS NULL")
    }



# --- Session Continuity (v4.3.0, #231) ---

def session_save(summary: str = None, context: dict = None) -> str:
    """Save a session checkpoint for later resumption.

    Creates a memory capturing the current session state. The checkpoint
    can be resumed later with session_resume() to restore context.

    Args:
        summary: Optional summary of session progress. If None, a default
            summary is generated with timestamp and session ID.
        context: Optional dict of arbitrary context data to persist
            (e.g., current task, working files, decisions made).

    Returns:
        Memory ID of the checkpoint.

    Example:
        >>> session_save("Implementing FTS5 search", context={"files": ["cache.py"]})
        >>> # Later, in a new session:
        >>> checkpoint = session_resume()

    v4.3.0: Added as part of session continuity system (#231).
    """
    import json as _json
    sid = get_session_id()
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    if summary is None:
        summary = f"Session checkpoint at {now}"

    # Build checkpoint content
    checkpoint_data = {
        "session_id": sid,
        "timestamp": now,
        "summary": summary,
    }
    if context:
        checkpoint_data["context"] = context

    content = f"[Session Checkpoint] {summary}\n\nSession: {sid}\nContext: {_json.dumps(context or {})}"

    return remember(
        content,
        "experience",
        tags=["session-checkpoint", sid],
        priority=1,
        session_id=sid,
        sync=True
    )


def session_resume(session_id: str = None) -> dict:
    """Resume from the most recent session checkpoint.

    Loads the latest checkpoint for the given session (or the current session)
    and returns its content for context restoration.

    Args:
        session_id: Session ID to resume. If None, uses the current session ID.

    Returns:
        Dict with checkpoint data:
        - 'checkpoint_id': Memory ID of the checkpoint
        - 'summary': Checkpoint summary text
        - 'session_id': Session that created the checkpoint
        - 'timestamp': When the checkpoint was created
        - 'context': Any stored context data (dict or None)
        - 'recent_memories': List of recent memories from that session

    Returns empty dict if no checkpoint found.

    Example:
        >>> cp = session_resume("previous-session-id")
        >>> print(cp['summary'])
        >>> print(cp['context'])

    v4.3.0: Added as part of session continuity system (#231).
    """
    import json as _json
    sid = session_id or get_session_id()

    # Find the latest checkpoint for this session
    checkpoints = recall(
        tags=["session-checkpoint", sid],
        tag_mode="all",
        n=1,
        strict=True,
        raw=True
    )

    if not checkpoints:
        return {}

    checkpoint = checkpoints[0]

    # Parse context from checkpoint content
    context = None
    content = checkpoint.get('summary', '')
    if 'Context: ' in content:
        try:
            context_str = content.split('Context: ', 1)[1]
            context = _json.loads(context_str)
        except (json.JSONDecodeError, IndexError):
            pass

    # Get recent memories from that session for additional context
    recent = recall(
        session_id=sid,
        n=20,
        strict=True,
        raw=True
    )

    return {
        'checkpoint_id': checkpoint.get('id'),
        'summary': checkpoint.get('summary', ''),
        'session_id': sid,
        'timestamp': checkpoint.get('t'),
        'context': context,
        'recent_memories': recent
    }


def sessions(n: int = 10, *, include_counts: bool = False) -> list:
    """List available session checkpoints.

    Returns a list of sessions that have checkpoints, ordered by most recent.

    Args:
        n: Maximum number of sessions to return (default 10)
        include_counts: If True, include memory count per session (slower)

    Returns:
        List of dicts, each with:
        - 'session_id': The session identifier
        - 'latest_checkpoint': Timestamp of the most recent checkpoint
        - 'summary': Summary from the latest checkpoint
        - 'checkpoint_count': Number of checkpoints for this session
        - 'memory_count': Total memories in this session (only if include_counts=True)

    Example:
        >>> for s in sessions():
        ...     print(f"{s['session_id']}: {s['summary'][:60]}")

    v4.3.0: Added as part of session continuity system (#231).
    """
    # Get all session checkpoints
    all_checkpoints = recall(
        tags=["session-checkpoint"],
        n=200,
        strict=True,
        raw=True
    )

    if not all_checkpoints:
        return []

    # Group by session_id, keeping the latest per session
    session_map = {}
    for cp in all_checkpoints:
        sid = cp.get('session_id', 'unknown')
        if sid not in session_map:
            session_map[sid] = {
                'session_id': sid,
                'latest_checkpoint': cp.get('t'),
                'summary': cp.get('summary', ''),
                'checkpoint_count': 1,
            }
        else:
            session_map[sid]['checkpoint_count'] += 1
            # Keep the latest
            if cp.get('t', '') > session_map[sid]['latest_checkpoint']:
                session_map[sid]['latest_checkpoint'] = cp.get('t')
                session_map[sid]['summary'] = cp.get('summary', '')

    # Sort by latest checkpoint time (newest first), take top n
    result = sorted(session_map.values(), key=lambda s: s['latest_checkpoint'], reverse=True)[:n]

    # Optionally include memory counts per session
    if include_counts:
        for s in result:
            sid = s['session_id']
            memories = recall(session_id=sid, n=1000, strict=True, raw=True)
            s['memory_count'] = len(memories)

    return result


def handoff_pending() -> list:
    """Get pending handoff instructions (not yet completed).

    Returns handoffs tagged with BOTH 'handoff' AND 'pending', excluding superseded ones.
    Use handoff_complete() to mark a handoff as done.

    Uses strict=True to bypass FTS5 search and use direct SQL tag matching with
    timestamp ordering for deterministic results.

    Returns:
        List of pending handoff memories, most recent first (by timestamp, not relevance)
    """
    return recall(tags=["handoff", "pending"], tag_mode="all", n=50, strict=True)


def handoff_complete(handoff_id: str, completion_notes: str, version: str = None) -> str:
    """Mark a handoff as completed by superseding it with completion record.

    The original handoff will be excluded from future handoff_pending() queries.
    Completion record is tagged with version for historical tracking.

    Args:
        handoff_id: ID of the handoff to mark complete
        completion_notes: Summary of what was done
        version: Optional version number (e.g., "0.5.0")

    Returns:
        ID of the completion record

    Example:
        handoff_id = handoff_pending()[0]['id']
        handoff_complete(handoff_id, "Implemented boot() function", "0.5.0")
    """
    # Read VERSION file if version not provided
    if version is None:
        try:
            from pathlib import Path
            version_file = Path(__file__).parent.parent / "VERSION"
            version = version_file.read_text().strip()
        except Exception:
            version = "unknown"

    # Supersede the handoff with completion record
    completion_tags = ["handoff-completed", f"v{version}"]
    return supersede(handoff_id, completion_notes, "world", tags=completion_tags)


def muninn_import(data: dict, *, merge: bool = False) -> dict:
    """Import Muninn state from exported JSON.

    Args:
        data: Dict from muninn_export()
        merge: If True, add to existing data. If False, replace all (destructive!)

    Returns:
        Stats dict with counts of imported items

    Raises:
        ValueError: If data format invalid
    """
    if not isinstance(data, dict) or "version" not in data:
        raise ValueError("Invalid import data: missing version field")

    stats = {"config_count": 0, "memory_count": 0, "errors": []}

    if not merge:
        # Destructive: clear all existing data
        _exec("DELETE FROM config")
        _exec("DELETE FROM memories")

    # Import config entries
    for c in data.get("config", []):
        try:
            config_set(
                c["key"],
                c["value"],
                c["category"],
                char_limit=c.get("char_limit"),
                read_only=bool(c.get("read_only", False))
            )
            stats["config_count"] += 1
        except Exception as e:
            stats["errors"].append(f"Config {c.get('key')}: {e}")

    # Import memories (regenerate IDs to avoid conflicts in merge mode)
    for m in data.get("memories", []):
        try:
            # Parse JSON fields
            tags = json.loads(m.get("tags", "[]")) if isinstance(m.get("tags"), str) else m.get("tags", [])
            entities = json.loads(m.get("entities", "[]")) if isinstance(m.get("entities"), str) else m.get("entities", [])
            refs = json.loads(m.get("refs", "[]")) if isinstance(m.get("refs"), str) else m.get("refs", [])

            # v0.13.0: Embeddings no longer supported
            remember(
                m["summary"],
                m["type"],
                tags=tags,
                conf=m.get("confidence"),
                entities=entities,
                refs=refs
            )
            stats["memory_count"] += 1
        except Exception as e:
            stats["errors"].append(f"Memory {m.get('id', 'unknown')}: {e}")

    return stats
