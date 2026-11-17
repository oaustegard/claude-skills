---
name: creating-skill
description: Builds a new agent skill or revises one (SKILL.md, scripts and references), validated and packaged as a zip. Use for "create a skill for X", "turn this into a reusable skill", "why does my skill not trigger", or "review this SKILL.md".
metadata:
  version: 2.6.0
---

# Creating skills

A skill is instructions to the agent: a procedure with commands, checks and failure signals. Facts alone belong in a document labelled as a reference. The measurements behind every rule here are in `references/skill-utility-evidence.md`; read it when a rule seems arbitrary.

## Not for

| Situation | Use |
|---|---|
| Whether the instruction should be a skill, project instructions or a prompt | `crafting-instructions` |
| Sentence-level quality of instruction prose | `writing-instructions` |
| Revising an existing skill that has evidence of underperforming | `optimizing-skills` |
| Project-specific context, one-off tasks | project instructions or a prompt |

## Procedure

1. **Create the directory.** `mkdir -p <name>/{scripts,references,assets}`; delete unused ones before shipping. Name: gerund first word (`processing-pdfs`), lowercase and hyphens, at most 64 characters, no "anthropic" or "claude".

2. **Write the description** (about 250 characters; 1024 is the hard limit):
   - one sentence on what it does, then two or three phrasings a user would type;
   - lead with the unit of the question (symbols, not ASTs);
   - third person; no angle brackets anywhere (`->` and `>200MB` are rejected too);
   - separate from neighbours by omission — a disclaimer ("does not X") pulls toward X; routing goes in the body;
   - never reuse a sibling's trigger phrases.

3. **Validate the frontmatter:**
   ```bash
   python3 /mnt/skills/examples/skill-creator/scripts/quick_validate.py <skill-dir>
   ```
   Allowed keys: `name`, `description`, `license`, `allowed-tools`, `metadata`, `compatibility`. One SKILL.md per directory.

4. **Check confusability** from `oaustegard/claude-workspace`:
   ```bash
   python3 scripts/skill_confusability.py --skills <skills-root> --queries q.json
   ```
   `q.json`: five task-shaped queries under the skill's name, negatives under `__none__`. Require top-1 on 5/5, no steals of sibling queries, no near-miss above the hit floor. A neighbour above ~0.65 cosine needs a routing row in both bodies.

5. **Write the body** in this order:
   - **Not for** — routing table naming real sibling skills; plus when to abandon the procedure mid-run.
   - **Setup** — install commands and each tool's silent-failure signal.
   - **Procedure** — numbered steps with the actual commands, flags and order; the intermediate checks and what a wrong result looks like. Leave to judgment whether the skill applies, which approach fits, and when to abandon.
   - **Rules with exceptions** — a table for any rule that is sometimes wrong.
   - **Failure modes** — a `signal | action` table. The signal is what the reader sees.
   - **Verification** — the commands that confirm success, and what a bad success looks like (passes inspection, lost content).

   Write imperatives. Give a reason only where it changes what the reader does, in one clause ("— it catches fixes the regression accepts"). Leave out motivation, provenance, results, dated incidents and paragraphs repeating the description; they go in the CHANGELOG. Phrase instructions positively, but keep negative scope (the Not-for table) as content.

6. **Add resources only when they earn it.** Code Claude would rewrite each time → `scripts/`, with explicit errors and non-zero exits. Detail that would push SKILL.md past ~500 lines → `references/`, one level deep. Output templates → `assets/`. A script that fails quietly is worse than none.

7. **Write the CHANGELOG entry**: what changed, provenance, measurements, and the dated story of any diagnosed failure the body now encodes as a row.

8. **Bump `metadata.version`** (releases trigger on the change). Commit each skill's bump separately: the release bot writes the commit subject into every bumped skill's CHANGELOG.

9. **Test on three real scenarios** — simple, complex, edge — and fix what actually happened.

10. **Package for claude.ai upload** when needed:
    ```bash
    zip -r <name>.zip <name>/ && unzip -l <name>.zip
    ```
    README.md, CHANGELOG.md and tests/ are stripped from release zips; put anything that must ship (credits, licenses) in SKILL.md or a shipped file.

## Failure modes

| Signal | Action |
|---|---|
| Skill does not load; no error | an unquoted `: ` or an angle bracket in the description; run `quick_validate.py` |
| Skill loses its own queries | description too long or reusing a sibling's phrases; cut to ~250 characters with three phrasings |
| Skill wins queries it should ignore | a disclaimer in the description; delete it and move routing into the body |
| Body explains, tells history or sells | move it to the CHANGELOG; keep steps, commands, signals |
| Steps read as goals ("scan the repo and check") | replace with the command and the output that means failure |
| CHANGELOG entry describes another skill's change | the release bot used a shared commit subject; edit it and bump separately next time |
| Agent applies the skill where it does not fit | the Not-for table is missing or names categories, not skills |

## Verification

```bash
python3 /mnt/skills/examples/skill-creator/scripts/quick_validate.py <skill-dir>
python3 scripts/skill_confusability.py --skills <skills-root> --queries q.json   # top-1 5/5
wc -l <skill-dir>/SKILL.md                                                       # under 500
grep -n "Diagnosed\|20[0-9][0-9]-[0-9][0-9]-" <skill-dir>/SKILL.md                # dated stories left in the body
```

Bad success: a skill that validates and wins its queries while its body is a goal statement or a history — read the procedure as someone who must execute it with no other context.

## Checklist

- [ ] Name and description follow step 1–2; `quick_validate.py` passes; confusability 5/5
- [ ] Not-for table names real skills; abandonment condition stated
- [ ] Setup with silent-failure signals, if it wraps a tool
- [ ] Every step has a command or a concrete check
- [ ] Failure modes are `signal | action` rows
- [ ] Verification commands and the bad-success case
- [ ] No motivation, provenance, results or dated stories in the body or references
- [ ] Reasons only where they change behaviour, one clause each
- [ ] SKILL.md under 500 lines; references one level deep; unused directories deleted
- [ ] CHANGELOG entry; version bumped in its own commit
- [ ] Tested on three real scenarios

## References

- `references/skill-utility-evidence.md` — measurements behind each rule, and the dated catalogue cases
- `references/bundled-resources.md` — scripts, references and assets patterns
- `references/advanced-patterns.md` — validation workflows, multi-stage skills
- `references/optimization-techniques.md` — token budget
- `references/environment-reference.md` — Claude.ai vs Claude Code paths
