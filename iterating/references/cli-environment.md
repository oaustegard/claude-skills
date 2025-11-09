# CLI Environment (Claude.ai with Project Knowledge)

This guide covers using the iterating skill in the CLI environment, where state is persisted via user-curated Project Knowledge files.

## User Acknowledgment

At session start, tell the user:
> "I'll create a structured document for you to curate into Project Knowledge. In future sessions, I'll automatically retrieve relevant context."

## Environment Detection

In the CLI environment, the `CLAUDE_CODE_REMOTE` environment variable is not set or is not `'true'`:

```python
import os

is_web_environment = os.environ.get('CLAUDE_CODE_REMOTE') == 'true'
if not is_web_environment:
    # CLI environment - use Project Knowledge
    pass
```

## State Persistence: Project Knowledge

In the CLI environment, create structured documents that users curate into their Project Knowledge. The RAG system automatically retrieves relevant context in future sessions.

## Document Format

Compressed format for AI parsing - curated artifact for Project Knowledge:

```markdown
---
title: [Descriptive Title]
date: YYYY-MM-DD
task: Research|Development|Debugging|etc
---

## YYYY-MM-DD HH:MM | Title

**Prev:** [previous context]
**Now:** [current goal]

**Work:**
+: [additions with file:line]
~: [changes with file:line]
!: [fixes with file:line]

**Decisions:**
- [what]: [why] (vs [alternatives])

**Works:** [effective approaches]
**Fails:** [ineffective, why]

**Open:** [questions]
**Next:** [actions]
```

**Key difference from Web/Desktop**: Curated artifact (user chooses what to save to Project Knowledge) vs running log (appended automatically)

## Project Knowledge Integration

### Automatic Retrieval

When Project Knowledge is enabled, the system automatically injects relevant context from:
- Past work documents user curated
- Previous findings marked as important
- Methodology notes and patterns
- Domain-specific knowledge accumulated over time

**You don't need to manually search project knowledge** - relevant content appears in your context automatically.

### Leveraging Retrieved Context

When you see project knowledge in context:

**Recognize it explicitly:**
```
"I see from project knowledge that we previously worked on..."
```

**Build on it:**
```
"Expanding on that approach with..."
```

**Validate it:**
```
"Cross-referencing with current state to verify..."
```

**Update it if needed:**
```
"Previous work suggested X, but now we've learned Y..."
```

## Optimizing for RAG Retrieval

Structure outputs to maximize retrieval effectiveness:

**Good for retrieval:**
- Clear, descriptive headings ("JWT Authentication Implementation" not "Work Done")
- Key terms in topic sentences
- Self-contained insights (readable out of context)
- Explicit methodology notes
- Specific references to files/lines

**Poor for retrieval:**
- Vague headings ("Notes", "Work", "Session 5")
- Context-dependent pronouns ("it", "that", "the thing")
- Scattered insights across paragraphs
- Implicit assumptions
- No file/code references

## User Communication

After creating a document, prompt the user:

> "I've created a structured document. Review the content and consider adding valuable insights to your Project Knowledge. Include:
> - Effective strategies that worked
> - Key decisions and their rationale
> - Patterns or learnings that will help future work
>
> In your next session, I'll automatically retrieve relevant context from your Project Knowledge."

At the start of a new session, acknowledge retrieved context:

> "Based on project knowledge about [topic], I can see we previously [summary of past work]. I'll build on these findings by [current session plan]..."

## Example Session

### Session 1: Initial Research

**User:** "Research microservice communication patterns for our architecture. I'll add findings to project knowledge."

**Claude:**
```
I'll structure my research for easy curation into Project Knowledge.

[Conducts research using web_search and web_fetch]

I've created a research document covering:
- Synchronous vs asynchronous communication patterns
- Event-driven architecture analysis
- Service mesh considerations
- Recommended pattern: Event-driven with message queue for our use case

Review the document and add valuable insights to Project Knowledge:
- Event-driven patterns work best for our decoupled microservices
- Message queues (RabbitMQ/Kafka) provide reliability
- Avoid synchronous HTTP chains (creates tight coupling)

In your next session, I'll automatically retrieve this context.
```

### Session 2: Continuing Work

**User:** "Let's design the event schema for the services."

**Claude:**
```
Based on project knowledge, we decided on event-driven architecture with message queues.
Key insights from previous research:
- Event-driven pattern for decoupling
- Message queue for reliability
- Avoid synchronous HTTP chains

I'll now design event schemas following those patterns...

[Designs schemas based on past decisions]

I've created event schema definitions building on our architecture decision.
The schemas include:
- User events (user.created, user.updated)
- Order events (order.placed, order.fulfilled)
- Standard envelope format (id, timestamp, type, payload)

Adding this to a document you can curate into Project Knowledge for future reference.
```

## Example Document: Research

```markdown
---
title: Microservice Communication Patterns
date: 2025-11-09
task: Research
---

## 2025-11-09 14:30 | Microservice Communication Patterns

**Prev:** None (initial research)
**Now:** Choose communication pattern for microservices - need loose coupling + reliability + async

**Work:**
+: Event-driven architecture research, message queue analysis (RabbitMQ vs Kafka), HTTP anti-patterns
~: Initial HTTP assumption → event-driven based on findings

**Decisions:**
- Event-driven + message queues: loose coupling, async, prevents cascading failures (vs sync HTTP: tight coupling; vs service mesh: premature complexity)
- RabbitMQ: simpler ops, handles 10k+ msg/sec (vs Kafka: overkill for scale; vs AWS SQS: vendor lock-in)

**Works:** Official docs (Fowler, Microsoft), cross-ref multiple sources, pattern-matched to requirements
**Fails:** Generic "best practices" articles (vague), contradicting blog posts (time waste)

**Open:** Exact throughput needs? Schema versioning strategy? Retry/DLQ policies?
**Next:** Design event schemas (users/orders/inventory), setup RabbitMQ dev env, POC publisher/subscriber, load testing
```

## Example Document: Feature Development

```markdown
---
title: JWT Authentication
date: 2025-11-09
task: Feature Development
---

## 2025-11-09 16:45 | JWT Authentication

**Prev:** DB schema + User model complete (Session 1)
**Now:** JWT auth flows - login, token validation, protected routes

**Work:**
+: JWT middleware (src/middleware/auth.ts), Login endpoint (src/routes/auth.ts:45), Protected route decorator, Refresh token mechanism
~: User model - add bcrypt password hash, API errors - return 401 for auth
!: Password comparison case-sensitive → constant-time, Token expiration not validated

**Decisions:**
- JWT 24h + 30d refresh: security/UX balance, industry standard (vs long-lived: security risk; vs session-based: breaks stateless req; vs shorter: poor UX)
- bcrypt cost=12: industry standard, 250ms/hash perf ok (vs Argon2: unnecessary complexity; vs PBKDF2: less GPU-resistant)

**Works:** Middleware pattern (DRY), real API testing via Postman (caught edge cases), OWASP cheat sheet (prevented timing attacks/storage issues)
**Fails:** Custom token format (complex, switched to JWT), httpOnly cookies (mobile incompatible, switched to Bearer tokens)

**Open:** Rate limiting now or later? Account lockout strategy? Password reset flow (email/SMS/TOTP)?
**Next:** Password reset, rate limiting (5/min/IP), integration tests, API docs

## Hypothesis Tracking

H1: Event-driven reduces coupling | Confirmed | Independent deploy, no dependencies, prototype proven (S2)
H2: RabbitMQ sufficient | In Progress | Handles 1k msg/sec, need 10k test (S3 planned)
H3: Schema versioning day-one | Inconclusive | Best practice but adds complexity for small team (S2) - prototype both to assess
```
