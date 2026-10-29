// Capture a web app at phone size for a Remotion reel: full-page stills,
// element positions, and deterministic frame sequences of live animations.
// Copy into the project as capture/capture.cjs, edit SHOTS, then run:
//   NODE_PATH=$(npm root -g) node capture/capture.cjs [shotName]
// Output: public/shots/<name>.png, public/shots/<name>/f0000.jpg..., public/shots/layout.json
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const OUT = path.resolve(__dirname, '../public/shots');
const BASE = process.env.APP_URL || 'https://example.com';
const VIEW = { width: 390, height: 844 }; // full screen; Playwright's 'iPhone 14' preset is 390x664
const DPR = 3;
// WebGPU in headless Chromium needs SwiftShader Vulkan; harmless for 2D apps.
const ARGS = ['--enable-unsafe-webgpu', '--enable-features=Vulkan', '--use-vulkan=swiftshader',
  '--use-angle=swiftshader', '--use-webgpu-adapter=swiftshader'];

// Each shot gets its own page. A page whose clock is frozen stays frozen,
// so later real-time waits on it no longer advance the app's timers.
const SHOTS = {
  // still: full-page PNG, scrolled through in Remotion with <ScrollShot>
  home: async (page) => {
    await page.goto(BASE + '/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${OUT}/home.png`, fullPage: true });
  },
  // motion: freeze the clock, start the animation, step it frame by frame
  chart: async (page) => {
    await page.goto(BASE + '/chart', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);
    await freezeClock(page);
    await page.getByRole('button', { name: 'Play', exact: true }).click(); // exact: a regex also hits 'replay', 'display'...
    await sequence(page, 'chart', /*pageSeconds*/ 10, /*frames*/ 120);
  },
};

// Element boxes in page CSS px, for tap points and scroll targets.
const MEASURE = async (page) => {
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  const box = (loc) => loc.first().evaluate((el) => {
    const r = el.getBoundingClientRect();
    return { x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height };
  });
  return { viewport: VIEW, header: await box(page.locator('header')) };
};

// clock.install() alone does NOT freeze time: the fake clock keeps ticking at
// real speed, so a slow screenshot lets the app run ahead. pauseAt() freezes it;
// after that only fastForward/runFor move the page's time.
async function freezeClock(page) {
  await page.clock.install();
  await page.clock.pauseAt(await page.evaluate(() => Date.now() + 50));
}

// Steps page time by pageSeconds/frames per output frame. rAF animations land
// on exact times however slow the software renderer is; a CDP screencast in
// real time gave 4 fps on a WebGPU heatmap.
async function sequence(page, name, pageSeconds, frames) {
  const dir = path.join(OUT, name);
  fs.mkdirSync(dir, { recursive: true });
  const per = (pageSeconds * 1000) / frames; // page ms per output frame
  const TICK = Math.min(34, per);             // runFor below also advances page time
  const step = per - TICK;
  for (let i = 0; i < frames; i++) {
    await page.clock.fastForward(step); // fires due timers once; rAF included
    await page.clock.runFor(TICK);        // two more rAF ticks so the canvas repaints
    await page.waitForTimeout(40);      // real time for the compositor to present
    await page.screenshot({ path: path.join(dir, `f${String(i).padStart(4, '0')}.jpg`), quality: 92 });
  }
  console.log(name, frames, 'frames');
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ARGS });
  const ctx = await browser.newContext({ viewport: VIEW, deviceScaleFactor: DPR, isMobile: true, hasTouch: true,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' });
  const only = process.argv[2];
  for (const [name, fn] of Object.entries(SHOTS)) {
    if (only && only !== name) continue;
    const page = await ctx.newPage();
    page.on('pageerror', (e) => console.log(name, 'pageerror', e.message));
    await fn(page);
    await page.close();
  }
  if (!only || only === 'layout') {
    const page = await ctx.newPage();
    fs.writeFileSync(`${OUT}/layout.json`, JSON.stringify(await MEASURE(page), null, 1));
    await page.close();
  }
  await browser.close();
})();
