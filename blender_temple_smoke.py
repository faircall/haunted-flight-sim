"""Real-renderer checks and same-camera review of the Blender temple kit."""
from pathlib import Path
import copy
import pyray as pr
from PIL import Image,ImageDraw
import g_main,g_water,g_weather
from moonlit_water_temple_photo import review_arena as photo
from moonlit_water_temple_blender import review_arena as baked


def run():
    output=Path('photo_asset_pipeline/temple3d/review');output.mkdir(exist_ok=True)
    game=g_main.update_and_render_module;original=game.update_and_render;state={'frame':0}
    cases=('previous','blender','flat','inspection','inside','storm','lightning','closed-door','cleanup')
    pr.set_trace_log_level(pr.TraceLogLevel.LOG_WARNING);pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    pr.is_key_pressed=lambda key:False;pr.is_key_down=lambda key:False;pr.is_key_released=lambda key:False
    pr.is_mouse_button_pressed=lambda button:False;pr.is_mouse_button_down=lambda button:False;pr.get_frame_time=lambda:.016
    game.update_camera=lambda camera,**kwargs:camera
    def checked(render,lighting,arena,assets,engine):
        frame=state['frame']
        if frame<4:arena=(photo(game,arena) if frame==0 else baked(game,arena,normals=frame!=2))
        if frame==1:state['lighting']=copy.deepcopy(arena['lighting_profile'])
        camera=assets.setdefault('camera_3d',game.make_default_camera());camera.position.x=112.;camera.position.y=111.
        assets.setdefault('ui_state',game.g_ui.make_ui_state())['show_editor']=False
        if frame==3:arena['lighting_profile'].update(ambient_color=[1.,1.,1.],ambient_strength=.75,black_point=0.)
        if frame==4:
            arena=arena.set('lighting_profile',copy.deepcopy(state['lighting']))
            arena['player_info']['position']=game.g_editor.world_to_tile_position({'x':480.,'y':240.},arena['tile_map'])
            g_water.prepare(assets,arena,.3,'play')
        if frame in (5,6):
            target=12. if frame==5 else 12.8
            arena=g_weather.update(arena,max(0.,target-arena['sequence_state']['weather']['elapsed']-.016))
            arena['player_info']['position']=game.g_editor.world_to_tile_position({'x':476.,'y':322.},arena['tile_map'])
            g_water.prepare(assets,arena,.3,'play')
            if frame==6:arena['sequence_state']['weather']['last_strike']=target-.06
        if frame==7:arena['entities']['facades']['door']['open']=False
        if frame==8:
            from night_trial import review_arena
            arena=review_arena(game,arena.remove('lake_profile'))
        result=original(render,lighting,arena.set('auto_reload',False).set('time_elapsed',.5 if frame<4 else 4.+frame),assets,engine)
        if frame in (1,3,4,5,6,7):
            assert assets['baked_normals'] and assets['baked_positions']
            assert len(assets['baked_normals'])<25 # shared by instances
            items=g_water.render_items(assets,result['entities'])
            assert all(i['self_shadow']['mode']=='normal_map' for i in items)
            assert not result['sequence_runtime']['errors']
        if frame==4:assert assets['water_runtime']['cutaways']['roof']==0.
        if frame==5:assert assets['water_runtime']['cutaways']['roof']==1. and assets['rain_stats']['enabled']
        if frame==7:assert 'door_closed' in assets['baked_normals']
        if frame==8:assert 'baked_normals' not in assets and 'baked_positions' not in assets
        capture=pr.load_image_from_texture(render.texture);pr.image_flip_vertical(capture);pr.export_image(capture,str(output/(cases[frame]+'.png')));pr.unload_image(capture)
        state['frame']+=1;return result
    def safe(*args):
        try:return checked(*args)
        except Exception:
            import traceback;traceback.print_exc();raise SystemExit(1)
    game.update_and_render=safe;pr.window_should_close=lambda:state['frame']>=len(cases);g_main.g_main()
    sheet=Image.new('RGB',(1440,600),(23,29,36));draw=ImageDraw.Draw(sheet)
    for i,name in enumerate(('previous','blender','inspection','inside','storm','lightning')):
        x=i%3*480;y=i//3*300;draw.text((x+8,y+8),name,fill='white');sheet.paste(Image.open(output/(name+'.png')).convert('RGB'),(x,y+26))
    sheet.save(output/'comparison.png')
    print('Blender temple GPU checks passed: normal data upload, shared textures, apertures, roof fade, weather and cleanup.')


if __name__=='__main__':run()
