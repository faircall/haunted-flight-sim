"""Native alpha, roof cutaway and pixel alignment checks in the night renderer."""
from pathlib import Path
import numpy as np
from PIL import Image
import pyray as pr
import g_roofs as roofs
import g_night as night
import g_surfaces as surfaces
import g_render_order as order
import g_graphics as graphics
import g_light_visibility as visibility


def check(game,assets):
    from night_lighting_smoke import pixels,assert_camera_locked
    out=Path('artifacts/roof-interior');out.mkdir(parents=True,exist_ok=True)
    tm=game.make_tile_map(15,15,16,16)
    roofs.paint(tm,[(x,y) for y in range(3,10) for x in range(3,12)])
    player={'position':{'x':80.,'y':200.}}
    local={'shaders':assets['shaders']}
    obj=night.make_facade({'x':104.,'y':160.})
    obj.update(lamp_intensity=1.8)
    arena={'tile_map':tm,'entities':{'facades':{'window':obj}},'lighting_profile':{}}
    target=pr.load_render_texture(240,240)
    floor=surfaces.upload_image(surfaces.base_patch('wood',0,0,240,240))
    actor=surfaces.upload_image(Image.new('RGBA',(10,10),(36,218,79,255)))
    local['test_textures']={'actor':actor}
    character=order.make_world_render_item('test','test','actor',0,
        dict(render_anchor_offset={'x':0.,'y':0.}),{'x':86.,'y':124.},10,10,
        order.make_texture_reference('test_textures','actor'),dict(x=0,y=0,width=10,height=10))
    character['sort_y']=140.
    try:
        night.prepare(local,arena,visibility.build_light_collision_grid(tm,{3}))
        roofs.prepare(local,tm,player)
        facade=night.render_items(local,tm)
        panel,holes=night.facade_art(obj)
        bounds=night.facade_bounds(obj,tm)
        mask=np.asarray(holes)>0
        def render(pan,items=(),emission=False):
            pr.begin_texture_mode(target);pr.clear_background(pr.BLACK)
            pr.draw_texture(floor,-round(pan.x),-round(pan.y),pr.WHITE)
            pr.end_texture_mode()
            ordered=order.sort_world_render_items(items)
            graphics.draw_sorted_world_render_items(ordered,target,pan,local,{})
            if emission:night.draw_emission(target,ordered,pan,local)
        camera=pr.Vector2(0,0)
        render(camera,[character]);baseline=pixels(target)
        render(camera,[character]+facade,True);through=pixels(target)
        x,y,w,h=(bounds[k] for k in ('x','y','width','height'))
        self_view=through[y:y+h,x:x+w][mask]
        real_view=baseline[y:y+h,x:x+w][mask]
        assert np.array_equal(self_view,real_view),'facade/emission repaints the floor or actor through holes'
        assert np.any(np.all(self_view[:,:3]==(36,218,79),axis=1)),'actor not visible through window'
        Image.fromarray(through).save(out/'window-real-interior.png')
        cached=local['roof_runtime']
        items=roofs.render_items(local)+[character]+facade
        render(camera,items,True);outside=pixels(target)
        assert not outside[50:100,50:180,:3].any(),'roof exposes interior floor'
        assert np.array_equal(outside[y:y+h,x:x+w][mask],real_view),'roof hides front aperture'
        Image.fromarray(outside).save(out/'roof-outside.png')
        assert_camera_locked(target,lambda pan:render(pan,items,True),'roof and transparent window')
        player['position'].update(x=80.,y=70.)
        roofs.prepare(local,tm,player,dt=roofs.FADE_SECONDS/2)
        render(camera,roofs.render_items(local)+[character]+facade,True)
        halfway=pixels(target)
        expected=through[50:100,50:180,:3].astype(float)*.5
        assert np.abs(halfway[50:100,50:180,:3]-expected).max()<=1.,'roof opacity did not reach the GPU'
        Image.fromarray(halfway).save(out/'roof-halfway.png')
        # Also exercise the real multi-pass entity composite, with a character
        # under the roof and a separate emission layer behind its faded mask.
        behind=dict(character,dest_rect=dict(character['dest_rect'],y=80.),sort_y=100.,_emission=actor)
        half_items=order.sort_world_render_items([behind]+roofs.render_items(local))
        readability=graphics.get_or_create_render_target(local,'roof_fade_readability',240,240)
        pr.begin_texture_mode(readability);pr.clear_background(pr.BLACK);pr.end_texture_mode()
        profile=dict(ambient_color=[1.,1.,1.],ambient_strength=1.,contrast=1.,black_point=0.,shadow_color=[0.,0.,0.])
        render(camera)
        graphics.draw_sorted_world_render_items(half_items,target,camera,local,profile,entity_readability_lighting=readability)
        lit=pixels(target)
        assert np.abs(lit[82,88,:3].astype(float)-np.array([36,218,79])*.5).max()<=2.,('lit actor does not fade through roof',lit[82,88])
        assert np.abs(lit[60,60,:3].astype(float)-through[60,60,:3]*.5).max()<=2.,'lit roof composites with wrong alpha'
        pr.begin_texture_mode(target);pr.clear_background(pr.BLACK);pr.end_texture_mode()
        night.draw_emission(target,half_items,camera,local)
        emitted=pixels(target)[82,88,:3]
        assert np.abs(emitted.astype(float)-np.array([36,218,79])*.5).max()<=2.,'roof blocks glow until fade finishes'
        roofs.prepare(local,tm,player,dt=roofs.FADE_SECONDS/2)
        assert not roofs.render_items(local),'occupied roof remains visible'
        assert local['roof_runtime'] is cached,'entry allocates a new roof'
        render(camera,roofs.render_items(local)+[character]+facade,True)
        assert np.array_equal(pixels(target),through),'cutaway changes the real interior'
        player['position']['y']=200.;roofs.prepare(local,tm,player,dt=roofs.FADE_SECONDS)
        assert len(roofs.render_items(local))==1,'roof missing after exit'
        print('Roof/aperture GPU: real floor and actor through windows, transparent glow, exterior cover, entry/exit and stable camera passed.')
    finally:
        roofs.unload(local);night.unload(local)
        for rt in local.get('render_targets',{}).values():pr.unload_render_texture(rt)
        pr.unload_texture(floor);pr.unload_texture(actor);pr.unload_render_texture(target)
