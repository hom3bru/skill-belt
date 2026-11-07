#ifndef RESIZE_H
#define RESIZE_H

typedef struct {
    int w, h;
    unsigned char *px;
} Image;

Image *resize(const Image *src, int w, int h);

#endif
