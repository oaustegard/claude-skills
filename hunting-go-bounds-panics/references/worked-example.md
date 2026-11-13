# Worked example: two planted bugs, end to end

Reference only. Every block below ran on 2026-11-13 (go1.24.7 linux/amd64,
z3-solver 4.x via pip) and produced the output shown. Copy the shape, not the
constants.

## The target

```go
package bcedemo

// ParseTwoChunkFrame: [hdrLen u8][bodyLen u8][hdr...][body...]
// Bug: hdrLen+bodyLen computed in uint8 wraps before the guard.
func ParseTwoChunkFrame(b []byte) (hdr, body []byte, ok bool) {
	if len(b) < 2 {
		return nil, nil, false
	}
	hdrLen, bodyLen := b[0], b[1]
	total := hdrLen + bodyLen // uint8: wraps at 256
	if int(total)+2 > len(b) {
		return nil, nil, false
	}
	hdr = b[2 : 2+int(hdrLen)]
	endBody := 2 + int(hdrLen) + int(bodyLen)
	body = b[2+int(hdrLen) : endBody]
	return hdr, body, true
}

// ExtractQuotedToken returns the contents of a leading "..." token.
// Bug: a trailing backslash skips past len(s).
func ExtractQuotedToken(s []byte) []byte {
	if len(s) == 0 || s[0] != '"' {
		return nil
	}
	i := 1
	for i < len(s) && s[i] != '"' {
		if s[i] == '\\' {
			i++ // skip escaped char
		}
		i++
	}
	return s[1:i]
}
```

## Step 1: surviving checks

```
$ python3 scripts/bce_targets.py .
./parse.go:14:9	slice	ParseTwoChunkFrame	hdr = b[2 : 2+int(hdrLen)]
./parse.go:16:10	slice	ParseTwoChunkFrame	body = b[2+int(hdrLen) : endBody]
./parse.go:27:21	index	ExtractQuotedToken	for i < len(s) && s[i] != '"' {
./parse.go:33:10	slice	ExtractQuotedToken	return s[1:i]
# 4 surviving bounds check(s)
```

The same four checks survive under `--goarch riscv64`. Line 27 is guarded by
`i < len(s)` in the same condition; the prove pass does not use it because `i`
steps by 2.

## Step 2: the frame model (straight-line, so `in_order=True`)

```python
import sys; sys.path.insert(0, 'SKILL_DIR/scripts')
from z3go import *

n, base = harness(max_len=64)
b0, b1 = byte_at('b0'), byte_at('b1')        # hdrLen, bodyLen (uint8)
base += [n >= 2]                              # passed: if len(b) < 2 { return }
total = b0 + b1                               # uint8 + uint8: wraps at 256
base += [Not(to_int(total) + 2 > n)]          # passed: if int(total)+2 > len(b) { return }
h, bl = to_int(b0), to_int(b1)
end = 2 + h + bl                              # computed in int: does not wrap
solve_traps(base, {
    'parse.go:14 b[2:2+hdrLen]':      slice_oob(BitVecVal(2, 64), 2 + h, n),
    'parse.go:16 b[2+hdrLen:endBody]': slice_oob(2 + h, end, n),
}, show=(n, b0, b1), in_order=True)
```

```
parse.go:14 b[2:2+hdrLen]: sat
    len = 64
    b0 = 126
    b1 = 192
parse.go:16 b[2+hdrLen:endBody]: sat
    len = 62
    b0 = 49
    b1 = 238
```

Trap 16's input passes trap 14 (2+49 = 51 ≤ 62) and dies at 16: `total` wraps
to 31, so the guard admits it, while `endBody` is computed in `int` and reaches
289.

Fix the guard (`total := int(hdrLen) + int(bodyLen)`), change the model to
match, and both traps go `unsat`.

## Step 3: the loop model (bounded unroll per length)

```python
import sys; sys.path.insert(0, 'SKILL_DIR/scripts')
from z3go import *

# The loop advances i by 1 or 2, so unroll it per concrete length L.
for L in range(1, 17):
    s = [byte_at(f's{k}') for k in range(L)]
    i, live = BitVecVal(1, 64), BoolVal(True)
    idx_traps = []
    for _ in range(L + 1):                    # at most L iterations
        enter = And(live, i < L)
        idx_traps.append(And(live, i < L, index_oob(i, L)))   # s[i] in the loop condition
        cur = BitVecVal(0, 8)
        for k in range(L):
            cur = If(i == k, s[k], cur)
        cont = And(enter, cur != ord('"'))
        i = If(cont, i + If(cur == ord('\\'), BitVecVal(2, 64), BitVecVal(1, 64)), i)
        live = cont
    base = [s[0] == ord('"')]                 # passed: s[0] != '"' returns nil
    r = solve_traps(base, {
        f'L={L} parse.go:27 s[i]':   Or(*idx_traps),
        f'L={L} parse.go:33 s[1:i]': slice_oob(BitVecVal(1, 64), i, BitVecVal(L, 64)),
    })
    m = r[f'L={L} parse.go:33 s[1:i]']
    if m:
        print('reproducer:', go_literal(concrete_bytes(m, s)))
        break
```

```
L=1 parse.go:27 s[i]: unsat
L=1 parse.go:33 s[1:i]: unsat
L=2 parse.go:27 s[i]: unsat
L=2 parse.go:33 s[1:i]: sat
reproducer: []byte{0x22, 0x5c}
```

Line 27 stays `unsat` at every length: the check survives but cannot fire.

## Step 4: reproducers

```go
package bcedemo

import "testing"

// fresh copies b into a slice with cap == len, the harness every model assumes.
func fresh(b []byte) []byte { return append([]byte(nil), b...)[:len(b):len(b)] }

// One test per sat trap. No recover: the panic trace names the line that fired.
func TestZ3_parse14(t *testing.T) {
	b := make([]byte, 64)
	b[0], b[1] = 126, 192
	ParseTwoChunkFrame(fresh(b))
}

func TestZ3_parse16(t *testing.T) {
	b := make([]byte, 62)
	b[0], b[1] = 49, 238
	ParseTwoChunkFrame(fresh(b))
}

func TestZ3_parse33(t *testing.T) {
	ExtractQuotedToken(fresh([]byte{0x22, 0x5c}))
}
```

Each test panics at the line its trap names:

```
TestZ3_parse14  slice bounds out of range [:128] with capacity 64   parse.go:14
TestZ3_parse16  slice bounds out of range [:289] with capacity 62   parse.go:16
TestZ3_parse33  slice bounds out of range [:3] with capacity 2      parse.go:33
```

## Step 5: the fuzz harness

Unseeded `go test -fuzz`, 30 s each, `-parallel 4`, fresh cache:

| target | harness | result |
|---|---|---|
| ParseTwoChunkFrame | `f.Fuzz(func(t *testing.T, d []byte) { F(d) })` | not found |
| ParseTwoChunkFrame | same, plus `d = d[:len(d):len(d)]` | found in under 1 s |
| ExtractQuotedToken | plain | not found |
| ExtractQuotedToken | plus `d = d[:len(d):len(d)]` | found in under 1 s |

The fuzzer generated crashing inputs all along. Its input slices carry spare
capacity, so `b[x:y]` with `len < y <= cap` succeeds silently and returns bytes
past the end of the input.
