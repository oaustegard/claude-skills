# declauding

declauding is a skill that rewrites prose that reads as model-written into the
plain technical prose that a person would have written. Before handing the text
back, it checks the rewrite against the draft for any number, name, quotation,
hedge or ranking that the edit dropped or added.

Install it like any skill in [oaustegard/claude-skills](https://github.com/oaustegard/claude-skills),
by copying this directory into the agent's skills folder. The agent then runs it
on a draft of prose that someone else will read, and when asked to "declaude",
"de-slop" or "humanize" a text. It returns the rewritten text, or, if you ask for
the annotated version, an HTML file that marks each edit with the original and
the reason for it.

## The register

"Register" means the style a piece of prose is written in.
[`references/register.md`](references/register.md) catalogues 56 tics that mark
prose as model-written. Each entry gives the tell (the surface pattern to look
for), why it marks model prose, the fix, and a before-and-after from real text. They fall into five families:

| Entries | Family | Example |
|---|---|---|
| 1–23, 37–42 | **Staging:** the sentence is built so the reader feels a finding arrive instead of being told it | *It is not a wrong answer. It is a non-answer.* |
| 24–36 | **Encyclopedic and chatbot:** stock phrasing with nothing staged: inflated verbs, participle tails, forced triads, chatbot sign-offs | *Gallery 825 serves as the exhibition space and boasts 3,000 square feet.* |
| 43–47 | **Flat certainty:** an adverb or absolute negative stands in for evidence | *The retry is provably safe.* |
| 48–52 | **Confiding essayist:** staging aimed at the reader's trust | *Let's be honest: I won't pretend the first run was clean.* |
| 53–56 | **Compressed syntax:** a claim packed into fewer words than a reader can parse | *the others check behaviour the old code never reached* |

The staging entries that come up most often:

| # | Tic | Example |
|---|---|---|
| 2 | Negation-first reveal | *It is not a wrong answer. It is a non-answer.* |
| 3 | Significance designation | *It is the leg that answers the actual question.* |
| 4 | Abstraction agency | *Median hides it.* / *The table shows it.* |
| 5 | Deferred noun | *Five of those six rows are one cluster. The sixth is not.* |
| 7 | Coy or thesis-shaped header | *What "exhausted" means* / *The one gap that does clear the bar* |
| 11 | Straw-man knockdown | *"It thinks twice as long" is the obvious reading, and it is wrong.* |
| 12 | Aphoristic closer | *It is the kind of number that looks like evidence and is not.* |
| 15 | Fragment cadence | *Six legs. One GPU, one server build, one sampler, one question set.* |
| 37 | Dressed metaphor | *That is information loss wearing the costume of a style fix.* |

## Workflow

[`SKILL.md`](SKILL.md) has the full procedure. In short:

1. Read the whole draft first, and note where it contradicts itself.
2. State the draft's point in one sentence. If it has none, get one from the
   author and rebuild around it.
3. Run the linter, then the structural review in a subagent or fresh session
   that did not write the draft.
4. Ask of each sentence whether it states a finding or stages one, then check
   headers, paragraph breaks and closers.
5. If the draft describes something that just changed, hand it to a subagent
   that has not seen the old version, and fix whatever it trips over.
6. Run the preservation diff, and report contradictions to the author instead of
   fixing them.

## Scripts

Run these from the skill's directory.

```sh
python3 scripts/declaude_lint.py DRAFT.md --skip-quoted    # tells, line by line
python3 scripts/declaude_review.py DRAFT.md                # headers, openers, closers
python3 scripts/declaude_rank.py DRAFT.md --top 15         # most staged sentences first
python3 scripts/declaude_diff.py SOURCE.md REWRITE.md      # what the edit lost or added
python3 scripts/fresh_eyes.py packet README.md             # prompt for a newcomer read
```

The linter reads Markdown, plain text and HTML, and needs only the standard
library and Python 3.9 or later. It exits 1 when it finds candidates, so it can run as a pre-commit hook.
Each hit still needs a reader's judgment, and no regex reaches a staged paragraph
or closer, so a clean report does not mean the draft is clean. `--skip-quoted`
ignores blockquotes, table rows, code and italic spans, where a document like
this one quotes bad prose as examples.

The structural review sends only the headers, the opening and closing sentences
and any isolated one-line paragraphs to a model: Gemini with `GEMINI_API_KEY`,
Claude with `ANTHROPIC_API_KEY`, and with neither it prints the prompt for an
agent to answer. The ranker needs torch and transformers. The diff counts
constructions rather than words: rewriting "the format that most invites staged
reveals" as "more than most formats do" keeps the word *most* and loses the
ranking.

When adding a lint rule, check that it reports zero on `tests/sample-clean.md`,
which is human-written prose. [`references/corpus.md`](references/corpus.md) and
[`references/preservation.md`](references/preservation.md) have the measurements
behind the diff, the ranker, and the linter's `corpus-register` line, which
measures how much of a draft uses the vocabulary of the flat-certainty family.
Above about 1.0 per 100 words, read entries 43 to 47. A high score locates the
register and does not mean a model wrote the draft.

## Overcorrection

Prose stripped of confidence, rhythm and opinion is worse than the tics. The
skill keeps certainty that has evidence behind it, first-person judgment, varied
sentence length, digression and the author's own habits. It does not compress
what remains: a rewrite that is shorter and harder to parse fails entries 53 to
56. A flagged shape sometimes carries a claim, and
[`references/exceptions.md`](references/exceptions.md) lists when each one is
earned.

The rewrite never adds a name, number, date, quote or citation that the source
or the author did not supply. When the author provides a sample of their writing,
the sample overrides the rules.

## Model profiles

[`references/models/`](references/models/) says what drafts from Opus 4.6 to 5.5,
Sonnet 4.6 and 5, Haiku 4.5 and Fable 5.1 tend to carry, and how each model goes wrong when it runs
the pass itself.

## Sources

Entries 1 to 23 come from a register pass on a published benchmark post, and 37
to 42 from passes on drafts and a reference page in this repository. Other families draw on
[blader/humanizer](https://github.com/blader/humanizer) and the Wikipedia AI
Cleanup project's [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)
(24–36), Louis Abraham's [load-bearing](https://github.com/louisabraham/load-bearing)
clusters of pull request descriptions (43–47), Simon Willison's
[llm-cliche-highlighter](https://github.com/simonw/tools/blob/main/llm-cliche-highlighter.html)
(48–52), and Clark, Martin and Mahowald,
[arXiv 2610.29162](https://arxiv.org/abs/2610.29162) (53–56).
[`CHANGELOG.md`](CHANGELOG.md) has the history of each addition.

Related skills: [challenging](../challenging) runs an adversarial review of a
draft's voice and returns findings rather than text;
[crafting-instructions](../crafting-instructions) covers prompts, which have a
different target register.
