// Shared plumbing: find Playwright and the Strudel web bundle, launch Chromium, write WAVs.
import { createRequire } from 'module';
import { execSync } from 'child_process';
import fs from 'fs';
import os from 'os';
import path from 'path';
import { fileURLToPath } from 'url';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
export const STRUDEL_VERSION = process.env.STRUDEL_VERSION || '1.2.6';

export function loadPlaywright() {
  const tries = [process.cwd() + '/', HERE + '/'];
  try { tries.push(execSync('npm root -g').toString().trim() + '/'); } catch {}
  for (const base of tries) {
    try { return createRequire(base)('playwright'); } catch {}
  }
  throw new Error('playwright not found: npm i -g playwright (Chromium must be installed or preinstalled)');
}

// Local copy of @strudel/web's UMD bundle, installed once into a cache dir.
export function strudelBundle() {
  const dir = path.join(os.homedir(), '.cache', 'listening-to-music', `strudel-${STRUDEL_VERSION}`);
  const file = path.join(dir, 'node_modules', '@strudel', 'web', 'dist', 'index.js');
  if (!fs.existsSync(file)) {
    fs.mkdirSync(dir, { recursive: true });
    execSync(`npm i --silent --prefix "${dir}" @strudel/web@${STRUDEL_VERSION}`, { stdio: 'inherit' });
  }
  return fs.readFileSync(file);
}

export async function launch() {
  const { chromium } = loadPlaywright();
  const opts = { args: ['--autoplay-policy=no-user-gesture-required'] };
  if (process.env.HTTPS_PROXY) opts.proxy = { server: process.env.HTTPS_PROXY };
  return chromium.launch(opts);
}

// Pages are served from an https origin via request interception: AudioWorklet (supersaw and
// other worklet synths) only exists in a secure context, and http://anything is not one.
export const ORIGIN = 'https://local.test/';

export async function wirePage(browser, { html, strudel = true, quiet = false }) {
  const page = await browser.newPage();
  await page.addInitScript({ path: path.join(HERE, 'tap.js') });
  const bundle = strudel ? strudelBundle() : null;
  page.on('pageerror', (e) => console.error('[pageerror]', e.message));
  if (!quiet) page.on('console', (m) => { const t = m.text(); if (/error|fail/i.test(t) && !/deprecated|Failed to load resource/i.test(t)) console.error('[page]', t.slice(0, 200)); });
  await page.route('**/*', (r) => {
    const u = r.request().url();
    if (u.startsWith(ORIGIN) && html) return r.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: html });
    if (bundle && /@strudel\/web(@[\d.]+)?\/dist\/index\.js/.test(u)) return r.fulfill({ status: 200, contentType: 'text/javascript; charset=utf-8', body: bundle });
    if (/fonts\.(googleapis|gstatic)\.com/.test(u)) return r.abort();
    return r.continue();
  });
  return page;
}

export function writeWav(file, { sr, b64 }) {
  const f32 = new Float32Array(Buffer.from(b64, 'base64').buffer.slice(0));
  const data = Buffer.from(f32.buffer), hdr = Buffer.alloc(44);
  hdr.write('RIFF', 0); hdr.writeUInt32LE(36 + data.length, 4); hdr.write('WAVE', 8); hdr.write('fmt ', 12);
  hdr.writeUInt32LE(16, 16); hdr.writeUInt16LE(3, 20); hdr.writeUInt16LE(2, 22); hdr.writeUInt32LE(sr, 24);
  hdr.writeUInt32LE(sr * 8, 28); hdr.writeUInt16LE(8, 32); hdr.writeUInt16LE(32, 34); hdr.write('data', 36); hdr.writeUInt32LE(data.length, 40);
  fs.writeFileSync(file, Buffer.concat([hdr, data]));
  let peak = 0; for (let i = 0; i < f32.length; i++) peak = Math.max(peak, Math.abs(f32[i]));
  let clip = 0; for (let i = 0; i < f32.length; i++) if (Math.abs(f32[i]) > 1) clip++;
  return { seconds: f32.length / 2 / sr, peak, clipped: clip / Math.max(1, f32.length) };
}

export function parseArgs(argv, defaults) {
  const out = { ...defaults, _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) { const k = a.slice(2); const v = argv[i + 1]; if (v === undefined || v.startsWith('--')) out[k] = true; else { out[k] = v; i++; } }
    else out._.push(a);
  }
  return out;
}
