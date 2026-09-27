"""Hidden real-game review: python .tree_game_smoke.py --water."""
from pathlib import Path
import pyray as pr
from PIL import Image
import g_main
import g_water
from moonlit_water_temple import review_arena


def run():
    game=g_main.update_and_render_module;original=game.update_and_render
    out=Path('artifacts/moonlit-water-temple');out.mkdir(parents=True,exist_ok=True)
    state={'frame':0}
    pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    pr.is_key_pressed=lambda key:False;pr.is_key_down=lambda key:False
    pr.is_mouse_button_pressed=lambda button:False;pr.is_mouse_button_down=lambda button:False
    pr.get_frame_time=lambda:.016
    def checked(render,lighting,arena,assets,engine):
        frame=state['frame']
        if frame==0:arena=review_arena(game,arena)
        camera=assets.setdefault('camera_3d',game.make_default_camera())
        camera.position.x=112.;camera.position.y=111.
        game.update_camera=lambda camera,**kwargs:camera
        assets.setdefault('ui_state',game.g_ui.make_ui_state())['show_editor']=False
        if frame==1:
            arena['entities']['emitters']['altar-left']['light']['contours'].update(speed=1.3,motion=.8,strength=.6,scale=22.)
        if frame==2:
            arena['player_info']['position']=game.g_editor.world_to_tile_position(dict(x=480.,y=230.),arena['tile_map'])
            g_water.prepare(assets,arena,.3,'play')
        if frame==3:
            arena['player_info']['position']=game.g_editor.world_to_tile_position(dict(x=476.,y=322.),arena['tile_map'])
            g_water.prepare(assets,arena,.3,'play')
        if frame==4:
            for emitter in arena['entities']['emitters'].values():emitter['enabled']=False
        if frame==5:
            from night_trial import review_arena as courtyard
            arena=courtyard(game,arena.remove('lake_profile'))
        # The retired comparison shortcut must no longer switch firelight modes
        # or accidentally activate effect debug text.
        pr.is_key_pressed=lambda key:frame in (1,2) and key==pr.KeyboardKey.KEY_GRAVE
        pr.is_key_down=lambda key:frame in (1,2) and key==pr.KeyboardKey.KEY_LEFT_CONTROL
        result=original(render,lighting,arena.set('time_elapsed',frame*1.8+.5).set('editor_mode','play'),assets,engine)
        pr.is_key_pressed=lambda key:False;pr.is_key_down=lambda key:False
        if frame<5:
            assert assets['water_runtime']['shaders']['reflection'][0].id>0
            assert assets['water_runtime']['shaders']['water'][0].id>0
            if frame==0:
                from firelight_pixel_smoke import check as check_firelight
                check_firelight(game,assets)
                from water_pixel_smoke import check
                check(game,assets)
                assert len([k for k in assets['runtime_lights'] if k.startswith('effect:fire:')])==6
                state['window']=assets['night_runtime']['entries']['facade:left']
                state['intensity']=state['window']['record']['light']['intensity']
                for name,target in assets['water_runtime']['targets'].items():
                    image=pr.load_image_from_texture(target.texture);pr.image_flip_vertical(image)
                    pr.export_image(image,str(out/(name+'.png')));pr.unload_image(image)
            if frame==1:
                entry=assets['night_runtime']['entries']['facade:left']
                assert entry is state['window'],'editing contour controls rebuilt window light geometry'
                assert entry['record']['light']['_fire_contours']==assets['runtime_lights']['effect:fire:altar-left'].get('_fire_contours'),'window spill lost the firelight contour settings'
                for key,value in dict(motion=.8,strength=.6,scale=22.).items():
                    assert entry['record']['light']['_fire_contours'][key]==value,'live contour edits did not reach window spill'
                assert not assets.get('show_effect_stats',False),'retired shortcut toggled debug text'
                assert entry['record']['light']['intensity']==state['intensity'],'window spill intensity pulses with fire'
            if frame==2:
                assert assets['water_runtime']['cutaways']['roof']==0.,'temple roof did not hide inside'
                assert assets['night_runtime']['entries']['facade:left']['record']['light']['_fire_contours'],'retired shortcut disabled contours'
            if frame in (2,3):
                assert assets['night_runtime']['entries']['facade:left']['record']['light']['intensity']==state['intensity'],'window spill brightness pulses with the flame'
            if frame==3:assert assets['water_runtime']['cutaways']['roof']==1.,'temple roof did not return outside'
            if frame==4:assert not any(k.startswith('effect:fire:') for k in assets['runtime_lights'])
        else:
            assert 'water_runtime' not in assets and 'water_prop_textures' not in assets,'water resources survived leaving scene'
        capture=pr.load_image_from_texture(render.texture);pr.image_flip_vertical(capture)
        pr.export_image(capture,str(out/f'review-{frame}.png'));pr.unload_image(capture)
        state['frame']+=1
        return result
    def safe(*args):
        try:return checked(*args)
        except Exception:
            import traceback;traceback.print_exc();raise SystemExit(1)
    game.update_and_render=safe;pr.window_should_close=lambda:state['frame']>=6
    g_main.g_main()
    with Image.open(out/'review-0.png') as im:im.resize((960,540),Image.Resampling.NEAREST).save(out/'moonlit-water-temple.png')
    print('Water temple: native lake/reflection shaders, fire-linked apertures, roof entry/exit, fire shutdown and scene cleanup passed.')
