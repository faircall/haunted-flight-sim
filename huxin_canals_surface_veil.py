"""A low, opaque-in-depth mist layer over the original lake surface.

The water changes height behind this layer. Its datum and ray samples never
follow that change; the unchanged pavilion and causeway stay out of its volume.
It is optional and composites over an existing premultiplied fog texture.
"""
from dataclasses import dataclass
from pathlib import Path
import math

import pyray as pr

from g_huxin_canals_surface_settings import DEFAULT_SURFACE_SETTINGS,surface_blend_window

ROOT=Path(__file__).resolve().parent


def _ease(a,b,value):
    t=max(0.,min(1.,(value-a)/max(.001,b-a)))
    return max(0.,min(1.,t*t*t*(10.+t*(-15.+6.*t))))


@dataclass(frozen=True,slots=True)
class VeilFrame:
    strength: float
    base_y: float
    building: float
    clearing: float

    @property
    def active(self):return self.strength>1.e-7


def veil_frame(profile,elapsed,state='canals'):
    """The fallback window holds the surface until the hidden blend is over.

    Strength has a gentle early ramp rather than becoming opaque immediately.
    Water height is intentionally not an input: base_y is the original datum.
    """
    settings=getattr(profile,'surface_fog',DEFAULT_SURFACE_SETTINGS)
    base=float(getattr(settings,'base_y',0.))
    if not (settings.enabled and getattr(settings,'water_mask',False) and settings.amount>0.
            and state in ('entering','canals')):
        return VeilFrame(0.,base,0.,0.)
    build=_ease(settings.build_start,settings.build_end,float(elapsed))
    clear_start=max(settings.reveal_start,surface_blend_window(profile)[1])
    clear_end=max(clear_start+.1,settings.reveal_end)
    clear=_ease(clear_start,clear_end,float(elapsed))
    strength=float(settings.amount)*build**2.2*(1.-clear)**2.2
    return VeilFrame(strength,base,build,clear)


def shared_causeway_points():
    """Six samples of the real curved, shared path, ordered toward shore."""
    from g_huxin_canals import PATH
    result=[]
    for z in (4.,5.6,7.2,8.8,10.4,12.):
        for a,b in zip(PATH,PATH[1:]):
            if min(a[1],b[1])<=z<=max(a[1],b[1]) and abs(a[1]-b[1])>1.e-8:
                t=(z-a[1])/(b[1]-a[1])
                result.append((a[0]+(b[0]-a[0])*t,z));break
        else:raise ValueError(f'Shared causeway has no point at z={z:g}.')
    return tuple(result)


class LakeSurfaceVeil:
    def __init__(self,width,height):
        self.width,self.height=width,height
        self.shader=self.noise=self.target=None
        self.locations={}
        self.last_active=False;self.last_clock=0.;self.last_elapsed=0.
        self.last_water_y=0.;self.last_reflected=False
        self.last_frame=VeilFrame(0.,0.,0.,0.)

    def prepare(self):
        if self.shader is not None:return
        try:
            from huxin_canals_surface_fog import surface_noise_lattice
            data,w,h=surface_noise_lattice()
            pixels=pr.ffi.new('unsigned char[]',data)
            self.noise=pr.load_texture_from_image(pr.Image(pixels,w,h,1,pr.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8))
            pr.set_texture_filter(self.noise,pr.TEXTURE_FILTER_BILINEAR)
            pr.set_texture_wrap(self.noise,pr.TEXTURE_WRAP_CLAMP)
            self.shader=pr.load_shader(pr.ffi.NULL,str(ROOT/'shaders/huxin_canals_surface_veil.fs'))
            if self.shader.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Lake surface veil shader compilation failed')
            names=('depthMap','noiseMap','resolution','lens','clip','eye','forward','right','up',
                   'fogColour','clock','waterY','reflectedView','baseY','strength','textureGrit','causeway',
                   'wispyFormation')
            self.locations={name:pr.get_shader_location(self.shader,name) for name in names}
            points=shared_causeway_points()
            pr.set_shader_value_v(self.shader,self.locations['causeway'],
                pr.ffi.new('float[]',[value for point in points for value in point]),pr.SHADER_UNIFORM_VEC2,len(points))
            self.target=pr.load_render_texture(self.width,self.height)
            pr.set_texture_filter(self.target.texture,pr.TEXTURE_FILTER_BILINEAR)
        except Exception:self.close();raise

    def uniform(self,name,value):
        values=value if isinstance(value,(tuple,list)) else (value,)
        kind={1:pr.SHADER_UNIFORM_FLOAT,2:pr.SHADER_UNIFORM_VEC2,3:pr.SHADER_UNIFORM_VEC3}[len(values)]
        pr.set_shader_value(self.shader,self.locations[name],pr.ffi.new('float[]',values),kind)

    def render(self,source,cam,sequence,clock,colour,water_y,reflected=False,base_texture=None):
        frame=veil_frame(sequence.direction,sequence.elapsed,sequence.state)
        self.last_frame=frame;self.last_active=frame.active
        self.last_clock=clock;self.last_elapsed=sequence.elapsed
        self.last_water_y=water_y;self.last_reflected=reflected
        # Exact identity for old profiles, finished reveals and disabled masks.
        # An inactive renderer has no GPU work or additional render targets.
        if not frame.active:return base_texture
        self.prepare()
        forward=pr.vector3_normalize(pr.vector3_subtract(cam.target,cam.position))
        right=pr.vector3_normalize(pr.vector3_cross_product(forward,cam.up))
        up=pr.vector3_cross_product(right,forward)
        eye=(cam.position.x,cam.position.y,cam.position.z)
        axes=[eye,(forward.x,forward.y,forward.z),(right.x,right.y,right.z),(up.x,up.y,up.z)]
        if reflected:axes=[(eye[0],2*water_y-eye[1],eye[2])]+[(v[0],-v[1],v[2]) for v in axes[1:]]
        for name,value in zip(('eye','forward','right','up'),axes):self.uniform(name,value)
        for name,value in (('resolution',(self.width,self.height)),
            ('lens',(math.tan(math.radians(cam.fovy)*.5),self.width/self.height)),
            ('clip',(pr.rl.rlGetCullDistanceNear(),pr.rl.rlGetCullDistanceFar())),
            ('fogColour',tuple(colour)),('clock',clock),('waterY',water_y),
            ('reflectedView',float(reflected)),('baseY',frame.base_y),('strength',frame.strength),
            ('wispyFormation',float(getattr(sequence.direction.surface_fog,'wispy_formation',False))),
            ('textureGrit',float(getattr(sequence.direction.surface_fog,'texture_grit',.65)))):
            self.uniform(name,value)
        pr.begin_texture_mode(self.target);pr.clear_background(pr.BLANK)
        pr.rl_set_blend_factors_separate(pr.RL_ONE,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_ONE,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_FUNC_ADD,pr.RL_FUNC_ADD)
        pr.begin_blend_mode(pr.BLEND_CUSTOM_SEPARATE)
        if base_texture is not None:
            pr.draw_texture_pro(base_texture,pr.Rectangle(0,0,base_texture.width,-base_texture.height),
                pr.Rectangle(0,0,self.width,self.height),pr.Vector2(0,0),0,pr.WHITE)
        pr.begin_shader_mode(self.shader)
        pr.set_shader_value_texture(self.shader,self.locations['depthMap'],source.depth)
        pr.set_shader_value_texture(self.shader,self.locations['noiseMap'],self.noise)
        pr.draw_rectangle(0,0,self.width,self.height,pr.WHITE)
        pr.end_shader_mode();pr.end_blend_mode();pr.end_texture_mode()
        return self.target.texture

    def close(self):
        if self.target:pr.unload_render_texture(self.target);self.target=None
        if self.noise:pr.unload_texture(self.noise);self.noise=None
        if self.shader:pr.unload_shader(self.shader);self.shader=None
