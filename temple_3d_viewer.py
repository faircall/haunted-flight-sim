"""Live 3D temple exploration, with the independent art review modes retained.

WASD walk (existing tile collision), Q/E orbit, arrows elevation, wheel zoom,
R roof cutaway, L inspection lighting, Home reset view, Esc quit. F12 screenshot.
Use --fixed-cameras (or moonlit_water_temple_3d.py) for the authored walkthrough.
"""
from pathlib import Path
import argparse,math,json
import pyray as pr
from pyrsistent import pmap
from PIL import Image
import g_update_and_render as game
import g_night,g_baked_assets,g_surfaces
import temple_mesh_loader
import g_temple_deck
import g_temple_structure as structure
from g_temple_scene import prop_origin
from photo_asset_pipeline.temple3d.living.gait import SETTINGS as GAIT_SETTINGS
from moonlit_water_temple_blender import review_arena

ROOT=Path(__file__).resolve().parent
ART=g_baked_assets.ROOT


def build_terrain(tm,folder=None):
    """One static mesh, grouped by material; cell data remains authoritative."""
    lines=['mtllib viewer_terrain.mtl'];offset=0
    for material in ('grass','planks_x','planks_y','wall_ground'):
        lines.extend(['o '+material,'usemtl '+material])
        for i,tile in enumerate(tm['tiles']):
            if tile.get('water'):continue
            kind=tile.get('surface_material','grass')
            if kind=='wood' and tile.get('surface_elevation',0.)>0:
                continue  # separate suspended boards, not a solid tile extrusion
            mat=('planks_'+tile.get('surface_axis','x')) if kind=='wood' else 'wall_ground' if kind in ('wall','stone') else 'grass'
            if mat!=material:continue
            x=i%tm['map_width']*16;y=i//tm['map_width']*16
            z=tile.get('surface_elevation',0.)+(48. if kind=='wall' else 0.)
            base=tile.get('surface_elevation',0.) if kind=='wall' else 0.
            # Vertices are X / height / ground Y, with outward winding.
            quads=[([(x,z,y),(x,z,y+16),(x+16,z,y+16),(x+16,z,y)],(0,1,0))]
            if z>0:
                for dx,dy,vertices,normal in (
                    (-1,0,[(x,0,y),(x,0,y+16),(x,z,y+16),(x,z,y)],(-1,0,0)),
                    (1,0,[(x+16,0,y+16),(x+16,0,y),(x+16,z,y),(x+16,z,y+16)],(1,0,0)),
                    (0,-1,[(x+16,0,y),(x,0,y),(x,z,y),(x+16,z,y)],(0,0,-1)),
                    (0,1,[(x,0,y+16),(x+16,0,y+16),(x+16,z,y+16),(x,z,y+16)],(0,0,1))):
                    neighbour=g_surfaces.cell(tm,x//16+dx,y//16+dy)
                    neighbour_z=neighbour.get('surface_elevation',0.)+(48. if neighbour.get('surface_material')=='wall' else 0.)
                    if neighbour_z<z:quads.append(([(px,max(base,py),pz) for px,py,pz in vertices],normal))
            sw,sh=(128,32) if material=='planks_x' else (32,128) if material=='planks_y' else (48,32) if material=='wall_ground' else (64,64)
            for vertices,normal in quads:
                for k in (0,1,2,0,2,3):
                    p=vertices[k];lines.append('v %g %g %g'%p)
                    lines.append('vt %g %g'%(p[0]/sw,-(p[2] if normal[1] else p[1])/sh));lines.append('vn %g %g %g'%normal)
                lines.extend('f '+' '.join(f'{k}/{k}/{k}' for k in range(offset+n+1,offset+n+4)) for n in (0,3));offset+=6
    folder=Path(folder) if folder is not None else ART/'models';folder.mkdir(parents=True,exist_ok=True)
    target=folder/'viewer_terrain.obj';target.write_text('\n'.join(lines))
    grass=folder/'viewer_grass.png';g_surfaces.base_patch('grass',0,0,64,64).save(grass)
    (folder/'viewer_terrain.mtl').write_text('\n'.join('newmtl '+n+'\nKd 1 1 1\nmap_Kd '+str(grass if n=='grass' else ART/'runtime'/(n+'.png')).replace('\\','/')+'\n' for n in ('grass','planks_x','planks_y','wall_ground')))
    return target


def can_walk(tm,x,y):
    # Use existing tile-shape collision, with a small body radius.
    for dx,dy in ((-3,-3),(3,-3),(-3,3),(3,3)):
        p=game.g_editor.world_to_tile_position(dict(x=x+dx,y=y+dy),tm)
        if not (0<=p['tile_x']<tm['map_width'] and 0<=p['tile_y']<tm['map_height']):return False
        if game.position_collides_within_tile_shape(p,tm):return False
    return True


def run(fixed_cameras=False,living_assets=False):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--structure-review',action='store_true',help='Save bridge, temple and shore-step construction views and exit')
    parser.add_argument('--player-review',action='store_true',help='Capture the new player walking/running at game resolution, plus an inspection-light costume pass')
    parser.add_argument('--gameplay-smoke',action='store_true',help='Exercise exploration, progress saves and scene editing in a hidden native window')
    parser.add_argument('--scene',type=Path,help='Use a separate authored scene file')
    parser.add_argument('--fixed-cameras',action='store_true',default=fixed_cameras,help='Play the three-shot camera walkthrough')
    assets=parser.add_mutually_exclusive_group()
    assets.add_argument('--living-assets',dest='living_assets',action='store_true',help='Use the rigged player and 3D willow (Raylib 5.5)')
    assets.add_argument('--classic-assets',dest='living_assets',action='store_false',help='Compare the capsule and tree billboards')
    parser.set_defaults(living_assets=living_assets)
    args=parser.parse_args();fixed_cameras=args.fixed_cameras
    if args.structure_review:args.smoke=True
    if args.player_review:
        args.smoke=True;args.living_assets=True;fixed_cameras=True
    if args.gameplay_smoke:
        args.smoke=True;args.living_assets=True;fixed_cameras=True
    gameplay_enabled=fixed_cameras and not (args.smoke and not args.gameplay_smoke)
    import g_temple_cameras as cameras
    if args.smoke:
        import faulthandler
        faulthandler.dump_traceback_later(30)
        print('VIEWER starting window',flush=True)
    if args.smoke:pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.TraceLogLevel.LOG_WARNING)
    pr.init_window(1440,810,'Moonlit water temple / fixed cameras' if fixed_cameras else 'Photo temple / live 3D comparison');pr.set_target_fps(60)
    if gameplay_enabled:pr.set_exit_key(pr.KEY_NULL)
    if args.gameplay_smoke:pr.set_target_fps(0)
    if args.smoke:print('VIEWER window ready',flush=True)
    arena=review_arena(game,pmap(dict(entities={},tile_map=game.make_tile_map(1,1,16,16),player_info=game.make_default_player(0,0,0))))
    arena=structure.prepare(arena)
    g_night.sync_collision(arena);tm=arena['tile_map'];props=arena['entities']['lake_props'];records=g_baked_assets.manifest()
    target=pr.load_render_texture(480,270);pr.set_texture_filter(target.texture,pr.TextureFilter.TEXTURE_FILTER_POINT)
    shader=pr.load_shader(str(ROOT/'shaders'/'temple_mesh.vs'),str(ROOT/'shaders'/'temple_mesh.fs'))
    if shader.id==pr.rl.rlGetShaderIdDefault():raise RuntimeError('Live mesh shader did not compile')
    shader.locs[pr.SHADER_LOC_MATRIX_MODEL]=pr.get_shader_location(shader,'matModel')
    shader.locs[pr.SHADER_LOC_MATRIX_NORMAL]=pr.get_shader_location(shader,'matNormal')
    locations={n:pr.get_shader_location(shader,n) for n in ('moonDirection','inspection','opacity','time','waterPass','lampCount','lamps')}
    def scalar(name,value):pr.set_shader_value(shader,locations[name],pr.ffi.new('float[]',[value]),pr.SHADER_UNIFORM_FLOAT)
    def integer(name,value):pr.set_shader_value(shader,locations[name],pr.ffi.new('int[]',[value]),pr.SHADER_UNIFORM_INT)
    models={};loaded_textures={}
    def load(name,path):
        if args.smoke:print('VIEWER loading '+name,flush=True)
        models[name]=temple_mesh_loader.load(path,shader,loaded_textures)
        if not models[name]:raise RuntimeError('Empty live mesh: '+name)
    def draw(name,position,angle=0.,scale=(1,1,1)):
        for model in models[name]:
            pr.draw_model_ex(model,position,pr.Vector3(0,1,0),angle,pr.Vector3(*scale),pr.WHITE)
    for name in records:load(name,ART/'models'/(name+'.obj'))
    load('terrain',build_terrain(tm,ROOT/'artifacts'/'temple-camera-trial'/'cache'))
    load('deck',g_temple_deck.write(tm,ROOT/'artifacts'/'temple-camera-trial'/'cache',ART))
    water=pr.load_model_from_mesh(pr.gen_mesh_plane(896,640,1,1));water.materials[0].shader=shader;models['water']=[water]
    # The existing trees remain billboards in this geometry experiment.
    tree=pr.load_texture(str(ROOT/'art'/'willow_tree_128.png'));pr.set_texture_filter(tree,pr.TEXTURE_FILTER_POINT)
    player_x,player_y=232.,334.;player_floor=None;azimuth=0.;elevation=30.;span=330.;inspection=False;roof_override=False;roof_alpha=1.;frame=0
    walk=cameras.Walkthrough();help_visible=True;living=None
    gameplay=None;editor=None;exploration_props=None;audio=None;smoke=None;status='';status_time=0.;rendered_revision=0
    def rebuild_layout(new_map):
        cache=ROOT/'artifacts'/'temple-camera-trial'/'cache'
        replacement={}
        try:
            for name,path in (('terrain',build_terrain(new_map,cache)),('deck',g_temple_deck.write(new_map,cache,ART))):
                replacement[name]=temple_mesh_loader.load(path,shader,loaded_textures)
        except Exception:
            for group in replacement.values():
                for model in group:pr.unload_model(model)
            raise
        # Install both new batches together; a failed load retains the old view.
        for name,group in replacement.items():
            for old in models[name]:pr.unload_model(old)
            models[name]=group
    try:
        if gameplay_enabled:
            from g_temple_scene import Scene,SCENE_FILE
            from g_temple_gameplay import Exploration
            from g_temple_editor import Editor
            from g_temple_exploration_view import Props,Audio,draw_ui
            scene=Scene.load(args.scene or SCENE_FILE)
            gameplay=Exploration(arena,scene);walk=gameplay.walk;arena=gameplay.arena
            import g_temple_layout
            if not g_temple_layout.authored(scene.document['layout']):rendered_revision=gameplay.geometry_revision
            editor=Editor(scene);exploration_props=Props(shader)
            if gameplay.spawn_error:
                editor.active=True;editor.status=gameplay.spawn_error;editor.focus=list(scene.document['spawn'])
            try:audio=Audio()
            except RuntimeError as exc:status='Audio unavailable: '+str(exc);status_time=6.
            if args.gameplay_smoke:
                from temple_exploration_smoke import Review
                smoke=Review(gameplay,editor,ROOT/'artifacts'/'temple-exploration')
        if args.living_assets:
            from g_temple_living import LivingScene
            living=LivingScene()
        while not pr.window_should_close():
            dt=min(.05,pr.get_frame_time());now=pr.get_time()
            if args.smoke and not args.gameplay_smoke:
                dt=.016;now=.5
                route_frame=frame%len(cameras.REVIEW_ROUTE)
                review_pass=frame//len(cameras.REVIEW_ROUTE) if args.player_review else 0
                if args.player_review:
                    inspection=review_pass==2
                    if route_frame==0:walk=cameras.Walkthrough()
                if not fixed_cameras:azimuth=0 if frame==0 else 25 if frame==1 else -30;inspection=frame==2
            if pr.is_key_pressed(pr.KEY_HOME) and not gameplay:
                azimuth=0.;elevation=30.;span=330.
                player_floor=None
                if fixed_cameras:walk=cameras.Walkthrough();roof_override=False
                else:player_x,player_y=232.,334.
                if living:living.yaw=90.;living.phase=0.;living.pose('idle',0.)
            if gameplay and not gameplay.modal and not editor.active and pr.is_key_pressed(pr.KEY_HOME):
                gameplay.set_position(*gameplay.scene.document['spawn']);gameplay.ensure_clear_position();player_floor=None
                if living:living.phase=0.;living.pose('idle',0.)
            if pr.is_key_pressed(pr.KEY_H):help_visible=not help_visible
            view_keys_enabled=not gameplay or (not gameplay.modal and not editor.active)
            if view_keys_enabled and pr.is_key_pressed(pr.KEY_L):inspection=not inspection
            if view_keys_enabled and pr.is_key_pressed(pr.KEY_R):roof_override=not roof_override
            running=pr.is_key_down(pr.KEY_LEFT_SHIFT) or pr.is_key_down(pr.KEY_RIGHT_SHIFT)
            old_position=(walk.x,walk.y) if fixed_cameras else (player_x,player_y)
            if fixed_cameras:
                keys={letter for letter,key in (('w',pr.KEY_W),('a',pr.KEY_A),('s',pr.KEY_S),('d',pr.KEY_D)) if pr.is_key_down(key)}
                if gameplay:
                    pressed={name for name in ('E','TAB','ENTER','ESCAPE','LEFT','RIGHT','UP','DOWN','R') if pr.is_key_pressed(getattr(pr,'KEY_'+name))}
                    if smoke:
                        dt=.05;keys,pressed,running=smoke.input()
                    editor_transition=pr.is_key_pressed(pr.KEY_F2) and not gameplay.modal
                    if editor_transition:
                        try:editor.toggle(gameplay)
                        except ValueError as exc:editor.status=str(exc)
                    if not editor.active and not gameplay.modal:
                        if 'ESCAPE' in pressed:break
                        try:
                            if pr.is_key_pressed(pr.KEY_F5):
                                gameplay.save();status='Progress saved.';status_time=3.
                            if pr.is_key_pressed(pr.KEY_F6):
                                gameplay.load();player_floor=None
                                if audio:audio.clear()
                                if living:living.phase=0.
                                status='Progress loaded.';status_time=3.
                        except (OSError,ValueError,KeyError,TypeError) as exc:
                            status='Cannot load/save: '+str(exc);status_time=5.
                    gameplay.tick(dt,keys,running,pressed,editor.active or editor_transition)
                    arena=gameplay.arena;tm=arena['tile_map'];props=arena['entities']['lake_props'];walk=gameplay.walk
                    now=gameplay.clock
                    if audio:
                        audio.update(gameplay,dt)
                        if smoke:smoke.audio_stats(audio.runtime['stats'])
                elif args.smoke:
                    walk.x,walk.y=cameras.REVIEW_ROUTE[route_frame];walk.director.update(walk.x,walk.y)
                    assert can_walk(tm,walk.x,walk.y),('Blocked route point',frame)
                    assert walk.director.active==cameras.REVIEW_SHOTS[route_frame],('Wrong camera',frame)
                else:
                    walk.step(keys,dt,lambda x,y:can_walk(tm,x,y),speed=GAIT_SETTINGS['run' if running else 'walk']['speed'] if living else (100. if running else 65.))
                player_x,player_y=walk.x,walk.y
            else:
                azimuth+=(int(pr.is_key_down(pr.KEY_E))-int(pr.is_key_down(pr.KEY_Q)))*45*dt
                elevation=max(15.,min(75.,elevation+(int(pr.is_key_down(pr.KEY_UP))-int(pr.is_key_down(pr.KEY_DOWN)))*35*dt))
                span=max(150.,min(560.,span-pr.get_mouse_wheel_move()*16))
                dx=int(pr.is_key_down(pr.KEY_D))-int(pr.is_key_down(pr.KEY_A));dy=int(pr.is_key_down(pr.KEY_S))-int(pr.is_key_down(pr.KEY_W));length=math.hypot(dx,dy)
                if length:
                    speed=GAIT_SETTINGS['run' if running else 'walk']['speed'] if living else 65.
                    dx*=speed*dt/length;dy*=speed*dt/length
                    if can_walk(tm,player_x+dx,player_y):player_x+=dx
                    if can_walk(tm,player_x,player_y+dy):player_y+=dy
            inside=400<=player_x<560 and 176<=player_y<272
            goal=0. if inside or roof_override else 1.;roof_alpha=max(goal,roof_alpha-dt/.3) if goal<roof_alpha else min(goal,roof_alpha+dt/.3)
            a=math.radians(azimuth);el=math.radians(elevation);focus=pr.Vector3(415,25,285)
            eye=pr.Vector3(focus.x+math.sin(a)*math.cos(el)*900,focus.y+math.sin(el)*900,focus.z+math.cos(a)*math.cos(el)*900)
            camera=pr.Camera3D(eye,focus,pr.Vector3(0,1,0),span,pr.CAMERA_ORTHOGRAPHIC)
            if fixed_cameras:
                shot=walk.director.shot
                camera=pr.Camera3D(pr.Vector3(*shot['eye']),pr.Vector3(*shot['target']),pr.Vector3(0,1,0),shot['span'],pr.CAMERA_ORTHOGRAPHIC)
                if args.smoke:roof_alpha=0. if inside else 1.
            if editor and editor.active:
                editor.update(gameplay,camera,dt)
                arena=gameplay.arena;tm=arena['tile_map']
                props=arena['entities']['lake_props']
                camera=editor.camera(camera)
                if editor.overhead:roof_alpha=0.
            if gameplay and rendered_revision!=gameplay.geometry_revision:
                rebuild_layout(tm);rendered_revision=gameplay.geometry_revision
                player_floor=None
                if smoke:smoke.mesh_rebuilds+=1
            if args.structure_review:
                eye,focus,extent=(((330,43,495),(330,10,335),110),
                                  ((330,100,445),(480,23,256),165),
                                  ((90,46,278),(162,7,334),66))[frame]
                camera=pr.Camera3D(pr.Vector3(*eye),pr.Vector3(*focus),pr.Vector3(0,1,0),extent,pr.CAMERA_ORTHOGRAPHIC)
                inspection=True
            scalar('inspection',float(inspection));scalar('time',now);scalar('opacity',1.);integer('waterPass',0)
            pr.set_shader_value(shader,locations['moonDirection'],pr.ffi.new('float[]',[-.45,.75,-.52]),pr.SHADER_UNIFORM_VEC3)
            lamps=[e for e in arena['entities']['emitters'].values() if e.get('type')=='fire'][:6]
            positions=[v for e in lamps for v in (e['position']['x'],e.get('base_height',16.)+42.,e['position']['y'])]
            integer('lampCount',len(lamps));pr.set_shader_value_v(shader,locations['lamps'],pr.ffi.new('float[]',positions),pr.SHADER_UNIFORM_VEC3,len(lamps))
            if living:
                living.environment(now,inspection,positions)
                if args.smoke and not args.gameplay_smoke:
                    if fixed_cameras:
                        previous=cameras.REVIEW_ROUTE[max(0,route_frame-1)]
                        dx,dz=player_x-previous[0],player_y-previous[1]
                        living.yaw=math.degrees(math.atan2(dx,dz)) if dx or dz else 90.
                    else:living.yaw=90.
                    review_clip='run' if args.player_review and review_pass==1 else 'idle' if args.player_review and review_pass==2 else 'walk'
                    living.pose(review_clip,route_frame*.13)
                elif fixed_cameras:
                    travel=gameplay.travel if gameplay else math.hypot(walk.x-old_position[0],walk.y-old_position[1])
                    if not gameplay or not gameplay.paused:
                        living.update(dt,walk.moving,walk.heading,travel,running)
                else:
                    travel_x,travel_y=player_x-old_position[0],player_y-old_position[1]
                    travel=math.hypot(travel_x,travel_y)
                    living.update(dt,travel>1e-6,(travel_x,travel_y),travel,running)
            pr.begin_texture_mode(target);pr.clear_background(pr.Color(3,7,12,255));pr.begin_mode_3d(camera)
            integer('waterPass',1);pr.draw_model(water,pr.Vector3(448,-.2,320),1.,pr.WHITE);integer('waterPass',0)
            draw('terrain',pr.Vector3(0,0,0))
            draw('deck',pr.Vector3(0,0,0))
            for identity,prop in props.items():
                if prop['kind']=='roof':continue
                if prop['kind']=='pile' and not identity.startswith('lantern-post:'):continue
                name=prop['asset'][6:]
                draw(name,pr.Vector3(*prop_origin(identity,prop,records)),prop.get('rotation_y',0.),prop.get('scale',(1,1,1)))
            for obj in arena['entities']['facades'].values():
                if fixed_cameras and shot.get('hide_front_facade',False):continue
                name=g_night.baked_facade_name(obj,obj.get('open',False));p=obj['position']
                draw(name,pr.Vector3(p['x'],obj.get('base_height',16.),p['y']))
            if exploration_props:exploration_props.draw(gameplay,editor.active)
            for e in lamps:
                p=e['position'];pr.draw_sphere(pr.Vector3(p['x'],e.get('base_height',16.)+19,p['y']),2.,pr.Color(255,150,50,255))
            for x in (138,686):
                if living:living.draw_willow(x,376,0. if x==138 else 83.)
                else:pr.draw_billboard(camera,tree,pr.Vector3(x,58,376),116,pr.Color(90,115,145,255) if not inspection else pr.WHITE)
            floor=structure.floor_height(tm,player_x,player_y)
            # Follow each low riser smoothly instead of teleporting up a whole
            # tile. This is root height following, not per-foot stair IK.
            player_floor=floor if player_floor is None or args.smoke else player_floor+(floor-player_floor)*(1-math.exp(-dt*24.))
            if args.smoke and fixed_cameras and not args.structure_review and not args.gameplay_smoke:
                for height in (floor+1,floor+29):
                    screen=pr.get_world_to_screen_ex(pr.Vector3(player_x,height,player_y),camera,480,270)
                    assert 8<screen.x<472 and 8<screen.y<262,('Player outside frame',frame,screen.x,screen.y)
            if living:living.draw_player(player_x,player_floor,player_y)
            else:pr.draw_capsule(pr.Vector3(player_x,player_floor+4,player_y),pr.Vector3(player_x,player_floor+24,player_y),3.,4,4,pr.Color(156,146,118,255))
            if roof_alpha>.001:
                scalar('opacity',roof_alpha);draw('roof',pr.Vector3(480,structure.TEMPLE_HEIGHT+64,208));scalar('opacity',1.)
            if editor and editor.active:editor.draw_world(tm)
            pr.end_mode_3d()
            status_time=max(0.,status_time-dt)
            if gameplay and not editor.active:draw_ui(gameplay,status if status_time>0 else '')
            pr.end_texture_mode()
            pr.begin_drawing();pr.clear_background(pr.BLACK)
            destination=pr.Rectangle(0,0,1440,810)
            if editor and editor.active:
                from g_temple_editor import VIEW_SCALE,VIEW_TOP
                destination=pr.Rectangle(0,VIEW_TOP,1140,270*VIEW_SCALE)
            pr.draw_texture_pro(target.texture,pr.Rectangle(0,0,480,-270),destination,pr.Vector2(0,0),0,pr.WHITE)
            if editor and editor.active:
                editor.draw_overlay(camera,tm,gameplay.assets)
            elif gameplay and help_visible:
                pr.draw_text(walk.director.shot['title'],18,18,18,pr.Color(198,189,164,255))
                pr.draw_text('WASD move | Shift run | E interact | Tab inventory | F5 save / F6 load | F2 edit level | H help | Esc quit',18,780,16,pr.Color(198,189,164,255))
            elif fixed_cameras and help_visible:
                pr.draw_text(walk.director.shot['title'],18,18,18,pr.Color(198,189,164,255))
                pr.draw_text('WASD move | Shift run | release keys to follow new view | H help | Home restart | L light | R roof',18,780,16,pr.Color(198,189,164,255))
            elif not fixed_cameras:
                pr.draw_text('LIVE MESH STUDY | WASD walk | Q/E orbit | arrows tilt | wheel zoom | R roof | L light | Home reset',12,12,16,pr.RAYWHITE)
                pr.draw_text('Shared tile collision; simplified lighting and water. Gameplay remains in the separate 2D scene.',12,786,14,pr.GRAY)
            if smoke and editor.active and smoke.capture:smoke.capture_ui()
            pr.end_drawing()
            if pr.is_key_pressed(pr.KEY_F12):
                folder=ROOT/'artifacts'/'temple-camera-trial' if fixed_cameras else ART/'review';folder.mkdir(parents=True,exist_ok=True)
                pr.take_screenshot(str(folder/('fixed-camera-user.png' if fixed_cameras else 'live-3d-user.png')))
            if smoke:
                smoke.after_frame(target,camera)
                frame+=1
                if smoke.done:break
            elif args.smoke:
                folder=ROOT/'artifacts'/'temple-camera-trial' if fixed_cameras else ART/'review';folder.mkdir(parents=True,exist_ok=True)
                prefix=('living-route' if living else 'route') if fixed_cameras else 'live-3d'
                if args.structure_review:prefix='structure'
                if args.player_review:prefix=('player-walk-night','player-run-night','player-costume-light')[review_pass]
                im=pr.load_image_from_texture(target.texture);pr.image_flip_vertical(im);pr.export_image(im,str(folder/f'{prefix}-{route_frame if args.player_review else frame}.png'));pr.unload_image(im)
                frame+=1
                if frame==(3 if args.structure_review else len(cameras.REVIEW_ROUTE)*(3 if args.player_review else 1) if fixed_cameras else 3):break
    finally:
        if smoke:smoke.close()
        if audio:audio.close()
        if exploration_props:exploration_props.close()
        if gameplay:
            import g_narrative_text
            g_narrative_text.unload(gameplay.assets)
        if living:living.close()
        # UnloadModel releases mesh/material arrays, but not their textures or the
        # shared shader. Track each uploaded material texture once.
        for group in models.values():
            for model in group:pr.unload_model(model)
        for tex in loaded_textures.values():pr.unload_texture(tex)
        pr.unload_texture(tree);pr.unload_render_texture(target);pr.unload_shader(shader);pr.close_window()
    if args.smoke:
        faulthandler.cancel_dump_traceback_later()
        print('Exploration and editor checks passed.' if args.gameplay_smoke else 'Player walk/run/night and costume-light passes rendered at 480x270.' if args.player_review else 'Bridge, temple and shore steps rendered.' if args.structure_review else 'Fixed-camera route rendered in both directions.' if fixed_cameras else 'Live 3D meshes rendered from three views; shared collision data loaded.')


if __name__=='__main__':run()
