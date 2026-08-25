# What makes a skill work, measured

Source: Jiang et al. 2026, "Demystifying Agent Skills: Why They Work — Until
They Don't", arXiv:2608.14036. Controlled comparison of three arms — Raw (no
prior experience), Workflow Memory (cleaned prior traces), Skill (the same
traces distilled into a SKILL.md) — over Terminal-Bench 2.0, Terminal-Bench-Pro
and SkillsBench, with Codex + GPT-5.3-Codex and Gemini CLI + Gemini-3.1-Pro.
8,135 normalised trial records; 528 paired triples; a 12-mode taxonomy
human-validated at 95.8% exact agreement, Cohen's κ = 0.952.

Read this when a rule in SKILL.md seems arbitrary. Every one of them is here.

## Skills stabilise action; they rarely supply facts

Mechanism labels over the skill arm:

| Mechanism | Share |
|---|---|
| `procedural_anchor` — a usable procedure, ordering, checklist, tool sequence or verification plan | **65.7%** |
| `knowledge_injection` — domain knowledge the agent otherwise lacked | 4.5% |

A skill that is mostly facts is betting on the 4.5% path. That is what a
reference document is for, and there is nothing wrong with writing one — but
label it as reference and do not expect it to change execution.

## High-level framing is the weak form, and it is worse than nothing

Four conditions on the same 26 Terminal-Bench-2 tasks, five trials each:

| Condition | Success |
|---|---|
| Raw (no prior experience) | 50.0% |
| Short plan — three to five high-level steps derived from the instruction | **47.7%** |
| Test-first template — success conditions and checks, no procedure | 59.2% |
| Workflow Memory — cleaned raw traces | 62.3% |
| Skill — the traces distilled into SKILL.md | **79.2%** |

The short plan scored *below* the no-help baseline. "Specify the goal and let
the model infer the procedure" is exactly the short-plan condition. Concreteness
is doing the work: which setup steps, which tool sequence, which intermediate
checks, which pitfalls.

This does not license enumerating every keystroke. It means the procedural
content is the deliverable and the goal statement is the frame around it.

## What skills demonstrably fix

Failure modes, share of trajectories in each arm:

| Mode | Raw | Workflow | Skill |
|---|---|---|---|
| `environment_infrastructure_failure` | 5.3% | 1.7% | **0.2%** |
| `output_format_schema_mismatch` | 7.4% | 3.8% | **3.2%** |
| `background_service_lifecycle_failure` | 2.7% | 2.5% | **0.8%** |
| `shell_code_corruption` | 1.1% | 1.9% | **0.2%** |

Environment and tooling problems are the most skillable thing there is. Once a
setup sequence, dependency workaround or path convention is known, writing it
down nearly eliminates the failure. If a skill wraps a tool, its setup and its
failure signal belong in that skill.

## What skills do not fix

| Mode | Raw | Workflow | Skill |
|---|---|---|---|
| `algorithmic_logic_error` | 8.3% | 11.0% | 7.4% |
| `static_verification_without_runtime` | 12.5% | 12.5% | 11.7% |

A skill does not repair a wrong algorithm, and it does not make the agent run
the thing unless it says to run the thing. `static_verification_without_runtime`
moves by 0.8 points across the whole study — a skill that wants a runtime check
has to demand one explicitly, with the command.

## Skills introduce a failure mode of their own

| Mode | Raw | Workflow | Skill |
|---|---|---|---|
| `skill_guidance_misapplied_or_ignored` | 0.8% | 0.4% | **10.0%** |

A twelvefold increase. From the paper: "the skill contains plausible guidance,
but the agent applies it mechanically, misses a condition, or carries over
assumptions that no longer hold."

This is the cost of abstraction and it is paid on every skill. The only defence
is written scope: when the skill applies, when it does not, which of its rules
have earned exceptions, and when to abandon it mid-run. A skill with no
negative scope has not paid for its own abstraction.

## Verbosity has a measured cost

`timeout_budget_exhaustion`: 1.7% raw, **10.6%** workflow memory, 4.4% skill.
Workflow memory's characteristic failure is process overload — long
explorations, failed branches and low-level debugging paths that distract from
the decisive procedure. Distillation is what separates a skill from a trace
dump, and a SKILL.md that grows back toward the trace re-earns the trace's
failure mode.

Token cost on the matched 83-task intersection: Raw 555.7K, Workflow Memory
426.2K, Skill 521.5K. Skill buys its 5.5-point gain over Raw with context.

## Outcome labels during construction are worth 15–35 points

Skills built from the same trajectories, with and without success/failure
annotations visible to the author:

| Source pool | Gemini CLI, TB2, labelled | unlabelled |
|---|---|---|
| 5 successes, 0 failures | 0.7923 | 0.4231 |
| 3 successes, 2 failures | 0.7462 | 0.4000 |
| 0 successes, 5 failures | 0.4769 | 0.4308 |

Withholding the labels barely matters when every source trace succeeded, and
matters enormously once failures are in the pool — an unlabelled failure reads
as a procedure to copy.

The practical form: when a skill records something that went wrong, say it went
wrong, say when, and say what the signal was. "Diagnosed 2026-08-22: a
5,697-line gather was cut at line 120" is the labelled condition. "Use
`--orient` for reviews" alone is not.

Corollary from the same table: a skill distilled only from failures scores
*below* the no-skill baseline in nearly every configuration. A pile of
post-mortems is not a skill. The failures belong inside a procedure that works.

## Retrieval is a separate bottleneck

Embedding top-1 as the candidate pool grows, by distractor type:

| Pool size | Random distractors | Near-neighbour distractors |
|---|---|---|
| 5 | 97.7% | 70.5% |
| 100 | 84.1% | **53.4%** |

Semantic confusability, not pool size, is the dominant stressor. Every skill in
a personal catalogue is a near neighbour of the others by construction — they
are all things one agent does.

Measured on our own catalogue 2026-08-24 with
`scripts/skill_confusability.py` in `oaustegard/claude-workspace`: 40.0% top-1
over 92 skills, down from 83.4% at a pool of 5. `tree-sitting` lost all five of
its own canonical queries. `declauding` won four of five, and the reason is
visible in its description — it enumerates the literal phrasings a user types
("de-claude", "humanize this", "this reads like AI") instead of listing
features.

Recall stayed high while precision collapsed, in the paper and in our
measurement alike. The right skill is usually in the shortlist; it just is not
first. A description competes against its neighbours, not against nothing.

## Writing a description that wins its own queries

The four rules in SKILL.md, with the measurements behind each:

- **Lead with the unit of the question**, not the technology. "Symbol-level
  navigation of a local checkout" beats "AST-powered code navigation" because
  users ask about symbols, not about ASTs.
- **Enumerate literal phrasings a user types.** `declauding` scored 4/5 on
  its own queries in a 92-skill pool because its description contains
  "de-claude", "humanize this", "this reads like AI". `remembering` scored 2/5
  because its description is a list of feature nouns; the two queries it won
  were the two phrased in its own API vocabulary.
- **Separate from a neighbour by OMISSION, never by disclaimer.** Delete the
  neighbour's vocabulary from your description. Do not add a sentence saying
  the neighbour's job is not yours — that sentence moves you *toward* them.
  A retriever scores bag-of-meaning and has no notion of negation, so
  "does not debug a Docker build" reads as "Docker build".

  Measured 2026-08-25 on this catalogue, one clause at a time:

  | Description | Query | Cosine |
  |---|---|---|
  | `container-layer`, plain | "why is this docker build taking twelve minutes" | 0.427 |
  | + "does not debug an existing Docker build" | same | **0.475** |
  | `cloning-project`, plain | "I just cloned this repo, what does it do" | 0.472 |
  | + "not for cloning or exploring a git repo" | same | **0.571** |

  Both disclaimers made the false positive worse — the second by ten points,
  enough to steal the query outright. Rewriting the same four skills by
  omission instead took the catalogue from 72.0% to 76.0% top-1 and from 1/8
  to 0/8 near-misses scoring as real hits.

  The routing belongs in the **body**, under When NOT to use, where an LLM
  reads it and understands the negation. The description is scored, not read.
  This is the Arm 1 / Arm 2 split: what helps the model choose can hurt the
  retriever that surfaces the choice.
- **Do not reuse a sibling's trigger phrases.** `tree-sitting` listed "map this
  codebase" and "explore repo" — both `exploring-codebases`' territory — and
  lost all five of its own canonical queries in the 2026-08-24 measurement,
  including "where is X defined".

**Run the check before shipping.** `oaustegard/claude-workspace` carries the
tool:

```bash
python3 scripts/skill_confusability.py                        # nearest-neighbour map
python3 scripts/skill_confusability.py --queries q.json       # top-1, steals, near-misses
```

The query file needs both halves. Positives go under the skill's own name.
Negatives go under the reserved `__none__` key — queries that share the
catalogue's vocabulary but belong to no skill in it, built the way
`skill-creator` builds should-not-trigger cases: adjacent domains and
ambiguous phrasing, never obvious filler. Read three numbers:

- **top-1** — does the skill win its own queries
- **steals** — does it win queries belonging to other skills
- **near-misses** — does anything it should ignore score in hit territory

A description tuned on top-1 alone gets better at being found and worse at
staying out of the way, and only the second and third numbers show it.

Write five task-shaped queries for the new skill, phrased as a user would state
the task, and confirm it takes top-1. A query that echoes the description
measures its own phrasing and nothing else. Any neighbour above ~0.65 cosine
needs an explicit boundary in both descriptions, or the two skills need
merging.
