#ifndef HF_VISIBILITY_H
#define HF_VISIBILITY_H
#include <stdint.h>
#ifdef _WIN32
#define HF_EXPORT __declspec(dllexport)
#else
#define HF_EXPORT
#endif
typedef struct {
    int width, height;
    double tile_width, tile_height;
    const uint8_t *shapes;
} HFGrid;
typedef struct {
    double distance, normal_x, normal_y;
    int hit, tile_x, tile_y, tile_index, shape, edge, steps;
} HFHit;
HF_EXPORT HFHit hf_light_ray(const HFGrid *grid, double ox, double oy,
                            double dx, double dy, double distance);
#endif
