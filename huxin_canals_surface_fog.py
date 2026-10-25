"""Raymarched, mesh-derived fog with three-dimensional formation and erosion."""
from pathlib import Path
import math
import numpy as np
import pyray as pr

from g_huxin_canals_surface_settings import DEFAULT_SURFACE_SETTINGS,surface_blend_window
from huxin_canals_volumes import noise_lattice

ROOT=Path(__file__).parent
FIELD_PATH=ROOT/'art/temple/huxin_canals/surface_fog.npz'
# Geometry concealment needs one fog ray per scene pixel: upsampling a missing
# depth sample exposes thin roof/window edges. Quality changes raymarch budget.
QUALITY={'draft':(1.,112),'balanced':(1.,176),'high':(1.,256)}


def surface_noise_lattice():
    """Keep the 3D RGB lattice; reuse a coarse cloud tile in spare alpha.

    This borrows the original card fog's six-tone painted texture without an
    extra sampler or camera-facing geometry. Older shaders only sample RGB.
    """
    from g_huxin_canals_particles import build_particle_atlas
    data,width,height=noise_lattice()
    pixels=np.frombuffer(data,np.uint8).reshape(height,width,4).copy()
    cards,cw,ch=build_particle_atlas()
    cards=np.frombuffer(cards,np.uint8).reshape(ch,cw,4)
    size=cw//4
    paint=cards[:size,size:2*size,0]
    iy=np.minimum(size-1,np.arange(height)*size//height)
    ix=np.minimum(size-1,np.arange(width)*size//width)
    pixels[:,:,3]=paint[iy[:,None],ix[None,:]]
    return pixels.tobytes(),width,height


def timing_rows(profile,owners):
    """Stable baked owner labels point at the existing named building timings."""
    if len(owners)>255:raise ValueError('Surface fog timing table supports at most 255 named owners.')
    settings=profile.surface_fog
    safe_start=surface_blend_window(profile)[1]
    rows=np.zeros((256,4),np.float32)
    rows[:,0]=max(settings.reveal_start,safe_start)
    rows[:,1]=max(settings.reveal_end,float(rows[0,0])+.1)
    groups={group.id:group for group in profile.groups}
    if settings.use_building_timing:
        for index,identity in enumerate(owners,1):
            group=groups.get(identity)
            if group:
                start=max(safe_start,group.reveal_start)
                rows[index,:2]=(start,max(start+.1,group.reveal_end))
    return rows


def owner_rows(profile,owners,targets=None):
    """Three texture rows: reveal window, actual roof bounds, XZ half-size.

    The target catalog pads architectural bounds for old cloud banks. Remove
    that padding here so the rising field converges on real building geometry.
    Generic/unrecognized geometry keeps its own field coordinates; its zero
    XZ half-size explicitly forbids a district-wide shrink toward the origin.
    """
    if targets is None:
        from g_huxin_canals_targets import target_groups
        targets=target_groups()
    lookup=targets if isinstance(targets,dict) else {target.id:target for target in targets}
    base=float(getattr(profile.surface_fog,'base_y',0.))
    rows=np.zeros((3,256,4),dtype=np.float32)
    rows[0]=timing_rows(profile,owners)
    rows[1,:,1]=base;rows[1,:,3]=9.
    for index,identity in enumerate(owners,1):
        target=lookup.get(identity)
        if target is None:continue
        height=max(.5,float(target.center[1]+target.half_extents[1]-.7-base))
        rows[1,index]=(target.center[0],base,target.center[2],height)
        rows[2,index,:2]=(max(.1,target.half_extents[0]-1.05),max(.1,target.half_extents[2]-1.05))
    return rows


class SurfaceFog:
    def __init__(self,width,height):
        self.width,self.height=width,height
        self.shader=self.noise=self.target=self.field_texture=self.timing_texture=None
        self.field=None;self.last_quality=None;self._profile=None;self.last_steps=0
        self.last_clock=0.;self.last_elapsed=0.;self.last_reflected=False;self.last_water_y=0.
        self.last_active=False;self.last_rows=None;self.last_owner_rows=None;self.atlas_columns=None
        self._support_base_y=None;self._field_atlas_shape=None
        try:
            data,w,h=surface_noise_lattice()
            pixels=pr.ffi.new('unsigned char[]',data)
            self.noise=pr.load_texture_from_image(pr.Image(pixels,w,h,1,pr.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8))
            pr.set_texture_filter(self.noise,pr.TEXTURE_FILTER_BILINEAR)
            pr.set_texture_wrap(self.noise,pr.TEXTURE_WRAP_CLAMP)
            self.shader=pr.load_shader(pr.ffi.NULL,str(ROOT/'shaders/huxin_canals_surface_fog.fs'))
            if self.shader.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Geometry-shaped fog shader compilation failed')
            names=('depthMap','noiseMap','fieldMap','timingMap','resolution','lens','clip','atlasSize',
                   'eye','forward','right','up','fogColour','fieldOrigin','fieldShape','wind',
                   'spacing','distanceCap','atlasColumns','clock','elapsed','waterY','reflectedView',
                   'amount','density','thickness','edge','noiseSize','patternAmount','buildStart','buildEnd','stepCount',
                   'riseResolve','initialScale','settleFraction','baseY','condenseMode','pullDuration','wispAmount','textureGrit',
                   'wispyFormation','pixelGrain','footCurve','lakeBaseY','causeway','lakeOwnsCurve','progressiveLake')
            self.locations={name:pr.get_shader_location(self.shader,name) for name in names}
            from g_huxin_canals_water_fog import shared_causeway_points
            points=shared_causeway_points()
            pr.set_shader_value_v(self.shader,self.locations['causeway'],
                pr.ffi.new('float[]',[value for point in points for value in point]),pr.SHADER_UNIFORM_VEC2,len(points))
            self.quality('balanced')
        except Exception:self.close();raise

    def prepare(self):
        if self.field is not None:return
        from g_huxin_canals_surface_fog import load_surface_field,build_surface_support
        self.field=load_surface_field(FIELD_PATH,verify_sources=True)
        # The extra channel is only fog: architecture, navigation and the
        # original surface-distance/owner channels remain untouched.
        support=build_surface_support(self.field)
        data,w,h,columns,rows=self.field.atlas(support=support)
        self.atlas_columns=columns
        pixels=pr.ffi.new('unsigned char[]',data)
        self.field_texture=pr.load_texture_from_image(pr.Image(pixels,w,h,1,pr.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8))
        self._support_base_y=0.;self._field_atlas_shape=(w,h,columns,rows)
        pr.set_texture_filter(self.field_texture,pr.TEXTURE_FILTER_BILINEAR)
        pr.set_texture_wrap(self.field_texture,pr.TEXTURE_WRAP_CLAMP)
        self.uniform('atlasSize',(w,h));self.uniform('atlasColumns',columns)
        self.uniform('fieldOrigin',tuple(self.field.origin));self.uniform('fieldShape',tuple(self.field.shape))
        self.uniform('spacing',self.field.spacing);self.uniform('distanceCap',self.field.distance_cap)
        pixels=pr.ffi.new('float[]',3*256*4)
        self.timing_texture=pr.load_texture_from_image(pr.Image(pixels,256,3,1,pr.PIXELFORMAT_UNCOMPRESSED_R32G32B32A32))
        pr.set_texture_filter(self.timing_texture,pr.TEXTURE_FILTER_POINT)
        pr.set_texture_wrap(self.timing_texture,pr.TEXTURE_WRAP_CLAMP)

    def sync_support(self,base_y):
        """Replace only alpha content when the authored lake datum changes.

        Reuse the same field texture and sampler bindings. The geometry RGB,
        dimensions and field metadata remain identical; ordinary live timing,
        wind and density edits never rebuild the support distance.
        """
        base_y=float(base_y)
        if base_y==self._support_base_y:return False
        from g_huxin_canals_surface_fog import build_surface_support
        support=build_surface_support(self.field,base_y=base_y)
        data,w,h,columns,rows=self.field.atlas(support=support)
        if (w,h,columns,rows)!=self._field_atlas_shape:
            raise RuntimeError('Support datum edit changed the field atlas dimensions.')
        pr.update_texture(self.field_texture,pr.ffi.cast('void *',pr.ffi.from_buffer(data)))
        self._support_base_y=base_y
        return True

    def sync_profile(self,profile):
        """Prepare/upload before both geometry materials and post fog draw."""
        self.prepare()
        support_changed=self.sync_support(getattr(profile.surface_fog,'base_y',0.))
        if profile==self._profile and self.last_owner_rows is not None:return support_changed
        self.last_owner_rows=owner_rows(profile,self.field.owners)
        self.last_rows=self.last_owner_rows[0]
        pr.update_texture(self.timing_texture,pr.ffi.cast('void *',pr.ffi.from_buffer(self.last_owner_rows)))
        self._profile=profile
        return True

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

    def render(self,source,cam,sequence,clock,colour,water_y,reflected=False,base_texture=None):
        settings=getattr(sequence.direction,'surface_fog',DEFAULT_SURFACE_SETTINGS)
        progressive_lake=bool(getattr(settings,'water_mask',False) and getattr(settings,'water_settle',False))
        from g_huxin_canals_water_fog import lake_fog_frame
        lake_frame=lake_fog_frame(sequence.direction,sequence.elapsed,sequence.state)
        self.quality(sequence.direction.volumes.quality)
        active=settings.enabled and settings.amount>0 and sequence.state in ('entering','canals')
        self.last_clock=clock;self.last_elapsed=sequence.elapsed;self.last_water_y=water_y
        self.last_reflected=reflected;self.last_active=active
        if active:
            self.sync_profile(sequence.direction)
            active=sequence.elapsed>settings.build_start and sequence.elapsed<float(self.last_rows[:,1].max())
            self.last_active=active
        w,h=self.target.texture.width,self.target.texture.height
        pr.begin_texture_mode(self.target);pr.clear_background(pr.BLANK)
        pr.rl_set_blend_factors_separate(pr.RL_ONE,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_ONE,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_FUNC_ADD,pr.RL_FUNC_ADD)
        pr.begin_blend_mode(pr.BLEND_CUSTOM_SEPARATE)
        if base_texture is not None:
            pr.draw_texture_pro(base_texture,pr.Rectangle(0,0,base_texture.width,-base_texture.height),pr.Rectangle(0,0,w,h),pr.Vector2(0,0),0,pr.WHITE)
        if not active:
            pr.end_blend_mode();pr.end_texture_mode();return self.target.texture
        forward=pr.vector3_normalize(pr.vector3_subtract(cam.target,cam.position))
        right=pr.vector3_normalize(pr.vector3_cross_product(forward,cam.up));up=pr.vector3_cross_product(right,forward)
        eye=(cam.position.x,cam.position.y,cam.position.z)
        axes=[eye,(forward.x,forward.y,forward.z),(right.x,right.y,right.z),(up.x,up.y,up.z)]
        if reflected:axes=[(eye[0],2*water_y-eye[1],eye[2])]+[(v[0],-v[1],v[2]) for v in axes[1:]]
        for name,value in zip(('eye','forward','right','up'),axes):self.uniform(name,value)
        for name,value in (('resolution',(w,h)),('lens',(math.tan(math.radians(cam.fovy)*.5),self.width/self.height)),
            ('clip',(pr.rl.rlGetCullDistanceNear(),pr.rl.rlGetCullDistanceFar())),('fogColour',tuple(colour)),
            ('wind',settings.wind),('clock',clock),('elapsed',sequence.elapsed),('waterY',water_y),
            ('reflectedView',float(reflected)),('amount',settings.amount),('density',settings.density),
            ('thickness',settings.thickness),('edge',settings.edge),('noiseSize',settings.noise_size),
            ('patternAmount',settings.pattern_amount),('buildStart',settings.build_start),('buildEnd',settings.build_end),
            ('riseResolve',float(getattr(settings,'evolution','erode') in ('rise_resolve','condense'))),
            ('condenseMode',float(getattr(settings,'evolution','erode')=='condense')),
            ('pullDuration',getattr(settings,'pull_duration',1.15)),('wispAmount',getattr(settings,'wisp_amount',.35)),
            ('textureGrit',getattr(settings,'texture_grit',0.)),
            ('wispyFormation',float(getattr(settings,'wispy_formation',False))),
            ('pixelGrain',getattr(settings,'pixel_grain',0.)),
            ('footCurve',getattr(settings,'foot_curve',0.)),
            ('progressiveLake',float(progressive_lake)),
            ('lakeOwnsCurve',float(progressive_lake and getattr(settings,'foot_curve',0.)>0.)),
            ('lakeBaseY',lake_frame.base_y),
            ('initialScale',getattr(settings,'initial_scale',.4)),
            ('settleFraction',getattr(settings,'settle_fraction',.65)),('baseY',getattr(settings,'base_y',0.)),
            ('stepCount',self.last_steps)):self.uniform(name,value)
        pr.begin_shader_mode(self.shader)
        for name,texture in (('depthMap',source.depth),('noiseMap',self.noise),('fieldMap',self.field_texture),('timingMap',self.timing_texture)):
            pr.set_shader_value_texture(self.shader,self.locations[name],texture)
        pr.draw_rectangle(0,0,w,h,pr.WHITE)
        pr.end_shader_mode();pr.end_blend_mode();pr.end_texture_mode()
        return self.target.texture

    def close(self):
        if self.target:pr.unload_render_texture(self.target);self.target=None
        for name in ('noise','field_texture','timing_texture'):
            texture=getattr(self,name,None)
            if texture:pr.unload_texture(texture);setattr(self,name,None)
        if self.shader:pr.unload_shader(self.shader);self.shader=None
