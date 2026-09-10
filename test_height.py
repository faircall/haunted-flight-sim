import unittest
import g_height
import g_render_order as render
import g_graphics as graphics


class HeightTests(unittest.TestCase):
    def item(self, **fields):
        entity = dict(current_state="idle", **fields)
        return render.make_world_render_item("entity", "red head", "test", "test", entity,
            {"x": 100., "y": 100.}, 24., 24., {}, {})

    def test_elevation_preserves_ground_and_sorting(self):
        ground, air = self.item(), self.item(elevation=10.)
        self.assertEqual(ground["base_world"], air["base_world"])
        self.assertEqual(ground["sort_y"], air["sort_y"])
        self.assertEqual(ground["dest_rect"]["y"]-10., air["dest_rect"]["y"])
        self.assertEqual(ground["light_sample_height"]+10., air["light_sample_height"])

    def test_dead_profile_and_override(self):
        entity = dict(current_state="dead", visual_height=24.)
        self.assertEqual(g_height.resolve(entity)["body_height"], 3.)
        entity["height_overrides"] = {"body_height": 4.}
        self.assertEqual(g_height.resolve(entity)["body_height"], 4.)
        self.assertEqual(entity["visual_height"], 24.)

    def test_grounded_silhouette_stays_near_body(self):
        info = dict(base_world={"x": 100., "y": 100.}, sprite_width=24.,
                    ground_rect={"x": 88., "y": 88., "width": 24., "height": 24.})
        settings = dict(mode="grounded", cast_height=3., maximum_length=72.)
        light = {"x": 100., "y": 0.}
        quad = graphics.build_cinematic_shadow_quad(info, settings, light, 30.)
        self.assertAlmostEqual(quad["far_left"]["y"], 88.+88./9.)
        self.assertGreater(quad["near_left"]["y"], quad["far_left"]["y"])
        settings["elevation"] = 5.
        lifted = graphics.build_cinematic_shadow_quad(info, settings, light, 30.)
        self.assertGreater(lifted["far_left"]["y"], quad["far_left"]["y"])

    def test_projection_limits(self):
        point, light = {"x": 10., "y": 0.}, {"x": 0., "y": 0.}
        self.assertEqual(g_height.project(point, 0., light, 20., 72.), point)
        self.assertEqual(g_height.project(point, 25., light, 20., 72.)["x"], 82.)
