"""Native water/reflection pixel checks, within the water-temple smoke context."""
import numpy as np
from PIL import Image
import pyray as pr
import g_water
import g_surfaces
import g_graphics as graphics
import g_render_order as order
import g_effects


def check(game,assets):
    from night_lighting_smoke import pixels,assert_camera_locked
    tm=game.make_tile_map(15,15,16,16)
    for tile in tm['tiles']:tile.update(water=True,lake_bed=True)
    tm['tiles'][5*15+6].update(water=False,surface_material='wood')
    fire=g_effects.make_default_fire_emitter({'x':184.,'y':64.})
    arena=dict(tile_map=tm,player_info=game.make_default_player(20.,20.,0.),entities={'lake_props':{},'emitters':{'lamp':fire}},
               lake_profile=dict(enabled=True,ripple_strength=1.25,reflection_strength=.9))
    local={'shaders':{'effect_fire':assets['shaders']['effect_fire']},'effects_runtime':g_effects.make_effects_runtime()}
    target=pr.load_render_texture(240,240);camera=pr.Vector2(0,0)
    texture=g_surfaces.upload_image(Image.new('RGBA',(8,20),(190,105,45,255)))
    local['test']={'post':texture}
    item=order.make_world_render_item('test','test','post',0,dict(render_anchor_offset={'x':-4.,'y':-20.}),
        {'x':104.,'y':90.},8,20,order.make_texture_reference('test','post'),dict(x=0,y=0,width=8,height=20))
    scene_items=[item]
    try:
        g_water.prepare(local,arena,0.,'play')
        def draw(pan,now=2.,reflect=True,with_fires=False):
            pr.begin_texture_mode(target);pr.clear_background(pr.Color(41,29,18,255));pr.end_texture_mode()
            g_water.draw(target,None,local,arena,scene_items,pan,now,False)
            graphics.draw_sorted_world_render_items(scene_items,target,pan,local,{})
            emitters={'lamp':fire} if with_fires else {}
            snapped=pr.Vector2(round(pan.x),round(pan.y))
            for group in ('world_front','emissive'):
                graphics.render_effect_group(target,snapped,local,{},None,group,False,emitters,tm,g_effects.make_wind_profile(),now)
            if reflect:g_water.draw(target,None,local,arena,scene_items,pan,now,True,effect_emitters=emitters)
        draw(camera,reflect=False);plain=pixels(target)
        draw(camera);reflected=pixels(target)
        self_diff=np.any(reflected[:,:,:3]!=plain[:,:,:3],axis=2)
        self_lake=np.asarray(g_water.water_mask(tm))>0
        assert self_diff.any(),'no reflected geometry reached the lake'
        assert not self_diff[~self_lake].any(),'reflections overwrite dry boardwalk tiles'
        assert np.array_equal(reflected[74:90,100:108],plain[74:90,100:108]),'reflection overwrites the real object'
        assert np.any(reflected[96:112,97:111,:3]>plain[96:112,97:111,:3]),'reflection does not project below ground anchor'
        water_only=self_lake.copy();water_only[70:90,100:108]=False
        used={tuple(color) for color in plain[:,:,:3][water_only]}
        assert used=={g_water.DEFAULT_SURFACE_COLOR,g_water.DEFAULT_RIPPLE_COLOR},('base water must use exactly two colours',used)
        detail=plain[112:200,16:232,:3]
        assert np.any(detail[::2,::2]!=detail[1::2,::2]),'water is still grouped into 2x2 pixels'
        raw_reflection=pixels(local['water_runtime']['targets']['reflections'])
        reflection_palette={tuple(color) for color in reflected[:,:,:3][self_lake]}
        assert reflection_palette<={g_water.DEFAULT_SURFACE_COLOR,g_water.DEFAULT_RIPPLE_COLOR,(190,105,45)},('reflection invents colours',reflection_palette)
        profile=arena['lake_profile']
        profile.update(surface_color=[.1,.04,.02],ripple_color=[.2,.12,.06],ripple_density=.8)
        draw(camera)
        assert np.array_equal(raw_reflection,pixels(local['water_runtime']['targets']['reflections'])),'surface styling changes sprite reflection colours'
        for key in ('surface_color','ripple_color','ripple_density'):profile.pop(key)
        profile['reflections_enabled']=False;draw(camera)
        assert np.array_equal(pixels(target),plain),'base-only review still contains reflection effects'
        profile['reflections_enabled']=True
        for strength in (0.,.3,1.):
            profile['reflection_strength']=strength;draw(camera)
            used={tuple(color) for color in pixels(target)[:,:,:3][self_lake]}
            assert used<={g_water.DEFAULT_SURFACE_COLOR,g_water.DEFAULT_RIPPLE_COLOR,(190,105,45)},('strength changes colours instead of coverage',strength,used)
        profile['reflection_strength']=.9
        foreground=order.make_world_render_item('test','test','foreground',1,dict(render_anchor_offset={'x':-4.,'y':-6.}),
            {'x':104.,'y':108.},8,6,order.make_texture_reference('test','post'),dict(x=0,y=0,width=8,height=6))
        foreground['opacity']=.5;scene_items.append(foreground)
        draw(camera);faded=pixels(target)
        expected=reflected[102:104,100:108,:3]*(127./255.)+np.asarray([190,105,45])*(128./255.)
        assert np.max(np.abs(faded[102:104,100:108,:3]-expected))<=2.,'water recolours or double-darkens a translucent foreground'
        scene_items.pop()
        item['composite_opacity']=0.
        draw(camera)
        assert not pixels(local['water_runtime']['targets']['reflections'])[:,:,:3].any(),'hidden roof still contributes a reflection'
        item.pop('composite_opacity')
        assert_camera_locked(target,draw,'lake water and reflected sprites')
        draw(camera,now=5.)
        assert np.count_nonzero(np.any(pixels(target)[:,:,:3]!=reflected[:,:,:3],axis=2))>30,'water is static'
        draw(camera,with_fires=True);burning=pixels(target)
        source=pixels(local['water_runtime']['targets']['source'])
        raw=pixels(local['water_runtime']['targets']['reflections'])
        flame_mask=pixels(local['water_runtime']['targets']['fire_mask'])[:,:,3]>0
        flame_palette={tuple(color) for color in source[:,:,:3][flame_mask]}
        mirrored=raw[80:150,160:210];visible=mirrored[:,:,3]>0
        assert visible.any(),'actual flame is missing from the reflection'
        assert {tuple(color) for color in mirrored[:,:,:3][visible]}<=flame_palette,'flame reflection invents shades absent from the visible flame'
        final_palette={tuple(color) for color in burning[80:150,160:210,:3].reshape(-1,3)}
        assert final_palette<=flame_palette|{g_water.DEFAULT_SURFACE_COLOR,g_water.DEFAULT_RIPPLE_COLOR},('fire compositing creates gradient colours',final_palette-flame_palette)
        profile['fire_reflections_enabled']=False;draw(camera,with_fires=True);no_glints=pixels(target)
        assert np.array_equal(no_glints[flame_mask],burning[flame_mask]),'fire reflection toggle changes visible flames'
        assert np.any(burning[88:150,160:210,0]>no_glints[88:150,160:210,0]),'fire reflection toggle does nothing'
        profile['fire_reflections_enabled']=True
        assert_camera_locked(target,lambda pan:draw(pan,with_fires=True),'literal flame reflections')
        fire['enabled']=False;draw(camera,with_fires=True);dark=pixels(target)
        assert np.any(burning[88:150,160:210,0]>dark[88:150,160:210,0]),'fire reflections ignore extinguishing the lamp'
        draw(camera,reflect=False)
        assert np.array_equal(pixels(target),plain),'lamp state changes the two-colour base surface'
        print('Water GPU pixels: two base colours, exact sprite/flame reflection palettes, native pixels, coverage-only strength, animated ripples, dry-mask clipping, foreground protection, fire shutdown and camera alignment passed.')
    finally:
        g_water.unload(local);pr.unload_texture(texture);pr.unload_render_texture(target)
