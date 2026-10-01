"""Photo-art comparison scene: python moonlit_water_temple_photo.py.

The original moonlit_water_temple.py remains the painted/procedural comparison.
The shared gameplay, weather, collision, reflections and roof fade are unchanged.
"""
import json
from pathlib import Path
from functools import lru_cache
from moonlit_water_temple import review_arena as painted_arena


@lru_cache(maxsize=1)
def roof_choices():
    return json.loads((Path(__file__).resolve().parent/'photo_asset_pipeline'/'blender'/'baked_assets.json').read_text())


def review_arena(game,arena,roof_angle=30):
    arena=painted_arena(game,arena);tm=arena['tile_map'];entities=arena['entities']
    for tile in tm['tiles']:
        if tile.get('surface_material') in ('wood','wall'):tile['surface_style']='photo_temple'
    tm['surface_revision']=tm.get('surface_revision',0)+1
    for facade in entities['facades'].values():facade['art_style']='photo_temple'
    for name,prop in entities['lake_props'].items():
        kind=prop['kind']
        if kind in ('roof','rail','column','pile'):
            prop['asset']='photo:'+kind
            if kind in ('roof','column'):prop['response']='photo:'+kind+'_response'
            if kind=='roof' and roof_angle!='photo':
                name='roof_blender_'+str(roof_angle);record=roof_choices()[name]
                prop.update(asset='photo:'+name,response='photo:'+name+'_response',
                            anchor_y=record['camera']['anchor_y'])
        elif kind=='lantern':
            prop.update(asset='photo:lantern_paper',emission='photo:lantern_paper_emission',
                        response='photo:lantern_paper_response',width=20,height=30)
            # The porcelain lantern is a floor/pedestal object, not hanging paper.
            if name=='lantern:2':
                prop.update(kind='ornament',asset='photo:lantern_porcelain',width=18,height=32,
                            anchor_y=-86,response='photo:lantern_porcelain_response')
                prop.pop('emission',None)
        elif kind=='lily':
            prop.update(asset='photo:'+('lily_cluster' if prop['asset']=='lily_flower' else 'lily_leaves'),
                        width=26,height=20)
    return arena.set('scene_name','moonlit_water_temple_photo')


def run():
    import argparse
    parser=argparse.ArgumentParser(description='Photo-derived water temple / Blender roof review')
    parser.add_argument('--roof-angle',choices=('30','40','50','photo'),default='30',
                        help='Orthographic roof elevation; photo retains the original rejected cutout for comparison.')
    args=parser.parse_args()
    import g_main
    game=g_main.update_and_render_module;original=game.update_and_render;started=False
    def initialize(render,lighting,arena,assets,engine):
        nonlocal started
        if not started:
            arena=review_arena(game,arena,args.roof_angle)
            assets.setdefault('ui_state',game.g_ui.make_ui_state())['show_editor']=False
            assets.setdefault('editor_state',{})['surface_art_style']='photo_temple'
            camera=assets.setdefault('camera_3d',game.make_default_camera())
            camera.position.x=112.;camera.position.y=111.
            started=True
        return original(render,lighting,arena,assets,engine)
    game.update_and_render=initialize;g_main.g_main()


if __name__=='__main__':run()
