---
name: creating-kb
description: Builds a portable, embedding-free knowledgebase from a set of files and delivers it as a self-contained `.skill` bundle (BM25 index + bundled searcher + query protocol). Use when a user wants to turn uploaded files, a folder, or a corpus into a searchable knowledgebase they can hand to any agent — phrased as "make a knowledgebase", "build a KB skill", "package these docs for retrieval", "create a searchable bundle", or references to a `.skill` KB. The output runs anywhere with Node or Python — no model, no install, no network. Distinct from `bm25` (ephemeral in-session search) and `building-github-index` (markdown project-knowledge index).
metadata:
  version: 0.2.0
---

# creating-kb

Turn a pile of files into a **portable, deployable knowledgebase**. The output
is a `.skill` bundle — an ordinary zip — containing a BM25 inverted index, the
chunk text, a pure-Node searcher, and a query protocol. It has no embedding
model and no semantic search: retrieval is lexical, and the consuming agent
supplies the semantic layer by expanding the query at search time. That is what
makes the bundle portable — any agent that can run `node` can query it with no
`npm install`, no model download, and no network.

The whole toolchain is JavaScript so one implementation serves both this builder
and the in-browser packer. Build with the bundled script; do not hand-roll the
index.

```
SCRIPTS=/mnt/skills/user/creating-kb/scripts
node $SCRIPTS/build_lexkb.js CORPUS_DIR --out /tmp/kb --name my-kb --zip
```

## Workflow

### 1. Gather the sources

Collect the files into one directory. In a Claude.ai chat, uploads land in
`/mnt/user-data/uploads/` — point the builder there. Otherwise use any path the
user names. Supported extensions default to `txt,md,html,htm`; pass `--ext` to
change them.

This MVP interface is bounded by how many files a chat can accept. For a large
corpus, stage the files in a directory first, or use the browser packer (built
from the same scripts) that runs entirely client-side.

### 2. Build the bundle

```bash
SCRIPTS=/mnt/skills/user/creating-kb/scripts
node $SCRIPTS/build_lexkb.js /mnt/user-data/uploads \
  --out /tmp/kb --name my-kb --zip \
  --source "human description of the corpus"
```

The script chunks each file, builds the BM25 index, writes the bundle dir
(`SKILL.md` + `search.js` + `index.json` + `chunks.jsonl`), and — with `--zip` —
emits `my-kb.skill` next to `--out`.

### 3. Deliver

Move the `.skill` to the outputs directory and give the user a download link:

```bash
cp /tmp/my-kb.skill /mnt/user-data/outputs/
```

```markdown
[Download my-kb.skill](computer:///mnt/user-data/outputs/my-kb.skill)
```

Tell the user how to deploy it: unzip into an agent's skill directory (or upload
it as a skill). The bundle's own `SKILL.md` then drives querying — the consuming
agent reads it, expands each question into search terms, and runs the bundled
`search.js`. No further setup.

## Choosing chunk size

The retrieval unit and the reasoning unit are decoupled, which makes chunk size a
low-stakes choice. `search.py`/`search.js` **rank** on the whole chunk (best
recall) but **return** only the query-densest passage of it by default
(`--snippet`, ~1200 chars), so a big chunk does not flood the consuming agent's
context with surrounding noise. Index for recall; the searcher handles signal.

`--target-chars` controls chunk size (whole paragraphs are packed up to the
target; `--target-chars 0` makes each file one chunk). Lexical BM25 tolerates —
and on a real-corpus sweep slightly *preferred* — larger chunks than
embedding-based retrieval, because there is no vector to dilute: BM25 scores
individual term presence with length normalization, so a big chunk still ranks on
the exact terms it contains.

- **Default: `--target-chars 0` (whole document).** Best recall, fewest chunks;
  the snippet return keeps reasoning context focused.
- Long, multi-topic files where you want tighter citation units: `1500`–`4000`.
- `500` only if you need very fine-grained chunk ids and accept more chunks.

## Verifying the bundle

Test before delivering. Run a query against the freshly built bundle and confirm
it returns sensible hits:

```bash
node /tmp/kb/search.js --query "a representative question" \
  --core "key term" --expand "synonym" --k 3
```

Each hit's `text` is the query-focused passage by default; add `--snippet 0` to
inspect a full chunk.

`search.js` prints JSON `{"hits": [...]}`. Confirm the right chunks surface.

## What ships in the bundle

| File | Role |
|---|---|
| `SKILL.md` | the query protocol the consuming agent follows (expand → search → cite) |
| `search.js` / `search.py` | equivalent BM25 + RM3 + metadata-filter searchers; return query-focused passages (matched sentences kept in neighbour context, merged); the agent runs whichever runtime it has |
| `index.json` | precomputed inverted index (postings, df, doc lengths, BM25 params) |
| `chunks.jsonl` | chunk text + structured metadata |

Both searchers are thin readers of the same neutral JSON index, so the bundle
runs in a Node-only or a Python-only consumer. Metadata stays structured (not
folded into the indexed text), which lets the consuming agent filter on it
(`--filter section=blog`, `--filter date>=2025`).

## Scripts

- `scripts/build_lexkb.js` — chunker + BM25 index builder + `.skill` writer.
- `scripts/search.js` — the JS runtime searcher, copied verbatim into every
  bundle. It owns the tokenizer; the builder imports it so index and queries
  tokenize identically.
- `scripts/search.py` — the Python runtime searcher, copied verbatim into every
  bundle; a thin reader of the same neutral JSON index, parity-pinned to
  `search.js` (identical results on a shared index).
- `scripts/zipstore.js` — pure-JS ZIP-STORED writer (used by the builder; shared
  with the in-browser packer).
- `scripts/bundle_SKILL.md` — the query-side SKILL.md template written into each
  bundle.
