"""Encounter, shared AI, height-aware shooting and progress regressions."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

import g_temple_layout as layout
from g_temple_encounter import install_terrace
from g_temple_combat import world,ray_box
from test_temple_exploration import exploration


def encounter():
    g=exploration();install_terrace(g.scene);g.apply_scene();g.set_position(580,344)
    g.tick(.05)
    return g


class CombatTests(unittest.TestCase):
    def test_trigger_starts_once_and_shared_ai_pursues_attacks(self):
        g=encounter();actor=g.combat.actors['terrace-redhead'];start=world(actor,g.arena['tile_map'])
        states=set()
        for _ in range(260):
            g.tick(.05);states.add(actor['current_state'])
        self.assertTrue({'noticing','angry chase','angry and attacking'}<=states)
        self.assertLess(g.player['health'],100)
        self.assertLess(world(actor,g.arena['tile_map'])[0],start[0])
        self.assertEqual(len(g.combat.actors),1)
        self.assertTrue(g.combat.encounters['temple-terrace']['started'])

    def test_three_hits_kill_and_unlock_linked_gate(self):
        g=encounter();c=g.combat;actor=c.actors['terrace-redhead']
        self.assertFalse(g.can_walk(664,352))
        for _ in range(3):
            x,z=world(actor,g.arena['tile_map'])
            g.tick(.05,aiming=True,aim=(x,34.5,z),fire=True)
            for _ in range(5):g.tick(.05)
        self.assertLessEqual(actor['health'],0)
        self.assertEqual(actor['current_state'],'dead')
        self.assertTrue(c.encounters['temple-terrace']['complete'])
        self.assertTrue(g.arena['puzzle_state']['facts']['temple-terrace:complete'])
        self.assertEqual(g.player['ammo']['pistol'],17)
        self.assertTrue(g.arena['puzzle_state']['objects']['terrace-gate:0']['unlocked'])
        self.assertFalse(g.can_walk(664,352)) # unlocking does not open a door
        g.set_position(650,352);g.tick(.05,pressed={'E'})
        self.assertTrue(g.arena['puzzle_state']['objects']['terrace-gate:0']['open'])
        self.assertTrue(g.can_walk(664,352))

    def test_paused_input_consumes_no_ammo_or_ai_time(self):
        g=encounter();c=g.combat;actor=c.actors['terrace-redhead'];saved=deepcopy(actor)
        for _ in range(10):g.tick(.05,editor=True,aiming=True,aim=(624,34.5,336),fire=True)
        self.assertEqual(actor,saved);self.assertEqual(g.player['ammo']['pistol'],20)
        g.tick(.05,pressed={'TAB'},aiming=True,fire=True)
        self.assertIsNotNone(g.modal)
        clock=g.clock;state=deepcopy(actor)
        for _ in range(10):g.tick(.05,aiming=True,fire=True)
        self.assertEqual(actor,state);self.assertEqual(g.clock,clock)
        g.tick(.05,pressed={'TAB'},aiming=True,fire=True)
        self.assertEqual(g.player['ammo']['pistol'],20)

    def test_fire_requires_aim_and_respects_cooldown_and_empty(self):
        g=encounter();c=g.combat
        g.tick(.05,fire=True);self.assertEqual(c.shots,0)
        g.tick(.05,aiming=True,aim=(624,34.5,336),fire=True)
        g.tick(.05,aiming=True,fire=True)
        self.assertEqual(c.shots,1);self.assertEqual(g.player['ammo']['pistol'],19)
        g.player['ammo']['pistol']=0;c.cooldown=0
        g.tick(.05,aiming=True,fire=True)
        self.assertEqual(c.shots,1)
        self.assertIn('weapon_empty',[e['type'] for e in c.events])

    def test_wall_height_blocks_shots_and_water_does_not(self):
        g=encounter();actor=g.combat.actors['terrace-redhead']
        layout.paint(g.scene,(608,320),(623,351),'wall',16);g.apply_scene()
        g.tick(.05,aiming=True,aim=(624,34.5,336),fire=True)
        self.assertEqual(actor['health'],60)
        g.combat.cooldown=0
        layout.paint(g.scene,(608,320),(623,351),'water');g.apply_scene()
        g.tick(.05,aiming=True,aim=(624,34.5,336),fire=True)
        self.assertEqual(actor['health'],40)

    def test_reload_consumes_inventory_atomically_and_pauses(self):
        g=encounter();g.player['ammo']['pistol']=3;spare=g.player['ammo']['spare_pistol']
        g.tick(.05,reload=True)
        self.assertGreater(g.combat.reload,0)
        timer=g.combat.reload
        for _ in range(30):g.tick(.05,editor=True)
        self.assertEqual(g.combat.reload,timer)
        for _ in range(25):g.tick(.05)
        self.assertEqual(g.player['ammo']['pistol'],20)
        self.assertEqual(g.player['ammo']['spare_pistol'],spare-17)

    def test_save_load_active_and_dead_enemy_no_resurrection(self):
        g=encounter();actor=g.combat.actors['terrace-redhead']
        for _ in range(36):g.tick(.05)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'progress.json';g.save(path);saved=g.snapshot()
            for _ in range(30):g.tick(.05)
            g.load(path)
            self.assertEqual(g.snapshot(),saved)
            g.combat.actors['terrace-redhead'].update(health=0,current_state='dead')
            g.tick(.05);g.save(path);g.load(path)
            self.assertTrue(g.combat.encounters['temple-terrace']['complete'])
            self.assertEqual(g.combat.actors['terrace-redhead']['health'],0)
            g.apply_scene();self.assertEqual(g.combat.actors['terrace-redhead']['health'],0)

    def test_invalid_combat_save_is_atomic(self):
        g=encounter();saved=g.snapshot();bad=deepcopy(saved)
        bad['player']['health']=10;bad['combat']['actors']['terrace-redhead']['position']['x']=float('nan')
        with self.assertRaises(ValueError):g.restore(bad)
        self.assertEqual(g.snapshot(),saved)

    def test_blocked_spawn_waits_without_false_completion(self):
        g=exploration();install_terrace(g.scene)
        layout.paint(g.scene,(624,336),(639,351),'wall',16);g.apply_scene();g.set_position(580,344)
        for _ in range(5):g.tick(.05)
        self.assertEqual(g.combat.actors,{})
        self.assertFalse(g.combat.encounters['temple-terrace']['complete'])
        g.scene.undo();g.apply_scene();g.tick(.05)
        self.assertEqual(len(g.combat.actors),1)

    def test_death_freezes_simulation_and_enter_restarts(self):
        g=encounter();g.player['health']=0;position=(g.walk.x,g.walk.y)
        for _ in range(25):g.tick(.05,{'d'},aiming=True,fire=True)
        self.assertEqual((g.walk.x,g.walk.y),position)
        self.assertEqual(g.player['ammo']['pistol'],20)
        self.assertGreater(g.combat.death_time,1)
        g.tick(.05,pressed={'ENTER'})
        self.assertEqual(g.player['health'],100)
        self.assertEqual((g.walk.x,g.walk.y),(256,334))
        self.assertEqual(g.combat.actors,{})
        self.assertFalse(g.combat.encounters['temple-terrace']['started'])

    def test_player_enemy_collision_uses_live_bodies_only(self):
        g=encounter();actor=g.combat.actors['terrace-redhead']
        self.assertFalse(g.can_walk(624,336))
        actor.update(health=0,current_state='dead')
        self.assertTrue(g.can_walk(624,336))

    def test_ray_box_handles_height_misses_and_nearest_entry(self):
        self.assertEqual(ray_box((0,10,0),(20,10,0),(8,0,-2),(12,20,2)),.4)
        self.assertIsNone(ray_box((0,30,0),(20,30,0),(8,0,-2),(12,20,2)))
        self.assertEqual(ray_box((10,10,0),(20,10,0),(8,0,-2),(12,20,2)),0)

    def test_shared_ai_climbs_stairs_and_never_crosses_tall_ledge(self):
        import g_temple_structure as structure
        g=exploration();install_terrace(g.scene)
        layout.paint(g.scene,(576,384),(607,415),'wood',32)
        layout.add_stairs(g.scene,(576,336),(607,383),16,32,'z')
        g.scene.get('terrace-redhead')['position']=[584,328]
        g.apply_scene();g.set_position(584,404)
        g.combat.encounters['temple-terrace']['started']=True;g.combat.sync()
        actor=g.combat.actors['terrace-redhead'];last=16
        for _ in range(240):
            g.tick(.05);p=world(actor,g.arena['tile_map']);height=structure.floor_height(g.arena['tile_map'],*p)
            self.assertLessEqual(abs(height-last),4.001);last=height
            if height==32:break
        self.assertEqual(last,32)

    def test_malformed_actor_and_gate_saves_leave_running_state_untouched(self):
        g=encounter();saved=g.snapshot()
        changes=(('heading',['bad',0]),('position',dict(tile_x=36.5,tile_y=20,x=0,y=0)),
                 ('attack_direction',dict(x=0,y=float('inf'))),('health',0))
        for field,value in changes:
            bad=deepcopy(saved);bad['combat']['actors']['terrace-redhead'][field]=value
            with self.assertRaises(ValueError):g.restore(bad)
            self.assertEqual(g.snapshot(),saved)
        bad=deepcopy(saved);bad['puzzle_state']['objects']['terrace-gate:0']=dict(unlocked=True,open=True)
        with self.assertRaises(ValueError):g.restore(bad)
        self.assertEqual(g.snapshot(),saved)

    def test_legacy_save_loads_with_unstarted_encounters(self):
        g=encounter();saved=deepcopy(g.initial_progress);saved.pop('combat')
        g.restore(saved)
        self.assertEqual(g.combat.actors,{})
        self.assertFalse(g.combat.encounters['temple-terrace']['started'])

    def test_editor_trigger_group_placement_rotation_and_undo(self):
        from test_temple_layout import EditorInputTests
        from g_temple_editor import Editor
        import g_temple_editor as module
        g=exploration();editor=Editor(g.scene);editor.toggle(g);editor.choose_tool(8)
        frame=EditorInputTests().frame;pr=module.pr
        frame(editor,g,(272,328),button=pr.MOUSE_BUTTON_LEFT)
        frame(editor,g,(316,348),button=pr.MOUSE_BUTTON_LEFT)
        trigger=g.scene.get(editor.selected)
        self.assertEqual(trigger['kind'],'encounter')
        self.assertEqual(editor.edit_field,'group')
        editor.edit_text='new-encounter';editor.finish_text();g.apply_scene()
        self.assertIn('new-encounter',g.combat.encounters)
        self.assertTrue(g.scene.undo());g.apply_scene()
        self.assertEqual(g.scene.get(trigger['id'])['group'],'temple-terrace')
        editor.choose_tool(1);editor.palette_index=next(i for i,p in enumerate(editor.palette) if p['kind']=='gate')
        frame(editor,g,(288,334),button=pr.MOUSE_BUTTON_LEFT)
        gate=g.scene.get(editor.selected)
        frame(editor,g,(288,334),pressed={pr.KEY_E})
        self.assertEqual(gate['rotation'],90)
        identity=g.scene.duplicate(gate['id'])
        self.assertNotEqual(identity,gate['id']);self.assertEqual(g.scene.get(identity)['group'],gate['group'])

    def test_encounter_reset_preserves_level_and_unrelated_progress(self):
        g=encounter();document=g.scene.checkpoint()
        g.combat.encounters['temple-terrace'].update(complete=True)
        g.arena['puzzle_state']['facts']['temple-terrace:complete']=True
        g.arena['puzzle_state']['facts']['read_inscription']=True
        g.combat.reset()
        self.assertEqual(g.scene.document,document)
        self.assertTrue(g.arena['puzzle_state']['facts']['read_inscription'])
        self.assertNotIn('temple-terrace:complete',g.arena['puzzle_state']['facts'])
        self.assertEqual(g.combat.actors,{})
        self.assertFalse(g.combat.encounters['temple-terrace']['started'])
        self.assertFalse(g.can_walk(664,352))
        g.tick(.05);self.assertEqual(len(g.combat.actors),1)

    def test_melee_cannot_damage_across_a_tall_ledge(self):
        import g_update_and_render as game
        g=encounter();actor=g.combat.actors['terrace-redhead']
        layout.paint(g.scene,(624,352),(639,367),'wood',32);g.apply_scene()
        actor['position']=game.get_tile_index_and_offset_from_pos(dict(x=624,y=346),g.arena['tile_map'])
        actor.update(current_state='angry and attacking',previous_state='angry chase')
        g.set_position(624,357)
        for _ in range(100):g.tick(.05)
        self.assertEqual(g.player['health'],100)

    def test_restart_respects_changed_spawn_and_current_groups(self):
        g=encounter();g.scene.document['spawn']=[288,334]
        g.scene.get('terrace-trigger')['group']='edited-group'
        g.apply_scene();g.player['health']=0
        g.tick(.05,pressed={'ENTER'})
        self.assertEqual((g.walk.x,g.walk.y),(288,334))
        self.assertEqual(g.player['health'],100)
        self.assertFalse(g.combat.encounters['edited-group']['started'])

    def test_retreat_from_committed_melee_causes_a_miss(self):
        g=encounter();actor=g.combat.actors['terrace-redhead'];g.set_position(603,336)
        actor.update(current_state='angry and attacking',previous_state='angry and attacking',
                     attack_timer=.99,attack_substate='committed',attack_direction=dict(x=-1.,y=0.))
        g.tick(.05)
        self.assertEqual(g.player['health'],100)
        self.assertEqual(actor['attack_substate'],'attacking')
        self.assertIn('melee_whoosh',[e['type'] for e in g.combat.events])


if __name__=='__main__':unittest.main()
