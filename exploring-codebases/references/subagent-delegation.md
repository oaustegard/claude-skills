# Delegating exploration to subagents

Loaded from the `exploring-codebases` workflow. Applies only when the repo is
large (>1000 files or several distinct subsystems) AND this environment exposes
a subagent tool. Steps 2-3 of the main workflow stay inline either way -- they are
mechanical and cheap; only step 4's judgment work fans out.


**Gate first: does this environment expose a subagent tool** (Agent/Task in
Claude Code and CCotw)? Claude.ai chat and bare-skill runs have none — run
steps 2–4 inline and skip this section entirely. Never simulate fan-out by
other means when the tool is absent.

When the tool exists and the repo is large (>1000 files or several distinct
subsystems), keep steps 2–3 inline — they're mechanical and cheap — and fan
out only step 4's judgment work, one agent per subsystem.

**Subagents inherit nothing.** Not your conversation, not this SKILL.md, not
the knowledge that scan artifacts exist on disk. An agent prompted only with
"explore `crates/foo`" will re-derive structure by `ls`/glob crawling at full
tier cost. (Observed 2026-07-16: four Sonnet agents launched onto a
2,300-file repo without the handoff spent their opening turns running `ls`,
with the full symbol index already on disk.)

Every subagent prompt must therefore carry:

1. **Its structure slice, pre-computed.** Partition the gather output's
   `## Public API` section by subsystem path prefix, write each slice to a
   file, and point the agent at its file: "grep/Read this instead of listing
   directories." Small slices (<50KB) can be pasted inline instead.
2. **The treesit recipe verbatim** — the full command including the venv
   python path, plus the batch rule (one invocation, many queries; each
   invocation pays the scan, extra queries are free).
3. **Anti-crawl instructions** — no `ls`/Glob for discovery; `Read` only to
   confirm or expand a line range the slice or treesit already located.
4. **An output spec** — what to report, a line budget, and "file paths +
   line refs" so results are verifiable.

Routing (see the `agent-routing` skill): multi-turn exploration is outside
Haiku's calibrated zone — use `sonnet` for subsystem agents and keep the
final cross-cluster synthesis in the orchestrator.
