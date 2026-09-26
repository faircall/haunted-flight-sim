"""GPU alignment checks run in the existing night smoke context."""
import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import pyray as pr
import g_graphics as graphics
import g_light_visibility as visibility
import g_render_order as order


def check(game,assets):
    from night_lighting_smoke import pixels,assert_camera_locked
    tm=game.make_tile_map(20,20,16,16)
    grid=visibility.build_light_collision_grid(tm,{3})
    target=pr.load_render_texture(240,240);camera=pr.Vector2(0,0)
    local={'shaders':assets['shaders']}
    out=Path('artifacts/flashlight-origin');out.mkdir(parents=True,exist_ok=True)
    sheet=Image.new('RGB',(960,500),'#15191b');labels=ImageDraw.Draw(sheet)
    try:
        for slot,angle in enumerate(range(0,360,45)):
            direction={'x':math.cos(math.radians(angle)),'y':math.sin(math.radians(angle))}
            player=game.make_default_player(120.,120.,0.)
            player.update(aim_heading=angle,aim_direction=direction,animation_direction=('right','down','left','up')[((angle+45)//90)%4],
                          procedural_gait={'phase':.7,'blend':1.,'run_blend':0.})
            lens=order.player_cutout_flashlight_world(player,tm)['position']
            light=graphics.apply_light_capability_defaults(graphics.make_player_flashlight(player,tm,grid))
            geometry=visibility.build_light_visibility_polygon_dda(light,light['position'],grid)
            prepared=dict(id='torch',light=light,world_position=light['position'],visibility_polygon=geometry['polygon'],receiver_polygons=[],
                **{key:light[key] for key in ('affects_world','affects_entities','affects_fog','affects_ai','casts_wall_shadows','casts_cinematic_shadows','casts_character_shadows')})
            def render(pan,kind='world'):
                graphics.render_prepared_lights_to_target([prepared],pan,target,local,kind)
            render(camera);ground=pixels(target)
            render(camera,'fog');fog=pixels(target)
            assert np.array_equal(ground,fog),'fog and ground cones disagree'
            sample={axis:math.floor(lens[axis]+direction[axis]*20)+.5 for axis in ('x','y')}
            expected=graphics.get_prepared_gameplay_light_strength_at_world_point(prepared,sample,grid)
            actual=int(ground[int(sample['y']),int(sample['x']),0])
            assert expected>.25 and abs(actual-min(255,round(expected*255)))<=2,('lens/beam mismatch',angle,expected,actual)
            # The character is drawn over the light field so each attachment can
            # be inspected against its real, animated held flashlight.
            pr.begin_texture_mode(target)
            item=order.build_player_render_item(player,tm,assets)
            graphics._draw_cutout_rig(item,camera,assets)
            pr.end_texture_mode()
            panel=Image.fromarray(pixels(target)).convert('RGB')
            marks=ImageDraw.Draw(panel);x,y=lens.values();marks.ellipse((x-1,y-1,x+1,y+1),outline='#00ffff')
            x,y=slot%4*240,slot//4*250
            labels.text((x+4,y+2),f'Aim {angle} / cyan = lens',fill='white');sheet.paste(panel,(x,y+10))
        assert_camera_locked(target,render,'lens-aligned flashlight')
        sheet.save(out/'aim-directions.png')

        # The wider visibility mask must still stop floor light at a solid wall.
        for y in range(20):tm['tiles'][y*20+11]['index']=3
        grid=visibility.build_light_collision_grid(tm,{3})
        light.update(direction={'x':1.,'y':0.},position={'x':120.,'y':142.},render_position={'x':120.,'y':120.})
        geometry=visibility.build_light_visibility_polygon_dda(light,light['position'],grid)
        prepared.update(world_position=light['position'],visibility_polygon=geometry['polygon'])
        render(camera)
        image=pixels(target)
        assert image[120,150,0]>25,'visible beam missing before wall'
        assert not image[24:220,194:230,:3].any(),'lens-aligned cone leaks through wall'
        print('Flashlight origin: eight animated aim directions, CPU/GPU agreement, fog, camera pans and wall clipping passed.')
    finally:
        for rt in local.get('render_targets',{}).values():pr.unload_render_texture(rt)
        pr.unload_render_texture(target)
