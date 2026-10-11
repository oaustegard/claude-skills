---
name: orchestrating-agents
description: DEPRECATED, renamed to orchestrating-chat-agents. Kept so existing imports of its scripts keep working; every module here loads the same module from orchestrating-chat-agents. Use orchestrating-chat-agents for parallel Claude calls over the API from claude.ai, and dispatching-subagents for fan-out in Claude Code.
metadata:
  version: 0.9.0
---

# Orchestrating Agents (deprecated)

Renamed to [orchestrating-chat-agents](../orchestrating-chat-agents/SKILL.md) on 2026-10-11.

## Why

The old name sent requests to the wrong skill. Shown only skill names, Haiku, Sonnet and
Opus 5.5 routed 10 of 45 parallel-dispatch requests here, work that belongs to
`dispatching-subagents`. Of seven candidate names, `orchestrating-chat-agents` caught the
most of this skill's own requests (19/21 against 15/21) without drawing more of the
others' (`oaustegard/experiments` subagent-skill-choice). The content is the same: API
fan-out from surfaces with no native subagents, and Gemini delegation.

## Where things went

| you want | go to |
|---|---|
| parallel Claude calls over the API from claude.ai, `ConversationThread`, `AgentPool` | `orchestrating-chat-agents` |
| fan-out in Claude Code: Agent tool vs Workflow vs headless `claude -p` | `dispatching-subagents` |
| `SendMessage` / `ListAgents` between native subagents | `dispatching-subagents/references/native-messaging.md` |
| which model or effort a subagent gets | `agent-routing` |

`scripts/` here holds shims, so `sys.path.insert(0, '/mnt/skills/user/orchestrating-agents/scripts')`
followed by `from claude_client import invoke_claude` still works. Point new code at
`/mnt/skills/user/orchestrating-chat-agents/scripts`.
