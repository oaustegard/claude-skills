"use strict";
/**
 * Minimal ZIP writer — STORED (no compression), pure JS, no dependencies.
 *
 * A `.skill` is an ordinary zip; STORED keeps the writer trivial and identical
 * across Node and the browser (no zlib / CompressionStream split), at a
 * negligible size cost for KB-scale knowledgebases. Output is deterministic
 * (fixed 1980-01-01 timestamps), so the same inputs produce a byte-identical
 * archive. This is the same writer the browser SPA / remax_kb#12 reader pairs
 * with (the reader's ZipStored is read-only).
 *
 * zipStore([{name, data}]) -> Uint8Array, where data is a Uint8Array/Buffer or
 * a string (encoded UTF-8).
 */

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

function zipStore(files) {
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
    dv.setUint32(0, 0x04034b50, true); // local file header sig
    dv.setUint16(4, 20, true); // version needed
    dv.setUint16(6, 0, true); // flags
    dv.setUint16(8, 0, true); // method = STORED
    dv.setUint16(10, DOS_TIME, true);
    dv.setUint16(12, DOS_DATE, true);
    dv.setUint32(14, e.crc, true);
    dv.setUint32(18, e.data.length, true); // compressed size
    dv.setUint32(22, e.data.length, true); // uncompressed size
    dv.setUint16(26, e.nameBytes.length, true);
    dv.setUint16(28, 0, true); // extra len
    const lh = new Uint8Array(local);
    lh.set(e.nameBytes, 30);
    chunks.push(lh, e.data);
    e.offset = offset;
    offset += lh.length + e.data.length;
  }

  for (const e of entries) {
    const cd = new ArrayBuffer(46 + e.nameBytes.length);
    const dv = new DataView(cd);
    dv.setUint32(0, 0x02014b50, true); // central dir sig
    dv.setUint16(4, 20, true); // version made by
    dv.setUint16(6, 20, true); // version needed
    dv.setUint16(8, 0, true);
    dv.setUint16(10, 0, true); // STORED
    dv.setUint16(12, DOS_TIME, true);
    dv.setUint16(14, DOS_DATE, true);
    dv.setUint32(16, e.crc, true);
    dv.setUint32(20, e.data.length, true);
    dv.setUint32(24, e.data.length, true);
    dv.setUint16(28, e.nameBytes.length, true);
    dv.setUint16(30, 0, true); // extra
    dv.setUint16(32, 0, true); // comment
    dv.setUint16(34, 0, true); // disk
    dv.setUint16(36, 0, true); // internal attrs
    dv.setUint32(38, 0, true); // external attrs
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

module.exports = { zipStore, crc32 };
