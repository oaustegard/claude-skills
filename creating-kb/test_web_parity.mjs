/**
 * Parity pin: the browser build core (lexkb-web.mjs) must produce byte-identical
 * output to the canonical Node builder (build_lexkb.js + zipstore.js). Same
 * pattern as test_parity.py (two impls, one pin). Run: node test_web_parity.mjs
 *
 * Asserts identical chunks.jsonl, index.json, the full bundle file map, and the
 * final .skill zip bytes for the same corpus. Exit 0 on parity, 1 otherwise.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const node = require("./scripts/build_lexkb.js");
const { zipStore } = require("./scripts/zipstore.js");
const web = await import("./scripts/lexkb-web.mjs");

const CORPUS = {
  "factions.txt": "Liberty is to faction what air is to fire. The latent causes of faction are sown in the nature of man.\n",
  "powers.txt": "The accumulation of all powers, legislative, executive, and judiciary, in the same hands is tyranny.\n",
  "sub/property.html": "<html><head><title>Property</title></head><body><article>Unequal faculties of acquiring property produce economic inequality.</article></body></html>\n",
};
const EXTS = new Set(["txt", "html"]);

function eq(label, a, b) {
  const ok = a === b;
  console.log(`${ok ? "OK  " : "DIFF"} ${label}`);
  if (!ok) {
    console.log("  node:", JSON.stringify(a).slice(0, 200));
    console.log("  web :", JSON.stringify(b).slice(0, 200));
  }
  return ok;
}

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "webparity-"));
try {
  // write corpus to disk for the Node reader; keep in-memory for the web core
  const files = [];
  for (const [name, text] of Object.entries(CORPUS)) {
    const full = path.join(tmp, name);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, text);
    files.push({ name, text });
  }

  const chunksN = node.collectChunks(tmp, EXTS, 0, 40);
  const idxN = node.buildIndex(chunksN, 1.5, 0.75);
  const filesN = node.bundleFiles(chunksN, idxN, "test corpus");

  const chunksW = web.collectChunks(files, EXTS, 0, 40);
  const idxW = web.buildIndex(chunksW, 1.5, 0.75);
  const runtime = {
    searchJs: fs.readFileSync(path.join(HERE, "scripts/search.js"), "utf8"),
    searchPy: fs.readFileSync(path.join(HERE, "scripts/search.py"), "utf8"),
    bundleSkillMd: fs.readFileSync(path.join(HERE, "scripts/bundle_SKILL.md"), "utf8"),
  };
  const filesW = web.bundleFiles(chunksW, idxW, "test corpus", runtime);

  // node-side zip (same root/entry construction as build_lexkb.zipSkill)
  const root = "mykb";
  const entriesN = Object.entries(filesN).sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([name, content]) => ({ name: `${root}/${name}`, data: content }));
  const zipN = zipStore(entriesN);
  const zipW = web.zipSkill(filesW, root);

  let ok = true;
  ok &= eq("chunks.jsonl", JSON.stringify(chunksN), JSON.stringify(chunksW));
  ok &= eq("index.json", JSON.stringify(idxN), JSON.stringify(idxW));
  ok &= eq("bundle file map", JSON.stringify(filesN), JSON.stringify(filesW));
  ok &= eq("zip length", String(zipN.length), String(zipW.length));
  ok &= eq("zip bytes", Buffer.from(zipN).toString("base64"), Buffer.from(zipW).toString("base64"));

  console.log("\nWEB PARITY:", ok ? "PASS" : "FAIL");
  process.exit(ok ? 0 : 1);
} finally {
  fs.rmSync(tmp, { recursive: true, force: true });
}
