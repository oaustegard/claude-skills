---
name: querying-markdown
description: Query, filter, and transform Markdown structurally with mq — a jq-like CLI for Markdown. Use to extract headings/sections/code-blocks/links from .md files, build a table of contents, pull code blocks of a given language, slice or reshape LLM prompt/output Markdown, or batch-transform docs. Triggers on "extract sections from this markdown", "get all the code blocks", "jq for markdown", "mq", or any structural query over Markdown that grep/Read can't do cleanly.
metadata:
  version: 0.1.0
---

# querying-markdown

`mq` is "jq for Markdown" — it parses a `.md` file into a node stream and lets
you select, filter, and transform by structure (`.h2`, `.code("rust")`,
`.link`) instead of by line-matching. Reach for it when the task is structural:
"every H2 title", "all bash code blocks", "a table of contents", "strip the
frontmatter". For plain substring search, `grep` is still the right tool; for
code (not prose) structure, use `tree-sitting`.

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

## Reference

Selector aliases, the built-in function library, table-of-contents and
transform recipes, in-place-edit caveats, and CLI flags live in
[references/cheatsheet.md](references/cheatsheet.md). Read it before writing a
non-trivial query — the dialect is jq-*like*, not jq, so the function names
differ. When unsure of syntax, `mq repl` gives instant feedback.
