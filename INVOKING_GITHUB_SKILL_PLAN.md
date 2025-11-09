# Invoking GitHub Skill - Implementation Plan

## Executive Summary

Create an `invoking-github` skill that enables Claude.ai web environment (and other Claude environments) to read from and write to GitHub repositories programmatically. This skill will:

1. **Enable web-based development** with GitHub as the persistent storage layer
2. **Augment the iterating skill** by auto-persisting DEVLOG.md to a GitHub branch
3. **Homogenize development workspace** across all Claude modes (Web, Desktop, CLI) using GitHub branches as the unified state store

## Vision: Unified Development Workspace

Currently, the iterating skill uses different storage strategies per environment:
- **Web**: DEVLOG.md in repository (requires manual commit/push)
- **Desktop**: Local DEVLOG.md (no cross-session persistence without manual sync)
- **CLI**: Project Knowledge documents (manual curation)

**Target state**: All environments use GitHub branches as the primary state store, enabling:
- Automatic persistence of DEVLOG.md
- Cross-environment continuity
- Git-based history and rollback
- Team collaboration on AI-assisted development

## Core Use Cases

### Use Case 1: Web-Based Repository Development
**Current limitation**: Claude.ai web can read repos via GitHub integration but cannot write back directly.

**Solution**: Skill enables Claude to:
1. Read files from any branch in connected repositories
2. Create/update files in a working branch
3. Commit changes with descriptive messages
4. Optionally create pull requests

**Workflow**:
```
User: "Update the README and commit to feature-branch"
Claude: [Uses invoking-github to read current README]
Claude: [Modifies content]
Claude: [Commits changes to feature-branch via GitHub API]
```

### Use Case 2: Automatic DEVLOG Persistence (Iterating Skill Integration)
**Current limitation**: DEVLOG.md must be manually copied to Project Knowledge or manually committed.

**Solution**: Skill auto-commits DEVLOG.md updates to a dedicated branch.

**Workflow**:
```python
# In iterating skill's update_devlog()
from invoking_github import commit_file

def update_devlog(data):
    # ... generate DEVLOG entry ...

    # Write locally
    with open("DEVLOG.md", 'a') as f:
        f.write(entry)

    # Auto-persist to GitHub (if configured)
    commit_file(
        repo="user/project",
        branch="devlog",
        file_path="DEVLOG.md",
        content=Path("DEVLOG.md").read_text(),
        message=f"DEVLOG: {data['title']}"
    )
```

### Use Case 3: Multi-Session State Management
**Problem**: Long-running tasks spanning multiple Claude sessions lose context.

**Solution**: Use a dedicated GitHub branch as session state store.

**Pattern**:
```
Session 1:
- Work on feature
- Update DEVLOG.md → auto-commit to devlog branch
- Store intermediate results → commit to working-state branch

Session 2:
- Read DEVLOG.md from devlog branch
- Restore context from working-state branch
- Continue work with full context
```

## Technical Architecture

### Credential Management (Three-Tier Fallback)

**Priority order**:

1. **Claude Web GitHub Integration (Primary)**
   - OAuth token automatically available when user connects GitHub to claude.ai
   - Detection: Check for environment variable `CLAUDE_GITHUB_TOKEN` or similar
   - Scope: Limited to repositories user has granted access to
   - **Advantage**: No manual configuration, most secure

2. **Project Knowledge: GITHUB_API_KEY (Secondary)**
   - User creates a Project Knowledge document named "GITHUB_API_KEY"
   - Content: Just the token (e.g., `ghp_abc123...`)
   - Scope: Classic or fine-grained PAT with repo permissions
   - **Use case**: When OAuth isn't available or needs broader scope

3. **API Credentials Skill (Tertiary)**
   - Leverages existing `api-credentials` skill pattern
   - Add `github_api_key` to config.json
   - **Use case**: Desktop/CLI environments or fallback

**Implementation**:
```python
def get_github_token() -> str:
    """
    Get GitHub token with three-tier fallback.

    Returns:
        str: GitHub API token

    Raises:
        ValueError: If no token found in any source
    """
    # 1. Check Claude Web GitHub Integration
    token = os.environ.get('CLAUDE_GITHUB_TOKEN')
    if token:
        return token.strip()

    # 2. Check Project Knowledge (Web environment)
    # In Web, Project Knowledge would be accessible via special path
    # This is environment-specific - may need adaptation
    pk_path = Path("/mnt/project-knowledge/GITHUB_API_KEY")
    if pk_path.exists():
        token = pk_path.read_text().strip()
        if token:
            return token

    # 3. Check api-credentials skill
    try:
        sys.path.append('/home/user/claude-skills/api-credentials/scripts')
        from credentials import get_github_api_key
        return get_github_api_key()
    except (ImportError, ValueError):
        pass

    # No token found
    raise ValueError(
        "No GitHub API token found!\n\n"
        "Configure using one of these methods:\n\n"
        "1. Claude Web: Connect GitHub at claude.ai/settings\n"
        "2. Project Knowledge: Create document named 'GITHUB_API_KEY' with your token\n"
        "3. api-credentials skill: Add github_api_key to config.json\n\n"
        "Generate token at: https://github.com/settings/tokens"
    )
```

### Core GitHub Operations

#### Operation 1: Read File
```python
def read_file(repo: str, path: str, branch: str = "main") -> str:
    """
    Read a file from GitHub repository.

    Args:
        repo: Repository in format "owner/name"
        path: File path within repository
        branch: Branch name (default: main)

    Returns:
        File content as string
    """
    pass
```

#### Operation 2: Write/Update File
```python
def write_file(
    repo: str,
    path: str,
    content: str,
    branch: str,
    message: str,
    create_branch_from: str | None = None
) -> dict:
    """
    Create or update a file in GitHub repository.

    Args:
        repo: Repository in format "owner/name"
        path: File path within repository
        content: New file content
        branch: Target branch
        message: Commit message
        create_branch_from: If branch doesn't exist, create from this branch

    Returns:
        dict with commit SHA, branch, and other metadata
    """
    pass
```

#### Operation 3: Batch Commit (Multiple Files)
```python
def commit_files(
    repo: str,
    files: list[dict],  # [{"path": "...", "content": "..."}]
    branch: str,
    message: str,
    create_branch_from: str | None = None
) -> dict:
    """
    Commit multiple files in a single commit.
    Uses Git Trees API for efficiency.

    Args:
        repo: Repository in format "owner/name"
        files: List of dicts with 'path' and 'content'
        branch: Target branch
        message: Commit message
        create_branch_from: If branch doesn't exist, create from this branch

    Returns:
        dict with commit SHA, branch, and files committed
    """
    pass
```

#### Operation 4: Create Pull Request
```python
def create_pull_request(
    repo: str,
    head: str,
    base: str,
    title: str,
    body: str = ""
) -> dict:
    """
    Create a pull request.

    Args:
        repo: Repository in format "owner/name"
        head: Source branch (where changes are)
        base: Target branch (where to merge)
        title: PR title
        body: PR description

    Returns:
        dict with PR number, URL, and metadata
    """
    pass
```

### GitHub API Implementation Details

**Library**: Use `requests` or `httpx` for HTTP calls (PyGitHub adds unnecessary weight)

**API Endpoints**:
- Read file: `GET /repos/{owner}/{repo}/contents/{path}?ref={branch}`
- Update file: `PUT /repos/{owner}/{repo}/contents/{path}` (requires file SHA for updates)
- Create tree: `POST /repos/{owner}/{repo}/git/trees`
- Create commit: `POST /repos/{owner}/{repo}/git/commits`
- Update ref: `PATCH /repos/{owner}/{repo}/git/refs/heads/{branch}`
- Create PR: `POST /repos/{owner}/{repo}/pulls`

**Error Handling**:
- 404: File/branch not found → Clear message about what's missing
- 401/403: Auth failure → Guide to credential configuration
- 409: Conflict → File changed since last read (provide resolution steps)
- 422: Validation error → Explain what's invalid
- Rate limits: Detect and provide wait time

### Integration with Iterating Skill

**Changes to iterating skill**:

Add optional GitHub sync to `web-environment.md`:

```python
# At top of file, detect if GitHub sync is enabled
def is_github_sync_enabled():
    """Check if GitHub auto-sync is configured"""
    try:
        from invoking_github import get_github_token, get_repo_config
        get_github_token()  # Will raise if not configured
        return True
    except:
        return False

# Modified update_devlog function
def update_devlog(data):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## {ts} | {data['title']}\n\n"

    # ... [existing entry generation] ...

    # Write to local file
    with open("DEVLOG.md", 'a') as f:
        f.write(entry)

    # Optionally sync to GitHub
    if is_github_sync_enabled():
        try:
            from invoking_github import commit_file, get_repo_config
            config = get_repo_config()

            commit_file(
                repo=config['repo'],
                path="DEVLOG.md",
                content=Path("DEVLOG.md").read_text(),
                branch=config.get('devlog_branch', 'devlog'),
                message=f"DEVLOG: {data['title']}"
            )
            print(f"✓ DEVLOG synced to GitHub ({config['repo']})")
        except Exception as e:
            print(f"⚠ DEVLOG sync failed: {e}")
            # Continue anyway - local DEVLOG.md still updated
```

**Configuration**:

User provides repo configuration via Project Knowledge document `GITHUB_REPO_CONFIG`:

```json
{
  "repo": "user/project-name",
  "devlog_branch": "devlog",
  "auto_sync": true
}
```

Or skill auto-detects from current repository context if running in Claude Code Web.

## Skill Structure

```
invoking-github/
├── SKILL.md                      # Main skill documentation
├── VERSION                       # Version tracking
├── scripts/
│   ├── github_client.py          # Core GitHub API client
│   ├── credentials.py            # Credential management with fallback chain
│   └── repo_config.py            # Repository configuration helpers
├── references/
│   ├── api-reference.md          # Detailed GitHub API documentation
│   ├── credential-setup.md       # Step-by-step credential configuration
│   ├── iterating-integration.md  # Integration with iterating skill
│   └── troubleshooting.md        # Common issues and solutions
└── assets/
    └── config.json.example       # Example configuration file
```

## SKILL.md Structure

```markdown
---
name: invoking-github
description: Enables GitHub repository operations (read/write/commit) for Claude.ai web and other environments. Use when users request GitHub commits, repository updates, DEVLOG persistence, or cross-session state management via GitHub branches.
---

# Invoking GitHub

Programmatically interact with GitHub repositories: read files, commit changes, create PRs, and persist state across sessions.

## When to Use This Skill

**Primary use cases:**
- Write back to repositories from Claude.ai web environment
- Auto-persist DEVLOG.md for iterating skill
- Manage state across sessions via GitHub branches
- Commit code/documentation updates programmatically
- Create pull requests from Claude

**Trigger patterns:**
- "Commit this to the repository"
- "Update the README on GitHub"
- "Save this to a feature branch"
- "Create a PR with these changes"
- "Persist DEVLOG to GitHub"

## Quick Start

### Single File Commit

```python
from invoking_github import commit_file

commit_file(
    repo="user/repo-name",
    path="README.md",
    content="# Updated README\n...",
    branch="main",
    message="Update README with new instructions"
)
```

### Auto-Sync DEVLOG (Iterating Integration)

Enable automatic DEVLOG persistence to GitHub:

1. Create Project Knowledge document: `GITHUB_REPO_CONFIG`
2. Content: `{"repo": "user/project", "devlog_branch": "devlog", "auto_sync": true}`
3. DEVLOG updates will auto-commit to the branch

[... rest of skill documentation ...]
```

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- [ ] Set up skill structure (init_skill.sh)
- [ ] Implement credential management with three-tier fallback
- [ ] Implement basic GitHub API client (read_file, write_file)
- [ ] Add comprehensive error handling
- [ ] Write unit tests for credential fallback
- [ ] Document credential setup in references/

### Phase 2: Advanced Operations (Week 1-2)
- [ ] Implement batch commit (multiple files)
- [ ] Implement create_pull_request
- [ ] Add branch creation/detection logic
- [ ] Implement file conflict detection and resolution
- [ ] Add rate limit handling with backoff
- [ ] Write integration tests with test repo

### Phase 3: Iterating Skill Integration (Week 2)
- [ ] Design iterating skill modification strategy
- [ ] Implement GitHub sync toggle for iterating skill
- [ ] Add repository config detection
- [ ] Test DEVLOG auto-commit workflow
- [ ] Update iterating/references/web-environment.md
- [ ] Document integration patterns

### Phase 4: Documentation & Polish (Week 2-3)
- [ ] Write comprehensive SKILL.md
- [ ] Create references/credential-setup.md with screenshots
- [ ] Create references/iterating-integration.md
- [ ] Add troubleshooting guide
- [ ] Create example workflows
- [ ] Write security best practices guide
- [ ] Package and test skill installation

## Technical Considerations

### Security
- **Never log full tokens**: Always mask (show first 4 and last 4 chars only)
- **Minimize scope**: Guide users to use fine-grained PATs with repo-only access
- **Secure storage**: Leverage existing credential patterns from api-credentials skill
- **Token rotation**: Include guidance on rotating tokens regularly

### Performance
- **Batch operations**: Use Git Trees API to commit multiple files in single commit
- **Rate limits**: GitHub API has rate limits (5000/hour for authenticated requests)
- **Caching**: Consider caching file SHAs to avoid redundant reads
- **Async operations**: For web environments, consider async/await patterns

### Reliability
- **Retry logic**: Implement exponential backoff for transient failures
- **Conflict resolution**: Detect file conflicts and guide user on resolution
- **Idempotency**: Operations should be safe to retry
- **Graceful degradation**: If GitHub sync fails, local operations should still work

### User Experience
- **Clear error messages**: Guide users to fix configuration issues
- **Progress feedback**: Show what's happening during multi-step operations
- **Dry-run mode**: Option to preview changes before committing
- **Undo support**: Document how to revert commits if needed

## Testing Strategy

### Unit Tests
- Credential fallback chain (mock each source)
- Token masking
- Error message generation
- Config file parsing

### Integration Tests
- Read file from test repository
- Commit single file
- Commit multiple files in batch
- Create branch and commit
- Create pull request
- Handle conflicts
- Handle rate limits (mock)

### End-to-End Tests
- Full iterating workflow with DEVLOG auto-sync
- Web environment simulation
- Desktop environment simulation
- Error recovery scenarios

## Success Metrics

1. **Adoption**: Number of users enabling GitHub sync for iterating
2. **Reliability**: <1% failure rate for GitHub operations
3. **Performance**: Commits complete within 3 seconds (95th percentile)
4. **Usability**: Users can configure credentials without support
5. **Integration**: Seamless integration with iterating skill

## Future Enhancements (Post-MVP)

### Phase 5: Advanced Features
- [ ] Support for GitHub Actions triggering
- [ ] Read PR comments and respond programmatically
- [ ] Manage GitHub Issues
- [ ] Support for GitHub Projects/Boards
- [ ] Repository cloning and initialization
- [ ] Support for GitHub Gists

### Phase 6: Multi-Platform State Sync
- [ ] Unified state store abstraction (GitHub, GitLab, Bitbucket)
- [ ] Cross-repository state references
- [ ] State versioning and rollback
- [ ] Collaborative state (multi-user DEVLOGs)

### Phase 7: Advanced Iterating Patterns
- [ ] Automatic summarization of long DEVLOGs
- [ ] DEVLOG search and query interface
- [ ] Milestone tracking
- [ ] Progress visualization
- [ ] Export to documentation formats

## Open Questions

1. **Environment variable naming**: What env var does Claude Web use for GitHub OAuth token?
   - Need to test in actual Web environment
   - May need to adapt based on Claude team's implementation

2. **Project Knowledge access**: How to programmatically read Project Knowledge documents in Web?
   - Current assumption: Special mount point like `/mnt/project-knowledge/`
   - May need different approach based on actual implementation

3. **Concurrency**: What if multiple Claude sessions try to commit to same branch simultaneously?
   - GitHub handles this with conflict detection
   - Need user guidance on branch naming strategy

4. **Scope boundaries**: Should skill handle GitHub Actions, Issues, Projects?
   - Phase 1: Focus on file operations only
   - Phase 5: Expand to other GitHub features

5. **Permissions**: What minimum permissions are needed for fine-grained PAT?
   - Required: `contents:write` (read/write files)
   - Optional: `pull_requests:write` (create PRs)
   - Document clearly in credential setup guide

## Dependencies

- **Python standard library**: os, json, pathlib, datetime, time
- **HTTP library**: requests or httpx (lightweight, no heavy dependencies)
- **api-credentials skill**: For tertiary credential fallback
- **iterating skill**: For integration (optional dependency)

## Migration Path

For existing iterating skill users:

1. **Phase 1**: Introduce as opt-in feature
   - Users must explicitly configure GITHUB_REPO_CONFIG
   - No changes to existing DEVLOG workflows

2. **Phase 2**: Provide migration guide
   - "How to move from manual DEVLOG to auto-sync"
   - Example configurations for common setups

3. **Phase 3**: Consider default-on for new projects
   - Auto-detect repository context
   - Suggest enabling GitHub sync on first DEVLOG update

## Documentation Deliverables

1. **SKILL.md**: Core skill documentation (~500 lines)
2. **references/credential-setup.md**: Step-by-step setup with screenshots
3. **references/api-reference.md**: Detailed API documentation for all functions
4. **references/iterating-integration.md**: Integration patterns and examples
5. **references/troubleshooting.md**: Common issues and solutions
6. **assets/config.json.example**: Example configuration file

## Acceptance Criteria

This skill is ready for release when:

- [ ] All Phase 1-3 tasks complete
- [ ] 95%+ test coverage
- [ ] All documentation complete
- [ ] Successfully tested in all three environments (Web, Desktop, CLI)
- [ ] Iterating integration working end-to-end
- [ ] Security review passed
- [ ] At least 3 external beta testers provide positive feedback
- [ ] Performance benchmarks meet targets
- [ ] Error messages are clear and actionable

## Timeline

- **Week 1**: Phases 1-2 (Core infrastructure + operations)
- **Week 2**: Phase 3 (Iterating integration)
- **Week 3**: Phase 4 (Documentation & polish)
- **Week 4**: Testing, feedback, refinement

Total: **4 weeks to MVP**

## Conclusion

The `invoking-github` skill will transform how Claude interacts with code repositories, enabling:

1. **Seamless web-based development** with automatic GitHub persistence
2. **Cross-session continuity** through DEVLOG auto-sync
3. **Unified development workspace** across all Claude environments

By building on proven patterns from existing skills (api-credentials, invoking-claude) and integrating tightly with the iterating skill, we'll create a powerful foundation for AI-assisted development workflows.

The three-tier credential fallback ensures security and flexibility, while the phased implementation allows for early feedback and iteration. The result will be a robust, user-friendly skill that fundamentally enhances Claude's ability to work with code repositories.
