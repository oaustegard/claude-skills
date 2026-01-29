# Pending Tasks Status Report

**Generated:** 2026-01-29

This document tracks the status of 12 pending tasks identified on 2026-01-27 against GitHub issues in the `oaustegard/claude-skills` repository.

---

## Summary

| Status | Count |
|--------|-------|
| ✅ Converted to GitHub Issue | 10 |
| ❌ Not Yet Created | 2 |

---

## Detailed Status

### ✅ Issue 1: Muninn Architecture Reference Document
**Priority:** Medium | **Skill:** remembering

**Status:** ✅ **CREATED** - Issue #229
- **Link:** https://github.com/oaustegard/claude-skills/issues/229
- **State:** OPEN
- **Title:** "remembering: Create architecture reference document (_ARCH.md)"

---

### ✅ Issue 2: FTS5 Search Optimization
**Priority:** Medium | **Skill:** remembering

**Status:** ✅ **CREATED** - Issue #230
- **Link:** https://github.com/oaustegard/claude-skills/issues/230
- **State:** OPEN
- **Title:** "remembering: Implement FTS5 search optimization"

---

### ✅ Issue 3: Session Continuity System (VM0-inspired)
**Priority:** High | **Skill:** remembering

**Status:** ✅ **CREATED** - Issue #231
- **Link:** https://github.com/oaustegard/claude-skills/issues/231
- **State:** OPEN
- **Title:** "remembering: Implement Session Continuity System (VM0-inspired)"

---

### ✅ Issue 4: Muninn Cleanup Tasks
**Priority:** Low | **Skill:** remembering

**Status:** ✅ **CREATED** - Issue #232
- **Link:** https://github.com/oaustegard/claude-skills/issues/232
- **State:** OPEN
- **Title:** "remembering: Muninn cleanup tasks"

---

### ✅ Issue 5: browsing-bluesky Auth Enhancement
**Priority:** Medium | **Skill:** browsing-bluesky

**Status:** ✅ **CREATED** - Issue #215 (CLOSED)
- **Link:** https://github.com/oaustegard/claude-skills/issues/215
- **State:** CLOSED (2026-01-25)
- **Title:** "browsing-bluesky: Add authenticated access for personalized feeds"
- **Note:** Referenced in pending tasks document. Issue was created and completed.

---

### ✅ Issue 6: TypeScript Export Default Handling
**Priority:** Low | **Skill:** mapping-codebases

**Status:** ✅ **CREATED** - Issue #233
- **Link:** https://github.com/oaustegard/claude-skills/issues/233
- **State:** OPEN
- **Title:** "mapping-codebases: Handle TypeScript export default declarations"

---

### ✅ Issue 7: TypeScript Signature Extraction
**Priority:** Low | **Skill:** mapping-codebases

**Status:** ✅ **CREATED** - Issue #234
- **Link:** https://github.com/oaustegard/claude-skills/issues/234
- **State:** OPEN
- **Title:** "mapping-codebases: Extract TypeScript function signatures"

---

### ✅ Issue 8: Complete Language Coverage
**Priority:** Low | **Skill:** mapping-codebases

**Status:** ✅ **CREATED** - Issue #235
- **Link:** https://github.com/oaustegard/claude-skills/issues/235
- **State:** OPEN
- **Title:** "mapping-codebases: Add method extraction for Go, Rust, Ruby"

---

### ✅ Issue 9: Verbose Logging Flag
**Priority:** Low | **Skill:** mapping-codebases

**Status:** ✅ **CREATED** - Issue #236
- **Link:** https://github.com/oaustegard/claude-skills/issues/236
- **State:** OPEN
- **Title:** "mapping-codebases: Add --verbose flag for debug output"

---

### ✅ Issue 10: Session Filtering Cache Support
**Priority:** Low | **Skill:** remembering

**Status:** ✅ **CREATED** - Issue #237
- **Link:** https://github.com/oaustegard/claude-skills/issues/237
- **State:** OPEN
- **Title:** "remembering: Add cache support for session-filtered queries"

---

### ✅ Issue 11: Configurable Query Expansion Threshold
**Priority:** Low | **Skill:** remembering

**Status:** ✅ **CREATED** - Issue #238
- **Link:** https://github.com/oaustegard/claude-skills/issues/238
- **State:** OPEN
- **Title:** "remembering: Make query expansion threshold configurable"

---

### ❌ Issue 12: GitHub Integration for Muninn Workflow
**Priority:** Medium | **Skill:** remembering

**Status:** ❌ **NOT CREATED AS SINGLE ISSUE**
- **Note:** The concept has been partially addressed through multiple related issues:
  - Issue #239: "remembering: Deeper GitHub integration for Muninn workflow" (OPEN)
  - Issue #240: "remembering: Boot should inject GitHub access and utility methods" (OPEN)
  - Issue #241: "Implement GitHubBot integration" (OPEN)
- **Assessment:** The original task's considerations have been split into more specific, actionable issues. No single issue directly matches the original "GitHub Integration for Muninn Workflow" description.

---

## Additional Observations

### Related Closed Issues

The following closed issues relate to the pending tasks but were completed before this status check:

- **Issue #215** (CLOSED 2026-01-25): browsing-bluesky auth enhancement
- **Issue #213** (CLOSED 2026-01-24): boot() not installing utilities automatically
- **Issue #214** (CLOSED 2026-01-24): Boot sequence broken: wrong env file + missing PYTHONPATH
- **Issue #221** (CLOSED 2026-01-27): remembering: boot should add /home/claude to PYTHONPATH

### New Related Issues

Since the pending tasks document was created, several related issues have been opened:

- **Issue #243**: Fix PYTHONPATH in project instructions boot block
- **Issue #244**: forget() silently fails on partial IDs
- **Issue #248**: Therapy: Audit memory→config promotion candidates

---

## Recommendations

1. **Issue 12 (GitHub Integration)**: Consider whether the existing issues (#239, #240, #241) adequately cover the original scope, or if an umbrella tracking issue should be created.

2. **Priority Review**: Review the priority assignments for issues #229-238 to ensure they align with current project goals.

3. **Pending Tasks Document**: The source document that generated these tasks can likely be archived or removed, as the issues now serve as the canonical tracking mechanism.

---

## Verification Commands

```bash
# List all open issues for remembering skill
gh issue list --repo oaustegard/claude-skills --label "remembering" --state open

# List all open issues for mapping-codebases skill
gh issue list --repo oaustegard/claude-skills --search "mapping-codebases in:title" --state open

# List all open issues for browsing-bluesky skill
gh issue list --repo oaustegard/claude-skills --search "browsing-bluesky in:title" --state all
```

---

**Report Status:** Complete  
**Last Updated:** 2026-01-29  
**Generated By:** Claude (Sonnet 4) via GitHub MCP Server
