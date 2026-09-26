"""Actual renderer integration check, via python .tree_game_smoke.py --night."""
from pathlib import Path
from PIL import Image
import pyray as pr
import g_main
import g_night as night
from night_trial import review_arena


def run():
    game=g_main.update_and_render_module;original=game.update_and_render
    state={'frame':0};out=Path('artifacts/night');out.mkdir(parents=True,exist_ok=True)
    pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    pr.is_key_pressed=lambda key:False;pr.is_key_down=lambda key:False
    pr.is_mouse_button_pressed=lambda button:False;pr.is_mouse_button_down=lambda button:False
    pr.get_frame_time=lambda:.016
    def checked(render,lighting,arena,assets,engine):
        frame=state['frame']
        if frame==0:arena=review_arena(game,arena)
        game.update_camera=lambda camera,**kwargs:camera
        if frame==1:arena['entities']['lights']['lamp:left']['enabled']=False
        if frame==2:
            arena['entities']['lights']['lamp:left']['enabled']=True
            game.g_puzzles.set_door_open(arena,arena['entities']['puzzles'][1],True)
        if frame==3:arena['lighting_profile']['moonlight']['azimuth']=125.
        if frame==5:
            arena['entities']['facades'].clear();arena['lighting_profile']['moonlight']['enabled']=False
        assets.setdefault('ui_state',game.g_ui.make_ui_state())['show_editor']=frame in (3,4)
        editor=game.g_editor.get_or_create_editor_state(assets)
        editor.update(inspector_tab='object' if frame==4 else 'world',selected_kind='facade',selected_id='door')
        result=original(render,lighting,arena.set('editor_mode','environment' if frame in (3,4) else 'play'),assets,engine)
        rt=assets['night_runtime']
        if frame==0:
            assert len(assets['facade_textures'])==8
            assert len(assets['architectural_lights'])==5
            state['moon']=rt['entries']['moon'];state['door']=rt['entries']['facade:door']
            moon=state['moon']['record']['light']
            assert game.g_graphics.light_visibility.get_unoccluded_light_strength_at_world_point(moon,{'x':32.,'y':230.},{})>.5
            assert game.g_graphics.light_visibility.get_unoccluded_light_strength_at_world_point(moon,{'x':224.,'y':96.},{})==0
            assert max(rt['entries']['facade:left']['record']['light']['_field']['values'])>0
        if frame==1:
            assert rt['entries']['moon'] is state['moon'],'lamp toggle rebuilt moon'
            assert max(rt['entries']['facade:left']['record']['light']['_field']['values'])==0
        if frame==2:
            assert rt['entries']['facade:door'] is not state['door'],'door state ignored'
            tile=arena['tile_map']['tiles'][9*36+18]
            assert not game.tile_is_collidable(tile,arena['tile_map']),'open facade still blocks doorway'
        if frame==3:assert rt['entries']['moon'] is not state['moon']
        if frame==5:
            assert not rt['entries'] and not assets['facade_textures'] and not assets['architectural_lights']
            assert not any(t.get('facade_blocked') for t in arena['tile_map']['tiles'])
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
    with Image.open(out/'review-0.png') as image:image.resize((960,540),Image.Resampling.NEAREST).save(out/'moonlit-courtyard.png')
    print('Night courtyard: moon, aperture lights, lamp toggle, linked door collision, editor and resource cleanup passed.')
