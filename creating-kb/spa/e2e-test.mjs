// End-to-end SPA test: real headless Chromium drives the packer, we verify the
// downloaded .skill unzips and is queryable.
//
// Optional/manual (browser dep). Requires `npm i playwright-core` and a Chromium
// binary; set $CHROMIUM to its path (defaults to the CCotw preinstalled build).
// The durable, dependency-free pin is test_web_parity.mjs (Node-only).
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { chromium } from "playwright-core";

const ROOT = "/home/user/claude-workspace/.spokes/claude-skills/creating-kb";
const CHROME = process.env.CHROMIUM || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const MIME = { ".html": "text/html", ".mjs": "text/javascript", ".js": "text/javascript",
  ".py": "text/plain", ".md": "text/markdown", ".json": "application/json" };

const server = http.createServer((req, res) => {
  const fp = path.join(ROOT, decodeURIComponent(req.url.split("?")[0]));
  if (!fp.startsWith(ROOT) || !fs.existsSync(fp) || fs.statSync(fp).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { "content-type": MIME[path.extname(fp)] || "application/octet-stream" });
  fs.createReadStream(fp).pipe(res);
});
await new Promise((r) => server.listen(0, r));
const port = server.address().port;

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "e2e-"));
const corpus = path.join(tmp, "corpus");
fs.mkdirSync(corpus);
fs.writeFileSync(path.join(corpus, "redis.md"), "# Redis\n\nRedis is an in-memory key-value store used for caching and queues.\n");
fs.writeFileSync(path.join(corpus, "postgres.md"), "# Postgres\n\nPostgreSQL is a relational database with strong ACID guarantees and SQL.\n");

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
const ctx = await browser.newContext({ acceptDownloads: true });
const page = await ctx.newPage();
const errs = [];
page.on("pageerror", (e) => errs.push(String(e)));
await page.goto(`http://localhost:${port}/spa/index.html`);

await page.setInputFiles("#picker", [path.join(corpus, "redis.md"), path.join(corpus, "postgres.md")]);
await page.fill("#name", "e2e-kb");
await page.fill("#target", "0");

await page.click("#build");
await page.waitForSelector("a.dl");
const status = await page.textContent("#status");
const [download] = await Promise.all([
  page.waitForEvent("download"),
  page.click("a.dl"),
]);
const out = path.join(tmp, "e2e-kb.skill");
await download.saveAs(out);
await browser.close();
server.close();

// verify the downloaded .skill
const names = execFileSync("python3", ["-c",
  `import zipfile;print('\\n'.join(zipfile.ZipFile('${out}').namelist()))`], { encoding: "utf8" }).trim();
const bundle = path.join(tmp, "unz");
execFileSync("python3", ["-c",
  `import zipfile;zipfile.ZipFile('${out}').extractall('${bundle}')`]);
const hit = execFileSync("python3", [path.join(bundle, "e2e-kb", "search.py"),
  "--index", path.join(bundle, "e2e-kb"), "--core", "database", "--expand", "relational SQL", "--k", "1"], { encoding: "utf8" });
const hitId = JSON.parse(hit).hits[0].id;

console.log("status:", status.replace(/\n/g, " "));
console.log("zip entries:\n" + names);
console.log("query 'database' top hit:", hitId);
const ok = errs.length === 0 && /Built 2 chunks/.test(status) && names.includes("e2e-kb/search.js")
  && names.includes("e2e-kb/search.py") && names.includes("e2e-kb/index.json") && hitId === "postgres.md#chunk-0";
if (errs.length) console.log("PAGE ERRORS:", errs);
console.log("\nE2E SPA:", ok ? "PASS" : "FAIL");
fs.rmSync(tmp, { recursive: true, force: true });
process.exit(ok ? 0 : 1);
