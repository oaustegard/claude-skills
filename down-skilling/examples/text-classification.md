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
Ticket 3: "We're being charged for 50 seats but only have 12 users."
</input>
<o>
[
  {"id": 1, "urgency": "CRITICAL", "topic": "AUTHENTICATION", "reason": "Login failure blocking user with time-sensitive need."},
  {"id": 2, "urgency": "LOW", "topic": "UI", "reason": "Cosmetic rendering issue on mobile."},
  {"id": 3, "urgency": "HIGH", "topic": "BILLING", "reason": "Overcharge affecting customer billing."}
]
</o>
</example>
</examples>

<context>
{{tickets}}
</context>
```

## Why it works for Haiku

- Ambiguity resolution rule (3): "if unclear, go higher" prevents Haiku
  from inconsistently guessing
- Default topic (4): "OTHER" prevents forced categorization
- Reason field constrains Haiku's tendency to over-explain
