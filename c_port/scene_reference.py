"""Offline/test adapter for the standalone C scene kernels (not a game runtime)."""
import ctypes as C
from pathlib import Path

class Point(C.Structure):
    _fields_=[('x',C.c_double),('y',C.c_double)]
class Arena(C.Structure):
    _fields_=[('base',C.c_void_p),('capacity',C.c_size_t),('used',C.c_size_t),('peak',C.c_size_t),
              ('pushes',C.c_uint64),('failures',C.c_uint64),('generation',C.c_uint64),('name',C.c_char_p)]
class Memory(C.Structure):
    _fields_=[('base',C.c_void_p),('size',C.c_size_t),('persistent',Arena),('assets',Arena),('frame',Arena)]
class Grid(C.Structure):
    _fields_=[('width',C.c_int),('height',C.c_int),('tile_width',C.c_double),('tile_height',C.c_double),('shapes',C.POINTER(C.c_ubyte))]
class Range(C.Structure):
    _fields_=[('first',C.c_uint32),('count',C.c_uint32)]
class Geometry(C.Structure):
    _fields_=[('grid',Grid),('vertices',C.POINTER(Point)),('vertex_count',C.c_uint32),
              ('buckets',C.POINTER(Range)),('bucket_vertices',C.POINTER(C.c_uint32)),
              ('buckets_x',C.c_uint32),('buckets_y',C.c_uint32),('bucket_width',C.c_double),('bucket_height',C.c_double)]
class Light(C.Structure):
    _fields_=[('position',Point),('direction',Point),('radius',C.c_double),('outer_angle',C.c_double),
              ('shadow_bias',C.c_double),('corner_epsilon',C.c_double),('spot',C.c_uint32),('ray_count',C.c_uint32),
              ('max_rays',C.c_uint32),('corner_rays',C.c_uint32),('corner_limit',C.c_uint32)]
class Visibility(C.Structure):
    _fields_=[('angles',C.POINTER(C.c_double)),('polygon',C.POINTER(Point)),('unbiased',C.POINTER(Point)),
              ('hit_tiles',C.POINTER(C.c_int32)),('count',C.c_uint32),('hit_count',C.c_uint32),
              ('baseline_count',C.c_uint32),('corner_count',C.c_uint32),('adaptive_count',C.c_uint32),
              ('tile_steps',C.c_uint32),('max_tile_steps',C.c_uint32)]
class Wind(C.Structure):
    _fields_=[('direction',Point),('strength',C.c_double),('gust_strength',C.c_double),('gust_speed',C.c_double),
              ('spatial_scale',C.c_double),('vertical_flutter',C.c_double),('seed',C.c_int32),('irregular',C.c_uint32)]
class Part(C.Structure):
    _fields_=[('pivot',Point),('bottom',C.c_double),('stiffness',C.c_double),('phase',C.c_double),
              ('exposure',C.c_double),('lag',C.c_double),('response',C.c_double),('flutter',C.c_double),('bend_gain',C.c_double)]
class Pose(C.Structure):
    _fields_=[('angle',C.c_double),('bend',C.c_double),('deformation',C.c_float*16)]

def point(value):
    return Point(value.get('x',0.),value.get('y',0.)) if isinstance(value,dict) else Point(*value)

def light_data(light,position,config=None):
    import g_light_visibility as lv
    settings=lv.visibility_config_for_light(light,config)
    return Light(point(position),point(light.get('direction',dict(x=1.,y=0.))),
                 max(0.,light.get('visibility_radius',light.get('radius',100.))),light.get('outer_angle',35.),
                 max(0.,light.get('shadow_bias',.25)),settings['corner_epsilon'],
                 int(lv.visibility_type(light)=='spot'),settings['ray_count'],settings['max_rays'],
                 int(settings['corner_rays']),settings['corner_candidate_limit'])

def wind_data(w):
    return Wind(point(w.get('direction',dict(x=1.,y=0.))),w.get('strength',8.),w.get('gust_strength',5.),
                w.get('gust_speed',.35),w.get('spatial_scale',.015),w.get('vertical_flutter',0.),
                w.get('tree_seed',17),int(w.get('tree_irregular',True)))

def part_data(p):
    return Part(point(p['pivot']),p['bounds'][3],*(p[k] for k in
                ('stiffness','phase','exposure','lag','response','flutter','bend_gain')))

class PackedGeometry:
    def __init__(self,grid):
        self.shapes=(C.c_ubyte*len(grid['shape_codes'])).from_buffer_copy(grid['shape_codes'])
        self.vertices=(Point*len(grid['boundary_vertices']))(*(point(p) for p in grid['boundary_vertices']))
        ranges=[];indices=[]
        for i in range(grid['bucket_count_x']*grid['bucket_count_y']):
            group=grid['boundary_vertex_buckets'].get(i,())
            ranges.append(Range(len(indices),len(group)));indices.extend(group)
        self.buckets=(Range*len(ranges))(*ranges)
        self.indices=(C.c_uint32*len(indices))(*indices)
        self.value=Geometry(Grid(grid['map_width'],grid['map_height'],grid['tile_width'],grid['tile_height'],self.shapes),
                            self.vertices,len(self.vertices),self.buckets,self.indices,grid['bucket_count_x'],grid['bucket_count_y'],
                            grid['bucket_world_width'],grid['bucket_world_height'])

class Kernels:
    def __init__(self):
        self.lib=C.CDLL(str(Path(__file__).resolve().parent/'build/hf_scene.dll'))
        for name,args,result in (
            ('hf_memory_init',[C.POINTER(Memory),C.c_size_t,C.c_size_t,C.c_size_t],C.c_int),
            ('hf_memory_destroy',[C.POINTER(Memory)],None),
            ('hf_arena_reset',[C.POINTER(Arena)],None),
            ('hf_build_visibility',[C.POINTER(Geometry),C.POINTER(Light),C.POINTER(Arena),C.POINTER(Visibility)],C.c_int),
            ('hf_tree_pose',[C.POINTER(Part),C.POINTER(Wind),Point,C.c_double,C.c_int,C.POINTER(Pose)],None),
        ):
            f=getattr(self.lib,name);f.argtypes=args;f.restype=result
        self.memory=Memory()
        if not self.lib.hf_memory_init(C.byref(self.memory),2*1048576,4*1048576,8*1048576):
            raise MemoryError('native arenas')
    def close(self):
        self.lib.hf_memory_destroy(C.byref(self.memory))
    def visibility(self,geometry,light):
        self.lib.hf_arena_reset(C.byref(self.memory.frame));out=Visibility()
        if not self.lib.hf_build_visibility(C.byref(geometry.value),C.byref(light),C.byref(self.memory.frame),C.byref(out)):
            raise RuntimeError('native visibility capacity exceeded')
        return out
    def pose(self,part,wind,world,time,strips=False):
        out=Pose()
        self.lib.hf_tree_pose(C.byref(part),C.byref(wind),point(world),time,int(strips),C.byref(out))
        return out
