# Web Environment (Claude Code on the Web)

This guide covers using the iterating skill in Claude Code web environment, where state is persisted via WorkLog.md in the repository.

## User Acknowledgment

At session start, tell the user:
> "I'll track our progress in WorkLog.md in the repository. Each session, I'll document key decisions, findings, and next steps with version tracking."

## Environment Detection

Detect via `CLAUDE_CODE_REMOTE='true'` environment variable.

## State Persistence: WorkLog.md

Maintain state across sessions using WorkLog.md in the repository root.

**Version management:**
- Check for existing WorkLog: `ls -1 WorkLog*.md 2>/dev/null | sort -V | tail -1`
- Parse version from frontmatter: `version: vN`
- Increment on each update: v1 → v2 → v3

## WorkLog Format

```markdown
---
version: v1
status: in_progress
---

# [Project Name] Work Log

## v1 | 2025-11-13 16:30 | Initial Implementation

**Prev:** [context from previous version OR "Starting new work"]
**Now:** Implementing user authentication with JWT

**Progress:** 30% | Auth service complete, endpoints pending

**Files:**
- `src/auth/service.ts` (JWT authentication logic)
  - L45-67: Token generation with expiry
  - L89-110: Token validation middleware
- `src/routes/auth.ts` (API endpoints, needs implementation)
  - L20-40: Login endpoint placeholder

**Work:**
+: src/auth/service.ts:45-67 (token generation)
+: src/auth/service.ts:89-110 (validation middleware)

**Decisions:**
- JWT over sessions: stateless auth enables horizontal scaling (vs sessions requiring sticky sessions/shared store)
- 1h access token + 7d refresh token: balance security and UX (vs short-lived only)

**Works:** Token generation tested with 100k iterations, sub-ms performance
**Fails:** Initial attempt at refresh endpoint had race condition with concurrent requests

**Blockers:** None

**Next:**
- [HIGH] Implement login endpoint (src/routes/auth.ts:20-40)
- [HIGH] Add refresh token rotation logic
- [MED] Write integration tests for auth flow
- [LOW] Add rate limiting to token endpoints

**Open:** Should we implement token revocation list or rely on short expiry?
```

## Updating WorkLog

```python
from datetime import datetime
from pathlib import Path

def update_worklog(data):
    worklog = Path("WorkLog.md")
    
    # Read existing version
    current_version = 0
    if worklog.exists():
        content = worklog.read_text()
        for line in content.split('\n'):
            if line.startswith('version:'):
                current_version = int(line.split('v')[1])
                break
    
    new_version = current_version + 1
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Build new entry
    entry = f"\n## v{new_version} | {ts} | {data['title']}\n\n"
    
    if data.get('prev'): 
        entry += f"**Prev:** {data['prev']}\n"
    entry += f"**Now:** {data['now']}\n\n"
    
    if data.get('progress'):
        entry += f"**Progress:** {data['progress']}\n\n"
    
    # Enhanced file references
    if data.get('files'):
        entry += "**Files:**\n"
        for file in data['files']:
            entry += f"- `{file['path']}` ({file['relevance']})\n"
            for focus in file.get('focus_areas', []):
                entry += f"  - L{focus['lines']}: {focus['note']}\n"
        entry += "\n"
    
    # Work summary
    if any(data.get(k) for k in ['added','changed','fixed']):
        entry += "**Work:**\n"
        if data.get('added'): 
            entry += f"+: {', '.join(data['added'])}\n"
        if data.get('changed'): 
            entry += f"~: {', '.join(data['changed'])}\n"
        if data.get('fixed'): 
            entry += f"!: {', '.join(data['fixed'])}\n"
        entry += "\n"
    
    # Decisions
    if data.get('decisions'):
        entry += "**Decisions:**\n"
        for d in data['decisions']:
            alt = f" (vs {d['alt']})" if d.get('alt') else ""
            entry += f"- {d['what']}: {d['why']}{alt}\n"
        entry += "\n"
    
    # Works/Fails
    if data.get('works'): 
        entry += f"**Works:** {', '.join(data['works'])}\n"
    if data.get('fails'): 
        entry += f"**Fails:** {', '.join(data['fails'])}\n"
    if data.get('works') or data.get('fails'): 
        entry += "\n"
    
    # Blockers
    blockers = data.get('blockers', 'None')
    entry += f"**Blockers:** {blockers}\n\n"
    
    # Next steps with priorities
    if data.get('next'):
        entry += "**Next:**\n"
        for step in data['next']:
            priority = step.get('priority', 'MED')
            entry += f"- [{priority}] {step['action']}\n"
        entry += "\n"
    
    # Open questions
    if data.get('open'): 
        entry += f"**Open:** {', '.join(data['open'])}\n\n"
    
    entry += "---\n"
    
    # Update frontmatter and append
    if worklog.exists():
        content = worklog.read_text()
        # Update version in frontmatter
        content = content.replace(f"version: v{current_version}", f"version: v{new_version}")
        # Update status if provided
        if data.get('status'):
            content = content.split('---\n', 2)
            content[1] = content[1].replace(f"status: {data.get('old_status', 'in_progress')}", f"status: {data['status']}")
            content = '---\n'.join(content)
        worklog.write_text(content + entry)
    else:
        # Create new WorkLog
        frontmatter = f"---\nversion: v1\nstatus: {data.get('status', 'in_progress')}\n---\n\n"
        frontmatter += f"# {data.get('project_name', 'Project')} Work Log\n"
        worklog.write_text(frontmatter + entry)
```

## Reading Past Context

```python
from pathlib import Path

# At session start, read WorkLog
worklog = Path("WorkLog.md")
if worklog.exists():
    content = worklog.read_text()
    
    # Parse version
    version = None
    status = None
    for line in content.split('\n'):
        if line.startswith('version:'):
            version = line.split(':')[1].strip()
        if line.startswith('status:'):
            status = line.split(':')[1].strip()
    
    print(f"Continuing from WorkLog {version}, status: {status}")
    
    # Focus on last 2-3 entries for recent context
    entries = content.split('## v')[1:]  # Skip frontmatter
    recent = entries[-3:] if len(entries) > 3 else entries
```

## Priority-Based Workflow

**Session start:**
1. Read WorkLog
2. Parse HIGH priority items from last entry
3. Acknowledge: "From WorkLog v3, HIGH priorities: [list]"
4. Execute HIGH items first

**If blocked:**
Update status to `blocked` and document blocker with owner/ETA.

## Progress Tracking

**Update progress on each session:**

```python
# Short task
data['progress'] = "60% complete"

# Long project
data['progress'] = "Phase 2/3 | Auth ✅ | Payments 50% 🔄 | UI ⏳"
```

**Why:** Token/quota constraints may prevent finishing full plan. Progress helps resume.

## Recognizing Handoff WorkLogs

**When user pastes a WorkLog at conversation start:**

1. **Detect handoff format:**
   - YAML frontmatter with `version:` and `status:`
   - WorkLog structure with task objective and file references

2. **Parse and acknowledge:**
   > "I see you're starting from WorkLog v1, status: in_progress.
   >
   > Task: [objective from WorkLog]
   > Progress: [percentage/milestones]
   > HIGH priorities: [list HIGH items]
   >
   > Starting with first HIGH priority: [item]"

3. **Execute HIGH priority items first**
   
4. **Update WorkLog as work progresses:**
   - Increment version
   - Update progress
   - Add new decisions
   - Mark completed items

5. **Prepare for handoff back to chat if needed:**
   - Update status to `needs_review` or `blocked` when appropriate

## Example Session

**Session 1:**
> "Starting WorkLog v1 for auth implementation. HIGH priority: JWT token service."

[Implements JWT service]

> "Updated WorkLog v1: JWT service complete, next HIGH: login endpoint."

**Session 2:**
> "From WorkLog v1, HIGH priority: login endpoint. Continuing..."

[Implements login]

> "Updated WorkLog v2: Login complete (progress 60%). Next HIGH: refresh token logic."

## User Communication

- **After update:** "Updated WorkLog v{N} with [summary]"
- **New session:** "From WorkLog v{N}, status: {status}. Last work: [summary]. Continuing with HIGH priority: [item]"
- **Status change:** "Updated WorkLog status to {new_status}: [reason]"
