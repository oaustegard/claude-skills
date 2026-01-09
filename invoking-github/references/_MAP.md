# references/
*Files: 3*

## Files

### credential-setup.md
- Credential Setup Guide `h1` :1
- Overview `h2` :5
- Method 1: Project Knowledge (Recommended) `h2` :12
- Step 1: Create GitHub Personal Access Token `h3` :16
- Option A: Fine-Grained Token (Recommended - More Secure) `h4` :18
- Option B: Classic Token (Easier - Less Secure) `h4` :32
- Step 2: Add Token to Project Knowledge `h3` :45
- In Claude.ai Web: `h4` :47
- In Claude.ai Mobile (iOS/Android): `h4` :57
- Step 3: Verify Configuration `h3` :67
- Method 2: API Credentials Skill (Fallback) `h2` :92
- Step 1: Create Token `h3` :96
- Step 2: Add to api-credentials config.json `h3` :100
- Step 3: Verify Configuration `h3` :113
- Security Best Practices `h2` :117
- 1. Use Fine-Grained Tokens `h3` :119
- 2. Set Expiration Dates `h3` :126
- 3. Minimal Permissions `h3` :132
- 4. Token Rotation `h3` :142
- 5. Never Commit Tokens `h3` :150
- 6. Revoke Compromised Tokens `h3` :156
- Troubleshooting `h2` :165
- "No GitHub API token found!" `h3` :167
- "Authentication failed" `h3` :177
- "Access denied" `h3` :186
- Token works in web but not mobile `h3` :196
- FAQ `h2` :206
- Next Steps `h2` :232

### iterating-integration.md
- Iterating Skill Integration `h1` :1
- Overview `h2` :5
- Basic Integration Pattern `h2` :14
- Modified Update DEVLOG Function `h3` :16
- Usage `h3` :69
- Configuration-Based Pattern `h2` :99
- Configuration via Project Knowledge `h3` :103
- Configuration-Aware Function `h3` :116
- Session-Specific Branch Pattern `h2` :172
- Multi-File Session State Pattern `h2` :216
- Progressive Summarization Pattern `h2` :278
- Cross-Environment Continuity `h2` :349
- Automatic PR Creation Pattern `h2` :391
- Best Practices `h2` :446
- 1. Graceful Degradation `h3` :448
- 2. Informative Messages `h3` :468
- 3. Configuration Over Code `h3` :482
- 4. Session Identifiers `h3` :494
- Troubleshooting `h2` :507
- Next Steps `h2` :521

### troubleshooting.md
- Troubleshooting Guide `h1` :1
- Credential Issues `h2` :5
- "No GitHub API token found!" `h3` :7
- "Authentication failed" (401) `h3` :50
- "Access denied" (403) `h3` :78
- Repository Issues `h2` :114
- "Resource not found" (404) `h3` :116
- "Conflict" (409) `h3` :153
- File Operation Issues `h2` :193
- File content is corrupted `h3` :195
- Large file fails to commit `h3` :220
- Network Issues `h2` :244
- "Network error" or timeouts `h3` :246
- Integration Issues `h2` :285
- DEVLOG sync silently fails `h3` :287
- Can't import github_client `h3` :316
- API Behavior Issues `h2` :344
- Commit succeeds but file doesn't update `h3` :346
- PR creation fails: "A pull request already exists" `h3` :369
- Performance Issues `h2` :393
- Operations are slow `h3` :395
- Getting Help `h2` :422
- Common Error Reference `h2` :438
- Next Steps `h2` :448

