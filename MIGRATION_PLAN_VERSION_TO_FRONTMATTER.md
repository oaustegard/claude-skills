# Migration Plan: VERSION Files to Frontmatter Metadata

## Executive Summary

Migrate version information from standalone `VERSION` files to YAML frontmatter `metadata.version` field in SKILL.md files, following the official Agent Skills specification.

**Impact**: 27 skills with VERSION files
**Benefits**:
- Single source of truth (SKILL.md)
- Follows official spec at https://agentskills.io/specification
- Reduces file clutter
- Better alignment with skill metadata standards

## Current State Analysis

### VERSION File Usage

**Count**: 27 of 28 skills have VERSION files (only `installing-skills` lacks one)

**Format**: Simple semver strings in plain text files
```
0.13.0
0.0.3
0.3.1
```

**Current Dependencies**:

1. **Runtime access** (`remembering/__init__.py:1794-1800`):
   ```python
   # handoff_complete() reads VERSION file as fallback
   version_file = Path(__file__).parent / "VERSION"
   version = version_file.read_text().strip()
   ```

2. **Release workflow** (`.github/scripts/release-skill.sh:163-169`):
   - Reads VERSION file to determine release version
   - Creates git tags like `skill-name-v1.0.0`
   - Includes VERSION file in release ZIP for "runtime version detection"

3. **Upload processing** (`.github/scripts/process-skill-upload.sh`):
   - Currently no VERSION file dependency identified

### Frontmatter Current State

**All 28 skills** use minimal frontmatter:
```yaml
---
name: skill-name
description: Brief description. Use when [triggers].
---
```

**One exception** (`controlling-spotify`) includes additional fields:
```yaml
---
name: controlling-spotify
description: ...
credentials:
  - SPOTIFY_CLIENT_ID
  - SPOTIFY_CLIENT_SECRET
  - SPOTIFY_REFRESH_TOKEN
domains:
  - api.spotify.com
  - accounts.spotify.com
---
```

**No skills currently use**:
- `metadata.version`
- `metadata.author`
- `license` field

## Target State

### New Frontmatter Schema

```yaml
---
name: skill-name
description: Brief description. Use when [triggers].
metadata:
  version: "1.0.0"
  author: oaustegard
---
```

**Rationale**:
- `metadata.version`: Required for migration, replaces VERSION file
- `metadata.author`: Optional but valuable attribution (can be added incrementally)
- `license`: Not needed per user request (repository has MIT LICENSE)

### Version String Format

- **Keep existing semver values** from VERSION files
- **Quote version strings** in YAML (e.g., `"1.0.0"` not `1.0.0`)
- **Preserve leading zeros** (e.g., `"0.13.0"` not `"0.13"`)

## Migration Strategy

### Phase 1: Preparation

1. **Create Python helper library** for frontmatter operations:
   - Parse YAML frontmatter from SKILL.md
   - Update frontmatter while preserving formatting
   - Extract metadata.version programmatically

2. **Create migration script** (`scripts/migrate-version-to-frontmatter.py`):
   - Read VERSION file content
   - Parse SKILL.md frontmatter
   - Add `metadata.version` field
   - Write updated SKILL.md
   - Validate YAML syntax

3. **Update runtime code** (`remembering/__init__.py`):
   - Add frontmatter reader
   - Check `metadata.version` first, fall back to VERSION file
   - Ensure backward compatibility during transition

### Phase 2: Automated Migration

**Script workflow**:
```python
for skill_dir in skill_directories:
    if not (skill_dir / "VERSION").exists():
        continue

    version = read_version_file(skill_dir / "VERSION")
    skill_md = skill_dir / "SKILL.md"

    # Parse and update frontmatter
    frontmatter = parse_frontmatter(skill_md)
    if "metadata" not in frontmatter:
        frontmatter["metadata"] = {}
    frontmatter["metadata"]["version"] = version

    # Write back to SKILL.md
    write_skill_md(skill_md, frontmatter, body)

    # Log for verification
    print(f"✓ {skill_dir.name}: {version}")
```

**Output**: Single commit with all SKILL.md files updated

### Phase 3: Release Workflow Updates

Update `.github/scripts/release-skill.sh`:

**Current behavior** (lines 163-169):
```bash
if [ ! -f "$SKILL_DIR/VERSION" ]; then
  echo "Error: No VERSION file found in $SKILL_DIR"
  exit 1
fi
VERSION=$(cat "$SKILL_DIR/VERSION" | tr -d '[:space:]')
```

**New behavior** (backward compatible):
```bash
# Try metadata.version first, fall back to VERSION file
VERSION=$(python3 .github/scripts/extract-version.py "$SKILL_DIR")
if [ -z "$VERSION" ]; then
  echo "Error: No version found in $SKILL_DIR (checked frontmatter and VERSION file)"
  exit 1
fi
```

**Helper script** (`.github/scripts/extract-version.py`):
```python
#!/usr/bin/env python3
import sys
import yaml
from pathlib import Path

skill_dir = Path(sys.argv[1])
skill_md = skill_dir / "SKILL.md"

# Parse frontmatter
with open(skill_md) as f:
    content = f.read()
    if content.startswith("---"):
        _, fm, _ = content.split("---", 2)
        frontmatter = yaml.safe_load(fm)

        # Check metadata.version
        if "metadata" in frontmatter and "version" in frontmatter["metadata"]:
            print(frontmatter["metadata"]["version"])
            sys.exit(0)

# Fall back to VERSION file
version_file = skill_dir / "VERSION"
if version_file.exists():
    print(version_file.read_text().strip())
    sys.exit(0)

sys.exit(1)
```

**ZIP packaging** (line 211):
- **Remove** VERSION file exclusion (or add explicit exclusion)
- VERSION files will be **deleted** post-migration, so no longer in ZIPs

### Phase 4: Runtime Code Updates

Update `remembering/__init__.py` `handoff_complete()`:

**Current** (lines 1793-1800):
```python
# Read VERSION file if version not provided
if version is None:
    try:
        from pathlib import Path
        version_file = Path(__file__).parent / "VERSION"
        version = version_file.read_text().strip()
    except Exception:
        version = "unknown"
```

**New** (backward compatible):
```python
# Read version from frontmatter if not provided
if version is None:
    try:
        import yaml
        from pathlib import Path
        skill_md = Path(__file__).parent / "SKILL.md"
        with open(skill_md) as f:
            content = f.read()
            if content.startswith("---"):
                _, fm, _ = content.split("---", 2)
                frontmatter = yaml.safe_load(fm)
                version = frontmatter.get("metadata", {}).get("version", "unknown")
            else:
                version = "unknown"
    except Exception:
        # Fall back to VERSION file for backward compatibility
        try:
            version_file = Path(__file__).parent / "VERSION"
            version = version_file.read_text().strip()
        except Exception:
            version = "unknown"
```

### Phase 5: Cleanup

After migration is complete and tested:

1. **Delete VERSION files** from all skill directories
2. **Remove fallback code** from release scripts (extract-version.py only checks frontmatter)
3. **Simplify runtime code** (remove VERSION file fallback)
4. **Update documentation** (AGENTS.md, CLAUDE.md references to VERSION)

## Migration Execution Order

```
1. Create helper library (frontmatter_utils.py)
2. Create migration script (migrate-version-to-frontmatter.py)
3. Create extraction helper (extract-version.py)
4. Update runtime code with backward compatibility (remembering/__init__.py)
5. Update release workflow (release-skill.sh)
6. Update documentation (crafting-instructions, AGENTS.md)
7. Run migration script on all skills
8. Test release workflow on one skill
9. Commit all changes (migration + docs)
10. Delete VERSION files
11. Remove backward compatibility code
12. Final commit
```

## Rollback Plan

If issues arise:

1. **Before VERSION deletion**: Revert SKILL.md changes, workflows still functional
2. **After VERSION deletion**:
   - Restore VERSION files from git history
   - Revert workflow changes
   - Optionally keep metadata.version in frontmatter (harmless)

## Testing Strategy

### Pre-Migration Tests

1. Verify all VERSION files parse as valid semver
2. Ensure all SKILL.md files have valid YAML frontmatter
3. Check for any VERSION file content anomalies (newlines, comments, etc.)

### Post-Migration Tests

1. **Frontmatter validation**: All SKILL.md files parse as valid YAML
2. **Version extraction**: `extract-version.py` returns correct versions
3. **Release workflow**: Test release creation for one skill
4. **Runtime access**: Test `remembering.handoff_complete()` version detection
5. **Backward compatibility**: Keep VERSION files temporarily, ensure dual-read works

### Validation Script

```python
# validate_migration.py
for skill_dir in skill_directories:
    skill_md = skill_dir / "SKILL.md"

    # Parse frontmatter
    frontmatter = parse_frontmatter(skill_md)

    # Validate metadata.version exists
    assert "metadata" in frontmatter
    assert "version" in frontmatter["metadata"]

    # Validate version format (basic semver)
    version = frontmatter["metadata"]["version"]
    assert re.match(r'^\d+\.\d+\.\d+$', version)

    # Compare with old VERSION file
    if (skill_dir / "VERSION").exists():
        old_version = (skill_dir / "VERSION").read_text().strip()
        assert version == old_version, f"Mismatch: {version} != {old_version}"
```

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| YAML parsing errors | High | Low | Validate all files before migration |
| Release workflow breaks | High | Medium | Backward compatible helper script |
| Runtime version detection fails | Medium | Low | Fallback to VERSION file during transition |
| Version format inconsistencies | Low | Medium | Validation script catches issues |
| Manual edits between steps | Medium | Low | Atomic git commits, clear sequencing |

## Open Questions

1. **Author metadata**: Should we add `metadata.author: oaustegard` uniformly?
   - Recommendation: Yes, single commit after version migration

2. **License field**: User declined, but should we document decision?
   - Recommendation: No action needed (MIT LICENSE at repo root suffices)

3. **CHANGELOG references**: Do any CHANGELOGs reference VERSION files?
   - Action: Grep for "VERSION" in CHANGELOG.md files

4. **External documentation**: Are VERSION files referenced in any .md files?
   - Action: Grep for "VERSION" in *.md files

5. **Backward compatibility timeline**: How long to keep VERSION file fallback?
   - Recommendation: Remove immediately after migration (not distributed to users)

## Success Criteria

- ✅ All 27 VERSION files migrated to `metadata.version`
- ✅ Release workflow creates releases using frontmatter version
- ✅ Runtime code reads version from frontmatter
- ✅ No VERSION files remain in repository
- ✅ All SKILL.md files validate as proper YAML
- ✅ Test release succeeds for at least one skill

## Timeline Estimate

- **Script development**: 1-2 hours
- **Migration execution**: 5 minutes (automated)
- **Testing**: 30 minutes
- **Cleanup**: 15 minutes
- **Total**: ~2-3 hours

## Documentation Updates

### Update crafting-instructions Skill

The `crafting-instructions` skill teaches users and Claude how to create skills. It must be updated to reflect the new frontmatter metadata fields.

**File**: `crafting-instructions/references/creating-skills.md`

**Current frontmatter example** (lines 46-51):
```yaml
---
name: skill-name
description: [Action verbs] [what]. Use for: [trigger patterns].
---
```

**New example with optional metadata**:
```yaml
---
name: skill-name
description: [Action verbs] [what]. Use for: [trigger patterns].
metadata:
  version: "1.0.0"
  author: your-name
---
```

**Add new subsection after line 76** ("Pattern: `[Verb] [Verb]...`"):

```markdown
### Optional Metadata Fields

**version** (recommended):
- Semantic version string (e.g., "1.0.0", "0.2.1")
- Quote the version in YAML: `version: "1.0.0"` not `version: 1.0.0`
- Increment following semver principles:
  - Major: Breaking changes to skill interface
  - Minor: New features, backward compatible
  - Patch: Bug fixes, documentation updates
- Helpful for tracking skill evolution and troubleshooting

**author** (optional):
- Your name, organization, or GitHub username
- Provides attribution and contact context
- Example: `author: oaustegard` or `author: my-org`

**license** (optional):
- SPDX identifier (e.g., "MIT", "Apache-2.0") or "Proprietary"
- Only needed if skill has different license than containing repository
- Can reference file: `license: "Proprietary. LICENSE.txt has complete terms"`

**Example with all optional fields**:
```yaml
---
name: processing-pdfs
description: Extract text and tables from PDF files, fill forms, merge documents. Use for: .pdf files, PDF analysis, form filling, document merging.
metadata:
  version: "2.1.0"
  author: my-org
license: Apache-2.0
---
```

**When to include**:
- `version`: Recommended for all skills under active development
- `author`: When distributing publicly or wanting attribution
- `license`: Only when different from repository license
```

**Quality checklist update** (around line 223):

Add to the "Metadata:" section:
```markdown
**Metadata:**
- [ ] Name: lowercase, hyphens, gerund form, max 64 chars
- [ ] Description: third person, includes WHAT + WHEN triggers, max 1024 chars, no XML
- [ ] Version: Present in metadata (recommended), follows semver, quoted
- [ ] Author: Present if distributing publicly (optional)
```

**Rationale**:
- Users creating skills should know about optional metadata
- Version tracking becomes standard practice
- Attribution is encouraged but not required
- License only mentioned when needed (most skills inherit repo license)

### Update AGENTS.md

**File**: `AGENTS.md`

**Update frontmatter examples** (around line 101):

Current:
```markdown
### 2. Create SKILL.md with required frontmatter:
   ```yaml
   ---
   name: skill-name
   description: What it does. Use when [trigger patterns].
   ---
   ```
```

New:
```markdown
### 2. Create SKILL.md with required frontmatter:
   ```yaml
   ---
   name: skill-name
   description: What it does. Use when [trigger patterns].
   metadata:
     version: "1.0.0"
   ---
   ```
```

**Update "Skill Frontmatter Requirements"** section (around line 132):

Add after **description** requirements:

```markdown
**metadata.version** (recommended):
- Semantic version string
- Quote in YAML: `"1.0.0"` not `1.0.0`
- Replaces standalone VERSION file

**metadata.author** (optional):
- Attribution for skill creator
- Organization or individual name
```

## Related Files

- SKILL.md files: All 28 skills
- VERSION files: 27 skills
- `.github/scripts/release-skill.sh`: Release workflow
- `.github/scripts/process-skill-upload.sh`: Upload processing
- `remembering/__init__.py`: Runtime version access
- `crafting-instructions/references/creating-skills.md`: Skill creation guide
- `AGENTS.md`: Repository documentation
- New files:
  - `scripts/frontmatter_utils.py`: Helper library
  - `scripts/migrate-version-to-frontmatter.py`: Migration script
  - `.github/scripts/extract-version.py`: Version extraction for workflows
  - `scripts/validate_migration.py`: Post-migration validation
