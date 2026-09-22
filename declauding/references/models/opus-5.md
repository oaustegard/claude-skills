# Opus 5 and Opus 5.5

Opus 5 is measured. Opus 5.5 is not: until a sample exists, treat the Opus 5
profile as the prior for it, and add a measured profile when one exists (the
Extending section of `SKILL.md` says how).

## As author

Opus 5 prose passes the linter and fails the sentence pass. In the
model-register-drift run (`oaustegard/experiments`, `model-register-drift/`,
2026-08-23) it was third-cleanest of six models on `declaude_lint.py` at 5.04
candidates per 1000 words, and it was the only model whose staging score
cleared zero on blind pairwise judging (+1.39, 95% CI [+0.63, +2.36], Opus
judges, eight comparisons per sample). The same judges rated it the *least*
detectable as machine-written.

The tics concentrate in the aphorism and verdict family. Entry counts across
its two hand-adjudicated samples, most frequent first:

| entry | count | what it looked like |
|---|---|---|
| 12 aphoristic closer | 12 | "Read-through caching is a p50 optimization sold as a latency optimization." |
| 3 significance designation | 7 | "The real fix was an N+1 on one endpoint", "That's the actual heuristic." |
| 7 verdict header | 7 | "A cache doesn't make things faster. It makes some things faster and everything else slower." |
| 2 negation-first | 7 | "Caches don't sit beside your database; they change its workload into the worst possible mix." |
| 39 welded epigram | 5 | "it buys a second system that can be slow in new ways, and your users only ever feel the slow ways." |
| 16 em-dash gotcha | 5 | "Median latency improved both times we touched it — that was the trap." |
| 38 announce-then-deliver | 3 | "Now do the percentile arithmetic." |

Four of six headers were verdicts; six paragraphs ended on a line built to be
quoted. Along the Opus line the share of violations in this family rose
30% → 69% → 80% from 4.6 to 4.8 to 5. The hand count itself was retracted as a
score (it did not converge across passes); the composition and the blind
staging result are what stand.

What this changes in the workflow:

- A clean lint report on Opus 5 prose means less than usual. Budget the pass
  for steps 2b, 3 and 4.
- Read every header and every paragraph's last sentence before reading
  anything else. That is where most of the edits will be.
- For each closer, ask whether it states a fact the paragraph has not already
  stated. Most Opus 5 closers restate the paragraph as a maxim, and deleting
  them loses nothing. Check with `declaude_diff.py` anyway.
- Split every sentence joined by `and` or `so` where the second clause
  generalises the first (entry 39).
- The argument underneath is usually good. The Opus 5 sample in that run had
  the strongest technical content of the six. Cut the register and keep every
  claim.

Evidence is two samples, one prompt (a blog post about a counterintuitive
result, the format that most invites staging) and one judge family. One of the
two samples carried most of the staging signal; the other sat at the median.
Expect Opus 5 to stage heavily often, and do not assume it does every time.

## As editor

Three failures observed in declauding's own passes on the Opus line (claude-skills
PRs #769, #771, #779):

- **It flees one flagged shape into the next.** The 0.4.0 lint flagged verdict
  headers; the rewrite moved all four into nominalized headers (entry 41) and
  the linter then reported the document clean. When a pass rewrites several
  instances of one shape, check whether the rewrites all landed on the same new
  shape.
- **It lands in the flat-certainty register.** The flat, concrete,
  verdict-shaped prose a clean pass produces is the register of entries 43 to
  47: `plainly`, `quietly`, `refusal`, `byte-identical`, `nothing` standing in
  for a search. After your rewrite, read it once against those five entries
  specifically, and check the linter's `corpus-register` line.
- **It lints the subject and not its own frame.** An annotation, a summary of
  changes or a report about the edit is prose too. Two of nine announce-then-
  deliver instances in one session were in the frame around a critique. Lint
  the finished artifact, not only the part being edited.

When Opus 5.x is both author and editor, which is the default case for "run this
before publishing any draft Claude wrote", run step 2b in a separate context. In
PR #771 a pass by the drafting model passed six sentences its reader then
flagged.
