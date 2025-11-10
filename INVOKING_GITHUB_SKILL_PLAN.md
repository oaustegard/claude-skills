# Invoking GitHub Skill - Implementation Plan

## Executive Summary

Create an `invoking-github` skill that enables **Claude.ai chat interface** (iOS/Android/Web at claude.ai) to read from and write to GitHub repositories programmatically. This skill will:

1. **Enable GitHub operations in Claude.ai chat** where native git access isn't available
2. **Augment the iterating skill** by auto-persisting DEVLOG.md to a GitHub branch
3. **Provide cross-session state management** via GitHub branches as persistent storage
4. **Use REST API with flexible authentication** (OAuth, Project Knowledge, or manual tokens)

**Note**: Claude Code (Desktop/CLI/Web IDE) already has native GitHub access via git proxy and doesn't need this skill.

## Vision: GitHub-Backed State for Claude.ai Chat

**Current limitation**: Claude.ai chat (mobile/web) has no persistent file system across sessions.

Currently:
- **Claude.ai Chat**: Project Knowledge documents (manual curation, no version control)
- **Claude Code**: Git integration (native, works out of the box)

**Target state**: Claude.ai chat can use GitHub branches as persistent storage, enabling:
- Automatic persistence of DEVLOG.md and other state
- Cross-session continuity without manual copy/paste
- Git-based history and rollback
- Seamless transition between chat and Claude Code environments

## Core Use Cases

### Use Case 1: Repository Operations from Claude.ai Chat
**Current limitation**: Claude.ai chat can read repos (via artifacts/paste) but cannot write back.

**Solution**: Skill provides programmatic GitHub operations:
1. Read files from any branch in repositories
2. Create/update files in a working branch
3. Commit changes with descriptive messages
4. Optionally create pull requests

**Workflow** (from claude.ai on mobile/web):
```
User: "Update the README in my repo and commit to feature-branch"
Claude: [Uses invoking-github to read current README via GitHub API]
Claude: [Modifies content]
Claude: [Commits changes to feature-branch via GitHub REST API]
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

### Credential Management (Two-Tier Fallback)

**Target environment**: Claude.ai chat (iOS/Android/Web)

**Important**: GitHub OAuth connection in claude.ai UI is NOT exposed to skills. Users must provide a Personal Access Token manually.

**Priority order**:

1. **Project Knowledge: GITHUB_API_KEY (Primary)**
   - User creates a Project Knowledge document named "GITHUB_API_KEY"
   - Content: Just the token (e.g., `ghp_abc123...` or fine-grained token)
   - Scope: Classic or fine-grained PAT with repo permissions
   - **Advantage**: Works across all Claude.ai platforms (iOS/Android/Web)
   - **Use case**: Primary method for all claude.ai chat users

2. **API Credentials Skill (Secondary)**
   - Leverages existing `api-credentials` skill pattern
   - Add `github_api_key` to config.json
   - **Use case**: Fallback, or for users who prefer config files
   - **Note**: Less accessible for mobile users, but works for power users

**Implementation Strategy**:

The skill uses GitHub REST API exclusively (no git proxy in chat environments):

```python
def get_github_token() -> str:
    """
    Get GitHub token with fallback chain.

    Returns:
        str: GitHub API token

    Raises:
        ValueError: If no token found in any source
    """
    # 1. Check Project Knowledge (claude.ai environment)
    # May be accessible via special path or through API
    # Implementation depends on Project Knowledge access method
    pk_path = Path("/mnt/project-knowledge/GITHUB_API_KEY")
    if pk_path.exists():
        token = pk_path.read_text().strip()
        if token:
            return token

    # 2. Check api-credentials skill (fallback)
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
        "1. Project Knowledge (recommended): Create document named 'GITHUB_API_KEY'\n"
        "   - In Claude.ai, go to Project settings → Add to Project Knowledge\n"
        "   - Create new document titled 'GITHUB_API_KEY'\n"
        "   - Paste your GitHub Personal Access Token as the content\n\n"
        "2. api-credentials skill: Add github_api_key to config.json\n\n"
        "Generate token at: https://github.com/settings/tokens\n"
        "Required scopes: repo (full repo access) or public_repo (public repos only)\n\n"
        "Note: GitHub OAuth in claude.ai UI is not accessible to skills"
    )

def commit_file(repo: str, path: str, content: str, branch: str, message: str):
    """
    Commit a file using GitHub REST API.

    Args:
        repo: Repository in format "owner/name"
        path: File path within repository
        content: New file content
        branch: Target branch
        message: Commit message

    Returns:
        dict with commit SHA, branch, and metadata
    """
    token = get_github_token()
    # Use GitHub REST API (implementation details below)
    # ...
```

**REST API Advantages for Claude.ai Chat:**
1. **No git installation required**: Pure HTTP, works in any environment
2. **Lightweight**: No need to clone repositories
3. **Fast**: Direct file operations without local filesystem
4. **Cross-platform**: Works identically on iOS/Android/Web
5. **Simple**: One API call per operation

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

### Implementation Details

#### GitHub REST API (Primary and Only Method)

**Library**: Use `httpx` for HTTP calls (async support, modern) or `requests` (simpler)
- Avoid PyGitHub (too heavy, unnecessary abstraction)
- Direct API calls give better control and error handling

**API Endpoints**:
- Read file: `GET /repos/{owner}/{repo}/contents/{path}?ref={branch}`
- Update file: `PUT /repos/{owner}/{repo}/contents/{path}` (requires file SHA for updates)
- Create tree: `POST /repos/{owner}/{repo}/git/trees`
- Create commit: `POST /repos/{owner}/{repo}/git/commits`
- Update ref: `PATCH /repos/{owner}/{repo}/git/refs/heads/{branch}`
- Create PR: `POST /repos/{owner}/{repo}/pulls`

**Authentication**: All requests include `Authorization: Bearer {token}` header

#### Error Handling:
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

1. **Project Knowledge access**: How to programmatically read Project Knowledge documents in claude.ai?
   - Current assumption: Special mount point like `/mnt/project-knowledge/`
   - May need different approach (API call, special file path, etc.)
   - Need to test in actual claude.ai environment (web/mobile)
   - **Critical**: This is the primary credential method for the skill

2. **Concurrency**: What if multiple Claude chat sessions try to commit to same branch?
   - GitHub API handles conflicts with 409 errors
   - Need user guidance on branch naming strategy
   - Consider session-specific branches (e.g., `devlog-{session-id}`)

3. **Scope boundaries**: Should skill handle GitHub Actions, Issues, Projects?
   - Phase 1: Focus on file operations only
   - Phase 5: Expand to other GitHub features

4. **Permissions**: What minimum permissions are needed for GitHub tokens?
   - PAT: `contents:write` (read/write files), `pull_requests:write` (create PRs)
   - Fine-grained tokens: Repository permissions for Contents (read/write) and Pull requests (read/write)
   - Document clearly in credential setup guide

5. **Mobile limitations**: Are there any restrictions on claude.ai mobile apps?
   - File size limits for API calls?
   - Rate limiting differences?
   - Network restrictions?
   - Can users access Project Knowledge from mobile?

6. **Token security**: How to guide users on secure token management?
   - Recommend fine-grained tokens over classic PATs
   - Minimum scopes required
   - Token expiration recommendations
   - How to rotate tokens safely

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

The `invoking-github` skill will unlock GitHub operations for Claude.ai chat users, enabling:

1. **GitHub write access from mobile/web chat** where it doesn't currently exist
2. **Cross-session state persistence** through automatic DEVLOG sync to GitHub
3. **Seamless workflow** between Claude.ai chat and Claude Code
4. **Simple authentication** via Project Knowledge documents

**Target users:**
- Claude.ai chat users (iOS/Android/Web) who want to commit code
- Mobile users who need persistent state across sessions
- Teams using Claude.ai chat for collaborative development
- Users who prefer chat interface over full IDE

**Not needed by:**
- Claude Code users (native git access already available)
- Users who only read repositories (current capabilities sufficient)

**Setup requirements:**
- Users must create a GitHub Personal Access Token manually
- Token stored in Project Knowledge document named "GITHUB_API_KEY"
- No OAuth integration available to skills (UI-only feature)

Building on proven patterns from existing skills (api-credentials, invoking-claude) and integrating tightly with the iterating skill, we'll create a powerful bridge between chat-based AI assistance and version-controlled development workflows.

The REST API approach provides cross-platform compatibility and simplicity, while the two-tier credential fallback (Project Knowledge → api-credentials) ensures accessibility. The result will be a robust skill that extends Claude.ai chat's capabilities into the realm of collaborative software development.
