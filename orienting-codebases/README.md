# orienting-codebases

Interactive codebase orientation for a human learner. Companion to
`exploring-codebases`: same structural pipeline (tree-sitting + featuring),
but synthesizes into guided HTML exercises rather than an analysis dump
for the agent.

## Why this exists

`exploring-codebases` answers "what is this repo?" for Claude. This skill
answers it for the person sitting at the keyboard.

The difference matters. Claude can ingest a `gather.py` dump and reason
about it immediately. A human needs to actively engage — predict,
synthesize, explain, get things wrong, correct — to build durable
understanding. Passive reading of generated analysis creates *fluency
illusion*: it feels understood but isn't retained. (Bjork & Bjork on
desirable difficulties; Tankelevitch et al., CHI 2024, on the
metacognitive demands of generative AI.)

## Why HTML

HTML makes the hardest pedagogical enforcement structural rather than
behavioral:

- **Pause protocol via `<details>`** — answers are physically hidden
  until the user clicks to reveal. No LLM drift can expose them
  prematurely; the generation effect is enforced by the DOM, not by
  prompt discipline.
- **Code-in-context** — the pipeline already has the source. treesit
  extracts specific functions with line ranges and the artifact shows
  them syntax-highlighted alongside the question. The user does the
  cognitive work; they don't waste orientation time on file navigation.
- **Standalone reuse** — an `orientation.html` anyone on the team can
  open in a browser. No tooling, no live AI session required.
  Collapsible exercises, architecture context, progress tracking.

## Pedagogical principles

Exercise design draws from established learning science:

- **Generation effect** — producing answers builds stronger memory than
  reading them (Roediger & Karpicke, 2006).
- **Pre-testing** — attempting before knowing primes encoding, even
  when the attempt is wrong (Giebl et al., 2021).
- **Desirable difficulty** — effort during learning produces stronger
  retention (Bjork & Bjork, 2013).
- **Fluency illusion** — easy processing ≠ durable knowledge; active
  engagement counters it (Soderstrom & Bjork, 2015).
- **Expertise reversal** — worked examples help novices but hinder
  experts; fading scaffolding addresses the transition (Kalyuga, 2007).
- **Program comprehension** — experts sample strategically, not
  exhaustively (Hermans 2021; Storey et al. 2006; Spinellis 2003).

Full reference: `DrCatHicks/learning-opportunities` `PRINCIPLES.md`.

## Lineage

Pedagogical design adapted from `DrCatHicks/learning-opportunities`
(`orient` skill + `PRINCIPLES.md`). Pipeline from `exploring-codebases`.
Presentation via `composing-html`.

License: CC-BY-4.0.
