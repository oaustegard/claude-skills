# Semi-Formal Code Reasoning

Structured certificate templates for code analysis, based on Ugare & Chandra (2026).

## Provenance

- Paper: Ugare & Chandra, "Agentic Code Reasoning with Semi-Formal Certificates" (arXiv:2603.01896, March 2026)
- Replication: Django name-shadowing (0%→100% fault localization), 3 real bugs (+11pp aggregate)
- CVE validation: CVE-2026-29000 (pac4j-jwt, 383 lines). Haiku: +20pp with template. Sonnet: -20pp with template.
- Finding: Template value is model-capability-dependent. Scaffolding helps weaker models; it becomes overhead for stronger ones.

## Structure

| File | Audience | Purpose |
|------|----------|---------|
| `SKILL.md` | All models | Thin router: skip conditions + model-tier routing |
| `sonnet.md` | Sonnet/Opus | 3 compact verification checkpoints |
| `haiku.md` | Haiku | Full procedural templates with worked examples |
