#!/usr/bin/env node
// Record whatever a web page plays through Web Audio (a generative radio, a synth demo).
//
//   node record_page.mjs <url-or-local.html> --out take.wav [--click "#power"] [--seconds 30]
//        [--warmup 0] [--query "station=house&energy=flow"] [--eval "window.__fm.setSeed(7)"]
//
// A local file is served from an https origin (AudioWorklet needs a secure context). A page
// that loads @strudel/web from a CDN gets a cached local copy of the bundle instead.
// --eval runs before the click, so a test hook can pin a seed for before/after comparisons.
import fs from 'fs';
import path from 'path';
import { launch, wirePage, writeWav, parseArgs, ORIGIN } from './common.mjs';

const a = parseArgs(process.argv.slice(2), { seconds: '30', warmup: '0', query: '' });
const src = a._[0];
if (!src || !a.out) { console.error('usage: record_page.mjs <url|file.html> --out take.wav [--click sel]'); process.exit(2); }
const local = fs.existsSync(src);
const browser = await launch();
try {
  const page = await wirePage(browser, { html: local ? fs.readFileSync(src, 'utf8') : null });
  const url = (local ? ORIGIN + path.basename(src) : src) + (a.query ? (src.includes('?') ? '&' : '?') + a.query : '');
  await page.goto(url, { waitUntil: 'load' });
  if (a.eval) await page.evaluate(a.eval);
  if (a.click) await page.click(a.click); else await page.mouse.click(4, 4);
  const res = await page.evaluate(async ([secs, warm]) => {
    await new Promise(r => setTimeout(r, warm * 1000));
    window.__listen.start();
    await new Promise(r => setTimeout(r, secs * 1000));
    return window.__listen.stop();
  }, [Number(a.seconds), Number(a.warmup)]);
  if (!res.b64) throw new Error('nothing reached the speakers: check --click and the page console');
  const info = writeWav(a.out, res);
  console.log(`wrote ${a.out}: ${info.seconds.toFixed(1)} s, peak ${info.peak.toFixed(2)}${info.clipped > 0 ? `, CLIPPED ${(100 * info.clipped).toFixed(2)}% of samples` : ''}`);
} finally { await browser.close(); }
