"""Real GPU regressions invoked by the night smoke inside its existing context."""
import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import pyray as pr
import g_graphics as graphics
import g_night as night
import g_render_order as order
import g_light_visibility as visibility


def check(game,assets):
    from night_lighting_smoke import pixels
    out=Path('artifacts/shadow-motion');out.mkdir(parents=True,exist_ok=True)
    target=pr.load_render_texture(480,480);camera=pr.Vector2(0,0)
    try:
        tree=dict(id=3,type='willow tree',position={'x':240.,'y':240.})
        item=order.build_brain_render_item(3,tree,dict(tile_width=16,tile_height=16),assets)
        sheet=Image.new('RGB',(1280,680),'#303b37');draw=ImageDraw.Draw(sheet)
        orbit=[]
        for step in range(24):
            angle=step*math.tau/24
            lamp=dict(type='point',position={'x':240+80*math.cos(angle),'y':240+80*math.sin(angle)},
                      height=22.,radius=600.,intensity=1.,falloff=1.)
            prepared=dict(light=lamp,world_position=lamp['position'],casts_cinematic_shadows=True)
            frame=graphics.build_cinematic_shadow_frame_data([item],assets,prepared)
            assert len(frame['shadows'])==1,'tree caster missing'
            pr.begin_texture_mode(target);pr.clear_background(pr.WHITE);pr.end_texture_mode()
            graphics.render_cinematic_shadow_raw(frame,camera,target,assets['shaders']['cinematic_shadow_projection'],attenuate_light=True)
            rgba=pixels(target)
            darkness=255-rgba[:,:,0]
            assert np.count_nonzero(darkness>20)>200,('tree vanished at light azimuth',step*15)
            assert darkness.max()<=round(frame['shadows'][0]['opacity']*255)+2,'crossed cards double-darkened the overlap'
            mask=np.zeros_like(rgba);mask[:,:,3]=darkness
            panel=Image.new('RGBA',(480,480),'#778878');panel.alpha_composite(Image.fromarray(mask))
            marks=ImageDraw.Draw(panel);marks.line((234,240,246,240),fill='red');marks.line((240,234,240,246),fill='red')
            lx,ly=lamp['position'].values();marks.ellipse((lx-3,ly-3,lx+3,ly+3),fill='yellow')
            orbit.append(panel.convert('RGB'))
            if step%3==0:
                slot=step//3;x,y=slot%4*320,slot//4*340
                draw.text((x+6,y+4),f'Light {step*15} degrees - root marked red',fill='white')
                sheet.paste(panel.resize((320,320)),(x,y+20))
        sheet.save(out/'tree-shadow-orbit.png')
        orbit[0].save(out/'tree-shadow-orbit.gif',save_all=True,append_images=orbit[1:],duration=100,loop=0)

        tm=game.make_tile_map(20,20,16,16)
        obj=night.make_facade({'x':104.,'y':96.},'pierced_door');obj['open']=True
        arena={'tile_map':tm,'entities':{'facades':{'door':obj}},'lighting_profile':{}}
        night.sync_collision(arena);grid=visibility.build_light_collision_grid(tm,{3})
        local={'shaders':assets['shaders'],'textures':assets['textures'],'sprite_sheets':assets.get('sprite_sheets',{})}
        try:
            night.prepare(local,arena,grid)
            record=local['architectural_lights'][0]
            light=graphics.apply_light_capability_defaults(record['light'])
            prepared=dict(id=record['id'],light=light,world_position=light['position'],
                **{k:light[k] for k in ('affects_world','affects_entities','affects_fog','casts_wall_shadows','casts_cinematic_shadows','casts_character_shadows')})
            panels=[];counts=[]
            for foot_y in (104.,100.,97.,96.,95.,92.,90.,72.):
                player=game.make_default_player(104.,foot_y-14.,0.)
                player.update(animation_direction='up',procedural_gait={'phase':.6,'blend':1.,'run_blend':0.})
                item=order.build_player_render_item(player,tm,local)
                assert item['draw_data']['cutout_rig_parts'],'animated player pose missing'
                local['shadow_render_items']=[]
                graphics.render_prepared_lights_to_target([prepared],camera,target,local,'world')
                baseline=pixels(target)
                local['shadow_render_items']=[item]
                graphics.render_prepared_lights_to_target([prepared],camera,target,local,'world')
                actual=pixels(target)
                changed=np.count_nonzero(baseline[96:180,:,0].astype(int)>actual[96:180,:,0].astype(int)+3)
                counts.append((foot_y,changed))
                if foot_y>=90.:assert changed>4,('door shadow cut off at threshold',foot_y,changed)
                if foot_y==72.:assert changed==0,('shadow should naturally end once projection cannot reach door',changed)
                assert not actual[:96,:,:3].any(),'spill shadow added indoor light'
                picture=Image.fromarray(actual).convert('RGB').crop((64,60,144,180)).resize((160,240),Image.Resampling.NEAREST)
                panels.append((foot_y,picture))
            sheet=Image.new('RGB',(1280,260),'#15191b');draw=ImageDraw.Draw(sheet)
            for index,(foot_y,picture) in enumerate(panels):
                draw.text((index*160+4,4),f'Feet y={foot_y:g} / door 96',fill='white')
                sheet.paste(picture,(index*160,20))
            sheet.save(out/'doorway-shadow-continuity.png')
            print('Doorway shadow pixels outside:',counts)
        finally:
            night.unload(local)
            for rt in local.get('render_targets',{}).values():pr.unload_render_texture(rt)
        print('Shadow motion: tree orbit through 24 azimuths and player crossing doorway passed.')
    finally:pr.unload_render_texture(target)
