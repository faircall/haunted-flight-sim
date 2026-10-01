"""Hidden GPU comparison and resource lifecycle check for the photo art study."""
from pathlib import Path
import copy
import pyray as pr
from PIL import Image,ImageDraw
import g_main,g_water,g_weather
from moonlit_water_temple import review_arena as painted
from moonlit_water_temple_photo import review_arena as photo


def run():
    output=Path('photo_asset_pipeline/review');output.mkdir(parents=True,exist_ok=True)
    game=g_main.update_and_render_module;original=game.update_and_render;state={'frame':0}
    cases=('painted-moon','photo-moon','photo-ambient','photo-inside','photo-storm','photo-lightning','cleanup')
    pr.set_trace_log_level(pr.TraceLogLevel.LOG_WARNING)
    pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    pr.is_key_pressed=lambda key:False;pr.is_key_down=lambda key:False;pr.is_key_released=lambda key:False
    pr.is_mouse_button_pressed=lambda button:False;pr.is_mouse_button_down=lambda button:False
    pr.get_frame_time=lambda:.016
    game.update_camera=lambda camera,**kwargs:camera
    def checked(render,lighting,arena,assets,engine):
        frame=state['frame']
        if frame in (0,1):arena=(painted if frame==0 else photo)(game,arena)
        if frame==1:state['lighting']=copy.deepcopy(arena['lighting_profile'])
        camera=assets.setdefault('camera_3d',game.make_default_camera());camera.position.x=112.;camera.position.y=111.
        assets.setdefault('ui_state',game.g_ui.make_ui_state())['show_editor']=False
        if frame==2:
            # Neutral inspection pass: can assess photographed colour independent
            # of the intentionally dark scene's moon and fire grading.
            arena['lighting_profile'].update(ambient_color=[1.,1.,1.],ambient_strength=.85,black_point=0.)
            arena['lighting_profile']['moonlight']['intensity']=0.
        if frame==3:
            arena=arena.set('lighting_profile',copy.deepcopy(state['lighting']))
            arena['player_info']['position']=game.g_editor.world_to_tile_position({'x':480.,'y':240.},arena['tile_map'])
            g_water.prepare(assets,arena,.3,'play')
        if frame in (4,5):
            target=12. if frame==4 else 12.8
            arena=g_weather.update(arena,max(0.,target-arena['sequence_state']['weather']['elapsed']-.016))
            arena['player_info']['position']=game.g_editor.world_to_tile_position({'x':476.,'y':322.},arena['tile_map'])
            g_water.prepare(assets,arena,.3,'play')
            if frame==5:
                # Force one deterministic lightning phase for the art review.
                arena['sequence_state']['weather']['last_strike']=target-.06
        if frame==6:
            from night_trial import review_arena as courtyard
            arena=courtyard(game,arena.remove('lake_profile'))
        result=original(render,lighting,arena.set('auto_reload',False).set('time_elapsed',.5 if frame<3 else 4.+frame),assets,engine)
        if 1<=frame<=5:
            assert len(assets['water_prop_responses'])==9
            assert all(texture.id>0 for texture in assets['water_prop_responses'].values())
            items=g_water.render_items(assets,result['entities'])
            porcelain=next(i for i in items if i['id']=='lantern:2')
            assert 'sprite_rotation' not in porcelain
            assert assets['night_runtime']['entries']['facade:left']['holes'].getextrema()==(0,255)
            if frame==1:
                resources=assets['water_prop_responses'];state['response_ids']={k:v.id for k,v in resources.items()}
            if frame==2:assert state['response_ids']=={k:v.id for k,v in assets['water_prop_responses'].items()}
        if frame==3:assert assets['water_runtime']['cutaways']['roof']==0.
        if frame==4:
            assert assets['water_runtime']['cutaways']['roof']==1.
            assert assets['rain_stats']['enabled']
        if frame==6:assert 'water_prop_responses' not in assets and 'water_runtime' not in assets
        capture=pr.load_image_from_texture(render.texture);pr.image_flip_vertical(capture)
        pr.export_image(capture,str(output/(cases[frame]+'.png')));pr.unload_image(capture)
        state['frame']+=1
        return result
    def safe(*args):
        try:return checked(*args)
        except Exception:
            import traceback;traceback.print_exc();raise SystemExit(1)
    game.update_and_render=safe;pr.window_should_close=lambda:state['frame']>=len(cases)
    g_main.g_main()
    sheet=Image.new('RGB',(1920,1120),(24,29,36));d=ImageDraw.Draw(sheet)
    for i,name in enumerate(cases[:4]):
        im=Image.open(output/(name+'.png')).convert('RGB').resize((960,540),Image.Resampling.NEAREST)
        x=i%2*960;y=i//2*560;sheet.paste(im,(x,y+20));d.text((x+8,y+5),name,fill='white')
    sheet.save(output/'scene-comparison.png')
    print('Photo scene GPU check passed: native captures, directional response reuse, roof entry/exit, rain, aperture holes and cleanup.')


if __name__=='__main__':run()
