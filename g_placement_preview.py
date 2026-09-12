"""Editor-only placement ghosts. Never inserted into level collections."""
import math
import pyray as pr


def placement_position(mode, mouse, camera, tile_map, state):
    import g_editor
    world = {"x": mouse.x+camera.x, "y": mouse.y+camera.y}
    if mode == "environment":
        world = g_editor.snap_world_position(world,state)
    position = g_editor.world_to_tile_position(world,tile_map)
    if not (0 <= position["tile_x"] < tile_map["map_width"] and 0 <= position["tile_y"] < tile_map["map_height"]):
        return None
    if mode == "tile":
        position.update(x=0.,y=0.)
    return position


def opacity(now):
    return .48 + .13*math.sin(float(now)*math.tau*.8)


def draw(scene, camera, assets, tile_map, state, mode, tile_index, shape_index, entity_index, now):
    import g_editor as editor
    import g_graphics as graphics
    import g_render_order as render
    import g_update_and_render as game
    import g_effects
    import g_ui
    if mode not in ("tile","entity","environment") or (mode != "tile" and state.get("tool","select") != "place"):
        return
    mouse = g_ui.get_mouse_position()
    if not (0 <= mouse.x < scene.texture.width and 0 <= mouse.y < scene.texture.height):
        return
    position = placement_position(mode,mouse,camera,tile_map,state)
    if position is None:
        return
    world = editor.tile_position_to_world(position,tile_map)
    screen = render.world_to_screen_pixel(world["x"],world["y"],camera)
    target = graphics.get_or_create_render_target(assets,"placement_preview",scene.texture.width,scene.texture.height)
    pr.begin_texture_mode(target)
    pr.clear_background(pr.BLANK)
    if mode == "tile":
        if state.get("tile_edit_mode","appearance") == "appearance":
            tiles = tile_map["tile_types"]
            if 0 <= tile_index < len(tiles):
                tile = tiles[tile_index]
                texture_name = {"wood":"wood_texture","wall":"wall_texture","stone":"grey_tile_texture","carpet":"orange_tile_texture"}.get(tile.get("type"))
                texture = assets.get("textures",{}).get(texture_name)
                if texture is not None:
                    game.draw_masked_tile_texture(texture,pr.Vector2(screen["x"],screen["y"]),shape_index,assets)
                else:
                    game.draw_tile_shape_tint(pr.Vector2(screen["x"],screen["y"]),shape_index,tile_map["tile_width"],tile_map["tile_height"],game.color_map(tile.get("color")))
        else:
            # Metadata brushes show their affected cell, not a replacement texture.
            pr.draw_rectangle(screen["x"],screen["y"],tile_map["tile_width"],tile_map["tile_height"],pr.SKYBLUE)
    elif mode == "entity":
        types = assets.get("entity_types",game.load_entity_types())
        if 0 <= entity_index < len(types):
            kind = types[entity_index]
            cache = assets.get("placement_specimen")
            if not cache or cache["type"] != kind:
                specimen = dict(type=kind,id="placement-preview",position=dict(position),
                    entity_width=game.g_default_entity_width,entity_height=game.g_default_entity_height)
                game.give_entity_stats_from_type(specimen,kind)
                cache = dict(type=kind,entity=specimen)
                assets["placement_specimen"] = cache
            specimen = cache["entity"]
            specimen["position"] = dict(position)
            category = game.categorise_entity_type(kind)
            if category == "puzzles":
                import g_puzzles as puzzles
                box = puzzles.bounds(specimen,tile_map)
                color = pr.Color(*puzzles.data.OBJECTS[kind]["color"],255)
                pr.draw_rectangle(round(box["x"]-camera.x),round(box["y"]-camera.y),int(box["width"]),int(box["height"]),color)
                if kind == "puzzle keypad":
                    for x in (2,5):
                        for y in (2,5):
                            pr.draw_rectangle(round(box["x"]-camera.x+x),round(box["y"]-camera.y+y),1,1,pr.WHITE)
                elif kind == "puzzle lever":
                    pr.draw_line(round(box["x"]-camera.x+4),round(box["y"]-camera.y+7),round(box["x"]-camera.x+1),round(box["y"]-camera.y),pr.WHITE)
            else:
                item = (render.build_brain_render_item if category == "brains" else render.build_pickup_render_item)("placement-preview",specimen,tile_map,assets)
                if item is not None:
                    texture = graphics.resolve_render_item_texture(item,assets)
                    if texture is not None or item.get("draw_data",{}).get("cutout_rig_parts"):
                        graphics._draw_render_item_main_shape(item,texture,camera,assets)
    else:
        kind = state.get("placement_type","point_light")
        entry = editor.ENVIRONMENT_OBJECT_REGISTRY.get(kind)
        if entry:
            specimen = entry["factory"](position)
            editor.apply_placement_radius_override(state,kind,specimen)
            if entry["target_collection"] == "emitters":
                bounds = graphics._effect_screen_bounds(specimen,tile_map,camera,scene.texture.width,scene.texture.height)
                if bounds:
                    for group in ("world_front","emissive"):
                        submission = graphics._procedural_effect_submission(specimen,group)
                        if submission:
                            info = assets["shaders"][submission["shader"]]
                            graphics._bind_effect_uniforms(info,specimen,bounds,camera,tile_map,g_effects.make_wind_profile(),now,submission["pass_mode"],scene.texture.width,scene.texture.height)
                            pr.begin_shader_mode(info["shader"])
                            pr.draw_rectangle_rec(bounds["clip"],pr.WHITE)
                            pr.end_shader_mode()
            entry["handles"]("new",specimen,camera,tile_map,True)
    pr.end_texture_mode()
    pr.begin_texture_mode(scene)
    pr.draw_texture_pro(target.texture,pr.Rectangle(0,0,target.texture.width,-target.texture.height),
        pr.Rectangle(0,0,scene.texture.width,scene.texture.height),pr.Vector2(0,0),0.,pr.Color(255,255,255,int(opacity(now)*255)))
    pr.end_texture_mode()
