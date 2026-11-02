// Runs WGSL jobs on WebGPU in headless Chromium (SwiftShader) and writes the results.
//
//   node harness/gpu.mjs jobs.json results.json
//
// Job kinds (all share one browser and one GPUDevice):
//   {id, kind:"compile", wgsl}                       -> {messages}
//   {id, kind:"render",  wgsl, width, height, time}  -> {rgba}  (vs/fs entry points, uniform
//        @group(0) @binding(0) holding vec4f(width, height, time, 0), rgba8unorm target)
//   {id, kind:"svg",     svg, width, height}         -> {rgba}  (Chromium's own SVG raster)
//   {id, kind:"webgl",   glsl, width, height, time}  -> {rgba}  (WebGL2 fragment shader, Shadertoy uniforms)
//   {id, kind:"compute", wgsl, entry, dispatch:[x,y,z],
//        bindings:[{group, binding, type:"uniform"|"storage"|"read-only-storage", data}],
//        constants:{name or @id: number}}   (pipeline-overridable constants)
//        -> {buffers:{"g.b": base64}}
// rgba and buffer data are base64. Every job reports {ok, error?}; one failure never stops
// the batch.
import fs from "fs";
import http from "http";
import { createRequire } from "module";
const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require("playwright")); } catch { ({ chromium } = require("playwright-core")); }

// CHROME_PATH overrides; otherwise this container's pinned Chromium, else Playwright's default.
const PINNED = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome";
const CHROME = process.env.CHROME_PATH || (fs.existsSync(PINNED) ? PINNED : undefined);
const ARGS = ["--no-sandbox", "--enable-unsafe-webgpu", "--use-angle=swiftshader",
  "--use-webgpu-adapter=swiftshader", "--enable-features=Vulkan"];

const PAGE = `<!doctype html><meta charset="utf-8"><body><script>
const b64 = (u8) => { let s = ""; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000)); return btoa(s); };
const unb64 = (s) => { const b = atob(s), u = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; };
let device;
async function dev() {
  if (device) return device;
  const ad = await navigator.gpu.requestAdapter();
  if (!ad) throw new Error("no adapter");
  device = await ad.requestDevice();
  device.lost.then((i) => { device = null; console.log("device lost: " + i.message); });
  return device;
}
async function compile(d, code) {
  d.pushErrorScope("validation");
  const mod = d.createShaderModule({ code });
  const info = await mod.getCompilationInfo();
  await d.popErrorScope();
  const messages = info.messages.map((m) => ({ type: m.type, line: m.lineNum, col: m.linePos, text: m.message }));
  return { mod, messages, errors: messages.filter((m) => m.type === "error") };
}
async function readTexture(d, tex, w, h) {
  const bpr = Math.ceil(w * 4 / 256) * 256;
  const buf = d.createBuffer({ size: bpr * h, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
  const enc = d.createCommandEncoder();
  enc.copyTextureToBuffer({ texture: tex }, { buffer: buf, bytesPerRow: bpr }, [w, h]);
  d.queue.submit([enc.finish()]);
  await buf.mapAsync(GPUMapMode.READ);
  const src = new Uint8Array(buf.getMappedRange()), out = new Uint8Array(w * h * 4);
  for (let y = 0; y < h; y++) out.set(src.subarray(y * bpr, y * bpr + w * 4), y * w * 4);
  buf.unmap(); buf.destroy();
  return out;
}
window.runJob = async (job) => {
  try {
    if (job.kind === "svg") {
      const img = new Image(job.width, job.height);
      img.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(job.svg)));
      await img.decode();
      const c = document.createElement("canvas"); c.width = job.width; c.height = job.height;
      const ctx = c.getContext("2d"); ctx.drawImage(img, 0, 0, job.width, job.height);
      return { ok: true, rgba: b64(new Uint8Array(ctx.getImageData(0, 0, job.width, job.height).data.buffer)) };
    }
    if (job.kind === "webgl") {
      // reference renderer for GLSL: a full-screen triangle in WebGL2, Shadertoy uniforms set by name
      const w = job.width, h = job.height;
      const c = document.createElement("canvas"); c.width = w; c.height = h;
      const gl = c.getContext("webgl2", { preserveDrawingBuffer: true, antialias: false });
      if (!gl) return { ok: false, error: "no webgl2" };
      const sh = (type, src) => { const x = gl.createShader(type); gl.shaderSource(x, src); gl.compileShader(x);
        if (!gl.getShaderParameter(x, gl.COMPILE_STATUS)) throw new Error("glsl: " + gl.getShaderInfoLog(x)); return x; };
      const prog = gl.createProgram();
      gl.attachShader(prog, sh(gl.VERTEX_SHADER, ["#version 300 es", "void main(){vec2 p=vec2(float(gl_VertexID%2),float(gl_VertexID/2))*4.0-1.0;gl_Position=vec4(p,0.0,1.0);}"].join(String.fromCharCode(10))));
      gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, job.glsl));
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return { ok: false, error: "link: " + gl.getProgramInfoLog(prog) };
      gl.useProgram(prog);
      const t = job.time || 0, U = (n) => gl.getUniformLocation(prog, n);
      if (U("iResolution")) gl.uniform3f(U("iResolution"), w, h, 1);
      if (U("iTime")) gl.uniform1f(U("iTime"), t);
      if (U("iTimeDelta")) gl.uniform1f(U("iTimeDelta"), 1 / 60);
      if (U("iFrame")) gl.uniform1i(U("iFrame"), Math.floor(t * 60));
      if (U("iFrameRate")) gl.uniform1f(U("iFrameRate"), 60);
      gl.viewport(0, 0, w, h); gl.drawArrays(gl.TRIANGLES, 0, 3);
      const px = new Uint8Array(w * h * 4); gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
      const out = new Uint8Array(w * h * 4);   // WebGL rows run bottom-up; flip to match WebGPU
      for (let y = 0; y < h; y++) out.set(px.subarray((h - 1 - y) * w * 4, (h - y) * w * 4), y * w * 4);
      return { ok: true, rgba: b64(out) };
    }
    const d = await dev();
    const t0 = performance.now();
    const { mod, messages, errors } = await compile(d, job.wgsl);
    const compile_ms = performance.now() - t0;
    if (job.kind === "compile" || errors.length) return { ok: !errors.length, messages, compile_ms, error: errors.length ? errors.map((m) => m.line + ":" + m.col + " " + m.text).join("; ") : undefined };
    if (job.kind === "render") {
      const w = job.width, h = job.height;
      d.pushErrorScope("validation");
      const pipe = d.createRenderPipeline({ layout: "auto", vertex: { module: mod, entryPoint: job.vs || "vs" },
        fragment: { module: mod, entryPoint: job.fs || "fs", targets: [{ format: "rgba8unorm" }] }, primitive: { topology: "triangle-list" } });
      const ubuf = d.createBuffer({ size: 16, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
      d.queue.writeBuffer(ubuf, 0, new Float32Array([w, h, job.time || 0, 0]));
      let bg = null;
      try { bg = d.createBindGroup({ layout: pipe.getBindGroupLayout(0), entries: [{ binding: 0, resource: { buffer: ubuf } }] }); } catch (e) {}
      const tex = d.createTexture({ size: [w, h], format: "rgba8unorm", usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC });
      const enc = d.createCommandEncoder();
      const pass = enc.beginRenderPass({ colorAttachments: [{ view: tex.createView(), loadOp: "clear", storeOp: "store", clearValue: [0, 0, 0, 0] }] });
      pass.setPipeline(pipe); if (bg) pass.setBindGroup(0, bg); pass.draw(3); pass.end();
      const t1 = performance.now();
      d.queue.submit([enc.finish()]);
      const err = await d.popErrorScope();
      if (err) return { ok: false, error: "pipeline: " + err.message, messages };
      const rgba = await readTexture(d, tex, w, h);
      const draw_ms = performance.now() - t1;
      tex.destroy(); ubuf.destroy();
      return { ok: true, rgba: b64(rgba), messages, compile_ms, draw_ms };
    }
    if (job.kind === "compute") {
      const groups = {};
      for (const b of job.bindings) (groups[b.group] ||= []).push(b);
      d.pushErrorScope("validation");
      const layouts = [], maxg = Math.max(-1, ...Object.keys(groups).map(Number));
      for (let g = 0; g <= maxg; g++) layouts.push(d.createBindGroupLayout({ entries: (groups[g] || []).map((b) => ({ binding: b.binding, visibility: GPUShaderStage.COMPUTE, buffer: { type: b.type } })) }));
      const pipe = d.createComputePipeline({ layout: d.createPipelineLayout({ bindGroupLayouts: layouts }), compute: { module: mod, entryPoint: job.entry, constants: job.constants || {} } });
      const bufs = {};
      const bgs = layouts.map((l, g) => d.createBindGroup({ layout: l, entries: (groups[g] || []).map((b) => {
        const data = unb64(b.data);
        const usage = (b.type === "uniform" ? GPUBufferUsage.UNIFORM : GPUBufferUsage.STORAGE) | GPUBufferUsage.COPY_DST | GPUBufferUsage.COPY_SRC;
        const buf = d.createBuffer({ size: Math.max(16, Math.ceil(data.length / 16) * 16), usage });
        d.queue.writeBuffer(buf, 0, data);
        bufs[g + "." + b.binding] = { buf, size: data.length };
        return { binding: b.binding, resource: { buffer: buf } };
      }) }));
      const enc = d.createCommandEncoder();
      const pass = enc.beginComputePass(); pass.setPipeline(pipe);
      bgs.forEach((bg, g) => pass.setBindGroup(g, bg));
      pass.dispatchWorkgroups(...job.dispatch); pass.end();
      const reads = {};
      for (const [k, { buf, size }] of Object.entries(bufs)) {
        const rb = d.createBuffer({ size: buf.size, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
        enc.copyBufferToBuffer(buf, 0, rb, 0, buf.size); reads[k] = { rb, size };
      }
      d.queue.submit([enc.finish()]);
      const err = await d.popErrorScope();
      if (err) return { ok: false, error: "pipeline: " + err.message, messages };
      const out = {};
      for (const [k, { rb, size }] of Object.entries(reads)) { await rb.mapAsync(GPUMapMode.READ); out[k] = b64(new Uint8Array(rb.getMappedRange()).slice(0, size)); rb.unmap(); rb.destroy(); }
      Object.values(bufs).forEach(({ buf }) => buf.destroy());
      return { ok: true, buffers: out, messages, compile_ms };
    }
    return { ok: false, error: "unknown kind " + job.kind };
  } catch (e) { return { ok: false, error: String(e && e.message || e) }; }
};
</script>`;

const [jobsPath, outPath] = process.argv.slice(2);
const jobs = JSON.parse(fs.readFileSync(jobsPath, "utf8"));
const srv = http.createServer((req, res) => { res.writeHead(200, { "Content-Type": "text/html" }); res.end(PAGE); });
await new Promise((r) => srv.listen(0, "127.0.0.1", r));
const browser = await chromium.launch({ executablePath: CHROME, headless: true, args: ARGS });
const results = {};
try {
  const page = await browser.newPage();
  page.on("console", (m) => process.stderr.write("[page] " + m.text() + "\n"));
  await page.goto(`http://127.0.0.1:${srv.address().port}/`);
  for (const job of jobs) {
    const t = Date.now();
    results[job.id] = await page.evaluate((j) => window.runJob(j), job);
    results[job.id].wall_ms = Date.now() - t;
    if (!results[job.id].ok) process.stderr.write(`[job ${job.id}] ${results[job.id].error}\n`);
  }
} finally {
  await browser.close();
  srv.close();
}
fs.writeFileSync(outPath, JSON.stringify(results));
