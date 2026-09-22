# Opus 5 and Opus 5.5

Opus 5.5 has not been sampled; apply this file to it until it has.

## Editing a draft this model wrote

Expect a clean lint report and a heavily staged draft. Do not let the report
shorten the pass: spend it on steps 2b, 3 and 4.

1. Read every header first. Rewrite each verdict into a label (entry 7). Expect
   most of them to be verdicts, some two sentences long: *A cache doesn't make
   things faster. It makes some things faster and everything else slower.*
2. Read the last sentence of every paragraph next. If it restates the paragraph
   as a maxim, delete it (entry 12): *Read-through caching is a p50 optimization
   sold as a latency optimization.* Keep it only if it states a fact the
   paragraph has not.
3. Split any sentence where `and` or `so` joins a fact to a generalisation of
   that fact (entry 39): *…a second system that can be slow in new ways, and your
   users only ever feel the slow ways.*
4. Cut significance designations the linter's noun list misses (entry 3): *the
   real fix*, *the actual heuristic*, *that was the trap*.
5. Keep every technical claim. The argument under the staging is usually sound;
   run `declaude_diff.py` to confirm the cuts removed none of it.

## Running the pass as this model

- After rewriting several instances of one flagged shape, check whether the
  rewrites all landed on the same new shape. Verdict headers rewritten into
  nominalized headers (entry 41) is the usual one.
- Read your rewrite once against entries 43 to 47 alone. Your clean prose
  defaults to that register: `plainly`, `quietly`, `byte-identical`, `nothing`
  standing in for a search.
- Lint the finished artifact, including your own annotations, summary and
  change list, not only the text you edited.
- If you also wrote the draft, run step 2b in a subagent or separate context.
  In PR #771 a pass by the drafting model let through six sentences the reader
  then flagged.

Evidence: `oaustegard/experiments` `model-register-drift/` (two samples, one
prompt) and claude-skills PRs #769, #771, #779.
