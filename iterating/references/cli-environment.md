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

CLI uses the **same unified format** as Web/Desktop, adapted as a curated artifact with frontmatter:

```markdown
---
title: [Descriptive Session Title]
date: [YYYY-MM-DD]
task: [Type: Research/Development/Debugging/etc]
---

## [YYYY-MM-DD HH:MM] - Session: [Descriptive Title]

### Context
[What we're working on and why - slightly more narrative for standalone reading]

### Work Completed
**Added:**
- [New features, code, or insights]

**Changed:**
- [Modifications to existing work]

**Fixed:**
- [Bugs resolved, issues addressed]

### Key Decisions
- **Decision:** [What was decided]
  **Rationale:** [Why this approach]
  **Alternatives considered:** [What else was evaluated]

### Effective Approaches
- [What strategies/techniques worked well]
- [Patterns to reuse in future sessions]

### Ineffective Approaches
- [What didn't work and why]
- [Pitfalls to avoid in future sessions]

### Open Questions
- [Unresolved issues or areas needing investigation]

### Next Steps
- [ ] [Specific next action]
- [ ] [Follow-up task]
```

**Key difference from Web/Desktop**: This is a **curated artifact** rather than a running log entry. The content is slightly more polished and narrative since the user is the gatekeeper deciding what to save to Project Knowledge.

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

## [2025-11-09 14:30] - Session: Microservice Communication Patterns Research

### Context
Researching communication patterns for our microservices architecture. Need to choose patterns that support loose coupling and reliability for our distributed system with async processing requirements.

### Work Completed
**Added:**
- Research on event-driven architecture patterns
- Analysis of message queue options (RabbitMQ vs Kafka)
- Documentation of synchronous HTTP anti-patterns

**Changed:**
- Initial assumption was to use HTTP; shifted to event-driven based on research

**Fixed:**
- N/A (research session)

### Key Decisions
- **Decision:** Use event-driven architecture with message queues
  **Rationale:** Provides loose coupling between services, enables async processing, prevents cascading failures
  **Alternatives considered:** Synchronous HTTP (rejected - tight coupling), Service mesh (deferred - adds complexity)

- **Decision:** Start with RabbitMQ for message queue
  **Rationale:** Simpler operations than Kafka, handles 10k+ msg/sec which exceeds our current needs
  **Alternatives considered:** Kafka (overkill for our scale), AWS SQS (vendor lock-in concern)

### Effective Approaches
- Started with official architecture documentation (Martin Fowler, Microsoft Architecture) - provided solid foundations
- Cross-referenced multiple authoritative sources for validation
- Focused research on patterns matching our specific requirements (loose coupling, async)

### Ineffective Approaches
- Generic "best practices" articles were too vague and not actionable
- Blog posts often contradicted each other without clear rationale - wasted time

### Open Questions
- What are our exact throughput requirements? (Need to validate with load testing)
- How should we handle message schema versioning from the start?
- What retry and dead-letter queue policies should we implement?

### Next Steps
- [ ] Design event schemas for our domain (users, orders, inventory)
- [ ] Set up RabbitMQ in development environment
- [ ] Implement first event publisher/subscriber pair as proof of concept
- [ ] Conduct load testing to validate throughput assumptions
```

## Example Document: Feature Development

```markdown
---
title: Authentication Implementation - Session 2
date: 2025-11-09
task: Feature Development
---

## [2025-11-09 16:45] - Session: JWT Authentication Implementation

### Context
Building JWT-based authentication for the API. Previous session (Session 1) established the database schema and User model. Today focusing on the core auth flows: login, token validation, and protected routes.

### Work Completed
**Added:**
- JWT token generation and validation middleware (src/middleware/auth.ts)
- Login endpoint with email/password verification (src/routes/auth.ts:45)
- Protected route decorator for securing endpoints
- Refresh token mechanism for long-lived sessions

**Changed:**
- Updated User model to include password hashing with bcrypt
- Modified API error handling to return proper 401 responses for auth failures

**Fixed:**
- Password comparison was case-sensitive (now uses constant-time comparison)
- Token expiration not being validated properly in middleware

### Key Decisions
- **Decision:** Use JWT with 24-hour access tokens + 30-day refresh tokens
  **Rationale:** Balances security (short-lived access tokens) with UX (refresh tokens prevent frequent re-login). Industry standard approach.
  **Alternatives considered:** Longer-lived access tokens (rejected - security risk), session-based auth (rejected - breaks statelessness requirement), shorter expiration (rejected - poor UX)

- **Decision:** Store passwords with bcrypt, cost factor 12
  **Rationale:** Industry standard, proven security, good performance tradeoff (250ms per hash on our hardware)
  **Alternatives considered:** Argon2 (rejected - unnecessary complexity for our scale), PBKDF2 (rejected - bcrypt more resistant to GPU attacks)

### Effective Approaches
- Middleware pattern kept auth logic DRY across all protected routes
- Testing with actual API requests (via Postman) caught edge cases early
- Reviewing OWASP authentication cheat sheet prevented common vulnerabilities (timing attacks, improper password storage, etc.)

### Ineffective Approaches
- Initially tried custom token format (unnecessarily complex, switched to standard JWT)
- Attempted to use httpOnly cookies for API (problematic for mobile clients, switched to Bearer tokens in Authorization header)

### Open Questions
- Should we implement rate limiting on the login endpoint now or later? (Prevents brute force attacks)
- Do we need account lockout after N failed attempts? (Security vs UX tradeoff)
- How to handle password reset flow securely? (Email token-based? SMS? TOTP?)

### Next Steps
- [ ] Implement password reset functionality (next critical security feature)
- [ ] Add rate limiting to login endpoint (5 attempts per minute per IP)
- [ ] Write integration tests for auth flows (login, token refresh, protected routes)
- [ ] Document API authentication in README for API consumers
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
