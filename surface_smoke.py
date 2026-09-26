"""Hidden actual-game test and review scene: python .tree_game_smoke.py --surfaces."""
from pathlib import Path
import time
import statistics
from PIL import Image
import pyray as pr
import g_main
import g_surfaces as surfaces


from surface_trial import review_map, review_profile


def check_grass_motion(assets, tm):
    # An already-open game must replace the old grass shader on code reload.
    assets['surface_runtime'].pop('shader_version',None)
    surfaces.ensure_grass(assets['surface_runtime'])
    target=pr.load_render_texture(480,270)
    poses=[]
    cases=[(0.,8.,(-100.,-100.)),(1.7,8.,(-100.,-100.)),
           (0.,0.,(-100.,-100.)),(0.,0.,(118.,148.))]
    try:
        for elapsed,strength,position in cases:
            pr.begin_texture_mode(target);pr.clear_background(pr.BLANK)
            surfaces.draw_details(assets,tm,pr.Vector2(0.,0.),
                {'position':dict(zip(('x','y'),position))},
                {'strength':strength,'gust_strength':0.},elapsed,False)
            pr.end_texture_mode()
            capture=pr.load_image_from_texture(target.texture)
            poses.append(bytes(pr.ffi.buffer(capture.data,capture.width*capture.height*4)))
            pr.unload_image(capture)
        assert poses[0]!=poses[1], 'wind does not deform grass'
        assert poses[2]!=poses[3], 'player proximity does not deform grass'
    finally:
        pr.unload_render_texture(target)


def run():
    game=g_main.update_and_render_module
    original=game.update_and_render
    state={'frame':0}; out=Path('artifacts/surfaces');out.mkdir(parents=True,exist_ok=True)
    pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    pr.is_key_pressed=lambda key:False
    pr.is_key_down=lambda key:False
    pr.is_mouse_button_pressed=lambda key:False
    pr.is_mouse_button_down=lambda key:False
    pr.get_frame_time=lambda:.016
    poses=[]
    def checked(render,lighting,arena,assets,engine):
        frame=state['frame']
        if frame==0:
            profile=review_profile(game)
            arena=arena.set('entities',{}).set('lighting_profile',profile).set('tile_map',review_map(game)).set('player_info',game.make_default_player(118,148,0))
        game.update_camera=lambda camera,**kwargs:camera
        assets.setdefault('ui_state',game.g_ui.make_ui_state())['show_editor']=frame==4
        if frame==2:
            arena['player_info']['position']=game.g_editor.world_to_tile_position({'x':160.,'y':148.},arena['tile_map'])
            assets['surface_runtime']['last_player']=(148.,162.)
        if frame==5:
            surfaces.paint(arena['tile_map'],[(5,5)],'dirt')
        if frame==6:
            arena=arena.set('tile_map',game.make_tile_map(10,10,16,16))
        assets.setdefault('editor_state',{})['tile_edit_mode']='materials'
        result=original(render,lighting,arena.set('editor_mode','tile' if frame==4 else 'play').set('time_elapsed',frame*.6),assets,engine)
        rt=assets['surface_runtime']
        if frame<6:assert rt['visible'] and rt['shader'].id != pr.rl.rlGetShaderIdDefault()
        if frame==0:
            state['textures']={k:c['texture'].id for k,c in rt['chunks'].items()}
            state['chunks']=dict(rt['chunks'])
            check_grass_motion(assets,arena['tile_map'])
            times=[]
            for _ in range(120):
                start=time.perf_counter();surfaces.prepare(assets,arena['tile_map'],pr.Vector2(0.,0.));times.append((time.perf_counter()-start)*1000)
            print(f'Cached surface preparation CPU median: {statistics.median(times):.3f} ms')
        elif frame<4:assert state['textures']=={k:c['texture'].id for k,c in rt['chunks'].items()},'unchanged ground rebuilt'
        if frame==5:
            changed=sum(c is not state['chunks'][k] for k,c in rt['chunks'].items())
            assert 0<changed<6, ('edit rebuilt too much',changed)
        if frame==6:assert not rt['chunks'] and not rt['footprints'],'map replacement leaked old surfaces'
        if frame==2:assert rt['footprints'],'moving player left no footprint'
        capture=pr.load_image_from_texture(render.texture);pr.image_flip_vertical(capture)
        pose=Image.frombytes('RGBA',(capture.width,capture.height),bytes(pr.ffi.buffer(capture.data,capture.width*capture.height*4)))
        poses.append(pose);pr.export_image(capture,str(out/f'game-review-{frame}.png'));pr.unload_image(capture)
        state['frame']+=1
        return result
    def safe(*args):
        try:return checked(*args)
        except Exception:
            import traceback;traceback.print_exc();raise SystemExit(1)
    game.update_and_render=safe
    pr.window_should_close=lambda:state['frame']>=7
    g_main.g_main()
    assert poses[0].crop((32,32,260,260)).tobytes()!=poses[1].crop((32,32,260,260)).tobytes()
    poses[0].resize((960,540),Image.Resampling.NEAREST).save(out/'game-review.png')
    poses[0].save(out/'motion.gif',save_all=True,append_images=poses[1:4],duration=220,loop=0)
    print('Material scene: GPU grass, cached bases, footprints, editor controls and cleanup passed.')
