def parse_record(b):
    """[nameLen u8][bodyLen u8][name][body][crc u16le] -> (name, body, crc)."""
    if len(b) < 2:
        return None
    n, m = b[0], b[1]
    if len(b) < 2 + n + m:              # bug: forgets the 2 crc bytes
        return None
    name = b[2:2 + n]
    body = b[2 + n:2 + n + m]
    crc = int.from_bytes(b[2 + n + m:2 + n + m + 2], 'little')
    return name, body, crc


def lz_decode(b):
    """Byte < 128 is a literal; byte >= 128 copies one byte from tok-127 back."""
    out = []
    for tok in b:
        if tok < 128:
            out.append(tok)
        else:
            dist = tok - 127
            if not out:
                raise ValueError('back-reference before any output')
            out.append(out[len(out) - dist])   # bug: no check dist <= len(out)
    return bytes(out)
