"""Geometric bake registration, lighting contracts and gameplay compatibility."""
import json,hashlib,math,unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
import g_baked_assets,g_graphics,g_night,g_surfaces,g_update_and_render as game
from moonlit_water_temple_blender import review_arena
from moonlit_water_temple_photo import review_arena as previous
from test_puzzles import make_arena
from test_entity_self_shadow import make_item,make_prepared_light,COLLISION_GRID

ROOT=g_baked_assets.ROOT


class BlenderAssetsTests(unittest.TestCase):
    def test_color_and_data_registration(self):
        for name,rec in g_baked_assets.manifest().items():
            color=np.asarray(g_baked_assets.image(name));mask=color[:,:,3]>0
            self.assertEqual((color.shape[1],color.shape[0]),tuple(rec['size']))
            self.assertLessEqual(len(np.unique(color[:,:,:3][mask],axis=0)),64,name)
            self.assertTrue(set(np.unique(color[:,:,3])).issubset({0,255}),name)
            for suffix,digest in rec['sha256'].items():
                self.assertEqual(hashlib.sha256((ROOT/'runtime'/(name+suffix+'.png')).read_bytes()).hexdigest(),digest)
            n=np.asarray(g_baked_assets.image(name+'_normal'));p=np.asarray(g_baked_assets.image(name+'_position'))
            self.assertEqual(n.shape,color.shape);self.assertEqual(p.shape,color.shape)
            self.assertTrue(np.all(n[~mask]==0));self.assertTrue(np.all(p[~mask]==0))
            normals=n[:,:,:3][mask].astype(float)/127.5-1
            self.assertLess(float(np.abs(np.linalg.norm(normals,axis=1)-1).max()),.012,name)

    def test_baked_positions_reproject_into_their_own_color_pixels(self):
        # Independent camera equation catches portrait camera-fit and Y-flip
        # errors which otherwise make plausible-looking, incorrectly aligned maps.
        for name,rec in g_baked_assets.manifest().items():
            color=np.asarray(g_baked_assets.image(name));mask=color[:,:,3]>0
            data=np.asarray(g_baked_assets.image(name+'_position'))[:,:,:3].astype(float)/255
            lo=np.array(rec['position_min']);hi=np.array(rec['position_max']);points=lo+data*(hi-lo)
            a=math.radians(rec['elevation']);yy,xx=np.mgrid[:mask.shape[0],:mask.shape[1]]
            x=rec['pivot'][0]+points[:,:,0];y=rec['pivot'][1]+points[:,:,1]*math.sin(a)-points[:,:,2]*math.cos(a)
            error=np.hypot(x-(xx+.5),y-(yy+.5))[mask]
            # A few silhouette pixels combine samples of separated front/back
            # surfaces. The bulk of visible coverage must remain subpixel aligned.
            self.assertLess(float(np.quantile(error,.9)),1.,name)

    def test_apertures_match_existing_art_and_collision(self):
        old=previous(game,make_arena());new=review_arena(game,make_arena())
        for key,obj in new['entities']['facades'].items():
            for opened in (False,True):
                a,ah=g_night.facade_art(old['entities']['facades'][key],opened)
                b,bh=g_night.facade_art(obj,opened)
                self.assertEqual(ah.tobytes(),bh.tobytes())
                self.assertEqual(a.getchannel('A').tobytes(),b.getchannel('A').tobytes())
        g_night.sync_collision(old);g_night.sync_collision(new)
        for a,b in zip(old['tile_map']['tiles'],new['tile_map']['tiles']):
            for key in ('index','shape_index','force_collidable','facade_blocked','surface_elevation','rain_exposure','acoustic_zone_id','surface_material','surface_axis'):
                self.assertEqual(a.get(key),b.get(key),key)
        self.assertEqual(old['world_sequences'],new['world_sequences'])
        self.assertEqual(old['entities']['brains'],new['entities']['brains'])
        self.assertEqual(old['entities']['emitters'],new['entities']['emitters'])

    def test_all_scene_props_are_converted_and_flat_comparison_is_available(self):
        lit=review_arena(game,make_arena());flat=review_arena(game,make_arena(),False)
        for key,prop in lit['entities']['lake_props'].items():
            self.assertTrue(prop['asset'].startswith('baked:'),key)
            self.assertIn(prop['geometry_asset'],g_baked_assets.manifest())
            self.assertNotIn('geometry_asset',flat['entities']['lake_props'][key])

    def test_floor_is_continuous_across_chunk_boundaries(self):
        tm=game.make_tile_map(12,8,16,16)
        for axis in ('x','y'):
            g_surfaces.paint(tm,[(x,y) for x in range(12) for y in range(8)],'wood',style='blender_temple',plank_axis=axis)
            full=g_surfaces.wood_layer(tm,0,0,192,128)
            for x in (0,64,128):
                for y in (0,64):self.assertEqual(full.crop((x,y,x+64,y+64)).tobytes(),g_surfaces.wood_layer(tm,x,y,64,64).tobytes())

    def test_each_light_keeps_its_real_height_in_normal_pass(self):
        item=make_item('roof',0,0,mode='normal_map');light=make_prepared_light('lamp',12,18,47)
        g_graphics.prepare_entity_self_shadows([item],[light],[],COLLISION_GRID)
        record=item['self_shadow_summary']['per_light'][0]
        per=g_graphics._make_per_light_render_item(item,record)
        self.assertEqual(per['self_shadow_summary']['geometry_light'],[12.,18.,47.])

    def test_missing_geometry_falls_back_without_affecting_other_sprites(self):
        texture=SimpleNamespace(width=16,height=16,id=1)
        item={'self_shadow':dict(mode='normal_map',fallback_mode='none',response_texture={'collection':'normal','name':'x'},position_texture={'collection':'position','name':'x'})}
        resources=g_graphics.resolve_entity_self_shadow_resources(item,texture,{'normal':{'x':texture}},False)
        self.assertEqual(resources['active_mode'],'none');self.assertTrue(resources['fallback_used'])
        resources=g_graphics.resolve_entity_self_shadow_resources(item,texture,{'normal':{'x':texture},'position':{'x':texture}},False)
        self.assertEqual(resources['active_mode'],'normal_map')


if __name__=='__main__':unittest.main()
