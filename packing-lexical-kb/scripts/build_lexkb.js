#!/usr/bin/env node
/**
 * Build a portable, embedding-free lexical KB `.skill` bundle — pure Node, no deps.
 *
 * Pipeline: collect files -> structural chunk -> BM25 inverted index -> write a
 * bundle dir (chunks.jsonl + index.json + SKILL.md + search.js) -> optionally zip
 * to `<name>.skill` (an ordinary zip with a renamed extension).
 *
 * The shipped search.js owns the tokenizer; this builder imports it so the index
 * and queries tokenize identically. The same logic runs in the browser SPA.
 *
 * Usage:
 *   node build_lexkb.js CORPUS_DIR --out out/kb --name mykb \
 *     --target-chars 1200 [--zip] [--ext txt,md,html]
 */
"use strict";

const fs = require("fs");
const path = require("path");
const { tokenize } = require("./search.js");
const { zipStore } = require("./zipstore.js");

const TEMPLATE_DIR = __dirname;
const BUNDLE_SKILL = "bundle_SKILL.md";

// --------------------------------------------------------------------------- //
// Text extraction + structural chunking
// --------------------------------------------------------------------------- //

function extractText(file) {
  const raw = fs.readFileSync(file, "utf8");
  const ext = path.extname(file).toLowerCase();
  let title, body;
  if (ext === ".html" || ext === ".htm") {
    const m = raw.match(/<title>([\s\S]*?)<\/title>/i);
    title = m ? m[1].trim() : path.basename(file, ext);
    body = raw.replace(/<(script|style)[^>]*>[\s\S]*?<\/\1>/gi, " ")
      .replace(/<[^>]+>/g, "\n")
      .replace(/&[a-zA-Z#0-9]+;/g, " ");
  } else {
    title = path.basename(file, ext);
    body = raw;
    for (const line of raw.split("\n")) {
      if (line.trim()) {
        const t = line.trim().replace(/^#+\s*/, "").trim();
        title = t.length > 80 ? t.slice(0, 80) + "…" : t;
        break;
      }
    }
  }
  const lines = body.split("\n").map((ln) => ln.replace(/[ \t]+/g, " ").replace(/\s+$/, ""));
  return { title, text: lines.join("\n") };
}

function chunkText(text, targetChars) {
  text = text.trim();
  if (!text) return [];
  if (targetChars <= 0) return [text];
  const paras = text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  const chunks = [];
  let buf = "";
  for (const p of paras) {
    if (!buf) buf = p;
    else if (buf.length + 2 + p.length <= targetChars) buf += "\n\n" + p;
    else { chunks.push(buf); buf = p; }
  }
  if (buf) chunks.push(buf);
  return chunks;
}

function walk(dir, exts) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full, exts));
    else if (exts.has(path.extname(entry.name).toLowerCase().replace(/^\./, ""))) out.push(full);
  }
  return out;
}

function collectChunks(corpus, exts, targetChars, minChars) {
  const files = walk(corpus, exts).sort();
  const chunks = [];
  for (const file of files) {
    const rel = path.relative(corpus, file).split(path.sep).join("/");
    const { title, text } = extractText(file);
    const pieces = chunkText(text, targetChars);
    pieces.forEach((piece, j) => {
      if (piece.length < minChars) return;
      chunks.push({
        id: `${rel}#chunk-${j}`,
        text: piece,
        meta: { title, source_path: rel, section: rel.includes("/") ? rel.split("/")[0] : "" },
      });
    });
  }
  return chunks;
}

// --------------------------------------------------------------------------- //
// BM25 inverted index
// --------------------------------------------------------------------------- //

function buildIndex(chunks, k1, b) {
  const postings = new Map(); // term -> [[docIdx, tf], ...]
  const doclen = [];
  chunks.forEach((ch, i) => {
    const toks = tokenize(ch.text);
    doclen.push(toks.length);
    const tf = new Map();
    for (const t of toks) tf.set(t, (tf.get(t) || 0) + 1);
    for (const [term, c] of tf) {
      if (!postings.has(term)) postings.set(term, []);
      postings.get(term).push([i, c]);
    }
  });
  const N = chunks.length;
  const avgdl = N ? doclen.reduce((s, x) => s + x, 0) / N : 0;
  const df = {};
  const postingsObj = {};
  for (const [t, pl] of postings) { df[t] = pl.length; postingsObj[t] = pl; }
  return { params: { k1, b }, N, avgdl, doclen, df, postings: postingsObj };
}

// --------------------------------------------------------------------------- //
// Bundle writer
// --------------------------------------------------------------------------- //

function bundleFiles(chunks, index, sourceDesc) {
  const chunksJsonl = chunks.map((ch) => JSON.stringify(ch)).join("\n") + "\n";
  const indexJson = JSON.stringify(index);
  const searchJs = fs.readFileSync(path.join(TEMPLATE_DIR, "search.js"), "utf8");
  let skillMd = fs.readFileSync(path.join(TEMPLATE_DIR, BUNDLE_SKILL), "utf8");
  skillMd = skillMd.split("{{SOURCE}}").join(sourceDesc).split("{{CHUNK_COUNT}}").join(String(chunks.length));
  return { "chunks.jsonl": chunksJsonl, "index.json": indexJson, "search.js": searchJs, "SKILL.md": skillMd };
}

function writeBundle(outDir, files) {
  fs.mkdirSync(outDir, { recursive: true });
  for (const [name, content] of Object.entries(files)) {
    fs.writeFileSync(path.join(outDir, name), content);
  }
}

function zipSkill(files, skillPath) {
  const root = path.basename(skillPath, path.extname(skillPath));
  const entries = Object.entries(files).sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([name, content]) => ({ name: `${root}/${name}`, data: content }));
  fs.writeFileSync(skillPath, zipStore(entries));
}

// --------------------------------------------------------------------------- //
// CLI
// --------------------------------------------------------------------------- //

function parseArgs(argv) {
  const a = { corpus: null, out: "out/kb", name: "lexical-kb", ext: "txt,md,html,htm",
    targetChars: 1200, minChars: 40, k1: 1.5, b: 0.75, source: "", zip: false };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t === "--zip") { a.zip = true; continue; }
    if (!t.startsWith("--")) { a.corpus = t; continue; }
    const val = argv[++i];
    if (t === "--out") a.out = val;
    else if (t === "--name") a.name = val;
    else if (t === "--ext") a.ext = val;
    else if (t === "--target-chars") a.targetChars = Number(val);
    else if (t === "--min-chars") a.minChars = Number(val);
    else if (t === "--k1") a.k1 = Number(val);
    else if (t === "--b") a.b = Number(val);
    else if (t === "--source") a.source = val;
  }
  return a;
}

function main(argv) {
  const a = parseArgs(argv);
  if (!a.corpus) { console.error("usage: node build_lexkb.js CORPUS_DIR [--out ...] [--zip]"); return 1; }
  const exts = new Set(a.ext.split(",").map((e) => e.trim().replace(/^\./, "").toLowerCase()).filter(Boolean));
  const chunks = collectChunks(a.corpus, exts, a.targetChars, a.minChars);
  if (!chunks.length) { console.error(`no chunks produced from ${a.corpus} (exts=${[...exts]})`); return 1; }
  const index = buildIndex(chunks, a.k1, a.b);
  const files = bundleFiles(chunks, index, a.source || `${path.basename(a.corpus)} corpus`);

  writeBundle(a.out, files);
  const nFiles = new Set(chunks.map((c) => c.meta.source_path)).size;
  console.log(`built ${chunks.length} chunks from ${nFiles} files (target_chars=${a.targetChars}, ` +
    `avgdl=${index.avgdl.toFixed(0)} tokens, vocab=${Object.keys(index.df).length}) -> ${a.out}`);

  if (a.zip) {
    const skillPath = path.join(path.dirname(a.out), `${a.name}.skill`);
    zipSkill(files, skillPath);
    console.log(`zipped -> ${skillPath} (${(fs.statSync(skillPath).size / 1024).toFixed(1)} KB)`);
  }
  return 0;
}

module.exports = { extractText, chunkText, collectChunks, buildIndex, bundleFiles };

if (require.main === module) {
  process.exit(main(process.argv.slice(2)));
}
