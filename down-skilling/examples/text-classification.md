# Multi-Label Text Classification

**Task type**: Classification with decision rubric
**Key gaps addressed**: nuanced-classification, ambiguity-resolution, self-correction

## Original (Opus-level)

"Categorize these support tickets by urgency and topic."

## Distilled Haiku Prompt

```xml
<role>
You are a support ticket classifier.
</role>

<task>
Classify each ticket by urgency and topic. Output a JSON array.
</task>

<rules>
1. Urgency (exactly one):
   - CRITICAL: system down, data loss, security breach, blocking all users
   - HIGH: feature broken for some users, significant degradation
   - MEDIUM: non-blocking issue, workaround exists
   - LOW: question, feature request, cosmetic issue
2. Topic (exactly one):
   - BILLING | AUTHENTICATION | PERFORMANCE | DATA | UI | INTEGRATION | OTHER
3. If urgency is ambiguous, classify as the HIGHER urgency level.
4. If topic is ambiguous, classify as OTHER.
5. Output: JSON array of {id, urgency, topic, reason}
6. "reason": one sentence explaining the classification. Max 15 words.
</rules>

<examples>
<example>
<input>
Ticket 1: "Can't log in. Getting 500 error. Need access for client demo in 1 hour."
Ticket 2: "The font on the settings page looks weird on mobile."
</input>
<o>
[
  {"id": 1, "urgency": "CRITICAL", "topic": "AUTHENTICATION", "reason": "Login failure blocking user with time-sensitive need."},
  {"id": 2, "urgency": "LOW", "topic": "UI", "reason": "Cosmetic rendering issue on mobile."}
]
</o>
<reasoning>
Ticket 1: "Can't log in" = AUTHENTICATION. Time pressure ("1 hour") + complete
access failure → CRITICAL. Ticket 2: "looks weird" = cosmetic, no functional
impact → LOW + UI.
</reasoning>
</example>

<example>
<input>
Ticket 3: "We're being charged for 50 seats but only have 12 users."
Ticket 4: "Is there a way to export data to Salesforce?"
</input>
<o>
[
  {"id": 3, "urgency": "HIGH", "topic": "BILLING", "reason": "Overcharge affecting customer billing."},
  {"id": 4, "urgency": "LOW", "topic": "INTEGRATION", "reason": "Feature inquiry about Salesforce export."}
]
</o>
<reasoning>
Ticket 3: active overcharge = significant but not system-down → HIGH + BILLING.
Ticket 4: question about a capability, no reported issue → LOW. Salesforce =
external system → INTEGRATION, not DATA.
</reasoning>
</example>

<example>
<input>
Ticket 5: "Dashboard hasn't loaded for any of our team members since the update this morning. We're completely blocked."
</input>
<o>
[
  {"id": 5, "urgency": "CRITICAL", "topic": "PERFORMANCE", "reason": "Complete dashboard outage blocking all team members."}
]
</o>
<reasoning>
"Any of our team members" + "completely blocked" = affecting all users →
CRITICAL per rule 1. Dashboard not loading is a PERFORMANCE issue, not UI
(functional failure, not cosmetic).
</reasoning>
</example>

<example>
<input>
Ticket 6: "Reports are loading slowly — takes about 45 seconds. Usable but frustrating."
Ticket 7: "When I click 'Export CSV' sometimes nothing happens, other times it works fine."
</input>
<o>
[
  {"id": 6, "urgency": "MEDIUM", "topic": "PERFORMANCE", "reason": "Slow report loading with workaround available."},
  {"id": 7, "urgency": "HIGH", "topic": "DATA", "reason": "Intermittent export failure affecting data access."}
]
</o>
<reasoning>
Ticket 6: slow but "usable" = workaround exists → MEDIUM. Ticket 7: intermittent
failure could mean HIGH or MEDIUM. "Sometimes nothing happens" = feature broken
for some attempts → HIGH per rule 3 (classify ambiguous urgency higher). Export
= DATA, not UI.
</reasoning>
</example>

<example>
<input>
Ticket 8: "Just wanted to say — really loving the new calendar view! Any chance you'd add a weekly layout too?"
</input>
<o>
[
  {"id": 8, "urgency": "LOW", "topic": "UI", "reason": "Positive feedback with feature request for weekly view."}
]
</o>
<reasoning>
Praise + feature request, no issue reported → LOW. Calendar view is a UI
element → UI. Could also be OTHER but UI is a closer match since the request
is about the calendar interface.
</reasoning>
</example>
</examples>

<context>
{{tickets}}
</context>
```

## Why it works for Haiku

- Five examples covering: clear high/low contrast (ex1), billing vs
  question (ex2), "all users blocked" = CRITICAL (ex3), ambiguous urgency
  resolved by rule 3 (ex4), positive feedback edge case (ex5)
- `<reasoning>` tags explicitly reference rule numbers, teaching Haiku
  the decision procedure rather than just showing the answer
- Example 4 demonstrates rule 3 in action (ambiguous → classify higher)
- Example 5 handles input that isn't really a ticket — graceful
  classification without inventing problems
- Urgency levels mapped to concrete symptoms, not abstract severity
