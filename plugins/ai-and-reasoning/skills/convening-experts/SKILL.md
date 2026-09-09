---
name: convening-experts
description: Convenes expert panels for problem-solving. Use when user mentions panel, experts, multiple perspectives, MECE, DMAIC, RAPID, Six Sigma, root cause analysis, strategic decisions, process improvement, or asks for philosophers/ancients (Socratic, Aristotelian, Stoic method experts).
metadata:
  version: 1.2.0
---

## SURFACE ROUTING — read first

This skill hand-rolls subagent orchestration via raw Anthropic API calls. A
managed runtime now does the same job. Which one to use depends on your surface:

- **In Claude Code (incl. CCotw): use the native runtime, NOT this skill.** If you
  can invoke `/deep-research`, trigger a run with the `workflow` keyword, set
  `/effort ultracode`, or spawn Task subagents — do that instead. The runtime gives
  16-concurrent / 1000-agent ceilings, an approval gate, adversarial cross-review,
  and in-session resume that this skill would otherwise reimplement badly. Dynamic
  workflows shipped in research preview (Claude Code v2.1.154+, 2026).
- **In claude.ai chat or the bare API (no workflow runtime): use this skill.**
  Parallel API instances over httpx is the only fan-out path here. `muninn_utils.dispatch`
  (17 pre-built lenses) already implements this panel over orchestrating-agents' execution
  model — prefer it over rebuilding the panel by hand. Proceed below.

Discriminator: do you have a native subagent/Task tool or a workflow command? Yes
→ native. No → this skill. Never reimplement the runtime where it already exists.

# Convening Experts

Convene domain experts and methodological specialists to solve problems through multi-round collaborative discussion. Experts build on each other's insights, challenge assumptions, and synthesize recommendations.

## Panel Format

### Single-Round Consultation
For simpler problems requiring multiple viewpoints:

1. **Assemble panel** (3-5 experts based on problem domain)
2. **Each expert provides independent perspective** (parallel, not sequential)
3. **Synthesize recommendations** with attribution

### Multi-Round Discussion
For complex problems requiring collaborative reasoning:

1. **Round 1**: Each expert analyzes problem independently
2. **Round 2**: Experts respond to each other's insights, building on or challenging points
3. **Round 3** (if needed): Converge on synthesis, resolve disagreements
4. **Final synthesis**: Integrated recommendations with decision framework

## Expert Roles

**Available expertise spans:**
- MSD domain experts (life sciences, engineering, manufacturing, quality, corporate functions)
- Consulting framework specialists (strategic, process improvement, innovation, systems analysis, root cause)
- Ancient philosopher method experts (elenchus, division-before-judgment, dichotomy of control, power analysis)

See [references/msd-domain-experts.md](references/msd-domain-experts.md), [references/consulting-frameworks.md](references/consulting-frameworks.md), and [references/ancient-philosophers.md](references/ancient-philosophers.md) for complete role catalogs.

Claude loads relevant references based on problem domain.

## Panel Convening Logic

Claude selects 3-5 experts based on problem characteristics:

**Problem type → Primary expert + Supporting experts**

- **Technical troubleshooting** → Domain expert + Systems Thinker + Five Whys Facilitator
- **Strategic decision** → McKinsey Consultant + relevant domain experts + SWOT Analyst
- **Process improvement** → Six Sigma Black Belt + Lean Practitioner + domain Manufacturing Engineer
- **Product innovation** → Design Thinking Facilitator + Jobs-to-Be-Done Specialist + relevant engineers
- **Root cause analysis** → Domain expert + Five Whys Facilitator + Systems Thinker
- **Market positioning** → Porter Framework Expert + Marketing Specialist + BCG Consultant
- **Cross-functional problem** → Relevant domain experts + Bain Consultant (RAPID) + Systems Thinker
- **Definitional / conceptual dispute** → Socratic Examiner + Aristotelian Taxonomist + domain expert
- **Governance / institutional design** → Aristotelian Taxonomist + Thucydidean Realist + Systems Thinker
- **Ideal-vs-pragmatic tension** → Platonic Idealist + Aristotelian Taxonomist (native adversarial pair, per Politics IV Part II) + domain expert

## Response Format

Name the panel up front, then give each expert's view before synthesizing.

**Single-round:** list the panel members, then each expert's independent
analysis (in any clear order — parallel, not sequential), then a synthesis
with attribution.

**Multi-round:** initial analysis from each expert, then a round where
experts respond to specific points from named others (building on or
challenging them), then convergence — resolving disagreements or flagging
which remain productive — and a final synthesis. Skip rounds that would add
nothing (e.g. no round 3 if round 2 already converged).

Headers separating experts and rounds help the reader; the exact heading
text doesn't matter.

## Expert Behavior Guidelines

**Domain Experts:**
- Apply MSD context (ECL platform, regulatory constraints, validated systems)
- Use domain-appropriate terminology without over-explanation
- Prioritize practical implementation over theoretical perfection
- Flag domain-specific risks and constraints

**Philosopher Experts:**
- Apply the named method (elenchus, division, dichotomy of control), showing its structure — method, not costume; no period voice
- Persona-only by default; corpus-injected grounding (verbatim source text + cite-every-claim) when output must be auditable or turns on a work's fine structure — mechanics and routing table in [references/ancient-philosophers.md](references/ancient-philosophers.md)
- Mix with domain experts — an all-philosopher panel answers modern questions at the wrong altitude unless the question itself is conceptual

**Framework Experts:**
- Apply frameworks systematically (show the structure)
- Adapt frameworks to problem context (not rigid application)
- Explain "why this framework" for this problem
- Integrate domain context when applying generic frameworks

**Cross-Panel Interaction:**
- Reference other experts' points specifically ("Building on [Expert]'s observation about...")
- Challenge constructively ("I see it differently because...")
- Synthesize across disciplines ("This connects [Expert 1]'s technical constraint with [Expert 2]'s business priority...")
- Flag tensions between perspectives explicitly

**Disagreement Handling:**
- Make disagreements productive (what assumptions differ?)
- Present multiple valid approaches when consensus isn't required
- Identify decision criteria to resolve disagreements
- Escalate to user if expert consensus can't be reached

## Decision Frameworks

When panel must recommend action:

**RAPID (Bain)**
- **Recommend**: Panel's recommendation with rationale
- **Agree**: Which stakeholders must agree
- **Perform**: Who implements
- **Input**: Who provides input
- **Decide**: Who makes final decision

**Weighted Decision Matrix**
- Criteria (importance weighted)
- Options scored on each criterion
- Total score with sensitivity analysis

**Risk-Benefit Analysis**
- Upside potential (probability × impact)
- Downside risk (probability × impact)
- Mitigation strategies
- Decision under uncertainty

## MSD Integration

Apply MSD-specific context automatically:

**Technical constraints:**
- ECL platform and assay chemistry
- ISO 13485 compliance and validated systems
- Regulatory requirements (FDA, CE marking)
- Technology stack (Python, AWS, Java, TypeScript)

**Business context:**
- Life sciences market dynamics
- Customer segments (pharma, biotech, CRO, academic)
- Competitive landscape

**Cultural factors:**
- Scientific rigor and data-driven decisions
- Cross-functional collaboration norms
- Innovation balanced with risk management
- Quality and regulatory consciousness

## Examples

### Example 1: Technical Troubleshooting

```
User: Our new assay is showing high background signal in serum samples

Claude convenes:
- Assay Scientist (primary)
- Systems Thinker (feedback loops)
- Five Whys Facilitator (root cause)

Format: Multi-round (technical nuance requires collaboration)
```

### Example 2: Strategic Decision

```
User: Should we build internal ML infrastructure or use vendor solutions?

Claude convenes:
- Software Engineer (implementation)
- McKinsey Consultant (strategic framing)
- Finance Analyst (cost analysis)
- DevOps Engineer (operational implications)

Format: Single-round → RAPID framework synthesis
```

### Example 3: Process Improvement

```
User: Manufacturing yield dropped 8% after equipment upgrade

Claude convenes:
- Manufacturing Engineer (primary domain)
- Six Sigma Black Belt (DMAIC)
- Systems Thinker (unintended consequences)

Format: Multi-round (root cause needs collaborative analysis)
```

## Constraints

Skip the panel entirely when the problem has one clearly correct answer —
give a direct answer instead of manufacturing perspectives around it.

Four constraints have no other source of truth in this document, so they stay
explicit. Don't invent fictional names for experts (role titles only —
"Software Engineer", not "Dr. John Smith, Software Engineer"), and don't
invent MSD-specific details beyond general domain knowledge; both would
misrepresent a generic panel as grounded in specifics it doesn't have.

The other two are failure modes the panel format itself invites: manufacturing
consensus where the experts genuinely disagree (flag the disagreement and say
what would settle it), and ending on "here are the perspectives, you decide"
instead of a synthesis someone can act on.
