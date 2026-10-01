"""Opt-in Blender material maps; loaded once, sampled on the GPU per light."""
from pathlib import Path
from functools import lru_cache
import json
from PIL import Image
import pyray as pr

ROOT=Path(__file__).resolve().parent/'photo_asset_pipeline'/'temple3d'


@lru_cache(maxsize=1)
def manifest():return json.loads((ROOT/'manifest.json').read_text())['assets']


def image(name):
    with Image.open(ROOT/'runtime'/(name+'.png')) as source:return source.convert('RGBA')


def prepare(assets,name):
    import g_surfaces
    for collection,suffix in (('baked_normals','_normal'),('baked_positions','_position')):
        textures=assets.setdefault(collection,{})
        if name not in textures:textures[name]=g_surfaces.upload_image(image(name+suffix))


def policy(name,base,offset=(0.,0.,0.)):
    from g_render_order import make_texture_reference
    rec=manifest()[name]
    return dict(mode='normal_map',response_texture=make_texture_reference('baked_normals',name),
                position_texture=make_texture_reference('baked_positions',name),fallback_mode='none',
                strength=1.,minimum_direct=.07,normal_bands=6.,normal_specular=.12 if name=='lantern_porcelain' else 0.,
                normal_transmission=.4 if name=='lantern_paper' else .15 if name.startswith('lily') else 0.,
                geometry_min=rec['position_min'],geometry_max=rec['position_max'],
                geometry_origin=[base['x']+offset[0],base['y']+offset[1],offset[2]],
                geometry_view=[0.,-rec['depth_direction'][1],rec['depth_direction'][2]])


def unload(assets):
    for name in ('baked_normals','baked_positions'):
        for texture in assets.pop(name,{}).values():pr.unload_texture(texture)
