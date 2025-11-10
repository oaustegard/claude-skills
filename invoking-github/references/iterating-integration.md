# Iterating Skill Integration

Patterns for integrating invoking-github with the iterating skill to enable automatic DEVLOG persistence to GitHub.

## Overview

The iterating skill tracks development progress across sessions using DEVLOG.md. By integrating with invoking-github, we can automatically persist this log to a GitHub branch, enabling:

- **Cross-session continuity**: Resume work across different Claude environments
- **Version control**: Git history of all decisions and progress
- **Team collaboration**: Share development logs with team members
- **Backup**: Automatic backup of session progress

## Basic Integration Pattern

### Modified Update DEVLOG Function

```python
from pathlib import Path
from datetime import datetime

def update_devlog_with_github_sync(
    data: dict,
    repo: str,
    branch: str = "devlog",
    auto_sync: bool = True
):
    """
    Update DEVLOG.md locally and optionally sync to GitHub.

    Args:
        data: DEVLOG entry data (title, prev, now, work, etc.)
        repo: GitHub repository ("owner/name")
        branch: Target branch for DEVLOG
        auto_sync: Whether to automatically sync to GitHub
    """
    from iterating import update_devlog  # Your existing function

    # Update local DEVLOG
    update_devlog(data)

    # Optionally sync to GitHub
    if auto_sync:
        try:
            import sys
            sys.path.append('/home/user/claude-skills/invoking-github/scripts')
            from github_client import commit_file

            devlog_content = Path("DEVLOG.md").read_text()

            result = commit_file(
                repo=repo,
                path="DEVLOG.md",
                content=devlog_content,
                branch=branch,
                message=f"DEVLOG: {data['title']}",
                create_branch_from="main"
            )

            print(f"✓ DEVLOG synced to GitHub ({repo}:{branch}) - {result['commit_sha'][:7]}")
            return result

        except Exception as e:
            print(f"⚠ DEVLOG sync failed: {e}")
            print("  Local DEVLOG.md updated successfully")
            return None
```

### Usage

```python
# At end of session
data = {
    'title': 'Implemented authentication middleware',
    'prev': 'Designed auth flow',
    'now': 'Built JWT middleware',
    'work': {
        'added': ['src/auth/middleware.py'],
        'changed': ['src/app.py'],
        'fixed': ['Auth validation bug']
    },
    'decisions': [
        {
            'what': 'Use JWT tokens',
            'why': 'Stateless, scalable',
            'alt': 'Session cookies'
        }
    ],
    'next': ['Add token refresh', 'Test edge cases']
}

update_devlog_with_github_sync(
    data=data,
    repo="username/project-name",
    branch="devlog"
)
```

## Configuration-Based Pattern

For users who want to configure once and forget:

### Configuration via Project Knowledge

Create `GITHUB_DEVLOG_CONFIG` in Project Knowledge:

```json
{
  "repo": "username/project-name",
  "branch": "devlog",
  "auto_sync": true,
  "create_branch_from": "main"
}
```

### Configuration-Aware Function

```python
import json
from pathlib import Path

def get_devlog_config():
    """Load DEVLOG GitHub sync configuration"""
    config_path = Path("/mnt/project/GITHUB_DEVLOG_CONFIG")

    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
            return config
        except (json.JSONDecodeError, IOError):
            pass

    # Default config (no sync)
    return {"auto_sync": False}


def update_devlog_smart(data: dict):
    """
    Update DEVLOG with automatic GitHub sync based on configuration.
    """
    from iterating import update_devlog

    # Update local DEVLOG
    update_devlog(data)

    # Check if GitHub sync is configured
    config = get_devlog_config()

    if config.get("auto_sync"):
        try:
            import sys
            sys.path.append('/home/user/claude-skills/invoking-github/scripts')
            from github_client import commit_file

            devlog_content = Path("DEVLOG.md").read_text()

            result = commit_file(
                repo=config["repo"],
                path="DEVLOG.md",
                content=devlog_content,
                branch=config.get("branch", "devlog"),
                message=f"DEVLOG: {data['title']}",
                create_branch_from=config.get("create_branch_from", "main")
            )

            print(f"✓ DEVLOG synced to {config['repo']}:{config['branch']}")

        except Exception as e:
            print(f"⚠ DEVLOG sync failed: {e}")
```

## Session-Specific Branch Pattern

Avoid conflicts by using unique branch names per session:

```python
from datetime import datetime

def update_devlog_with_session_branch(data: dict, repo: str):
    """
    Update DEVLOG and sync to session-specific branch.
    """
    from iterating import update_devlog

    # Update local DEVLOG
    update_devlog(data)

    # Generate session-specific branch name
    session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"devlog-{session_id}"

    try:
        import sys
        sys.path.append('/home/user/claude-skills/invoking-github/scripts')
        from github_client import commit_file

        devlog_content = Path("DEVLOG.md").read_text()

        result = commit_file(
            repo=repo,
            path="DEVLOG.md",
            content=devlog_content,
            branch=branch_name,
            message=f"DEVLOG: {data['title']}",
            create_branch_from="main"
        )

        print(f"✓ DEVLOG synced to {repo}:{branch_name}")
        print(f"  Commit: {result['commit_sha'][:7]}")
        print(f"  To merge: Create PR from {branch_name} to main")

    except Exception as e:
        print(f"⚠ DEVLOG sync failed: {e}")
```

## Multi-File Session State Pattern

Persist entire session state (not just DEVLOG):

```python
def persist_session_state(
    repo: str,
    branch: str,
    files: dict[str, str],
    message: str
):
    """
    Persist multiple files representing session state.

    Args:
        repo: GitHub repository
        branch: Target branch
        files: Dict of {file_path: content}
        message: Commit message
    """
    try:
        import sys
        sys.path.append('/home/user/claude-skills/invoking-github/scripts')
        from github_client import commit_files

        # Convert dict to list format
        files_list = [
            {"path": path, "content": content}
            for path, content in files.items()
        ]

        result = commit_files(
            repo=repo,
            files=files_list,
            branch=branch,
            message=message,
            create_branch_from="main"
        )

        print(f"✓ Session state synced: {result['files_committed']} files")
        return result

    except Exception as e:
        print(f"⚠ State sync failed: {e}")
        return None


# Usage
session_files = {
    "DEVLOG.md": Path("DEVLOG.md").read_text(),
    "session_notes.md": "# Session Notes\n...",
    "current_progress.json": json.dumps(progress_data)
}

persist_session_state(
    repo="user/project",
    branch="session-state",
    files=session_files,
    message="Session checkpoint"
)
```

## Progressive Summarization Pattern

Maintain both detailed and summarized DEVLOGs:

```python
def update_devlog_with_summary(
    data: dict,
    repo: str,
    branch: str = "devlog"
):
    """
    Update DEVLOG and maintain a summary file.
    """
    from iterating import update_devlog

    # Update local DEVLOG
    update_devlog(data)

    # Generate or update summary
    summary = generate_devlog_summary()  # Your summarization logic

    try:
        import sys
        sys.path.append('/home/user/claude-skills/invoking-github/scripts')
        from github_client import commit_files

        devlog_content = Path("DEVLOG.md").read_text()

        files = [
            {"path": "DEVLOG.md", "content": devlog_content},
            {"path": "DEVLOG_SUMMARY.md", "content": summary}
        ]

        result = commit_files(
            repo=repo,
            files=files,
            branch=branch,
            message=f"DEVLOG: {data['title']} (with summary)",
            create_branch_from="main"
        )

        print(f"✓ DEVLOG and summary synced")

    except Exception as e:
        print(f"⚠ Sync failed: {e}")


def generate_devlog_summary():
    """
    Generate a summary of DEVLOG.md.
    Extract key decisions, milestones, open items.
    """
    devlog = Path("DEVLOG.md").read_text()

    # Simple summarization (you can enhance this)
    summary_parts = [
        "# DEVLOG Summary",
        "",
        "## Key Decisions",
        "<!-- Extract from DEVLOG -->",
        "",
        "## Open Items",
        "<!-- Extract from DEVLOG -->",
        "",
        "## Next Steps",
        "<!-- Extract from DEVLOG -->"
    ]

    return "\n".join(summary_parts)
```

## Cross-Environment Continuity

Resume work from any Claude environment by reading DEVLOG from GitHub:

```python
def resume_session_from_github(repo: str, branch: str = "devlog"):
    """
    Resume a session by reading DEVLOG from GitHub.
    """
    try:
        import sys
        sys.path.append('/home/user/claude-skills/invoking-github/scripts')
        from github_client import read_file

        devlog_content = read_file(
            repo=repo,
            path="DEVLOG.md",
            branch=branch
        )

        # Save to local working directory
        Path("DEVLOG.md").write_text(devlog_content)

        print(f"✓ Resumed session from {repo}:{branch}")
        print("\nRecent entries:")

        # Show last 20 lines
        recent = "\n".join(devlog_content.split("\n")[-20:])
        print(recent)

        return devlog_content

    except Exception as e:
        print(f"✗ Could not resume session: {e}")
        return None


# Usage at start of new session
print("Resuming previous session...")
resume_session_from_github("user/project", "devlog")
```

## Automatic PR Creation Pattern

At session end, automatically create PR with DEVLOG:

```python
def finalize_session_with_pr(
    data: dict,
    repo: str,
    session_branch: str,
    message: str = "Session progress"
):
    """
    Finalize session by syncing DEVLOG and creating PR.
    """
    from iterating import update_devlog

    # Update local DEVLOG
    update_devlog(data)

    try:
        import sys
        sys.path.append('/home/user/claude-skills/invoking-github/scripts')
        from github_client import commit_file, create_pull_request

        # Commit DEVLOG
        devlog_content = Path("DEVLOG.md").read_text()

        commit_result = commit_file(
            repo=repo,
            path="DEVLOG.md",
            content=devlog_content,
            branch=session_branch,
            message=message,
            create_branch_from="main"
        )

        print(f"✓ DEVLOG committed: {commit_result['commit_sha'][:7]}")

        # Create PR
        pr = create_pull_request(
            repo=repo,
            head=session_branch,
            base="main",
            title=f"Session: {data['title']}",
            body=f"## Session Summary\n\n{message}\n\n## DEVLOG\n\nSee DEVLOG.md for details."
        )

        print(f"✓ PR created: {pr['html_url']}")
        return pr

    except Exception as e:
        print(f"⚠ Finalization failed: {e}")
        return None
```

## Best Practices

### 1. Graceful Degradation

Always update local DEVLOG first, sync as bonus:

```python
# Good
update_devlog(data)  # Always succeeds
try:
    sync_to_github()  # Bonus feature
except:
    pass

# Bad
try:
    sync_to_github()  # If this fails, local DEVLOG not updated
    update_devlog(data)
except:
    pass
```

### 2. Informative Messages

Tell user what's happening:

```python
print("Updating DEVLOG...")
update_devlog(data)
print("✓ DEVLOG updated locally")

print("Syncing to GitHub...")
sync_to_github()
print("✓ Synced to GitHub")
```

### 3. Configuration Over Code

Use Project Knowledge for configuration:

```json
{
  "repo": "user/project",
  "branch": "devlog",
  "auto_sync": true
}
```

### 4. Session Identifiers

Use timestamps or UUIDs for unique branches:

```python
# Good
f"devlog-{datetime.now().isoformat()}"
f"devlog-{uuid.uuid4().hex[:8]}"

# Avoid
"devlog"  # Can conflict across sessions
```

## Troubleshooting

**DEVLOG syncs but shows conflicts**
→ Use session-specific branches

**Sync is slow**
→ Normal, GitHub API is network-dependent

**Sync fails silently**
→ Check error handling, print exceptions

**DEVLOG not resuming correctly**
→ Verify branch name, check GitHub token permissions

## Next Steps

- [SKILL.md](../SKILL.md) - Core skill documentation
- [credential-setup.md](credential-setup.md) - Token configuration
- [troubleshooting.md](troubleshooting.md) - Common issues
