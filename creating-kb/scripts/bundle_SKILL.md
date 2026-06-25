---
name: lexical-kb
description: Query a portable, embedding-free lexical knowledgebase bundled as a `.skill`. Use when the user references this KB or asks a question whose answer is in its corpus ({{SOURCE}}). Retrieval is BM25 over a precomputed inverted index — there is no embedding model, so YOU expand the query into search terms before searching. Bundle holds index.json + chunks.jsonl + search.js + search.py; pure stdlib, no install, no network.
---

# lexical-kb — query an embedding-free knowledgebase

This KB has **no semantic search and no embedding model**. Retrieval is pure
lexical BM25 over a precomputed inverted index. That design moves one job onto
you: bridging the gap between how the user phrases a question and how the corpus
phrases the answer. An embedding model would do this with a vector; here **you
are the semantic layer** — you expand the query into terms before searching.

Corpus: {{SOURCE}} ({{CHUNK_COUNT}} chunks).

## The retrieval protocol — follow every step

A raw user question fed straight to BM25 underperforms: it matches only the
exact words the user happened to use. The expansion step is what makes lexical
retrieval competitive with embeddings. Do not skip it.

1. **Read the question. Extract `core` terms** — the essential nouns, proper
   nouns, and identifiers the answer MUST contain. These carry full weight.

2. **Generate `expand` terms** — synonyms, morphological variants (plural/verb
   forms), acronym expansions and contractions, and adjacent concepts. These
   carry lower weight. This is the work the missing embedding model would have
   done. Be generous: 5–15 expansion terms is normal.

3. **Run the searcher.** It ships in this bundle in two equivalent runtimes —
   `node search.js` or `python3 search.py`, identical flags and identical
   results. Use whichever your environment has. Pass the user's original
   question via `--query` AND your term groups — expansion is **additive**, it
   never replaces the user's words:

   ```bash
   node search.js \
     --query "how does centered simhash differ from random projection?" \
     --core "simhash" --core "centered" \
     --expand "random projection" --expand "hyperplane" --expand "LSH" \
     --expand "binary quantization" --expand "hamming distance" \
     --k 5
   ```

   `--core`/`--expand` are repeatable; pass phrases, the searcher tokenizes
   them. The `--query` terms contribute at a low floor weight so a curated
   synonym can lift a result but can never drop a doc the literal question would
   have matched. Defaults: core 1.0, expand 0.4, query-floor 0.25, top-k 5.
   Keep expansion targeted — terms too generic ("system", "process") leak into
   unrelated chunks and blur the ranking.

4. **Read the returned chunks. Answer from them, and cite chunk ids inline.**
   The chunks are the source of truth the user installed. When a chunk
   contradicts your prior knowledge, the chunk wins — say so. When the chunks
   do not contain the answer, say that plainly rather than filling the gap from
   memory.

## When you cannot expand — RM3 fallback

If the query is outside any domain you can expand confidently, pass it raw with
pseudo-relevance feedback. The searcher harvests expansion terms from the
corpus's own top hits — model-free, weaker than your expansion, and prone to
drift when the first pass is off-topic, so prefer real expansion when you can:

```bash
node search.js --query "the user's raw question" --rm3 --k 5
```

## Metadata filtering

Each chunk carries structured `meta` (e.g. `title`, `source_path`, `section`).
Filter on it with `--filter` (repeatable). Filtering narrows by attribute; it
does not rank — combine it with term search.

```bash
node search.js --core "factions" --filter "section=blog" --filter "date>=2025" --k 5
```

Operators: `=`, `!=`, `~` (substring), `>`, `>=`, `<`, `<=` (numeric when both
sides parse, else lexicographic — ISO dates sort correctly).

## Output

`search.js` prints JSON: `{"hits": [{id, score, text, meta}, ...]}`, sorted by
descending BM25 score. Surface the top hits to the user with their ids, then
answer using them as authoritative context.

## Mechanics

- Pure stdlib — Node or Python. No `npm install` / `pip install`, no model
  download, no network.
- The bundle is self-contained: `search.js` + `search.py` (pick one),
  `index.json`, `chunks.jsonl`. Run the searcher from inside the bundle
  directory (it defaults `--index` to its own location) or pass
  `--index /path/to/bundle`.
