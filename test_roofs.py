"""Independent roof authoring, cutaway membership and true facade apertures."""
import copy
import pickle
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
import g_roofs as roofs
import g_night as night
import g_editor
import g_editor_history as history
import g_effects
import g_update_and_render as game
from test_puzzles import make_arena


class RoofTests(unittest.TestCase):
    def test_paint_preserves_gameplay_and_removing_restores_authored_exposure(self):
        tm=game.make_tile_map(4,4,16,16)
        tile=tm['tiles'][5]
        tile.update(index=2,force_collidable=True,surface_material='wood',rain_exposure=.7,
                    acoustic_zone_id=3,footstep_overlay='water')
        original=copy.deepcopy(tile)
        self.assertEqual(roofs.paint(tm,[(1,1),(1,1),(-1,0)]),1)
        self.assertEqual({k:tile[k] for k in original},original)
        self.assertEqual(g_effects.get_tile_rain_exposure(tile),0.)
        revision=tm['roof_revision']
        self.assertEqual(roofs.paint(tm,[(1,1)]),0)
        self.assertEqual(tm['roof_revision'],revision)
        self.assertEqual(roofs.paint(tm,[(1,1)],'none'),1)
        self.assertEqual(tile,original)
        self.assertEqual(g_effects.get_tile_rain_exposure(tile),.7)

    def test_connected_roof_crosses_floor_finishes_but_not_diagonal_gaps(self):
        tm=game.make_tile_map(5,5,16,16)
        tm['tiles'][7]['surface_material']='ceramic'
        roofs.paint(tm,[(1,1),(2,1),(3,2)])
        groups,lookup=roofs.layout(tm)
        self.assertEqual(len(groups),2)
        self.assertEqual(lookup[6],lookup[7])
        self.assertNotEqual(lookup[7],lookup[13])
        self.assertEqual(groups[0]['bounds'],dict(x=16,y=-28,width=32,height=16))
        self.assertEqual(groups[0]['sort_y'],31.5)

    def test_flood_follows_floor_when_bare_and_roof_when_covered(self):
        tm=game.make_tile_map(5,5,16,16)
        for i in (6,7,8):tm['tiles'][i]['surface_material']='wood'
        self.assertEqual(roofs.flood(tm,1,1),3)
        tm['tiles'][7]['surface_material']='ceramic'
        self.assertEqual(roofs.flood(tm,1,1,'none'),3)
        roofs.paint(tm,[(1,1),(2,1),(3,1)])
        roofs.paint(tm,[(2,1)],'none')
        self.assertEqual(len(roofs.layout(tm)[0]),2)

    def test_cutaway_uses_player_feet_and_only_the_occupied_building(self):
        tm=game.make_tile_map(8,8,16,16)
        roofs.paint(tm,[(2,3),(2,4),(5,3)])
        lookup=roofs.layout(tm)[1]
        # Torso is above the roof footprint; feet are inside it.
        player={'position':{'x':40.,'y':35.},'render_base_offset':{'x':0.,'y':14.}}
        self.assertEqual(roofs.player_region(tm,lookup,player),26)
        player['position']['y']=34.
        self.assertEqual(roofs.player_region(tm,lookup,player),26)
        player['position']['y']=33.9
        self.assertIsNone(roofs.player_region(tm,lookup,player))
        player['position'].update(x=88.,y=35.)
        self.assertEqual(roofs.player_region(tm,lookup,player),29)
        player['position']['x']=-1.
        self.assertIsNone(roofs.player_region(tm,lookup,player))

    def test_cache_survives_entry_exit_and_releases_on_edit_or_map_replacement(self):
        tm=game.make_tile_map(8,8,16,16);roofs.paint(tm,[(2,3),(5,3)])
        assets={};player={'position':{'x':40.,'y':100.}}
        with patch.object(roofs.g_surfaces,'upload_image',side_effect=lambda im:object()) as upload, patch.object(roofs.pr,'unload_texture') as unload:
            roofs.prepare(assets,tm,player)
            self.assertEqual(len(roofs.render_items(assets)),2)
            first=assets['roof_runtime']
            player['position']['y']=35.
            roofs.prepare(assets,tm,player,dt=roofs.FADE_SECONDS)
            self.assertIs(assets['roof_runtime'],first)
            self.assertEqual(len(roofs.render_items(assets)),1)
            self.assertEqual(upload.call_count,2)
            self.assertEqual(unload.call_count,0)
            roofs.prepare(assets,tm,player,'tile')
            self.assertEqual(roofs.render_items(assets),[])
            assets['editor_state']={'roof_preview':True}
            roofs.prepare(assets,tm,player,'tile')
            self.assertEqual(len(roofs.render_items(assets)),2)
            roofs.paint(tm,[(5,3)],'none');roofs.prepare(assets,tm,player)
            self.assertEqual(unload.call_count,2)
            roofs.prepare(assets,game.make_tile_map(8,8,16,16),player)
            self.assertEqual(unload.call_count,3)
            self.assertFalse(assets['roof_textures'])
            roofs.unload(assets)
            self.assertNotIn('roof_runtime',assets)

    def test_fade_is_reversible_frame_rate_independent_and_does_not_rebuild(self):
        tm=game.make_tile_map(8,8,16,16);roofs.paint(tm,[(2,3),(5,3)])
        player={'position':{'x':40.,'y':100.}};assets={}
        with patch.object(roofs.g_surfaces,'upload_image',return_value=object()) as upload:
            roofs.prepare(assets,tm,player)
            player['position']['y']=35.
            roofs.prepare(assets,tm,player,dt=roofs.FADE_SECONDS/2)
            items=roofs.render_items(assets)
            self.assertAlmostEqual(items[0]['opacity'],.5)
            self.assertEqual(items[1]['opacity'],1.,'other building fades too')
            roofs.prepare(assets,tm,player,dt=0.)
            self.assertAlmostEqual(roofs.render_items(assets)[0]['opacity'],.5)
            player['position']['y']=100.
            roofs.prepare(assets,tm,player,dt=roofs.FADE_SECONDS/4)
            self.assertAlmostEqual(roofs.render_items(assets)[0]['opacity'],.84375)
            roofs.prepare(assets,tm,player,dt=roofs.FADE_SECONDS)
            self.assertEqual(roofs.render_items(assets)[0]['opacity'],1.)
            player['position']['y']=35.
            for _ in range(15):roofs.prepare(assets,tm,player,dt=roofs.FADE_SECONDS/30)
            self.assertAlmostEqual(roofs.render_items(assets)[0]['opacity'],.5)
            roofs.prepare(assets,tm,player,dt=roofs.FADE_SECONDS)
            self.assertEqual(len(roofs.render_items(assets)),1)
            self.assertEqual(upload.call_count,2,'fade uploads textures')

    def test_loading_inside_starts_hidden_without_an_initial_flash(self):
        tm=game.make_tile_map(8,8,16,16);roofs.paint(tm,[(2,3)])
        player={'position':{'x':40.,'y':35.}};assets={}
        with patch.object(roofs.g_surfaces,'upload_image',return_value=object()):
            roofs.prepare(assets,tm,player,dt=.016)
            self.assertEqual(roofs.render_items(assets),[])
            player['position']['y']=100.
            roofs.prepare(assets,tm,player,dt=roofs.FADE_SECONDS/2)
            self.assertAlmostEqual(roofs.render_items(assets)[0]['opacity'],.5)
            roofs.prepare(assets,tm,player,'tile',dt=.016)
            self.assertEqual(roofs.render_items(assets),[])
            roofs.prepare(assets,tm,player,'play',dt=.016)
            self.assertEqual(roofs.render_items(assets)[0]['opacity'],1.)

    def test_save_and_undo_preserve_roof_layer(self):
        arena=make_arena().set('editor_mode','tile');tm=arena['tile_map']
        editor=g_editor.make_editor_state();assets={'editor_state':editor};h=history.state(assets)
        before=history.snapshot(arena,editor,'tile')
        roofs.paint(tm,[(2,3)],height=52)
        history.record(h,before,history.snapshot(arena,editor,'tile'))
        restored=pickle.loads(pickle.dumps(arena))
        self.assertEqual(restored['tile_map']['tiles'][92]['roof_height'],52)
        revision=tm['roof_revision']
        arena=history.undo(arena,assets)
        self.assertNotIn('roof_material',arena['tile_map']['tiles'][92])
        self.assertGreater(arena['tile_map']['roof_revision'],revision)

    def test_editor_drag_interpolates_roof_cells_without_painting_floor(self):
        tm=game.make_tile_map(8,2,16,16);editor=g_editor.make_editor_state()
        editor.update(tile_edit_mode='roofs',roof_height=40)
        with patch.object(game.g_ui,'interactive_mouse_left_down',return_value=True):
            for x in (0,7):
                game.update_tile_editor_paint(editor,tm,SimpleNamespace(x=x,y=0),2,3,True,1.,0,'none')
        self.assertTrue(all(t.get('roof_height')==40 for t in tm['tiles'][:8]))
        self.assertTrue(all(t['index']==0 for t in tm['tiles']))


class ApertureTests(unittest.TestCase):
    def test_window_door_and_damage_reveal_actual_scene_without_emission_fill(self):
        for kind,opened in (('window_wall',False),('pierced_door',False),('pierced_door',True)):
            with self.subTest(kind=kind,opened=opened):
                obj=night.make_facade({'x':0.,'y':0.},kind)
                panel,holes=night.facade_art(obj,opened)
                emission=night.aperture_emission(panel,holes,dict(enabled=True,intensity=2.,color=[1.,.4,.1]))
                background=Image.new('RGBA',panel.size,(10,123,67,255))
                composed=Image.alpha_composite(Image.alpha_composite(background,panel),emission)
                self.assertGreater(sum(holes.getdata()),0)
                for h,p,e,c in zip(holes.getdata(),panel.getdata(),emission.getdata(),composed.getdata()):
                    if h:
                        self.assertEqual(p[3],0)
                        self.assertEqual(e[3],0)
                        self.assertEqual(c,(10,123,67,255))
                    else:self.assertEqual(p[3],255)


if __name__=='__main__':unittest.main()
