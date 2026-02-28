import os
import sys

UTIL_DIR = "/home/claude/muninn_utils"
CODE_START = "<" + "<" + "<PYTHON>" + ">" + ">"
CODE_END = "<" + "<" + "<END>" + ">" + ">"

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
        with open(file_path, 'w') as f:
            f.write(code + "\n")
        installed[name] = {"path": file_path, "use_when": use_when}

    return installed
