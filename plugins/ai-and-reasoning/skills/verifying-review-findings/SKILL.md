---
name: verifying-review-findings
description: "Checks each finding from a code review against the code it cites and keeps only the ones that hold. Drops findings whose quoted code is not in the file, then asks TypeSafe's Jev decision model whether the code shown really has the claimed defect, returning P(confirmed), P(refuted), a severity distribution and whether the proposed fix works. Use for \"verify these review findings\", \"filter false positives from the review\", \"is this bug real\", \"double-check the reviewer's claims\", \"get a second opinion on these findings\", a pre-commit or CI gate that blocks only on confirmed high-severity findings, or a finder-then-verifier review with a different model as the verifier."
metadata:
  version: 0.1.1
---

# Verifying review findings

A model that reviews code for defects also invents them: it misreads a guard
ten lines up, a loop bound, or a lock the caller holds. This skill splits the
review into two roles, as the open-source reviewer bluesky-social/roast does.
A **finder** (you, the `code-review` skill, any reviewer) writes each finding
with a verbatim quote of the code it is about. A **verifier** from a different
model family then reads that code and confirms or refutes the claim.

The verifier is Jev, a decision model from TypeSafe. It answers typed questions
(yes/no, multiple choice, ordered scale) with a probability for every answer in
about 0.3 s. Jev is not a Claude model, so when Claude finds and Jev verifies,
the verifier is less likely to share the finder's blind spots. Below,
P(x) means the probability Jev gives to answer x.

`scripts/verify.py` does the following for each finding:

1. **Grounding.** The quote must occur in the file, compared with runs of
   whitespace collapsed. A finding with no quote, or a quote that is not in
   the file, is dropped before Jev sees it.
2. **The window.** The verifier sees a *window* of the file: the top-level
   block (function, class, statement) that contains the quote, with at least
   12 lines on each side, capped at 160 lines. Lines are numbered and the
   quoted ones are marked `>`. With `--diff`, the file's diff hunks go along
   too.
3. **Three questions to Jev**, one call per finding, in parallel:
   - verdict: `confirmed`, `refuted` or `insufficient_context`
   - severity if the defect is real, on the scale `info`, `low`, `medium`,
     `high`, `critical`
   - when the finding proposes a fix, whether the fix works
4. **Thresholds.** P(refuted) of at least 0.7 drops the finding
   (`--refute-at`). P(confirmed) of at least 0.7 confirms it (`--confirm-at`).
   Anything else is `uncertain`. Only a refutation removes a finding; a
   verifier that is unsure keeps it.

## When NOT to use this skill

| Situation | Use instead |
|---|---|
| Nobody has looked for defects yet | `code-review` (or any reviewer) first; this skill only judges findings that exist |
| Checking that a README or docstring still matches the code | `verifying-claims` |
| An adversarial read of a whole deliverable (prose, analysis, a PR's design) | `challenging` |
| A routing, triage or yes/no question that is not about a code finding | `deciding-with-confidence`, or the Muninn `decide` tool directly |
| Building a deterministic check that must be able to go red | `gating` |
| The claim is about runtime behaviour the code cannot show (performance, a flaky test, production data) | run it; a verifier reading code can say `insufficient_context` at best |

Stop the run when most findings come back `uncertain` with reason
`needs_more_context`: the evidence for those claims lives outside their
windows (in a caller, another file, a config). Verify those findings by
reading the code yourself.

## Procedure

Throughout, `V=/mnt/skills/user/verifying-review-findings/scripts/verify.py`.

1. **Write the findings as a JSON list.** `file` (relative to the repository
   root) and `code_quote` are required. Copy the quote character for character
   from the file, one to six lines; a paraphrase is dropped.

   ```json
   [{"id": "1", "file": "src/util.py", "line": 6,
     "description": "Off-by-one: the loop skips the last element.",
     "code_quote": "for i in range(len(items) - 1):",
     "fix": "for i in range(len(items)):", "severity": "high"}]
   ```

   The other fields are optional. `id` defaults to the item's position.
   `line` picks between several matches of the same quote. `description` is
   the claim Jev judges. `fix` adds the fix question. `severity` is the
   finder's own estimate and is passed to Jev as a claim. Findings in the
   `ReportFindings` shape (`summary` and `failure_scenario` instead of
   `description`) are accepted too. When you are the finder, emit this shape
   directly.

2. **Pick the path.** `--transport auto`, the default, uses the first of
   `jev` and `gateway` whose credentials are set.

   | Path | Needs | How |
   |---|---|---|
   | Jev direct (`jev`) | `TYPESAFE_API_KEY`, a TypeSafe API key | `run` (step 3a) |
   | Jev via Cloudflare Workers AI (`gateway`) | `CF_ACCOUNT_ID` and `CF_API_TOKEN`, optionally `CF_GATEWAY_ID` | `run`; pass `--transport gateway` when both paths have credentials |
   | Muninn `decide` tool, which calls Jev | the Muninn MCP connector in the session | `emit`, then `apply` (step 3b) |
   | Claude Haiku via `deciding-with-confidence` | that skill installed next to this one | `run --transport decider`; the verifier is then also Claude |

3. **Run it.**

   a. With credentials in the environment:
   ```bash
   python3 $V run findings.json --repo . --format md      # default output is JSON
   git diff main... > /tmp/d.diff && python3 $V run findings.json --diff /tmp/d.diff
   python3 $V run findings.json --ref HEAD~1               # read files at a git ref
   ```

   b. Through the Muninn `decide` tool:
   ```bash
   python3 $V emit findings.json --out batch.json
   ```
   `emit` saves the grounded findings to `batch.json` and prints the Jev
   requests, one per surviving finding, each as `{"id", "state",
   "questions"}`. Call `decide` once per request, passing its `state` and
   `questions` unchanged; the calls are independent, so send them together.
   Save the replies in `answers.json` as an object that maps each finding's
   `id` to the full text `decide` returned, then:
   ```bash
   python3 $V apply batch.json answers.json --format md
   ```

4. **Read the report.** The top level has `complete` (false when any finding
   could not be verified), `counts` per status, and `gate`. Each finding keeps
   its input fields and adds:
   - `status`: `confirmed`, `uncertain`, `dropped`, or `unverified` (Jev was
     not reached or replied in an unexpected shape)
   - `reason`: why it is not confirmed. One of `missing_code_quote`,
     `ungrounded_code_quote`, `file_not_found`, `refuted_by_verifier`,
     `split_verdict`, `needs_more_context` (`insufficient_context` was the
     largest verdict), `no_answer`, or `verifier_error: ...`
   - `verdict`: the three verdict probabilities
   - `severity`: `probabilities` per level, and `expected`, the level nearest
     the probability-weighted average
   - `fix_ok`: the probability that the fix works
   - `claimed_severity`: the finder's own `severity` from the input
   - `fingerprint`: a hash of the file and the whitespace-collapsed quote. Use
     it to match a finding across runs, never to suppress one: two different
     claims about the same lines share a fingerprint.

5. **Act on it.**
   - Report `confirmed` findings as findings.
   - Report `uncertain` ones separately and read their code yourself; the
     verifier's mistakes cluster there.
   - Leave `dropped` findings out, but give their count and reasons so a
     reader can recover one that was refuted wrongly.
   - When a confirmed finding has `fix_ok` under 0.5, rewrite the fix before
     proposing it.

6. **Gate a commit or CI step** with `--fail-on LEVEL` (any severity level).
   Exit codes:

   | Code | Meaning |
   |---|---|
   | 0 | every finding verified, and no gate tripped |
   | 1 | a confirmed finding has P(severity at least LEVEL) of at least `--severity-at` (default 0.5) |
   | 2 | bad input, or no transport available |
   | 3 | some finding is `unverified`: the run is incomplete, not clean |

   A pre-commit hook that should not block on an outage can let the commit
   through on 3, as long as the hook prints the report so the gap is visible:
   ```bash
   python3 $V run staged.json --fail-on high --format md; rc=$?
   [ $rc -eq 3 ] && echo "verify: incomplete run, commit allowed" >&2 && rc=0
   exit $rc
   ```

## Earned exceptions

| Default | Change it when | Keep it when |
|---|---|---|
| `--refute-at 0.7` | a missed defect costs more than reading a false one (security review, release gate): raise it toward 0.9 so fewer findings are dropped | the review is advisory, and noise is what makes people stop reading |
| The gate counts only confirmed findings | the gate guards something irreversible: lower `--confirm-at` so more findings count as confirmed | `uncertain` findings get a human look before merge |
| One window per finding | the claim depends on another file (a caller, a type, config) | the evidence is in the same top-level block, which covers most of what reviewers flag |

## Common failure modes

- **`verify: no Jev transport`, exit 2** → neither `TYPESAFE_API_KEY` nor the
  Cloudflare pair is set. Use the `emit`/`apply` path, or `--transport decider`.
- **Every finding `dropped` with `ungrounded_code_quote`** → the finder quoted
  from memory or reformatted the code, or `--repo` points at the wrong
  checkout. Run `grep -F` with one quote against the file to tell which.
- **`file_not_found` for files that exist** → `file` is resolved against
  `--repo` (default: the current directory). A path that leaves the
  repository is treated as missing on purpose.
- **`unverified` with `verifier_error: HTTP 4xx`** → check the error text.
  When it names the input length, the window was too long for Jev's default
  context: lower `MAX_LINES` (the 160-line cap, a constant at the top of
  `verify.py`). The report says `complete: false` until those findings are
  re-run.
- **`unverified` with `no_answer` after `apply`** → `answers.json` has no
  entry for that finding's `id`. Ids are strings: `"1"`, not `1`.
- **A high `severity.expected` on a dropped finding** → severity answers "how
  bad if real". Read it only on findings that survive.

## Verification

```bash
python3 -m pytest /mnt/skills/user/verifying-review-findings/tests -q   # offline, no network
python3 $V eval /mnt/skills/user/verifying-review-findings/assets/eval.jsonl
```

`eval` runs 36 labelled findings (16 real defects, 16 false findings, 4
quotes not in the file) and prints the counts. Grounding is deterministic,
so `ungrounded_dropped` must be 4/4. Jev's part gave `real_kept` 16/16 and
`false_dropped` 11/16 with jev-1.14.0 on 2026-11-07. A lower count means the
Jev version or the window settings changed; compare per item with
`--out results.jsonl`.

A **bad success** is a report with `complete: true` in which every finding is
`confirmed` near 1.0, including ones you know are false: Jev is judging the
description without the code. Check that `state.code` in the requests `emit`
prints holds the numbered window.

The eval's per-item results, the threshold sweep and what it does not cover
are in `references/method.md`.

## Diagnosed failures

- **2026-11-07, eval item `ts-04`:** a finding claimed a race condition in
  synchronous single-threaded JavaScript. Jev confirmed it at 0.89, the only
  false finding confirmed. No threshold catches a confident error like this.
  Read the code behind any concurrency claim about single-threaded code yourself.
- **2026-11-07, eval items `py-05` and `sh-03`:** the evidence that refutes
  each claim was in the same file but in a different function, outside the
  window. Neither was dropped. `sh-03` came back `uncertain` with
  `needs_more_context` (P(insufficient_context) 0.82). `py-05` came back
  `uncertain` with `split_verdict` (P(confirmed) 0.55, P(insufficient_context)
  0.40). Both outcomes are correct: the finding stays in the report, flagged
  for a human to read.
