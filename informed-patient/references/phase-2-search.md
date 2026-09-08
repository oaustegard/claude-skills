# Phase 2: Literature Search

Read this before running the first search query. The red-flags check at the end
of this file runs before Phase 3 begins, not at the end of the session.

After the interview and before evidence evaluation, conduct a structured mini literature review. This is one of the most valuable things the skill does: most patients don't know what to search for, don't have access to the right databases, and can't easily distinguish a landmark systematic review from a single case report. Claude does this legwork and shows its work.

**Transition from Phase 1 (required, non-blocking):** Before beginning the search, state the search framing in 2-3 sentences: what symptom picture you'll be searching against and what diagnostic territory you'll explore. Format like: "Before I search, let me confirm what I'll be looking for: [brief symptom summary]. I'll focus on [conditions/territory]. Correct me if I'm missing something — otherwise I'll get started." Do not wait for explicit approval — if the user doesn't correct the framing, proceed. The purpose is to give the user a chance to redirect, not to create a mandatory gate. Even if the user asks to skip ahead, still state the framing in one sentence before searching.

**Tell the user what's happening:**

> "Now I'm going to search the medical literature based on what you've told me. I'll share the exact search terms I use so you can see what I looked for — and tell me if I'm missing anything."

### Search Mode

This skill supports two search modes. The default is **structured search**.
The user can request **open search** at any point, or the facilitator can
suggest it when the user's situation warrants it.

**Structured search** (default): Follow the source hierarchy below in order.
This ensures systematic coverage and is appropriate for most sessions —
especially when the user is early in their diagnostic journey, dealing with
a well-studied condition, or using this skill for the first time. The
hierarchy is the deliverable: the user gets a reproducible, auditable
search with clear source types and quality tags.

**Open search**: The source hierarchy serves as a starting checklist, not a
workflow. After ensuring baseline coverage (at minimum: one systematic
review search and one guideline search), follow the evidence where the
interview data leads. This mode is appropriate when:

- The user's situation involves the intersection of multiple conditions
  (where the most relevant evidence won't be in standard single-condition
  searches)
- The user has a confirmed diagnosis and is asking about risk, prognosis,
  or prevention which are questions that require following mechanistic and
  epidemiological threads rather than searching a single condition
- The interview reveals an onset trigger or comorbidity pattern that
  changes which body of literature is relevant (e.g., post-viral onset,
  medication-triggered symptoms)
- Standard searches return thin results and the evidence landscape
  requires creative search strategies to map
- The user brings specific claims, studies, or information they've
  encountered and wants evaluated, requiring the search to engage with
  the user's sources rather than only finding new ones

In open search mode, adhere to general documentation and evidence assessment guidelines. Still document every search query, still tag every source with quality indicators, and still report what you couldn't find. Inform the user that open search mode is being used and why.

**Structured Search strategy:**

Use web search across these source types, in priority order. Full query templates and per-source rationale are in `literature-search-strategy.md` — read it before running the search.

1. **Systematic reviews — cast a wide net, not just Cochrane.** Search Cochrane, then PubMed, NICE, and AHRQ. **If Cochrane or AHRQ return no results, do not silently skip them** — report the null result explicitly; it can itself signal an understudied condition. Silent omission has been a recurring failure in testing.
2. **Clinical practice guidelines** from major bodies (ACP, NICE, WHO, specialty societies). Note whether they're recent — guidelines over 5-10 years old may not reflect current evidence.
3. **Peer-reviewed primary research** — if systematic reviews are thin, prioritize RCTs and prospective cohorts over retrospective and case studies.
4. **FDA/regulatory information** — if treatments are discussed, check approved indications, black box warnings, recent safety communications.
5. **Patient advocacy organizations** — time-to-diagnosis data and patient experience. Context, not clinical evidence.

**When to stop searching:** Work through the hierarchy in order, but stop once the evidence base is sufficient to support the user's questions. If Cochrane and guideline coverage is solid, lower-priority sources can be skipped unless they'd add something new. Use judgment. When you stop early, say so: "I stopped here because the Cochrane and guideline coverage was sufficient — see the informed-patient skill README if you want to force a complete search through all source types."

**Search term transparency:**

Share every search query with the user as you go. Format like:

> "I searched for: `[exact query]` — here's what I found."

This models good research practice and lets the user course-correct. They may know terminology, specialist names, or subtype distinctions that improve the search.

**For each source found, tag it with a plain-language quality indicator:**

- Study type and what that means (e.g., "Systematic review of 12 RCTs — this is strong synthesized evidence")
- Sample size and population (e.g., "342 participants, mostly women aged 30-50"); for meta-analyses, number of studies included is more informative than participant count (e.g., "pooled analysis of 27 RCTs")
- How recent it is (e.g., "Published 2023 — relatively current")
- Relevance to the user's specific situation (e.g., "This studied the exact symptom pattern you described" or "This focused on a different population but the mechanism is relevant")

Refer to `evidence-hierarchy.md` for how to explain each study type in plain language.

**The "what I couldn't find" moment:**

This is critical. If the search reveals limited evidence, say so explicitly and name what it means:

> "I searched for [terms] and found very little published research. This is itself important information. It tells us this could be an understudied area, which means clinical practice may be based more on expert experience than on rigorous studies."

Absence of evidence is not nothing, it's a finding. It should:

- Trigger the "understudied condition" red flag
- Be included prominently in the output artifact (not buried or glossed over)
- Be framed as actionable: "This means it's especially important to find a clinician with direct experience treating this condition, since published guidance is limited"

If the evidence is **contested** (conflicting meta-analyses, guideline disagreements, active scientific debate), name that too. Don't resolve it — present the disagreement clearly and flag it as a metascience concern for the red flags section. Contested evidence should:

- Trigger the "metascience concerns" red flag and potentially the "treatment is highly personalized" red flag
- Be included prominently in the output artifact (not buried or glossed over)
- Be framed as actionable: "This means it's important to develop a specific treatment plan for your individual context with the guidance of a clinician"

**Search scope:**

Aim for 5-10 key sources that represent the best available evidence. Prioritize quality and relevance over volume. For each hypothesis generated later, there should be at least one relevant source — if there isn't, that's a notable gap to document.

Do not cite sources you haven't actually found and reviewed through web search. If you can only access an abstract rather than the full text, say so: "I could only see the abstract of this study, so I can't assess the full methodology. The abstract reports [X]."

**Citation integrity — non-negotiable:** Every source in the artifact must include the URL that was returned by the web search tool. Never construct or recall a PMID, DOI, or other identifier from memory — only use identifiers that appeared in an actual search result URL. If a search returned a result but no stable URL is available, describe the source (journal, author, year, title) and note that a direct link could not be retrieved. A source without a verifiable URL is weaker evidence of retrieval than one with a URL — flag it as such rather than omitting it or fabricating an identifier.  

**Source-level warnings — use ⚠️ inline:** When a source has a nuanced issue that affects how much weight to give it, flag it directly in the source entry with a ⚠️ and a one-sentence explanation — don't bury it in prose, make it impossible to miss. See `literature-search-strategy.md` for the specific warning conditions and phrasing (outdated guidelines, abstract-only access, missing risk-of-bias assessment, small samples, population mismatch).

**Evidence Snapshot (required):**

Before presenting the detailed source list, synthesize 1-3 bullet points that orient the user to the research landscape. Keep each bullet to 1-2 sentences. These should collectively address:

- **How well-studied is this?** Is there robust published evidence (systematic reviews, guidelines) or is this an understudied area where clinical practice is based more on expert experience?
- **What does the strongest evidence tell us?** One specific, concrete finding that is most relevant to the user's situation.
- **How challenging is this clinically?** If the research includes data on clinical care challenges — misdiagnosis rates, common errors in triage, conditions frequently confused with this one, or known diagnostic delays, include that here. This helps the user understand whether they're navigating a straightforward clinical situation or one where even experienced clinicians regularly struggle. If no such research was found, omit this bullet.

Format like:

> **What the research landscape looks like:**
>
> - [Well-studied / Moderately studied / Understudied]: [Brief reason — e.g., "Several systematic reviews exist, though most focus on treatment rather than early diagnosis."]
> - Strongest relevant finding: [Specific, concrete takeaway from the best source found]
> - [If applicable] Clinical challenges: [What the literature says about misdiagnosis, common errors, or diagnostic difficulty — omit if no relevant research found]

The goal is to help the user immediately understand whether they're dealing with a common, well-mapped problem or a more complex, less-charted one, and whether the clinical pathway is typically clear or frequently goes wrong.

**Red flags check (run immediately after the literature search, before Phase 3):**

Based on what the search revealed, apply the red flags framework now, not later. The literature search is itself the primary input for flags 1, 7, and 9:

- **Flag 1 (Understudied condition):** Did the search return few or no systematic reviews or RCTs? Say so explicitly and flag it.
- **Flag 7 (Long time-to-diagnosis):** Did the literature or advocacy sources mention a long diagnostic delay for this condition?
- **Flag 10 (Metascience concerns):** Did the search reveal conflicting guidelines, contested meta-analyses, or known evidence-practice gaps?

Surface the 1-3 most relevant flags at this point and carry them into the output artifact. Flags identified here should shape how confidently evidence is presented in Phase 3. A condition with active flags warrants more scrutiny of hypotheses more explicit uncertainty than a well-mapped one.

Refer to `red-flags.md` for the full set of flags and suggested actions.
