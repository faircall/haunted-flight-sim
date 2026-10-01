"""Photo sprite contracts and compatibility with the existing tile/portal model."""
import copy,hashlib,json,pickle,unittest
from pathlib import Path
import numpy as np
from PIL import Image
import g_night,g_surfaces,g_update_and_render as game
from test_puzzles import make_arena
from moonlit_water_temple import review_arena as painted
from moonlit_water_temple_photo import review_arena as photo
from photo_asset_pipeline.build import pixels

ROOT=Path(__file__).resolve().parent/'photo_asset_pipeline'


class PhotoAssetTests(unittest.TestCase):
    def test_sources_and_runtime_palette_contract(self):
        records=json.loads((ROOT/'manifest.json').read_text())['assets'];checked=set()
        for name,record in records.items():
            im=Image.open(ROOT/'runtime'/(name+'.png'));a=np.asarray(im)
            self.assertEqual(im.size,tuple(record['runtime_size']))
            self.assertLessEqual(len(np.unique(a[:,:,:3][a[:,:,3]>0],axis=0)),64,name)
            self.assertTrue(set(np.unique(a[:,:,3])).issubset({0,255}),name)
            self.assertTrue(np.all(a[a[:,:,3]==0]==0),name)
            self.assertEqual(hashlib.sha256((ROOT/'runtime'/(name+'.png')).read_bytes()).hexdigest(),record['sha256'])
            for source in record['sources']:
                if source in checked:continue
                checked.add(source);metadata=json.loads((ROOT/'sources'/source/'source.json').read_text(encoding='utf8'))
                self.assertIn('CC0',metadata['licence'])
                self.assertTrue(metadata['rights_url'].startswith('https://'))
                self.assertEqual(hashlib.sha256((ROOT/metadata['original_file']).read_bytes()).hexdigest(),metadata['sha256'])

    def test_premultiplied_resize_does_not_import_background_colour(self):
        im=Image.new('RGBA',(16,16),(0,0,255,0))
        for y in range(4,12):
            for x in range(4,12):im.putpixel((x,y),(240,90,30,255))
        out=np.asarray(pixels(im,(5,5),32));visible=out[out[:,:,3]>0]
        self.assertTrue(np.all(visible[:,0]>235))
        self.assertTrue(np.all(visible[:,2]<35))

    def test_separate_scene_preserves_gameplay_and_original_scene(self):
        old=painted(game,make_arena());before=pickle.dumps(old);new=photo(game,old)
        self.assertEqual(pickle.dumps(old),before)
        self.assertEqual(new['scene_name'],'moonlit_water_temple_photo')
        for a,b in zip(old['tile_map']['tiles'],new['tile_map']['tiles']):
            for key in ('index','shape_index','water','force_collidable','surface_elevation','rain_exposure','surface_material','surface_axis','acoustic_zone_id'):
                self.assertEqual(a.get(key),b.get(key),key)
        self.assertEqual(old['world_sequences'],new['world_sequences'])
        self.assertEqual(old['entities']['emitters'],new['entities']['emitters'])
        self.assertEqual(old['lake_profile'],new['lake_profile'])

    def test_facade_apertures_identical_for_both_art_sets(self):
        for kind in g_night.KINDS:
            facade=g_night.make_facade(dict(x=48.,y=56.),kind)
            for opened in (False,True):
                old,holes=g_night.facade_art(facade,opened)
                new,new_holes=g_night.facade_art(dict(facade,art_style='photo_temple'),opened)
                self.assertEqual(holes.tobytes(),new_holes.tobytes())
                self.assertEqual(old.getchannel('A').tobytes(),new.getchannel('A').tobytes())
                self.assertNotEqual(old.tobytes(),new.tobytes())

    def test_photo_planks_remain_registered_across_chunk_boundaries(self):
        tm=game.make_tile_map(12,8,16,16)
        for axis in ('x','y'):
            g_surfaces.paint(tm,[(x,y) for x in range(12) for y in range(8)],'wood',style='photo_temple',plank_axis=axis)
            whole=g_surfaces.wood_layer(tm,0,0,192,128)
            for x in (0,64,128):
                for y in (0,64):
                    self.assertEqual(whole.crop((x,y,x+64,y+64)).tobytes(),g_surfaces.wood_layer(tm,x,y,64,64).tobytes())
        self.assertNotEqual(g_surfaces.plank_sample('x','temple').tobytes(),g_surfaces.plank_sample('x','photo_temple').tobytes())

    def test_response_alpha_is_the_right_channel_not_sprite_alpha(self):
        for name in ('roof','lantern_paper','lantern_porcelain','column','roof_blender_30','roof_blender_40','roof_blender_50'):
            sprite=Image.open(ROOT/'runtime'/(name+'.png'));packed=Image.open(ROOT/'runtime'/(name+'_response.png'))
            self.assertEqual(sprite.size,packed.size)
            self.assertNotEqual(sprite.getchannel('A').tobytes(),packed.getchannel('A').tobytes())
            self.assertEqual(packed.getchannel('A').tobytes(),Image.open(ROOT/'responses'/name/'right.png').tobytes())

    def test_roof_angles_share_front_eave_alignment_and_gameplay(self):
        records=json.loads((ROOT/'blender'/'baked_assets.json').read_text())
        original=photo(game,make_arena(),'photo');reference=original['entities']['lake_props']['roof']
        for angle in (30,40,50):
            arena=photo(game,make_arena(),angle);roof=arena['entities']['lake_props']['roof']
            self.assertEqual(roof['cutaway'],reference['cutaway'])
            self.assertEqual(roof['position'],reference['position'])
            self.assertEqual(arena['tile_map']['tiles'],original['tile_map']['tiles'])
            record=records['roof_blender_'+str(angle)]
            self.assertAlmostEqual(roof['position']['y']+roof['anchor_y']+record['camera']['front_fascia_pixel'],232.,delta=.5)
            self.assertEqual(record['camera']['projection'],'ORTHO')

    def test_blender_light_profiles_have_correct_left_right_orientation(self):
        for angle in (30,40,50):
            name='roof_blender_'+str(angle);mask=np.asarray(Image.open(ROOT/'runtime'/(name+'.png')))[:,:,3]>0
            profile=np.asarray(Image.open(ROOT/'runtime'/(name+'_response.png'))).astype(float)
            self.assertTrue(np.all(profile[~mask]==0))
            half=mask.shape[1]//2
            left=profile[:,:half][mask[:,:half]];right=profile[:,half:][mask[:,half:]]
            self.assertGreater(left[:,2].mean(),right[:,2].mean()+5.)
            self.assertGreater(right[:,3].mean(),left[:,3].mean()+5.)

    def test_baked_normals_are_unit_vectors_and_share_sprite_coverage(self):
        for angle in (30,40,50):
            normal=np.asarray(Image.open(ROOT/'blender'/'renders'/f'normal_{angle}_native.png'))
            alpha=Image.open(ROOT/'runtime'/f'roof_blender_{angle}.png').getchannel('A')
            self.assertTrue(np.array_equal(normal[:,:,3],np.asarray(alpha)))
            vectors=normal[:,:,:3][normal[:,:,3]>0].astype(float)/127.5-1.
            self.assertTrue(np.all(np.abs(np.linalg.norm(vectors,axis=1)-1.)<.012))


if __name__=='__main__':unittest.main()
