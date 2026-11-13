// Strict arrays for test harnesses: silent out-of-range access throws.
//
// JavaScript never signals an out-of-range index. a[i] past the end reads
// undefined, which then becomes NaN or 0 in arithmetic (undefined << 8 === 0).
// A write past the end of a typed array is dropped. slice and subarray clamp
// their bounds. A fuzzer or property test sees none of it.
//
//   import { strict } from "./strict.mjs";
//   decode(strict(bytes));        // Array or any TypedArray
//
// Integer-key reads and writes outside [0, length) throw RangeError, as do
// slice/subarray calls whose end passes length or whose bounds are negative.
// Their results are strict too. Other methods run on the raw array: a
// strict view does not check what forEach, map or set do internally.

const isIndex = (p) => typeof p === "string" && /^(0|[1-9]\d*)$/.test(p);
const isNegIndex = (p) => typeof p === "string" && /^-\d+$/.test(p);

export class StrictAccessError extends RangeError {}

export function strict(target) {
  if (!Array.isArray(target) && !ArrayBuffer.isView(target)) {
    throw new TypeError("strict() takes an Array or a TypedArray");
  }
  return new Proxy(target, {
    get(t, p) {
      if (isIndex(p) && Number(p) >= t.length) {
        throw new StrictAccessError(`read [${p}] past end of length ${t.length}`);
      }
      if (isNegIndex(p)) throw new StrictAccessError(`read [${p}] on length ${t.length}`);
      const v = Reflect.get(t, p, t);
      if (typeof v !== "function") return v;
      if (p === "slice" || p === "subarray") {
        return (lo = 0, hi = t.length) => {
          if (lo < 0 || hi < 0) throw new StrictAccessError(`${p}(${lo}, ${hi}) with a negative bound`);
          if (hi > t.length && hi > lo) {
            throw new StrictAccessError(`${p}(${lo}, ${hi}) past end of length ${t.length}`);
          }
          return strict(v.call(t, lo, hi));
        };
      }
      if (p === "at") {
        return (i) => {
          if (i < 0 || i >= t.length) throw new StrictAccessError(`at(${i}) on length ${t.length}`);
          return v.call(t, i);
        };
      }
      return v.bind(t);
    },
    set(t, p, val) {
      if ((isIndex(p) && Number(p) >= t.length) || isNegIndex(p)) {
        throw new StrictAccessError(`write [${p}] outside length ${t.length}`);
      }
      return Reflect.set(t, p, val, t);
    },
  });
}
