import io
import os
import re
import sys
import tarfile
import urllib.request

UTIL_DIR = os.environ.get("MUNINN_UTIL_DIR", os.path.join(os.path.expanduser("~"), "muninn_utils"))
CODE_START = "<" + "<" + "<PYTHON>" + ">" + ">"
CODE_END = "<" + "<" + "<END>" + ">" + ">"

# muninn_utils source-of-truth has moved from Turso `utility-code` memories
# to files in oaustegard/muninn-utilities (public). See memory `0d63ed4f`.
MUNINN_UTILS_REPO = os.environ.get("MUNINN_UTILS_REPO", "oaustegard/muninn-utilities")
MUNINN_UTILS_BRANCH = os.environ.get("MUNINN_UTILS_BRANCH", "main")
MUNINN_UTILS_SUBDIR = "muninn_utils"

# Valid utility names: alphanumeric, underscore, hyphen only
_VALID_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]*$')

# @lat: [[infrastructure#Utility Materialization]]
def install_utilities() -> dict:
    """
    Materialize all utility-code memories to disk.
    Called by boot() after cache refresh.

    Returns:
        Dict mapping utility names to {"path": file_path, "use_when": str|None}
    """
    from .memory import recall

    os.makedirs(UTIL_DIR, exist_ok=True)
    init_path = os.path.join(UTIL_DIR, "__init__.py")
    if not os.path.exists(init_path):
        open(init_path, 'w').close()

    parent = os.path.dirname(UTIL_DIR)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    results = recall(tags=["utility-code"], n=50)
    installed = {}

    for mem in results:
        content = mem.get("summary", "")
        if not content.startswith("NAME:"):
            continue
        name = content.split("\n")[0].replace("NAME:", "").strip()

        # Sanitize name: reject path separators, traversal, and invalid chars
        if not _VALID_NAME_RE.match(name):
            continue
        name = os.path.basename(name)  # Belt-and-suspenders

        if CODE_START not in content:
            continue
        code = content.split(CODE_START, 1)[1].split(CODE_END, 1)[0].strip()

        # Parse USE WHEN: from header (between PURPOSE: and DEPS:)
        use_when = None
        for line in content.split("\n"):
            if line.startswith("USE WHEN:"):
                use_when = line.replace("USE WHEN:", "").strip()
                break

        file_path = os.path.join(UTIL_DIR, f"{name}.py")
        # Final check: resolved path must be within UTIL_DIR
        resolved = os.path.realpath(file_path)
        if not resolved.startswith(os.path.realpath(UTIL_DIR) + os.sep):
            continue
        with open(file_path, 'w') as f:
            f.write(code + "\n")
        installed[name] = {"path": file_path, "use_when": use_when}

    return installed


# @lat: [[infrastructure#Utility Materialization]]
def fetch_muninn_utils() -> dict:
    """
    Pull canonical muninn_utils/*.py from oaustegard/muninn-utilities over
    the Turso materialization. Source-of-truth has moved from `utility-code`
    memories to files in a dedicated public repo (per memory 0d63ed4f).

    Runs after install_utilities() so disk files override Turso copies for
    utilities already migrated. Non-migrated utilities continue to work via
    the Turso fallback that install_utilities() produces.

    Single tarball fetch from codeload.github.com — no auth required since
    the repo is public. Skips tests/ subdir; only top-level *.py land in
    UTIL_DIR.

    Returns:
        Dict with keys:
        - fetched: list[str] — names of .py files written
        - failed: list[str] — names that errored during write
    """
    result = {"fetched": [], "failed": []}

    os.makedirs(UTIL_DIR, exist_ok=True)
    init_path = os.path.join(UTIL_DIR, "__init__.py")
    if not os.path.exists(init_path):
        open(init_path, "w").close()

    parent = os.path.dirname(UTIL_DIR)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    url = f"https://codeload.github.com/{MUNINN_UTILS_REPO}/tar.gz/{MUNINN_UTILS_BRANCH}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            raw = resp.read()
    except Exception:
        return result

    util_realpath = os.path.realpath(UTIL_DIR) + os.sep

    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                # Tarball paths look like: <repo>-<sha>/muninn_utils/<name>.py
                # Skip nested dirs (tests/, etc.)
                parts = member.name.split("/")
                if len(parts) != 3 or parts[1] != MUNINN_UTILS_SUBDIR:
                    continue
                name = parts[2]
                if not name.endswith(".py"):
                    continue
                stem = name[:-3]
                # __init__.py is the one allowed exception to the name regex
                if stem != "__init__" and not _VALID_NAME_RE.match(stem):
                    continue

                file_path = os.path.join(UTIL_DIR, name)
                # Final guard: resolved path must be within UTIL_DIR
                resolved = os.path.realpath(file_path)
                if not resolved.startswith(util_realpath):
                    result["failed"].append(name)
                    continue

                try:
                    fileobj = tf.extractfile(member)
                    if fileobj is None:
                        result["failed"].append(name)
                        continue
                    content = fileobj.read().decode("utf-8")
                    with open(file_path, "w") as f:
                        f.write(content)
                    result["fetched"].append(name)
                except Exception:
                    result["failed"].append(name)
    except Exception:
        return result

    return result
