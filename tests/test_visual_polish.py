# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D1-C visual-only consistency across game pages and window sizes."""
import unittest
from unittest import mock

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from vrhub import theme
from vrhub.app_update_gui import HubUpdateController
from vrhub.gui import HubWindow


class VisualPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        for patch in (
            mock.patch.object(HubWindow, "check_updates"),
            mock.patch.object(HubWindow, "scan_setup"),
            mock.patch.object(HubUpdateController, "startup"),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.window = HubWindow()
        self.window.show()
        self.app.processEvents()
        self.addCleanup(self.window.close)

    def icon_opaque_colors(self, tab):
        img = self.window.game_details_tabs.tabIcon(tab).pixmap(
            QSize(18, 18)).toImage()
        return [img.pixelColor(x, y)
                for x in range(img.width())
                for y in range(img.height())
                if img.pixelColor(x, y).alpha() >= 200]

    def test_original_brand_colors_remain_unchanged(self):
        self.assertEqual((theme.YELLOW, theme.BLUE, theme.BG),
                         ("#FFD21A", "#23B7FF", "#0A0D10"))
        css = self.window.styleSheet()
        self.assertIn("QTabWidget#gameDetailsTabs QTabBar::tab:selected", css)
        self.assertIn("background: #FFD21A", css)
        self.assertIn("border-color: #23B7FF", css)

    def test_selected_tab_icons_retain_theme_shape_with_correct_contrast(self):
        icons = self.window._game_tab_original_icons
        self.assertEqual(len(icons), 7)
        for selected in (0, 2, 4, 6, 0):
            with self.subTest(selected=selected):
                self.window.game_details_tabs.setCurrentIndex(selected)
                self.app.processEvents()
                for index in range(7):
                    colors = self.icon_opaque_colors(index)
                    self.assertGreater(len(colors), 6)
                    expected = QColor(theme.BG if index == selected
                                      else theme.MUTED)
                    # QPixmap conversion uses premultiplied alpha, so
                    # anti-aliased edge pixels can round by 1 RGB unit.
                    self.assertTrue(all(
                        abs(component - target) <= 2
                        for color in colors
                        for component, target in zip(
                            (color.red(), color.green(), color.blue()),
                            (expected.red(), expected.green(), expected.blue()))))

    def test_icon_recoloring_does_not_replace_widget_or_tab_labels(self):
        tabs = self.window.game_details_tabs
        before = [tabs.widget(i) for i in range(7)]
        names = [tabs.tabText(i) for i in range(7)]
        for index in (1, 3, 5, 4, 0):
            tabs.setCurrentIndex(index)
            self.app.processEvents()
        self.assertEqual([tabs.widget(i) for i in range(7)], before)
        self.assertEqual([tabs.tabText(i) for i in range(7)], names)
        self.assertTrue(tabs.tabBar().usesScrollButtons())

    def test_overview_secondary_actions_have_consistent_presentation_only(self):
        self.assertEqual(self.window.launch_tools_panel.objectName(),
                         "overviewLaunchTools")
        self.assertEqual(self.window.launch_tools_label.objectName(),
                         "launchToolsLabel")
        self.assertLessEqual(self.window.launch_tools_panel.maximumWidth(), 760)
        for button in (self.window.copy_btn, self.window.inject_btn,
                       self.window.doom_probe_btn):
            self.assertEqual(button.objectName(), "overviewSecondaryLaunch")
            self.assertIs(button.parent(), self.window.launch_tools_panel)
        self.assertEqual(self.window.game_launch_btn.objectName(),
                         "primaryAction")
        self.assertIn("QPushButton#overviewSecondaryLaunch:hover",
                      self.window.styleSheet())

    def test_disclosures_keep_accessible_states_and_original_text(self):
        for button, panel, page in (
            (self.window.library_toggle, self.window.library_panel,
             self.window.overview_page),
            (self.window.update_tools_toggle, self.window.update_tools_panel,
             self.window.mod_updates),
            (self.window.more_tools_toggle, self.window.more_tools_panel,
             self.window.compat_page),
        ):
            with self.subTest(button=button.text()):
                self.window.game_details_tabs.setCurrentWidget(page)
                self.app.processEvents()
                self.assertFalse(panel.isVisible())
                self.assertFalse(button.isChecked())
                button.click()
                self.app.processEvents()
                self.assertTrue(panel.isVisible())
                self.assertTrue(button.isChecked())
                button.click()
                self.app.processEvents()
                self.assertFalse(panel.isVisible())
                self.assertFalse(button.isChecked())
        self.assertTrue(self.window.install_tools_toggle.isHidden())
        self.assertTrue(self.window.install_tools_panel.isHidden())
        self.assertEqual(self.window.downloads.layout().indexOf(
            self.window.install_tools_panel), -1)
        self.assertIn("QPushButton#launcherDisclosure:checked",
                      self.window.styleSheet())
        self.assertIn("font-size: 12px", self.window.styleSheet())

    def test_compatibility_margins_consistent_without_changing_its_report(self):
        margins = self.window.compat_page.layout().contentsMargins()
        self.assertEqual((margins.left(), margins.top(),
                          margins.right(), margins.bottom()), (12, 12, 12, 12))
        self.window.game_details_tabs.setCurrentWidget(self.window.compat_page)
        self.app.processEvents()
        self.assertIn("Bundled compatibility reference",
                      self.window.compat_details.toHtml())
        self.assertEqual(self.window.compat_refresh_btn.text(),
                         "Refresh compatibility")

    def test_narrow_windows_scroll_tab_strip_not_entire_page(self):
        for width, height in ((1630, 1060), (1200, 750),
                              (920, 600), (850, 560)):
            with self.subTest(width=width):
                self.window.resize(width, height)
                self.app.processEvents()
                self.assertEqual((self.window.width(), self.window.height()),
                                 (width, height))
                self.assertEqual(
                    self.window.game_page_scroll.horizontalScrollBar().maximum(), 0)
                self.assertTrue(
                    self.window.game_details_tabs.tabBar().usesScrollButtons())
