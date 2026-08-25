---
name: creating-skill
description: Builds and revises a complete skill DIRECTORY — SKILL.md, scripts, references, assets — and packages it. Use for "create a skill for X", "turn this into a skill", "update/improve this skill", "why doesn't my skill trigger", "review this SKILL.md", "package this skill", or when a repeated procedure should become a reusable artifact. Enforces the structure that makes skills work — a concrete procedure rather than a goal statement, an explicit applicability boundary, failure modes with their signals, a runtime verification step, and a description checked against the existing catalogue for confusability. For choosing whether the instruction should be a skill at all rather than project instructions or a prompt, use crafting-instructions. For writing quality inside the prose, use writing-instructions.
metadata:
  version: 2.3.0
---

# Creating Skills

Create portable, reusable expertise that extends Claude's capabilities across contexts.

## What a skill is for — read before writing one

A skill is a **procedural anchor**. Measured across 528 paired executions,
65.7% of skill effects come from supplying a usable procedure — setup steps,
tool sequence, intermediate checks, pitfalls — and 4.5% from supplying facts
the agent lacked (Jiang et al. 2026, arXiv:2608.14036).

Three consequences shape every rule below:

1. **The procedure is the deliverable.** A high-level plan of three to five
   steps measured at 47.7% success against a 50.0% no-skill baseline. The same
   experience written as a full SKILL.md measured 79.2%. Vagueness scores worse
   than silence.
2. **Abstraction costs something.** `skill_guidance_misapplied_or_ignored`
   runs at 0.8% without a skill and **10.0%** with one. A skill that never says
   when it does not apply has not paid for itself.
3. **Facts are a reference, not a skill.** Writing one is fine. Call it a
   reference and do not expect it to change behaviour.

Load [references/skill-utility-evidence.md](references/skill-utility-evidence.md)
before authoring or reviewing a SKILL.md. It carries the failure-mode tables
behind every requirement here, and reading it is what stops these rules from
being followed as ritual.

## When to Create Skills

Skills are appropriate when:
- Capability needed across multiple projects/conversations
- Procedural knowledge that applies broadly (not project-specific)
- Instructions should activate automatically on trigger patterns
- Want portable expertise that loads progressively on-demand

Not appropriate when:
- Context is project-specific (use Project instructions instead)
- One-off task (use standalone prompt instead)
- See **crafting-instructions** skill for detailed decision framework

## Skill Structure

Every skill is a directory containing:
- `SKILL.md` (required): Frontmatter + imperative instructions
- `scripts/` (optional): Executable code for deterministic operations
- `references/` (optional): Detailed docs loaded on-demand
- `assets/` (optional): Templates/files used in output

Create this structure directly:
```bash
mkdir -p skill-name/{scripts,references,assets}
```

Delete unused directories before packaging.

## Naming Convention

Use gerund form (verb + -ing):
- ✅ `processing-pdfs`, `analyzing-data`, `creating-reports`
- ❌ `pdf-helper`, `data-tool`, `report-maker`

Requirements:
- Lowercase letters, numbers, hyphens only
- Max 64 characters
- No reserved words (anthropic, claude)

## Frontmatter Requirements

```yaml
---
name: skill-name
description: What it does. Use when [trigger patterns].
---
```

**name:** Follow naming convention above

**description:** (max 1024 chars)
- Third person voice: "Processes files" not "I process files"
- WHAT it does + WHEN to use it (trigger patterns)
- Specify: file types, keywords, task types that should activate this skill
- No angle brackets at all — the rule is stricter than "no XML tags". A `->` arrow
  or a `>200MB` threshold is rejected on upload just as a `<tag>` is.

**Good examples:**
- "Creates PowerPoint presentations. Use when users mention slides, .pptx files, or presentations."
- "Analyzes SQL queries for performance. Use when debugging slow queries, optimization requests, or EXPLAIN output."

**Ineffective examples:**
- "I can help create presentations" (first person, no triggers)
- "Presentation creator" (no triggers, vague what)
- "Advanced presentation creation with animations" (over-detailed implementation)

The description is critical—it determines when Claude activates this skill.

### The description competes against its neighbours

A description is never read alone — it is ranked against every other skill, and
the nearest in meaning are what beat it. Confusability, not catalogue size, is
the stressor: embedding top-1 falls to 84.1% at a pool of 100 with unrelated
distractors and 53.4% with near-neighbour ones, and in a personal catalogue
every distractor is a near neighbour.

Four rules, each measured on this catalogue:

1. **Lead with the unit of the question**, not the technology. Users ask about
   symbols, not about ASTs.
2. **Enumerate literal phrasings a user types.** The skill that scored 4/5 on
   its own queries is the one whose description contains "de-claude",
   "humanize this", "this reads like AI".
3. **Separate from a neighbour by OMISSION, never by disclaimer.** A retriever
   scores bag-of-meaning and cannot represent negation, so "does not debug a
   Docker build" reads as "Docker build" and pulls you *toward* the thing you
   disclaimed — measured at +0.05 and +0.10 cosine on two skills. Routing goes
   in the body under When NOT to use, where an LLM reads it and understands the
   negation. The description is scored; the body is read.
4. **Do not reuse a sibling's trigger phrases.** `tree-sitting` listed "map
   this codebase" and "explore repo" — both `exploring-codebases`' territory —
   and lost all five of its own canonical queries.

**Run the check before shipping.** `oaustegard/claude-workspace` carries it:

```bash
python3 scripts/skill_confusability.py --queries q.json
```

Positives go under the skill's own name; negatives under the reserved
`__none__` key. Read three numbers: **top-1** (does it win its own queries),
**steals** (does it win other skills' queries), **near-misses** (does anything
it should ignore score in hit territory). A description tuned on top-1 alone
gets better at being found and worse at staying out of the way.

Full measurements and the per-clause experiment:
[references/skill-utility-evidence.md](references/skill-utility-evidence.md).

### Validate the frontmatter with Anthropic's validator, not by eye

A description rich enough to be findable is long enough to break the spec. An
unquoted `: ` ends the YAML scalar and the file stops parsing; an angle bracket
is rejected outright. Either way the skill does not load, silently, because
nothing validates frontmatter at read time.

Do not hand-roll this check. `skill-creator` ships one, and it is stricter than
anything worth rewriting:

```bash
python3 /mnt/skills/examples/skill-creator/scripts/quick_validate.py <skill-dir>
```

It enforces YAML parseability, the allowed-property whitelist
(`name`, `description`, `license`, `allowed-tools`, `metadata`,
`compatibility`), kebab-case names under 64 chars, descriptions under 1024
chars with no angle brackets, and exactly one SKILL.md per directory — the
Skills API and claude.ai reject multiple on upload even though Claude Code's
filesystem loads them.

Run it over the whole catalogue before a batch edit:

```bash
for d in */; do
  printf '%-24s ' "${d%/}"
  python3 /mnt/skills/examples/skill-creator/scripts/quick_validate.py "$d" 2>&1 | tail -1
done
```

Diagnosed 2026-08-24, twice in one pass. First: two skills shipped
`Primitives: depends_on...` and `makes skills work: a concrete...` inside
unquoted descriptions, and both files became unparseable. Second, the next day:
a description carrying the literal `"review what's new in <repo>"` violated the
no-angle-brackets rule. A regex reader — including `skill_confusability.py` —
accepts all three happily, so the retrieval check passes while the skill is
dead. `quick_validate.py` catches every one in about a second, and it was on
disk the whole time.

## Writing Effective SKILL.md

Apply **writing-instructions** principles:

### Imperative Construction
Frame as direct commands:
- ✅ "Extract text with pdfplumber" / "Validate output with script"
- ❌ "Consider extracting..." / "You might want to validate..."

### Concrete Procedure, Strategic Judgment
Split the two. Mechanics get spelled out; the decision to engage stays a
judgment call.

Spell out — this is the 65.7% a skill exists to deliver:
- the setup and dependency sequence, with the actual commands
- the tool sequence, in order, with the flags that matter
- the intermediate checks, and what a wrong answer looks like
- the pitfalls, each with the signal that announces it

Leave to judgment — forcing these produces mechanical misapplication:
- whether the situation is the one this skill addresses
- which of several defensible approaches fits this case
- when to abandon the procedure because its assumptions broke

- ✅ "`$TREESIT /tmp/$REPO --stats`. Zero symbols on a repo you know has code means tree-sitter core is missing; it exits 0 either way."
- ❌ "Scan the repo structurally and check the result."

The second form is the measured short-plan condition: 47.7% success against a
50.0% no-skill baseline. Trimming a procedure down to its goal does not make it
strategic, it makes it worse than absent.

Trivially inferable steps still come out — `mkdir -p skill-name/{scripts,references}`
is one line, not three. The test is whether omitting a step costs the reader a
wrong guess, not whether the result looks tidy.

### Trust Base Behavior
Claude already knows:
- Basic programming patterns, common tools, file operations
- How to structure clear output, format markdown
- General best practices for code quality

Only specify skill-specific deviations or domain expertise Claude lacks.

### Positive Directive Framing
State what TO do, not what to avoid:
- ✅ "Write in imperative voice with direct instructions"
- ❌ "Don't use suggestive language or tentative phrasing"

Frame requirements positively because it's clearer and more actionable.

**This rule governs how an instruction is phrased. It does not apply to
scope.** "When NOT to use this skill", the routing table, and the earned
exceptions are content, not phrasing, and they are required — see Applicability
Boundary below. Rewriting "do not use this for X" into "use this for Y" deletes
the boundary instead of stating it positively, and the boundary is the defence
against the 10.0% misapplication rate. Keep both: say what the skill does, and
say where it stops.

### Provide Context
Explain WHY for non-obvious requirements:
- ✅ "Keep SKILL.md under 500 lines to enable progressive loading—move detailed content to references/"
- ❌ "Keep SKILL.md under 500 lines"

Context helps Claude make good autonomous decisions in edge cases.

### Example Quality
Examples teach ALL patterns, including unintended ones. Ensure every aspect demonstrates desired behavior. Better to omit examples than include mixed signals.

**For comprehensive prompting guidance**, invoke **writing-instructions**.
**For whether this should be a skill at all**, invoke **crafting-instructions**.

## Required Sections

Every skill that changes how work is done carries these four. A pure reference
document may skip them — and must say in its first line that it is a reference,
so nobody expects it to change execution.

### Applicability Boundary

Non-negotiable. `skill_guidance_misapplied_or_ignored` runs at 0.8% without a
skill and 10.0% with one; a plausible skill applied to the wrong situation is
the single largest cost skills introduce. Write:

- **When NOT to use this skill** — as a routing table when siblings exist:
  situation in one column, the skill that owns it in the other. Name real
  skills, not categories.
- **Earned exceptions** — for any rule strong enough to be wrong sometimes,
  a `banned when` / `earned when` pair. `declauding` is the model here: three
  such tables, and it is why a register pass can cut a tic without cutting the
  claim the tic was carrying.
- **When to abandon it mid-run** — the condition under which the procedure's
  assumptions have broken and continuing makes things worse.

A skill whose author cannot name a case where it does not apply has not
finished thinking about scope.

### Common Failure Modes

Each entry is **signal → mitigation**, never a bare warning. The signal is what
the reader will actually see; without it the mitigation cannot fire.

```
✅ "Zero symbols on a repo you know has code → tree-sitter core is missing.
    It exits 0 and prints no error. Reinstall before concluding anything."
❌ "Make sure dependencies are installed."
```

Environment, output-format and service-lifecycle failures are the most
skillable class there is — writing the setup sequence down took
`environment_infrastructure_failure` from 5.3% to 0.2% in the study. If a skill
wraps a tool, that tool's setup and its silent-failure signal belong here.

### Verification

State how to confirm the work actually succeeded, with the command. Skills do
not add runtime verification on their own: `static_verification_without_runtime`
sits at 12.5% without a skill and 11.7% with one, a 0.8-point move across the
whole study. An agent checks at runtime when the skill tells it to, and not
otherwise.

For a skill that edits or produces something, also state what a **bad success**
looks like — the output that passes inspection while having lost content. That
is the failure a read-through does not catch.

### Diagnosed Failures, With Their Outcomes Labelled

When the skill encodes something learned the hard way, record that it went
wrong, when, and what the signal was. Withholding outcome labels during skill
construction cost 15 to 35 points in the study's ablation once failed
trajectories entered the source pool — an unlabelled failure reads as a
procedure to copy.

```
✅ "Diagnosed 2026-08-22 on a FreeToken review: a 5,697-line gather was cut at
    line 120 and every finding came from targeted reads instead. Use --orient."
❌ "Use --orient for reviews."
```

Dates and specifics, not "a known issue". And keep them inside a procedure that
works: a skill distilled purely from post-mortems measured *below* the no-skill
baseline in nearly every configuration. Failures annotate a working procedure;
they are not a substitute for one.

## Bundled Resources Patterns

**Decision framework:** Will Claude repeatedly generate similar code? → `scripts/`.
Is there extensive domain knowledge, or is SKILL.md nearing 500 lines? →
`references/`. Are there output templates the user receives? → `assets/`.
Otherwise SKILL.md only.

Scripts need explicit error handling and clear outputs — a script that fails
quietly is worse than no script, because the skill then reports success. Keep
references one level deep; assets are used but never read into context, which
is what makes them free.

Full patterns and worked examples:
[references/bundled-resources.md](references/bundled-resources.md).

## Progressive Disclosure

Skills load in three tiers:
1. **Metadata** (name + description): Always loaded for all skills
2. **SKILL.md body**: Loaded when skill activates
3. **Bundled resources**: Loaded as Claude reads them

Keep SKILL.md focused on core workflows (~500 lines max). Move detailed content to references/ for on-demand loading. This enables context-efficient skill ecosystems.

## Token Efficiency

Challenge each line: Does Claude really need this explanation? Can I assume Claude knows this? Does this justify its token cost?

Prefer concise patterns:
- Code examples over verbose explanations
- Decision frameworks over exhaustive lists
- One command with its failure signal over a paragraph describing the command

**Cut process residue, not procedure.** These are opposite things and the
distinction is measurable. Raw trajectories and lightly-cleaned workflow memory
fail through process overload — `timeout_budget_exhaustion` at 10.6% against
1.7% for no help at all — because they preserve exploration, dead ends and
low-level debugging alongside the decisive steps. Distillation is the whole
difference between a skill and a trace dump, and a SKILL.md that grows back
toward the trace re-earns the trace's failure mode.

So the thing to delete is the narration of how the procedure was discovered.
The thing to keep is the procedure, its checks, and its pitfalls — even when
that runs long. Skills cost real context (521.5K tokens per task against
426.2K for workflow memory in the study) and buy 4.8 points of success with it.
Length spent on steps and signals is the purchase; length spent on backstory is
the leak.

## Packaging & Delivery

Create ZIP archive:
```bash
cd /home/claude
zip -r /mnt/user-data/outputs/skill-name.zip skill-name/
```

Verify contents:
```bash
unzip -l /mnt/user-data/outputs/skill-name.zip
```

Show user the packaged structure:
```bash
tree skill-name/
# or
ls -lhR skill-name/
```

Provide download link:
```markdown
[Download skill-name.zip](computer:///mnt/user-data/outputs/skill-name.zip)
```

## Version Control (Optional)

For skills under active development, track changes:
```bash
cd /home/claude/skill-name
git init && git add . && git commit -m "Initial: skill structure"
```

After modifications:
```bash
git add . && git commit -m "Update: description of change"
```

See **versioning-skills** for advanced patterns (rollback, branching, comparison).

## Best Practices

Write TO Claude in imperative commands, not ABOUT Claude in documentation.
Lead with what the skill enables, group related instructions, and use headings
that name content rather than describe procedure. Assume Claude's intelligence:
specify success criteria and let it choose the approach, and only add a bundled
resource that solves a real problem. Keep terminology consistent, and put the
WHY next to any requirement that is not self-evident.

Test on 3+ real scenarios — simple, complex, edge case — and iterate on what
actually happened rather than on what you expected.

## Quality Checklist

Before providing skill to user:

**Metadata:**
- [ ] Name: lowercase, hyphens, gerund form, max 64 chars
- [ ] Description: third person, includes WHAT + WHEN triggers, max 1024 chars, no XML
- [ ] Description leads with the unit of the question, not the technology
- [ ] Description contains literal phrasings a user would type
- [ ] Description separates from siblings by OMISSION, not by a disclaimer
- [ ] `skill_confusability.py` run: skill takes top-1 on 5 task-shaped queries
- [ ] No neighbour above ~0.65 cosine without an explicit boundary in both
- [ ] `quick_validate.py` passes (YAML, allowed keys, name, length, no angle brackets)
- [ ] `metadata.version` bumped (releases gate on the delta; unchanged = silent no-op)

**Structure:**
- [ ] SKILL.md under 500 lines (move extras to references/)
- [ ] Unused directories deleted
- [ ] References one level deep (no long chains)

**Content:**
- [ ] Imperative voice throughout
- [ ] Positive phrasing — while keeping negative *scope* (they are not the same rule)
- [ ] Mechanics concrete: real commands, real flags, real order
- [ ] Judgment left open: applies-here, which-approach, when-to-abandon
- [ ] Context provided for non-obvious requirements
- [ ] Examples perfectly demonstrate desired patterns
- [ ] Consistent terminology

**Required sections** (skip only for a document that declares itself a reference):
- [ ] When NOT to use — routing table naming real sibling skills
- [ ] Earned exceptions for any rule that is sometimes wrong
- [ ] When to abandon the procedure mid-run
- [ ] Failure modes written as signal → mitigation, never a bare warning
- [ ] Setup and its silent-failure signal, if the skill wraps a tool
- [ ] Verification: the command that confirms success
- [ ] What a *bad success* looks like, if the skill edits or produces something
- [ ] Diagnosed failures carry a date, a signal, and the outcome label

**Resources:**
- [ ] Scripts solve actual problems (not punting to Claude)
- [ ] Scripts have error handling and clear outputs
- [ ] References are focused and topic-specific
- [ ] Assets are templates/files for output

**Testing:**
- [ ] Tested on 3+ real scenarios
- [ ] Activates on expected triggers
- [ ] Bundled resources accessible
- [ ] Package structure verified

## Advanced Topics

For complex skill patterns, see:
- [references/skill-utility-evidence.md](references/skill-utility-evidence.md) - The measurements behind the required sections
- **writing-instructions** skill - Comprehensive prompting principles
- **crafting-instructions** skill - Choosing between skill, project instructions and prompt
- **versioning-skills** skill - Git-based development workflow
- [references/advanced-patterns.md](references/advanced-patterns.md) - Validation workflows, multi-stage patterns
- [references/optimization-techniques.md](references/optimization-techniques.md) - Token budget management
- [references/bundled-resources.md](references/bundled-resources.md) - Detailed resource patterns and examples
- [references/environment-reference.md](references/environment-reference.md) - Environment-specific patterns
