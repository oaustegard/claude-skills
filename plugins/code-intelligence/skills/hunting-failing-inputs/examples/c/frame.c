#include <stdint.h>
#include <string.h>
#include <stddef.h>

/* [hdrLen u8][bodyLen u8][hdr][body]. Copies body into out (256 bytes). */
int parse_frame(const uint8_t *b, size_t n, uint8_t *out) {
    if (n < 2) return -1;
    uint8_t hdr = b[0], body = b[1];
    uint8_t total = hdr + body;            /* bug: wraps at 256 */
    if ((size_t)total + 2 > n) return -1;
    memcpy(out, b + 2 + hdr, body);
    return body;
}
