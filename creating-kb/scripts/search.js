#!/usr/bin/env node
/**
 * Lexical KB searcher — pure-Node BM25 over a portable, embedding-free index.
 *
 * Ships *inside* a `.skill` bundle alongside index.json + chunks.jsonl. Zero
 * dependencies (Node stdlib only): any agent that can run `node` can query the
 * KB with no install, no model download, no network.
 *
 * The semantic layer lives in the calling agent, not here. There is no embedding
 * model to bridge the query<->document vocabulary gap; the agent does that by
 * expanding the query into --core (essential terms) and --expand (synonyms,
 * morphological variants, acronym expansions, adjacent concepts). When no
 * expansion is supplied, --rm3 runs corpus-driven pseudo-relevance feedback as a
 * weaker, model-free fallback.
 *
 * The tokenizer here is the single source of truth: build_lexkb.js imports it so
 * the index and the query tokenize identically.
 *
 * Usage:
 *   node search.js --query "..." --core term --expand syn --k 5
 *   node search.js --query "..." --rm3 --k 5
 *   node search.js --core x --filter "section=blog" --filter "date>=2025"
 */
"use strict";

const fs = require("fs");
const path = require("path");

// --------------------------------------------------------------------------- //
// Tokenizer — single source of truth (builder imports this).
// Matches search.py: lowercase, Unicode \w+ runs.
// --------------------------------------------------------------------------- //

const TOKEN_RE = /[\p{L}\p{N}_]+/gu;

function tokenize(text) {
  const out = [];
  for (const m of String(text).toLowerCase().matchAll(TOKEN_RE)) out.push(m[0]);
  return out;
}

// --------------------------------------------------------------------------- //
// Index
// --------------------------------------------------------------------------- //

class Index {
  constructor(dir) {
    this.dir = dir;
    const idx = JSON.parse(fs.readFileSync(path.join(dir, "index.json"), "utf8"));
    this.k1 = Number(idx.params.k1);
    this.b = Number(idx.params.b);
    this.N = Number(idx.N);
    this.avgdl = Number(idx.avgdl);
    this.doclen = idx.doclen;
    this.postings = idx.postings;
    this._idf = new Map();
    this._chunks = null;
  }

  get chunks() {
    if (this._chunks === null) {
      const raw = fs.readFileSync(path.join(this.dir, "chunks.jsonl"), "utf8");
      this._chunks = raw.split("\n").filter((l) => l.trim()).map((l) => JSON.parse(l));
    }
    return this._chunks;
  }

  idf(term) {
    let v = this._idf.get(term);
    if (v === undefined) {
      const df = (this.postings[term] || []).length;
      v = Math.log(1.0 + (this.N - df + 0.5) / (df + 0.5));
      this._idf.set(term, v);
    }
    return v;
  }

  termDocScore(term, docIdx, tf) {
    const dl = this.doclen[docIdx];
    const denom = tf + this.k1 * (1.0 - this.b + (this.b * dl) / this.avgdl);
    return (this.idf(term) * (tf * (this.k1 + 1.0))) / denom;
  }

  // weightedTerms: Map<term, weight> -> Map<docIdx, score>
  score(weightedTerms) {
    const scores = new Map();
    for (const [term, weight] of weightedTerms) {
      const plist = this.postings[term];
      if (!plist) continue;
      for (const [docIdx, tf] of plist) {
        scores.set(docIdx, (scores.get(docIdx) || 0) + weight * this.termDocScore(term, docIdx, tf));
      }
    }
    return scores;
  }
}

// --------------------------------------------------------------------------- //
// Query construction — expansion is strictly additive over the raw query.
// --------------------------------------------------------------------------- //

function buildQuery(core, expand, wCore, wExpand, backstop, wBackstop) {
  const q = new Map();
  const groups = [
    [expand || [], wExpand],
    [backstop || [], wBackstop],
    [core || [], wCore],
  ];
  for (const [group, w] of groups) {
    for (const phrase of group) {
      for (const tok of tokenize(phrase)) {
        q.set(tok, Math.max(q.get(tok) || 0, w));
      }
    }
  }
  return q;
}

// --------------------------------------------------------------------------- //
// RM3 pseudo-relevance feedback (model-free fallback expansion)
// --------------------------------------------------------------------------- //

function rm3Expand(index, seed, { nDocs = 10, nTerms = 15, alpha = 0.5 } = {}) {
  const first = index.score(seed);
  if (first.size === 0) return seed;
  const top = [...first.entries()].sort((a, b) => b[1] - a[1]).slice(0, nDocs);
  const total = top.reduce((s, [, v]) => s + v, 0) || 1.0;

  const fb = new Map();
  for (const [docIdx, docScore] of top) {
    const toks = tokenize(index.chunks[docIdx].text);
    if (toks.length === 0) continue;
    const w = docScore / total;
    const tfLocal = new Map();
    for (const t of toks) tfLocal.set(t, (tfLocal.get(t) || 0) + 1);
    const invLen = 1.0 / toks.length;
    for (const [t, c] of tfLocal) fb.set(t, (fb.get(t) || 0) + w * c * invLen);
  }

  const ranked = [...fb.entries()]
    .filter(([t]) => !seed.has(t))
    .sort((a, b) => b[1] - a[1])
    .slice(0, nTerms);
  const fbTotal = ranked.reduce((s, [, m]) => s + m, 0) || 1.0;

  const merged = new Map();
  for (const [t, w] of seed) merged.set(t, alpha * w);
  for (const [t, m] of ranked) merged.set(t, (merged.get(t) || 0) + (1.0 - alpha) * (m / fbTotal));
  return merged;
}

// --------------------------------------------------------------------------- //
// Metadata filtering
// --------------------------------------------------------------------------- //

function parseFilter(expr) {
  for (const op of ["!=", ">=", "<=", "~", "=", ">", "<"]) {
    const i = expr.indexOf(op);
    if (i !== -1) return [expr.slice(0, i).trim(), op, expr.slice(i + op.length).trim()];
  }
  throw new Error(`unparseable filter: ${expr}`);
}

function matchFilter(meta, key, op, val) {
  const actual = meta[key];
  if (actual === undefined || actual === null) return false;
  const a = String(actual);
  if (op === "=") return a === val;
  if (op === "!=") return a !== val;
  if (op === "~") return a.toLowerCase().includes(val.toLowerCase());
  const af = Number(a), vf = Number(val);
  const numeric = a.trim() !== "" && val.trim() !== "" && !Number.isNaN(af) && !Number.isNaN(vf);
  const x = numeric ? af : a;
  const y = numeric ? vf : val;
  if (op === ">") return x > y;
  if (op === ">=") return x >= y;
  if (op === "<") return x < y;
  if (op === "<=") return x <= y;
  return false;
}

function passesFilters(index, docIdx, filters) {
  if (!filters.length) return true;
  const meta = index.chunks[docIdx].meta || {};
  return filters.every(([k, op, v]) => matchFilter(meta, k, op, v));
}

// --------------------------------------------------------------------------- //
// Search
// --------------------------------------------------------------------------- //

// Sentence splitter shared with search.py (same regex) so snippet selection is
// byte-identical across runtimes.
const SENT_SPLIT = /(?<=[.!?])\s+|\n+/;

function spanChars(sents, idxs) {
  // Char cost of the merged passage; same formula as search.py _span_chars so
  // both runtimes make identical budget decisions.
  if (!idxs.length) return 0;
  const s = [...idxs].sort((a, b) => a - b);
  let runs = 1;
  for (let i = 1; i < s.length; i++) if (s[i] !== s[i - 1] + 1) runs++;
  let total = s.reduce((acc, i) => acc + sents[i].length, 0);
  total += s.length - runs;     // spaces joining sentences within a run
  total += (runs - 1) * 3;      // ' … ' between runs
  return total;
}

function makeSnippet(index, text, query, budget, context = 1) {
  // Decouple the reasoning payload from the retrieval unit: rank a doc whole
  // (recall), return only its query-densest sentences (signal) — each expanded
  // by `context` neighbour sentences so a match keeps its referent/setup, with
  // adjacent/overlapping matches merged into contiguous passages. Scores are
  // rounded so JS and Python select identically.
  if (budget <= 0 || text.length <= budget) return [text, false];
  const sents = text.split(SENT_SPLIT).map((s) => s.trim()).filter(Boolean);
  if (!sents.length) return [text.slice(0, budget) + "…", true];
  const n = sents.length;
  // Only query-bearing sentences can seed; score them, drop zero-score
  // sentences before sorting (filter the rounded value to match the prior
  // round-then-filter exactly), so the sort is over the few matches, not all
  // sentences of a whole-document chunk.
  const scored = [];
  for (let i = 0; i < n; i++) {
    let sc = 0;
    for (const t of new Set(tokenize(sents[i]))) if (query.has(t)) sc += query.get(t) * index.idf(t);
    const r = Math.round(sc * 1e6) / 1e6;
    if (r > 0) scored.push([r, i]);
  }
  scored.sort((a, b) => (b[0] - a[0]) || (a[1] - b[1]));
  const seeds = scored.map(([, i]) => i);
  if (!seeds.length) return [text.slice(0, budget) + "…", true];

  let selected = new Set();
  for (const seed of seeds) {
    const cand = new Set(selected);
    for (let j = Math.max(0, seed - context); j < Math.min(n, seed + context + 1); j++) cand.add(j);
    if (selected.size && spanChars(sents, [...cand]) > budget) break;
    selected = cand;
    if (spanChars(sents, [...selected]) >= budget) break;
  }
  if (!selected.size) {
    const seed = seeds[0];
    for (let j = Math.max(0, seed - context); j < Math.min(n, seed + context + 1); j++) selected.add(j);
  }

  const idxs = [...selected].sort((a, b) => a - b);
  const runs = [[idxs[0]]];
  for (const i of idxs.slice(1)) {
    if (i === runs[runs.length - 1][runs[runs.length - 1].length - 1] + 1) runs[runs.length - 1].push(i);
    else runs.push([i]);
  }
  let body = runs.map((run) => run.map((i) => sents[i]).join(" ")).join(" … ");
  if (idxs[0] > 0) body = "… " + body;
  if (idxs[idxs.length - 1] < n - 1) body = body + " …";
  return [body, true];
}

function search(index, query, { k = 5, filters = [], useRm3 = false, rm3 = {}, snippetChars = 0, snippetContext = 1 } = {}) {
  if (useRm3) query = rm3Expand(index, query, rm3);
  const scores = index.score(query);
  const ranked = [...scores.entries()].sort((a, b) => b[1] - a[1]);
  const out = [];
  for (const [docIdx, sc] of ranked) {
    if (!passesFilters(index, docIdx, filters)) continue;
    const chunk = index.chunks[docIdx];
    const [text, truncated] = makeSnippet(index, chunk.text, query, snippetChars, snippetContext);
    const hit = { id: chunk.id, score: Math.round(sc * 1e6) / 1e6, text, meta: chunk.meta || {} };
    if (truncated) hit.full_chars = chunk.text.length;
    out.push(hit);
    if (out.length >= k) break;
  }
  return out;
}

// --------------------------------------------------------------------------- //
// CLI
// --------------------------------------------------------------------------- //

function parseArgs(argv) {
  const a = { index: __dirname, query: "", core: [], expand: [], filter: [],
    wCore: 1.0, wExpand: 0.4, wQuery: 0.25, k: 5, rm3: false,
    rm3Docs: 10, rm3Terms: 15, rm3Alpha: 0.5, snippet: 1200, context: 1 };
  const multi = { "--core": "core", "--expand": "expand", "--filter": "filter" };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t === "--rm3") { a.rm3 = true; continue; }
    const val = argv[++i];
    if (multi[t]) a[multi[t]].push(val);
    else if (t === "--index") a.index = val;
    else if (t === "--query") a.query = val;
    else if (t === "--w-core") a.wCore = Number(val);
    else if (t === "--w-expand") a.wExpand = Number(val);
    else if (t === "--w-query") a.wQuery = Number(val);
    else if (t === "--k") a.k = Number(val);
    else if (t === "--rm3-docs") a.rm3Docs = Number(val);
    else if (t === "--rm3-terms") a.rm3Terms = Number(val);
    else if (t === "--rm3-alpha") a.rm3Alpha = Number(val);
    else if (t === "--snippet") a.snippet = Number(val);
    else if (t === "--context") a.context = Number(val);
    else { i--; } // unknown flag without value; skip
  }
  return a;
}

function main(argv) {
  const a = parseArgs(argv);
  const index = new Index(a.index);

  let core = [...a.core];
  let backstop = [];
  if (a.query) {
    if (!core.length && !a.expand.length) core = [a.query];
    else backstop = [a.query];
  }
  const query = buildQuery(core, a.expand, a.wCore, a.wExpand, backstop, a.wQuery);
  if (query.size === 0) {
    console.log(JSON.stringify({ error: "empty query: pass --core/--expand or --query" }));
    return 2;
  }

  const hits = search(index, query, {
    k: a.k,
    filters: a.filter.map(parseFilter),
    useRm3: a.rm3,
    rm3: { nDocs: a.rm3Docs, nTerms: a.rm3Terms, alpha: a.rm3Alpha },
    snippetChars: a.snippet, snippetContext: a.context,
  });
  console.log(JSON.stringify({ hits }, null, 2));
  return 0;
}

module.exports = { tokenize, Index, buildQuery, rm3Expand, parseFilter, search };

if (require.main === module) {
  process.exit(main(process.argv.slice(2)));
}
