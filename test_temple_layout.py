"""Blockout authoring, shared collision/heights/audio, and editor ownership."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import g_audio
import g_temple_layout as layout
import g_temple_deck as deck
import g_temple_structure as structure
import g_temple_editor as editor_module
from g_temple_editor import Editor, ground_point, VIEW_SCALE, VIEW_TOP
from g_temple_scene import Scene
from test_temple_exploration import exploration


class LayoutTests(unittest.TestCase):
    def test_legacy_scene_keeps_exact_floor_mesh_and_tile_sources(self):
        g=exploration()
        original=g.base_tile_map
        self.assertFalse(layout.authored(g.scene.document['layout']))
        self.assertEqual(deck.layout(original),deck.layout(g.arena['tile_map']))
        self.assertEqual(original['tile_types'],g.arena['tile_map']['tile_types'])
        for x,z in ((128,334),(146,334),(168,334),(480,294),(480,282),(480,250)):
            self.assertEqual(structure.floor_height(original,x,z),structure.floor_height(g.arena['tile_map'],x,z))

    def test_floor_material_height_collision_and_audio_stay_together(self):
        g=exploration()
        baseline=deepcopy(g.base_tile_map)
        for material in ('wood','stone','grass','wall','water'):
            layout.paint(g.scene,[512,320],[543,351],material,16)
            g.apply_scene()
            tm=g.arena['tile_map']
            self.assertEqual(g.can_walk(520,334),material not in ('wall','water'))
            self.assertEqual(structure.floor_height(tm,520,334),0 if material=='water' else 16)
            if material in ('wood','stone','grass'):
                self.assertEqual(g_audio.get_tile_audio_surface(tm,dict(x=520,y=334)),material)
        self.assertEqual(g.base_tile_map,baseline)

    def test_internal_rails_disappear_when_bridge_is_widened(self):
        g=exploration()
        layout.paint(g.scene,[288,352],[351,383],'wood',16)
        g.apply_scene()
        rails=g.arena['entities']['lake_props']
        self.assertNotIn('bridge-front:320',rails)
        self.assertNotIn('edge:19,21:front',rails)
        self.assertIn('edge:19,23:front',rails)
        self.assertTrue(g.can_walk(312,366))
        before=g.scene.checkpoint()
        g.scene.document['layout']['rails']=False;g.scene.commit(before);g.apply_scene()
        self.assertFalse(any(p['kind']=='rail' for p in g.arena['entities']['lake_props'].values()))
        g.scene.undo();g.apply_scene()
        self.assertIn('edge:19,23:front',g.arena['entities']['lake_props'])

    def test_four_stair_directions_match_visible_treads_and_pick_heights(self):
        for axis in layout.AXES:
            g=exploration()
            layout.paint(g.scene,[560,336],[655,399],'wood',16)
            layout.add_stairs(g.scene,[576,352],[639,383],16,32,axis)
            g.apply_scene();tm=g.arena['tile_map']
            stairs=next(s for s in structure.stairs_for(tm) if s.name not in ('shore','threshold'))
            parts=deck.layout(tm)
            treads=[p for p in parts if p.owner=='stairs:'+stairs.name and p.kind=='tread']
            self.assertEqual(len(treads),stairs.count)
            heights=[]
            for bounds,height in stairs.treads():
                x,z=(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2
                heights.append(height)
                self.assertTrue(g.can_walk(x,z))
                self.assertAlmostEqual(structure.floor_height(tm,x,z),height)
                self.assertTrue(any(p.low[0]<=x<=p.high[0] and p.low[2]<=z<=p.high[2] and abs(p.high[1]-height)<.0001 for p in treads))
                picked=ground_point((x,400,z),(x,0,z),(0,0,-1),180,(240,135),
                    lambda px,pz:structure.floor_height(tm,px,pz),tm['temple3d_levels'])
                self.assertEqual(picked,(x,z))
            self.assertEqual(heights,sorted(heights))

    def test_running_climbs_stairs_and_cannot_jump_up_or_down_a_ledge(self):
        g=exploration()
        layout.paint(g.scene,[288,352],[319,415],'wood',16)
        layout.paint(g.scene,[288,416],[319,447],'wood',32)
        g.apply_scene();g.set_position(304,408)
        self.assertFalse(g.can_move_to(304,417))
        g.walk.intent.basis=((1,0),(0,-1))
        for _ in range(15):g.tick(.05,{'s'},True)
        self.assertLess(g.walk.y,416)
        layout.add_stairs(g.scene,[288,368],[319,415],16,32,'z')
        g.apply_scene();g.set_position(304,360)
        g.walk.intent.basis=((1,0),(0,-1))
        for _ in range(38):g.tick(.05,{'s'},True)
        self.assertGreater(g.walk.y,416)
        self.assertEqual(structure.floor_height(g.arena['tile_map'],g.walk.x,g.walk.y),32)
        self.assertFalse(g.can_move_to(304,360))

    def test_undo_redo_progress_and_layout_reload_are_independent(self):
        with tempfile.TemporaryDirectory() as folder:
            g=exploration(Path(folder)/'scene.json')
            g.arena['puzzle_state']['facts']['visited']=True
            layout.paint(g.scene,[512,320],[543,351],'stone',16)
            g.scene.save();g.apply_scene();revision=g.geometry_revision
            g.set_position(520,334);g.save(Path(folder)/'progress.json')
            g.scene.undo();g.apply_scene()
            self.assertGreater(g.geometry_revision,revision)
            self.assertFalse(g.can_walk(520,334))
            g.scene.redo();g.apply_scene()
            self.assertTrue(g.can_walk(520,334))
            g.scene.reload();g.apply_scene();g.load(Path(folder)/'progress.json')
            self.assertEqual((g.walk.x,g.walk.y),(520,334))
            self.assertTrue(g.arena['puzzle_state']['facts']['visited'])
            self.assertEqual(Scene.load(g.scene.path).document,g.scene.document)

    def test_restoring_default_stairs_rebuilds_the_original_geometry(self):
        g=exploration()
        layout.paint(g.scene,[144,320],[175,351],'water');g.apply_scene()
        self.assertEqual(len(structure.stairs_for(g.arena['tile_map'])),1)
        layout.paint(g.scene,[144,320],[159,335],'restore');g.apply_scene()
        self.assertFalse(layout.authored(g.scene.document['layout']))
        self.assertEqual(deck.layout(g.base_tile_map),deck.layout(g.arena['tile_map']))

    def test_new_floor_camera_adapts_but_original_shots_keep_their_basis(self):
        g=exploration()
        original=g.walk.director.shot
        layout.paint(g.scene,[512,320],[559,351],'wood',16);g.apply_scene()
        self.assertIsNone(g.walk.director.override)
        g.set_position(536,334)
        self.assertEqual(g.walk.director.shot['title'],'New layout')
        self.assertEqual(g.walk.director.shot['target'][::2],(536,334))
        g.walk.intent.direction({'w'},g.walk.director)
        basis=g.walk.intent.basis
        g.set_position(480,334)
        self.assertIsNone(g.walk.director.override)
        g.walk.intent.basis=basis
        g.walk.intent.direction({'w'},g.walk.director)
        self.assertEqual(g.walk.intent.basis,basis)
        self.assertEqual(original['title'],'Across the lake')

    def test_invalid_height_stair_overlap_and_short_flights_leave_scene_unchanged(self):
        g=exploration()
        before=g.scene.checkpoint()
        for height in (float('nan'),-2,99):
            with self.assertRaises(ValueError):layout.paint(g.scene,[512,320],[543,351],'wood',height)
            self.assertEqual(before,g.scene.document)
        with self.assertRaises(ValueError):layout.add_stairs(g.scene,[512,320],[527,335],0,48,'x')
        self.assertEqual(before,g.scene.document)

    def test_erasing_floor_under_player_recovers_and_empty_layout_stays_editable(self):
        g=exploration();editor=Editor(g.scene);editor.toggle(g)
        layout.paint(g.scene,[144,288],[495,415],'water')
        editor.toggle(g)
        self.assertTrue(g.can_walk(g.walk.x,g.walk.y))
        self.assertGreater(abs(g.walk.x-256),64)
        editor.toggle(g)
        layout.paint(g.scene,[0,0],[895,639],'water')
        with self.assertRaises(ValueError):editor.toggle(g)
        self.assertTrue(editor.active)
        fresh=exploration()
        fresh.scene=g.scene;fresh.apply_scene();fresh.set_position(*fresh.scene.document['spawn'])
        with self.assertRaises(ValueError):fresh.ensure_clear_position()
        fresh.scene.undo();fresh.apply_scene();fresh.ensure_clear_position()
        self.assertTrue(fresh.can_walk(fresh.walk.x,fresh.walk.y))

    def test_new_layout_preserves_original_acoustic_zones(self):
        g=exploration()
        base=g.base_tile_map['tiles'][14*56+30].get('acoustic_zone_id',0)
        layout.paint(g.scene,[480,224],[495,239],'stone',24);g.apply_scene()
        self.assertEqual(g.arena['tile_map']['tiles'][14*56+30].get('acoustic_zone_id',0),base)


class EditorInputTests(unittest.TestCase):
    def frame(self,editor,g,world,pressed=(),held=(),button=None,down=False,release=False,click=True):
        pr=editor_module.pr
        mouse=pr.Vector2(570,405)
        with patch.object(pr,'is_key_pressed',side_effect=lambda k:k in pressed), \
             patch.object(pr,'is_key_down',side_effect=lambda k:k in held), \
             patch.object(pr,'get_mouse_position',return_value=mouse), \
             patch.object(pr,'get_mouse_wheel_move',return_value=0), \
             patch.object(pr,'is_mouse_button_pressed',side_effect=lambda k:k==button and click and not release), \
             patch.object(pr,'is_mouse_button_down',side_effect=lambda k:k==button and down), \
             patch.object(pr,'is_mouse_button_released',side_effect=lambda k:k==button and release), \
             patch.object(editor_module,'ground_point',return_value=world):
            editor.update(g,None,.05)

    def test_floor_drag_commits_once_and_undo_returns_collision(self):
        g=exploration();editor=Editor(g.scene);editor.toggle(g)
        editor.choose_tool(5);pr=editor_module.pr
        count=len(g.scene.undo_stack)
        self.frame(editor,g,(512,320),button=pr.MOUSE_BUTTON_LEFT,down=True)
        self.frame(editor,g,(543,351),button=pr.MOUSE_BUTTON_LEFT,down=True,click=False)
        self.assertEqual(len(g.scene.undo_stack),count)
        self.assertFalse(g.can_walk(520,334))
        self.frame(editor,g,(543,351),button=pr.MOUSE_BUTTON_LEFT,release=True)
        self.assertEqual(len(g.scene.undo_stack),count+1)
        self.assertTrue(g.can_walk(520,334))
        self.frame(editor,g,(543,351),pressed={pr.KEY_Z},held={pr.KEY_LEFT_CONTROL})
        self.assertFalse(g.can_walk(520,334))

    def test_right_drag_erases_alt_samples_height_and_spawn_owns_input(self):
        g=exploration();editor=Editor(g.scene);editor.toggle(g);editor.choose_tool(5)
        pr=editor_module.pr
        self.frame(editor,g,(304,334),button=pr.MOUSE_BUTTON_LEFT,held={pr.KEY_LEFT_ALT})
        self.assertEqual((editor.material,editor.floor_height),('wood',16))
        self.frame(editor,g,(304,334),button=pr.MOUSE_BUTTON_RIGHT,down=True)
        self.frame(editor,g,(319,335),button=pr.MOUSE_BUTTON_RIGHT,release=True)
        self.assertFalse(g.can_walk(312,334))
        editor.choose_tool(7)
        self.frame(editor,g,(280,334),button=pr.MOUSE_BUTTON_LEFT)
        self.assertEqual(g.scene.document['spawn'],[280,336])
        previous=(g.walk.x,g.walk.y,g.clock)
        g.tick(.05,{'d'},True,editor=True)
        self.assertEqual((g.walk.x,g.walk.y,g.clock),previous)

    def test_stairs_clicks_create_flight_right_click_removes_and_escape_cancels(self):
        g=exploration();editor=Editor(g.scene);editor.toggle(g);editor.choose_tool(6)
        layout.paint(g.scene,[512,320],[543,351],'wood',16);g.apply_scene()
        editor.floor_height=32;editor.stair_axis='z';pr=editor_module.pr
        self.frame(editor,g,(520,334),button=pr.MOUSE_BUTTON_LEFT)
        self.assertIsNotNone(editor.pending)
        self.frame(editor,g,(543,382),button=pr.MOUSE_BUTTON_LEFT)
        self.assertIsNone(editor.pending)
        self.assertEqual(len(g.scene.document['layout']['stairs']),3)
        self.frame(editor,g,(520,360),button=pr.MOUSE_BUTTON_RIGHT)
        self.assertEqual(len(g.scene.document['layout']['stairs']),2)
        editor.choose_tool(5)
        count=len(g.scene.undo_stack)
        self.frame(editor,g,(512,320),button=pr.MOUSE_BUTTON_LEFT,down=True)
        self.frame(editor,g,(543,351),pressed={pr.KEY_ESCAPE})
        self.assertIsNone(editor.floor_drag)
        self.assertEqual(len(g.scene.undo_stack),count)


if __name__=='__main__':unittest.main()
