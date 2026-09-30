"""Real GPU review of the calm lake, mission transition, rain, wet deck and flash."""
from pathlib import Path
import sys
import pyray as pr
from PIL import Image
import g_main
import g_weather
from moonlit_water_temple import review_arena


def run():
    game=g_main.update_and_render_module;original=game.update_and_render
    output=Path('artifacts/temple-storm');output.mkdir(parents=True,exist_ok=True)
    state={'frame':0};cases=('calm','fireflies','entry','rain','lightning','storm-outside','wet-deck','sheltered','leave-scene')
    motion_count=96 if '--motion' in sys.argv else 0;motion=[]
    pr.set_trace_log_level(pr.TraceLogLevel.LOG_WARNING)
    pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    pr.is_key_pressed=lambda key:False;pr.is_key_down=lambda key:False;pr.is_key_released=lambda key:False
    pr.is_mouse_button_pressed=lambda button:False;pr.is_mouse_button_down=lambda button:False
    pr.get_frame_time=lambda:1./30. if 7<=state['frame']<7+motion_count else .016
    game.update_camera=lambda camera,**kwargs:camera
    def checked(render,lighting,arena,assets,engine):
        ordinal=state['frame'];recording=7<=ordinal<7+motion_count
        frame=6 if recording else ordinal if ordinal<7 else ordinal-motion_count
        if frame==0:arena=review_arena(game,arena)
        camera=assets.setdefault('camera_3d',game.make_default_camera());camera.position.x=112.;camera.position.y=111.
        assets.setdefault('ui_state',game.g_ui.make_ui_state())['show_editor']=False
        if frame==2:arena['player_info']['position']=game.g_editor.world_to_tile_position({'x':480.,'y':240.},arena['tile_map'])
        if frame in (3,4,5,6,7):
            target={3:1.8,4:2.8,5:12.,6:32.,7:34.}[frame]
            current=arena['sequence_state']['weather']['elapsed']
            arena=g_weather.update(arena,max(0.,target-current-.016))
        if frame==5:arena['player_info']['position']=game.g_editor.world_to_tile_position({'x':476.,'y':322.},arena['tile_map'])
        if frame==7:arena['player_info']['position']=game.g_editor.world_to_tile_position({'x':480.,'y':240.},arena['tile_map'])
        if frame in (3,5,7):game.g_water.prepare(assets,arena,.3,'play')
        if frame==8:
            from night_trial import review_arena as courtyard
            arena=courtyard(game,arena.remove('lake_profile'))
        now={0:.5,1:3.7,2:4.,3:5.8,4:6.8,5:16.,6:36.,7:38.,8:40.}[frame]
        if recording:now=36.+(ordinal-6)/30.
        result=original(render,lighting,arena.set('auto_reload',False).set('time_elapsed',now).set('editor_mode','play'),assets,engine)
        if frame==0:
            from rain_surface_smoke import check
            check(game,assets)
            assert 'fireflies' in assets['weather_runtime']['shaders']
            state['moon']=assets['night_runtime']['entries']['moon']
            state['terrain']=assets['weather_runtime']['terrain'].id
        if 2<=frame<8:
            weather=result['sequence_state']['weather'];assert weather['started']
            assert assets['night_runtime']['entries']['moon'] is state['moon'],'radiance animation rebuilt moon shadow map'
            assert assets['weather_runtime']['terrain'].id==state['terrain'],'weather rebuilt the static surface mask'
        if 3<=frame<8:
            assert assets['rain_stats']['enabled'];assert 'surface' in assets['weather_runtime']['shaders']
            assert result['wind_profile']['strength']>=35.
            assert 'runoff' in assets['weather_runtime']['shaders']
        if frame==4:assert result['sequence_state']['weather']['flash']>.8
        if frame==6:assert result['sequence_state']['weather']['wetness']>.75
        if frame==7:assert assets['water_runtime']['cutaways']['roof']==0.
        if frame==8:assert 'weather_runtime' not in assets and 'water_runtime' not in assets
        image=pr.load_image_from_texture(render.texture);pr.image_flip_vertical(image)
        if recording:
            # This is the final framebuffer: preserve its RGB, not intermediate
            # pass alpha (GIF otherwise makes dark roof pixels transparent).
            motion.append(Image.frombytes('RGBA',(image.width,image.height),bytes(pr.ffi.buffer(image.data,image.width*image.height*4))).convert('RGB'))
        else:pr.export_image(image,str(output/(cases[frame]+'.png')))
        pr.unload_image(image)
        state['frame']+=1
        return result
    def safe(*args):
        try:return checked(*args)
        except Exception:
            import traceback;traceback.print_exc();raise SystemExit(1)
    game.update_and_render=safe;pr.window_should_close=lambda:state['frame']>=len(cases)+motion_count
    g_main.g_main()
    for name in cases[:-1]:
        with Image.open(output/(name+'.png')) as im:im.resize((960,540),Image.Resampling.NEAREST).save(output/(name+'-2x.png'))
    if motion:
        motion[0].save(output/'storm-motion-start.png');motion[-1].save(output/'storm-motion-end.png')
        motion[0].save(output/'storm-motion.gif',save_all=True,append_images=motion[1:],duration=33,loop=0)
    print('Temple storm: asset loading, shader compile, one-shot entry, cached moon/terrain, wind, rain, wetness, shelter and cleanup passed.')


if __name__=='__main__':run()
