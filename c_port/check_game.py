"""Verify the playable compiled game against every exported Python frame."""
import argparse
from pathlib import Path
import struct
import sys
import pyray as pr
import g_main

def run():
    from c_port.export_scene import fnv_rgb
    from moonlit_water_temple import review_arena
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parity',action='store_true')
    parser.add_argument('--fixture',default='c_port/data/water/scene.hfc')
    args=parser.parse_args()
    data=memoryview(Path(args.fixture).read_bytes());offset=8
    total,w,h,target=struct.unpack_from('<4I',data,offset);offset+=16
    size=struct.unpack_from('<I',data,offset)[0];offset+=4+size
    frames=[]
    for index in range(total):
        case,local,measured,digest,size=struct.unpack_from('<3IQI',data,offset)
        offset+=24+size;frames.append((case,local,digest))
    span=total//3
    game=g_main.update_and_render_module;original=game.update_and_render
    state={'frame':0,'mismatches':[]}
    pr.set_trace_log_level(pr.TraceLogLevel.LOG_WARNING)
    pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    fps=pr.set_target_fps;pr.set_target_fps=lambda value:fps(0)
    pr.is_key_pressed=lambda key:False;pr.is_key_down=lambda key:False;pr.is_key_released=lambda key:False
    pr.is_mouse_button_pressed=lambda button:False;pr.is_mouse_button_down=lambda button:False
    pr.get_frame_time=lambda:1./60.;game.update_camera=lambda camera,**kwargs:camera
    def checked(render,lighting,arena,assets,engine):
        frame=state['frame'];case,index,expected=frames[frame]
        if frame==0:arena=review_arena(game,arena)
        camera=assets.setdefault('camera_3d',game.make_default_camera())
        camera.position.x=112.;camera.position.y=111.
        assets.setdefault('ui_state',game.g_ui.make_ui_state())['show_editor']=False
        progress=min(1.,index/max(1,span-1))
        x,y=(232.,322.) if case==0 else (480.,230.) if case==2 else (232.+progress*240.,322.)
        if case==1:camera.position.x=112.+(x-232.)*.25
        arena['player_info']['position']=game.g_editor.world_to_tile_position(dict(x=x,y=y),arena['tile_map'])
        arena=arena.set('auto_reload',False).set('time_elapsed',.5+frame/60.).set('editor_mode','play')
        result=original(render,lighting,arena,assets,engine)
        image=pr.load_image_from_texture(render.texture)
        actual=fnv_rgb(bytes(pr.ffi.buffer(image.data,w*h*4)))
        if actual!=expected:
            state['mismatches'].append((case,index))
            if len(state['mismatches'])<=12:
                pr.image_flip_vertical(image);pr.export_image(image,f'c_port/output/compiled-difference-{case}-{index}.png')
        pr.unload_image(image);state['frame']+=1
        if index==span-1:print(f'Playable C game parity: view {case+1}/3, mismatches so far {len(state["mismatches"])}',flush=True)
        return result
    def safe(*values):
        try:return checked(*values)
        except Exception:
            import traceback;traceback.print_exc();raise SystemExit(1)
    game.update_and_render=safe;pr.window_should_close=lambda:state['frame']>=total
    g_main.g_main()
    import json
    Path('c_port/output/game-parity.json').write_text(json.dumps(dict(frames=total,mismatches=state['mismatches']),indent=2))
    if state['mismatches']:raise AssertionError(state['mismatches'][:20])
    print(f'Playable C game: all {total} frames match Python exactly.',flush=True)

if __name__=='__main__':run()
