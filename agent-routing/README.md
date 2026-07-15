# agent-routing

Decides which model (Haiku / Sonnet / Opus) and effort level a subagent
should get, when to cascade cheap-first behind a verifier instead of
picking one tier, and how to run improvement loops without them silently
regressing. Use when spawning subagents via the Agent or Workflow tools —
especially fan-outs of more than a handful — or when asked which model or
effort a task should route to.

Claude Code only — the `compatibility` field says so, and the skill's
advice (per-call `model`/`effort`, Agent/Workflow subagents) doesn't apply
to claude.ai chat.

The headline finding: Haiku 4.5 went 240/240 on mechanically checkable
work (nested arithmetic, multi-hop lookups, state tracking, trap math,
constraint-stacked generation) at `effort: low`, while Sonnet at low
effort missed 3/20 on the same battery. That inverts the usual default —
route *down* first, escalate on verifier failure, not the reverse.

Full routing table, cascade cost math, and loop discipline (evaluator as
exit gate — never trust the last iteration blindly) live in
**[SKILL.md](./SKILL.md)**. Raw evidence and re-run instructions in
**[references/calibration-2026-07-15.md](./references/calibration-2026-07-15.md)**.
