"""Native water/reflection pixel checks, within the water-temple smoke context."""
from pathlib import Path
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
    out=Path('artifacts/moonlit-water-temple');out.mkdir(parents=True,exist_ok=True)
    tm=game.make_tile_map(15,15,16,16)
    for tile in tm['tiles']:tile.update(water=True,lake_bed=True)
    tm['tiles'][5*15+6].update(water=False,surface_material='wood')
    fire=g_effects.make_default_fire_emitter({'x':184.,'y':64.})
    arena=dict(tile_map=tm,player_info=game.make_default_player(20.,20.,0.),entities={'lake_props':{},'emitters':{'lamp':fire}},
               lake_profile=dict(enabled=True,ripple_strength=1.25,reflection_strength=.9))
    local={'shaders':assets['shaders'],'effects_runtime':g_effects.make_effects_runtime()}
    target=pr.load_render_texture(240,240);light_target=pr.load_render_texture(240,240);camera=pr.Vector2(0,0)
    texture=g_surfaces.upload_image(Image.new('RGBA',(8,20),(190,105,45,255)))
    local['test']={'post':texture}
    item=order.make_world_render_item('test','test','post',0,dict(render_anchor_offset={'x':-4.,'y':-20.}),
        {'x':104.,'y':90.},8,20,order.make_texture_reference('test','post'),dict(x=0,y=0,width=8,height=20))
    scene_items=[item]
    try:
        g_water.prepare(local,arena,0.,'play')
        def draw(pan,now=2.,reflect=True,with_fires=False,lighting=None):
            pr.begin_texture_mode(target);pr.clear_background(pr.Color(41,29,18,255));pr.end_texture_mode()
            g_water.draw(target,lighting,local,arena,scene_items,pan,now,False)
            graphics.draw_sorted_world_render_items(scene_items,target,pan,local,{})
            emitters={'lamp':fire} if with_fires else {}
            snapped=pr.Vector2(round(pan.x),round(pan.y))
            for group in ('world_front','emissive'):
                graphics.render_effect_group(target,snapped,local,{},None,group,False,emitters,tm,g_effects.make_wind_profile(),now)
            if reflect:g_water.draw(target,lighting,local,arena,scene_items,pan,now,True,effect_emitters=emitters)
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
        wavelets=np.all(plain[:,:,:3]==g_water.DEFAULT_RIPPLE_COLOR,axis=2)
        deep=wavelets[112:220,16:232]
        assert 0.<deep.mean()<.008,'open-water glimmers should leave almost all water quiet'
        assert not (deep[:-1]&deep[1:]).any(),'default glimmers are thicker than one native pixel'
        arena['lake_profile']['ripple_width']=3.;draw(camera,reflect=False)
        thick=np.all(pixels(target)[:,:,:3]==g_water.DEFAULT_RIPPLE_COLOR,axis=2)
        assert thick.sum()>wavelets.sum()*1.5,'authored ripple width no longer works'
        arena['lake_profile'].pop('ripple_width')
        Image.fromarray(plain).save(out/'water-wavelets.png')
        # Birth/death changes stroke lengths; surviving pixels must still
        # follow the shared current rather than travel in opposite directions.
        def overlap(a,b):
            a=np.all(a[:,:,:3]==g_water.DEFAULT_RIPPLE_COLOR,axis=2)
            b=np.all(b[:,:,:3]==g_water.DEFAULT_RIPPLE_COLOR,axis=2)
            return (a&b).sum()/max(1,min(a.sum(),b.sum()))
        arena['lake_profile'].update(ripple_speed=1.,ripple_speed_variation=0.,ripple_density=.8)
        draw(camera,now=2.,reflect=False);flow_a=pixels(target)
        draw(camera,now=3.,reflect=False);flow_b=pixels(target)
        forward=overlap(flow_a[115:195,16:232],flow_b[120:200,16:232])
        reverse=overlap(flow_a[115:195,16:232],flow_b[110:190,16:232])
        assert forward>.2 and forward>reverse+.15,('glimmers do not share one travel direction',forward,reverse)
        assert not np.array_equal(flow_a[115:195,16:232],flow_b[120:200,16:232]),'glimmers never form or dissipate'
        arena['lake_profile']['ripple_direction']={'x':.6,'y':.8}
        draw(camera,now=2.,reflect=False);flow_a=pixels(target)
        draw(camera,now=3.,reflect=False);flow_b=pixels(target)
        forward=overlap(flow_a[116:196,16:229],flow_b[120:200,19:232])
        reverse=overlap(flow_a[116:196,16:229],flow_b[112:192,13:226])
        assert forward>.2 and forward>reverse+.15,('glimmers ignore the authored current direction',forward,reverse)
        arena['lake_profile']['ripple_speed']=0.
        draw(camera,now=2.);still=pixels(target)
        draw(camera,now=5.)
        assert np.array_equal(still,pixels(target)),'reflection ripples keep moving independently of the common current'
        for key in ('ripple_speed','ripple_direction','ripple_speed_variation','ripple_density'):arena['lake_profile'].pop(key)
        def components(frame):
            mask=np.all(frame[:,:,:3]==g_water.DEFAULT_RIPPLE_COLOR,axis=2)
            mask[:20]=False;mask[228:]=False
            remaining=set(zip(*np.nonzero(mask)));found={}
            while remaining:
                seed=remaining.pop();points=[seed];todo=[seed]
                while todo:
                    y,x=todo.pop()
                    for point in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
                        if point in remaining:remaining.remove(point);points.append(point);todo.append(point)
                ys,xs=zip(*points);x0,x1=min(xs),max(xs);y0,y1=min(ys),max(ys)
                if x1-x0<4 or y1-y0>3 or x0<3 or x1>235 or y0<=20 or y1>=227:continue
                key=(x0,x1-x0,y1-y0,mask[y0:y1+1,x0:x1+1].tobytes())
                found.setdefault(key,[]).append(y0)
            return found
        # Integer travel isolates speed differences from subpixel stencil changes.
        arena['lake_profile'].update(ripple_speed=1.,ripple_speed_variation=.4,ripple_density=.65)
        shifts=[]
        for now in (1.,3.,5.,7.):
            draw(camera,now=now,reflect=False);cohorts_a=components(pixels(target))
            draw(camera,now=now+1.,reflect=False);cohorts_b=components(pixels(target))
            shifts.extend(cohorts_b[key][0]-value[0] for key,value in cohorts_a.items()
                          if len(value)==1 and len(cohorts_b.get(key,[]))==1)
        assert {3,5,7}<=set(shifts),('glimmers do not travel at different forward speeds',shifts)
        for key in ('ripple_speed','ripple_speed_variation','ripple_density'):arena['lake_profile'].pop(key)
        glimmers=[]
        for index in range(64):
            draw(camera,now=index*.125,reflect=False)
            glimmers.append(Image.fromarray(pixels(target)))
        glimmers[0].save(out/'water-glimmers.gif',save_all=True,append_images=glimmers[1:],duration=125,loop=0)
        reflection_palette={tuple(color) for color in reflected[:,:,:3][self_lake]}
        assert reflection_palette<={g_water.DEFAULT_SURFACE_COLOR,g_water.DEFAULT_RIPPLE_COLOR,(190,105,45)},('reflection invents colours',reflection_palette)
        profile=arena['lake_profile']
        profile.update(reflection_strength=1.,reflection_sway=0.)
        draw(camera);unswayed=pixels(target)
        assert np.all(unswayed[98:110,100:108,:3]==(190,105,45)),'zero horizontal sway still shifts reflection sideways'
        profile['reflection_sway']=2.;offsets=[]
        for now in (0.,3.,6.,9.,12.,15.):
            draw(camera,now=now)
            post=np.all(pixels(target)[98:110,:,:3]==(190,105,45),axis=2)
            for row in post:
                xs=np.flatnonzero(row)
                if len(xs):offsets.append((xs[0]+xs[-1])*.5-103.5)
        assert min(offsets)<=-2. and max(offsets)>=2.,('reflection has no noticeable horizontal sway',offsets)
        assert max(abs(value) for value in offsets)<=4.,'reflection sway exceeds its native-pixel bound'
        profile.update(reflection_strength=.9);profile.pop('reflection_sway')
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

        # The actual flashlight cone now reaches water through the already
        # shadowed lighting target. Reflections must still copy literal colours.
        light=graphics.make_player_flashlight(arena['player_info'],tm)
        light.update(position={'x':32.,'y':106.},render_position={'x':32.,'y':106.},enabled=True,direction={'x':1.,'y':0.})
        prepared=dict(light=light,world_position=light['position'],casts_wall_shadows=False)
        pr.begin_texture_mode(light_target);pr.clear_background(pr.BLACK)
        graphics.draw_prepared_light_to_target(prepared,camera,light_target,local)
        # A blocked half-plane represents the light field's occlusion stencil.
        pr.draw_rectangle(160,0,80,240,pr.BLACK);pr.end_texture_mode()
        draw(camera,reflect=False,lighting=light_target);illuminated=pixels(target)
        changed=np.any(illuminated!=plain,axis=2)
        assert changed.sum()>300,'flashlight never illuminates lake surface'
        assert not changed[:,160:].any(),'water lights up beyond the shadowed light field'
        assert not changed[:35].any(),'water illumination ignores the flashlight cone'
        assert not changed[~self_lake].any(),'water illumination paints over the timber deck'
        used={tuple(c) for c in illuminated[:,:,:3][water_only]}
        assert len(used)<=8,('water lighting adds smooth gradients',used)
        draw(camera,lighting=light_target);lit_reflection=pixels(target)
        exact=np.all(reflected[:,:,:3]==(190,105,45),axis=2)
        assert np.array_equal(lit_reflection[:,:,:3][exact],reflected[:,:,:3][exact]),'water lighting tints the reflected sprite'
        Image.fromarray(np.concatenate((plain,illuminated,lit_reflection),axis=1)).save(out/'water-flashlight.png')
        pr.begin_texture_mode(light_target);pr.clear_background(pr.BLACK);pr.end_texture_mode()
        draw(camera,reflect=False,lighting=light_target)
        assert np.array_equal(pixels(target),plain),'disabled flashlight leaves a stale patch on water'

        # Moon ambience is already authored into the base palette. Its cached
        # visibility is packed once, and intensity changes need no mask uploads.
        sky=bytes([255])*240*240
        moon=dict(color=[.2,.4,.8],intensity=.3,_field=dict(origin=(0,0),width=240,height=240,values=sky))
        local['night_runtime']={'entries':{'moon':{'record':{'light':moon}}}}
        g_water.prepare(local,arena,0.,'play');mask_id=local['water_runtime']['mask'].id
        pr.begin_texture_mode(light_target);pr.clear_background(pr.Color(15,31,61,255));pr.end_texture_mode()
        draw(camera,reflect=False,lighting=light_target)
        assert np.array_equal(pixels(target),plain),'moon colour is counted twice in the water palette'
        moon['intensity']=.4;g_water.prepare(local,arena,0.,'play')
        assert local['water_runtime']['mask'].id==mask_id,'moon brightness rebuilds the water mask'
        local.pop('night_runtime');g_water.prepare(local,arena,0.,'play')

        # A rounded natural shore with a raised deck in deep water. Isolate the
        # shoreline animation from open-water ripples and reflections.
        for y in range(15):
            for x in range(15):
                tm['tiles'][y*15+x].update(water=x>=3 and y>=3,lake_bed=x>=3 and y>=3)
        tm['tiles'][9*15+9].update(water=False,surface_material='wood')
        tm['water_revision']=tm.get('water_revision',0)+1
        profile.update(ripple_density=0.,shore_width=12.,shore_speed=.65)
        scene_items.clear();g_water.prepare(local,arena,0.,'play')
        packed=np.asarray(g_water.water_map_image(tm))
        lake=packed[:,:,0]>0;allowed=packed[:,:,2]>0
        distance=(packed[:,:,1].astype(float)-128.)*(g_water.SHORE_DISTANCE/127.)
        frames=[];foam_areas=[];wash_areas=[];edge_positions=[]
        for now in np.arange(0.,10.,.25):
            draw(camera,now=float(now),reflect=False);frame=pixels(target);frames.append(frame)
            lapping=np.all(frame[:,:,:3]==g_water.DEFAULT_RIPPLE_COLOR,axis=2)
            wet=lapping|np.all(frame[:,:,:3]==g_water.DEFAULT_SURFACE_COLOR,axis=2)
            assert not wet[~allowed].any(),'moving water covers the boardwalk'
            assert not wet[distance< -3.].any(),'lapping overruns its shore limit'
            assert not lapping[distance>15.].any(),'shore wave leaks into deep water or follows raised decks'
            assert np.all(wet[lake]),'lapping exposes missing ground underneath the lake'
            assert {tuple(color) for color in frame[:,:,:3][wet]}<={g_water.DEFAULT_SURFACE_COLOR,g_water.DEFAULT_RIPPLE_COLOR},'lapping adds intermediate colours'
            foam_areas.append(int(lapping.sum()));wash_areas.append(int((wet&~lake).sum()))
            edge_positions.append(int(np.argmax(wet[110])))
        assert max(foam_areas)>200 and min(foam_areas)<max(foam_areas)*.1,('shore foam never forms and dissipates',foam_areas)
        assert max(wash_areas)>100 and min(wash_areas)==0,('actual shoreline never washes over the bank and retreats',wash_areas)
        assert max(edge_positions)-min(edge_positions)>=2,('water/land boundary remains static',edge_positions)

        # Reflections must obey the animated silhouette as it crosses the bank.
        shore_post=order.make_world_render_item('test','test','shore-post',2,dict(render_anchor_offset={'x':-4.,'y':-20.}),
            {'x':48.,'y':100.},8,20,order.make_texture_reference('test','post'),dict(x=0,y=0,width=8,height=20))
        scene_items.append(shore_post)
        for now in (0.,4.,7.):
            draw(camera,now=now,reflect=False);base=pixels(target)
            wet=np.all(base[:,:,:3]==g_water.DEFAULT_SURFACE_COLOR,axis=2)|np.all(base[:,:,:3]==g_water.DEFAULT_RIPPLE_COLOR,axis=2)
            draw(camera,now=now);mirrored=pixels(target)
            changed=np.any(mirrored!=base,axis=2)
            assert changed.any() and not changed[~wet].any(),'reflection leaks past the moving shoreline'
            assert {tuple(color) for color in mirrored[:,:,:3][changed]}<={g_water.DEFAULT_SURFACE_COLOR,g_water.DEFAULT_RIPPLE_COLOR,(190,105,45)},'moving shoreline recolours reflection pixels'
        scene_items.clear()
        assert_camera_locked(target,lambda pan:draw(pan,reflect=False),'shore lapping')
        cached_mask=local['water_runtime']['mask'].id
        g_water.prepare(local,arena,.016,'play')
        assert local['water_runtime']['mask'].id==cached_mask,'shore distance field rebuilds each frame'
        profile['shore_speed']=0.;draw(camera,now=0.,reflect=False);frozen=pixels(target)
        draw(camera,now=8.,reflect=False)
        assert np.array_equal(pixels(target),frozen),'zero shore speed does not freeze lapping'
        profile['shore_width']=0.;draw(camera,reflect=False)
        assert np.all(pixels(target)[:,:,:3][lake]==g_water.DEFAULT_SURFACE_COLOR),'zero shore width does not disable lapping'
        profile.update(shore_width=12.,shore_speed=.65)
        preview=[Image.fromarray(frame).convert('RGB') for frame in frames]
        preview[0].save(out/'shore-lapping.gif',save_all=True,append_images=preview[1:],duration=250,loop=0)
        Image.fromarray(np.concatenate([frames[i] for i in (0,8,16,24)],axis=1)).save(out/'shore-lapping-phases.png')
        print('Water GPU pixels: different forward ripple speeds, horizontal reflection sway, forming/dissolving shore waves, moving boundary, two colours, deck/reflection clipping, cached shore field and camera alignment passed.')
    finally:
        g_water.unload(local);pr.unload_texture(texture);pr.unload_render_texture(target);pr.unload_render_texture(light_target)
