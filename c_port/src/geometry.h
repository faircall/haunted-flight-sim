#ifndef HF_GEOMETRY_H
#define HF_GEOMETRY_H
#include <stddef.h>
typedef struct { double x, y; } HFPoint;
int hf_point_in_polygon(HFPoint point, const HFPoint *polygon, size_t count);
int hf_polygon_overlaps_rectangle(const HFPoint *polygon, size_t count,
                                  double x, double y, double width, double height);
#endif
