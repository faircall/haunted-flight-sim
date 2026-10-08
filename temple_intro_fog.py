"""Small depth-aware volume pass shared by the intro and cinematics editor."""
import math
from pathlib import Path
import pyray as pr
from g_intro_landscape import road_x,road_slope


def depth_target(width,height):
    """Raylib's usual target has a renderbuffer; this one exposes depth to GLSL."""
    image=pr.gen_image_color(width,height,pr.BLANK)
    colour=pr.load_texture_from_image(image);pr.unload_image(image)
    depth=pr.Texture2D(pr.rl.rlLoadTextureDepth(width,height,False),width,height,1,19)
    target=pr.RenderTexture2D(pr.rl.rlLoadFramebuffer(),colour,depth)
    pr.rl.rlEnableFramebuffer(target.id)
    pr.rl.rlFramebufferAttach(target.id,colour.id,pr.RL_ATTACHMENT_COLOR_CHANNEL0,pr.RL_ATTACHMENT_TEXTURE2D,0)
    pr.rl.rlFramebufferAttach(target.id,depth.id,pr.RL_ATTACHMENT_DEPTH,pr.RL_ATTACHMENT_TEXTURE2D,0)
    complete=pr.rl.rlFramebufferComplete(target.id);pr.rl.rlDisableFramebuffer()
    if not complete:
        pr.unload_render_texture(target)
        raise RuntimeError('Intro requires a sampleable depth framebuffer.')
    return target


class Mist:
    def __init__(self,width,height):
        self.width,self.height=width,height
        self.shader=pr.load_shader(pr.ffi.NULL,str(Path(__file__).parent/'shaders'/'temple_intro_fog.fs'))
        if self.shader.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Volumetric fog shader failed.')
        self.locations={name:pr.get_shader_location(self.shader,name) for name in
                        ('depthMap','eye','forward','right','up','lens','clip','fogColour','dusk','headlights','clock','worldFrame','enabled')}
        self.enabled=True

    def value(self,name,value):
        values=value if isinstance(value,(tuple,list)) else [value]
        kind={1:pr.SHADER_UNIFORM_FLOAT,2:pr.SHADER_UNIFORM_VEC2,3:pr.SHADER_UNIFORM_VEC3,4:pr.SHADER_UNIFORM_VEC4}[len(values)]
        pr.set_shader_value(self.shader,self.locations[name],pr.ffi.new('float[]',values),kind)

    def draw(self,target,world,camera,intro,fog,copy):
        delta=pr.vector3_normalize(pr.vector3_subtract(camera.target,camera.position))
        right=pr.vector3_normalize(pr.vector3_cross_product(delta,camera.up))
        up=pr.vector3_cross_product(right,delta)
        for name,v in (('eye',camera.position),('forward',delta),('right',right),('up',up)):
            self.value(name,(v.x,v.y,v.z))
        orthographic=camera.projection==pr.CAMERA_ORTHOGRAPHIC
        self.value('lens',(camera.fovy*.5 if orthographic else math.tan(math.radians(camera.fovy)*.5),
                           self.width/self.height,float(orthographic)))
        self.value('clip',(pr.rl.rlGetCullDistanceNear(),pr.rl.rlGetCullDistanceFar()))
        self.value('fogColour',(fog.r/255,fog.g/255,fog.b/255))
        self.value('dusk',intro.dusk);self.value('headlights',intro.headlights)
        self.value('clock',intro.elapsed);self.value('enabled',float(self.enabled))
        angle=math.atan(road_slope(intro.distance))
        self.value('worldFrame',(road_x(intro.distance),intro.distance,math.cos(angle),math.sin(angle)))
        pr.begin_texture_mode(target);pr.clear_background(pr.BLACK)
        pr.begin_shader_mode(self.shader)
        pr.set_shader_value_texture(self.shader,self.locations['depthMap'],world.depth)
        copy(world.texture)
        pr.end_shader_mode();pr.end_texture_mode()

    def close(self):pr.unload_shader(self.shader)
