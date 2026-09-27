"""Native water/reflection pixel checks, within the water-temple smoke context."""
import numpy as np
from PIL import Image
import pyray as pr
import g_water
import g_surfaces
import g_graphics as graphics
import g_render_order as order
import g_effects


def check(game):
    from night_lighting_smoke import pixels,assert_camera_locked
    tm=game.make_tile_map(15,15,16,16)
    for tile in tm['tiles']:tile.update(water=True,lake_bed=True)
    tm['tiles'][5*15+6].update(water=False,surface_material='wood')
    fire=g_effects.make_default_fire_emitter({'x':184.,'y':64.})
    arena=dict(tile_map=tm,player_info=game.make_default_player(20.,20.,0.),entities={'lake_props':{},'emitters':{'lamp':fire}},
               lake_profile=dict(enabled=True,moon_position=[160.,30.],ripple_strength=1.25,reflection_strength=.9))
    local={};target=pr.load_render_texture(240,240);camera=pr.Vector2(0,0)
    texture=g_surfaces.upload_image(Image.new('RGBA',(8,20),(190,105,45,255)))
    local['test']={'post':texture}
    item=order.make_world_render_item('test','test','post',0,dict(render_anchor_offset={'x':-4.,'y':-20.}),
        {'x':104.,'y':90.},8,20,order.make_texture_reference('test','post'),dict(x=0,y=0,width=8,height=20))
    try:
        g_water.prepare(local,arena,0.,'play')
        def draw(pan,now=2.,reflect=True):
            pr.begin_texture_mode(target);pr.clear_background(pr.Color(41,29,18,255));pr.end_texture_mode()
            g_water.draw(target,None,local,arena,[item],pan,now,False)
            graphics.draw_sorted_world_render_items([item],target,pan,local,{})
            if reflect:g_water.draw(target,None,local,arena,[item],pan,now,True)
        draw(camera,reflect=False);plain=pixels(target)
        draw(camera);reflected=pixels(target)
        self_diff=np.any(reflected[:,:,:3]!=plain[:,:,:3],axis=2)
        self_lake=np.asarray(g_water.water_mask(tm))>0
        assert self_diff.any(),'no reflected geometry reached the lake'
        assert not self_diff[~self_lake].any(),'reflections overwrite dry boardwalk tiles'
        assert np.array_equal(reflected[74:90,100:108],plain[74:90,100:108]),'reflection overwrites the real object'
        assert np.any(reflected[96:112,97:111,:3]>plain[96:112,97:111,:3]),'reflection does not project below ground anchor'
        item['composite_opacity']=0.
        draw(camera)
        assert not pixels(local['water_runtime']['targets']['reflections'])[:,:,:3].any(),'hidden roof still contributes a reflection'
        item.pop('composite_opacity')
        assert_camera_locked(target,draw,'lake water and reflected sprites')
        draw(camera,now=5.)
        assert np.count_nonzero(np.any(pixels(target)[:,:,:3]!=reflected[:,:,:3],axis=2))>30,'water is static'
        draw(camera);burning=pixels(target)
        fire['enabled']=False;draw(camera);dark=pixels(target)
        assert np.any(burning[88:185,171:199,0]>dark[88:185,171:199,0]),'fire glints ignore extinguishing the lamp'
        print('Water GPU pixels: animated ripples, real reflected sprites, dry-mask clipping, foreground protection, fire shutdown and camera alignment passed.')
    finally:
        g_water.unload(local);pr.unload_texture(texture);pr.unload_render_texture(target)
