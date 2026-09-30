"""Offline reference scene -> raylib command/assets fixture for native C.

This trace is deliberately not a game/simulation format. It isolates rendering
headroom without approximating the artwork or omitting expensive render passes.
"""
import argparse
import json
import math
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pyray as pr
from PIL import Image
import g_main
import g_light_visibility
from c_port.recording import Recorder, PACK, blob, ROOT

_native_hash=None

def fnv_rgb(data):
    global _native_hash
    if _native_hash is None and (ROOT/'build'/'hf_checksum.dll').exists():
        import ctypes
        library=ctypes.CDLL(str(ROOT/'build'/'hf_checksum.dll'))
        _native_hash=library.hf_hash_rgb
        _native_hash.argtypes=[ctypes.c_char_p,ctypes.c_size_t]
        _native_hash.restype=ctypes.c_uint64
    if _native_hash is not None:return _native_hash(data,len(data))
    value=14695981039346656037
    for i,byte in enumerate(data):
        if i%4!=3:value=((value^byte)*1099511628211)&0xffffffffffffffff
    return value

def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames',type=int,default=120)
    parser.add_argument('--scene',choices=('water','courtyard'),default='water')
    parser.add_argument('--native-scene',action='store_true',help='Use native C visibility and wind results in the renderer')
    args=parser.parse_args()
    if args.frames<1:parser.error('--frames must be positive')
    from moonlit_water_temple import review_arena as water
    from night_trial import review_arena as courtyard
    factory=water if args.scene=='water' else courtyard
    out=ROOT/'data'/(args.scene+'-native' if args.native_scene else args.scene);out.mkdir(parents=True,exist_ok=True)
    game=g_main.update_and_render_module;original=game.update_and_render
    rec=Recorder();rec.install()
    native=None
    if args.native_scene:
        from c_port.record_native_scene import NativeSceneRecorder
        native=NativeSceneRecorder(rec);native.install()
    ray=g_light_visibility.dda_first_light_hit_values
    def captured_ray(ox,oy,dx,dy,distance,grid):
        result=ray(ox,oy,dx,dy,distance,grid)
        if rec.active and not (native and native.building_visibility):
            identity=id(grid)
            if identity not in rec.grid_ids:
                gid=len(rec.grid_ids);rec.grid_ids[identity]=(gid,grid)
                rec.emit('HFGrid',PACK('Iii dd',gid,grid['map_width'],grid['map_height'],grid['tile_width'],grid['tile_height'])+blob(bytes(grid['shape_codes'])))
            gid=rec.grid_ids[identity][0]
            hit,steps=result
            values=(hit[0],hit[6],hit[7],1,*hit[1:6],steps) if hit else (0.,0.,0.,0,0,0,0,0,0,steps)
            rec.emit('HFRay',PACK('I5d3d7i',gid,ox,oy,dx,dy,distance,*values))
        return result
    g_light_visibility.dda_first_light_hit_values=captured_ray
    warm=8;span=warm+args.frames;cases=('approach','walking','interior')
    state={'frame':0};metadata=[]
    pr.set_trace_log_level(pr.TraceLogLevel.LOG_WARNING)
    pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    fps=pr.set_target_fps;pr.set_target_fps=lambda value:fps(0)
    pr.is_key_pressed=lambda key:False;pr.is_key_down=lambda key:False;pr.is_key_released=lambda key:False
    pr.is_mouse_button_pressed=lambda button:False;pr.is_mouse_button_down=lambda button:False
    pr.get_frame_time=lambda:1./60.
    game.update_camera=lambda camera,**kwargs:camera
    stream=(out/'scene.hfc').open('wb')
    def checked(render,lighting,arena,assets,engine):
        frame=state['frame'];case=cases[frame//span];index=frame%span
        if frame==0:arena=factory(game,arena)
        camera=assets.setdefault('camera_3d',game.make_default_camera())
        camera.position.x=112.;camera.position.y=111.
        assets.setdefault('ui_state',game.g_ui.make_ui_state())['show_editor']=False
        progress=min(1.,index/max(1,span-1))
        x,y=(232.,322.) if case=='approach' else (480.,230.) if case=='interior' else (232.+progress*240.,322.)
        if args.scene=='courtyard':x,y=(240.,250.) if case=='approach' else (315.,190.) if case=='interior' else (240.+progress*90.,250.)
        if case=='walking':camera.position.x=112.+(x-232.)*.25
        arena['player_info']['position']=game.g_editor.world_to_tile_position(dict(x=x,y=y),arena['tile_map'])
        arena=arena.set('auto_reload',False).set('time_elapsed',.5+frame/60.).set('editor_mode','play')
        prefix=rec.start_frame()
        if frame==0:
            stream.write(b'HFCP0001'+PACK('4I',span*3,render.texture.width,render.texture.height,rec.ref('texture',render.texture.id)))
            stream.write(blob(prefix))
        elif prefix:
            # Resource state emitted between update calls belongs to the next frame.
            rec.commands+=prefix
        result=original(render,lighting,arena,assets,engine)
        commands=rec.end_frame()
        if native:native.end_frame()
        rec.suspended=True
        image=pr.load_image_from_texture(render.texture)
        data=bytes(pr.ffi.buffer(image.data,image.width*image.height*4));digest=fnv_rgb(data)
        if index in (0,warm,span-1):
            pr.image_flip_vertical(image);pr.export_image(image,str(out/f'python-{case}-{index}.png'))
        pr.unload_image(image)
        rec.suspended=False
        stream.write(PACK('3IQ',frame//span,index,int(index>=warm),digest)+blob(commands))
        metadata.append(dict(case=case,index=index,bytes=len(commands),commands=sum(rec.frame_counts.values()),counts=dict(rec.frame_counts)))
        state['frame']+=1
        if index==span-1:print(f'Exported {args.scene}/{case}: {span} native frames',flush=True)
        return result
    def safe(*values):
        try:return checked(*values)
        except Exception:
            import traceback;traceback.print_exc();stream.close();raise SystemExit(1)
    game.update_and_render=safe;pr.window_should_close=lambda:state['frame']>=span*3
    g_main.g_main();stream.close();rec.generate_dispatch()
    (out/'manifest.json').write_text(json.dumps(dict(scene=args.scene,frames=args.frames,warmup=warm,
        resources=rec.next,commands=rec.all_counts,frame_details=metadata,
        native_scene=dict(trees=len(native.trees),lights=len(native.jobs),tree_poses=native.pose_count,
                          visibility_builds=native.visibility_count,visibility_fans=native.fan_count) if native else None),indent=2),encoding='utf8')
    print(f'Native export: {(out/"scene.hfc").stat().st_size/1048576:.1f} MiB; {out}',flush=True)

if __name__=='__main__':run()
