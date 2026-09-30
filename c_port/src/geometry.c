/* Inclusive lighting coverage tests. Preserve the Python double arithmetic,
 * edge tolerances and even degenerate-edge behavior for pixel parity. */
#include "geometry.h"
#include <math.h>

int hf_point_in_polygon(HFPoint p, const HFPoint *polygon, size_t count) {
    if (count < 3) return 0;
    int inside = 0;
    for (size_t i = 0; i < count; ++i) {
        HFPoint a = polygon[i], b = polygon[(i + 1) % count];
        double sx = b.x - a.x, sy = b.y - a.y;
        double px = p.x - a.x, py = p.y - a.y;
        double dot = px * sx + py * sy;
        if (fabs(sx * py - sy * px) <= .0001 &&
            dot >= -.0001 && dot <= sx * sx + sy * sy + .0001) return 1;
        if ((a.y > p.y) != (b.y > p.y)) {
            double edge_x = a.x + py * sx / sy;
            if (p.x < edge_x) inside = !inside;
        }
    }
    return inside;
}

static int segments_intersect(HFPoint a, HFPoint b, HFPoint c, HFPoint d) {
    double ax = b.x - a.x, ay = b.y - a.y;
    double bx = d.x - c.x, by = d.y - c.y;
    double ox = c.x - a.x, oy = c.y - a.y;
    double denominator = ax * by - ay * bx;
    if (fabs(denominator) <= .000001) return 0;
    double ta = (ox * by - oy * bx) / denominator;
    double tb = (ox * ay - oy * ax) / denominator;
    return ta >= -.000001 && ta <= 1.000001 && tb >= -.000001 && tb <= 1.000001;
}

int hf_polygon_overlaps_rectangle(const HFPoint *polygon, size_t count,
                                  double x, double y, double width, double height) {
    if (!count || width <= 0 || height <= 0) return 0;
    double right = x + width, bottom = y + height;
    HFPoint corners[4] = {{x, y}, {right, y}, {right, bottom}, {x, bottom}};
    for (size_t i = 0; i < count; ++i) {
        HFPoint p = polygon[i];
        if (p.x >= x && p.x <= right && p.y >= y && p.y <= bottom) return 1;
    }
    for (int j = 0; j < 4; ++j)
        if (hf_point_in_polygon(corners[j], polygon, count)) return 1;
    for (size_t i = 0; i < count; ++i)
        for (int j = 0; j < 4; ++j)
            if (segments_intersect(polygon[i], polygon[(i + 1) % count],
                                   corners[j], corners[(j + 1) % 4])) return 1;
    return 0;
}
