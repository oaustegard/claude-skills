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
    this.df = idx.df;
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
      const df = this.df[term] || 0;
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

function search(index, query, { k = 5, filters = [], useRm3 = false, rm3 = {} } = {}) {
  if (useRm3) query = rm3Expand(index, query, rm3);
  const scores = index.score(query);
  const ranked = [...scores.entries()].sort((a, b) => b[1] - a[1]);
  const out = [];
  for (const [docIdx, sc] of ranked) {
    if (!passesFilters(index, docIdx, filters)) continue;
    const chunk = index.chunks[docIdx];
    out.push({ id: chunk.id, score: Math.round(sc * 1e6) / 1e6, text: chunk.text, meta: chunk.meta || {} });
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
    rm3Docs: 10, rm3Terms: 15, rm3Alpha: 0.5, textChars: 0 };
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
    else if (t === "--text-chars") a.textChars = Number(val);
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
  });
  if (a.textChars > 0) {
    for (const h of hits) if (h.text.length > a.textChars) h.text = h.text.slice(0, a.textChars) + "…";
  }
  console.log(JSON.stringify({ hits }, null, 2));
  return 0;
}

module.exports = { tokenize, Index, buildQuery, rm3Expand, parseFilter, search };

if (require.main === module) {
  process.exit(main(process.argv.slice(2)));
}
