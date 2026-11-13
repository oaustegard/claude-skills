#include <stdint.h>
#include <stdlib.h>
#include <string.h>
int parse_frame(const uint8_t *b, size_t n, uint8_t *out);
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    uint8_t out[256];
    uint8_t *b = malloc(size ? size : 1);   /* exact-size copy: no slack for ASan to miss */
    memcpy(b, data, size);
    parse_frame(b, size, out);
    free(b);
    return 0;
}
