#include <stdlib.h>
#include "resize.h"

Image *resize(const Image *src, int w, int h) {
    Image *dst = malloc(sizeof(Image));
    dst->w = w;
    dst->h = h;
    dst->px = malloc((size_t)w * h);
    for (int y = 0; y < h; y++) {
        for (int x = 0; x < w; x++) {
            int sx = x * src->w / w;
            int sy = y * src->h / h;
            dst->px[y * w + x] = src->px[sy * src->w + sx];
        }
    }
    return dst;
}
