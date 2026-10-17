"""The lake's existing overcast sky, with a fixed moon used by the basin optics."""
from pathlib import Path
import math
import pyray as pr
from g_huxin_moon_sequence import MOON
from temple_intro_sky import Sky

class MoonSky(Sky):
    def __init__(self):
        self.shader=pr.load_shader(pr.ffi.NULL,str(Path(__file__).parent/'shaders'/'huxin_moon_sky.fs'))
        if self.shader.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Moon sky failed')
        self.locations={n:pr.get_shader_location(self.shader,n) for n in ('forward','right','up','fogColour','lens','time','dusk','moonDirection')}
    def draw(self,camera,intro,fog,width,height):
        forward=pr.vector3_normalize(pr.vector3_subtract(camera.target,camera.position));right=pr.vector3_normalize(pr.vector3_cross_product(forward,camera.up));up=pr.vector3_cross_product(right,forward)
        for name,v in (('forward',forward),('right',right),('up',up)):self.value(name,(v.x,v.y,v.z))
        self.value('lens',(math.tan(math.radians(camera.fovy)*.5),width/height,width,height));self.value('moonDirection',MOON)
        self.value('fogColour',(fog.r/255,fog.g/255,fog.b/255));self.value('time',intro.elapsed);self.value('dusk',intro.dusk)
        pr.begin_shader_mode(self.shader);pr.draw_rectangle(0,0,width,height,pr.WHITE);pr.end_shader_mode()
