"""Launch a separate material playground with the normal editor and gameplay."""
import g_surfaces as surfaces


def review_map(game):
    tm = game.make_tile_map(32, 22, 16, 16)
    surfaces.paint(tm, [(x, y) for y in range(22) for x in range(32)], 'dirt', density=.75)
    grass = [(x, y) for y in range(2, 19) for x in range(2, 17)
             if (x-8)**2/62 + (y-10)**2/75 < 1 and not (8<x<12 and y>8)]
    surfaces.paint(tm, grass, 'grass', density=.85)
    surfaces.paint(tm, [(x,y) for y in range(3,10) for x in range(20,29)], 'wood')
    surfaces.paint(tm, [(x,y) for y in range(5,8) for x in range(22,27)], 'carpet')
    surfaces.paint(tm, [(x,y) for y in range(12,17) for x in range(20,29)], 'ceramic', soft=False)
    surfaces.paint(tm, [(x,y) for y in range(1,3) for x in range(20,29)], 'wall', soft=False)
    for y in range(1,3):
        for x in range(20,29):
            surfaces.cell(tm,x,y)['force_collidable']=True
    surfaces.add_impact(tm, {'x':340., 'y':24.}, {'x':1.,'y':0.})
    return tm


def review_profile(game):
    profile = game.g_graphics.make_lighting_profile()
    profile.update(ambient_color=[1.,1.,1.], ambient_strength=.9,
                   black_point=0., contrast=1., light_posterize_enabled=False)
    return profile


def run():
    import g_main
    game = g_main.update_and_render_module
    original = game.update_and_render
    started = False
    def initialize(render, lighting, arena, assets, engine):
        nonlocal started
        if not started:
            arena = (arena.set('entities', {}).set('tile_map', review_map(game))
                     .set('player_info', game.make_default_player(118,148,0))
                     .set('lighting_profile', review_profile(game)).set('editor_mode', 'tile'))
            assets.setdefault('ui_state', game.g_ui.make_ui_state())['show_editor'] = True
            game.g_editor.get_or_create_editor_state(assets).update(
                tile_edit_mode='materials', surface_material='grass')
            started = True
        return original(render, lighting, arena, assets, engine)
    game.update_and_render = initialize
    g_main.g_main()


if __name__ == '__main__':
    run()
