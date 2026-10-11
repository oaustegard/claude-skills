# Native inter-agent messaging: `SendMessage` and `ListAgents`

Reference, moved from `orchestrating-agents` on 2026-10-11 when that skill became
`orchestrating-chat-agents`. Applies where native subagents exist (Claude Code, Cowork).

`ListAgents` discovers reachable agents; `SendMessage` delivers plain text to one
by name or id. Both reach subagents, agent-team teammates, and independent
sessions. Official docs: `code.claude.com/docs/en/cross-session-messaging`
(shipped v2.1.224, macOS and Linux).

Four measured behaviors the docs do not state. Each cost a round trip to find;
full method and verbatim receipts in `oaustegard/experiments` →
`subagent-messaging/RESULTS.md`.

- **NEVER reply using the incoming envelope's `from` attribute.** For subagents
  that value is the agent *type* (`general-purpose`), not an address, and the
  send fails with `No agent named 'general-purpose' is reachable`. Two
  same-type peers emit identical `from` values, so it cannot distinguish
  senders even in principle. Both the `SendMessage` description and the harness
  footer on every delivered message instruct otherwise. **Capture the agentId
  from the spawn result and address that.**
- **Subagents have no `ListAgents`.** `ToolSearch("select:ListAgents")` returns
  `No matching deferred tools found` — absent, not unloaded. A subagent reaches
  `"main"` and any address handed to it in its prompt, and nothing else. **The
  topology is a star through the main conversation, not a mesh: hand every peer
  its siblings' ids at spawn, or they cannot coordinate.**
- **Delivery queues and never interrupts.** The receiver reads between tool
  calls, so a peer inside a long `Bash` call is unreachable until it surfaces.
- **A send to a completed agent resumes it with full context, and the agent
  cannot tell.** Asked directly, a resumed agent reports no gap or restart
  marker. Instructions shaped as "if you were resumed, do X" never fire —
  **state the resume in the message.** Each resume replays the transcript:
  ~40k tokens for a small agent, and a measured eight-round chain ran
  199k → 324k. **Batch questions into one send.**

Contested: `anthropics/claude-code#48160` and `ruvnet/ruflo#2028` report that
subagents can receive but not originate `SendMessage`. A CCotw subagent
originated three sends successfully on 2026-08-12 with no
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` set. **Verify origination in your own
environment before designing around either claim.**

