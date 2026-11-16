# building-property-tests

Find correctness bugs by running code against a simple reference model over
generated inputs and operation sequences. Shrink each disagreement to a
deterministic regression test, and fix it without trusting the generator.

## Credit

This skill is an adaptation of the work of **Inanna Malick**:

- the post [Property Testing with Agent Swarms](https://recursion.wtf/posts/agents-and-property-tests/)
  on [recursion.wtf](https://recursion.wtf). It describes having agents build
  reference implementations, generators and assertions, and shows the results
  on Codex, jj, uv, Prometheus, Babel, rv and Apollo's Router;
- her `proptest-praxis` skill in
  [inanna-malick/agent-skills](https://github.com/inanna-malick/agent-skills/tree/main/skills/proptest-praxis),
  released under the MIT License (Copyright (c) 2026 Inanna Malick).

The method is hers: target selection, independent reference models, generator
design, treating a quiet run as a coverage problem, mutation calibration, root
cause clustering, and one focused regression and fix per bug kept apart from
the discovery suite. This skill rewrites it for Python and Hypothesis, and
routes the calibration step through `gating` and the invariant step through
`declaring-invariants`. It adds a coverage-floor script, a runnable
state-machine template, and lessons from applying the method to two codebases
(see `CHANGELOG.md`). Where this skill falls short of the original, read the
original.

## Contents

| Path | What |
|---|---|
| `SKILL.md` | The procedure, routing against sibling skills, earned exceptions, failure modes |
| `scripts/hypothesis_stats.py` | Runs a Hypothesis suite and fails when a relied-on `event()` class falls below a floor or never fires |
| `assets/stateful_template.py` | A runnable `RuleBasedStateMachine` with a toy subject, a planted mutant and event counters |
| `references/targets.md` | Property kinds, generator rules, tolerances, where bugs were found |
| `references/delegating.md` | One agent per area: the brief, the constraints, the orchestrator's half |

```bash
python3 -m pytest -q tests/                     # the script's own tests
```
