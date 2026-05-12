---
name: orienting-codebases
description: >-
  Interactive codebase orientation for human learning. Companion to
  exploring-codebases (which builds Claude's understanding); this skill
  builds the user's understanding through guided exercises grounded in
  learning science. Uses the same tree-sitting + featuring pipeline but
  synthesizes into interactive teaching via HTML artifacts rather than
  analysis documents. Triggers on "orient me to this repo", "teach me
  this codebase", "help me understand this code", "learning orientation",
  or when the user wants to build genuine comprehension of an unfamiliar
  codebase rather than just getting work done in it.
metadata:
  version: 0.2.0
  license: CC-BY-4.0
  lineage: >-
    Pedagogical design adapted from DrCatHicks/learning-opportunities
    (orient skill + PRINCIPLES.md). Pipeline from exploring-codebases.
    Presentation via composing-html.
---

# Orienting Codebases

Interactive codebase orientation for the human, not the agent. Uses the
same structural pipeline as exploring-codebases (tree-sitting + featuring)
but synthesizes into guided HTML exercises that build the user's mental model.

## Why this exists

exploring-codebases answers "what is this repo?" for Claude.
This skill answers "what is this repo?" for the person sitting at the keyboard.

The difference matters. Claude can ingest a gather.py dump and reason about
it immediately. A human needs to actively engage — predict, synthesize,
explain, get things wrong, correct — to build durable understanding.
Passive reading of generated analysis creates fluency illusion: it *feels*
understood but isn't retained. (See: Bjork & Bjork on desirable difficulties;
Tankelevitch et al. CHI 2024 on metacognitive demands of generative AI.)

## Why HTML

HTML makes the hardest pedagogical enforcement structural rather than
behavioral:

- **Pause protocol via `<details>`**: answers are physically hidden until
  the user clicks to reveal. No LLM drift can expose them prematurely.
  The generation effect is enforced by the DOM, not by prompt discipline.
- **Code-in-context**: the pipeline already has the source — treesit
  extracts specific functions with line ranges. Instead of "open this
  file yourself", the artifact shows syntax-highlighted code alongside
  the question. The user still does the cognitive work; they don't waste
  orientation time on file navigation.
- **Standalone reuse**: an `orientation.html` anyone on the team can open
  in a browser. No tooling, no live AI session needed. Collapsible
  exercises, architecture context, progress tracking.

## Pipeline

### 0. Setup (once per session)

```bash
uv venv /home/claude/.venv 2>/dev/null
uv pip install tree-sitter-language-pack --python /home/claude/.venv/bin/python
export PYTHON=/home/claude/.venv/bin/python
export TREESIT=/mnt/skills/user/tree-sitting/scripts/treesit.py
export GATHER=/mnt/skills/user/featuring/scripts/gather.py
export COMPOSE=/mnt/skills/user/composing-html/scripts/build.py
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

### 4. Targeted source extraction

For each exercise target identified from gather output, extract the
actual source using treesit queries:

```bash
# Entry point source
$PYTHON $TREESIT /tmp/$REPO --no-tree 'source:main'

# Specific function for an exercise
$PYTHON $TREESIT /tmp/$REPO --no-tree 'source:validate_token'

# Imports for a hub file
$PYTHON $TREESIT /tmp/$REPO --no-tree 'imports:src/api.py'
```

This source feeds directly into the HTML artifact — the user sees
real code, syntax-highlighted, without having to navigate the repo.

**Do not show raw pipeline output to the user.** It's material for
exercise design. The user sees HTML artifacts and conversation.


## Orientation session

After the pipeline steps, synthesize into an interactive orientation.
Three phases.

### Phase A: Framing (1 message, no artifact)

Summarize the repo in ONE sentence (what it does, who it's for). Then:

> I can walk you through a hands-on orientation — about 15 minutes,
> two exercises that'll give you a working mental model of this codebase.
> Want to try it?

Do not start exercises without confirmation.

### Phase B: Exercises (2 exercises, interactive)

For each exercise, generate an HTML artifact using composing-html's
`freeform` template, then continue the conversation around it.

#### Artifact structure per exercise

Build a spec with `body_html` containing:

```html
<section class="stack">
  <div class="eyebrow">EXERCISE 1 OF 2</div>
  <h2>[Exercise title]</h2>

  <div class="card">
    <div class="eyebrow">CONTEXT</div>
    <p>[Brief explanation of what this code does in the system
       and why it matters for orientation.]</p>
  </div>

  <div class="card">
    <div class="eyebrow">CODE</div>
    <pre><code>[Actual source extracted by treesit — entry point,
function, config, imports, or test names. Escaped properly.]</code></pre>
  </div>

  <details class="card">
    <summary>
      <span class="badge badge--clay">Your turn</span>
      [Specific comprehension/synthesis question]
    </summary>
    <div style="margin-top:1rem">
      <div class="eyebrow">KEY POINTS</div>
      <p>[Pre-generated feedback covering what the code reveals about
         the system's architecture, design decisions, or workflow.
         This is the "answer key" — hidden until clicked.]</p>
    </div>
  </details>
</section>
```

Build and present the artifact:

```bash
python3 $COMPOSE build freeform --spec /tmp/exercise_N.json --out /tmp/exercise_N.html
```

#### Two interaction modes

After presenting the artifact, tell the user:

> Take a look at the code and the question. You can either:
> - **Tell me your answer** in chat and I'll give you specific feedback
> - **Click to reveal** the key points in the artifact when you're ready

If they respond in chat: give personalized feedback based on what they
actually said — confirm what's right, be specific about gaps, explore
misconceptions. This is pedagogically richer than pre-canned feedback.

If they click through: that's fine too — the artifact's hidden feedback
covers the essential points. Move to the next exercise.

#### Exercise design from pipeline signals

Each exercise type maps to specific pipeline output:

**Entry-point walkthrough** — gather found clear entry points:
Show the main function/handler source. Ask what the program does on
startup and what the 2-3 most important operations are.

**Architecture synthesis** — treesit --stats shows clear directory structure:
Show the directory tree with file counts and symbol density. Ask what
the system's main components are and how they relate.

**Dependency detective** — gather found import clusters:
Show a hub file's imports. Ask what the import list reveals about the
file's role — integration point, orchestrator, leaf node?

**Config reader** — manifest/config files are rich:
Show the config file. Ask which 2-3 settings they'd change first for
a new project and why.

**Test-as-spec** — test files present and readable:
Show test names (not bodies). Ask what the tests tell them about what
the module is supposed to do.

### Phase C: Synthesis (1 message after exercises)

After both exercises, ask in chat (no artifact needed):

> What's one thing about this codebase that surprised you, or that you
> want to dig into further?

Use their answer to either:
- Point them to a specific file or symbol for independent exploration
- Offer a targeted follow-up exercise — but only if they want more


## Producing orientation.html (optional)

If the user asks for a persistent orientation document, or if the session
produced insights worth preserving, generate a standalone HTML artifact
that any teammate can open in a browser without tooling.

Build via composing-html `freeform` with this body structure:

```html
<section class="stack">
  <div class="card">
    <div class="eyebrow">PURPOSE</div>
    <p>[One-line: what this repo does and why it exists.]</p>
  </div>

  <div class="card">
    <div class="eyebrow">LANGUAGES</div>
    <p>[From treesit --stats.]</p>
  </div>

  <h2 class="rule">Key files</h2>
  <div class="grid grid--2">
    [For each of 6-10 key files from gather's density ranking:]
    <div class="card card--soft">
      <code>[path/to/file]</code>
      <p>[What it does — why a new developer should read it.]</p>
    </div>
  </div>

  <h2 class="rule">Core concepts</h2>
  [For each of 3-5 concepts:]
  <details class="card">
    <summary><strong>[Concept name]</strong> — [one-line summary]</summary>
    <p>[Where it lives in the code. Why it matters.]</p>
  </details>

  <h2 class="rule">Orientation exercises</h2>
  <p>Two exercises to build a working mental model. Read the code,
  answer the question, then click to check your understanding.</p>

  [Exercise 1 — same card+details structure as Phase B artifacts]
  [Exercise 2 — same structure]
</section>
```

Spec keys:
```json
{
  "title": "Orientation: [repo name]",
  "eyebrow": "CODEBASE ORIENTATION",
  "subtitle": "[one-line purpose]",
  "show_masthead": true,
  "page_class": "page page--narrow",
  "body_html": "..."
}
```

Build and present:
```bash
python3 $COMPOSE build freeform --spec /tmp/orientation_spec.json \
  --out /mnt/user-data/outputs/orientation.html
```


## Feedback and scaffolding

### Feedback after chat responses

When the user responds in chat (rather than clicking the reveal):
- If correct: confirm briefly, then extend ("Right — and that connects
  to [next concept] because...")
- If partially correct: acknowledge what's right, be specific about
  what's missing, explore the gap
- If wrong: say so directly without softening, then walk through the
  actual behavior together
- Do not attribute understanding the user didn't demonstrate. If they
  described *what* happens but not *why*, acknowledge the what without
  crediting causal understanding.

### Fading scaffolding

Adjust the amount of code shown and question specificity based on
demonstrated familiarity — but always keep the *answer* as the user's
responsibility.

| Level | Artifact shows | Question asks | Use when |
|-------|---------------|---------------|----------|
| High | Full function source, line numbers, file path | "What does this function check?" | First exercise, unfamiliar language |
| Medium | Function signature + key lines only | "What's the validation logic here?" | Second exercise, or user nailed the first |
| Low | File path only, no source in artifact | "Where would you look to change how auth works?" | Follow-up if user wants more |

Fading adjusts the difficulty of *finding and reading* the code, not
*explaining* it. At every level the user still produces the synthesis.

If the user struggles, move UP the ladder (show more code, be more
specific), not sideways (hint at the answer).


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
