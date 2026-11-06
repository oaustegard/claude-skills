# Contribution validation

The package provides a selected-regression workflow for an initialized agent-qa project. It does not claim to make a chat-only environment capable of reaching a user's browser or mobile device.

## Executable scope

The stock agent-qa 0.2.3 CLI was exercised on isolated local fixtures with a dummy provider and target at `127.0.0.1:9`, no provider credentials, and privacy enabled. The incomplete database record is synthetic and has no application verdict.

| Scenario | Expected observation | Claim supported |
| --- | --- | --- |
| Valid checkout YAML; validation and dry-run selection | Successful validation and exactly one selected test | Structure/selection only |
| Invalid test YAML | Validation fails with a diagnostic | Malformed input is rejected |
| Required env file removed | Dry run exits `1` and identifies the missing file | Setup failure remains unresolved execution |
| Synthetic incomplete run | Overview exits nonzero; knowledge reports `evidence-incomplete` | Missing verdict is not a completed application result |
| Empty failed-run list and knowledge store | Empty JSON arrays | These views are readable, not proof of application success |

No live provider/application run, healed-run efficacy, JUnit generation, browser/device execution, or broader product-effectiveness measurement is claimed.

## Routing check still pending

The repository's `creating-skill` workflow requires `skill_confusability.py` from `oaustegard/claude-workspace`. That checker is not present in this public checkout and its referenced repository is unavailable to this contributor. No substitute score or embedding result is claimed.

[routing-queries.json](routing-queries.json) contains five task-shaped positives, adjacent-skill cases, and `__none__` negatives for the maintainer's checker. These are proposed check inputs, not measured results. Before this draft is ready, run the native checker against the full catalog and inspect top-1, steals, near-misses, and neighbors above the documented similarity threshold. Resolve any genuine boundary collision before publishing.
