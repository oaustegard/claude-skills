// [count u8][stride u8] then count 16-bit little-endian samples, stride bytes apart.
export function decodeSamples(u8) {
  if (u8.length < 2) return null;
  const count = u8[0], stride = u8[1];
  if (2 + count * stride > u8.length) return null;   // bug: a sample is 2 bytes, not stride
  const out = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    const p = 2 + i * stride;
    out[i] = (u8[p] | (u8[p + 1] << 8)) / 32768;
  }
  return out;
}
