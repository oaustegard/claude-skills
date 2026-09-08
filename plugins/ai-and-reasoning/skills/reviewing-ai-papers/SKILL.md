---
name: reviewing-ai-papers
description: >-
  Analyzes an AI/ML publication — paper, preprint, article, technical blog
  post — and extracts what an enterprise AI engineer should do about it. Use
  when someone supplies a URL or document on RAG, embeddings, fine-tuning,
  prompt engineering, agents, or LLM deployment and asks "review this
  paper", "what do you make of this", "is this worth adopting", or
  "summarise the method and its limits". The subject matter must itself be
  machine learning.
metadata:
  version: 0.4.0
---

# Reviewing AI Papers

When users request analysis of AI/ML technical content (papers, articles, blog posts), extract actionable insights filtered through an enterprise AI engineering lens and store valuable discoveries to memory for cross-session recall.

## When NOT to use this skill

The subject matter has to be machine learning. Adjacent asks that are not:

| Situation | Use |
|---|---|
| "Does this text read as AI-written?" | declauding |
| Register or voice pass on a draft | declauding |
| Review a pull request or a diff | code-review |
| A paper outside ML | read it directly; this skill's lens will not fit |

"AI" appearing in the request is not the trigger — AI being the *topic of the
document* is.

## Contextual Priorities

**Technical Architecture:**
- RAG systems (semantic/lexical search, hybrid retrieval)
- Vector database optimization and embedding strategies
- Model fine-tuning for specialized scientific domains
- Knowledge distillation for secure on-premise deployment

**Implementation & Operations:**
- Prompt engineering and in-context learning techniques
- Security and IP protection in AI systems
- Scientific accuracy and hallucination mitigation
- AWS integration (Bedrock/SageMaker)

**Enterprise & Adoption:**
- Enterprise deployment in regulated environments
- Building trust with scientific/legal stakeholders
- Internal customer success strategies
- Build vs. buy decision frameworks

## Analytical Standards

- **Maintain objectivity**: Extract factual insights without amplifying source hype
- **Challenge novelty claims**: Identify what practitioners already use as baselines. Distinguish "applies existing techniques" from "genuinely new methods". The procedure for this is "The ablation the paper did not run" below. Run it; do not improvise a judgement
- **Separate rigor from novelty**: Well-executed study of standard techniques ≠ methodological breakthrough
- **Confidence transparency**: Distinguish established facts, emerging trends, speculative claims
- **Contextual filtering**: Prioritize insights mapping to current challenges

## The ablation the paper did not run

Run this before writing any part of the assessment. It reads off the paper's
own tables and needs no code, no reimplementation and no access to the data.

A paper's ablation table names what its authors thought was contestable. The
axis every row holds fixed is the one nobody argued, and it is where an
unearned mechanism survives review.

Four steps:

1. List every ablation the paper reports and name the axis each one varies.
2. Name the axis that no row varies.
3. On that axis, name the cheapest mechanism producing the same output shape,
   meaning what a practitioner would reach for having never read the paper.
4. Determine whether the paper ran it.

Emit this block in every review. A review without it is incomplete:

```
VARIED:               <axes the paper ablates>
HELD FIXED:           <the axis no row varies>
CHEAPEST ALTERNATIVE: <what a practitioner would use on that axis>
RAN IT:               yes | no | partially, against <what>
```

Step 3 is where this fails. The alternative a paper argues against is the one
its mechanism was built to beat, and adopting it as the comparator inherits the
paper's framing. Write the comparator from what a practitioner would use, not
from the alternatives the paper chose to name.

`RAN IT: no` describes the paper's coverage. It does not settle whether the
method works. State what the missing comparison would decide and what running
it would cost. A mechanism can beat the cheap alternative; the paper simply
does not say so yet. When the answer is `yes`, say so in the credibility
assessment: a paper that ran the comparison is stronger for having run it.

DIAGNOSED, twice, both times found after the fact:

- **SPD/hLLM** (arXiv:2609.01807, 2026-09-08). Tables 3 and 4 ablate the
  scoring head, the training signal and the backbone. No row varies the
  decoder, and the Hungarian solve is the paper's contribution. Measured
  afterwards: sorting one column of the score matrix ties the assignment
  solve, +0.0008 [−0.0028, +0.0044] NDCG@10 over 1,785 slates. The paper's own
  comparator, row-argmax with repair, does lose to the Hungarian, so its
  ablation is correct as far as it goes and the finding sits one step past it.
  (`oaustegard/experiments` PR #92.)
- **TTT-Embed** (arXiv:2608.12569, 2026-08-14). Ablates reward scope and reward
  budget. No row varies how the residual query vector is obtained, which is the
  contribution. Two label-free constructions of the same object cost zero
  reward budget and were not run: Rocchio over the top-k retrieved documents,
  and the query-document modality-gap direction. (Memory `7461f178`.)

## Analysis Structure

### For Substantive Content

**Article Assessment** (2-3 sentences)
- Core topic and primary claims
- Credibility: author expertise, evidence quality, methodology rigor

**Prioritized Insights**
- High Priority: Direct applications to active projects
- Medium Priority: Adjacent technologies worth monitoring
- Low Priority: Interesting but not immediately actionable

**Technical Evaluation**
- Distinguish novel methods from standard practice presented as innovation
- Flag implementation challenges, risks, resource requirements
- Note contradictions with established best practices

**Actionable Recommendations**
- Research deeper: Specific areas requiring investigation
- Evaluate for implementation: Techniques worth prototyping
- Share with teams: Which teams benefit from this content
- Monitor trends: Emerging areas to track

**Immediate Applications**
Map insights to current projects. Identify quick wins or POC opportunities.

### For Thin Content

- State limitations upfront
- Extract marginal insights if any
- Recommend alternatives if topic matters
- Keep brief

## Memory Integration

**Automatic storage triggers:**
- High-priority insights (directly applicable)
- Novel techniques worth prototyping
- Pattern recognitions across papers
- Contradictions to established practice

**Storage format:**
```python
remember(
    "[Source: {title or url}] {condensed insight}",
    "world",
    tags=["paper-insight", "{domain}", "{technique}"],
    conf=0.85  # higher for strong evidence
)
```

**Compression rule:**
- Full analysis → conversation (what user sees)
- Condensed insight → memory (searchable nugget with attribution)
- Store the actionable kernel, not the whole analysis

**Example:**

Analysis says: "Hybrid retrieval (BM25 + dense) shows 23% improvement over pure semantic search for scientific queries. Two-stage approach..."

Store as: `"[Source: arxiv.org/abs/2401.xxxxx] Hybrid BM25+dense retrieval: 23% lift over semantic-only for scientific corpora. Requires 10K+ domain examples for fine-tuning benefit."`

Tags: `["paper-insight", "rag", "hybrid-retrieval", "scientific-domain"]`

## Output Standards

- **Conciseness**: Actionable insights, not content restatement
- **Precision**: Distinguish demonstrates/suggests/claims/speculates
- **Relevance**: Connect to focus areas or state no connection
- **Adaptive depth**: Match length to content value

## Constraints

- No hype amplification
- No timelines unless requested
- No speculation beyond article
- Note contradictions explicitly
- State limitations on thin content
