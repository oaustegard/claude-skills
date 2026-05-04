---
name: asking-questions
description: "Structure clarifying questions with concrete options and trade-offs. Use when user requests are ambiguous, have multiple valid implementation approaches, involve destructive actions, or require critical architectural decisions."
metadata:
  version: 1.0.7
---

# Asking Questions

Ask clarifying questions when the answer materially changes what you'll build.

## When to Ask

1. **Ambiguous implementation** — multiple valid approaches (middleware vs wrapper, library choice)
2. **Missing critical context** — database type, deployment platform, credential strategy
3. **Destructive actions** — "clean up files" could mean delete or archive
4. **Scope clarification** — vague terms like "refactor," "optimize," "improve"
5. **Conflicting requirements** — "make it faster" + "add extensive logging"
6. **Trade-offs** — solutions with different cost/benefit profiles

**Skip when**: request is unambiguous, answer is derivable from codebase context, or the question wouldn't change your implementation.

## Question Structure

1. **State context** — show you've analyzed the situation
2. **Present 2-5 options** with brief trade-offs
3. **Ask directly** — clear question guiding the decision
4. **Offer a default** (optional) — for less critical decisions

```
I see you're using JWT auth. To add refresh tokens, I can:
1. **httpOnly cookies** — more secure, harder to XSS
2. **localStorage** — simpler, works with mobile apps
3. **In-memory only** — most secure, lost on refresh

What works best for your use case?
```

## Layer Questions Progressively

Ask one decision at a time, not everything at once:

- First: "Should I use WebSockets, SSE, or polling?"
- Then: "For WebSockets, Socket.io (easier) or native (lighter)?"

**Avoid**: "Should I use WebSockets or SSE or polling and if WebSockets should I use Socket.io or native and should I implement reconnection and..."

## Examples

**Good**: "You mentioned 'clean up migrations.' Archive to /old-migrations or delete entirely? (Note: deletion breaks databases that haven't run them yet)"

**Bad**: "What do you mean by clean up?" — too vague, doesn't guide the decision.

## After Receiving an Answer

Acknowledge the choice, proceed immediately, and apply the stated preference to similar future decisions.
