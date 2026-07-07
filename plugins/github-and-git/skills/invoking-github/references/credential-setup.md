# Credential Setup Guide

Complete guide to configuring GitHub authentication for the invoking-github skill.

## Overview

This skill requires a GitHub Personal Access Token (PAT). Two configuration methods are supported:

1. **Project Knowledge** (Primary) - Recommended for claude.ai chat users
2. **API Credentials Skill** (Fallback) - For power users or local environments

## Method 1: Project Knowledge (Recommended)

Best for Claude.ai chat (mobile/web/desktop).

### Step 1: Create GitHub Personal Access Token

#### Option A: Fine-Grained Token (Recommended - More Secure)

1. Go to https://github.com/settings/tokens?type=beta
2. Click "Generate new token"
3. Configure:
   - **Token name**: `claude-ai-chat` (or your preference)
   - **Expiration**: 90 days (or your preference)
   - **Repository access**: Select specific repositories you want Claude to access
   - **Permissions**:
     - Repository permissions → **Contents**: Read and write
     - Repository permissions → **Pull requests**: Read and write
4. Click "Generate token"
5. **Copy the token immediately** (you won't see it again!)

#### Option B: Classic Token (Easier - Less Secure)

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Configure:
   - **Note**: `claude-ai-chat`
   - **Expiration**: 90 days
   - **Scopes**:
     - ✓ `repo` (Full control of private repositories)
     - Or just `public_repo` if you only need public repo access
4. Click "Generate token"
5. **Copy the token immediately**

### Step 2: Add Token to Project Knowledge

#### In Claude.ai Web:

1. Open your project in Claude.ai
2. Click the project name/settings
3. Click "Add to Project Knowledge"
4. Create a new document:
   - **Title**: `GITHUB_API_KEY` (exactly this, all caps)
   - **Content**: Paste your token (e.g., `ghp_1234567890abcdefgh...`)
5. Click "Add" or "Save"

#### In Claude.ai Mobile (iOS/Android):

1. Open your project
2. Tap the menu icon
3. Select "Project Knowledge"
4. Tap "Add document"
5. Title: `GITHUB_API_KEY`
6. Content: Paste your token
7. Save

### Step 3: Verify Configuration

Ask Claude to run this test:

```python
import sys
sys.path.append('/home/user/claude-skills/invoking-github/scripts')
from github_client import get_github_token

try:
    token = get_github_token()
    masked = f"{token[:7]}...{token[-4:]}"
    print(f"✓ Token found: {masked}")
    print(f"✓ Token length: {len(token)} characters")
except ValueError as e:
    print(f"✗ Token not found")
    print(e)
```

**Expected output**:
```
✓ Token found: ghp_123...xyz
✓ Token length: 40 characters
```

## Method 2: API Credentials Skill (Fallback)

For power users who prefer file-based configuration.

### Step 1: Create Token

Follow the same token creation steps as Method 1.

### Step 2: Add to api-credentials config.json

1. Edit `/home/user/claude-skills/api-credentials/config.json`
2. Add your token:
   ```json
   {
     "anthropic_api_key": "sk-ant-...",
     "google_api_key": "AIza...",
     "github_api_key": "ghp_your_token_here"
   }
   ```
3. Save the file

### Step 3: Verify Configuration

Same test as Method 1 above.

## Security Best Practices

### 1. Use Fine-Grained Tokens

Fine-grained tokens are more secure because:
- Limited to specific repositories
- Specific permissions (not full repo access)
- Easier to audit

### 2. Set Expiration Dates

- Recommended: 90 days
- Maximum: 1 year (but not recommended)
- Never select "No expiration" for production use

### 3. Minimal Permissions

Only grant permissions you actually need:

| Operation | Required Permissions |
|-----------|---------------------|
| Read files | Contents: Read |
| Commit files | Contents: Read and write |
| Create PRs | Contents: Read and write + Pull requests: Read and write |

### 4. Token Rotation

Rotate tokens regularly:
- Set calendar reminder before expiration
- Create new token
- Update Project Knowledge or config.json
- Revoke old token

### 5. Never Commit Tokens

- **Never** paste tokens in code that gets committed
- **Never** commit config.json with real tokens
- Use .gitignore (api-credentials/config.json is already gitignored)

### 6. Revoke Compromised Tokens

If a token is accidentally exposed:
1. Go to https://github.com/settings/tokens
2. Find the token
3. Click "Delete" or "Revoke"
4. Create a new token immediately
5. Update configuration

## Troubleshooting

### "No GitHub API token found!"

**Problem**: Token not detected in either location.

**Solutions**:
- Check Project Knowledge document is titled **exactly** `GITHUB_API_KEY` (all caps)
- Verify token is the only content in the document (no extra text)
- Check for trailing whitespace
- Try Method 2 (api-credentials) as a test

### "Authentication failed"

**Problem**: Token is invalid or expired.

**Solutions**:
- Verify token hasn't expired (check GitHub settings)
- Ensure no extra characters when copying token
- Generate a new token and update configuration

### "Access denied"

**Problem**: Token lacks required permissions.

**Solutions**:
- For fine-grained tokens: Check repository access includes your target repo
- For fine-grained tokens: Verify Contents and Pull requests permissions
- For classic tokens: Ensure `repo` scope is selected
- Generate new token with correct permissions

### Token works in web but not mobile

**Problem**: Project Knowledge might not sync properly.

**Solutions**:
- Wait a few minutes for sync
- Refresh the app
- Try deleting and re-adding the document
- Use api-credentials method as workaround (if app supports file access)

## FAQ

**Q: Can I use the GitHub OAuth connection in claude.ai UI?**

A: No, the OAuth connection in the UI is not accessible to skills. You must create a Personal Access Token manually.

**Q: How long do tokens last?**

A: Based on your selection during creation. Recommended: 90 days with rotation.

**Q: Can I use the same token across multiple Claude projects?**

A: Yes, but for security, consider creating separate tokens per project with limited repo access.

**Q: What happens when my token expires?**

A: The skill will fail with authentication errors. Create a new token and update your configuration.

**Q: Can I use a GitHub App token?**

A: Not directly. This skill is designed for Personal Access Tokens. GitHub App tokens have different authentication flows.

**Q: Is my token secure in Project Knowledge?**

A: Project Knowledge is stored securely, but treat it like a password - use minimal permissions, set expiration, rotate regularly.

## Next Steps

- [SKILL.md](../SKILL.md) - Core skill documentation
- [iterating-integration.md](iterating-integration.md) - Auto-sync DEVLOG patterns
- [troubleshooting.md](troubleshooting.md) - Common issues and solutions
