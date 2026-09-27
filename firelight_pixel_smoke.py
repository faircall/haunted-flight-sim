"""Real GPU checks for firelight contours, run by the water scene smoke."""
from pathlib import Path
import numpy as np
from PIL import Image
import pyray as pr
import g_effects
import g_editor
import g_firelight
import g_graphics as graphics
import g_night as night
import g_light_visibility as visibility


def check(game, assets):
    from night_lighting_smoke import pixels, assert_camera_locked
    out=Path('artifacts/firelight-review');out.mkdir(parents=True,exist_ok=True)
    target=pr.load_render_texture(240,240);scene=pr.load_render_texture(240,240);blank=pr.load_render_texture(240,240)
    local={'shaders':assets['shaders'],'night_runtime':{'entries':{}}}
    camera=pr.Vector2(0,0);field=None
    emitter=g_effects.make_default_fire_emitter({'x':120.,'y':120.})
    emitter['light'].update(radius=106.,color=[1.,1.,1.])
    tm=game.make_tile_map(15,15,16,16)
    pattern=g_firelight.parameters(emitter,0.)
    pattern['motion']=0.
    light=g_effects.build_fire_runtime_lights({'torch':emitter},tm,0.)['effect:fire:torch']
    light.pop('_fire_contours')
    prepared=dict(light=light,world_position=light['position'],casts_wall_shadows=False)
    profile=graphics.make_lighting_profile()
    profile.update(ambient_strength=0.,direct_light_strength=1.,contrast=1.,black_point=0.,shadow_softness=.00001,
                   light_posterize_enabled=True,light_posterize_levels=8.,light_dither_enabled=False)
    try:
        pr.begin_texture_mode(blank);pr.clear_background(pr.BLACK);pr.end_texture_mode()
        def draw(pan):
            pr.begin_texture_mode(target);pr.clear_background(pr.BLACK)
            graphics.draw_prepared_light_to_target(prepared,pan,target,local)
            pr.end_texture_mode()
        def bands():
            pr.begin_texture_mode(scene);pr.clear_background(pr.WHITE);pr.end_texture_mode()
            graphics.apply_lighting(scene,target,blank,local,profile)
            return pixels(scene)
        draw(camera);plain=pixels(target);plain_bands=bands()
        light['_fire_contours']=pattern
        draw(camera);shaped=pixels(target);shaped_bands=bands()
        assert np.count_nonzero(shaped[:,:,0]!=plain[:,:,0])>3000,'firelight contours have no visible effect'
        yy,xx=np.mgrid[:240,:240]
        outside=np.hypot(xx+.5-120.,yy+.5-120.)>=light['radius']
        assert not shaped[outside,:3].any(),'contours illuminate pixels outside the light radius'
        assert len(np.unique(shaped_bands[:,:,0]))<=8,'contours create gradients after posterization'
        assert np.count_nonzero(shaped_bands[:,:,0]!=shaped_bands[::-1,:,0])>1000,'bands remain circular'
        Image.fromarray(plain_bands).save(out/'bands-original.png')
        Image.fromarray(shaped_bands).save(out/'bands-contours.png')
        assert_camera_locked(target,draw,'firelight contours')
        frames=[];band_frames=[]
        for now in (0.,.4,.8,1.6,3.2,6.4):
            light.update(g_effects.build_fire_runtime_lights({'torch':emitter},tm,now)['effect:fire:torch'])
            draw(camera);animated=pixels(target);stepped=bands()
            assert np.array_equal(animated[shaped[:,:,0]<=25],shaped[shaped[:,:,0]<=25]),'dim outer light edge fluctuates'
            assert np.array_equal(stepped[:,:,0]>0,shaped_bands[:,:,0]>0),'visible reach changes as inner bands evolve'
            assert len(np.unique(stepped[:,:,0]))<=8,'animated contours introduce extra gradient shades'
            frames.append(animated);band_frames.append(stepped)
        difference=band_frames[-1][:,:,0].astype(int)-band_frames[0][:,:,0].astype(int)
        assert np.count_nonzero(difference>0)>100 and np.count_nonzero(difference<0)>100,'band boundaries only expand or contract together'
        assert_camera_locked(target,draw,'evolving firelight contours')
        # Freezing contour motion freezes the field while the flame still moves.
        light['_fire_contours']=pattern;draw(camera)
        assert np.array_equal(pixels(target),shaped),'static contours still pulse with global fire intensity'
        # A real-time animation for reviewing the distinction from a pulse.
        preview=[]
        for index in range(40):
            now=index/10.
            light['_fire_contours']=g_firelight.parameters(emitter,g_effects.fire_activity(emitter,now),now)
            draw(camera)
            preview.append(Image.fromarray(bands()).convert('RGB'))
        preview[0].save(out/'bands-evolving.gif',save_all=True,append_images=preview[1:],duration=100,loop=0)
        light['_fire_contours']=pattern

        # Cached window/receiver fields use exactly the same noise coordinates.
        field=night.field_record(Image.fromarray(plain[:,:,0]),(0,0),dict(light,intensity=1.),'test',local)
        field['light']['_fire_contours']=pattern
        def draw_field(pan):
            pr.begin_texture_mode(target);pr.clear_background(pr.BLACK)
            night.draw_field(field,pan,target,local)
            pr.end_texture_mode()
        draw_field(camera);cached=pixels(target)
        assert np.abs(cached[:,:,:3].astype(int)-shaped[:,:,:3].astype(int)).max()<=2,'receiver and radial contour patterns disagree'
        assert_camera_locked(target,draw_field,'cached firelight contours')
        for index,now in enumerate((0.,.4,.8,1.6,3.2,6.4)):
            field['light']['_fire_contours']=g_firelight.parameters(emitter,g_effects.fire_activity(emitter,now),now)
            draw_field(camera)
            assert np.abs(pixels(target)[:,:,:3].astype(int)-frames[index][:,:,:3].astype(int)).max()<=2,'cached spill pulses instead of sharing the steady animated field'
        field['light']['_fire_contours']=pattern
        night.reload_field_shader(local);draw_field(camera)
        assert np.array_equal(cached,pixels(target)),'shader reload changes the noise pattern'

        # The intensity modulation must leave the geometric shadow fully sealed.
        tm=game.make_tile_map(15,15,16,16)
        for x,y in [(x,6) for x in range(6)]+[(6,y) for y in range(6)]:tm['tiles'][y*15+x]['index']=3
        grid=visibility.build_light_collision_grid(tm,{3})
        light['position']={'x':64.,'y':64.};light['radius']=220.
        geometry=visibility.build_light_visibility_polygon_dda(light,light['position'],grid)
        _,receivers=visibility.query_receiver_polygons(light['position'],light['radius'],grid,light)
        prepared.update(world_position=light['position'],casts_wall_shadows=True,visibility_polygon=geometry['polygon'],receiver_polygons=receivers)
        draw(camera)
        assert not pixels(target)[114:220,114:220,:3].any(),'firelight contours leak through wall shadows'
        assert_camera_locked(target,draw,'firelight wall shadows')
        # A subsequent ordinary light must not inherit the prior fire uniforms.
        light.pop('_fire_contours');draw(camera);normal=pixels(target)
        light['_fire_contours']=dict(pattern,strength=0.);draw(camera)
        assert np.array_equal(normal,pixels(target)),'disabling contours changes ordinary light rendering'
        # Render the real editor widgets and commit a value through their normal
        # numeric-edit path, rather than changing the authored dictionary directly.
        ui=game.g_ui.make_ui_state()
        game.g_ui.ui_begin_frame(ui,None)
        ui['pending_numeric_commits']['torch:light_contours:speed']=1.3
        pr.begin_texture_mode(target);pr.clear_background(pr.BLACK)
        game.g_ui.ui_begin_panel(ui,'fire-light',pr.Rectangle(0,0,184,160),'Firelight')
        g_editor.inspect_fire_light(ui,'torch',emitter['light'])
        game.g_ui.ui_end_panel(ui)
        game.g_ui.ui_end_frame(ui)
        pr.end_texture_mode()
        assert emitter['light']['contours']['speed']==1.3,'editor numeric commit did not update contour speed'
        Image.fromarray(pixels(target)).save(out/'editor-firelight.png')
        print('Firelight GPU: fixed visible footprint and dim edge, independently evolving stepped bands, frozen-motion stability, matching cached fields, camera alignment, sealed shadows and shader reload passed.')
    finally:
        if field:pr.unload_texture(field['light']['_field']['texture'])
        night.unload(local)
        for rt in local.get('render_targets',{}).values():pr.unload_render_texture(rt)
        for rt in (target,scene,blank):pr.unload_render_texture(rt)
