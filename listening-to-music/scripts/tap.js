// Injected before any page script. Every node that connects straight to an AudioContext's
// destination is routed through a per-context tap gain; a ScriptProcessor on each tap records
// float PCM. Works alongside pages that wrap AudioNode.prototype.connect themselves (their
// wrapper ends up calling this one). window.__listen.start()/stop() control capture.
(() => {
  const origConnect = AudioNode.prototype.connect;
  const taps = new Map(); // context -> { gain, proc, L: [], R: [] }
  let recording = false;
  function tapFor(ctx) {
    let t = taps.get(ctx);
    if (t) return t;
    const gain = ctx.createGain(); gain.__listenTap = true;
    const proc = ctx.createScriptProcessor(4096, 2, 2); proc.__listenTap = true;
    t = { ctx, gain, proc, L: [], R: [] };
    proc.onaudioprocess = (e) => {
      if (recording) {
        t.L.push(new Float32Array(e.inputBuffer.getChannelData(0)));
        t.R.push(new Float32Array(e.inputBuffer.getChannelData(1)));
      }
      e.outputBuffer.getChannelData(0).fill(0); e.outputBuffer.getChannelData(1).fill(0);
    };
    origConnect.call(gain, ctx.destination);
    origConnect.call(gain, proc);
    origConnect.call(proc, ctx.destination);
    taps.set(ctx, t);
    return t;
  }
  AudioNode.prototype.connect = function (dest, ...rest) {
    if (typeof AudioDestinationNode !== 'undefined' && dest instanceof AudioDestinationNode && !this.__listenTap) {
      return origConnect.call(this, tapFor(dest.context).gain, ...rest);
    }
    return origConnect.call(this, dest, ...rest);
  };
  window.__listen = {
    start() { for (const t of taps.values()) { t.L = []; t.R = []; } recording = true; },
    // returns the loudest context's capture as interleaved float32, base64-encoded
    stop() {
      recording = false;
      let best = null, bestE = -1;
      for (const t of taps.values()) {
        let e = 0; for (const b of t.L) for (let i = 0; i < b.length; i += 16) e += b[i] * b[i];
        if (e > bestE) { bestE = e; best = t; }
      }
      if (!best) return { sr: 44100, b64: '' };
      const n = best.L.reduce((a, b) => a + b.length, 0), out = new Float32Array(n * 2);
      let o = 0;
      for (let i = 0; i < best.L.length; i++) for (let j = 0; j < best.L[i].length; j++) { out[o++] = best.L[i][j]; out[o++] = best.R[i][j]; }
      const bytes = new Uint8Array(out.buffer); let s = '';
      for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
      return { sr: best.ctx.sampleRate, b64: btoa(s) };
    },
  };
})();
