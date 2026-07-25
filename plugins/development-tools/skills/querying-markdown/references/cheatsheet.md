# mq cheatsheet

jq-like query language for Markdown. A node stream flows left→right through `|`;
selectors pick nodes, functions transform them. All examples below were verified
against mq 0.5.31.

## Invocation

```bash
mq 'QUERY' file.md            # query a file
cat file.md | mq 'QUERY'      # query stdin
mq -f query.mq file.md        # load query from a file
mq repl                       # interactive REPL — use this to test syntax
```

Useful flags:

| Flag | Effect |
| ---- | ------ |
| `-F, --output-format` | `markdown` (default), `html`, `text`, `json`, `table`, `grep`, `raw`, `none` |
| `-I, --input-format` | force input parse: `markdown` (default), `html`, `text`, `json`, `csv`, `yaml`, `toml`, `xml`, … |
| `-o FILE` | write output to FILE |
| `-A, --aggregate` | aggregate all input into a single array before the query |
| `-U, --in-place` | write result back to the input file — **whole-document transforms only** (see Transforming) |
| `-S QUERY` | separator query inserted between multiple input files |

## Selectors

`.` prefix selects Markdown nodes:

```
.h        # all headings        .code        # fenced code blocks
.text     # paragraphs (.p)     .code_inline # inline code (.inline_code)
.link     # links               .list        # list items (.li)
.table    # tables              .hr          # horizontal rules
```

Selector **calls** filter by property:

```
.h(1)          # only h1
.h(2, 3)       # h2 and h3
.h(1..3)       # h1 through h3 (range)
.h2            # shorthand for .h(2)  (also .h1 … .h6)
.code("rust")  # only rust-tagged code blocks
```

Attribute access via dot notation:

```
.h.level   # heading depth 1–6 (alias .h.depth)
.h.value   # heading text
.code.value
```

## Verified examples

```bash
# Section titles — every H2 as plain text
mq '.h2 | to_text()' file.md

# All headings, any level
mq '.h | to_text()' file.md

# Heading levels (one integer per heading)
mq '.h.level' file.md

# Extract only the bash code blocks
mq '.code("bash") | to_text()' file.md

# All links (rendered as markdown)
mq '.link' file.md

# Slugify the H1 (e.g. for an anchor/filename)
mq '.h1 | to_text() | slugify(self)' file.md

# Headings as structured JSON
mq -F json '.h2 | to_text()' file.md

# Count matches — pipe to wc, the reliable idiom
mq '.h2 | to_text()' file.md | wc -l

# Table-of-contents: nested markdown list of headings with anchor links
mq '.h
    | let link = to_link("#" + to_text(self), to_text(self), "")
    | let level = .h.depth
    | if (not(is_none(level))): to_md_list(link, to_number(level))' file.md
```

## Transforming

`self` refers to the current node. Build transforms with the function library:

```bash
# Uppercase H1 text (emitted to stdout)
mq 'if (is_h1(self)): upcase(to_text(self)) else: self' file.md

# Increase every heading depth by one (demote)
mq 'nodes | map(increase_header_level)' file.md
```

`-U`/`--in-place` writes back **only when the query yields a complete document**
(e.g. a `nodes | map(...)` transform). A filtering selector like `.h1 | …`
produces a partial stream, so mq emits it to stdout and leaves the file
untouched — verify the write-back in `mq repl` before relying on `-U` for a
destructive edit, or just use `-o out.md`.

## Functions (built-in)

Selection / iteration: `select` `filter` `reject` `map` `compact_map`
`flat_map` `each` `find_index` `first` `second` `last` `take` `skip`
`take_while` `skip_while` `nodes`

Text: `to_text` `upcase` `downcase` `slugify` `lpad` `rpad` `ltrimstr`
`rtrimstr` `lines` `unlines` `matches_url` `test` `ngram`

Markdown builders: `to_link` `to_md_list` `to_number`
`increase_header_level` `decrease_header_level` `promote_heading`
`demote_heading` `frontmatter` `load_markdown`

Aggregation: `len` `count_by` `group_by` `sort_by` `unique_by` `sum` `sum_by`
`mean` `max_by` `min_by` `partition` `chunks` `zip` `transpose` `fold`

Predicates: `is_h` `is_h1`…`is_h6` `is_code` `is_list` `is_text` `is_link`
`is_table_cell` `is_em` `is_none` `is_empty` `is_array` `is_string` `is_number`

Run `mq --list` for the full subcommand/function surface, or open `mq repl`
and experiment. Full reference: https://mqlang.org/book/

## Defining functions

```
def double(x): mul(x, 2);          # named, ';' or 'end' terminates
nodes | map(fn(x): upcase(x);)     # anonymous (lambda)
nodes | map(->(x): upcase(x);)     # '->' is shorthand for 'fn'
```
