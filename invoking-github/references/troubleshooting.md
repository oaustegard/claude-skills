# Troubleshooting Guide

Common issues and solutions when using the invoking-github skill.

## Credential Issues

### "No GitHub API token found!"

**Symptoms**:
- Any operation fails immediately with credential error
- Self-test shows "Token not configured"

**Causes**:
1. Token not added to Project Knowledge
2. Wrong document title in Project Knowledge
3. api-credentials config.json missing or malformed

**Solutions**:

**Check Project Knowledge**:
- Document must be titled exactly `GITHUB_API_KEY` (all caps, underscores)
- Content should be just the token, no extra text
- No trailing whitespace or line breaks

**Check api-credentials**:
```bash
cat /home/user/claude-skills/api-credentials/config.json
```

Should contain:
```json
{
  "github_api_key": "ghp_your_token_here"
}
```

**Test credential detection**:
```python
import sys
sys.path.append('/home/user/claude-skills/invoking-github/scripts')
from github_client import get_github_token

try:
    token = get_github_token()
    print(f"✓ Token found: {token[:7]}...{token[-4:]}")
except ValueError as e:
    print(e)
```

### "Authentication failed" (401)

**Symptoms**:
- Token is detected but API calls fail with 401
- "Authentication failed" error message

**Causes**:
1. Token has expired
2. Token was revoked
3. Token contains typos or extra characters

**Solutions**:

**Check token status on GitHub**:
1. Go to https://github.com/settings/tokens
2. Find your token
3. Check if it's expired or revoked

**Generate new token**:
1. Create new token at https://github.com/settings/tokens
2. Update Project Knowledge or config.json
3. Retry operation

**Verify no extra characters**:
- Token should start with `ghp_` (classic) or `github_pat_` (fine-grained)
- No spaces, quotes, or line breaks
- Exact length: 40 characters (classic) or longer (fine-grained)

### "Access denied" (403)

**Symptoms**:
- Authentication works but specific operations fail
- "Access denied" or "insufficient permissions" errors

**Causes**:
1. Token lacks required permissions
2. Repository is private and token doesn't have access
3. Rate limit exceeded

**Solutions**:

**Check token permissions**:
- For fine-grained tokens:
  - Repository access: Verify target repo is in the list
  - Permissions: Contents (read/write), Pull requests (read/write)
- For classic tokens:
  - Scope: Must have `repo` (or `public_repo` for public repos only)

**Check rate limits**:
```python
import sys
sys.path.append('/home/user/claude-skills/invoking-github/scripts')
from github_client import _make_api_request

response = _make_api_request("/rate_limit")
print(f"Remaining: {response['rate']['remaining']}/{response['rate']['limit']}")
print(f"Reset at: {response['rate']['reset']}")
```

If rate limited:
- Wait until reset time
- Reduce request frequency
- Consider using different token

## Repository Issues

### "Resource not found" (404)

**Symptoms**:
- Repository, branch, or file not found
- "404" error message

**Causes**:
1. Repository name is incorrect
2. Branch doesn't exist
3. File path is wrong
4. Repository is private and token doesn't have access

**Solutions**:

**Verify repository format**:
- Correct: `username/repo-name` or `organization/repo-name`
- Incorrect: `https://github.com/username/repo-name`
- Incorrect: `username-repo-name`
- Incorrect: `repo-name` (missing owner)

**Check branch exists**:
```python
import sys
sys.path.append('/home/user/claude-skills/invoking-github/scripts')
from github_client import _make_api_request

# List all branches
response = _make_api_request("/repos/username/repo-name/branches")
branches = [b['name'] for b in response]
print(f"Available branches: {branches}")
```

**Verify file path**:
- Use forward slashes: `src/main.py` not `src\main.py`
- No leading slash: `README.md` not `/README.md`
- Case-sensitive: `readme.md` ≠ `README.md`

### "Conflict" (409)

**Symptoms**:
- Commit fails with 409 error
- "Conflict" or "file was modified" message

**Causes**:
1. File was modified since last read
2. Multiple concurrent commits to same file
3. Branch was force-pushed

**Solutions**:

**Read file again before committing**:
```python
from github_client import read_file, commit_file

# Read current version
current = read_file(repo, path, branch)

# Make your changes
new_content = modify(current)

# Commit (will have latest SHA)
commit_file(repo, path, new_content, branch, "Update")
```

**Use unique branches per session**:
```python
from datetime import datetime

branch = f"feature-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
commit_file(repo, path, content, branch, "Update", create_branch_from="main")
```

**Check for concurrent modifications**:
- Ensure only one Claude session is modifying the file
- Use session-specific branches
- Coordinate with team members

## File Operation Issues

### File content is corrupted

**Symptoms**:
- File appears as binary/garbage after commit
- Encoding errors when reading

**Causes**:
1. Binary file being treated as text
2. Encoding issues

**Solutions**:

**This skill is for text files only**:
- Supports: .txt, .md, .py, .js, .json, .yaml, etc.
- Not supported: Images, PDFs, executables, archives

**Ensure UTF-8 encoding**:
```python
# Read with explicit encoding
content = Path("file.txt").read_text(encoding='utf-8')

# Commit
commit_file(repo, path, content, branch, "Update")
```

### Large file fails to commit

**Symptoms**:
- Commit fails for large files
- Timeout errors

**Causes**:
1. File exceeds GitHub API limits (~100MB)
2. Network timeout

**Solutions**:

**Check file size**:
```python
size = len(content.encode('utf-8'))
if size > 100 * 1024 * 1024:  # 100MB
    print(f"File too large: {size / (1024*1024):.1f}MB")
```

**Split large files**:
- Break into smaller chunks
- Use Git LFS (not supported by this skill)
- Consider alternative storage

## Network Issues

### "Network error" or timeouts

**Symptoms**:
- Operations fail with network errors
- Timeouts during API calls

**Causes**:
1. No internet connection
2. GitHub API is down
3. Firewall blocking requests

**Solutions**:

**Check internet connection**:
```bash
curl -I https://api.github.com
```

**Check GitHub status**:
- Visit https://www.githubstatus.com
- Check for ongoing incidents

**Retry with backoff**:
```python
import time

for attempt in range(3):
    try:
        result = commit_file(...)
        break
    except Exception as e:
        if attempt < 2:
            wait = 2 ** attempt
            print(f"Retry in {wait}s...")
            time.sleep(wait)
        else:
            raise
```

## Integration Issues

### DEVLOG sync silently fails

**Symptoms**:
- Local DEVLOG updates but no GitHub commit
- No error messages

**Causes**:
1. Exception is being caught and suppressed
2. auto_sync is False

**Solutions**:

**Add logging**:
```python
try:
    sync_to_github()
except Exception as e:
    print(f"⚠ Sync failed: {e}")
    import traceback
    traceback.print_exc()
```

**Check configuration**:
```python
config = get_devlog_config()
print(f"auto_sync: {config.get('auto_sync')}")
print(f"repo: {config.get('repo')}")
```

### Can't import github_client

**Symptoms**:
- `ImportError: No module named github_client`
- `ModuleNotFoundError`

**Causes**:
1. Path not in sys.path
2. Skill not installed

**Solutions**:

**Add to path explicitly**:
```python
import sys
sys.path.insert(0, '/home/user/claude-skills/invoking-github/scripts')
from github_client import commit_file
```

**Verify skill exists**:
```bash
ls -la /home/user/claude-skills/invoking-github/scripts/
```

Should show:
- `github_client.py`
- `__init__.py`

## API Behavior Issues

### Commit succeeds but file doesn't update

**Symptoms**:
- Commit returns success
- File on GitHub hasn't changed

**Causes**:
1. Committing to wrong branch
2. Looking at different branch on GitHub

**Solutions**:

**Verify branch**:
```python
result = commit_file(repo, path, content, branch, "Update")
print(f"Committed to branch: {result['branch']}")
print(f"Commit SHA: {result['commit_sha']}")
```

**Check GitHub UI**:
- Make sure you're viewing the correct branch
- Click branch dropdown and select your target branch

### PR creation fails: "A pull request already exists"

**Symptoms**:
- PR creation fails with "already exists" error

**Causes**:
1. PR from head to base already exists
2. Previous PR wasn't closed

**Solutions**:

**List existing PRs**:
```python
from github_client import _make_api_request

response = _make_api_request(f"/repos/{repo}/pulls?state=open")
for pr in response:
    print(f"PR #{pr['number']}: {pr['head']['ref']} → {pr['base']['ref']}")
```

**Close or merge existing PR first**:
- Go to GitHub and close/merge the existing PR
- Or use a different head branch

## Performance Issues

### Operations are slow

**Symptoms**:
- Each commit takes several seconds
- Batch operations take a long time

**Causes**:
1. Network latency
2. Large files
3. Many files in batch

**Solutions**:

**Use batch operations**:
```python
# Slow: Multiple individual commits
for file in files:
    commit_file(repo, file['path'], file['content'], branch, f"Update {file['path']}")

# Fast: Single batch commit
commit_files(repo, files, branch, "Update multiple files")
```

**Minimize requests**:
- Don't read file before every commit if you already have content
- Use commit_files() instead of multiple commit_file() calls

## Getting Help

If you're still stuck:

1. **Check GitHub API status**: https://www.githubstatus.com
2. **Verify token permissions**: https://github.com/settings/tokens
3. **Test with GitHub CLI**: Try same operation with `gh` CLI
4. **Check GitHub docs**: https://docs.github.com/rest

**Provide this info when asking for help**:
- Error message (full text)
- Operation you're trying to perform
- Repository name (if not sensitive)
- Token type (classic vs fine-grained)
- Whether credential test passes

## Common Error Reference

| Error Code | Meaning | Common Solution |
|------------|---------|-----------------|
| 401 | Authentication failed | Check token is valid and not expired |
| 403 | Access denied | Check token permissions and rate limits |
| 404 | Not found | Verify repo/branch/file exists and is accessible |
| 409 | Conflict | Re-read file, use unique branch names |
| 422 | Validation error | Check branch name format, commit message |

## Next Steps

- [credential-setup.md](credential-setup.md) - Token configuration guide
- [SKILL.md](../SKILL.md) - Main skill documentation
- [GitHub API Docs](https://docs.github.com/rest) - Official API reference
