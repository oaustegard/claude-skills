#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int parse_frame(const uint8_t *b, size_t n, uint8_t *out);
int main(void) {
    size_t n = 64;                          /* from the model: len=64, hdr=127, body=191 */
    uint8_t *b = calloc(n, 1);              /* exact size */
    b[0] = 127; b[1] = 191;
    uint8_t out[256];
    printf("parse_frame -> %d\n", parse_frame(b, n, out));
    free(b);
    return 0;
}
