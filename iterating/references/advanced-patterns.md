# Advanced Patterns for Iterative Work

Advanced multi-session patterns beyond basic WorkLog usage.

## Feature Status Tracking

For complex features spanning 5+ sessions:

```markdown
### Feature: User Authentication
**Progress:** 60% | Started: 2025-11-05 | Target: 2025-11-15

**Done:** ✅ User model, JWT service, Login endpoint, Middleware
**Active:** 🔄 Password reset (50%) - Blocker: email provider decision pending
**Backlog:** ⏳ Account lockout, 2FA integration, UI polish
```

## Hypothesis-Driven Debugging

Track hypotheses to avoid repeating failed approaches:

```markdown
### Bug: Memory leak (200MB→2GB over 2h)

**Hypotheses:**
H1: Large objects retained | Refuted | Heap snapshot clean (v2)
H2: Event listeners leak | ✅ Confirmed | 10k+ listeners, fixed with removeAllListeners() (v3)
H3: Circular references | Invalidated | H2 was root cause

**Tried:** Heap snapshots, profiling, minimal reproduction test case
**Dead ends:** GC tuning (no effect), object pool optimization (wrong direction)

**Solution:** src/events/emitter.ts:89-110 - Added cleanup on component unmount
```

## Architecture Evolution

Track decision evolution across versions:

```markdown
### Caching Strategy Evolution

**v1-v3:** In-memory LRU, 1000 items
- Issue: 45% hit rate, too small for production load
- Decision: Need distributed cache

**v4-v6:** Redis 2h TTL for all data
- Issue: 85% hit rate BUT stale data causing user complaints
- Decision: Differentiate by data type

**v7+:** Redis tiered TTL (5m/1h/24h by data type)
- Result: 90% hit rate, fresh data ✅
- Lesson: Access patterns > cache size; different data needs different TTL
```

## Implementation Patterns

**Incremental:** 
- v1: Core happy path
- v2: Error handling  
- v3: Tests and validation
- v4: Performance optimization

**Spike-and-Implement:** 
- v1: Quick spike (1-2h, throwaway code) - validates approach
- v2: Production implementation - follows best practices
- v3: Polish and edge cases

**Research-and-Apply:** 
- v1: Research phase (docs/articles, create decision document)
- v2: Implement following best practices discovered
- v3: Refine based on real usage

## Cross-Session Analysis

**Pattern Recognition:**
- Auth bugs cluster on Fridays (v5, v7, v9, v12)
- Root cause: Thursday deployments → insufficient pre-deploy testing
- Solution: Added comprehensive auth test suite (v13)
- Result: 90% reduction in Friday incidents

**Detecting Contradictions:**
- Cache hit rate 85% (v3) vs 60% (v7) - what changed?
- Investigation: User base 3x larger → access patterns shifted
- Solution: Dynamic TTL based on access frequency (v8)

**Trend Tracking:**
- API latency: 200ms (v1) → 180ms (v3, caching) → 250ms (v5, features) → 150ms (v7, optimized)
- Insight: Proactive optimization > reactive firefighting

## Handoff Pattern Examples

### Research → Implementation Handoff

**v1 (Chat - Research):**
```markdown
**Status:** needs_review
**Progress:** Research complete ✅ | Implementation pending ⏳

**Decisions:**
- PostgreSQL over MongoDB: ACID guarantees needed for financial transactions
- Row-level security: Multi-tenancy isolation at database level

**Next:**
- [HIGH] Create database schema with RLS policies
- [HIGH] Implement authentication layer
- [MED] Setup migration scripts
```

**v2 (Code - Implementation):**
```markdown
**Status:** in_progress  
**Progress:** 40% | Schema ✅ | Auth layer 70% 🔄 | Migrations pending ⏳

**Files:**
- `prisma/schema.prisma` (Database schema with RLS)
  - L45-89: User and Tenant models with relationships
- `src/auth/rls.ts` (Row-level security policies, partial)
  - L23-56: Tenant isolation logic (needs testing)

**Next:**
- [HIGH] Complete RLS policies and test isolation
- [HIGH] Add migration generation scripts
```

### Parallel Workstreams

When multiple features in progress, use separate Work Logs:

```
Auth-Refactor-WorkLog-v5.md       (Auth team, 70% complete)
Payment-Integration-WorkLog-v3.md (Payments team, 50% complete)
UI-Redesign-WorkLog-v2.md         (Frontend team, 30% complete)
```

**Cross-references in Work Logs:**
```markdown
**Dependencies:**
- Payment integration depends on Auth-Refactor-WorkLog-v5
- Need: OAuth flow must be complete before Stripe checkout
- Status: Auth v5 shows OAuth ready ✅
```

### Long-Running Project Template (10+ sessions)

```markdown
# E-commerce Backend Work Log

**Status:** in_progress
**Progress:** Phase 2/3 - 60% overall | Started: Oct 1 | Target: Dec 1

## Components Status

**Phase 1: Foundation** (v1-v8) ✅ Completed Oct 15
- Auth system (src/auth/*) ✅
- Database schema (prisma/*) ✅
- API framework (src/api/*) ✅

**Phase 2: Features** (v9-v16) 🔄 Current - 60% complete
- Product catalog (75% complete)
  - Search implemented ✅
  - Inventory tracking 🔄 (v14 in progress)
- Shopping cart (50% complete)
  - Cart operations ✅
  - Persistence pending ⏳
- Payment processing (planned for v17-20)

**Phase 3: Scale** (v21+) ⏳ Planned
- Caching layer (Redis)
- Read replicas
- Rate limiting

## Performance Targets

- API Response: <200ms (current: 150ms ✅)
- Page Load: <2s (current: 1.8s ✅)
- Search: <100ms (current: 85ms ✅)

## Key Decisions Log

- v1: PostgreSQL for ACID guarantees
- v2: JWT for stateless auth (vs sessions)
- v5: Redis for session storage (performance)
- v11: Stripe for payments (vs in-house)
- v13: Elasticsearch for search (>10k products)

## Current Blockers

- v14: Inventory sync needs warehouse API credentials (ETA: Nov 20)

## Lessons Learned

- Integration tests first → caught issues early
- API contracts upfront → prevented breaking changes
- Performance budget from day one → stayed within targets
```

**Tips for long projects:**
- Summarize progress every 5 versions
- Log all major decisions with version number
- Track blockers with ETAs
- Update architecture diagram as it evolves
- Celebrate milestone completions

## Blocked → Unblocked Pattern

```markdown
## v5 | 2025-11-10 14:00 | Payment Integration [BLOCKED]

**Blockers:** Missing production Stripe API keys
- Owner: @ops-team
- Requested: 2025-11-10 10:00
- ETA: 24 hours
- Workaround: Continuing with test keys in staging

**Next:**
- [HIGH] [BLOCKED] Configure production Stripe webhook
- [MED] Complete payment flow tests (can proceed with staging)
- [LOW] Add payment analytics
```

Then later:

```markdown  
## v6 | 2025-11-11 09:00 | Payment Integration Unblocked

**Prev:** v5 blocked on Stripe keys
**Now:** Keys received, configuring production

**Progress:** 80% → 90% | Unblocked ✅

**Blocker Resolution:**
- Stripe production keys received from @ops-team
- Configured in environment variables
- Webhook endpoint verified

**Next:**
- [HIGH] Deploy to production and test end-to-end
- [MED] Monitor first real transactions
- [LOW] Add payment analytics dashboard
```

## Review Cycle Pattern

```markdown
## v8 | 2025-11-12 16:00 | Feature Complete [NEEDS_REVIEW]

**Status:** needs_review
**Progress:** 100% implementation | Testing complete ✅ | Review pending ⏳

**Review Checklist:**
- [ ] Code quality and style
- [ ] Test coverage (current: 85%)
- [ ] Performance benchmarks
- [ ] Security review
- [ ] Documentation complete

**Reviewer Notes:**
@tech-lead: Please focus on:
- Error handling in src/payments/stripe.ts:145-180
- Race condition prevention in webhook handler
- Token optimization strategy

**Next:**
- [HIGH] Address review feedback
- [MED] Update documentation based on review
```

Then after review:

```markdown
## v9 | 2025-11-13 10:00 | Review Applied

**Prev:** v8 needs_review → feedback received
**Status:** in_progress (applying feedback)

**Review Feedback Applied:**
- ✅ Enhanced error handling in stripe.ts:145-180
- ✅ Added mutex lock for webhook race condition
- ✅ Optimized token refresh strategy
- 🔄 Documentation updates in progress

**Next:**
- [HIGH] Complete documentation updates
- [HIGH] Re-test after changes
- [MED] Request final approval
```

## Token Budget Management

When approaching token limits:

```markdown
**Progress:** Phase 2 - 60% | ⚠️ Token budget: 40% remaining

**Completed This Session:**
- ✅ Payment webhook handler (HIGH priority)
- ✅ Error recovery logic (HIGH priority)

**Deferred to Next Session:**
- ⏳ Payment analytics (LOW priority)
- ⏳ Admin dashboard (LOW priority)
- ⏳ Email notifications (MED priority)

**Next Session Priority:**
- [HIGH] Complete MED priority: Email notifications
- [HIGH] Deploy to staging for testing
- [MED] Then tackle LOW priority items if budget allows
```

**Why this matters:** User may run out of tokens mid-session. Progress tracking + priority system ensures HIGH items completed first.
