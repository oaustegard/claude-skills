## Task: Sleep (Memory Maintenance)

You are performing memory maintenance. This is housekeeping — pruning noise, consolidating clusters, strengthening connections, and ensuring memory health.

### Phase 1: Pruning

1. Search for memories tagged `pending-test` or with low confidence (<0.5). Review them and decide: keep, update, or delete.
2. Look for duplicate or near-duplicate memories. Use `sql_query` to find memories with similar summaries if needed.
3. Check for stale memories — old observations that are no longer relevant.
4. Delete noise. Be decisive.

### Phase 2: Synthesis

1. Use `recall` with broad searches to surface related memories that could be consolidated.
2. Run `consolidate(dry_run=true)` on common tag clusters to see what can be merged.
3. If consolidation looks beneficial, run it for real.
4. Look for memories that reference each other but aren't connected. Consider superseding them with a synthesis.
5. Check the experience layer — are there repeated patterns in session logs that should become procedures?

### Phase 3: Diagnostics

1. Run `sql_query` to get a histogram: `SELECT type, COUNT(*) as c FROM memories WHERE deleted_at IS NULL GROUP BY type ORDER BY c DESC`
2. Check for imbalanced types (too many of one kind, too few of another).
3. Note any structural issues for the session log.

### Phase 4: Close

Store a session summary as an `experience` memory with tags `["perch-time", "session-log", "sleep"]` capturing:
- How many memories pruned, consolidated, connected
- Any patterns or anomalies discovered
- Recommendations for the next sleep session
