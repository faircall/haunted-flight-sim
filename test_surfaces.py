"""Region authoring, seam continuity, persistence and cache regression checks."""
import copy
import pickle
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
import g_surfaces as s
import g_audio
import g_editor
import g_editor_history as history
import g_update_and_render as game
from test_puzzles import make_arena


class SurfaceTests(unittest.TestCase):
    def test_paint_erase_preserve_geometry_zones_and_restore_audio(self):
        tm=game.make_tile_map(4,4,16,16)
        tile=s.cell(tm,1,1)
        tile.update(index=4,shape_index=3,force_collidable=True,acoustic_zone_id=2,
                    rain_exposure=.3,footstep_overlay='water',decals=[{'type':'blood'}])
        original=copy.deepcopy(tile)
        s.paint(tm,[(1,1),(-1,0),(4,1)],'grass',seed=42)
        self.assertEqual(g_audio.get_tile_audio_surface(tm,{'x':24,'y':24}),'grass')
        self.assertEqual(tm['geometry_revision'],0)
        self.assertEqual({k:tile[k] for k in original},original)
        s.paint(tm,[(1,1)],'erase')
        self.assertEqual(tile,original)
        self.assertEqual(g_audio.get_tile_audio_surface(tm,{'x':24,'y':24}),'wood')

    def test_paint_order_and_pickle_reproduce_same_pixels(self):
        a=game.make_tile_map(8,8,16,16);b=copy.deepcopy(a)
        points=[(x,y) for y in range(8) for x in range(8)]
        s.paint(a,points,'dirt',seed=7)
        for point in reversed(points):s.paint(b,[point],'dirt',seed=7)
        b=pickle.loads(pickle.dumps(b))
        self.assertEqual(s.bake_chunk(a,0,0)[0].tobytes(),s.bake_chunk(b,0,0)[0].tobytes())

    def test_chunked_render_equals_one_large_bake(self):
        tm=game.make_tile_map(12,12,16,16)
        s.paint(tm,[(x,y) for y in range(12) for x in range(12)],'dirt',density=1)
        s.paint(tm,[(x,y) for y in range(1,8) for x in range(2,6)],'grass',density=1)
        s.paint(tm,[(x,y) for y in range(5,8) for x in range(5,8)],'wood',soft=False)
        stitched=Image.new('RGBA',(128,128));small_grass=[]
        for y in range(2):
            for x in range(2):
                im,grass=s.bake_chunk(tm,x,y);stitched.paste(im,(x*64,y*64));small_grass+=grass
        with patch.object(s,'CHUNK',8):whole,grass=s.bake_chunk(tm,0,0)
        self.assertEqual(stitched.tobytes(),whole.tobytes())
        self.assertEqual(sorted((x,y) for x,y,*_ in small_grass),sorted((x,y) for x,y,*_ in grass))
        self.assertEqual(stitched.crop((8,8,120,120)).getchannel('A').getextrema(),(255,255))

    def test_rounded_stencil_corners_square_edges_and_neighbor_invalidation(self):
        tm=game.make_tile_map(16,16,16,16)
        s.paint(tm,[(3,3)],'grass',soft=True)
        fields,crop,_=s.masks(tm,0,0)
        rounded=fields['grass'].crop(crop)
        self.assertEqual(rounded.getpixel((48,48)),0)
        self.assertEqual(rounded.getpixel((56,56)),255)
        self.assertEqual(set(rounded.getdata()),{0,255})
        far=s.signature(tm,3,3);near=s.signature(tm,1,0)
        s.paint(tm,[(4,3)],'grass')
        self.assertEqual(far,s.signature(tm,3,3));self.assertNotEqual(near,s.signature(tm,1,0))
        s.paint(tm,[(3,3)],'grass',soft=False)
        fields,crop,_=s.masks(tm,0,0)
        self.assertEqual(fields['grass'].crop(crop).getpixel((48,48)),255)
        self.assertEqual(fields['grass'].crop(crop).getpixel((47,48)),0)

    def test_material_junctions_have_one_owner_and_no_mixed_colors(self):
        tm=game.make_tile_map(8,8,16,16)
        s.paint(tm,[(x,y) for y in range(8) for x in range(8)],'dirt',density=0)
        s.paint(tm,[(1,1),(2,1),(1,2)],'grass',density=0)
        s.paint(tm,[(3,1),(3,2)],'wood',density=0)
        s.paint(tm,[(2,2),(2,3),(3,3)],'carpet',density=0)
        fields,crop,_=s.masks(tm,0,0)
        masks={kind:list(mask.crop(crop).getdata()) for kind,mask in fields.items() if kind!='_coverage'}
        coverage=list(fields['_coverage'].crop(crop).getdata())
        bases={kind:list(s.base_patch(kind,0,0,64,64).getdata()) for kind in masks}
        rendered,grass=s.bake_chunk(tm,0,0)
        self.assertFalse(grass)
        self.assertTrue(all(set(values)<={0,255} for values in masks.values()))
        for index,pixel in enumerate(rendered.getdata()):
            owners=[kind for kind,values in masks.items() if values[index]]
            self.assertEqual(len(owners),int(coverage[index]==255))
            if owners:
                self.assertEqual(pixel,bases[owners[0]][index])
            else:
                self.assertEqual(pixel[3],0)
        self.assertEqual(rendered.crop((8,8,60,60)).getchannel('A').getextrema(),(255,255))

    def test_square_triangle_stencils_keep_authored_geometry(self):
        tm=game.make_tile_map(4,4,16,16)
        s.paint(tm,[(1,1)],'wood',soft=False)
        s.cell(tm,1,1)['shape_index']=1
        fields,crop,_=s.masks(tm,0,0)
        mask=fields['wood'].crop(crop)
        self.assertEqual(mask.getpixel((16,16)),255)
        self.assertEqual(mask.getpixel((31,31)),0)
        self.assertEqual(mask.getpixel((31,16)),255)

    def test_flood_stops_at_unpainted_geometry_and_material_boundaries(self):
        tm=game.make_tile_map(5,5,16,16)
        for y in range(5):s.cell(tm,2,y)['force_collidable']=True
        self.assertEqual(s.flood(tm,0,0,'dirt'),10)
        self.assertEqual(s.material_at(tm,56,8),'erase')
        self.assertEqual(s.flood(tm,0,0,'grass'),10)
        self.assertEqual(s.flood(tm,-1,0,'grass'),0)

    def test_material_brush_interpolates_and_undo_restores_scalars(self):
        arena=make_arena();tm=arena['tile_map'];editor={'tile_edit_mode':'materials','surface_brush':3,'surface_material':'grass'}
        before=history.snapshot(arena,editor,'tile')
        with patch.object(game.g_ui,'interactive_mouse_left_down',return_value=True):
            for x in (2,6):
                game.update_tile_editor_paint(editor,tm,SimpleNamespace(x=x,y=3),4,3,True,1.,0,'none')
        for x in range(1,8):
            for y in range(2,5):
                self.assertEqual(s.cell(tm,x,y)['surface_material'],'grass')
                self.assertEqual(s.cell(tm,x,y)['index'],0)
        after=history.snapshot(arena,editor,'tile')
        history.apply(arena,editor,history.differences(before,after))
        self.assertTrue(all('surface_material' not in t for t in tm['tiles']))

    def test_impacts_are_bounded_and_preserve_other_decals(self):
        tm=game.make_tile_map(2,2,16,16)
        s.paint(tm,[(1,0)],'wall')
        s.cell(tm,1,0)['decals']=[{'type':'blood'}]
        for _ in range(20):s.add_impact(tm,{'x':15.9,'y':8.},{'x':100.,'y':0.})
        self.assertEqual(len(s.cell(tm,1,0)['decals']),13)
        self.assertEqual(s.cell(tm,1,0)['decals'][0],{'type':'blood'})

    def test_stationary_cache_reuses_resources_and_erase_releases(self):
        tm=game.make_tile_map(12,8,16,16);assets={};camera=SimpleNamespace(x=0,y=0)
        s.paint(tm,[(1,1)],'dirt')
        with patch.object(s,'upload_image',return_value=object()),patch.object(s,'build_grass_mesh',return_value=None),patch.object(s,'free_chunk') as free:
            s.prepare(assets,tm,camera)
            with patch.object(s,'bake_chunk',side_effect=AssertionError('unnecessary bake')),patch.object(s,'signature',side_effect=AssertionError('unnecessary scan')):
                s.prepare(assets,tm,camera)
            old_chunks=dict(assets['surface_runtime']['chunks'])
            assets['surface_runtime'].pop('mask_version')
            s.prepare(assets,tm,camera)
            self.assertTrue(all(c is not old_chunks[k] for k,c in assets['surface_runtime']['chunks'].items()))
            s.paint(tm,[(1,1)],'erase');s.prepare(assets,tm,camera)
            self.assertFalse(assets['surface_runtime']['chunks']);self.assertTrue(free.called)

    def test_material_controls_capture_the_seed_field_before_paint(self):
        ui={'mouse_captured':False};editor={'tile_edit_mode':'materials'}
        with patch.object(game.g_ui,'get_mouse_position',return_value=SimpleNamespace(x=350,y=162)):
            self.assertTrue(g_editor.capture_editor_ui_regions(ui,editor,'tile'))


if __name__=='__main__':unittest.main()
