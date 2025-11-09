# CLI Environment (Claude.ai with Project Knowledge)

This guide covers using the iterating skill in the CLI environment, where state is persisted via user-curated Project Knowledge files.

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

Create documents optimized for human curation and RAG retrieval:

```markdown
---
title: [Topic/Task] - Session [N]
date: [YYYY-MM-DD]
task: [Type: Research/Development/Debugging/etc]
---

# [Topic/Task] - Session [N]

## Quick Summary
[2-3 sentences capturing essence of work]

## Methodology Notes
**Effective strategies:**
- [What approaches worked well]
- [Which techniques were most valuable]

**Ineffective approaches:**
- [What didn't work and why]

## Key Progress

### [Area 1]
**What was done:** [Description]
**Key insight:** [Main takeaway]
**Confidence:** [High/Medium/Low] - [Reasoning]

**Code locations:**
- [file.ts:line] - [What's there]

### [Area 2]
[Same structure]

## Decisions Made
- **Decision:** [What]
  **Rationale:** [Why]
  **Alternatives:** [What else was considered]

## Open Items
- [What remains unfinished]
- [What requires further investigation]

## Recommended Next Steps
- [Logical next actions]
- [Areas for deeper work]
```

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
title: Microservice Communication Patterns - Session 1
date: 2025-11-09
task: Research
---

# Microservice Communication Patterns - Session 1

## Quick Summary
Researched communication patterns for microservices architecture. Event-driven architecture with message queues recommended for our use case due to loose coupling requirements and need for reliability. Synchronous HTTP should be avoided for inter-service communication.

## Methodology Notes
**Effective strategies:**
- Started with official architecture documentation (Martin Fowler, Microsoft Architecture)
- Cross-referenced multiple sources for validation
- Focused on patterns matching our requirements (loose coupling, async processing)

**Ineffective approaches:**
- Generic "best practices" articles were too vague
- Blog posts often contradicted each other without rationale

## Key Findings

### Event-Driven Architecture
**What we found:** Event-driven patterns provide loose coupling between services through asynchronous message passing
**Key insight:** Services publish events when state changes, other services subscribe to relevant events - no direct dependencies
**Confidence:** High - industry standard, well-documented, matches our requirements

**Sources:**
- Microsoft Cloud Design Patterns (official)
- Martin Fowler on Event-Driven Architecture
- AWS Microservices whitepaper

### Message Queue Selection
**What we found:** RabbitMQ and Apache Kafka are leading options for message queues
**Key insight:** RabbitMQ better for our scale (simpler operations, sufficient throughput), Kafka better for very high throughput needs
**Confidence:** Medium - need to validate throughput requirements

**Decision:** Start with RabbitMQ for simplicity
**Rationale:** Our current scale doesn't justify Kafka complexity; RabbitMQ handles 10k+ msg/sec easily
**Alternatives:** Kafka (overkill for our needs), AWS SQS (vendor lock-in concern)

### Anti-Pattern: Synchronous HTTP Chains
**What we found:** Chaining synchronous HTTP calls between services creates tight coupling and cascading failures
**Key insight:** Avoid Service A → HTTP → Service B → HTTP → Service C patterns
**Confidence:** High - well-documented anti-pattern

## Open Items
- Validate exact throughput requirements for message queue selection
- Investigate message schema versioning strategies
- Determine retry and dead-letter queue policies

## Recommended Next Steps
- Design event schemas for our domain (users, orders, inventory)
- Set up RabbitMQ in development environment
- Implement first event publisher/subscriber pair as proof of concept
```

## Example Document: Feature Development

```markdown
---
title: Authentication Implementation - Session 2
date: 2025-11-09
task: Feature Development
---

# User Authentication Implementation - Session 2

## Quick Summary
Implemented JWT-based authentication with secure password hashing. System now supports user login, token validation, and protected routes. Open items: password reset, rate limiting, comprehensive testing.

## Methodology Notes
**Effective strategies:**
- Middleware pattern for auth logic provided clean separation of concerns
- Early testing with actual requests helped catch edge cases
- OWASP authentication cheat sheet review prevented common vulnerabilities

**Ineffective approaches:**
- Custom token format added unnecessary complexity (switched to JWT standard)
- httpOnly cookies problematic for mobile API clients (switched to Bearer tokens)

## Key Progress

### Authentication System
**What was done:** Implemented JWT token system with login endpoint and protected route middleware
**Key insight:** Refresh tokens essential for balancing security and UX - users stay logged in without compromising security through long-lived access tokens
**Confidence:** High - follows industry standards and security best practices

**Code locations:**
- src/middleware/auth.ts:15 - JWT validation middleware
- src/routes/auth.ts:45 - Login endpoint
- src/models/User.ts:78 - Password hashing with bcrypt

### Security Decisions
**Decision:** bcrypt with cost factor 12 for password hashing
**Rationale:** Industry standard, proven security, good performance tradeoff (250ms per hash on our hardware)
**Alternatives:** Argon2 (rejected - unnecessary complexity for our scale), PBKDF2 (rejected - bcrypt more resistant to GPU attacks)

**Decision:** 24-hour access tokens + 30-day refresh tokens
**Rationale:** Limits access token exposure window while maintaining good UX with refresh tokens
**Alternatives:** Longer-lived access tokens (rejected - security risk), sessions (rejected - statelessness requirement), shorter expiration (rejected - poor UX)

## Open Items
- Rate limiting on login endpoint to prevent brute force attacks
- Account lockout mechanism after N failed attempts
- Password reset flow implementation (email token-based)
- Comprehensive integration testing of auth flows

## Recommended Next Steps
- Implement password reset (next critical security feature)
- Add rate limiting (5 attempts per minute per IP)
- Write integration tests for login, token refresh, protected routes
- Document authentication in API docs for consumers
```

## Advanced: Hypothesis Tracking (Research)

For research spanning multiple sessions:

```markdown
## Hypothesis Tracking

### H1: Event-driven architecture reduces coupling
**Status:** Confirmed
**Evidence:** Services can be deployed independently, no direct dependencies, demonstrated in prototype
**Session:** Session 2

### H2: RabbitMQ sufficient for our throughput
**Status:** In Progress
**Evidence:** Handles test load (1000 msg/sec) easily, need to test at 10k msg/sec
**Session:** Session 3 (planned)
**Next test:** Load testing with realistic message sizes and patterns

### H3: Schema versioning needed from day one
**Status:** Inconclusive
**Evidence:** Best practices recommend it, but adds complexity for our small team
**Session:** Session 2
**Next test:** Prototype with and without versioning to assess complexity/benefit
```

## Tips for Effective Documentation

1. **Write for future you**: Assume you'll forget the context
2. **Be specific**: Include file paths, line numbers, exact error messages
3. **Explain why**: Decisions are more valuable than actions
4. **Track alternatives**: Document what you didn't choose and why
5. **Note confidence levels**: Help future you know what to validate
6. **Link to sources**: URLs, docs, commits for traceability
