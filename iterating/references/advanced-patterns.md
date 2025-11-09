# Advanced Patterns for Iterative Work

Advanced multi-session patterns beyond basic DEVLOG usage.

## Feature Status Tracking

For complex features spanning 5+ sessions:

```markdown
### Feature: User Authentication
**Progress:** 60% | Started: 2025-11-05 | Target: 2025-11-15

**Done:** ✅ User model, JWT, Login, Middleware
**Active:** 🔄 Password reset (50%) - Blocker: email provider decision
**Backlog:** ⏳ Account lockout, 2FA, UI
```

## Hypothesis-Driven Debugging

Track hypotheses to avoid repeating failed approaches:

```markdown
### Bug: Memory leak (200MB→2GB over 2h)

H1: Large objects retained | Refuted | Heap snapshot clean (S1)
H2: Event listeners leak | ✅ Confirmed | 10k+ listeners found, fixed with removeAllListeners() (S2)
H3: Circular refs | Invalidated | H2 was root cause

**Tried:** Heap snapshots, profiling, test case
**Dead ends:** GC tuning, object size reduction
```

## Architecture Evolution

Track decision evolution:

```markdown
### Caching Strategy

**V1** (S1-3): In-mem LRU, 1000 items | Issue: 45% hit rate, too small
**V2** (S4-6): Redis 2h TTL | Issue: 85% hit rate but stale data
**V3** (S7+): Redis tiered TTL (5m/1h/24h by data type) | 90% hit rate, fresh data

**Lessons:** Access patterns > size; different data needs different TTL; monitor hit rate + staleness
```

## Implementation Patterns

**Incremental:** S1=Core happy path, S2=Error handling, S3=Tests, S4=Optimization

**Spike-and-Implement:** S1=Quick spike (1-2h, throwaway code, validate approach), S2=Production impl, S3=Polish

**Research-and-Apply:** S1=Research (docs/articles, decision doc), S2=Implement (follow best practices), S3=Refine

## Cross-Session Analysis

**Pattern Recognition:** Auth bugs cluster Fridays (S5,7,9,12) → Thu deployments → add pre-deploy tests → 90% reduction

**Contradictions:** Hit rate 85% (S3) vs 60% (S7) → user base 3x → access patterns changed → need dynamic TTL

**Trend Tracking:** API 200ms (S1) → 180ms (S3, caching) → 250ms (S5, features) → 150ms (S7, optimized) | Insight: optimize proactively

## Large Project Template (10+ sessions)

```markdown
# Project: E-commerce Backend
**Status:** 60% | Started: Oct 1 | Target: Dec 1

**Components:**
✅ Auth (S1-4: src/auth/*)
🔄 Catalog (S5-8: 75%, remaining: search, inventory)
⏳ Cart (S9-11 planned)
⏳ Payments (S12-15 planned)

**Targets:** <200ms API, <2s page | Current: 150ms API ✅

**Decisions:** PostgreSQL (ACID, S1), JWT (stateless, S2), Redis (perf, S5), Stripe (S11)

**Issues:** Search slow >10k products (S8) → Elasticsearch (S13)

**Lessons:** Integration tests first, API contracts early, performance budget from day one
```

**Tips:** Summarize every 5 sessions, log decisions, track issues, update architecture, celebrate milestones
