"""Compare real player direct-light pixels with a nearby glow light off/on."""
import pyray as pr
import g_main
import g_glow
from test_puzzles import make_arena
game = g_main.update_and_render_module
pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
original = game.update_and_render
draw_original = game.g_graphics.draw_sorted_world_render_items
frame = 0
probe = {}
samples = []
def draw(items, scene, camera, *args, **kwargs):
    player = next(item for item in items if item["source_id"] == "player")
    probe.update(rect=dict(player["dest_rect"]), camera=(camera.x,camera.y),
                 records=player.get("self_shadow_summary",{}).get("per_light",[]))
    return draw_original(items,scene,camera,*args,**kwargs)
def checked(render,lighting,arena,assets,engine):
    global frame
    if frame == 0:
        fixture = make_arena()
        fixture["player_info"]["position"] = dict(tile_x=10,tile_y=10,x=5.,y=5.)
        obj = dict(type="buddha",id="probe",position=dict(tile_x=5,tile_y=5,x=8.,y=8.))
        game.give_entity_stats_from_type(obj,"buddha")
        fixture["entities"]["brains"] = {"probe":obj}
        for key,value in fixture.items(): arena=arena.set(key,value)
        arena = g_glow.set_glow(arena,"brains:probe",strength=.8,color=[0.,1.,0.],mode="edge",
                              light=dict(enabled=True,radius=160.,intensity=2.))
    policy = arena["entities"]["brains"]["probe"]["glow"]["light"]
    policy["enabled"] = frame != 0
    policy["radius"] = 80. if frame == 1 else 160.
    arena = original(render,lighting,arena.set("editor_mode","entity"),assets,engine)
    target = assets["render_targets"]["entity_direct_light"]
    image = pr.load_image_from_texture(target.texture);pr.image_flip_vertical(image)
    rect,camera = probe["rect"],probe["camera"]
    total = 0
    for y in range(max(0,int(rect["y"]-camera[1])), min(image.height,int(rect["y"]-camera[1]+rect["height"]))):
        for x in range(max(0,int(rect["x"]-camera[0])), min(image.width,int(rect["x"]-camera[0]+rect["width"]))):
            total += pr.get_image_color(image,x,y).g
    pr.unload_image(image)
    records = [record for record in probe["records"] if "effect:glow:" in str(record.get("light_id"))]
    samples.append(total)
    print("PLAYER_PROBE",frame,"green_direct_pixels_sum",total,"glow_records",records)
    frame += 1
    return arena
game.g_graphics.draw_sorted_world_render_items = draw
game.update_and_render = checked
frames = iter((False,False,False,True))
pr.window_should_close = lambda: next(frames)
g_main.g_main()
assert samples[2] > samples[0], samples
print("Player receives glow light: confirmed by GPU pixel comparison",samples)
