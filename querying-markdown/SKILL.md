---
name: querying-markdown
description: Query, filter, and transform Markdown structurally with mq — a jq-like CLI for Markdown. Use to extract headings/sections/code-blocks/links from .md files, build a table of contents, pull code blocks of a given language, slice or reshape LLM prompt/output Markdown, or batch-transform docs. Triggers on "extract sections from this markdown", "get all the code blocks", "jq for markdown", "mq", or any structural query over Markdown that grep/Read can't do cleanly.
metadata:
  version: 0.2.0
---

# querying-markdown

`mq` is "jq for Markdown" — it parses a `.md` file into a node stream and lets
you select, filter, and transform by structure (`.h2`, `.code("rust")`,
`.link`) instead of by line-matching. Reach for it when the task is structural:
"every H2 title", "all bash code blocks", "a table of contents", "strip the
frontmatter". For plain substring search, `grep` is still the right tool; for
code (not prose) structure, use `tree-sitting`.

## Before you use mq: is this actually a structural task?

mq parses the whole document into a node tree before it answers, and that parse
cost is real (see [Empirical findings](#empirical-findings)). Most "query a
markdown file" tasks don't need it. Decide first, using the target — not the
file type:

| Your target | Use | Why |
| --- | --- | --- |
| Lines with a fixed prefix — `#`/`##` headings, `>` quotes, `-` bullets, a leading line/verse number | **grep / awk** | Line-matching, not structure. grep is faster and already installed. |
| A substring anywhere | **grep** | mq adds nothing. |
| Code *structure* inside fences (ASTs, symbols, call sites) | **tree-sitting** | mq sees the fence, not the code inside it. |
| Language-filtered code blocks (`.code("bash")`); links as structured `(text, url)` (`-F json '.link'`) | **mq** | grep can't filter a fenced block by language without a brittle hand-rolled fence state machine. |
| Markdown→Markdown transforms that must emit valid Markdown — demote/promote headings, rebuild a TOC with anchors, in-place edit | **mq** | `sed` doesn't know structure and will corrupt nesting/fences. |

If your task lands in a grep/awk row, **do not install mq** — close this skill
and use the line tool. Diagnosed 2026-06-04: a full-KJV smoke test queried
books/chapters/verses (all line-prefix structure) with mq — ~3.3 s per query
where grep is milliseconds, the same answers, and a grep post-filter still
needed on top. Wrong-shape corpus; mq's selectors earn their parse cost only on
the structural rows.

The judgment call is whether the case is *actually* line-prefix or only looks
it. A heading is a prefix; a heading you want demoted **with its subtree**, or a
match you must re-emit as valid Markdown, is structure — mq's row even when the
match looks like a prefix.

## Setup

mq is a single static binary, not preinstalled. Install on first use (idempotent
— exits early if already present, ~1s, no build step):

```bash
bash /mnt/skills/user/querying-markdown/scripts/install-mq.sh
```

This drops the pinned `mq` release into `/usr/local/bin`. Override the version
with `MQ_VERSION=vX.Y.Z`.

## Usage

```bash
mq 'QUERY' file.md          # query a file
cat file.md | mq 'QUERY'    # query stdin
mq repl                     # interactive REPL — use to test syntax fast
```

A node stream flows left→right through `|`. Selectors (`.h`, `.code`, `.link`)
pick nodes; functions (`to_text`, `slugify`, `map`, `len`) transform them.
`self` is the current node.

```bash
mq '.h2 | to_text()' README.md            # every H2 as plain text
mq '.code("python") | to_text()' file.md  # all python code blocks
mq '.h.level' file.md                     # heading depth per heading
mq -F json '.h2 | to_text()' file.md      # results as JSON
mq '.h2 | to_text()' file.md | wc -l      # count matches (reliable idiom)
```

## Empirical findings

Measured 2026-06-04 against a full public-domain KJV Bible (66 files, 4.28 MB).

**Parse-bound, not query-bound.** mq reparses the whole document on every
invocation; latency tracks document *size*, not selector or match count. On the
4.28 MB file every query — whether it returned 66 matches or 32,418 — ran
~3.2–3.3 s (~1.3 MB/s); on a normal-sized doc it is single-digit ms. Never loop
mq per query over a large corpus: extract once with `-F json` and work on the
result, or accept a constant per-call parse tax.

**Selectors return nodes, not your domain concepts.** `.h2` over the KJV
returned 1,250 nodes — 1,184 chapter headings plus 66 `eof` markers the source
appended per file, while single-chapter books emitted no chapter heading at all.
`.text` also pulled heading text into the paragraph stream. A raw selector count
is a *node* count; map it to your concept with an explicit predicate
(e.g. `grep -E '^[0-9]+ '` for verses) and check it against a known total before
trusting the number.

**An empty result is ambiguous.** Zero output means *either* the selector
matched nothing *or* mq never ran — a wrapper like `time`/`env` failed in `dash`,
or a malformed heredoc swallowed the command. Re-run the bare
`mq 'QUERY' file.md` before concluding a selector or function is broken.
(Self-inflicted 2026-06-04: a `time: not found` shell error read as a
`to_text()` defect; `to_text()` on code blocks works.)

## Reference

Selector aliases, the built-in function library, table-of-contents and
transform recipes, in-place-edit caveats, and CLI flags live in
[references/cheatsheet.md](references/cheatsheet.md). Read it before writing a
non-trivial query — the dialect is jq-*like*, not jq, so the function names
differ. When unsure of syntax, `mq repl` gives instant feedback.
