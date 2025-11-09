# Advanced Patterns for Iterative Work

This guide covers advanced patterns for multi-session iterative work across different task types.

## Multi-Session Feature Development

For complex features spanning many sessions, break down the work and track progress systematically.

### Pattern Overview

**Session 1:** Design and architecture planning
**Session 2-N:** Incremental implementation with learnings
**Session N+1:** Testing, refinement, documentation

### Tracking Feature Status

Document feature progress to maintain clarity across sessions:

```markdown
### Feature Status: User Authentication System
**Progress:** 60% complete
**Started:** 2025-11-05
**Target:** 2025-11-15

**Completed:**
- ✅ User model with password hashing
- ✅ JWT token generation and validation
- ✅ Login endpoint
- ✅ Protected route middleware

**In Progress:**
- 🔄 Password reset flow - 50% done
  **Blocker:** Need to decide on email service provider
  **Next:** Evaluate SendGrid vs AWS SES

**Not Started:**
- ⏳ Account lockout after failed attempts
- ⏳ Two-factor authentication
- ⏳ Session management UI
```

### Session-to-Session Handoff

At the end of each session, document:
- What was completed
- What's partially done (and where you left off)
- Blockers encountered
- Next logical step

At the start of next session:
- Review status
- Address blockers first
- Continue from documented next step

## Debugging Across Sessions

For complex bugs requiring multiple investigation sessions:

### Hypothesis Testing Framework

```markdown
### Bug: Memory leak in data processing pipeline

**Symptoms:**
- Memory usage grows from 200MB to 2GB over 2 hours
- Occurs only with production-size datasets (>10k items)
- GC doesn't reclaim memory

**Hypothesis 1:** Large objects not being released
**Status:** Refuted
**Evidence:** Heap snapshot shows no large objects retained after processing
**Session:** Session 1 (2025-11-08)

**Hypothesis 2:** Event listeners not being cleaned up
**Status:** Confirmed
**Evidence:** Found 10k+ event listeners registered on event emitter, listeners reference processed items
**Solution:** Added removeAllListeners() after processing batch
**Session:** Session 2 (2025-11-09)
**Result:** Memory stays stable at 250MB after fix

**Hypothesis 3:** Circular references preventing GC
**Status:** Invalidated (H2 was root cause)
**Session:** Session 2
```

### Debugging Checklist

Track what you've tried to avoid repeating approaches:

```markdown
### Debugging Checklist

**Tried:**
- [x] Heap snapshots (no large objects)
- [x] Memory profiling (identified event listeners)
- [x] Code review of object lifecycle
- [x] Reduced test case (reproduced with 1k items)

**Not Yet Tried:**
- [ ] V8 native memory profiler
- [ ] Comparison with reference implementation

**Known Dead Ends:**
- Switching GC algorithm (no effect)
- Reducing object size (not the issue)
```

## Architecture Evolution

Track how architectural decisions evolve over time and why:

### Decision Evolution Template

```markdown
### Architecture: Data Caching Strategy

**Version 1** (Session 1-3, Nov 1-5):
**Approach:** In-memory LRU cache with 1000-item limit
**Why:** Simple to implement, good for getting started
**Issue:** Cache eviction too frequent, hit rate only 45%
**Lesson:** Need to understand access patterns before sizing cache

**Version 2** (Session 4-6, Nov 6-10):
**Approach:** Redis cache with 2-hour TTL, no size limit
**Why:** External cache allows sharing across instances, much larger capacity
**Result:** Hit rate improved to 85%, but stale data issues
**Issue:** TTL too long for frequently-changing data
**Lesson:** Need differentiated TTL based on data type

**Current** (Session 7+, Nov 11+):
**Approach:** Redis cache with tiered TTL (5min for user data, 1hr for static data, 24hr for computed aggregates)
**Why:** Balances freshness needs with cache effectiveness
**Result:** 90% hit rate, no stale data complaints
**Lessons Learned:**
- Access patterns matter more than cache size
- Different data types need different strategies
- Monitor hit rate and staleness separately
```

## Pattern: Incremental Implementation

Proven pattern for building features iteratively:

### Phase 1: Core Functionality (Session 1)
**Goal:** Get it working with happy path
**Deliverable:** Basic feature functional in ideal conditions
**Example:** Login works with valid credentials

### Phase 2: Error Handling (Session 2)
**Goal:** Handle edge cases and errors gracefully
**Deliverable:** Feature works reliably with invalid inputs
**Example:** Proper error messages for wrong password, missing fields, locked accounts

### Phase 3: Testing (Session 3)
**Goal:** Automated tests for core and edge cases
**Deliverable:** Comprehensive test suite
**Example:** Unit tests for auth logic, integration tests for API endpoints

### Phase 4: Optimization (Session 4)
**Goal:** Performance and UX improvements
**Deliverable:** Production-ready feature
**Example:** Rate limiting, caching, loading states

## Pattern: Spike and Implement

For uncertain technical approaches:

### Session 1: Quick Spike
**Goal:** Validate approach viability quickly
**Time box:** 1-2 hours max
**Deliverable:** Proof of concept, learnings documented
**Quality bar:** Throwaway code is fine

**Example:**
```
Spike: Can we use WebAssembly for image processing?
Result: Yes, 3x faster than JavaScript
Learnings:
- WASM module loading adds 200ms startup time
- Memory transfer between JS/WASM is expensive
- Best for long-running operations, not single images
Decision: Use WASM for batch processing, not single images
```

### Session 2: Proper Implementation
**Goal:** Build production-quality version based on spike learnings
**Deliverable:** Well-tested, documented implementation
**Quality bar:** Production-ready

### Session 3: Polish
**Goal:** Edge cases, error handling, performance
**Deliverable:** Fully production-ready feature

## Pattern: Research and Apply

For learning-intensive tasks:

### Session 1: Research
**Goal:** Understand landscape, options, best practices
**Methods:** Read docs, articles, code examples
**Deliverable:** Decision document with recommendations

### Session 2: Apply
**Goal:** Implement based on research learnings
**Methods:** Follow best practices discovered
**Deliverable:** Working implementation

### Session 3: Iterate
**Goal:** Refine based on real-world learnings
**Methods:** Address gaps found during implementation
**Deliverable:** Polished solution

## Cross-Session Synthesis

When accumulating knowledge over many sessions:

### Pattern Recognition

Look for patterns across sessions:
```markdown
## Pattern Identified: Authentication Issues Cluster on Fridays

**Observation:** 80% of auth bugs reported on Fridays
**Sessions:** 5, 7, 9, 12
**Investigation:** Deployment schedule - new auth code deployed Thursdays
**Action:** Add auth-specific integration tests to pre-deployment checks
**Result:** Friday auth issues dropped 90%
```

### Contradictions

When findings contradict, investigate:
```markdown
## Contradiction: Cache Hit Rate

**Session 3 finding:** Hit rate 85% with 1-hour TTL
**Session 7 finding:** Hit rate 60% with 1-hour TTL
**Investigation:** User base grew 3x, access pattern changed
**Resolution:** Need dynamic TTL based on load
**Lesson:** Metrics need context (when, what load, etc.)
```

### Trend Analysis

Track how metrics evolve:
```markdown
## Trend: API Response Time

**Session 1:** 200ms average (baseline)
**Session 3:** 180ms (after caching)
**Session 5:** 250ms (after feature additions)
**Session 7:** 150ms (after optimization)

**Insight:** Features degraded performance before optimization
**Learning:** Build performance budget, optimize proactively
```

## Multi-Session Project Template

For large projects spanning 10+ sessions:

```markdown
# Project: E-commerce Platform Backend

## Project Status
**Started:** 2025-10-01
**Phase:** Implementation (60% complete)
**Target:** 2025-12-01

## High-Level Architecture
[Diagram or description]
[Links to architecture decisions]

## Component Status

### Authentication & Authorization
**Status:** Complete
**Sessions:** 1-4
**Key files:** src/auth/*, src/middleware/auth.ts

### Product Catalog
**Status:** In Progress (75%)
**Sessions:** 5-8
**Remaining:** Search functionality, inventory integration

### Shopping Cart
**Status:** Not Started
**Planned:** Sessions 9-11

### Payment Processing
**Status:** Not Started
**Planned:** Sessions 12-15

## Cross-Cutting Concerns

### Performance
**Targets:** <200ms API response, <2s page load
**Status:** On track (150ms avg API response)

### Security
**Checklist:**
- [x] Authentication implemented
- [x] Authorization middleware
- [ ] Rate limiting (in progress)
- [ ] Input validation (planned)

## Major Decisions Log
1. **PostgreSQL for database** (Session 1) - ACID compliance needed
2. **JWT for auth** (Session 2) - Stateless API requirement
3. **Redis for caching** (Session 5) - Improved product catalog performance
4. **Stripe for payments** (Session 11) - Best API, pricing acceptable

## Known Issues
1. Search performance degrades with >10k products (Session 8)
   - Planned: Elasticsearch integration (Session 13)
2. Cart not persistent across sessions (Session 9)
   - Planned: Session storage (Session 10)

## Lessons Learned
- Start with integration tests for API endpoints (catches more bugs)
- Document API contracts early (prevents breaking changes)
- Performance budget from day one (easier than retrofitting)
```

## Tips for Long-Running Projects

1. **Weekly summaries**: Every 5 sessions, write a summary of progress
2. **Decision log**: Keep a chronological list of major decisions
3. **Known issues tracker**: Don't lose track of deferred problems
4. **Metrics dashboard**: Track key metrics over time
5. **Architecture updates**: Update diagrams as system evolves
6. **Celebrate milestones**: Note when components are complete
