import unittest
from unittest import mock

import g_main
import g_update_and_render


class _FakeTexture:
    def __init__(self, texture_id):
        self.id = texture_id
        self.width = 4
        self.height = 4


class AssetHotReloadTests(unittest.TestCase):
    def test_snapshot_diff_detects_modified_added_and_deleted_pngs(self):
        previous = {
            "art/modified.png": (1, 10),
            "art/deleted.png": (1, 10),
            "art/unchanged.png": (1, 10),
        }
        current = {
            "art/modified.png": (2, 10),
            "art/added.png": (2, 10),
            "art/unchanged.png": (1, 10),
        }
        self.assertEqual(
            g_main.changed_snapshot_files(previous, current),
            [
                "art/added.png",
                "art/deleted.png",
                "art/modified.png",
            ],
        )

    def test_png_change_reloads_assets_and_advances_snapshot(self):
        snapshot = {"art/player.png": (1, 10)}
        current = {"art/player.png": (2, 12)}
        assets = {"textures": {}}
        with mock.patch.object(
            g_main, "get_png_asset_snapshot", return_value=current,
        ), mock.patch.object(
            g_main.update_and_render_module, "reload_image_assets",
        ) as reload_assets:
            changed = g_main.reload_png_assets_if_needed(snapshot, assets)
        self.assertEqual(changed, ["art/player.png"])
        self.assertEqual(snapshot, current)
        reload_assets.assert_called_once_with(assets)

    def test_failed_png_reload_keeps_snapshot_for_retry(self):
        snapshot = {"art/player.png": (1, 10)}
        original = dict(snapshot)
        current = {"art/player.png": (2, 12)}
        with mock.patch.object(
            g_main, "get_png_asset_snapshot", return_value=current,
        ), mock.patch.object(
            g_main.update_and_render_module, "reload_image_assets",
            side_effect=RuntimeError("still being written"),
        ), mock.patch.object(g_main, "render_error_message") as report:
            changed = g_main.reload_png_assets_if_needed(snapshot, {})
        self.assertEqual(changed, [])
        self.assertEqual(snapshot, original)
        report.assert_called_once()

    def test_image_asset_reload_swaps_before_unloading_old_handles(self):
        old_textures = {"old": _FakeTexture(1)}
        old_sheets = {"old_sheet": {"sheet": _FakeTexture(2)}}
        new_textures = {"new": _FakeTexture(3)}
        new_sheets = {"new_sheet": {"sheet": _FakeTexture(4)}}
        assets = {
            "textures": old_textures,
            "sprite_sheets": old_sheets,
        }
        with mock.patch.object(
            g_update_and_render, "load_textures", return_value=new_textures,
        ), mock.patch.object(
            g_update_and_render, "load_sprite_sheets", return_value=new_sheets,
        ), mock.patch.object(
            g_update_and_render, "unload_image_asset_collections",
            return_value=2,
        ) as unload:
            result = g_update_and_render.reload_image_assets(assets)
        self.assertIs(assets["textures"], new_textures)
        self.assertIs(assets["sprite_sheets"], new_sheets)
        unload.assert_called_once_with(old_textures, old_sheets)
        self.assertEqual(result["unloaded"], 2)

    def test_image_asset_unload_deduplicates_shared_texture_handles(self):
        shared = _FakeTexture(7)
        with mock.patch.object(g_update_and_render.pr, "unload_texture") as unload:
            count = g_update_and_render.unload_image_asset_collections(
                {"one": shared}, {"sheet": {"sheet": shared}},
            )
        self.assertEqual(count, 1)
        unload.assert_called_once_with(shared)

    def test_invalid_replacement_does_not_discard_live_asset_collections(self):
        old_textures = {"old": _FakeTexture(1)}
        old_sheets = {"old_sheet": {"sheet": _FakeTexture(2)}}
        invalid = _FakeTexture(0)
        assets = {
            "textures": old_textures,
            "sprite_sheets": old_sheets,
        }
        with mock.patch.object(
            g_update_and_render, "load_textures",
            return_value={"broken": invalid},
        ), mock.patch.object(
            g_update_and_render, "load_sprite_sheets", return_value={},
        ), mock.patch.object(
            g_update_and_render, "unload_image_asset_collections",
        ) as unload:
            with self.assertRaisesRegex(RuntimeError, "textures.broken"):
                g_update_and_render.reload_image_assets(assets)
        self.assertIs(assets["textures"], old_textures)
        self.assertIs(assets["sprite_sheets"], old_sheets)
        unload.assert_called_once()


if __name__ == "__main__":
    unittest.main()
