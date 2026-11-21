# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5A layout polish: spreadsheet-style, remembered and safe column widths."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QHeaderView, QTableWidget, QTableWidgetItem

from vrhub import hub, table_columns as tc
from vrhub.app_update_gui import HubUpdateController
from vrhub.gui import HubWindow
from vrhub.mod_updates_gui import ModUpdatesPage
from vrhub.downloads_gui import GuidedDownloadsPage


class ColumnWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.prefs = self.dir / "column-layouts.json"
        patch = mock.patch.object(tc, "preferences_file", return_value=self.prefs)
        patch.start()
        self.addCleanup(patch.stop)

    def fixture(self, key="game-library", sizes=(320, 135, 135, 135, 165),
                visible=True, text="Long Game Title / VR Plugin / Several Extra Words"):
        table = QTableWidget(2, 5)
        table.setHorizontalHeaderLabels(["Game", "Game install", "Mod", "Profile", "Updates"])
        table.setObjectName(key)
        for row in range(2):
            for col in range(5):
                table.setItem(row, col, QTableWidgetItem(text if col == 0 else "A value"))
        controller = tc.enable_spreadsheet_columns(
            table, key, sizes, min_row_height=30)
        table.resize(1050, 270)
        if visible:
            table.show()
            self.app.processEvents()
        def safe_close():
            try:
                table.close()
            except RuntimeError:
                pass  # another test intentionally deletes the Qt widget first
        self.addCleanup(safe_close)
        return table, controller

    def test_all_five_headers_are_interactive_not_fixed_or_stretched(self):
        table, behavior = self.fixture()
        header = table.horizontalHeader()
        for col in range(5):
            self.assertEqual(header.sectionResizeMode(col), QHeaderView.Interactive)
        self.assertFalse(header.stretchLastSection())
        self.assertTrue(table.wordWrap())
        self.assertEqual(table.horizontalScrollBarPolicy(), Qt.ScrollBarAsNeeded)
        self.assertFalse(self.prefs.exists())  # simply opening causes no write

    def test_first_show_fills_available_width_without_locking_sections(self):
        table, behavior = self.fixture()
        self.app.processEvents()
        viewport = table.viewport().width()
        allocated = sum(table.columnWidth(i) for i in range(5))
        self.assertLess(abs(viewport - allocated), 20)
        for i in range(5):
            self.assertEqual(table.horizontalHeader().sectionResizeMode(i),
                             QHeaderView.Interactive)
        self.assertFalse(self.prefs.exists())

    def test_separator_drag_resizes_game_column(self):
        table, behavior = self.fixture()
        header = table.horizontalHeader()
        initial = table.columnWidth(0)
        border = header.sectionViewportPosition(0) + header.sectionSize(0) - 2
        point_y = max(5, header.height() // 2)
        from PySide6.QtCore import QPoint
        QTest.mousePress(header.viewport(), Qt.LeftButton,
                         Qt.NoModifier, QPoint(border, point_y))
        for dx in (22, 47, 81):
            QTest.mouseMove(header.viewport(), QPoint(border + dx, point_y))
        QTest.mouseRelease(header.viewport(), Qt.LeftButton,
                           Qt.NoModifier, QPoint(border + 81, point_y))
        self.app.processEvents()
        self.assertGreater(table.columnWidth(0), initial + 25)

    def test_double_click_header_separator_auto_fits_content(self):
        table, behavior = self.fixture(text="Tiny")
        table.setItem(0, 0, QTableWidgetItem("A long enough display value for auto fitting"))
        table.setColumnWidth(0, 110)
        header = table.horizontalHeader()
        from PySide6.QtCore import QPoint
        border = header.sectionViewportPosition(0) + header.sectionSize(0) - 2
        QTest.mouseDClick(header.viewport(), Qt.LeftButton, Qt.NoModifier,
                         QPoint(border, max(5, header.height() // 2)))
        self.app.processEvents()
        self.assertGreater(table.columnWidth(0), 150)
        self.assertLessEqual(table.columnWidth(0), 720)

    def test_auto_fit_long_filename_is_bounded(self):
        table, controller = self.fixture(key="guided-downloads")
        table.setItem(0, 0, QTableWidgetItem("Very long " * 130))
        controller._fit_column(0)
        self.app.processEvents()
        self.assertLessEqual(table.columnWidth(0), 720)

    def test_column_widths_are_remembered_after_manual_resize(self):
        table, controller = self.fixture()
        table.setColumnWidth(0, 245)
        table.setColumnWidth(4, 235)
        controller.flush()
        raw = json.loads(self.prefs.read_text())
        self.assertEqual(raw["tables"]["game-library"][0], 245)
        self.assertEqual(raw["tables"]["game-library"][4], 235)
        other, _ = self.fixture(visible=False)
        self.assertEqual(other.columnWidth(0), 245)
        self.assertEqual(other.columnWidth(4), 235)

    def test_saved_widths_are_independent_per_table(self):
        table, controller = self.fixture()
        table.setColumnWidth(1, 245)
        controller.flush()
        another, independent = self.fixture(key="guided-downloads")
        self.assertNotEqual(another.columnWidth(1), 245)
        another.setColumnWidth(2, 445)
        independent.flush()
        saved = json.loads(self.prefs.read_text())["tables"]
        self.assertEqual(saved["game-library"][1], 245)
        self.assertEqual(saved["guided-downloads"][2], 445)

    def test_corrupted_preferences_preserved_not_overwritten(self):
        self.prefs.write_text('{"unexpected":"data"}')
        prior = self.prefs.read_bytes()
        table, behavior = self.fixture()
        table.setColumnWidth(0, 248)
        behavior.flush()
        self.assertEqual(self.prefs.read_bytes(), prior)
        self.assertIn("could not be saved", table.toolTip())

    def test_symlink_preferences_do_not_overwrite_target(self):
        outside = self.dir / "important.json"
        outside.write_text('{"do-not-touch":1}')
        self.prefs.symlink_to(outside)
        table, behavior = self.fixture()
        table.setColumnWidth(0, 230)
        behavior.flush()
        self.assertEqual(outside.read_text(), '{"do-not-touch":1}')

    def test_text_wraps_after_narrow_column_without_resizing_window(self):
        table, controller = self.fixture()
        table.setColumnWidth(0, 105)
        controller.reflow_rows()
        self.assertGreater(table.rowHeight(0), 30)
        self.assertLessEqual(table.rowHeight(0), 140)
        self.assertEqual(table.width(), 1050)
        self.assertGreater(table.horizontalScrollBar().maximum(), 0) if sum(
            table.columnWidth(i) for i in range(5)) > table.viewport().width() else None

    def test_deferred_first_show_is_owned_by_table(self):
        table, controller = self.fixture()
        table.close()
        table.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()  # no deferred callback to a deleted Qt object


class IntegratedColumnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pref_file = Path(self.temp.name) / "widths.json"
        for p in (
            mock.patch.object(tc, "preferences_file", return_value=self.pref_file),
            mock.patch.object(HubWindow, "check_updates"),
            mock.patch.object(HubWindow, "scan_setup"),
            mock.patch.object(HubUpdateController, "startup")):
            p.start()
            self.addCleanup(p.stop)
        self.window = HubWindow()
        self.window.show()
        self.app.processEvents()
        self.addCleanup(self.cleanup_window)

    def cleanup_window(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def test_library_game_column_not_forced_to_take_whole_width(self):
        # Qt's default 800px offscreen screen gives a very narrow library
        # pane, unlike the user's actual 1630px desktop window.
        self.window.resize(1630, 1060)
        self.app.processEvents()
        self.window.library_toggle.click()
        self.app.processEvents()
        table = self.window.table
        self.assertEqual(table.horizontalHeader().sectionResizeMode(0),
                         QHeaderView.Interactive)
        # Instead of swallowing almost all width, all five get useful room.
        self.assertLess(table.columnWidth(0), table.viewport().width() * 0.65)
        self.assertGreaterEqual(table.columnWidth(1), 130)
        self.assertEqual(table.item(0, 0).toolTip(), table.item(0, 0).text())

    def test_all_download_columns_are_manually_resizable(self):
        t = self.window.downloads.table
        self.window.game_details_tabs.setCurrentIndex(self.window.game_details_tabs.indexOf(self.window.downloads))
        self.app.processEvents()
        for i in range(5):
            self.assertEqual(t.horizontalHeader().sectionResizeMode(i),
                             QHeaderView.Interactive)
        before = t.columnWidth(2)
        t.setColumnWidth(2, before + 40)
        self.window.downloads.set_recipe(hub.load_recipes()["subnautica"])
        self.app.processEvents()
        self.assertEqual(t.columnWidth(2), before + 40)

    def test_mod_updates_rows_are_resizable_and_keep_links(self):
        self.window.game_details_tabs.setCurrentIndex(self.window.game_details_tabs.indexOf(self.window.mod_updates))
        self.app.processEvents()
        table = self.window.mod_updates.sections["update"].table
        self.assertEqual(table.horizontalHeader().sectionResizeMode(0),
                         QHeaderView.Interactive)
        table.setColumnWidth(0, 210)
        table.spreadsheet_columns.reflow_rows()
        self.assertEqual(table.columnWidth(0), 210)
        self.assertEqual(table.verticalScrollBarPolicy(), Qt.ScrollBarAlwaysOff)

    def test_compact_920_window_keeps_outer_page_unscrolled_horizontally(self):
        self.window.library_toggle.click()
        self.window.game_details_tabs.setCurrentIndex(self.window.game_details_tabs.indexOf(self.window.downloads))
        self.window.resize(920, 600)
        self.app.processEvents()
        self.assertEqual(self.window.game_page_scroll.horizontalScrollBar().maximum(), 0)
        self.assertEqual((self.window.width(), self.window.height()), (920, 600))


if __name__ == "__main__":
    unittest.main()
