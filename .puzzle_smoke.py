"""Hidden full-game checks and screenshots for the four puzzle prototypes."""
from pathlib import Path
from unittest.mock import patch
import pyray as pr
import g_main
import g_update_and_render as game
import g_puzzles as p
import g_ui
from test_puzzles import make_arena, place

pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
output = Path('artifacts/puzzles')
output.mkdir(parents=True, exist_ok=True)
fixture = make_arena()
for tile in fixture['tile_map']['tiles']:
    tile['index'] = 6  # stone floor
placed = []
for group, kind in enumerate(p.DOOR_TYPES, 1):
    x = 7 + (group - 1) * 6
    placed.append(place(fixture, kind, x=x, y=7, group=group))
    control = ('puzzle key', 'puzzle key', 'puzzle lever', 'puzzle keypad')[group - 1]
    placed.append(place(fixture, control, x=x, y=11, group=group))
lever = place(fixture, 'puzzle lever', x=12, y=14, group=2)
marker = place(fixture, 'puzzle spawn', x=17, y=14, group=2)
placed.extend((lever, marker))
player = fixture['player_info']
player['position'] = dict(tile_x=12, tile_y=8, x=8., y=8.)
original = game.update_and_render
frame = 0
failures = []


def checked(render, lighting, arena, assets, engine):
    global frame
    try:
        if frame == 0:
            for key, value in fixture.items():
                arena = arena.set(key, value)
        editor = game.g_editor.get_or_create_editor_state(assets)
        assets.setdefault('ui_state', g_ui.make_ui_state())['show_editor'] = frame < 10
        arena = arena.set('editor_mode', 'entity' if frame < 10 else 'play').set('auto_reload', False)
        if frame < 10:
            obj = placed[frame]
            arena = arena.set('current_entity_selection', game.load_entity_types().index(obj['type']))
            editor.update(tool='select', selected_kind='gameplay_entity', selected_collection='puzzles', selected_id=obj['id'])
        pressed = set()
        chars = [0]
        if frame == 11:
            keypad = placed[7]
            arena['player_info']['position'] = dict(keypad['position'])
            pressed = {pr.KeyboardKey.KEY_E}
        if frame == 12:
            chars = [48, 52, 53, 49, 0]
        if frame == 13:
            pressed = {pr.KeyboardKey.KEY_ENTER}
        if frame == 14:
            for obj in (placed[3], lever, placed[2]):
                arena = p.interact(arena, obj['persistent_id'])
        with patch.object(pr, 'is_key_pressed', side_effect=lambda key: key in pressed), \
             patch.object(pr, 'get_char_pressed', side_effect=chars):
            arena = original(render, lighting, arena, assets, engine)
        if frame in (0, 6, 10, 12, 14):
            image = pr.load_image_from_texture(render.texture)
            pr.image_flip_vertical(image)
            pr.export_image(image, str(output / f'frame-{frame}.png'))
            pr.unload_image(image)
        if frame == 13:
            assert p.object_state(arena, placed[6]).get('open'), 'keypad did not open door'
        if frame == 14:
            assert len(arena['entities']['brains']) == 1, 'authored spawn missing'
        frame += 1
        return arena
    except Exception as error:
        failures.append(error)
        raise


game.update_and_render = checked
remaining = iter([False] * 16 + [True])
pr.window_should_close = lambda: next(remaining)
pr.get_frame_time = lambda: .016
g_main.g_main()
assert not failures, failures
assert frame == 16, frame
print('Full-game puzzle smoke passed: all inspectors, keypad keyboard input, authored enemy spawn, 16 frames.')
