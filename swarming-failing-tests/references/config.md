# swarm.toml reference

Loaded by `swarmkit/config.py`: defaults overlaid with the file; an unknown key is an
error. Paths are relative to the project root. `.json` works too.

| key | default | meaning |
|---|---|---|
| `project` | `"project"` | label only |
| `state_dir` | `.swarm/state` | ledger, known.json, baselines, task dirs; added to `.git/info/exclude` |
| `rejected_dir` | `.swarm/rejected` | rejected diffs with the reason in a header |
| `wt_root` | `<root>-wt` | worker worktrees, `_gate`, `_results` |

## [tests]
| key | default | meaning |
|---|---|---|
| `command` | `python3 tests/run.py --suite {suites} --jobs {jobs} --json {out} --quiet` | argv; `{suites}` comma list, `{jobs}`, `{out}`, `{tree}` |
| `filter_args` | `["--filter", "{glob}"]` | appended once per test id |
| `filter_escape` | `fnmatch` | escape `* ? [ ]` in ids as `[c]`; `none` to pass ids raw |
| `env` | `{}` | extra environment; values may use `{tree}` and `$VAR` |
| `timeout` | 3600 | seconds per invocation; a timeout reads as "no JSON" (ERROR) |
| `suites_dir` | `tests/suites` | each subdirectory is a suite |
| `suites` | `[]` | explicit suite list instead of listing `suites_dir` |
| `tests_tree` | `tests` | tree watched for changes on main |
| `link_untracked` | `["tests/suites", "tests/tools"]` | gitignored entries symlinked into worktrees |
| `source_root` | `tests/suites` | `<source_root>/<suite>/<rel>` sizes rank representatives (smallest first) |
| `quarantine` | `[]` | globs of flaky tests: never a regression, never queued |

**Output contract.** `{test_id: {status, reason, stage}}`. `test_id` = `<suite>/<rest>`.
`PASS` passes; `SKIP` is ignored; anything else is failing. A requested id missing from
the output is `MISSING`: it no longer runs (skip list, removed) and is dropped from
known.json, never counted as a regression. No JSON at all is `ERROR` for every id: it
counts as a regression at the gate (fail closed) and is never recorded in known.json.

## [paths]
| key | default | meaning |
|---|---|---|
| `code` | `["src/"]` | a candidate must change something here; must apply cleanly |
| `allowed` | `[]` | also taken, best effort: dropped on conflict |
| `forbidden` | `["tests/"]` | any edit here rejects the candidate |
| `junk` | `["__pycache__/", ".pyc"]` | never taken; tracked junk fails preflight |
Files outside `code`/`allowed` are silently left out of the candidate.

## [queue]
| key | default | meaning |
|---|---|---|
| `ladder` | `[["smoke", 6]]` | `[suite prefix, level]`, first match; priority = 10 x level + 3 log2(cluster size) - 4 x failures |
| `default_level` | 2 | |
| `keep_words` | `[]` | quoted words kept in signatures (language keywords) |
| `shard_size`, `max_shards` | 10, 6 | a masked signature of n tests gets min(6, n/10) shards; a concrete one (nothing masked) is never sharded |
| `max_test_attempts` | 3 | counted failures before a test is parked (a lost merge race is not one; a no-result death counts half) |
| `reps` | 3 | representatives per item |
| `gate_targets` | 20 | members the gate checks for a flip |
| `feature_after` | 2 | counted failures on a signature before feature mode |

## [gate]
| key | default | meaning |
|---|---|---|
| `always_suites` | `["smoke"]` | every known test of these runs at every gate |
| `cheap_suites` | `["smoke"]` | sampled on every federated node |
| `compat_command` | `[]` | argv in the gate tree per candidate, `{tree}`; non-zero rejects; preflight checks it exists |
| `batch`, `sample` | 4, 150 | candidates stacked per gate run; known-passing sample size |
| `full_every` | 200 | merges between full refreshes (bisect + revert) |
| `quick_every` | 25 | merges between quick refreshes of `quick_suites`, bisected over those merges only and reverted; 0 = off |
| `idle_refresh` | true | full refresh when the queue drains with merges since the last one; a drained queue otherwise ships their regressions (2026-10-12: TinyCC 333 to 35 after the last refresh) |
| `quick_suites` | `[]` | suites a quick refresh runs; `[]` = `cheap_suites`; on a partitioned node, only its own plus the cheap ones |
| `recheck_max` | 1500 | cluster members re-run after each merge |
| `max_main_races` | 3 | re-gates when main moves mid-gate, then "main kept moving" |
| `coauthor` | Haiku 5.5 | `Co-Authored-By:` trailer on swarm commits; `""` for none |

## [git], [worker], [run], [federation], [compare]
| key | default | meaning |
|---|---|---|
| `git.author_name/email` | git config of root | author of swarm commits |
| `worker.system_prompt` | — | path; required for real runs |
| `worker.schema` | bundled | result JSON schema |
| `worker.model`, `effort` | `haiku`, `""` | first attempt; later attempts and feature work run at `high` |
| `worker.timeout`, `per_task_usd` | 1500, 2.0 | |
| `worker.feature_timeout`, `feature_usd` | 3600, 5.0 | feature-mode budget |
| `worker.tools`, `allow` | `Read,Grep,Glob,Edit,Write,Bash`, `["Edit(//tmp/**)", "Bash"]` | plus `Edit(/<worktree>/**)` and the scratch dir, always |
| `worker.scratch` | `/tmp/{id}` | deleted when the worker is reaped |
| `worker.repro_command` | `""` | per representative, `{suite}` `{test}` |
| `worker.task_footer`, `feature_mode` | generic | text appended to every task / to feature tasks (`{scratch}`) |
| `worker.preflight_files` | `[]` | must exist before launch |
| `run.concurrency`, `max_load`, `min_free_gb`, `idle_max`, `poll` | 24, 3 x CPUs, 3.0, 14400, 5 | |
| `federation.remote`, `prefix` | `""`, `swarm/` | transport repo and branch namespace |
| `federation.poll`, `rebase_every` | 180, 900 | hub poll / sibling rebase seconds |
| `federation.setup_command` | `[]` | project bootstrap run by `sibling_setup.sh` (`$SWARM_SIBLING` = name) |
| `compare.arms` | haiku, haiku-high, sonnet | `{name: {model, effort}}` |
| `compare.usd_cap`, `sample` | 3.0, 120 | |

## State files (state_dir)
| file | content |
|---|---|
| `ledger.jsonl` | append-only snapshots, last line per id wins: id, key, signature, tests, targets, base, status (launched, finished, merged, rejected, failed, reverted), cost_usd, turns, denials, result, merged_commit, reason, feature, rebase_of, effort |
| `known.json` | `{test_id: {status, reason, stage, commit}}`: what the gate compares against |
| `baseline.json` | last full run: commit, time, suite counts, suite_names, tests-tree stamps |
| `results/<commit>.json`, `history.jsonl`, `merges.jsonl`, `reverts.jsonl`, `counters.json` | observations, pass counts over time, merge order for bisect |
| `events.jsonl` | harness events for the stats timeline |
| `epoch.json` | attempt epoch set by `unpark` |
| `loop.pid` | the running loop (one per state dir) |
| `tasks/<id>/` | task.jsonl, runner.log, fanout/ (runner ledger), patch.diff |
