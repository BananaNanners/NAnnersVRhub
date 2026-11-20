# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev2 follow-up: full window must genuinely resize at KDE desktop scales.

Tests assert actual Qt geometry, not just a successful resize() call.
"""
import unittest
from unittest import mock

from PySide6.QtWidgets import QApplication, QScrollArea
from vrhub.app_update_gui import HubUpdateController
from vrhub.gui import HubWindow


class ResponsiveLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        patchers = [
            mock.patch.object(HubWindow, "check_updates"),
            mock.patch.object(HubWindow, "scan_setup"),
            mock.patch.object(HubUpdateController, "startup"),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.window = HubWindow()
        self.window.show()
        self.app.processEvents()
        self.addCleanup(self.window.close)

    def set_dimensions(self, width, height):
        self.window.resize(width, height)
        self.app.processEvents()
        self.assertEqual((self.window.width(), self.window.height()), (width, height))

    def test_minimum_does_not_force_maximizing_on_laptop_screen(self):
        self.assertLessEqual(self.window.minimumSizeHint().height(), 600)
        self.assertLessEqual(self.window.minimumSizeHint().width(), 850)
        self.set_dimensions(920, 600)
        self.assertTrue(self.window.sidebar.system_button.isVisible())
        self.assertTrue(self.window.sidebar.games_button.isVisible())

    def test_compact_page_scrolls_vertically_not_horizontally(self):
        self.assertIsInstance(self.window.game_page_scroll, QScrollArea)
        for width, height in ((1200, 750), (1000, 700), (920, 600), (850, 560)):
            with self.subTest(size=(width, height)):
                self.set_dimensions(width, height)
                scroll = self.window.game_page_scroll
                self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
                self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
                self.assertTrue(self.window.game_details_tabs.isVisible())

    def test_compact_cards_use_two_readable_columns(self):
        self.set_dimensions(1000, 700)
        self.assertEqual(self.window.game_dashboard._columns, 2)
        self.assertEqual(self.window.quick_actions._columns, 2)
        self.assertGreaterEqual(min(card.width() for card
                                    in self.window.game_dashboard.cards.values()), 300)
        self.assertTrue(self.window.preflight_btn.isVisible())

    def test_first_drag_reflow_never_clips_cards_or_action_buttons(self):
        for width, height in ((1450, 880), (1120, 720),
                              (920, 600), (1450, 880), (1120, 720)):
            with self.subTest(size=(width, height)):
                self.set_dimensions(width, height)
                cards = self.window.game_dashboard
                actions = self.window.quick_actions
                self.assertTrue(all(
                    card.y() + card.height() <= cards.height()
                    for card in cards.cards.values()))
                self.assertTrue(all(
                    button.y() + button.height() <= actions.height()
                    for button in actions.buttons if button.isVisible()))
                self.assertGreaterEqual(cards.height(), cards.minimumSizeHint().height())
                self.assertGreaterEqual(actions.height(), actions.minimumSizeHint().height())

    def test_mid_width_keeps_shortcuts_and_content(self):
        self.set_dimensions(1200, 750)
        self.assertEqual(self.window.game_dashboard._columns, 2)
        self.assertEqual(self.window.quick_actions._columns, 5)
        self.assertGreater(self.window.game_details_tabs.width(), 600)

    def test_wide_window_centers_and_caps_content(self):
        self.set_dimensions(2200, 1200)
        page = self.window.game_page_scroll.widget()
        self.assertLessEqual(page.width(), 1420)
        self.assertGreaterEqual(page.width(), 1300)
        self.assertEqual(self.window.game_dashboard._columns, 4)
        self.assertEqual(self.window.quick_actions._columns, 5)
        self.assertEqual(self.window.game_page_scroll.horizontalScrollBar().maximum(), 0)
        self.assertLessEqual(max(card.width() for card
                                 in self.window.game_dashboard.cards.values()), 360)

    def test_vr_system_and_games_navigation_stay_visible(self):
        self.set_dimensions(920, 600)
        self.window.sidebar.system_button.click()
        self.app.processEvents()
        self.assertEqual(self.window.tabs.currentIndex(), 0)
        self.window.sidebar.games_button.click()
        self.app.processEvents()
        self.assertEqual(self.window.tabs.currentIndex(), 1)
        self.assertIs(self.window.tabs.widget(1), self.window.game_page_scroll)

    def test_expanding_old_tools_does_not_resize_main_window(self):
        self.set_dimensions(1000, 700)
        self.window.more_tools_toggle.click()
        self.app.processEvents()
        self.assertTrue(self.window.more_tools_panel.isVisible())
        self.assertEqual((self.window.width(), self.window.height()), (1000, 700))
        self.assertGreater(self.window.game_page_scroll.verticalScrollBar().maximum(), 0)
        self.window.library_toggle.click()
        self.app.processEvents()
        self.assertTrue(self.window.library_panel.isVisible())
        self.assertEqual((self.window.width(), self.window.height()), (1000, 700))

    def test_scrolling_can_reach_setup_guide_without_maximizing(self):
        self.set_dimensions(920, 600)
        scroll = self.window.game_page_scroll.verticalScrollBar()
        self.assertGreater(scroll.maximum(), 0)
        scroll.setValue(scroll.maximum())
        self.app.processEvents()
        self.assertEqual(scroll.value(), scroll.maximum())
        self.assertTrue(self.window.game_details_tabs.isVisible())


if __name__ == "__main__":
    unittest.main()
