# CLI Environment (Claude.ai with Project Knowledge)

This guide covers using the iterating skill in the CLI environment, where state is persisted via user-curated Project Knowledge files.

## User Acknowledgment

At session start, tell the user:
> "I'll create a structured document for you to curate into Project Knowledge. In future sessions, I'll automatically retrieve relevant context."

## Environment Detection

CLI environment lacks `CLAUDE_CODE_REMOTE` variable or it's not `'true'`.

## State Persistence: Project Knowledge

Create structured documents for users to curate into Project Knowledge. RAG system automatically retrieves context in future sessions.

## Document Format

Use DEVLOG format from SKILL.md with frontmatter for curated artifacts:

```markdown
---
title: [Descriptive Title]
date: YYYY-MM-DD
task: Research|Development|Debugging|etc
---

[Use DEVLOG format from SKILL.md]
```

**Key difference**: Curated artifact (user saves to Project Knowledge) vs running log (auto-appended).

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

## Example

**Session 1:** "[Research] Created doc: Event-driven + RabbitMQ decision. Curate key findings to Project Knowledge."

**Session 2:** "From Project Knowledge: event-driven decided. [Designs schemas] Created: event schema doc for curation."
