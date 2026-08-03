# Auditing — can this check fail?

For a check suite that already exists: tests, a linter config, a CI job, a
calibration script. The question is not whether it passes. It is whether it
*could* fail.

Run this when a suite passes on the first try, when it has never gone red, when
it was written by the same process that produced the code, or before you rely
on it to gate something that matters.

---

## Pass 1 — name the failing input

For each assertion, name a concrete input that makes it fail.

If you cannot, it is decoration. Two things usually explain it:

- **The assertion is independent of the subject.** "The screenshot contains at
  least N distinct colours" is equally true of an unchanged frame, so it passed
  for all seven keyboard shortcuts while none of the keystrokes were being
  delivered. Two tells were visible and read as success: every state reported
  the *identical* count, and the suite passed first try.
- **The assertion restates the implementation.** `assert total == sum(xs)`
  where `total` is computed as `sum(xs)`. Tautologies pass forever.

Replace both with **differential** checks: the state must change when it should,
and an operation applied twice must return to the byte-identical original.

---

## Pass 2 — check the oracle's range

For every check anchored on an external value, ask what range that anchor
covers, and compare it to the range you actually operate in.

The failure is quiet and total: past the end of the anchor's range there is no
check at all, and the suite reports the same green it does everywhere else.

A published quantizer table stopping at 5 bits meant a 16% error at 8 bits was
unreachable by the table comparison — and the error's direction *loosened* a
downstream check that depended on the same quantity, so the defect made the
suite more permissive rather than less.

Ask also: does the error direction of a wrong anchor tighten or loosen the
checks downstream of it? A wrong value that loosens is far more dangerous than
one that tightens, because tightening announces itself.

---

## Pass 3 — mutate

```bash
python3 scripts/mutate.py --target src/thing.py -- <your gate command>
```

Every survivor is a behaviour nothing checks.

**First, disable any on-disk cache the subject keeps.** If the code under test
caches artifacts keyed on the *problem* (`grid_m8_K65536.npz`) rather than on
the *method*, a mutation of the producing code changes nothing observable: the
gate loads the pre-mutation artifact and reports green. Every mutation to the
trainer then "survives" for a reason that has nothing to do with the gate, and
the survivor count is noise. Point the cache at a temporary directory for the
mutation run. This is the same anti-pattern the gate section warns about, and
it is far more damaging here because it inflates rather than hides.

**Budget for it.** `mutate.py` runs the gate command once per mutation, so a
90-second gate over 100 sites is two and a half hours. That pressure is what
produces a fast gate variant — which is fine, as long as you remember that a
known-bad validated only in the fast variant may not be bad at full size, and
that the fast variant's reduced dimensions may make whole classes of mutation
unobservable. Record which ones in the gate's stated coverage limits.

**Reading the report.** Survivors cluster, and the cluster is the diagnosis:

- Survivors on one function → that function is untested. Usually the fix is
  one test, not one assertion.
- Survivors on comparison operators only → boundaries are untested. Add cases
  at, just below, and just above each threshold.
- Survivors on numeric literals → thresholds and tolerances are unpinned.
  This is where *slack wider than the defect* lives: if the constant can move
  and nothing notices, it was never doing work.
- Survivors on `and`/`or` → compound conditions are exercised on one branch
  only.

**Legitimate survivors exist.** Equivalent mutants (a change with no
observable effect), and code genuinely outside the gate's remit. Do not chase
them to zero — move them to the gate's stated coverage limits, which converts
an invisible hole into a written one. Write down *why* each is equivalent: an
unexplained survivor and an equivalent mutant look identical in a report, and
six months later nobody can tell which they are looking at.

**Survivor line numbers are ephemeral — pin permanent fixtures by content.**
The report says `grids.py:166`, and that reference is correct for exactly as
long as nobody edits the file above line 166. If you promote survivors into a
standing fixture (recommended — see the meta-check below), locate each target
by a unique snippet of the line, not by its number. A fixture pinned by line
survived until an upstream refactor shifted one file by ~50 lines, then failed
with "line 206 does not contain '*'" — an error about the fixture, not about
the subject, which is the most confusing kind to receive.

---

## Pass 4 — tolerances

For every numeric tolerance, ask where it came from.

If the answer is "it seemed reasonable," measure instead: run the thing several
times, observe the spread, set the threshold outside the spread — then check
that the *known-bad* also falls outside it. A tolerance that admits both the
good and the bad case is worse than none, because it reports PASS with
authority.

A 2% slack once let a deliberately under-trained model through a check its
properly-trained counterpart cleared by 2.6%. The slack was not derived from
anything; it was generosity. Tightening it to a margin the real subject clears
comfortably and the bad one does not restored the check's whole point.

---

## Pass 5 — provenance

- Did any expected value come from running the code under test? Then it is a
  changelog entry, not an oracle.
- Are cached or fitted artifacts keyed on the *method* that produced them, or
  only on the problem? A cache keyed `(m, K)` cannot notice that the trainer
  changed, and will serve stale artifacts indefinitely — including across a
  deliberate cache wipe, if a background writer loses the race.
- Can you tell a stale artifact from a fresh one by looking at it? If the only
  difference is schema drift you happened to notice, add a version stamp.

---

## Pass 6 — the meta-check

Break something on purpose and confirm the suite goes red.

Not "invoke it and confirm the step appears in the output" — that catches a
check that was never wired up, and says nothing about one that is wired up and
toothless. Actually break the subject, actually watch it fail, actually put it
back.

Then keep it: a permanent known-bad fixture is worth more than the transient
experiment, because it re-runs forever and catches the day someone widens a
tolerance for an unrelated reason.

---

## Reporting an audit

Say which of these is true, per check:

- **CONFIRMED** — a named input makes it fail, and it was observed failing.
- **PLAUSIBLE** — a named input should make it fail, not yet observed.
- **CANNOT FAIL** — no input makes it fail. Delete or repair.
- **BLIND** — it can fail, but not on the regime that matters. State the gap.

A suite of forty checks where thirty-eight are CONFIRMED and two are BLIND is
in far better shape than forty green ones of unknown status, and the audit is
only worth writing down at that resolution.
