"""Pixel checks run inside the night smoke's real OpenGL context."""
from pathlib import Path
import numpy as np
from PIL import Image
import pyray as pr
import g_graphics as graphics
import g_night as night
import g_render_order as order
import g_light_visibility as visibility


def pixels(target):
    image=pr.load_image_from_texture(target.texture);pr.image_flip_vertical(image)
    values=np.frombuffer(bytes(pr.ffi.buffer(image.data,image.width*image.height*4)),dtype=np.uint8).reshape(image.height,image.width,4)
    pr.unload_image(image)
    return values


def assert_camera_locked(target, render, label):
    """Compare the same world pixels across subpixel pans and pixel boundaries."""
    render(pr.Vector2(0,0))
    reference=pixels(target)[24:208,24:208,:3]
    for x,y in ((.1,.2),(.49,-.49),(.51,-.51),(.9,.9),(1.49,-1.49),(1.51,-1.51),(-2.6,2.6)):
        render(pr.Vector2(x,y))
        sx,sy=round(x),round(y)
        actual=pixels(target)[24-sy:208-sy,24-sx:208-sx,:3]
        changed=np.count_nonzero(np.any(actual!=reference,axis=2))
        assert not changed,(label,'camera pan moved lighting within world pixels',(x,y),changed)


def check(game, assets):
    out=Path('artifacts/night');target=pr.load_render_texture(240,240);camera=pr.Vector2(0,0)
    try:
        polygons=[visibility.tile_shape_world_vertices(x,0,0,16,16) for x in range(3)]
        pr.begin_texture_mode(target);pr.clear_background(pr.BLACK)
        graphics.draw_receiver_polygons(polygons,camera);pr.end_texture_mode()
        assert np.all(pixels(target)[:16,:48,:3]==255),'wall receiver batch leaves diagonal holes'

        # Two perpendicular walls meet diagonally at (96,96). No-width corner
        # seams must not turn one DDA ray into a visible orange streak outside.
        corner_map=game.make_tile_map(15,15,16,16)
        for x,y in [(x,6) for x in range(6)]+[(6,y) for y in range(6)]:
            corner_map['tiles'][y*15+x]['index']=3
        corner_grid=visibility.build_light_collision_grid(corner_map,{3})
        source=dict(type='point',position={'x':64.,'y':64.},radius=220.,intensity=1.,falloff=1.,color=[1.,.4,.1])
        geometry=visibility.build_light_visibility_polygon_dda(source,source['position'],corner_grid)
        _,receivers=visibility.query_receiver_polygons(source['position'],source['radius'],corner_grid,source)
        prepared_corner=dict(light=source,world_position=source['position'],casts_wall_shadows=True,
                             visibility_polygon=geometry['polygon'],receiver_polygons=receivers)
        def render_corner(pan):
            pr.begin_texture_mode(target);pr.clear_background(pr.BLACK)
            graphics.draw_prepared_light_to_target(prepared_corner,pan,target,assets)
            pr.end_texture_mode()
        render_corner(camera)
        assert not pixels(target)[114:220,114:220,:3].any(),'light leaks through touching wall corners'
        assert_camera_locked(target,render_corner,'sealed wall corner')

        tm=game.make_tile_map(15,15,16,16)
        obj=night.make_facade({'x':104.,'y':96.});obj.update(lamp_intensity=0.)
        arena={'tile_map':tm,'entities':{'facades':{'window':obj}},'lighting_profile':{}}
        night.sync_collision(arena);grid=visibility.build_light_collision_grid(tm,{3})
        local={'shaders':assets['shaders']}
        try:
            night.prepare(local,arena,grid)
            for label,sy,direction in (('inward',106.,-1.),('outward',70.,1.)):
                source=graphics.apply_light_capability_defaults(dict(type='spot',position={'x':102.,'y':sy},
                    direction={'x':0.,'y':direction},color=[1.,1.,1.],radius=180.,height=22.,
                    intensity=1.,falloff=1.,inner_angle=18.,outer_angle=27.,near_fade_distance=0.,owner_id='player'))
                records=night.flashlight_portals(local,source,grid)
                assert len(records)==1,(label,'no window transmission')
                light=records[0]['light']
                def render_portal(pan):
                    pr.begin_texture_mode(target);pr.clear_background(pr.BLACK)
                    night.draw_portal({'light':light},pan,target,local)
                    pr.end_texture_mode()
                render_portal(camera)
                image=pixels(target)
                expected=np.array([[night.portal_strength(light,{'x':x+.5,'y':y+.5}) for x in range(240)] for y in range(240)])
                assert expected.max()>.02,(label,'window never passes flashlight')
                error=np.abs(image[:,:,0].astype(float)-expected*255)
                assert np.mean(error)<.8 and np.quantile(error,.99)<3.,(label,error.max(),error.mean())
                capture=pr.load_image_from_texture(target.texture);pr.image_flip_vertical(capture)
                pr.export_image(capture,str(out/f'flashlight-window-{label}.png'));pr.unload_image(capture)
                assert_camera_locked(target,render_portal,'window '+label)
            item=night.render_items(local,tm)[0]
            front=dict(source,position={'x':102.,'y':130.},direction={'x':0.,'y':-1.})
            prepared={'id':'front','light':front,'world_position':front['position']}
            response=night.facade_receiver(prepared,item,grid)
            assert response['strength']>.1,'outside flashlight does not light front face'
            # A thin wall receives the light while its visibility polygon blocks
            # the floor behind it. Both the shader origin and geometry must pan
            # on the same pixel lattice as the facade texture.
            geometry=visibility.build_light_visibility_polygon_dda(front,front['position'],grid)
            _,receivers=visibility.query_receiver_polygons(front['position'],front['radius'],grid,front)
            wall_light=dict(prepared,casts_wall_shadows=True,visibility_polygon=geometry['polygon'],receiver_polygons=receivers)
            def render_wall(pan):
                pr.begin_texture_mode(target);pr.clear_background(pr.BLACK)
                graphics.draw_prepared_light_to_target(wall_light,pan,target,local)
                pr.end_texture_mode()
            assert_camera_locked(target,render_wall,'wall flashlight/receiver')
            scratch=night.draw_facade_receiver(prepared,item,camera,local,240,240)
            assert pixels(scratch)[:,:,0].max()>25,'upright facade field not drawn'
            back=dict(front,position={'x':102.,'y':64.},direction={'x':0.,'y':1.})
            assert night.facade_receiver({'id':'back','light':back,'world_position':back['position']},item,grid)['strength']==0,'backside flashlight leaks onto exterior'
            player=game.make_default_player(104.,130.,0.)
            player.update(aim_direction={'x':0.,'y':-1.},animation_direction='up')
            for _ in range(200):
                player['position']=game.move_entity_with_velocity(player,{'x':0.,'y':-35.},tm,None,.016)
            torch=graphics.make_player_flashlight(player,tm,grid)
            contact=dict(id='contact',light=torch,world_position=torch['position'])
            response=night.facade_receiver(contact,item,grid)
            assert response['strength']>.25,'wall torch goes dark at collision contact'
            scratch=night.draw_facade_receiver(contact,item,camera,local,240,240)
            assert np.count_nonzero(pixels(scratch)[:,:,0]>25)>4,'wall torch collapses to zero pixels'

            # The same beam is projected at hand height for upright sprites,
            # while its ground pass retains the physical floor coordinates.
            beam=dict(torch,position={'x':80.,'y':120.},render_position={'x':80.,'y':98.},
                      direction={'x':1.,'y':0.},casts_wall_shadows=False)
            prepared_beam=dict(light=beam,world_position=beam['position'],casts_wall_shadows=False)
            def render_beam(pan,ground):
                pr.begin_texture_mode(target);pr.clear_background(pr.BLACK)
                graphics.draw_prepared_light_to_target(prepared_beam,pan,target,local,clip_to_wall_visibility=ground)
                pr.end_texture_mode()
            render_beam(camera,True);ground=pixels(target)[22:,:,:3]
            render_beam(camera,False);upright=pixels(target)[:-22,:,:3]
            assert ground.any(),'torch ground beam missing'
            assert np.abs(ground.astype(int)-upright.astype(int)).max()<=1,'sprite beam detached from projected torch tip'
            assert_camera_locked(target,lambda pan:render_beam(pan,False),'projected torch')
        finally:
            night.unload(local)
            for rt in local.get('render_targets',{}).values():pr.unload_render_texture(rt)

        # Compare independent light channels. The red lamp casts the player's
        # actual animated silhouette; an unrelated blue fill must remain intact.
        tm=game.make_tile_map(15,15,16,16)
        player=game.make_default_player(85.,76.,0)
        item=order.build_player_render_item(player,tm,assets)
        def prepared(identity,light):
            light=graphics.apply_light_capability_defaults(light)
            return dict(id=identity,light=light,world_position=light['position'],
                        **{k:light[k] for k in ('affects_world','affects_entities','affects_fog','casts_wall_shadows','casts_cinematic_shadows','casts_character_shadows')})
        lamp=prepared('test-lamp',dict(type='point',position={'x':48.,'y':48.},radius=200.,height=72.,
                                     color=[1.,0.,0.],intensity=1.,falloff=1.,casts_wall_shadows=False))
        fill=prepared('test-fill',dict(type='top_down',position={'x':120.,'y':120.},size={'x':240.,'y':240.},
                                     color=[0.,0.,.2],intensity=1.,casts_wall_shadows=False))
        frame=graphics.build_cinematic_shadow_frame_data([item],assets,lamp)
        assert frame and len(frame['shadows'])==1,'lamp does not include player caster'
        old=assets.get('shadow_render_items',[])
        try:
            assets['shadow_render_items']=[]
            graphics.render_prepared_lights_to_target([lamp,fill],camera,target,assets,'world')
            baseline=pixels(target)
            assets['shadow_render_items']=[item]
            graphics.render_prepared_lights_to_target([lamp,fill],camera,target,assets,'world')
            shadowed=pixels(target)
            assert np.count_nonzero(baseline[:,:,0]>shadowed[:,:,0]+3)>15,'lamp silhouette missing'
            assert np.array_equal(baseline[:,:,2],shadowed[:,:,2]),'lamp shadow erased another light'
            assert_camera_locked(target,lambda pan: graphics.render_prepared_lights_to_target(
                [lamp,fill],pan,target,assets,'world'),'lamp, top-down fill and cast shadow')
            field=night.field_record(Image.new('L',(240,240),255),(0,0),lamp['light'],'test-spill',assets)
            try:
                spill=prepared('test-spill',field['light'])
                frame=graphics.build_cinematic_shadow_frame_data([item],assets,spill)
                assert frame and len(frame['shadows'])==1,'aperture spill omits player caster'
                assets['shadow_render_items']=[]
                graphics.render_prepared_lights_to_target([spill,fill],camera,target,assets,'world')
                clear_spill=pixels(target)
                assets['shadow_render_items']=[item]
                graphics.render_prepared_lights_to_target([spill,fill],camera,target,assets,'world')
                cast_spill=pixels(target)
                assert np.count_nonzero(clear_spill[:,:,0]>cast_spill[:,:,0]+3)>15,'aperture spill has no player silhouette'
                assert np.array_equal(clear_spill[:,:,2],cast_spill[:,:,2]),'spill shadow erased another light'
                assert_camera_locked(target,lambda pan: graphics.render_prepared_lights_to_target(
                    [spill,fill],pan,target,assets,'world'),'cached spill and cast shadow')
            finally:pr.unload_texture(field['light']['_field']['texture'])
            capture=pr.load_image_from_texture(target.texture);pr.image_flip_vertical(capture)
            pr.export_image(capture,str(out/'independent-lamp-shadow.png'));pr.unload_image(capture)
        finally:assets['shadow_render_items']=old
        print('Pixel checks: sealed wall corners, flashlight contact and projection, both window directions, facade response, player shadows, independent lights and camera pan alignment passed.')
    finally:pr.unload_render_texture(target)
