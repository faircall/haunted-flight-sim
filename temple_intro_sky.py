"""One inexpensive, world-oriented overcast layer for scene and reflection views."""
import math
from pathlib import Path
import pyray as pr
from g_intro_landscape import road_x,road_slope


class Sky:
    def __init__(self):
        self.shader=pr.load_shader(pr.ffi.NULL,str(Path(__file__).parent/'shaders'/'temple_intro_sky.fs'))
        if self.shader.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Overcast sky shader failed')
        self.locations={n:pr.get_shader_location(self.shader,n) for n in ('forward','right','up','fogColour','lens','worldFrame','time','dusk')}

    def value(self,name,value):
        values=value if isinstance(value,(tuple,list)) else [value]
        pr.set_shader_value(self.shader,self.locations[name],pr.ffi.new('float[]',values),
                            {1:pr.SHADER_UNIFORM_FLOAT,3:pr.SHADER_UNIFORM_VEC3,4:pr.SHADER_UNIFORM_VEC4}[len(values)])

    def draw(self,camera,intro,fog,width,height):
        forward=pr.vector3_normalize(pr.vector3_subtract(camera.target,camera.position))
        right=pr.vector3_normalize(pr.vector3_cross_product(forward,camera.up));up=pr.vector3_cross_product(right,forward)
        for name,v in (('forward',forward),('right',right),('up',up)):self.value(name,(v.x,v.y,v.z))
        self.value('lens',(math.tan(math.radians(camera.fovy)*.5) if camera.projection==pr.CAMERA_PERSPECTIVE else .5,width/height,width,height))
        heading=math.atan(road_slope(intro.distance,intro.arrival_station))
        self.value('worldFrame',(road_x(intro.distance,intro.arrival_station),intro.distance,math.cos(heading),math.sin(heading)))
        self.value('fogColour',(fog.r/255,fog.g/255,fog.b/255));self.value('time',intro.elapsed);self.value('dusk',intro.dusk)
        pr.begin_shader_mode(self.shader);pr.draw_rectangle(0,0,width,height,pr.WHITE);pr.end_shader_mode()

    def close(self):pr.unload_shader(self.shader)
