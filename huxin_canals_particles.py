"""Puzzle-only fog cards, rendered into a depth-aware transparent layer.

The ordinary lake mist is deliberately owned by the existing scene. These
clouds exist only after the annulus is placed, and share one time-only layout
between the lake, canals and reflected passes.
"""
from pathlib import Path
from collections import Counter
import math
import numpy as np
import pyray as pr
from g_huxin_canals_particles import particles_at, building_frame_at, build_particle_atlas

ROOT=Path(__file__).parent


class PuzzleFog:
    @property
    def last_signature(self):
        # Native reviews inspect this; normal gameplay never needs thousands
        # of diagnostic tuples. Keep the live rendering path array-only.
        if self._signature is None:
            frame=self._frame
            self._signature=tuple((int(i),tuple(p),float(a)) for i,p,a in
                                  zip(frame.ids,frame.centers,frame.alphas))
        return self._signature

    @last_signature.setter
    def last_signature(self,value):
        self._signature=value

    @property
    def last_groups(self):
        if self._groups is None:self._groups=dict(Counter(self._frame.group_ids))
        return self._groups

    @last_groups.setter
    def last_groups(self,value):
        self._groups=value

    def __init__(self,width,height):
        self.width,self.height=width,height
        self.texture=None;self.shader=None;self.target=None
        self.last_count=0;self.last_draw_count=0;self.last_signature=()
        self.last_groups={}
        self._render_data=None;self._frame=None;self._ordered_views={}
        try:
            data,w,h=build_particle_atlas()
            pixels=pr.ffi.new('unsigned char[]',data)
            im=pr.Image(pixels,w,h,1,pr.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8)
            self.texture=pr.load_texture_from_image(im)
            # A small atlas carries the grain. Filtering only softens individual
            # texels, leaving its coarse lobes and stepped shading intact.
            pr.set_texture_filter(self.texture,pr.TEXTURE_FILTER_BILINEAR)
            pr.set_texture_wrap(self.texture,pr.TEXTURE_WRAP_CLAMP)
            self.target=pr.load_render_texture(width,height)
            self.shader=pr.load_shader(str(ROOT/'shaders/huxin_canals_particles.vs'),str(ROOT/'shaders/huxin_canals_particles.fs'))
            if self.shader.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Puzzle particle shader compilation failed')
            self.locations={n:pr.get_shader_location(self.shader,n) for n in ('depthMap','resolution','clip','fogColour','reflectionPass','waterY','nearFade','targetedFog')}
        except Exception:
            self.close();raise

    def uniform(self,name,value):
        if isinstance(value,(tuple,list)):
            kind={2:pr.SHADER_UNIFORM_VEC2,3:pr.SHADER_UNIFORM_VEC3}[len(value)]
        else:value=(value,);kind=pr.SHADER_UNIFORM_FLOAT
        pr.set_shader_value(self.shader,self.locations[name],pr.ffi.new('float[]',value),kind)

    def render(self,source,cam,sequence,clock,colour,water_y,reflected=False):
        """Premultiplied cloud colour and coverage, without modifying scene depth."""
        active=sequence.state in ('entering','canals')
        direction=getattr(sequence,'direction',None)
        targeted=getattr(direction,'fog_mode','banks')=='buildings'
        frame=building_frame_at(sequence.elapsed,clock,direction) if active and targeted else None
        clouds=particles_at(sequence.elapsed,clock,direction) if active and not targeted else ()
        data=frame if frame is not None else clouds
        self.last_count=len(frame.ids) if frame is not None else len(clouds)
        self.last_draw_count=0
        # Both reflected/direct views, and both hidden world endpoints, use
        # the same immutable arrays. No per-particle Python containers are
        # allocated here, avoiding garbage-collection stalls at the crest.
        if data is not getattr(self,'_render_data',None):
            self._render_data=data;self._frame=frame;self._ordered_views={}
            if frame is not None:
                self.last_signature=None;self.last_groups=None
                self._radii=np.hypot(frame.widths,frame.heights)*.5
            else:
                self.last_signature=tuple((p.id,p.center,p.alpha) for p in clouds)
                self.last_groups=dict(Counter('legacy' for p in clouds))
        pr.begin_texture_mode(self.target);pr.clear_background(pr.BLANK)
        if not self.last_count:
            pr.end_texture_mode();return self.target.texture
        forward=pr.vector3_normalize(pr.vector3_subtract(cam.target,cam.position))
        right=pr.vector3_normalize(pr.vector3_cross_product(forward,cam.up))
        vertical=pr.vector3_cross_product(right,forward)
        tan_y=math.tan(math.radians(cam.fovy)*.5);tan_x=tan_y*self.width/self.height
        ex,ey,ez=cam.position.x,cam.position.y,cam.position.z
        fx,fy,fz=forward.x,forward.y,forward.z
        rx,ry,rz=right.x,right.y,right.z;ux,uy,uz=vertical.x,vertical.y,vertical.z
        extent_x,extent_y=math.sqrt(1.+tan_x*tan_x),math.sqrt(1.+tan_y*tan_y)
        view_key=(ex,ey,ez,fx,fy,fz,rx,ry,rz,ux,uy,uz,tan_x,tan_y,
                  water_y if reflected else None)
        ordered=self._ordered_views.get(view_key) if targeted else None
        if ordered is None and targeted:
            points=frame.centers.copy() if reflected else frame.centers
            if reflected:points[:,1]=2*water_y-points[:,1]
            delta=points-(ex,ey,ez);dx,dy,dz=delta.T
            depth=dx*fx+dy*fy+dz*fz;radius=self._radii
            visible=(depth+radius>0.)
            visible&=np.abs(dx*rx+dy*ry+dz*rz)<=depth*tan_x+radius*extent_x
            visible&=np.abs(dx*ux+dy*uy+dz*uz)<=depth*tan_y+radius*extent_y
            indices=np.flatnonzero(visible)
            indices=indices[np.argsort(-depth[indices],kind='stable')]
            # One flat list of scalar values has no per-card tracked objects.
            # It is also cheaper to read in the FFI loop than NumPy scalars.
            draws=np.empty((len(indices),8),dtype=np.float64)
            draws[:,:3]=points[indices]
            draws[:,3]=frame.widths[indices];draws[:,4]=frame.heights[indices]
            draws[:,5]=np.degrees(frame.rotations[indices])
            draws[:,6]=np.rint(65535*frame.alphas[indices]);draws[:,7]=frame.variants[indices]
            ordered=draws.ravel().tolist()
            # A paused editor can fly through arbitrarily many camera views
            # while retaining one packet; bound that cache as well.
            if len(self._ordered_views)>=4:self._ordered_views.pop(next(iter(self._ordered_views)))
            self._ordered_views[view_key]=ordered
        elif ordered is None:
            ordered=[]
            for p in clouds:
                x,y,z=p.center
                if reflected:y=2*water_y-y
                dx,dy,dz=x-ex,y-ey,z-ez
                depth=dx*fx+dy*fy+dz*fz
                radius=.5*math.hypot(p.width,p.height)
                if depth+radius<=0.:continue
                if abs(dx*rx+dy*ry+dz*rz)>depth*tan_x+radius*extent_x:continue
                if abs(dx*ux+dy*uy+dz*uz)>depth*tan_y+radius*extent_y:continue
                ordered.append((depth,p,x,y,z))
            ordered.sort(key=lambda row:row[0],reverse=True)
        # Sorting along the camera direction keeps alpha overlap stable when
        # the camera changes. Cache each transformed point in the same pass,
        # avoiding repeated FFI field reads for thousands of small fragments.
        self.last_draw_count=len(ordered)//8 if targeted else len(ordered)
        self.uniform('resolution',(self.width,self.height))
        self.uniform('clip',(pr.rl.rlGetCullDistanceNear(),pr.rl.rlGetCullDistanceFar()))
        self.uniform('fogColour',colour);self.uniform('reflectionPass',float(reflected));self.uniform('waterY',water_y)
        self.uniform('targetedFog',float(targeted))
        # Once a gameplay camera is amongst the banks, nearest cards become
        # transparent wisps instead of a stretched texture against the lens.
        # Pavilion cameras remain in the authored central pocket. This only
        # affects viewing distance, never particle lifetime or explored space.
        outside=max(0.,min(1.,(math.hypot(cam.position.x,cam.position.z)-5.5)/2.5))
        outside=outside*outside*(3.-2.*outside)
        # Building clouds are fitted around their own geometry. Keep them
        # present when a camera moves towards a facade; only the small portion
        # immediately against the lens softens. The saved bank version retains
        # its original, wider lens protection.
        self.uniform('nearFade',(.18+.35*outside,1.25+1.75*outside) if targeted
                     else (.18+.6*outside,1.25+8.75*outside))
        pr.begin_mode_3d(cam);pr.begin_shader_mode(self.shader)
        pr.rl.rlDrawRenderBatchActive();pr.rl.rlDisableDepthMask();pr.rl.rlDisableDepthTest();pr.rl.rlDisableBackfaceCulling()
        # RGB is accumulated premultiplied and alpha records cloud coverage.
        # Each cloud owns its fade; the compositor applies no second fade.
        pr.rl_set_blend_factors_separate(pr.RL_SRC_ALPHA,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_ONE,pr.RL_ONE_MINUS_SRC_ALPHA,pr.RL_FUNC_ADD,pr.RL_FUNC_ADD)
        pr.begin_blend_mode(pr.BLEND_CUSTOM_SEPARATE)
        pr.set_shader_value_texture(self.shader,self.locations['depthMap'],source.depth)
        tile=self.texture.width/4
        up=pr.Vector3(0,-1 if reflected else 1,0)
        rectangles=[pr.ffi.new('Rectangle *',(i%4*tile,i//4*tile,tile,tile))[0] for i in range(8)]
        # Reuse native structs in this hot loop; DrawBillboardPro immediately
        # copies their vertices/colours into its batch. No per-card Python
        # wrapper ownership tracking is required for these numeric structs.
        point=pr.ffi.new('Vector3 *');size=pr.ffi.new('Vector2 *')
        origin=pr.ffi.new('Vector2 *');tint=pr.ffi.new('Color *',(255,255,255,255))
        if targeted:
            for i in range(0,len(ordered),8):
                point.x=ordered[i];point.y=ordered[i+1];point.z=ordered[i+2]
                size.x=ordered[i+3];size.y=ordered[i+4]
                origin.x=ordered[i+3]*.5;origin.y=ordered[i+4]*.5
                opacity=int(ordered[i+6]);tint.r=opacity&255;tint.a=opacity>>8
                pr.draw_billboard_pro(cam,self.texture,rectangles[int(ordered[i+7])],point[0],up,
                                      size[0],origin[0],ordered[i+5],tint[0])
        else:
            for _,p,x,y,z in ordered:
                point.x,point.y,point.z=x,y,z
                size.x,size.y=p.width,p.height;origin.x,origin.y=p.width*.5,p.height*.5
                # Pack sixteen-bit opacity into the otherwise unused red channel
                # and alpha. Very faint cards can fade smoothly before despawning.
                opacity=round(65535*p.alpha)
                tint.r=opacity&255;tint.a=opacity>>8
                pr.draw_billboard_pro(cam,self.texture,rectangles[p.variant],point[0],up,
                                      size[0],origin[0],math.degrees(p.rotation),tint[0])
        pr.rl.rlDrawRenderBatchActive();pr.end_blend_mode()
        pr.rl.rlEnableDepthMask();pr.rl.rlEnableDepthTest();pr.rl.rlEnableBackfaceCulling()
        pr.end_shader_mode();pr.end_mode_3d();pr.end_texture_mode()
        return self.target.texture

    def close(self):
        if self.texture:pr.unload_texture(self.texture);self.texture=None
        if self.target:pr.unload_render_texture(self.target);self.target=None
        if self.shader:pr.unload_shader(self.shader);self.shader=None
