"""Bounded 3D fog volumes, independent of the existing puzzle cloud cards.

Each oriented region raymarches only its projected bounds and the interval in
front of scene depth. A small periodic 3D noise lattice lives in a 2D texture;
hardware interpolation keeps multiple moving octaves inexpensive. The layer
is premultiplied and is also rendered into the water's reflected view.
"""
from functools import lru_cache
from dataclasses import replace
from pathlib import Path
import math

import numpy as np
import pyray as pr

from g_huxin_canals_volumes import DEFAULT_VOLUME_SETTINGS, volume_frame_at

ROOT=Path(__file__).parent
QUALITY={'draft':(.5,24),'balanced':(.5,40),'high':(1.,56)}


def settling_water_regions(regions,profile,elapsed,state='canals'):
    """Move the authored low water banks with the lake veil, without edits.

    House/alley volumes retain their own positions and retreat paths. These
    stable water IDs refer to the lake banks in the existing target catalog.
    """
    from g_huxin_canals_water_fog import lake_fog_frame
    surface=getattr(profile,'surface_fog',None)
    if surface is None or not getattr(surface,'water_settle',False):return regions
    offset=lake_fog_frame(profile,elapsed,state).base_y-getattr(surface,'base_y',0.)
    if not offset:return regions
    return tuple(replace(region,center=(region.center[0],region.center[1]+offset,region.center[2]))
                 if region.id.startswith('volume-water-') else region for region in regions)


@lru_cache(maxsize=1)
def noise_lattice():
    """32 cubed RGB noise, eight slices across, with periodic XY gutters."""
    n=32;tile=n+2
    rng=np.random.default_rng(0xF063D)
    lattice=np.rint(rng.random((n,n,n,3))*255).astype(np.uint8)
    atlas=np.full((4*tile,8*tile,4),255,dtype=np.uint8)
    indices=np.arange(-1,n+1)%n
    for z in range(n):
        x,y=(z%8)*tile,(z//8)*tile
        atlas[y:y+tile,x:x+tile,:3]=lattice[z][indices[:,None],indices[None,:]]
    return atlas.tobytes(),8*tile,4*tile


def projected_bounds(region,cam,width,height,water_y=0.,reflected=False):
    """A conservative screen rectangle; camera-inside volumes use full view."""
    eye=np.array((cam.position.x,cam.position.y,cam.position.z))
    forward=np.array((cam.target.x,cam.target.y,cam.target.z))-eye
    forward/=np.linalg.norm(forward)
    right=np.cross(forward,(cam.up.x,cam.up.y,cam.up.z));right/=np.linalg.norm(right)
    up=np.cross(right,forward)
    angle=math.radians(region.yaw);c,s=math.cos(angle),math.sin(angle)
    hx,hy,hz=region.half_extents;cx,cy,cz=region.center
    corners=np.array([(cx+c*x-s*z,cy+y,cz+s*x+c*z)
                      for x in (-hx,hx) for y in (-hy,hy) for z in (-hz,hz)])
    if reflected:corners[:,1]=2*water_y-corners[:,1]
    delta=corners-eye;depth=delta@forward
    if np.max(depth)<=.01:return None
    if np.min(depth)<=.03:return (0,0,width,height)
    tangent=math.tan(math.radians(cam.fovy)*.5)
    x=(delta@right)/(depth*tangent*width/height)
    y=(delta@up)/(depth*tangent)
    x0=max(0,math.floor((float(x.min())*.5+.5)*width)-2)
    x1=min(width,math.ceil((float(x.max())*.5+.5)*width)+2)
    y0=max(0,math.floor((.5-float(y.max())*.5)*height)-2)
    y1=min(height,math.ceil((.5-float(y.min())*.5)*height)+2)
    return (x0,y0,x1-x0,y1-y0) if x1>x0 and y1>y0 else None


class FogVolumes:
    def __init__(self,width,height):
        self.width,self.height=width,height
        self.shader=self.noise=self.target=None
        self.last_regions=();self.last_draw_count=0;self.last_clock=0.
        self.last_reflected=False;self.last_water_y=0.;self.last_steps=0
        self.last_quality=None
        try:
            data,w,h=noise_lattice()
            pixels=pr.ffi.new('unsigned char[]',data)
            self.noise=pr.load_texture_from_image(pr.Image(pixels,w,h,1,pr.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8))
            pr.set_texture_filter(self.noise,pr.TEXTURE_FILTER_BILINEAR)
            pr.set_texture_wrap(self.noise,pr.TEXTURE_WRAP_CLAMP)
            self.shader=pr.load_shader(pr.ffi.NULL,str(ROOT/'shaders/huxin_canals_volumes.fs'))
            if self.shader.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Spatial fog shader compilation failed')
            names=('depthMap','noiseMap','resolution','eye','forward','right','up','lens','clip',
                   'fogColour','clock','waterY','reflectedView','center','halfSize','rotation',
                   'shape','density','edge','noiseSize','turbulence','wind','hollow','stepCount')
            self.locations={name:pr.get_shader_location(self.shader,name) for name in names}
            self.quality('balanced')
        except Exception:
            self.close();raise

    def quality(self,name):
        if name==self.last_quality:return
        fraction,self.last_steps=QUALITY[name]
        if self.target:pr.unload_render_texture(self.target)
        self.target=pr.load_render_texture(round(self.width*fraction),round(self.height*fraction))
        pr.set_texture_filter(self.target.texture,pr.TEXTURE_FILTER_BILINEAR)
        self.last_quality=name

    def uniform(self,name,value):
        values=value if isinstance(value,(tuple,list)) else (value,)
        kind={1:pr.SHADER_UNIFORM_FLOAT,2:pr.SHADER_UNIFORM_VEC2,3:pr.SHADER_UNIFORM_VEC3}[len(values)]
        pr.set_shader_value(self.shader,self.locations[name],pr.ffi.new('float[]',values),kind)

    def render(self,source,cam,sequence,clock,colour,water_y,reflected=False):
        settings=getattr(sequence.direction,'volumes',DEFAULT_VOLUME_SETTINGS)
        self.quality(settings.quality)
        active=sequence.state in ('entering','canals')
        regions=volume_frame_at(sequence.elapsed,clock,settings) if active else ()
        regions=settling_water_regions(regions,sequence.direction,sequence.elapsed,sequence.state)
        self.last_regions=regions;self.last_draw_count=0;self.last_clock=clock
        self.last_reflected=reflected;self.last_water_y=water_y
        w,h=self.target.texture.width,self.target.texture.height
        pr.begin_texture_mode(self.target);pr.clear_background(pr.BLANK)
        if not regions:
            pr.end_texture_mode();return self.target.texture
        forward=pr.vector3_normalize(pr.vector3_subtract(cam.target,cam.position))
        right=pr.vector3_normalize(pr.vector3_cross_product(forward,cam.up))
        up=pr.vector3_cross_product(right,forward)
        eye=(cam.position.x,cam.position.y,cam.position.z)
        axes=[eye,(forward.x,forward.y,forward.z),(right.x,right.y,right.z),(up.x,up.y,up.z)]
        if reflected:
            axes=[(eye[0],2*water_y-eye[1],eye[2])]+[(v[0],-v[1],v[2]) for v in axes[1:]]
        for name,value in zip(('eye','forward','right','up'),axes):self.uniform(name,value)
        self.uniform('resolution',(w,h))
        self.uniform('lens',(math.tan(math.radians(cam.fovy)*.5),self.width/self.height))
        self.uniform('clip',(pr.rl.rlGetCullDistanceNear(),pr.rl.rlGetCullDistanceFar()))
        self.uniform('fogColour',tuple(colour));self.uniform('clock',clock)
        self.uniform('waterY',water_y);self.uniform('reflectedView',float(reflected))
        self.uniform('stepCount',self.last_steps)
        # Independent volumes have the same base colour. Back-to-front region
        # blending preserves foreground wisps across separated architectural
        # spaces; density inside each region integrates front-to-back in 3D.
        def depth(region):return sum((v-e)*f for v,e,f in zip(region.center,axes[0],axes[1]))
        visible=[]
        for region in sorted(regions,key=depth,reverse=True):
            rectangle=projected_bounds(region,cam,w,h,water_y,reflected)
            if rectangle:visible.append((region,rectangle))
        pr.begin_shader_mode(self.shader)
        pr.rl_set_blend_factors_separate(pr.RL_ONE,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_ONE,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_FUNC_ADD,pr.RL_FUNC_ADD)
        pr.begin_blend_mode(pr.BLEND_CUSTOM_SEPARATE)
        for region,rectangle in visible:
            angle=math.radians(region.yaw)
            for name,value in (('center',region.center),('halfSize',region.half_extents),
                ('rotation',(math.cos(angle),math.sin(angle))),('shape',float(region.shape=='ellipsoid')),
                ('density',region.density),('edge',region.edge),('noiseSize',region.noise_size),
                ('turbulence',region.turbulence),('wind',region.wind),('hollow',region.hollow)):
                self.uniform(name,value)
            pr.set_shader_value_texture(self.shader,self.locations['depthMap'],source.depth)
            pr.set_shader_value_texture(self.shader,self.locations['noiseMap'],self.noise)
            pr.draw_rectangle(*rectangle,pr.WHITE)
            # Region uniforms differ; submit before binding the next region.
            pr.rl.rlDrawRenderBatchActive()
            self.last_draw_count+=1
        pr.end_blend_mode();pr.end_shader_mode();pr.end_texture_mode()
        return self.target.texture

    def close(self):
        if self.target:pr.unload_render_texture(self.target);self.target=None
        if self.noise:pr.unload_texture(self.noise);self.noise=None
        if self.shader:pr.unload_shader(self.shader);self.shader=None
