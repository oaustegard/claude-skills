---
name: orienting-codebases
description: >-
  Interactive codebase orientation for human learning. Companion to
  exploring-codebases (which builds Claude's understanding); this skill
  builds the user's understanding through guided exercises grounded in
  learning science. Uses the same tree-sitting + featuring pipeline but
  synthesizes into interactive teaching rather than analysis documents.
  Triggers on "orient me to this repo", "teach me this codebase",
  "help me understand this code", "learning orientation", or when the
  user wants to build genuine comprehension of an unfamiliar codebase
  rather than just getting work done in it.
metadata:
  version: 0.1.0
  license: CC-BY-4.0
  lineage: >-
    Pedagogical design adapted from DrCatHicks/learning-opportunities
    (orient skill + PRINCIPLES.md). Pipeline from exploring-codebases.
---

# Orienting Codebases

Interactive codebase orientation for the human, not the agent. Uses the
same structural pipeline as exploring-codebases (tree-sitting + featuring)
but synthesizes into guided exercises that build the user's mental model.

## Why this exists

exploring-codebases answers "what is this repo?" for Claude.
This skill answers "what is this repo?" for the person sitting at the keyboard.

The difference matters. Claude can ingest a gather.py dump and reason about
it immediately. A human needs to actively engage — predict, synthesize,
explain, get things wrong, correct — to build durable understanding.
Passive reading of generated analysis creates fluency illusion: it *feels*
understood but isn't retained. (See: Bjork & Bjork on desirable difficulties;
Tankelevitch et al. CHI 2024 on metacognitive demands of generative AI.)

## Pipeline (same as exploring-codebases)

### 0. Setup (once per session)

```bash
uv venv /home/claude/.venv 2>/dev/null
uv pip install tree-sitter-language-pack --python /home/claude/.venv/bin/python
export PYTHON=/home/claude/.venv/bin/python
export TREESIT=/mnt/skills/user/tree-sitting/scripts/treesit.py
export GATHER=/mnt/skills/user/featuring/scripts/gather.py
```

### 1. Get the repo

```bash
OWNER=... REPO=... REF=main
curl -sL -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/tarball/$REF" -o /tmp/$REPO.tar.gz
mkdir -p /tmp/$REPO && tar -xzf /tmp/$REPO.tar.gz -C /tmp/$REPO --strip-components=1
```

For local repos, skip the curl — point directly at the path.

### 2. Structural scan

```bash
$PYTHON $TREESIT /tmp/$REPO --stats
```

### 3. Feature gathering

```bash
$PYTHON $GATHER /tmp/$REPO \
  --skip tests,.github,node_modules --source-budget 8000
```

**Do not show pipeline output to the user.** It's raw material for
exercise design, not a deliverable. The user sees exercises, not dumps.


## Orientation session

After steps 0–3, synthesize the pipeline output into an interactive
orientation. The session has three phases.

### Phase A: Framing (1 message)

Summarize the repo in ONE sentence (what it does, who it's for). Then:

> I can walk you through a hands-on orientation — about 15 minutes,
> two exercises that'll give you a working mental model of this codebase.
> Want to try it?

Do not start exercises without confirmation.

### Phase B: Exercises (2 exercises, interactive)

Design exactly 2 exercises from the pipeline output. Each exercise follows
the read-then-synthesize pattern:

1. Direct the user to a specific, short artifact (file, function, config)
2. Ask them to synthesize or explain what they read
3. Wait for their response (HARD STOP — see Pause Protocol below)
4. Provide feedback connecting their understanding to actual behavior
5. If wrong, say so clearly — then explore the gap

#### Exercise design constraints

**DO** design exercises that:
- Point to specific files the pipeline identified as high-value (entry
  points, high-density directories, hub files with many imports)
- Ask comprehension/synthesis questions ("what does this tell you about
  how the system works?")
- Build from concrete to abstract ("now that you've seen the auth flow,
  what's the general pattern here?")
- Use the gather output's "candidate areas" ranking to pick targets

**DO NOT** design exercises that:
- Ask users to predict things they couldn't know without reading
- Require implementation-level detail (line-by-line tracing)
- Cover more than one concept per exercise
- Require reading files longer than ~100 lines without narrowing scope

#### Exercise type selection

Choose from these types based on what the pipeline revealed:

**Entry-point walkthrough** (best when gather found clear entry points):
> Open `[entry file]` and read the main function/handler. What are the
> 2-3 things this program does when it starts up?

**Architecture synthesis** (best when treesit --stats shows clear structure):
> Look at the directory structure. `src/` has [N] files across [dirs].
> Based on the directory names alone, what do you think this system's
> main components are?

**Dependency detective** (best when gather found import clusters):
> Open `[hub file]` and look at its imports. What does the import list
> tell you about this file's role in the system?

**Config reader** (best when manifest/config files are rich):
> Open `[config file]`. What are the 2-3 settings you'd most likely
> need to change for a new project, and why?

**Test-as-spec** (best when test files are present and readable):
> Read the test names in `[test file]` (just the names, not the bodies).
> What do they tell you about what `[module]` is supposed to do?

### Phase C: Synthesis (1 message after exercises)

After both exercises, ask:

> What's one thing about this codebase that surprised you, or that you
> want to dig into further?

Use their answer to either:
- Point them to a specific file or symbol for independent exploration
- Offer a targeted follow-up (a "debug this" or "trace the path" exercise
  from the learning-opportunities repertoire — but only if they want more)


## Pause Protocol

This is the hardest enforcement in the skill. LLMs default to answering
their own questions. Every exercise question is a HARD STOP.

**End your message immediately after the question.** Do not generate
any further content after the pause point.

After the question, do not generate:
- Suggested or example responses
- Hints disguised as encouragement ("Think about...", "Consider...")
- Multiple questions in sequence
- Italicized or parenthetical clues
- Any teaching content

Allowed after the question:
- Content-free reassurance: "(Take your best guess — wrong answers are
  useful data.)"
- An escape hatch: "(Or we can skip this one.)"

Use explicit markers:

> **Your turn:** [specific question about what they just read]
>
> (Take your best guess — wrong answers are useful data.)

Wait for their response before continuing.

### Feedback after responses

When the user responds:
- If correct: confirm briefly, then extend ("Right — and that connects
  to [next concept] because...")
- If partially correct: acknowledge what's right, be specific about
  what's missing, explore the gap
- If wrong: say so directly without softening, then walk through the
  actual behavior together
- Do not attribute understanding the user didn't demonstrate. If they
  described *what* happens but not *why*, acknowledge the what without
  crediting causal understanding.


## Fading scaffolding

Adjust question specificity based on demonstrated familiarity — but
always keep the *answer* as the user's responsibility.

| Level | Question style | Use when |
|-------|---------------|----------|
| High scaffold | "Open `src/auth.py`, find the `validate` function around line 45. What does it check?" | First exercise, unfamiliar language |
| Medium | "Find where authentication happens. What's the validation logic?" | Second exercise, or user nailed the first |
| Low | "Where would you look to change how auth works?" | Follow-up after both exercises |

Fading adjusts the difficulty of *finding* the answer, not *generating*
it. At every level the user still produces the explanation themselves.

If the user struggles, move UP the ladder (more specific), not sideways
(hint at the answer).


## When to use this vs. other skills

| Situation | Use |
|-----------|-----|
| "I just cloned this, what is it?" (Claude needs to understand) | exploring-codebases |
| "Help me understand this codebase" (user needs to understand) | **orienting-codebases** (this skill) |
| "Where is the retry logic?" | searching-codebases |
| "I want to set a learning goal" | learning-goal |
| "Help me learn [specific concept] from my code" | learning-opportunities (if installed) |

This skill is the **orientation** layer — first-encounter mental model
building. For ongoing learning during development (exercises after
commits, retrieval check-ins, prediction drills), pair with
learning-opportunities from DrCatHicks/learning-opportunities.


## Producing orientation.md (optional)

If the user asks for a persistent orientation document, or if the session
produces insights worth preserving, write an `orientation.md` to the
repo. Use this structure:

```markdown
# Repo Orientation: [name]

> Generated by orienting-codebases. Re-run to update.

## One-line purpose
[Single sentence.]

## Primary language(s)
[From treesit --stats.]

## Key files
[6-10 entries from gather's density ranking + entry point detection:]
- `path/to/file` — [what it does] | [why a new developer should read it]

## Core concepts
[3-5 domain/architectural concepts essential to working here.]

## Suggested exercises
[The 2 exercises from this session, written as standalone prompts
 another developer could follow without the skill installed.]
```

This is compatible with DrCatHicks' orient format — a user with
learning-opportunities installed can consume it via `/learning-opportunities orient`.


## Principles reference

Exercise design draws from established learning science:

- **Generation effect**: producing answers builds stronger memory than
  reading them (Roediger & Karpicke, 2006)
- **Pre-testing**: attempting before knowing primes encoding, even when
  the attempt is wrong (Giebl et al., 2021)
- **Desirable difficulty**: effort during learning = stronger retention
  (Bjork & Bjork, 2013)
- **Fluency illusion**: easy processing ≠ durable knowledge; exercises
  counter this by requiring active engagement (Soderstrom & Bjork, 2015)
- **Expertise reversal**: worked examples help novices but hinder experts;
  fading scaffolding addresses this transition (Kalyuga, 2007)
- **Program comprehension**: experts sample strategically, not exhaustively
  (Hermans 2021, Storey et al. 2006, Spinellis 2003)

Full reference: DrCatHicks/learning-opportunities PRINCIPLES.md
