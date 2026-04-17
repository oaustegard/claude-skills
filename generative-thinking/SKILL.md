---
name: generative-thinking
description: Break out of a locked problem frame by picking one disciplined move — reframe, provocation (Po), random stimulus, SCAMPER, inversion, perspective shift, or constraint play — and committing to it before evaluating. Use when stuck, when options feel narrow or obvious, when iterations produce variations of the same idea, or when the user says "widen this", "break out of", "think differently", "I'm stuck", "feels too obvious", "stress-test the framing", "what am I missing". Complements challenging (which evaluates) and convening-experts (which synthesizes viewpoints); this skill generates distance, not judgment.
metadata:
  version: 0.1.2
---

# Generative Thinking — One Move, Committed

Fixation is the default state. When a generator (human or LLM) has been working on a problem, attention concentrates on the current framing and subsequent ideas tend to be local variations on it. This skill is the interrupt: spend one move stepping sideways, then resume.

The discipline matters more than the move. Pick ONE technique per invocation, run it without second-guessing, and produce explicit reframings or candidate entry points — not a brainstorm list in the same frame.

## When to reach for this

Claude activates this skill when:
- The last 2+ iterations are variations of one idea (fixation signal)
- The user says "widen this", "think bigger", "I'm stuck", "what am I missing", "too narrow", "break out of"
- A problem is framed as a binary ("X or Y") and neither option is good
- An agent loop is producing convergent variations — suspect the frame, not the search depth
- The user explicitly wants a pre-mortem on the *framing* (not the plan) before committing

Do NOT activate this skill as a default before every consequential task — fixation is the trigger, not stakes. If the current frame is working, let it work.

## Core discipline

Three rules that apply across every move below. Violations make the output ideation-flavored but structurally identical to what came before.

1. **Generation before evaluation.** De Bono's core distinction: lateral thinking cares about *movement value*, not truth value. A provocation is not a proposal. Evaluate only after the move has produced 3+ candidate framings.
2. **One move, committed.** Do not rotate through five techniques as a menu. Pick the move that matches the diagnosis, execute it fully, surface what shook loose, then stop. Menus produce noise; commitment produces distance.
3. **Output framings, not ideas.** The deliverable of a generative move is usually *a new statement of the problem* or *a new entry angle*, not another solution candidate inside the old frame. If the output could have been produced without the move, the move didn't fire.

**Stop condition.** Stop when the move has produced 3+ non-trivial framings, or a single framing that reorganizes the problem (one sharp surprise beats five adjacent). Do not keep generating because the list looks short — volume is not the product.

**The fire test.** After every move, ask: *could this output have been produced without the move?* If yes, the move did not fire. Either commit harder (push the provocation further, make the reframe more aggressive, re-roll the random word, invert on a different axis) or the move was mismatched to the stuck-pattern — re-diagnose and pick the better-matched move. Re-diagnosis after a miss is not menu-rotation; menu-rotation is cycling through techniques without commitment. One move at a time, each one fully, and if it misses, diagnose why before the next.

## Diagnostic → Move

Match the stuck-pattern to the move. When unsure, default to **Reframe**.

| If the stuck-pattern is… | Reach for… |
|---|---|
| Framing feels forced ("must be X or Y") | **Reframe** — change the verb, subject, scope, or level |
| Generator keeps returning near-duplicates | **Random stimulus** — force an unrelated concept into the frame |
| Obvious answer is wrong but you can't see past it | **Provocation (Po)** — state something impossible, extract movement |
| Iterating on an existing artifact | **SCAMPER** — seven structured transforms |
| Stuck on "how do we make X succeed?" | **Inversion** — ask "how do we guarantee X fails?" then negate |
| Problem is defined entirely in one domain's vocabulary | **Perspective shift** — how would [distant domain] solve this? |
| Every solution is blocked by a constraint | **Constraint play** — remove it ("assume magic"), or add an absurd one ("must fit in a tweet") |

### Reframe
The problem-as-stated is rarely the problem-to-solve. Mutate the sentence:
- Change the **verb**: "reduce X" → "redistribute X", "time-shift X", "prevent X from mattering"
- Change the **subject**: "our team can't ship faster" → "reviewers are the bottleneck" → "the artifact is too reviewable"
- Change the **scope**: zoom out (whose problem is this upstream?) or zoom in (which one user, which one minute?)
- Change the **frame**: from "problem to fix" to "signal to interpret"

Produce 3 reframings. **Fired if**: at least one makes the original statement sound naive, or shifts who owns the problem.

### Provocation (Po)
Edward de Bono's method. Prefix a deliberately wrong, impossible, or absurd statement with `Po:` to signal it is not a proposal — it is a stimulus. Then extract movement: what principle, consequence, or adjacent idea does this surface?

Four recipes (de Bono's formal provocations):
- **Escape**: remove an essential feature. *Po: the database has no writes.*
- **Reversal**: flip the causal direction. *Po: users pay us to NOT use the product.*
- **Exaggeration**: push a quantity to the absurd limit. *Po: onboarding takes six months.*
- **Wishful thinking**: assume impossible capability. *Po: we know what the user will click next week.*

The canonical example: a factory pollutes a river. *Po: the factory is downstream of itself.* Impossible, but it generates: move intake downstream of discharge. Internal incentive to not pollute. Closed-loop water. The provocation is discarded; the movement stays.

**Fired if**: the provocation is genuinely impossible or absurd (not merely edgy), AND extracting movement yields a principle that survives translation back to the real constraints. If the "provocation" is a thing you could actually do, it's a proposal, not a Po — push it further.

### Random stimulus
Pick a word, object, or domain with no connection to the problem. Force a connection. The forced-feel is the point — it routes around the habituated pathway.

Template: *"How is [problem] like [random]?"* then *"What does that suggest?"*

**Sourcing for humans**: a random Wikipedia article, a nearby physical object, an Oblique Strategies card, a concept from an unrelated field on the current desk. Commit to the first thing you land on; re-rolling defeats the method.

**Sourcing for an LLM agent**: an LLM picking its own "random" word is not random — the same fixated attention that locked onto the frame will pick a word adjacent to it. Use an external source:
- Ask the user for a word, any word
- Call a tool: fetch a random Wikipedia article, draw an Oblique Strategy, pull a noun from a URL the user has open
- Use the tail of the current timestamp or a hash modulo a pre-listed vocabulary (e.g., the Oblique Strategies deck)
- When none available, deliberately pick the domain you are *least* currently thinking about and name the first concrete noun from it

**Fired if**: the connection is genuinely forced (the first 10 seconds feel wrong), and working through the force produces an angle that was not in your prior search space. If the random word feels "relevant" immediately, you re-rolled or picked from attention — get a new one.

### SCAMPER
For iterating on an existing artifact. Walk the seven prompts once; do not pick favorites in advance.

- **S**ubstitute — swap a component, material, person, step
- **C**ombine — merge with something else, including something it competes with
- **A**dapt — borrow a mechanism from elsewhere that solves a related problem
- **M**odify / magnify / minify — change a dimension, frequency, or weight drastically
- **P**ut to another use — who else could use this, for what?
- **E**liminate — what happens if this part simply is not there?
- **R**everse / rearrange — swap order, roles, or polarity

**Fired if**: at least one prompt produced a candidate you would not have reached by asking "what's a better version of this?". If all seven outputs are adjacent polish, the artifact is not the unit of analysis — zoom out and try Reframe.

### Inversion
Solve the inverse problem, then negate the solution. Works because failure modes are often more concrete than success paths.

- "How would I guarantee this fails?" → each failure mode is a protective requirement
- "What would the worst possible version look like?" → the inverse shape of the good version
- "If an adversary wanted us to choose X, why?" → surfaces the hidden trap in X

**Fired if**: inverting surfaced a concrete risk, mechanism, or incentive the forward framing was hiding. If negating the inverted answer gives you the same thing you already had, the inversion was too symmetric — invert on a different axis (goals → incentives, success → unobservable, user → operator).

### Perspective shift
Move the problem into a different domain's vocabulary and see what gets easier.

- **Natural**: how does biology / ecology solve this coordination problem?
- **Trade**: how does a restaurant kitchen / ER triage / shipping dock handle throughput spikes?
- **Role**: what would a CFO / a child / a historian / an adversary notice first?
- **Scale**: how is this solved at 100x scale? at 1/100x scale?

**Fired if**: the borrowed vocabulary made at least one previously-invisible option visible, or renamed a core object in a way that changes what you'd do next. If the new domain's terms map one-to-one onto the old, pick a more distant domain.

### Constraint play
Constraints define the solution space. Move them deliberately.

- **Remove**: "assume infinite budget / time / compute / permission" — what opens up?
- **Add absurd**: "must fit in a tweet", "under $5", "no code", "one meeting only", "physical-only"
- **Invert**: the constraint becomes the feature. Limited time → event-driven. Small budget → tiny team as the pitch.

**Fired if**: a relaxed-constraint solution reveals what you actually value (not just what you'll accept), or an added-constraint solution is sharper than the unconstrained one. If both feel like the same answer with a different budget, the binding constraint is elsewhere — find it.

## Applying the skill to an agent's own reasoning

LLM agents exhibit a context-bound analog of functional fixedness: attention concentrates on current framing and generates variations of it. Signals this is happening:
- The nth iteration has the same structure as the first
- The agent has rejected the same class of option three times with similar reasoning
- The plan has a step labeled "brainstorm" that is producing adjacent bullets

When detected, the fix is the same: pick one move from the diagnostic table, execute it on the agent's own current framing, and explicitly write out the new framing(s) before resuming work. The write-out is load-bearing — a framing that stays implicit in attention gets re-absorbed into the previous frame.

## What this skill does NOT do

- **Does not evaluate.** Pair with **challenging** after generation if the artifact is high-stakes.
- **Does not do MECE coverage.** Use **tiling-tree** for exhaustive partitioning.
- **Does not synthesize multiple viewpoints.** Use **convening-experts** for collaborative multi-role panels.
- **Does not produce long idea lists.** A three-reframe output with one surprising move beats a fifty-item brainstorm in the original frame.

## Canonical references (progressive disclosure)

Load these only when the user wants depth on a specific technique.

- Lateral thinking, provocation, Po, random stimulus — Edward de Bono. Primary: [Wikipedia: Lateral thinking](https://en.wikipedia.org/wiki/Lateral_thinking), [Wikipedia: Po](https://en.wikipedia.org/wiki/Po_(lateral_thinking)). Essay: [de Bono, "Serious Creativity"](https://www.debono.com/serious-creativity-article). Books: *Lateral Thinking* (1970), *Serious Creativity* (1992).
- SCAMPER — Bob Eberle, *SCAMPER: Games for Imagination Development* (1971), built on Alex Osborn's *Applied Imagination* (1953) checklist. Summary: [Wikipedia: SCAMPER](https://en.wikipedia.org/wiki/SCAMPER).
- Oblique Strategies — Brian Eno & Peter Schmidt (1974–2001, five editions). Summary: [Wikipedia: Oblique Strategies](https://en.wikipedia.org/wiki/Oblique_Strategies). Full deck: [mattrickard.com/list-of-all-oblique-strategies](https://mattrickard.com/list-of-all-oblique-strategies). Draw one at random when reaching for random stimulus.
- Functional fixedness (the cognitive bias this skill counters) — Karl Duncker, originally *Zur Psychologie des produktiven Denkens* (1935); English translation *On Problem-Solving* (1945), [doi:10.1037/h0093599](https://doi.org/10.1037/h0093599). The candle problem is the canonical demonstration.
- Design fixation and generative-AI specific failure modes — Wadinambiarachchi, Kelly, Pareek, Zhou & Velloso, "The Effects of Generative AI on Design Fixation and Divergent Thinking," CHI 2024, paper 380, [doi:10.1145/3613904.3642919](https://doi.org/10.1145/3613904.3642919) ([arXiv:2403.11164](https://arxiv.org/abs/2403.11164)). N=60 visual ideation experiment: participants with AI image-generator support showed *higher* fixation on the initial example, and lower fluency, variety, and originality than the no-support baseline. Directly relevant when the fixation is coming from an LLM's own prior outputs.

## Quick-reference card

```
DIAGNOSE: What kind of stuck?
  → framing forced        : REFRAME
  → near-duplicates       : RANDOM STIMULUS
  → can't see past obvious: PROVOCATION (Po)
  → iterating an artifact : SCAMPER
  → chasing success       : INVERSION
  → one domain vocabulary : PERSPECTIVE SHIFT
  → blocked by constraint : CONSTRAINT PLAY

DISCIPLINE:
  1. Generation before evaluation
  2. One move, committed
  3. Output framings, not ideas

STOP when: 3+ non-trivial framings produced, or one surprising framing that reorganizes the problem.
```
