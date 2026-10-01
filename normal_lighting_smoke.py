"""GPU proof that real surface orientation and light height affect the baked kit."""
from pathlib import Path
import math
import numpy as np
from PIL import Image,ImageDraw
import pyray as pr
import g_baked_assets,g_surfaces,g_graphics as graphics

ROOT=Path(__file__).resolve().parent


def run():
    pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN);pr.set_trace_log_level(pr.LOG_WARNING);pr.init_window(256,160,'Normal lighting check')
    shader=pr.load_shader('',str(ROOT/'shaders'/'entity_self_shadow.fs'))
    assert shader.id!=pr.rl.rlGetShaderIdDefault()
    loc=lambda name:pr.get_shader_location(shader,name)
    f=lambda name,v:graphics.set_shader_float(shader,loc(name),v)
    integer=lambda name,v:graphics.set_shader_int(shader,loc(name),v)
    vector=lambda name,v:graphics.set_shader_vec3(shader,loc(name),*v)
    target=pr.load_render_texture(216,116);white=pr.load_render_texture(216,116)
    pr.begin_texture_mode(white);pr.clear_background(pr.WHITE);pr.end_texture_mode()
    integer('selfShadowPass',1);integer('selfShadowMode',3)
    graphics.set_shader_vec2(shader,loc('resolution'),216,116)
    graphics.set_shader_vec2(shader,loc('sourceUvMin'),0,0);graphics.set_shader_vec2(shader,loc('sourceUvMax'),1,1)
    f('worldOcclusionScale',1.);f('selfShadowStrength',1.);f('selfShadowMinimumDirect',.07)
    def render(color,normal,position,point,low,high):
        graphics.set_baked_normal_shader_values(shader,loc('normalData'),dict(geometry_min=low,geometry_max=high),point)
        pr.begin_texture_mode(target);pr.clear_background(pr.BLANK);pr.begin_shader_mode(shader)
        for key,texture in (('entityLightTexture',white.texture),('directionalResponseTexture',normal),('geometryPositionTexture',position)):
            graphics.set_shader_texture(shader,loc(key),texture)
        pr.draw_texture(color,0,0,pr.WHITE);pr.end_shader_mode();pr.end_texture_mode()
        im=pr.load_image_from_texture(target.texture);pr.image_flip_vertical(im)
        colors=pr.load_image_colors(im);array=np.frombuffer(pr.ffi.buffer(colors,216*116*4),dtype='uint8').copy().reshape((116,216,4))
        pr.unload_image_colors(colors);pr.unload_image(im);return Image.fromarray(array)
    textures=[]
    def upload(im):
        t=g_surfaces.upload_image(im);textures.append(t);return t
    try:
        color=upload(Image.new('RGBA',(8,8),(255,255,255,255)));position=upload(Image.new('RGBA',(8,8),(128,128,128,230)))
        for axis,encoded in ((0,(255,128,128,255)),(1,(128,255,128,255)),(2,(128,128,255,255))):
            normal=upload(Image.new('RGBA',(8,8),encoded));point=[0.,0.,0.];point[axis]=100.
            front=np.asarray(render(color,normal,position,point,(-.5,-.5,-.5),(.5,.5,.5)))[3,3,0]
            point[axis]=-100.
            back=np.asarray(render(color,normal,position,point,(-.5,-.5,-.5),(.5,.5,.5)))[3,3,0]
            assert front>245 and back<25,(axis,front,back)
        rec=g_baked_assets.manifest()['roof'];albedo=g_baked_assets.image('roof')
        color=upload(albedo);normal=upload(g_baked_assets.image('roof_normal'));position=upload(g_baked_assets.image('roof_position'))
        sheet=Image.new('RGB',(864,270),(22,28,35));draw=ImageDraw.Draw(sheet)
        cases=(('Left / high',(-180,80,150)),('Right / high',(180,80,150)),('Front / low',(0,180,5)),('Overhead',(0,0,300)))
        for i,(title,point) in enumerate(cases):
            response=render(color,normal,position,point,rec['position_min'],rec['position_max'])
            strength=np.asarray(response)[:,:,:3].astype(float)/255
            rgb=np.asarray(albedo).copy();rgb[:,:,:3]=np.rint(rgb[:,:,:3]*(.17+.83*strength)).astype('uint8')
            result=Image.fromarray(rgb);draw.text((i*216+5,10),title,fill='white');sheet.paste(result,(i*216,30),result)
            sheet.paste(response,(i*216,150),response)
        folder=g_baked_assets.ROOT/'review';folder.mkdir(exist_ok=True);sheet.save(folder/'normal-lighting-study.png')
    finally:
        for texture in textures:pr.unload_texture(texture)
        pr.unload_render_texture(target);pr.unload_render_texture(white);pr.unload_shader(shader);pr.close_window()
    print('GPU normal lighting: all six axis/light-height checks passed; roof light sweep rendered.')


if __name__=='__main__':run()
