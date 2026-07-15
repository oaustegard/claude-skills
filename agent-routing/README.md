# agent-routing

Decide which model (Haiku/Sonnet/Opus) and effort level each subagent gets, when to cascade cheap-first behind a verifier, and how to run improvement loops safely (evaluator-as-selector, stop on regression). Use when spawning subagents via the Agent or Workflow tools, when fanning out more than a handful of agents, or when the user asks which model or effort a task should route to. Grounded in measured calibration data (references/calibration-2026-07-15.md), not vibes.
