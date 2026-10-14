# goal.md template

`goal.md` is the standing prompt that drives drafting. It is given verbatim to every subagent and re-read at the start of every session. It is the one place the project's established facts, reading order, and working rules live. Product-specific parts are marked `{...}`; the "Things already established" section is empty at the start and fills in as foundations are written.

---

# Goal: complete the {product} product description

You are working in the `{repo-name}` repo. Read `README.md`, `glossary.md`, `foundations/{core-foundation}.md`, and `{area}/{pilot}.md` first. The README defines the purpose, the document template, the method, the structure, and the coverage table. The other three are the exemplars: match their depth, tone, and structure exactly. Your job is to write every document in the README's structure until the coverage table has no `not started` rows, then run a consistency pass.

## Source of truth

{The source repo} is checked out at `{absolute path}`. Describe the experience on {the surface: route, config, entry point} (`{path to that entry point}`), in {the default configuration, with nothing customized}. {Excluded thing} is out of scope.

For each document, read in this order before writing:

1. {Where the interaction state lives for the feature: the state machine directory and its child states; the domain object's util/controller.}
2. {The shared pipeline where relevant: the central dispatcher or router, the validation or hit-testing layer, and the managers or services that shape the experience.}
3. The tests in `{test directory}`. They are close to executable specifications of edge cases. Key files: {the list}.
4. UI behavior: `{ui directory}` ({hooks for actions, tools, shortcuts; components for the panels and menus}).
5. Defaults and thresholds: `{options file}` and `{constants file}`.

Do not describe code. Describe what the user sees and does. Technical detail goes only in `> Technical note:` block quotes, and only when the mechanism changes what the user would expect.

## Writing rules

- Follow the eight-section template in the README for every {tool, object, and action} document. Foundations, UI, and cross-cutting documents may drop sections that do not apply (a settings panel has no extended phase) but must still cover cancel/interrupt behavior wherever an interaction exists.
- Modifiers and cancel/interrupt go in tables, split by phase ({the product's names for "before extended" / "while extended"}) as in `{pilot}.md`. The interrupt rows and the order of cross-cutting concerns are fixed in the README; do not add, drop, or reorder them in a single document.
- Use the glossary's words. If you need a term the glossary lacks, add it to `glossary.md` in the right section with a one-paragraph definition, then use it. If you are one of several drafters working in parallel, do not edit `glossary.md`: use the term, and list it with its proposed definition and section in your report so the reviewer merges it once.
- Sentence case for all headings. Direct, concrete language. No hedging, no marketing.
- State surprising behavior plainly and say why if the reason is in the code or a comment. If it looks like a bug, say so in "Open questions" rather than smoothing it over.
- Cross-reference other documents with relative links rather than repeating their content. {The input model} owns thresholds, click detection, modifiers, and the cancel/complete/interrupt definitions. Do not restate them; link.
- Every document ends with "## Open questions and verification" listing what was read from code but not confirmed by hand, followed by `Verified against {source repo} commit \`{sha}\`` using the current `git rev-parse --short HEAD` of {the source repo}.
- Mermaid `stateDiagram-v2` for each interaction's states. Keep it to the states the user passes through; omit internal bookkeeping states.

## Things already established (do not re-derive, do not contradict)

{Empty at first. As each foundation document is written, add its load-bearing facts here as one-line bullets: numbers, defaults, rules, naming decisions. The shape of it:}

- {Thresholds and timings: what separates the short path from the extended one, per input kind, measured in which units; debounce and timeout values; limits on size, count, and length.}
- {How variants are read: live, or latched at the start of an interaction; whether a role or flag can change mid-way.}
- {Naming decisions: e.g. the code's "Accel" is written as Ctrl/Cmd; the code's "workspace" is the UI's "project".}
- {What each gesture-ending event does and what dispatches it: cancel, complete, interrupt.}
- {Which features are unavailable in restricted states (readonly, a lesser role, offline, output piped).}
- {Defaults that many documents depend on: the default role and plan; the autosave interval and what "saved" means; configuration precedence and exit codes; scroll and zoom behavior; what is selected or focused on arrival.}
- {Which document owns which states of the hardest area, once decided.}

## Order of work

1. `foundations/` first, in this order: {list}. Everything else links to them.
2. `{hardest area}/` next, all {n} documents. This is the hardest part and the bulk of the experience. Read every {state file} before starting any of them, because the states hand off to each other and the documents must agree on where one ends and the next begins. {Say which document owns which states.}
3. The remaining `{area}/` documents, then `{area}/`, `{area}/`, `cross-cutting/`. These are independent of each other and can be drafted in parallel with subagents once the foundations and {hardest area} documents exist to link to. If you parallelize, give each subagent this prompt, the four exemplars, and the specific document to write; then review every result yourself for consistency with the glossary and the established facts above before accepting it.
4. Consistency pass over the whole set: same term for the same thing everywhere, no two documents describing the same behavior differently, every glossary term used is defined. Run `{skill dir}/scripts/check_links.py` and `{skill dir}/scripts/check_structure.py` on the repo; both must exit 0.
5. Update the coverage table in `README.md` as you go: `drafted` when written, never `verified` (verification by hand is a separate pass you are not doing).

## Working rules

- Commit after each document or coherent group of documents with a message of the form `docs: add {path}` or `docs: revise {path}`. {State the repo's convention on AI attribution in commits.}
- Do not modify anything in {the source repo}. It is read-only reference material.
- Do not add files outside the README's structure without updating the structure and coverage table to match.
- When a behavior cannot be determined from code and tests, write down what you could determine, put the rest in "Open questions", and move on. Do not guess and do not block.
- Depth bar: `{pilot}.md` is roughly {n} lines for a small {feature}. The {hardest area} documents will be longer; UI documents will often be shorter. Completeness matters more than length. Every state, every modifier, every cancel/interrupt row must be accounted for, even if the answer is "no effect".
- If you find that the README's structure is wrong for something you discover (a document that should be split, two that should merge), make the change, update the structure and coverage table, and note why in the commit message.

You are done when the coverage table has no `not started` rows, the consistency pass is complete, and everything is committed.
