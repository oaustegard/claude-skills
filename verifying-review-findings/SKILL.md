---
name: verifying-review-findings
description: "Checks each finding from a code review against the code it cites and keeps only the ones that hold. Drops findings whose quoted code is not in the file, then asks TypeSafe's Jev decision model whether the code shown really has the claimed defect, returning P(confirmed), P(refuted), a severity distribution and whether the proposed fix works. Use for \"verify these review findings\", \"filter false positives from the review\", \"is this bug real\", \"double-check the reviewer's claims\", \"get a second opinion on these findings\", a pre-commit or CI gate that blocks only on confirmed high-severity findings, or a finder-then-verifier review with a different model as the verifier."
metadata:
  version: 0.1.0
---

# Verifying review findings

A reviewer model that finds defects also invents them: it misreads a guard ten
lines up, a loop bound or a lock the caller holds. This skill applies the
finder/verifier split from bluesky-social/roast. The finder (you, the
`code-review` skill, any reviewer) writes each finding with a verbatim code
quote. `scripts/verify.py` then:

1. **Grounds** every finding: the quote must occur in the file, compared with
   whitespace collapsed. A missing or paraphrased quote is dropped before any
   model sees it (`missing_code_quote`, `ungrounded_code_quote`).
2. **Shows the verifier the code**: the enclosing top-level block around the
   quote (padded to 12 lines each side, capped at 160), line-numbered, with the
   quoted lines marked `>`, plus the file's diff hunks with `--diff`.
3. **Asks Jev three typed questions** per finding: a verdict (`confirmed`,
   `refuted`, `insufficient_context`), a severity score (info to critical) and,
   when a fix is given, whether it works. One call each, in parallel, about
   0.3 s apiece.
4. **Applies thresholds**: P(refuted) at or above 0.7 drops the finding,
   P(confirmed) at or above 0.7 confirms it, anything else stays as
   `uncertain`. Only refutation removes a finding; an unsure verifier keeps it.

Jev is TypeSafe's own model, not Claude, so a Claude finder with a Jev verifier
keeps the cross-model independence the pattern depends on.

## When NOT to use this skill

| Situation | Use instead |
|---|---|
| Nobody has looked for defects yet | `code-review` (or any reviewer) first; this skill only judges findings that exist |
| Checking that a README or docstring still matches the code | `verifying-claims` |
| An adversarial read of a whole deliverable (prose, analysis, a PR's design) | `challenging` |
| A routing, triage or yes/no question that is not about a code finding | `deciding-with-confidence`, or the Muninn `decide` tool directly |
| Building a deterministic check that must be able to go red | `gating` |
| The claim is about runtime behaviour the code alone cannot show (performance, a flaky test, production data) | run it; a verifier reading code will answer `insufficient_context` at best |

Abandon a run when most findings come back `uncertain` with
`needs_more_context`: the defects live across files and the window cannot show
them. Re-run with the files that hold the evidence named in the findings (one
finding per file the claim depends on), or verify those by hand.

## Procedure

1. **Write findings with verbatim quotes.** One JSON list; `file` and
   `code_quote` are what grounding needs. Copy the quote character for
   character from the file (one to six lines); a paraphrase is dropped.

   ```json
   [{"id": "1", "file": "src/util.py", "line": 6,
     "description": "Off-by-one: the loop skips the last element.",
     "code_quote": "for i in range(len(items) - 1):",
     "fix": "for i in range(len(items)):", "severity": "high"}]
   ```

   `summary` and `failure_scenario` (the `ReportFindings` shape) are accepted
   in place of `description`. When you are the finder, instruct yourself or the
   reviewing subagent to emit exactly this shape.

2. **Pick the path.**

   | Path | Needs | Command |
   |---|---|---|
   | Jev direct | `TYPESAFE_API_KEY` | `verify.py run findings.json` |
   | Jev via Cloudflare Workers AI | `CF_ACCOUNT_ID`, `CF_API_TOKEN` (optional `CF_GATEWAY_ID`) | same; `--transport gateway` to force it |
   | Muninn `decide` tool | the Muninn connector, no key in the shell | `emit` then `apply` (step 3b) |
   | No Jev at all | `deciding-with-confidence` installed beside this skill | `--transport decider` (Claude Haiku: loses the cross-model independence) |

3. **Run it.**

   a. With a key in the environment:
   ```bash
   V=/mnt/skills/user/verifying-review-findings/scripts/verify.py
   python3 $V run findings.json --repo . --format md
   git diff main... > /tmp/d.diff && python3 $V run findings.json --diff /tmp/d.diff
   python3 $V run findings.json --ref HEAD~1     # read files at a git ref
   ```

   b. Through the Muninn `decide` tool:
   ```bash
   python3 $V emit findings.json --out batch.json   # prints {"requests": [{id, state, questions}]}
   ```
   Call `decide` once per request with its `state` and `questions` unchanged,
   all in one message. Save the replies as `{"<id>": "<reply text>"}` in
   `answers.json`, then `python3 $V apply batch.json answers.json --format md`.

4. **Read the report.** Each finding gets `status` (`confirmed`, `uncertain`,
   `dropped`, `unverified`), `reason`, `verdict` (the three probabilities),
   `severity.probabilities` and `severity.expected`, `fix_ok` (P the fix
   works) and a `fingerprint`. The fingerprint hashes the file and the
   whitespace-collapsed quote: use it to match a finding across runs, never to
   suppress one, because two different claims about the same lines share it.

5. **Act on it.**
   - Report `confirmed` findings as findings.
   - Report `uncertain` ones separately and look at them yourself; a split
     verdict is where the verifier's errors concentrate.
   - Leave `dropped` ones out, but say how many and why: a reader should be
     able to recover a wrongly refuted finding.
   - A `fix_ok` under 0.5 on a confirmed finding: rewrite the fix before
     proposing it.

6. **Gate a commit or CI step** with `--fail-on LEVEL`: exit 1 when a
   *confirmed* finding has P(severity at or above LEVEL) of at least
   `--severity-at` (default 0.5). Exit 3 means some finding was not verified
   (network, quota, odd reply): the run is incomplete, not clean. A pre-commit
   hook that should fail open treats 3 as a pass on purpose and prints the
   reason.

## Earned exceptions

| Rule | Banned when | Earned when |
|---|---|---|
| Drop at P(refuted) 0.7 | a missed defect costs more than reading a false one (security review, a release gate) | the review is advisory and noise is what makes people stop reading it; raise toward 0.9 for the opposite case |
| Gate on confirmed findings only | the gate guards something irreversible | `uncertain` findings get a human look before merge; otherwise gate on them too by lowering `--confirm-at` |
| Verifier sees one window per finding | the claim spans files (a caller, a type, config) | the evidence sits in the same function or file, which is most of what reviewers flag |

## Common failure modes

- **`verify: no Jev transport`** (exit 2) → no `TYPESAFE_API_KEY` and no
  Cloudflare pair. Use the `emit`/`apply` path through the Muninn `decide` tool,
  or `--transport decider`.
- **Every finding `dropped (ungrounded_code_quote)`** → the finder quoted from
  memory or reformatted the code, or `--repo` points at the wrong checkout.
  Check one quote with `grep -F` against the file before blaming the finder.
- **`file_not_found` on findings that exist** → paths are relative to `--repo`
  (default: the current directory). A path that climbs out of the repo is
  treated as missing on purpose.
- **`unverified (verifier_error: HTTP 4xx ...)`** on some findings → usually a
  window too long for Jev's default context. Lower `MAX_LINES` in the script
  or split the file's findings; the run reports `complete: false` meanwhile.
- **`unverified (no_answer)` after `apply`** → a reply was missing from
  `answers.json` or keyed by the wrong id. Ids are strings.
- **`severity.expected` looks high on a dropped finding** → severity answers
  "how bad if real". Read it only on findings that survive.

## Verification

```bash
python3 -m pytest /mnt/skills/user/verifying-review-findings/tests -q   # 27 pass, no network
python3 $V eval /mnt/skills/user/verifying-review-findings/assets/eval.jsonl
```

The eval prints how many real defects survived (`real_kept`), how many false
findings were dropped (`false_dropped`) and whether every ungrounded quote was
caught (`ungrounded_dropped` must be 4/4: that check is deterministic). The
2026-11-07 run gave `real_kept` 16/16, `false_dropped` 11/16; a drop below
14/16 real kept means the Jev version or the window changed. A
**bad success** is a report with `complete: true` whose findings all read
`confirmed` at P near 1.0, including ones you know are wrong: the verifier is
reading the finding's description instead of the code. Check that the `code`
field in `emit`'s requests holds the window, not an empty string.

## Measured performance

The skill was run on a 36-item synthetic eval on 2026-11-07 with jev-1.14.0.
All 16 real defects were kept, 11 of them as `confirmed`. Of the 16 false
findings, 11 were dropped, 4 stayed `uncertain` and 1 was confirmed at 0.89 (a
race claimed in single-threaded code). All 4 ungrounded quotes were dropped.
Expect roughly two thirds of a reviewer's false positives to disappear, and
expect an occasional confident false confirmation that no threshold catches.
`references/method.md` has the per-item results, the threshold sweep (0.7 is
the lowest drop threshold that kept every real defect, with a margin of 0.06)
and what the eval does not cover.

## Diagnosed failures

- **2026-11-07, first smoke run:** the finder's claimed `severity` string and
  the verifier's severity distribution shared one field, and the Markdown report
  crashed on dropped findings. The finder's value is now `claimed_severity`, and
  a test guards the split.
