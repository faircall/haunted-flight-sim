"""Full lake-scene timings: python .tree_game_smoke.py --water-benchmark --label baseline.

Warm frames, uncapped presentation, fixed simulation time, then a separate CPU
profile. Completion timings include a GPU readback (and its transfer overhead).
"""
import argparse
import cProfile
import json
import math
from pathlib import Path
import pstats
import statistics
import time
import pyray as pr
import g_main
from moonlit_water_temple import review_arena


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--water-benchmark',action='store_true')
    parser.add_argument('--label',default='current')
    parser.add_argument('--frames',type=int,default=24)
    parser.add_argument('--profile-frames',type=int,default=6)
    parser.add_argument('--reference', action='store_true', help='Use per-tile/per-light scenery submission for A/B checks')
    weather=parser.add_mutually_exclusive_group()
    weather.add_argument('--storm', action='store_true', help='Start with the temple storm and wet decking already active')
    weather.add_argument('--calm', action='store_true', help='Keep the entry trigger disabled for a calm-weather comparison')
    parser.add_argument('--profile-case', choices=('all','approach','walking','interior'), default='all')
    args=parser.parse_args()
    if args.frames<1 or args.profile_frames<0:parser.error('invalid frame count')
    game=g_main.update_and_render_module;original=game.update_and_render
    out=Path('artifacts/moonlit-water-temple');out.mkdir(parents=True,exist_ok=True)
    state={'frame':0,'depth':{},'stages':{}};rows=[];profiler=cProfile.Profile()
    warm=8;span=warm+args.frames+args.profile_frames
    cases=('approach','walking','interior')
    stages=((game.g_water,'draw'),(game.g_water,'prepare'),(game.g_graphics,'prepare_lighting_frame'),
            (game.g_graphics,'prepare_entity_self_shadows'),(game.g_graphics,'draw_sorted_world_render_items'),
            (game.g_graphics,'render_prepared_lighting'),(game.g_night,'prepare'),(game.g_tree_render,'prepare'),
            (game.g_glow,'render'),(game.g_graphics,'render_effect_group'),(game.g_player_reveal,'prepare'),
            (game.g_ground,'prepare'),(game.g_weather,'update'),(game.g_weather,'draw'),(game.g_weather,'draw_runoff'))
    for module,name in stages:
        method=getattr(module,name);key=module.__name__+'.'+name
        def timed(*values,_method=method,_key=key,**kwargs):
            depth=state['depth'].get(_key,0);state['depth'][_key]=depth+1;start=time.perf_counter()
            try:return _method(*values,**kwargs)
            finally:
                state['depth'][_key]=depth
                if depth==0:state['stages'][_key]=state['stages'].get(_key,0.)+(time.perf_counter()-start)*1000.
        setattr(module,name,timed)
    pr.set_trace_log_level(pr.TraceLogLevel.LOG_WARNING)
    pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    real_fps=pr.set_target_fps;pr.set_target_fps=lambda value:real_fps(0)
    pr.is_key_pressed=lambda key:False;pr.is_key_down=lambda key:False
    pr.is_key_released=lambda key:False
    pr.is_mouse_button_pressed=lambda button:False;pr.is_mouse_button_down=lambda button:False
    pr.get_frame_time=lambda:1./60.
    game.update_camera=lambda camera,**kwargs:camera
    def checked(render,lighting,arena,assets,engine):
        frame=state['frame'];case=cases[frame//span];index=frame%span
        if frame==0:
            arena=review_arena(game,arena)
            if args.calm:arena['world_sequences']['triggers']['temple:storm']['enabled']=False
            if args.storm:
                arena=game.g_weather.update(game.g_weather.start_storm(arena),32.)
                arena['sequence_runtime']['sounds'].clear()
            for flag in ('ground_batches_enabled','entity_atlas_enabled','sprite_culling_enabled'):
                assets[flag] = not args.reference
        camera=assets.setdefault('camera_3d',game.make_default_camera())
        camera.position.x=112.;camera.position.y=111.
        assets.setdefault('ui_state',game.g_ui.make_ui_state())['show_editor']=False
        progress = min(1.,index/max(1,span-1))
        if index >= warm+args.frames:
            progress = .25 + .5*(index-warm-args.frames)/max(1,args.profile_frames-1)
        x,y=(232.,322.) if case=='approach' else (480.,230.) if case=='interior' else (232.+progress*240.,322.)
        if case=='walking':camera.position.x=112.+(x-232.)*.25
        arena['player_info']['position']=game.g_editor.world_to_tile_position({'x':x,'y':y},arena['tile_map'])
        arena=arena.set('auto_reload',False).set('time_elapsed',.5+frame/60.).set('editor_mode','play')
        state['stages']={};profiling=index>=warm+args.frames and args.profile_case in ('all',case)
        if profiling:profiler.enable()
        start=time.perf_counter()
        result=original(render,lighting,arena,assets,engine)
        submitted=time.perf_counter()
        image=pr.load_image_from_texture(render.texture)
        finished=time.perf_counter()
        if profiling:profiler.disable()
        if index==warm+args.frames-1:
            pr.image_flip_vertical(image);pr.export_image(image,str(out/f'{args.label}-{case}.png'))
        pr.unload_image(image)
        if warm<=index<warm+args.frames:
            rows.append(dict(case=case,submit_ms=(submitted-start)*1000.,complete_ms=(finished-start)*1000.,
                             stages=state['stages'].copy(),lighting=assets.get('lighting_frame_stats',{}).copy()))
        state['frame']+=1
        return result
    def safe(*values):
        try:return checked(*values)
        except Exception:
            import traceback;traceback.print_exc();raise SystemExit(1)
    game.update_and_render=safe;pr.window_should_close=lambda:state['frame']>=span*len(cases)
    g_main.g_main()
    summary={}
    for case in cases:
        group=[row for row in rows if row['case']==case]
        summary[case]={key:round(statistics.median(row[key] for row in group),3) for key in ('submit_ms','complete_ms')}
        for key in ('submit_ms','complete_ms'):
            ordered=sorted(row[key] for row in group)
            summary[case][key+'_distribution']={
                'p95':round(ordered[min(len(ordered)-1,math.ceil(.95*len(ordered))-1)],3),
                'p99':round(ordered[min(len(ordered)-1,math.ceil(.99*len(ordered))-1)],3),
                'max':round(max(ordered),3),
                'over_60fps_budget':sum(value>1000./60. for value in ordered),
                'frame_count':len(ordered)}
        summary[case]['stages_ms']={key:round(statistics.median(row['stages'].get(key,0.) for row in group),3) for key in group[0]['stages']}
        summary[case]['lighting']=group[-1]['lighting']
    (out/f'{args.label}-timings.json').write_text(json.dumps(dict(reference=args.reference,storm=args.storm,calm=args.calm,summary=summary,frames=rows),indent=2),encoding='utf8')
    with (out/f'{args.label}-profile.txt').open('w',encoding='utf8') as stream:
        if args.profile_frames:
            pstats.Stats(profiler,stream=stream).strip_dirs().sort_stats('cumulative').print_stats(65)
        else:stream.write('CPU profiling disabled. Frame timings are in the adjacent JSON file.\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':run()
