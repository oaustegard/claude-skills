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
