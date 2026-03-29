# lat.md Authoring Rules

Detailed syntax and structure rules for writing lat.md/ files. Reference this when generating or editing sections.

## Section Structure

Every section is a markdown heading plus content underneath it. Sections form a tree based on heading depth.

```markdown
# Top-Level Section

Brief overview (≤250 chars, this is the section's identity in search results).

More detail in subsequent paragraphs.

## Child Section

Brief overview of child topic (≤250 chars).

### Grandchild Section

Even deeper nesting is fine — just maintain the ≤250 char first paragraph rule.
```

**Hard rules:**
- Every section MUST have a leading paragraph before any child headings
- First paragraph MUST be ≤250 characters (excluding `[[wiki link]]` content)
- `lat check` enforces both rules

## Section IDs

Sections are addressed by file path + heading chain:
- Full form: `lat.md/path/to/file#Heading#SubHeading`
- Short form: `file#Heading#SubHeading` (when file stem is unique in lat.md/)

The root heading (h1) can be omitted in references: `[[data#Sync Pipeline]]` works even if the h1 is `# Data`.

## Wiki Links

Obsidian-style: `[[target]]` or `[[target|display text]]`.

### Section Links

Link between lat.md sections:
```markdown
See [[architecture#Data Flow]] for the full pipeline.
The sync engine ([[data#Sync Pipeline]]) handles rate limiting.
Awards require [[data#IndexedDB Schema|segment history]] to compute.
```

### Source Code Links

Link to symbols in source files:
```markdown
[[src/auth.js#getValidToken]]          — function
[[src/sync.js#startBackfill]]          — function
[[src/awards.js#computeAwards]]        — function
[[src/components/Dashboard.js#Dashboard]] — component
```

Supported: `.ts`, `.tsx`, `.js`, `.jsx`, `.py`, `.rs`, `.go`, `.c`, `.h`

Source links always require the full path (no short refs for source files).

### Link Density Guidance

Dense linking is valuable — it's the connective tissue that makes lat.md a graph rather than flat documentation. Aim for:
- Every mention of a concept defined elsewhere → wiki link
- Every non-trivial function referenced in prose → source code link
- Cross-references between related sections (awards↔data, architecture↔all)

## Index Files

Every directory in lat.md/ (including root) needs an index file named after the directory.

Root: `lat.md/lat.md`
Subdirectory: `lat.md/api/api.md`

Index format — bullet list with wiki links and one-sentence descriptions:
```markdown
- [[architecture]] — System design, OAuth flow, routing, signals
- [[awards]] — Award computation engine, data quality rules, comeback mode
- [[data]] — IndexedDB schema, sync pipeline, demo mode
```

## Frontmatter

Optional YAML frontmatter for per-file configuration:
```yaml
---
lat:
  require-code-mention: true
---
```

Use `require-code-mention: true` for test spec files — ensures every leaf section has a matching `@lat:` comment in source code.

## Conceptual Grouping

Organize by domain concept, not by file structure. A `data.md` file might reference `db.js`, `sync.js`, and `demo.js` because they're all part of the data layer. An `awards.md` file documents the awards engine conceptually even though the implementation spans `awards.js`, `award-config.js`, and parts of `db.js`.

The mapping-codebases `_MAP.md` files already provide file-level structure. lat.md adds the semantic layer on top — explaining WHY things are shaped the way they are and HOW concepts connect across files.

## @lat: Back-links

Source code can reference lat.md sections with `@lat:` comments:
```javascript
// @lat: [[awards#Data Quality Rules]]
const HIGH_VARIANCE_CV_THRESHOLD = 0.5;
```

```python
# @lat: [[data#Sync Pipeline#Backfill]]
async def start_backfill(on_progress):
```

One comment per section reference. Place at the relevant code — the function, constant, or class that implements the concept — not at the file top.
