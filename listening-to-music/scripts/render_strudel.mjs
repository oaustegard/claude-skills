#!/usr/bin/env node
// Render Strudel code through the real engine (superdough in headless Chromium) to a float WAV,
// and/or dump the note events of each $layer for the clash scan.
//
//   node render_strudel.mjs code.js --out take.wav [--seconds 20] [--warmup 0] [--no-samples]
//   node render_strudel.mjs code.js --events events.json [--cycles 16]
//
// --warmup N  let the pattern run N seconds before capture starts (samples load on first use,
//             so the first bar of a fresh page can be missing sounds)
import fs from 'fs';
import { launch, wirePage, writeWav, parseArgs, ORIGIN, STRUDEL_VERSION } from './common.mjs';

const a = parseArgs(process.argv.slice(2), { seconds: '20', warmup: '0', cycles: '16' });
const codeFile = a._[0];
if (!codeFile || (!a.out && !a.events)) { console.error('usage: render_strudel.mjs code.js --out take.wav | --events ev.json'); process.exit(2); }
const code = fs.readFileSync(codeFile, 'utf8');

const html = `<!doctype html><html><body>
<script src="https://cdn.jsdelivr.net/npm/@strudel/web@${STRUDEL_VERSION}/dist/index.js"></script>
<script>
window.boot = async (withSamples) => {
  const ds = 'https://raw.githubusercontent.com/felixroos/dough-samples/main';
  const ts = 'https://raw.githubusercontent.com/todepond/samples/main';
  await strudel.initStrudel({ prebake: withSamples ? () => Promise.all([
    strudel.samples(ds + '/tidal-drum-machines.json'), strudel.samples(ds + '/piano.json'),
    strudel.samples('github:tidalcycles/dirt-samples'), strudel.aliasBank(ts + '/tidal-drum-machines-alias.json'),
  ]).catch(e => console.error('sample banks failed: ' + e)) : undefined });
};
// split "$name:" / "name:" blocks so each layer can be queried on its own
window.layers = (code) => {
  const lines = code.split('\\n'), head = [], blocks = [];
  let cur = null;
  for (const ln of lines) {
    const m = /^(_?\\$?[A-Za-z0-9_]*)\\s*:(?!:)/.exec(ln);
    if (m && m[1] !== '' && !/^\\s/.test(ln)) { cur = { name: m[1] === '$' ? 'layer' + (blocks.length + 1) : m[1].replace(/^\\$/, ''), lines: [ln] }; blocks.push(cur); }
    else if (cur) cur.lines.push(ln); else head.push(ln);
  }
  return { head: head.join('\\n'), blocks: blocks.map(b => ({ name: b.name, code: b.lines.join('\\n') })) };
};
window.events = async (code, cycles) => {
  const { head, blocks } = layers(code), out = [];
  const list = blocks.length ? blocks : [{ name: 'all', code: '' }];
  for (const b of list) {
    const pat = await strudel.evaluate(head + '\\n' + b.code, false);
    if (!pat || !pat.queryArc) continue;
    for (const h of pat.queryArc(0, cycles)) {
      if (!h.hasOnset()) continue;
      const v = h.value || {};
      let midi = null;
      if (typeof v.note === 'number') midi = v.note; else if (typeof v.note === 'string') { try { midi = strudel.noteToMidi(v.note); } catch {} }
      else if (typeof v.freq === 'number') midi = 69 + 12 * Math.log2(v.freq / 440);
      if (midi === null || Number.isNaN(midi)) continue;
      out.push({ layer: b.name, t0: h.whole.begin.valueOf(), t1: h.whole.end.valueOf(), midi: Math.round(midi), s: v.s || '' });
    }
  }
  strudel.hush();
  return out;
};
</script></body></html>`;

const browser = await launch();
try {
  const page = await wirePage(browser, { html });
  await page.goto(ORIGIN + 'render.html');
  await page.evaluate((s) => window.boot(s), !a['no-samples']);
  await page.mouse.click(4, 4); // initStrudel loads the AudioWorklets on the first document click
  if (a.events) {
    const ev = await page.evaluate(([c, n]) => window.events(c, n), [code, Number(a.cycles)]);
    fs.writeFileSync(a.events, JSON.stringify({ cycles: Number(a.cycles), events: ev }));
    console.log(`events: ${ev.length} over ${a.cycles} cycles -> ${a.events}`);
  }
  if (a.out) {
    const res = await page.evaluate(async ([c, secs, warm]) => {
      await strudel.evaluate(c);
      await new Promise(r => setTimeout(r, warm * 1000));
      window.__listen.start();
      await new Promise(r => setTimeout(r, secs * 1000));
      const out = window.__listen.stop(); strudel.hush(); return out;
    }, [code, Number(a.seconds), Number(a.warmup)]);
    const info = writeWav(a.out, res);
    console.log(`wrote ${a.out}: ${info.seconds.toFixed(1)} s, peak ${info.peak.toFixed(2)}${info.clipped > 0 ? `, CLIPPED ${(100 * info.clipped).toFixed(2)}% of samples` : ''}`);
  }
} finally { await browser.close(); }
