"""Native lighting geometry; only marshal at the game-container boundary."""
from libc.stdlib cimport malloc, free
from libc.stdint cimport SIZE_MAX
import numpy as np

cdef extern from "geometry.h":
    ctypedef struct HFPoint:
        double x
        double y
    int hf_point_in_polygon(HFPoint, const HFPoint *, size_t)
    int hf_polygon_overlaps_rectangle(const HFPoint *, size_t, double, double, double, double)

cdef HFPoint *pack_polygon(polygon) except NULL:
    cdef size_t count = len(polygon)
    cdef size_t index
    cdef dict point
    if count > SIZE_MAX // sizeof(HFPoint):
        raise MemoryError()
    cdef HFPoint *result = <HFPoint *>malloc(max(count, 1) * sizeof(HFPoint))
    if result == NULL:
        raise MemoryError()
    try:
        for index in range(count):
            point = polygon[index]
            result[index].x = point['x']
            result[index].y = point['y']
    except:
        free(result)
        raise
    return result

def points_in_polygon(points, polygon):
    cdef size_t count = len(polygon), length = len(points), index
    if count < 3:
        return np.zeros(length, dtype=bool)
    cdef HFPoint *vertices = pack_polygon(polygon)
    cdef HFPoint point
    cdef bytearray result = bytearray(length)
    cdef unsigned char[:] flags = result
    try:
        for index in range(length):
            point.x = points[index][0]
            point.y = points[index][1]
            flags[index] = hf_point_in_polygon(point, vertices, count)
    finally:
        free(vertices)
    return np.frombuffer(result, dtype=np.bool_)

def polygon_intersects_rectangle(polygon, dict rectangle):
    if not polygon or rectangle.get('width', 0.) <= 0 or rectangle.get('height', 0.) <= 0:
        return False
    cdef HFPoint *vertices = pack_polygon(polygon)
    try:
        return bool(hf_polygon_overlaps_rectangle(vertices, len(polygon), rectangle['x'], rectangle['y'],
                                                  rectangle['width'], rectangle['height']))
    finally:
        free(vertices)

def install():
    import g_graphics
    g_graphics.points_in_polygon = points_in_polygon
    g_graphics.polygon_intersects_rectangle = polygon_intersects_rectangle
