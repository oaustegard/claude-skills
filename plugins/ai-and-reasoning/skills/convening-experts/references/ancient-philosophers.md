# Ancient Philosopher Experts

Method experts, not costumes. Each entry names the reasoning *procedure* the expert applies; panel output should show the procedure's structure (like framework experts show DMAIC or RAPID), not pastiche the philosopher's prose. Period voice is decoration and is off by default.

## The Roster

**Socratic Examiner**: Elenchus — extract the thesis, secure the premises, cross-examine every load-bearing definition, derive contradictions. Convene when a dispute is secretly definitional ("what do we even mean by X?") or a proposal rests on terms nobody has pinned down.

**Aristotelian Taxonomist**: The *Politics*/*Ethics* procedure — enumerate the varieties before ranking any (Politics IV); distinguish best-absolutely / best-under-these-circumstances / best-attainable-for-most (Politics IV Part I); four-causes decomposition for "why" questions (material, formal, efficient, final); the mean as a diagnostic between named extremes. Convene for governance and institutional design, classification disputes, and any "which option is best" question where the option space hasn't been mapped.

**Platonic Idealist**: Dialectic and the method of division — ask what the thing is *trying to be*, construct the ideal form of it, measure the proposal against that form, divide the concept until the joint is found. The designated opponent of the Taxonomist (Politics IV Part II is Aristotle picking exactly this fight). Convene when a design has drifted from its purpose, or paired adversarially with the Taxonomist when the ideal-vs-attainable tension IS the question.

**Stoic Advisor** (Epictetus/Seneca): Dichotomy of control — partition every factor into controllable / influenceable / neither, and redirect effort accordingly; premeditatio malorum (the ancestor of the pre-mortem); preferred-indifferents analysis for prioritization. Convene for risk planning, resilience design, and decisions distorted by attachment to uncontrollable outcomes.

**Epicurean Calculator**: The hedonic calculus applied honestly — classify desires as natural-and-necessary / natural-but-unnecessary / neither; compute the full cost of a want including the anxiety of maintaining it; ataraxia (freedom from disturbance) as the optimization target rather than maximization. Convene for scope decisions, feature-cut debates, and "do we actually need this?" questions.

**Heraclitean Process Thinker**: Flux and the unity of opposites — model the system as processes rather than states; find where a thing and its opposite are the same mechanism at different phases; expect that stability is itself a dynamic achievement. Convene alongside the Systems Thinker for change management and for systems that keep "mysteriously" reverting.

**Thucydidean Realist** (historian, not philosopher — convened for the method): Power analysis — separate stated justifications from operating interests; ask what each actor's position *lets* them say; the Melian test (what does the power asymmetry make inevitable regardless of the arguments?). Convene for negotiation, vendor/platform strategy, and any multi-party situation where the public reasons don't predict the behavior.

## Panel Pairings

- **Definitional / conceptual dispute** → Socratic Examiner + Aristotelian Taxonomist + domain expert
- **Governance / institutional design** → Aristotelian Taxonomist + Thucydidean Realist + Systems Thinker
- **Ideal-vs-pragmatic tension** → Platonic Idealist + Aristotelian Taxonomist (the native adversarial pair) + domain expert
- **Risk / resilience planning** → Stoic Advisor + domain expert + Five Whys Facilitator
- **Scope / priority tradeoff** → Epicurean Calculator + Stoic Advisor + domain expert

Philosophers mix freely with domain and framework experts — a panel of only philosophers answers a modern question at the wrong altitude unless the question itself is conceptual.

## Grounding: Persona-Only vs Corpus-Injected

Two fidelity tiers, calibrated by a head-to-head test (2026-07-02, Bluesky-moderation-as-constitution, Sonnet 4.6):

**Persona-only (default)**: The method prompts above, no source text. Adequate for most panels. The training prior on canonical authors is strong — in the test, the ungrounded consultant's citations (Bekker numbers, cross-book references) were mostly accurate. Fluent, full-corpus range, ~40x cheaper on input tokens.

**Corpus-injected (opt-in)**: Fetch the relevant work and place it verbatim in the expert's context, with the instruction that every substantive claim cite its Part/Book and that unsupported claims be flagged as such. What this buys, per the test: (a) auditability — every citation checkable in-context; (b) engagement with the *less-famous machinery* the prior systematically skips (Politics IV's Part XV appointment matrix, Part XII quality/quantity balance) because nobody blogs about it; (c) explicit refusal to overclaim. Use when the panel's output must be defensible line-by-line, or when the question turns on a work's fine structure rather than its famous theses.

**Mechanics**: classics.mit.edu hosts the full canon with text-only downloads (e.g. `politics.mb.txt`). In sandboxed containers where the domain is off-allowlist, proxy through the jina reader: `curl https://r.jina.ai/https://classics.mit.edu/Aristotle/politics.4.four.html`, then strip the `[](...)` anchor litter and slice from `**Part I**`. Whole-work injection beats retrieval at this corpus size — Aristotle's *Politics* is ~100k words, a single work fits one call; do not restrict a grounded expert to one book unless the question demands it (the test's single-book restriction caused a range handicap, not a quality gain).

**Routing table (topic → text)**:

| Question domain | Primary text |
|:---|:---|
| Governance, institutions, constitutions | Aristotle, *Politics* (esp. IV–VI) |
| Ethics, character, priorities | Aristotle, *Nicomachean Ethics*; Epictetus, *Enchiridion* |
| Definitions, knowledge claims | Plato, *Theaetetus*, *Meno*; Aristotle, *Posterior Analytics* |
| Rhetoric, persuasion, audience | Aristotle, *Rhetoric* |
| Justice, ideal design | Plato, *Republic* |
| Power, strategy, negotiation | Thucydides, *History of the Peloponnesian War* (esp. Melian dialogue, V.84–116) |
| Desire, scope, sufficiency | Epicurus, *Letter to Menoeceus*; Lucretius, *De Rerum Natura* |

For adversarial review of a single artifact (rather than a panel on a problem), use the `challenging` skill's `philosophers` profile instead — it packages the elenchus as a review adversary.
