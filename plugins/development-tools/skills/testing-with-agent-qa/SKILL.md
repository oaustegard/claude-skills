---
name: testing-with-agent-qa
description: "Validates selected agent-qa regression tests and inspects their run evidence. Use for 'validate my agent-qa YAML', 'rerun checkout with agent-qa', 'why is this agent-qa run healed', or 'inspect this run's memidex'."
license: MIT
compatibility: "Node.js 24+, an installed agent-qa CLI, and an initialized project. Live runs require access to the configured provider and web/mobile target."
metadata:
  version: "1.0.0"
  author: "vostride"
---

# Testing with agent-qa

Validate, execute, and triage selected natural-language web, Android, or iOS regressions. agent-qa brings advanced memidex memory and self-improvement; inspect the recorded evidence to establish what happened in a particular run.

## Applicability boundary

Use this when the project already uses agent-qa or the user explicitly chooses it. Work from the selected test/configuration and the user's authorized target. This is a CLI workflow: a chat-only environment without project files, Node.js 24+, or target access cannot execute it.

| When NOT to use this skill | Route instead |
| --- | --- |
| Browse a page or fix a webctl proxy failure without agent-qa tests | `using-webctl` |
| Build a feature inventory from application source | `mapping-webapp` |
| Coordinate hundreds of workers over a large failing-test backlog | `swarming-to-green` |
| Preserve conversation/session context | `session-memory`; memidex here means agent-qa's test memory |
| Generate unit tests or author raw Playwright/Appium scripts | The project's existing test framework; this skill does not replace it |

These routes identify adjacent tasks; using this skill does not require installing its siblings.

## Establish scope and prerequisites

1. Locate `agent-qa.config.yaml`, the selected test or suite, and its target. Resolve any missing target or execution authorization before a live run. Reuse the project's installed CLI and provider configuration.
2. Run from the project directory. In the npm examples, `--no-install` prevents silently downloading another agent-qa version. Adapt the package-manager invocation to the project.

   ```sh
   node --version
   npx --no-install agent-qa --version
   npx --no-install agent-qa run --help
   ```

3. Confirm Node.js 24+ and the installed command syntax. These examples were checked against agent-qa 0.2.3. `--version` prints a number; that number is not a command. For a custom configuration, put the global `--config PATH` before the subcommand.
4. If initialization or installation is missing, report that prerequisite and use the [official quickstart](https://vostride.com/docs/agent-qa/quickstart) when setup is in scope. A container's browser availability does not prove access to a user's local app, emulator, or mobile device.

## Validate and select

Replace `tests/checkout.yaml` with the selected path, then run:

```sh
npx --no-install agent-qa validate tests/checkout.yaml
npx --no-install agent-qa run tests/checkout.yaml --dry-run
```

Check that validation succeeds and the dry run lists the intended tests. An empty or unexpected selection needs investigation. Omitting the path selects all discovered tests; keep the explicit path unless the user requested the whole suite.

Record these as structure and selection checks. A dry run performs no application test and does not establish a passing verdict.

## Execute the authorized regression

Confirm the target environment, test data, and provider use are within the user's request. Application actions can change data; configured model/device services can incur costs. Then execute the selected flow:

```sh
npx --no-install agent-qa run tests/checkout.yaml --junit-output results.xml
```

Preserve the exit status, run ID, and available report/evidence paths. Inspect the recorded verdict before describing the result.

| Exit | Interpretation |
| --- | --- |
| `0` | Passed or healed; inspect the verdict to distinguish them |
| `1` | Failed/timed-out tests or missing required files; inspect the diagnostic |
| `2` | agent-qa could not run |
| `130` | Cancelled |

A setup failure leaves execution unresolved; it is not an application assertion failure. Check that a requested JUnit file actually exists before linking it.

## Triage the recorded run

```sh
npx --no-install agent-qa runs list --verdict failed --limit 10 --json
npx --no-install agent-qa runs overview RUN_ID --json
npx --no-install agent-qa runs knowledge RUN_ID --json
npx --no-install agent-qa knowledge inspect --json
```

Replace `RUN_ID` with the selected record, not merely the newest run. Use `runs list --json` without the failed filter when investigating a healed or other outcome.

Read the failed step, verdict, and evidence before proposing a correction. Separate application defects, expectation problems, and provider/device/setup failures. The run knowledge view shows available memidex evidence; an empty knowledge store says nothing about whether the application passed.

If the run lacks a completed verdict or reports `evidence-incomplete`, report unresolved evidence. Preserve assertions and memory while diagnosing. After an evidence-based correction, rerun only the selected flow and compare its new run ID and verdict with the earlier evidence.

## Exceptions and stopping conditions

| Action | Banned when | Earned when |
| --- | --- | --- |
| Expand from one test to the whole suite | The user selected one regression | The user requests broader coverage and the target/data budget supports it |
| Live execution | Only validation/inspection was requested or target access is absent | The existing request authorizes the chosen environment and provider use |
| Correct stored knowledge | The goal is merely to force a green result | Evidence identifies a specific bad entry and a separate memory correction is authorized |

Abandon execution if configuration points at a different target, selected tests are missing, required files/access are unavailable, or the next action exceeds the agreed scope. Report the exact prerequisite. Stop retrying an unchanged failure when no new corrective action is justified.

## Failure signals and verification

| Signal | Mitigation |
| --- | --- |
| CLI unavailable or Node version below 24 | Resolve installation/runtime prerequisites before interpreting test behavior |
| Dry run exits `0` and lists tests | Report selection success only; execute an authorized run to verify application behavior |
| Missing required env/configuration file with exit `1` | Restore the intended local setup; do not rewrite application assertions |
| Empty failed-run list | Inspect the selected run across all verdicts; absence from this filter is not proof of a pass |
| No completed verdict or `evidence-incomplete` | Preserve the unresolved classification and inspect available logs/dashboard records |
| Repeated failure after the same command | Investigate new evidence or stop; repeated invocations alone are not a correction |

Verify completion with the selected run's `runs overview RUN_ID --json`, execution status, and actual evidence/report files. A **bad success** is reporting that checkout passed because validation succeeded, the failed-run filter was empty, or a dry run returned zero. Likewise, a healed result must remain labeled healed.

Return a concise record: selected config/test/target; commands actually run; exit status and run ID; native verdict; available evidence/report paths; correction and rerun result; unresolved or unexecuted checks. Redact credentials and sensitive application data.

## Diagnosed outcomes

Checked on 2026-10-25 with the stock 0.2.3 CLI in isolated fixtures:

- **Selection succeeded, execution not attempted:** valid YAML and a dry run listed one test. No application pass was established.
- **Setup failed:** removing the required env file made the dry run exit `1`. The failure concerned setup, not an application assertion.
- **Evidence unresolved:** a synthetic incomplete run record made overview fail for lack of a verdict and knowledge report `evidence-incomplete`. It was not a completed application run.

These outcomes cover the local CLI checks, not a live provider, browser, or device session. See [validation notes](references/validation.md) for the contribution's remaining checks.

## Sources and license

- [CLI commands and exit codes](https://vostride.com/docs/agent-qa/cli)
- [Inspect and correct memory](https://vostride.com/docs/agent-qa/memory/inspect)
- [agent-qa repository](https://github.com/vostride/agent-qa)

These original instructions use MIT. The separately installed agent-qa package uses FSL-1.1-ALv2; provider and device services have their own requirements and costs.
