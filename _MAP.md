# claude-skills/
*Files: 5 | Subdirectories: 33*

## Subdirectories

- [accessing-github-repos/](./accessing-github-repos/_MAP.md)
- [api-credentials/](./api-credentials/_MAP.md)
- [asking-questions/](./asking-questions/_MAP.md)
- [browsing-bluesky/](./browsing-bluesky/_MAP.md)
- [categorizing-bsky-accounts/](./categorizing-bsky-accounts/_MAP.md)
- [charting-vega-lite/](./charting-vega-lite/_MAP.md)
- [check-tools/](./check-tools/_MAP.md)
- [cloning-project/](./cloning-project/_MAP.md)
- [controlling-spotify/](./controlling-spotify/_MAP.md)
- [convening-experts/](./convening-experts/_MAP.md)
- [crafting-instructions/](./crafting-instructions/_MAP.md)
- [creating-bookmarklets/](./creating-bookmarklets/_MAP.md)
- [creating-mcp-servers/](./creating-mcp-servers/_MAP.md)
- [creating-skill/](./creating-skill/_MAP.md)
- [developing-preact/](./developing-preact/_MAP.md)
- [exploring-data/](./exploring-data/_MAP.md)
- [extracting-keywords/](./extracting-keywords/_MAP.md)
- [generating-patches/](./generating-patches/_MAP.md)
- [hello-demo/](./hello-demo/_MAP.md)
- [installing-skills/](./installing-skills/_MAP.md)
- [invoking-gemini/](./invoking-gemini/_MAP.md)
- [invoking-github/](./invoking-github/_MAP.md)
- [iterating/](./iterating/_MAP.md)
- [making-waffles/](./making-waffles/_MAP.md)
- [mapping-codebases/](./mapping-codebases/_MAP.md)
- [orchestrating-agents/](./orchestrating-agents/_MAP.md)
- [remembering/](./remembering/_MAP.md)
- [reviewing-ai-papers/](./reviewing-ai-papers/_MAP.md)
- [sampling-bluesky-zeitgeist/](./sampling-bluesky-zeitgeist/_MAP.md)
- [scripts/](./scripts/_MAP.md)
- [templates/](./templates/_MAP.md)
- [updating-knowledge/](./updating-knowledge/_MAP.md)
- [versioning-skills/](./versioning-skills/_MAP.md)

## Files

### AGENTS.md
- AGENTS.md `h1` :1
- Repository Overview `h2` :5
- Skills Availability in This Repository `h2` :11
- Repository Structure `h2` :35
- Key Principles `h3` :49
- Working with Skills `h2` :56
- Developing or Modifying Existing Skills `h3` :58
- Creating a New Skill `h3` :82
- Uploading Skills (Automated Workflow) `h3` :111
- Skill Frontmatter Requirements `h3` :128
- Key Skills in This Repository `h2` :141
- Meta-Skills (Skills for Creating Skills) `h3` :143
- Domain-Specific Skills `h3` :149
- Important Implementation Patterns `h2` :159
- 1. Progressive Disclosure `h3` :161
- 2. Skill.md Structure `h3` :168
- 3. Scripts Pattern `h3` :192
- 4. Token Efficiency `h3` :201
- Git Workflow `h2` :210
- Common Tasks `h2` :229
- Viewing a Skill's Structure `h3` :231
- Testing SKILL.md Frontmatter `h3` :237
- Finding Skills by Pattern `h3` :243
- Packaging Multiple Skills `h3` :249
- Architecture Notes `h2` :258
- Skill Discovery and Activation `h3` :260
- Context Window Management `h3` :267
- Validation and Quality `h3` :276
- Anti-Patterns to Avoid `h2` :286
- License `h2` :298

### CLAUDE.md
- Claude Code on the Web Development `h2` :3
- Branch and PR Lifecycle `h3` :7
- Why This Matters `h3` :27
- Environment-Specific Tips `h2` :34
- Environment Variable Access `h3` :36
- Code Maps `h2` :58
- Using the Maps `h3` :62
- Keeping Maps Fresh `h3` :81
- Skill Development Workflow `h2` :101
- Before Executing ANY Code `h3` :105
- CRITICAL: Skills Have Multiple Documentation Files `h3` :124
- Skill Naming and Metadata Guidelines `h3` :175
- CLAUDE.md Files Take Priority `h3` :187
- Meta-Usage Pattern `h3` :195
- PR Reviews and Code Testing `h2` :212
- Pre-Flight: Verify Branch Setup `h3` :216
- Testing Workflow: NO STATIC REVIEWS `h3` :236
- Review Document Format `h3` :319
- Dependency Updates `h3` :333
- Remembering Skill and Handoff Process `h2` :353
- Handoff Execution Expectations `h3` :391

### PR_160_REVIEW.md
- PR #160 Review: Improve codemap.py with symbol hierarchy `h1` :1
- Overview `h2` :3
- Strengths `h2` :12
- 1. Excellent Feature Enhancement `h3` :14
- 2. Good Documentation `h3` :20
- 3. Consistent Refactoring `h3` :24
- Issues Found `h2` :29
- Critical Issues `h3` :31
- 1. **Python Version Compatibility** 🔴 `h4` :33
- 2. **Empty Symbol Names** 🔴 `h4` :54
- 3. **Rust Public Symbol Detection Issue** 🟡 `h4` :84
- Minor Issues `h3` :111
- 4. **Commented Debug Code** 🟡 `h4` :113
- 5. **Silent Exception Handling** 🟡 `h4` :135
- 6. **Inconsistent Private Symbol Filtering** 🟢 `h4` :156
- 7. **TypeScript Signature Extraction Missing** 🟢 `h4` :170
- 8. **Python Method Filtering** 🟢 `h4` :179
- Testing Recommendations `h2` :200
- Required Testing `h3` :202
- Suggested Test Files `h3` :225
- Recommendations `h2` :234
- Must Fix (Before Merge) `h3` :236
- Should Fix (Before Merge) `h3` :241
- Nice to Have (Can Be Future Work) `h3` :246
- Overall Assessment `h2` :252
- Summary Checklist `h2` :264

### PR_160_REVIEW_UPDATED.md
- PR #160 Review: Improve codemap.py with symbol hierarchy `h1` :1
- Updates Applied `h2` :3
- Testing Results `h2` :12
- ✅ What Works Excellently `h3` :14
- ⚠️ Issues Found in Testing `h3` :42
- 1. **Private Methods Not Filtered in Python** 🟡 `h4` :44
- 2. **Java Methods Not Extracted** 🔴 `h4` :63
- 3. **Limited Language Coverage** 🟡 `h4` :82
- 4. **TypeScript Signature Extraction Not Implemented** 🟢 `h4` :96
- Original PR Strengths `h2` :115
- 1. Excellent Core Feature `h3` :117
- 2. Good Documentation `h3` :123
- 3. Clean Refactoring `h3` :127
- Recommended Fixes `h2` :132
- Must Fix Before Merge `h3` :134
- 1. Add Private Method Filtering in Python `h4` :136
- 2. Fix Java Method Extraction `h4` :152
- Should Fix (Important) `h3` :164
- 3. Add Empty Name Validation `h4` :166
- Nice to Have (Future Work) `h3` :184
- Dependency Updates (Applied) `h2` :190
- Overall Assessment `h2` :203
- What's Great `h3` :207
- What Needs Work `h3` :213
- Impact `h3` :218
- Testing Checklist `h2` :223
- Sources `h2` :246

### README.md
- claude-skills `h1` :1
- Installing Skills `h2` :4
- For Claude.ai (Web/Mobile) `h3` :6
- For Claude Code (Automated Installation) `h3` :14
- Contributing Skills `h2` :56
- Via ZIP Upload (Easiest) `h3` :60
- Via Direct Development `h3` :78
- Releasing Skills `h2` :85
- How It Works `h3` :93
- Creating a New Release `h3` :98
- Manual Release `h3` :119
- Version Format `h3` :127
- Resources `h2` :135

