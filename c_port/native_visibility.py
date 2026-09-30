"""Optional Python reference harness for the independent C visibility kernel.

This is an integration benchmark, not the standalone C renderer. No existing
game files are modified. Native memory borrows the grid's persistent bytearray.
"""
import ctypes as c
from pathlib import Path

class Grid(c.Structure):
    _fields_=[('width',c.c_int),('height',c.c_int),('tile_width',c.c_double),
              ('tile_height',c.c_double),('shapes',c.POINTER(c.c_uint8))]

class Hit(c.Structure):
    _fields_=[('distance',c.c_double),('normal_x',c.c_double),('normal_y',c.c_double),
              ('hit',c.c_int),('tile_x',c.c_int),('tile_y',c.c_int),('tile_index',c.c_int),
              ('shape',c.c_int),('edge',c.c_int),('steps',c.c_int)]

_lib=None
def library():
    global _lib
    if _lib is None:
        _lib=c.CDLL(str(Path(__file__).parent/'build'/'hf_visibility.dll'))
        _lib.hf_light_ray.argtypes=[c.POINTER(Grid)]+[c.c_double]*5
        _lib.hf_light_ray.restype=Hit
    return _lib

def ray(ox,oy,dx,dy,distance,grid):
    cached=grid.get('_native_grid')
    shapes=grid['shape_codes']
    if cached is None or cached[0] is not shapes:
        data=(c.c_uint8*len(shapes)).from_buffer(shapes)
        value=Grid(grid['map_width'],grid['map_height'],grid['tile_width'],grid['tile_height'],data)
        cached=(shapes,data,value,c.byref(value));grid['_native_grid']=cached
    hit=library().hf_light_ray(cached[3],ox,oy,dx,dy,distance)
    values=(hit.distance,hit.tile_x,hit.tile_y,hit.tile_index,hit.shape,hit.edge,hit.normal_x,hit.normal_y) if hit.hit else None
    return values,hit.steps

def install():
    import g_light_visibility
    library()
    g_light_visibility.dda_first_light_hit_values=ray

if __name__=='__main__':
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    install()
    if '--water-benchmark' in sys.argv:
        import benchmark_water
        benchmark_water.run()
    else:
        import moonlit_water_temple
        moonlit_water_temple.run()
