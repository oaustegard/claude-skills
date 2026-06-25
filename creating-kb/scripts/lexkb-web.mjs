/**
 * lexkb-web.mjs — browser build core for the creating-kb packer SPA.
 *
 * A faithful ES-module port of the pure build logic in `build_lexkb.js` +
 * `zipstore.js` (chunk -> BM25 index -> STORED zip), with no Node/`fs`
 * dependency so it runs in the browser. The Node CLI stays canonical; this is
 * the second implementation, pinned byte-identical by `test_web_parity.mjs`
 * (same pattern as the search.js/search.py parity pin). The tokenizer is copied
 * verbatim from search.js so the index matches what the shipped searchers read.
 *
 * The SPA fetches the canonical search.js / search.py / bundle_SKILL.md at
 * runtime and passes them to bundleFiles(), so the shipped runtime is never
 * duplicated here.
 */

const TOKEN_RE = /[\p{L}\p{N}_]+/gu;

export function tokenize(text) {
  const out = [];
  for (const m of String(text).toLowerCase().matchAll(TOKEN_RE)) out.push(m[0]);
  return out;
}

// --- text extraction + structural chunking (string in, no fs) --------------- //

export function extractText(name, raw) {
  const dot = name.lastIndexOf(".");
  const ext = dot >= 0 ? name.slice(dot).toLowerCase() : "";
  const stem = dot >= 0 ? name.slice(0, dot) : name;
  let title, body;
  if (ext === ".html" || ext === ".htm") {
    const m = raw.match(/<title>([\s\S]*?)<\/title>/i);
    title = m ? m[1].trim() : stem;
    body = raw.replace(/<(script|style)[^>]*>[\s\S]*?<\/\1>/gi, " ")
      .replace(/<[^>]+>/g, "\n")
      .replace(/&[a-zA-Z#0-9]+;/g, " ");
  } else {
    title = stem;
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

export function chunkText(text, targetChars) {
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

/** files: [{name, text}] (relative name with forward slashes). */
export function collectChunks(files, exts, targetChars, minChars) {
  const sorted = [...files].sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  const chunks = [];
  for (const f of sorted) {
    const dot = f.name.lastIndexOf(".");
    const ext = dot >= 0 ? f.name.slice(dot + 1).toLowerCase() : "";
    if (!exts.has(ext)) continue;
    const rel = f.name;
    const { title, text } = extractText(f.name, f.text);
    chunkText(text, targetChars).forEach((piece, j) => {
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

// --- BM25 inverted index ---------------------------------------------------- //

export function buildIndex(chunks, k1, b) {
  const postings = new Map();
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

// --- bundle assembly -------------------------------------------------------- //

/** runtime = {searchJs, searchPy, bundleSkillMd} fetched by the caller. */
export function bundleFiles(chunks, index, sourceDesc, runtime) {
  const chunksJsonl = chunks.map((ch) => JSON.stringify(ch)).join("\n") + "\n";
  const skillMd = runtime.bundleSkillMd
    .split("{{SOURCE}}").join(sourceDesc)
    .split("{{CHUNK_COUNT}}").join(String(chunks.length));
  return {
    "chunks.jsonl": chunksJsonl,
    "index.json": JSON.stringify(index),
    "search.js": runtime.searchJs,
    "search.py": runtime.searchPy,
    "SKILL.md": skillMd,
  };
}

// --- STORED zip writer (ported verbatim from zipstore.js) ------------------- //

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function toBytes(data) {
  if (typeof data === "string") return new TextEncoder().encode(data);
  return data instanceof Uint8Array ? data : new Uint8Array(data);
}

const DOS_TIME = 0;
const DOS_DATE = 0x0021; // 1980-01-01

export function zipStore(files) {
  const entries = files.map((f) => {
    const nameBytes = new TextEncoder().encode(f.name);
    const data = toBytes(f.data);
    return { nameBytes, data, crc: crc32(data) };
  });
  const chunks = [];
  let offset = 0;
  const central = [];
  for (const e of entries) {
    const local = new ArrayBuffer(30 + e.nameBytes.length);
    const dv = new DataView(local);
    dv.setUint32(0, 0x04034b50, true);
    dv.setUint16(4, 20, true);
    dv.setUint16(6, 0, true);
    dv.setUint16(8, 0, true);
    dv.setUint16(10, DOS_TIME, true);
    dv.setUint16(12, DOS_DATE, true);
    dv.setUint32(14, e.crc, true);
    dv.setUint32(18, e.data.length, true);
    dv.setUint32(22, e.data.length, true);
    dv.setUint16(26, e.nameBytes.length, true);
    dv.setUint16(28, 0, true);
    const lh = new Uint8Array(local);
    lh.set(e.nameBytes, 30);
    chunks.push(lh, e.data);
    e.offset = offset;
    offset += lh.length + e.data.length;
  }
  for (const e of entries) {
    const cd = new ArrayBuffer(46 + e.nameBytes.length);
    const dv = new DataView(cd);
    dv.setUint32(0, 0x02014b50, true);
    dv.setUint16(4, 20, true);
    dv.setUint16(6, 20, true);
    dv.setUint16(8, 0, true);
    dv.setUint16(10, 0, true);
    dv.setUint16(12, DOS_TIME, true);
    dv.setUint16(14, DOS_DATE, true);
    dv.setUint32(16, e.crc, true);
    dv.setUint32(20, e.data.length, true);
    dv.setUint32(24, e.data.length, true);
    dv.setUint16(28, e.nameBytes.length, true);
    dv.setUint16(30, 0, true);
    dv.setUint16(32, 0, true);
    dv.setUint16(34, 0, true);
    dv.setUint16(36, 0, true);
    dv.setUint32(38, 0, true);
    dv.setUint32(42, e.offset, true);
    const c = new Uint8Array(cd);
    c.set(e.nameBytes, 46);
    central.push(c);
  }
  const centralSize = central.reduce((s, c) => s + c.length, 0);
  const centralOffset = offset;
  const eocd = new ArrayBuffer(22);
  const dv = new DataView(eocd);
  dv.setUint32(0, 0x06054b50, true);
  dv.setUint16(8, entries.length, true);
  dv.setUint16(10, entries.length, true);
  dv.setUint32(12, centralSize, true);
  dv.setUint32(16, centralOffset, true);
  const all = [...chunks, ...central, new Uint8Array(eocd)];
  const totalLen = all.reduce((s, c) => s + c.length, 0);
  const result = new Uint8Array(totalLen);
  let p = 0;
  for (const c of all) { result.set(c, p); p += c.length; }
  return result;
}

/** Assemble a .skill zip; entries placed under a top-level <root>/ folder. */
export function zipSkill(files, root) {
  const entries = Object.entries(files).sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([name, content]) => ({ name: `${root}/${name}`, data: content }));
  return zipStore(entries);
}
