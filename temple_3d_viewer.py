"""Independent live-mesh art experiment. Shared scene data; not a gameplay port.

WASD walk (existing tile collision), Q/E orbit, arrows elevation, wheel zoom,
R roof cutaway, L inspection lighting, Home reset view, Esc quit. F12 screenshot.
"""
from pathlib import Path
import argparse,math,json
import pyray as pr
from pyrsistent import pmap
from PIL import Image
import g_update_and_render as game
import g_night,g_baked_assets,g_surfaces
import temple_mesh_loader
from moonlit_water_temple_blender import review_arena

ROOT=Path(__file__).resolve().parent
ART=g_baked_assets.ROOT


def build_terrain(tm):
    """One static mesh, grouped by material; cell data remains authoritative."""
    lines=['mtllib viewer_terrain.mtl'];offset=0
    for material in ('grass','planks_x','planks_y','wall_ground'):
        lines.extend(['o '+material,'usemtl '+material])
        for i,tile in enumerate(tm['tiles']):
            if tile.get('water'):continue
            kind=tile.get('surface_material','grass')
            mat=('planks_'+tile.get('surface_axis','x')) if kind=='wood' else 'wall_ground' if kind=='wall' else 'grass'
            if mat!=material:continue
            x=i%tm['map_width']*16;y=i//tm['map_width']*16
            z=tile.get('surface_elevation',0.)+(48. if kind=='wall' else 0.)
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
                    if neighbour_z<z:quads.append((vertices,normal))
            sw,sh=(128,32) if material=='planks_x' else (32,128) if material=='planks_y' else (48,32) if material=='wall_ground' else (64,64)
            for vertices,normal in quads:
                for k in (0,1,2,0,2,3):
                    p=vertices[k];lines.append('v %g %g %g'%p)
                    lines.append('vt %g %g'%(p[0]/sw,-(p[2] if normal[1] else p[1])/sh));lines.append('vn %g %g %g'%normal)
                lines.extend('f '+' '.join(f'{k}/{k}/{k}' for k in range(offset+n+1,offset+n+4)) for n in (0,3));offset+=6
    folder=ART/'models';target=folder/'viewer_terrain.obj';target.write_text('\n'.join(lines))
    g_surfaces.base_patch('grass',0,0,64,64).save(ART/'runtime'/'viewer_grass.png')
    (folder/'viewer_terrain.mtl').write_text('\n'.join('newmtl '+n+'\nKd 1 1 1\nmap_Kd ../runtime/'+('viewer_grass' if n=='grass' else n)+'.png\n' for n in ('grass','planks_x','planks_y','wall_ground')))
    return target


def can_walk(tm,x,y):
    # Use existing tile-shape collision, with a small body radius.
    for dx,dy in ((-3,-3),(3,-3),(-3,3),(3,3)):
        p=game.g_editor.world_to_tile_position(dict(x=x+dx,y=y+dy),tm)
        if not (0<=p['tile_x']<tm['map_width'] and 0<=p['tile_y']<tm['map_height']):return False
        if game.position_collides_within_tile_shape(p,tm):return False
    return True


def run():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
    if args.smoke:
        import faulthandler
        faulthandler.dump_traceback_later(30)
        print('VIEWER starting window',flush=True)
    if args.smoke:pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
    pr.set_trace_log_level(pr.TraceLogLevel.LOG_WARNING)
    pr.init_window(1440,810,'Photo temple / live 3D comparison');pr.set_target_fps(60)
    if args.smoke:print('VIEWER window ready',flush=True)
    arena=review_arena(game,pmap(dict(entities={},tile_map=game.make_tile_map(1,1,16,16),player_info=game.make_default_player(0,0,0))))
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
    def draw(name,position):
        for model in models[name]:pr.draw_model(model,position,1.,pr.WHITE)
    for name in records:load(name,ART/'models'/(name+'.obj'))
    load('terrain',build_terrain(tm))
    water=pr.load_model_from_mesh(pr.gen_mesh_plane(896,640,1,1));water.materials[0].shader=shader;models['water']=[water]
    # The existing trees remain billboards in this geometry experiment.
    tree=pr.load_texture(str(ROOT/'art'/'willow_tree_128.png'));pr.set_texture_filter(tree,pr.TEXTURE_FILTER_POINT)
    player_x,player_y=232.,334.;azimuth=0.;elevation=30.;span=330.;inspection=False;roof_override=False;roof_alpha=1.;frame=0
    try:
        while not pr.window_should_close():
            dt=min(.05,pr.get_frame_time());now=pr.get_time()
            if args.smoke:dt=.016;now=.5;azimuth=0 if frame==0 else 25 if frame==1 else -30;inspection=frame==2
            if pr.is_key_pressed(pr.KEY_HOME):azimuth=0.;elevation=30.;span=330.
            if pr.is_key_pressed(pr.KEY_L):inspection=not inspection
            if pr.is_key_pressed(pr.KEY_R):roof_override=not roof_override
            azimuth+=(int(pr.is_key_down(pr.KEY_E))-int(pr.is_key_down(pr.KEY_Q)))*45*dt
            elevation=max(15.,min(75.,elevation+(int(pr.is_key_down(pr.KEY_UP))-int(pr.is_key_down(pr.KEY_DOWN)))*35*dt))
            span=max(150.,min(560.,span-pr.get_mouse_wheel_move()*16))
            dx=int(pr.is_key_down(pr.KEY_D))-int(pr.is_key_down(pr.KEY_A));dy=int(pr.is_key_down(pr.KEY_S))-int(pr.is_key_down(pr.KEY_W));length=math.hypot(dx,dy)
            if length:
                dx*=65*dt/length;dy*=65*dt/length
                if can_walk(tm,player_x+dx,player_y):player_x+=dx
                if can_walk(tm,player_x,player_y+dy):player_y+=dy
            inside=400<=player_x<560 and 176<=player_y<272
            goal=0. if inside or roof_override else 1.;roof_alpha=max(goal,roof_alpha-dt/.3) if goal<roof_alpha else min(goal,roof_alpha+dt/.3)
            a=math.radians(azimuth);el=math.radians(elevation);focus=pr.Vector3(415,25,285)
            eye=pr.Vector3(focus.x+math.sin(a)*math.cos(el)*900,focus.y+math.sin(el)*900,focus.z+math.cos(a)*math.cos(el)*900)
            camera=pr.Camera3D(eye,focus,pr.Vector3(0,1,0),span,pr.CAMERA_ORTHOGRAPHIC)
            scalar('inspection',float(inspection));scalar('time',now);scalar('opacity',1.);integer('waterPass',0)
            pr.set_shader_value(shader,locations['moonDirection'],pr.ffi.new('float[]',[-.45,.75,-.52]),pr.SHADER_UNIFORM_VEC3)
            lamps=[e for e in arena['entities']['emitters'].values() if e.get('type')=='fire']
            positions=[v for e in lamps for v in (e['position']['x'],58.,e['position']['y'])]
            integer('lampCount',len(lamps));pr.set_shader_value_v(shader,locations['lamps'],pr.ffi.new('float[]',positions),pr.SHADER_UNIFORM_VEC3,len(lamps))
            pr.begin_texture_mode(target);pr.clear_background(pr.Color(3,7,12,255));pr.begin_mode_3d(camera)
            integer('waterPass',1);pr.draw_model(water,pr.Vector3(448,-.2,320),1.,pr.WHITE);integer('waterPass',0)
            draw('terrain',pr.Vector3(0,0,0))
            for identity,prop in props.items():
                if prop['kind']=='roof':continue
                name=prop['asset'][6:];p=prop['position'];offset=prop.get('geometry_offset',(0,0,0))
                height=(0 if prop['kind']=='lily' else 16.)+offset[2]
                if prop['kind']=='pile' and not identity.startswith('lantern-post:'):height=16-records[name]['position_max'][2]
                if identity=='lantern:2':height=16+records['pile54']['position_max'][2]
                if identity=='lantern:3':height=16+records['pile54']['position_max'][2]-records[name]['position_max'][2]
                draw(name,pr.Vector3(p['x']+offset[0],height,p['y']+offset[1]))
            for obj in arena['entities']['facades'].values():
                name=g_night.baked_facade_name(obj,obj.get('open',False));p=obj['position']
                draw(name,pr.Vector3(p['x'],16,p['y']))
            for e in lamps:
                p=e['position'];pr.draw_sphere(pr.Vector3(p['x'],35,p['y']),2.,pr.Color(255,150,50,255))
            for x in (138,686):pr.draw_billboard(camera,tree,pr.Vector3(x,58,376),116,pr.Color(90,115,145,255) if not inspection else pr.WHITE)
            tile=g_surfaces.cell(tm,int(player_x)//16,int(player_y)//16);floor=tile.get('surface_elevation',0.)
            pr.draw_capsule(pr.Vector3(player_x,floor+4,player_y),pr.Vector3(player_x,floor+24,player_y),3.,4,4,pr.Color(156,146,118,255))
            if roof_alpha>.001:
                scalar('opacity',roof_alpha);draw('roof',pr.Vector3(480,80,208));scalar('opacity',1.)
            pr.end_mode_3d();pr.end_texture_mode()
            pr.begin_drawing();pr.clear_background(pr.BLACK)
            pr.draw_texture_pro(target.texture,pr.Rectangle(0,0,480,-270),pr.Rectangle(0,0,1440,810),pr.Vector2(0,0),0,pr.WHITE)
            pr.draw_text('LIVE MESH STUDY | WASD walk | Q/E orbit | arrows tilt | wheel zoom | R roof | L light | Home reset',12,12,16,pr.RAYWHITE)
            pr.draw_text('Shared tile collision; simplified lighting and water. Gameplay remains in the separate 2D scene.',12,786,14,pr.GRAY)
            pr.end_drawing()
            if pr.is_key_pressed(pr.KEY_F12):pr.take_screenshot(str(ART/'review'/'live-3d-user.png'))
            if args.smoke:
                folder=ART/'review';folder.mkdir(exist_ok=True)
                im=pr.load_image_from_texture(target.texture);pr.image_flip_vertical(im);pr.export_image(im,str(folder/f'live-3d-{frame}.png'));pr.unload_image(im)
                frame+=1
                if frame==3:break
    finally:
        # UnloadModel releases mesh/material arrays, but not their textures or the
        # shared shader. Track each uploaded material texture once.
        for group in models.values():
            for model in group:pr.unload_model(model)
        for tex in loaded_textures.values():pr.unload_texture(tex)
        pr.unload_texture(tree);pr.unload_render_texture(target);pr.unload_shader(shader);pr.close_window()
    if args.smoke:
        faulthandler.cancel_dump_traceback_later()
        print('Live 3D meshes rendered from three views; shared collision data loaded.')


if __name__=='__main__':run()
