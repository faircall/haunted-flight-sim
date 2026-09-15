import copy
import pickle
import unittest
from unittest.mock import patch
import g_inventory as inv
import g_interactions as ui
import g_puzzles as puzzles
import g_update_and_render as game
from test_puzzles import make_arena, place


class InventoryTests(unittest.TestCase):
    def test_stack_fills_existing_before_empty_and_legacy_overflow_is_claimable(self):
        slots = [None, dict(kind="ammo", count=30)]
        self.assertTrue(inv.add(slots, dict(kind="ammo", count=10)))
        self.assertIsNone(slots[0])
        self.assertEqual(slots[1]["count"], 40)
        arena = make_arena()
        arena["player_info"]["ammo"]["spare_pistol"] = 1000
        arena = inv.ensure(arena)
        player = arena["player_info"]
        self.assertEqual(inv.count(player["inventory"], "ammo") + inv.count(player["inventory_overflow"], "ammo"), 1000)
        self.assertTrue(all(s["count"] <= 60 for s in player["inventory_overflow"]))

    def test_atomic_stack_capacity(self):
        slots = [dict(kind="ammo", count=59), dict(kind="health", count=1)]
        before = copy.deepcopy(slots)
        self.assertFalse(inv.add(slots, dict(kind="ammo", count=2)))
        self.assertEqual(before, slots)
        self.assertTrue(inv.add(slots, dict(kind="ammo", count=1)))
        self.assertEqual(slots[0]["count"], 60)

    def test_key_transfer_full_retry_and_door(self):
        arena = ui.ensure(make_arena())
        key = place(arena, "puzzle key")
        door = place(arena, "key door", x=8)
        slots = arena["player_info"]["inventory"]
        slots[:] = [dict(kind="health", count=1)] * 8
        arena = ui.take(arena, ["puzzles", key["id"]])
        self.assertFalse(puzzles.object_state(arena, key).get("collected"))
        self.assertFalse(puzzles.has_key(arena, door))
        slots[0] = None
        arena = ui.take(arena, ["puzzles", key["id"]])
        self.assertTrue(puzzles.has_key(arena, door))
        arena = puzzles.interact(arena, door["persistent_id"])
        self.assertTrue(puzzles.object_state(arena, door)["unlocked"])
        ui.take(arena, ["puzzles", key["id"]])
        self.assertEqual(inv.count(slots, "key"), 1)

    def test_health_use_and_ammo_reload(self):
        arena = ui.ensure(make_arena())
        player = arena["player_info"]
        self.assertTrue(inv.add(player["inventory"], dict(kind="health", count=1, value=25)))
        inv.use(player, 1)
        self.assertIsNotNone(player["inventory"][1])
        player["health"] = 90
        inv.use(player, 1)
        self.assertEqual(player["health"], 100)
        self.assertIsNone(player["inventory"][1])
        player["ammo"]["pistol"] = 0
        player.update(reload_state="reloading", reload_timer=0)
        game.update_player_reload(player, "pistol", False, 10, None)
        self.assertEqual(inv.count(player["inventory"], "ammo"), player["ammo"]["spare_pistol"])
        self.assertGreater(player["ammo"]["pistol"], 0)

    def test_migration_save_and_reset(self):
        arena = make_arena()
        arena["puzzle_state"]["inventory"]["9"] = 1
        arena = ui.ensure(arena)
        saved = pickle.loads(pickle.dumps(arena.remove("interaction_runtime")))
        saved = ui.ensure(saved)
        self.assertEqual(inv.count(saved["player_info"]["inventory"], "key"), 1)
        saved = puzzles.reset_progress(saved)
        self.assertEqual(inv.count(saved["player_info"]["inventory"], "key"), 0)

    def test_cancel_and_callback_consume_frame(self):
        arena = ui.open_dialogue(ui.ensure(make_arena()), ["test"], [{"label":"yes", "handler":"inscription_button"}], "demo")
        with patch.object(ui.pr, "is_key_pressed", side_effect=lambda k: k == ui.pr.KeyboardKey.KEY_ESCAPE):
            arena, owned = ui.update(arena, True, {})
        self.assertTrue(owned)
        self.assertTrue(arena["interaction_runtime"]["modal"]["cancelled"])
        with patch.object(ui.pr, "get_frame_time", return_value=ui.DIALOGUE_FADE_OUT_SECONDS):
            arena, owned = ui.update(arena, True, {})
        self.assertIsNone(arena["interaction_runtime"]["modal"])
        self.assertEqual(arena["puzzle_state"]["facts"], {})
        arena = ui.open_dialogue(arena, ["test"], [{"label":"yes", "handler":"inscription_button"}], "demo")
        with patch.object(ui.pr, "is_key_pressed", side_effect=lambda k: k == ui.pr.KeyboardKey.KEY_ENTER), patch.object(ui.text, "wrap", return_value=["test"]):
            arena, owned = ui.update(arena, True, {})
        self.assertNotIn("inscription_button:demo", arena["puzzle_state"]["facts"])
        with patch.object(ui.pr, "get_frame_time", return_value=ui.DIALOGUE_FADE_OUT_SECONDS):
            arena, owned = ui.update(arena, True, {})
        self.assertTrue(arena["puzzle_state"]["facts"]["inscription_button:demo"])
        self.assertEqual(arena["interaction_runtime"]["modal"]["page"], 0)

    def test_prompt_retains_label_and_reverses_fade_on_reapproach(self):
        runtime = {}
        candidate = ("puzzles", "one", {"type": "inspectable", "label": "Statue"})
        ui.update_prompt(runtime, candidate, 0)
        ui.update_prompt(runtime, candidate, ui.PROMPT_FADE_SECONDS)
        ui.update_prompt(runtime, None, ui.PROMPT_FADE_SECONDS / 2)
        self.assertEqual(runtime["prompt"]["amount"], .5)
        self.assertEqual(runtime["prompt"]["label"], "Statue")
        ui.update_prompt(runtime, candidate, ui.PROMPT_FADE_SECONDS / 4)
        self.assertEqual(runtime["prompt"]["amount"], .75)
        ui.update_prompt(runtime, None, ui.PROMPT_FADE_SECONDS)
        self.assertEqual(runtime["prompt"]["label"], "")

    @patch.object(ui.data, "SHOW_NARRATIVE_BACKGROUNDS", True)
    def test_page_transition_keeps_panel_and_ignores_repeated_continue(self):
        arena = ui.open_dialogue(make_arena(), ["old", "new"])
        modal = arena["interaction_runtime"]["modal"]
        modal["fade_elapsed"] = ui.DIALOGUE_FADE_IN_SECONDS
        with patch.object(ui.pr, "get_frame_time", return_value=0), patch.object(ui.pr, "is_key_pressed", side_effect=lambda k: k == ui.pr.KeyboardKey.KEY_ENTER), patch.object(ui.text, "wrap", side_effect=lambda assets, value, width: [value]):
            ui.update(arena, True, {})
        self.assertEqual(modal["page"], 0)
        with patch.object(ui.pr, "get_frame_time", return_value=ui.PAGE_FADE_SECONDS), patch.object(ui.pr, "is_key_pressed", side_effect=lambda k: k == ui.pr.KeyboardKey.KEY_ENTER):
            ui.update(arena, True, {})
            self.assertEqual(modal["page"], 1)
            with patch.object(ui.pr, "draw_rectangle") as panels, patch.object(ui.text, "draw") as labels, patch.object(ui.text, "wrap", return_value=["new"]):
                ui.draw(arena, {})
            self.assertEqual(panels.call_args_list[-1].args[-1].a, 255)
            self.assertEqual(labels.call_args_list[0].args[-1].a, 0)
            ui.update(arena, True, {})
        self.assertNotIn("closing_elapsed", modal)
        self.assertNotIn("page_elapsed", modal)

    @patch.object(ui.data, "SHOW_NARRATIVE_BACKGROUNDS", True)
    def test_closing_blocks_repeated_actions_and_fades_entire_dialogue(self):
        arena = ui.open_dialogue(make_arena(), ["test"], on_complete="inscription_button", target="demo")
        modal = arena["interaction_runtime"]["modal"]
        modal.update(fade_elapsed=ui.DIALOGUE_FADE_IN_SECONDS, closing_elapsed=0.0)
        with patch.object(ui.pr, "get_frame_time", return_value=ui.DIALOGUE_FADE_OUT_SECONDS / 2), patch.object(ui.pr, "is_key_pressed", return_value=True):
            arena, owned = ui.update(arena, True, {})
            self.assertTrue(owned)
            self.assertEqual(arena["puzzle_state"]["facts"], {})
            with patch.object(ui.pr, "draw_rectangle") as panels, patch.object(ui.text, "draw") as labels, patch.object(ui.text, "wrap", return_value=["test"]):
                ui.draw(arena, {})
            self.assertEqual(panels.call_args_list[-1].args[-1].a, 128)
            self.assertEqual(labels.call_args_list[0].args[-1].a, 128)
            arena, owned = ui.update(arena, True, {})
        self.assertTrue(arena["puzzle_state"]["facts"]["inscription_button:demo"])
        self.assertIsNot(arena["interaction_runtime"]["modal"], modal)


if __name__ == "__main__":
    unittest.main()
