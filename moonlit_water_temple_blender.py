"""Independent photo-textured Blender asset review, with optional normal lighting."""
import math
from moonlit_water_temple_photo import review_arena as photo_arena
import g_baked_assets


def review_arena(game,arena,normals=True):
    arena=photo_arena(game,arena);records=g_baked_assets.manifest();tm=arena['tile_map']
    for tile in tm['tiles']:
        if tile.get('surface_material') in ('wood','wall'):tile['surface_style']='blender_temple'
    tm['surface_revision']=tm.get('surface_revision',0)+1
    for obj in arena['entities']['facades'].values():obj.update(art_style='blender_temple',normal_lighting=normals)
    for identity,prop in arena['entities']['lake_props'].items():
        kind=prop['kind']
        name=('lantern_porcelain' if identity=='lantern:2' else 'lantern_paper') if identity.startswith('lantern:') else (
            'rail'+str(prop['width']) if kind=='rail' else 'pile'+str(prop['height']) if kind=='pile' else
            'lily_cluster' if prop.get('asset')=='photo:lily_cluster' else 'lily_leaves' if kind=='lily' else kind)
        if name not in records:raise ValueError('Unconverted temple prop: '+identity+' / '+name)
        rec=records[name];prop.update(asset='baked:'+name,width=rec['size'][0],height=rec['size'][1])
        prop.pop('response',None);prop.pop('emission',None)
        if name=='lantern_paper':prop['emission']='baked:lantern_paper_emission'
        if name=='roof':
            # Ground footprint and cutaway are unchanged. The roof sits above
            # the facade: geometry origin is behind its front eave and elevated.
            prop['geometry_offset']=(0.,-64.,64.)
        elif identity.startswith('lantern:'):
            # Image top is the suspension; convert its raised placement to
            # physical light height, keeping existing lantern/fire positions.
            bottom=prop.get('anchor_y',-prop['height'])+rec['pivot'][1]
            prop['geometry_offset']=(0.,0.,max(0.,-bottom)/math.cos(math.radians(30.)))
        else:prop['geometry_offset']=(0.,0.,0.)
        if normals:prop['geometry_asset']=name
    return arena.set('scene_name','moonlit_water_temple_blender')


def run():
    import argparse,g_main
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lighting',choices=('normals','flat'),default='normals')
    args=parser.parse_args();game=g_main.update_and_render_module;original=game.update_and_render;started=False
    def initialize(render,lighting,arena,assets,engine):
        nonlocal started
        if not started:
            arena=review_arena(game,arena,args.lighting=='normals')
            assets.setdefault('ui_state',game.g_ui.make_ui_state())['show_editor']=False
            assets.setdefault('editor_state',{})['surface_art_style']='blender_temple'
            camera=assets.setdefault('camera_3d',game.make_default_camera());camera.position.x=112.;camera.position.y=111.
            started=True
        return original(render,lighting,arena,assets,engine)
    game.update_and_render=initialize;g_main.g_main()


if __name__=='__main__':run()
