# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev4: local-only artwork import, restoration, discovery, Qt presentation."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from vrhub import artwork, hub
from vrhub.gui import HubWindow
from vrhub.app_update_gui import HubUpdateController


def png_file(path: Path, width=640, height=240):
    image = QImage(width, height, QImage.Format_RGB32)
    image.fill(QColor("#23B7FF"))
    if not image.save(str(path), "PNG"):
        raise RuntimeError("Could not write fake artwork fixture")
    return path


class ArtworkManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "homedir"
        self.home.mkdir()
        self.data = self.root / "data"
        patcher1 = mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(self.data)})
        patcher2 = mock.patch.object(artwork.Path, "home", return_value=self.home)
        patcher3 = mock.patch("vrhub.artwork.heroic_config_roots",
                              return_value=[self.home / ".config/heroic"])
        for p in (patcher1, patcher2, patcher3):
            p.start()
            self.addCleanup(p.stop)
        self.cp = {"id": "cyberpunk-2077", "steam_appid": 1091500}
        self.hl = {"id": "hogwarts-legacy", "store": "heroic-epic",
                   "heroic_title": "Hogwarts Legacy"}
        self.doom = {"id": "doom-2016-gog", "store": "heroic-gog",
                     "heroic_appid": "1390579243"}

    def test_empty_falls_back_to_original(self):
        result = artwork.locate_artwork(self.cp)
        self.assertIsNone(result.path)
        self.assertEqual(result.source, "NAnnersVRhub original banner")
        self.assertFalse(self.data.exists())

    def test_local_steam_hero_is_detected_without_copying_it(self):
        path = self.home / ".local/share/Steam/appcache/librarycache/1091500/library_hero.jpg"
        path.parent.mkdir(parents=True)
        # Formats are detected from actual bytes, not just extension.
        png_file(path)
        result = artwork.locate_artwork(self.cp)
        self.assertEqual(result.path, path)
        self.assertEqual(result.source, "Steam library artwork")
        self.assertFalse(result.custom)
        self.assertFalse(self.data.exists())

    def test_local_steam_header_is_valid_fallback(self):
        path = self.home / ".local/share/Steam/appcache/librarycache/1091500/header.jpg"
        path.parent.mkdir(parents=True)
        png_file(path)
        self.assertEqual(artwork.locate_artwork(self.cp).path, path)

    def test_custom_steam_grid_overrides_built_in_art(self):
        base = self.home / ".local/share/Steam"
        original = base / "appcache/librarycache/1091500/library_hero.jpg"
        custom = base / "userdata/12345/config/grid/1091500_hero.png"
        for x in (original, custom):
            x.parent.mkdir(parents=True, exist_ok=True)
            png_file(x)
        result = artwork.locate_artwork(self.cp)
        self.assertEqual(result.path, custom)
        self.assertEqual(result.source, "Steam custom grid artwork")

    def test_heroic_epic_local_art_matches_recorded_installed_title(self):
        root = self.home / ".config/heroic"
        installed = root / "legendaryConfig/legendary/installed.json"
        installed.parent.mkdir(parents=True)
        installed.write_text('{"abc123": {"title":"Hogwarts Legacy"}}')
        icon = root / "icons/abc123.jpg"
        icon.parent.mkdir()
        png_file(icon)
        result = artwork.locate_artwork(self.hl)
        self.assertEqual(result.path, icon)
        self.assertEqual(result.source, "Heroic local cover artwork")
        self.assertFalse(result.custom)

    def test_heroic_gog_local_art_is_detected_without_install_writes(self):
        icon = self.home / ".config/heroic/icons/1390579243.png"
        icon.parent.mkdir(parents=True)
        png_file(icon)
        self.assertEqual(artwork.locate_artwork(self.doom).path, icon)

    def test_custom_png_import_is_scoped_per_game_and_persists(self):
        src = png_file(self.root / "my-art.png", 1200, 600)
        before = src.read_bytes()
        stored = artwork.import_banner(self.cp, src)
        self.assertEqual(stored, self.data / "nannersvrhub/artwork/cyberpunk-2077.png")
        self.assertTrue(stored.is_file())
        self.assertEqual(src.read_bytes(), before)
        self.assertEqual(artwork.locate_artwork(self.cp).path, stored)
        self.assertTrue(artwork.locate_artwork(self.cp).custom)
        # Separate call simulates next program invocation without global state.
        self.assertEqual(artwork.locate_artwork(dict(self.cp)).path, stored)
        self.assertFalse(artwork.locate_artwork(self.doom).custom)
        self.assertEqual(stored.stat().st_mode & 0o777, 0o600)

    def test_png_jpeg_and_webp_import_when_qt_supports_them(self):
        for file_format, suffix in (("PNG", "png"), ("JPEG", "jpg"), ("WEBP", "webp")):
            with self.subTest(format=file_format):
                img = QImage(400, 200, QImage.Format_RGB32)
                img.fill(QColor("#FFD21A"))
                filename = self.root / f"input.{suffix}"
                if not img.save(str(filename), file_format):
                    if file_format == "WEBP":
                        continue  # Optional Qt WebP plugin; handled when installed.
                    self.fail(f"Qt cannot encode {file_format} test fixture")
                stored = artwork.import_banner(self.cp, filename)
                self.assertTrue(stored.is_file())
                self.assertEqual(artwork.locate_artwork(self.cp).path, stored)
                self.assertTrue(artwork.restore_default(self.cp))

    def test_restoring_default_preserves_original_and_steam_art(self):
        steam = self.home / ".local/share/Steam/appcache/librarycache/1091500/library_hero.png"
        steam.parent.mkdir(parents=True)
        png_file(steam)
        src = png_file(self.root / "custom.png")
        steam_before = steam.read_bytes()
        source_before = src.read_bytes()
        dest = artwork.import_banner(self.cp, src)
        self.assertTrue(artwork.restore_default(self.cp))
        self.assertFalse(dest.exists())
        self.assertFalse(artwork.restore_default(self.cp))
        self.assertEqual(artwork.locate_artwork(self.cp).path, steam)
        self.assertEqual(src.read_bytes(), source_before)
        self.assertEqual(steam.read_bytes(), steam_before)

    def test_invalid_file_never_clobbers_existing_custom_choice(self):
        source = png_file(self.root / "banner.png")
        dest = artwork.import_banner(self.cp, source)
        old = dest.read_bytes()
        corrupt = self.root / "bad.png"
        corrupt.write_bytes(b"not an actual PNG")
        with self.assertRaisesRegex(ValueError, "not supported"):
            artwork.import_banner(self.cp, corrupt)
        self.assertEqual(dest.read_bytes(), old)
        with self.assertRaisesRegex(ValueError, "Choose a JPG"):
            artwork.import_banner(self.cp, self.root / "not-an-image.txt")
        self.assertEqual(dest.read_bytes(), old)

    def test_missing_source_and_oversized_image_fail_without_modification(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            artwork.import_banner(self.cp, self.root / "missing.png")
        too_large = self.root / "oversized.png"
        with too_large.open("wb") as out:
            out.truncate(artwork.MAX_IMAGE_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "25 MB"):
            artwork.import_banner(self.cp, too_large)
        self.assertFalse(artwork.custom_artwork_path(self.cp).exists())

    def test_unsafe_game_id_cannot_traverse_directory(self):
        for rid in ("../evil", "/tmp/evil", "", "UPPER", "space name"):
            with self.subTest(id=rid):
                recipe = {"id": rid}
                with self.assertRaises(ValueError):
                    artwork.custom_artwork_path(recipe)
                with self.assertRaises(ValueError):
                    artwork.restore_default(recipe)
                with self.assertRaises(ValueError):
                    artwork.import_banner(recipe, self.root / "image.png")

    def test_only_explicit_source_file_can_change_banner(self):
        recipe = dict(self.cp)
        icon = self.home / ".local/share/Steam/appcache/librarycache/1091500/library_hero.png"
        icon.parent.mkdir(parents=True)
        png_file(icon)
        before = icon.read_bytes()
        imported = png_file(self.root / "custom.png")
        artwork.import_banner(recipe, imported)
        self.assertEqual(icon.read_bytes(), before)
        self.assertTrue(artwork.custom_artwork_path(recipe).is_file())

    def test_damaged_user_copy_falls_back_to_available_game_art(self):
        source = self.home / ".local/share/Steam/appcache/librarycache/1091500/library_hero.png"
        source.parent.mkdir(parents=True)
        png_file(source)
        managed = artwork.custom_artwork_path(self.cp)
        managed.parent.mkdir(parents=True)
        managed.write_bytes(b"broken managed image")
        self.assertEqual(artwork.locate_artwork(self.cp).path, source)


class ArtworkWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.xdg = self.root / "data"
        self.saved = mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(self.xdg)})
        self.saved.start()
        self.addCleanup(self.saved.stop)
        for patcher in (
            mock.patch.object(HubWindow, "check_updates"),
            mock.patch.object(HubWindow, "scan_setup"),
            mock.patch.object(HubUpdateController, "startup")):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.window = HubWindow()
        self.window.show()
        self.app.processEvents()
        self.addCleanup(self.dispose_window)

    def dispose_window(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def select_game(self, rid):
        i = next(i for i, row in enumerate(self.window.rows)
                 if row["recipe"]["id"] == rid)
        self.window.sidebar.game_list.setCurrentRow(i)
        self.app.processEvents()

    def test_banner_controls_exist_for_all_nine_games(self):
        self.assertEqual(self.window.sidebar.game_list.count(), 9)
        for row in self.window.rows:
            self.select_game(row["recipe"]["id"])
            self.assertTrue(self.window.change_banner_btn.isEnabled())
            self.assertIn("Artwork:", self.window.artwork_label.text())
            self.assertIn("banner", self.window.change_banner_btn.text().lower())

    def test_copy_select_and_restore_affects_hub_art_only(self):
        self.select_game("cyberpunk-2077")
        incoming = png_file(self.root / "example.png")
        original_bytes = incoming.read_bytes()
        with mock.patch("vrhub.gui.QFileDialog.getOpenFileName",
                        return_value=(str(incoming), "Image files")):
            self.window.change_banner_btn.click()
        self.app.processEvents()
        self.assertTrue(self.window.game_banner.artwork_choice.custom)
        self.assertTrue(self.window.restore_banner_btn.isEnabled())
        self.assertEqual(incoming.read_bytes(), original_bytes)
        self.assertTrue(artwork.custom_artwork_path(self.window.current()).exists())
        self.window.restore_banner_btn.click()
        self.app.processEvents()
        self.assertFalse(self.window.game_banner.artwork_choice.custom)
        self.assertFalse(artwork.custom_artwork_path(self.window.current()).exists())
        self.assertEqual(incoming.read_bytes(), original_bytes)

    def test_other_game_keeps_its_own_banner(self):
        self.select_game("cyberpunk-2077")
        source = png_file(self.root / "banner.png")
        artwork.import_banner(self.window.current(), source)
        self.window.show_details()
        self.select_game("valheim")
        self.assertFalse(self.window.game_banner.artwork_choice.custom)
        self.select_game("cyberpunk-2077")
        self.assertTrue(self.window.game_banner.artwork_choice.custom)

    def test_window_resize_with_artwork_controls_keeps_no_horizontal_scroll(self):
        for width, height in ((1630, 1060), (920, 600), (850, 560)):
            self.window.resize(width, height)
            self.app.processEvents()
            self.assertEqual((self.window.width(), self.window.height()), (width, height))
            self.assertEqual(self.window.game_page_scroll.horizontalScrollBar().maximum(), 0)
            self.assertTrue(self.window.change_banner_btn.isVisible())

    def test_restore_button_can_clear_a_damaged_managed_custom_copy(self):
        self.select_game("cyberpunk-2077")
        managed = artwork.custom_artwork_path(self.window.current())
        managed.parent.mkdir(parents=True, exist_ok=True)
        managed.write_bytes(b"damaged personal copy")
        self.window.show_details()
        self.assertFalse(self.window.game_banner.artwork_choice.custom)
        self.assertTrue(self.window.restore_banner_btn.isEnabled())
        self.window.restore_banner_btn.click()
        self.app.processEvents()
        self.assertFalse(managed.exists())

    def test_cancelled_picker_does_not_write_data(self):
        with mock.patch("vrhub.gui.QFileDialog.getOpenFileName", return_value=("", "")):
            self.window.change_banner_btn.click()
        self.assertFalse(self.xdg.exists())

    def test_invalid_picker_reports_warning_and_preserves_state(self):
        self.select_game("cyberpunk-2077")
        broken = self.root / "broken.jpg"
        broken.write_bytes(b"invalid JPEG")
        with mock.patch("vrhub.gui.QFileDialog.getOpenFileName",
                        return_value=(str(broken), "Image files")), mock.patch(
                            "vrhub.gui.QMessageBox.warning") as warning:
            self.window.change_banner_btn.click()
        self.assertEqual(warning.call_count, 1)
        self.assertFalse(self.window.game_banner.artwork_choice.custom)

    def test_default_size_and_mod_updates_tab_are_unchanged(self):
        from vrhub.gui import preferred_launcher_size
        self.assertEqual(preferred_launcher_size(2327, 1309), (1630, 1060))
        self.assertEqual(self.window.game_details_tabs.tabText(0), "Overview")
        self.assertEqual(self.window.game_details_tabs.tabText(1), "Mod Updates")
        self.assertIn("#FFD21A", self.window.styleSheet())
        self.assertIn("#23B7FF", self.window.styleSheet())


if __name__ == "__main__":
    unittest.main()
