# down-skilling

Distills Opus-level reasoning into explicit, procedural prompts with
n-shot examples so Haiku (or Sonnet) can execute a task reliably. Use
when the user says "down-skill", "distill for Haiku", or wants to
delegate a task to a smaller model with high reliability.

Before distilling anything, the skill now triages: if the task's output
is mechanically checkable (schema validates, tests pass, a count is a
count), a minimal prompt plus a deterministic verifier beats a
heavy example-laden distillation — save the n-shot investment for
outputs that genuinely need judgment. That triage step, the per-gap
mitigations, and the pricing in the Economics section were all recalibrated
against measured Haiku 4.5 data on 2026-07-15 (see `agent-routing`'s
[calibration reference](../agent-routing/references/calibration-2026-07-15.md)) —
several model-card-era priors turned out to understate Haiku, most notably
on counting/enumeration and multi-hop reasoning over *explicit* chains.

Full prompt architecture, the gap catalog (`gaps/`), worked
before/after examples (`examples/`), and the self-check checklist live in
**[SKILL.md](./SKILL.md)**. Version history in
**[CHANGELOG.md](./CHANGELOG.md)**.
