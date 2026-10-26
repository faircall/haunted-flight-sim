"""Localized architectural mist for the moon teahouse encounter.

This optional renderer is independent of the canals experiment. It returns a
premultiplied fog texture for the existing moon post pass, using one canonical
world volume for direct sight and the water reflection.
"""
from functools import lru_cache
from pathlib import Path
import math

import numpy as np
import pyray as pr

ROOT=Path(__file__).resolve().parent
MAX_REGIONS=24


@lru_cache(maxsize=1)
def noise_lattice():
    """Small repeatable 3D lattice with wrapped XY gutters on every Z tile."""
    rng=np.random.default_rng(17593)
    field=rng.integers(0,256,(32,32,32,4),dtype=np.uint8)
    image=np.empty((136,272,4),dtype=np.uint8)
    for z in range(32):
        tile=np.pad(field[z],((1,1),(1,1),(0,0)),mode='wrap')
        y,x=(z//8)*34,(z%8)*34
        image[y:y+34,x:x+34]=tile
    return image.tobytes(),272,136


def bank_shape(region):
    """Broader clouds for large banks; tiny ceiling/lamp masks stay precise."""
    broad=region.role in ('wall','stair','annex','roof','balcony')
    width=max(region.edge*2.,region.noise_size*(1. if region.role=='roof' else .85)) if broad else 0.
    shape=1. if region.id=='main-roof' else 2. if region.id=='annex-roof' else 0.
    bottom=region.center[1]-region.half_extents[1]
    guard,feather=(bottom-.85,.45) if shape==1. else (-1000.,.1)
    return width,guard,feather,shape


def region_rows(regions):
    if len(regions)>MAX_REGIONS:raise ValueError(f'Moon fog supports at most {MAX_REGIONS} regions.')
    rows=np.zeros((4,MAX_REGIONS,4),dtype=np.float32)
    for i,region in enumerate(regions):
        rows[0,i]=(*region.center,region.density)
        rows[1,i]=(*region.half_extents,region.edge)
        rows[2,i]=(*region.wind,region.noise_size)
        rows[3,i]=bank_shape(region)
    if not np.isfinite(rows).all():raise ValueError('Moon fog region data must be finite.')
    return rows


class MoonTargetFog:
    def __init__(self,width,height):
        self.width,self.height=width,height
        # Fog and source depth share pixel centers. Upsampling a coarse mask
        # leaks changing geometry around the unchanged slender timber posts.
        self.render_width=width;self.render_height=height
        self.shader=self.noise=self.target=None
        self.locations={}
        self.last_active=False;self.last_frame=None;self.last_rows=None
        self.last_reflected=False;self.last_clock=0.

    def prepare(self):
        if self.shader is not None:return
        from g_huxin_moon_fog import MOON_FOG_REGIONS
        region_rows(MOON_FOG_REGIONS)
        # Bounds never change as targets fade: changing background geometry
        # or staged region opacity cannot move the ray's quadrature origin.
        padding=[max(r.edge*2.5,bank_shape(r)[0]*2.3+r.edge) for r in MOON_FOG_REGIONS]
        low=np.min([np.asarray(r.center)-np.asarray(r.half_extents)-pad for r,pad in zip(MOON_FOG_REGIONS,padding)],axis=0)
        high=np.max([np.asarray(r.center)+np.asarray(r.half_extents)+pad for r,pad in zip(MOON_FOG_REGIONS,padding)],axis=0)
        try:
            data,w,h=noise_lattice()
            pixels=pr.ffi.new('unsigned char[]',data)
            self.noise=pr.load_texture_from_image(pr.Image(pixels,w,h,1,pr.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8))
            pr.set_texture_filter(self.noise,pr.TEXTURE_FILTER_BILINEAR)
            pr.set_texture_wrap(self.noise,pr.TEXTURE_WRAP_CLAMP)
            self.shader=pr.load_shader(pr.ffi.NULL,str(ROOT/'shaders/huxin_moon_target_fog.fs'))
            if self.shader.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Moon target fog shader compilation failed')
            names=('depthMap','noiseMap','resolution','lens','clip','eye','forward','right','up',
                   'fogColour','clock','reflectedView','playerCenter','build','depthHold',
                   'boundsLow','boundsHigh','regionCount','regionCenters','regionHalves','regionFlow','regionBanks')
            self.locations={name:pr.get_shader_location(self.shader,name) for name in names}
            self.uniform('boundsLow',tuple(map(float,low)));self.uniform('boundsHigh',tuple(map(float,high)))
            self.target=pr.load_render_texture(self.render_width,self.render_height)
            pr.set_texture_filter(self.target.texture,pr.TEXTURE_FILTER_BILINEAR)
        except Exception:self.close();raise

    def uniform(self,name,value):
        values=value if isinstance(value,(tuple,list)) else (value,)
        kind={1:pr.SHADER_UNIFORM_FLOAT,2:pr.SHADER_UNIFORM_VEC2,3:pr.SHADER_UNIFORM_VEC3}[len(values)]
        pr.set_shader_value(self.shader,self.locations[name],pr.ffi.new('float[]',values),kind)

    def render(self,source,cam,sequence,clock,colour,reflected=False,player_center=None):
        from g_huxin_moon_fog import moon_fog_frame
        frame=moon_fog_frame(sequence)
        self.last_frame=frame;self.last_clock=clock;self.last_reflected=reflected
        self.last_active=frame.strength>1.e-7 and any(r.density>1.e-7 for r in frame.regions)
        if not self.last_active:return None
        self.prepare()
        rows=region_rows(frame.regions);self.last_rows=rows
        pr.set_shader_value(self.shader,self.locations['regionCount'],pr.ffi.new('int[]',[len(frame.regions)]),pr.SHADER_UNIFORM_INT)
        for name,row in zip(('regionCenters','regionHalves','regionFlow','regionBanks'),rows):
            pr.set_shader_value_v(self.shader,self.locations[name],pr.ffi.cast('void *',pr.ffi.from_buffer(row)),pr.SHADER_UNIFORM_VEC4,MAX_REGIONS)
        forward=pr.vector3_normalize(pr.vector3_subtract(cam.target,cam.position))
        right=pr.vector3_normalize(pr.vector3_cross_product(forward,cam.up))
        up=pr.vector3_cross_product(right,forward)
        axes=[(cam.position.x,cam.position.y,cam.position.z),
              (forward.x,forward.y,forward.z),(right.x,right.y,right.z),(up.x,up.y,up.z)]
        if reflected:axes=[(v[0],-v[1],v[2]) for v in axes]
        for name,value in zip(('eye','forward','right','up'),axes):self.uniform(name,value)
        center=(0.,1.3,0.) if player_center is None else tuple(player_center)
        for name,value in (('resolution',(self.render_width,self.render_height)),
            ('lens',(math.tan(math.radians(cam.fovy)*.5),self.width/self.height)),
            ('clip',(pr.rl.rlGetCullDistanceNear(),pr.rl.rlGetCullDistanceFar())),
            ('fogColour',tuple(colour)),('clock',clock),('reflectedView',float(reflected)),
            ('playerCenter',center),('build',frame.build),('depthHold',frame.depth_hold)):
            self.uniform(name,value)
        pr.begin_texture_mode(self.target);pr.clear_background(pr.BLANK)
        pr.rl_set_blend_factors_separate(pr.RL_ONE,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_ONE,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_FUNC_ADD,pr.RL_FUNC_ADD)
        pr.begin_blend_mode(pr.BLEND_CUSTOM_SEPARATE);pr.begin_shader_mode(self.shader)
        pr.set_shader_value_texture(self.shader,self.locations['depthMap'],source.depth)
        pr.set_shader_value_texture(self.shader,self.locations['noiseMap'],self.noise)
        pr.draw_rectangle(0,0,self.render_width,self.render_height,pr.WHITE)
        pr.end_shader_mode();pr.end_blend_mode();pr.end_texture_mode()
        return self.target.texture

    def close(self):
        if self.target:pr.unload_render_texture(self.target);self.target=None
        if self.noise:pr.unload_texture(self.noise);self.noise=None
        if self.shader:pr.unload_shader(self.shader);self.shader=None
