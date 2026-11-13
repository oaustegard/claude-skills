import { test } from "node:test";
import assert from "node:assert/strict";
import { strict, StrictAccessError } from "../../scripts/strict.mjs";
import { decodeSamples } from "./samples.mjs";

const input = (len, ...head) => { const u = new Uint8Array(len); u.set(head); return u; };

test("z3: u8[p + 1] past end (count=62, stride=1, len=64)", () => {
  const u = input(64, 62, 1);
  assert.equal(decodeSamples(u).length, 62);              // plain: no error, last sample wrong
  assert.throws(() => decodeSamples(strict(u)), StrictAccessError);
});

test("z3: u8[p] past end (count=95, stride=0, len=2)", () => {
  assert.throws(() => decodeSamples(strict(input(2, 95, 0))), StrictAccessError);
});
