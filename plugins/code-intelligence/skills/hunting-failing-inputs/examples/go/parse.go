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
