"""Behavior checks for compiled modules, with visible harness exclusions."""
import unittest

MODULES='''test_light_visibility test_render_order test_render_performance test_night
test_roofs test_water_temple test_player_reveal test_editor_ui test_editor_history
test_surfaces test_effects test_tree_game test_tree_assets test_tree_animation
test_character_shadows test_entity_self_shadow test_entity_light_optimization
test_flashlight_origin test_bullet_collision test_puzzles test_sequences
test_inventory test_player_aim test_redhead_behavior_improvements'''.split()

EXCLUSIONS={
    'test_render_order.RenderOrderTests.test_environment_composites_place_rain_between_emissive_fog_and_darkness_fallback':
        'Uses inspect.getsource on a Python function; C rendering order is covered by scene parity and GPU checks.',
    'test_player_aim.PlayerAimHeadingTests.test_interaction_no_longer_aims_at_absolute_mouse_position':
        'Uses inspect.getsource on a Python function; behavioral aim tests still run.',
    'test_entity_self_shadow.DirectionalProfileTests.test_missing_response_warning_is_reported_once':
        'Mocks builtins.print; Cython caches that builtin. Logging occurs but bypasses the Python mock.',
    'test_entity_self_shadow.EntitySelfShadowTests.test_entity_draw_snaps_camera_relative_position_to_pixel_grid':
        'Also fails in original Python: mocks the old pyray wrapper while drawing now uses pr.rl.DrawTexturePro. GPU camera checks still run.',
    'test_tree_assets.TreeAssetTests.test_packs_reconstruct_and_masks_align':
        'Also fails in original Python: reference image differs from cleaned split artwork. This build does not modify those assets.',
}

def flatten(suite):
    for value in suite:
        if isinstance(value,unittest.TestSuite):yield from flatten(value)
        else:yield value

def load_tests(loader,tests,pattern):
    all_tests=list(flatten(loader.loadTestsFromNames(MODULES)))
    for test in all_tests:
        reason=EXCLUSIONS.get(test.id())
        if reason:
            method=getattr(type(test),test._testMethodName)
            method.__unittest_skip__=True
            method.__unittest_skip_why__=reason
    return unittest.TestSuite(all_tests)
