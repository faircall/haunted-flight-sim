"""Hidden GPU check for actual Chinese text and modal composition."""
from pathlib import Path
import pyray as pr
import g_interactions as ui
import g_inventory as inv
from test_puzzles import make_arena

pr.set_config_flags(pr.ConfigFlags.FLAG_WINDOW_HIDDEN)
pr.init_window(480, 270, "Inventory and Chinese text validation")
assets = {}
target = pr.load_render_texture(480, 270)
arena = ui.ensure(make_arena())
inv.add(arena["player_info"]["inventory"], dict(kind="key", group="1", count=1))
inv.add(arena["player_info"]["inventory"], dict(kind="health", value=25, count=1))
Path("artifacts/inventory").mkdir(parents=True, exist_ok=True)
try:
    for language in ("en", "zh_hans", "zh_hant"):
        ui.data.LANGUAGE = language
        font = ui.text.font(assets, "物品栏铭文鑰匙")
        assert font.texture.id > 0
        for char in "物品铭文鑰匙":
            index = pr.get_glyph_index(font, ord(char))
            assert font.glyphs[index].value == ord(char), char
        for mode in ("inventory", "dialogue"):
            if mode == "inventory":
                arena["interaction_runtime"]["modal"] = dict(kind="inventory", message="")
            else:
                definition = ui.data.DESCRIPTIONS["old_inscription"]
                arena = ui.open_dialogue(arena, definition["pages"], definition["choices"], "demo")
                arena["interaction_runtime"]["modal"]["page"] = 1
            pr.begin_texture_mode(target)
            pr.clear_background(pr.Color(55, 45, 35, 255))
            ui.draw(arena, assets)
            pr.end_texture_mode()
            image = pr.load_image_from_texture(target.texture)
            pr.image_flip_vertical(image)
            pr.export_image(image, f"artifacts/inventory/{language}-{mode}.png")
            pr.unload_image(image)
    print("Inventory, Chinese glyphs and both Chinese variants rendered successfully")
finally:
    ui.text.unload(assets)
    pr.unload_render_texture(target)
    pr.close_window()
