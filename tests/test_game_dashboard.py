# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev2 game dashboard: factual statuses and backward-compatible Qt integration."""
import unittest
from unittest import mock

from PySide6.QtWidgets import QApplication
from vrhub.app_update_gui import HubUpdateController
from vrhub.dashboard_ui import GameDashboard, snapshot
from vrhub.gui import HubWindow
from vrhub.launcher_ui import GameBanner


def row(found=True, components=(14, 15, True)):
    return {
        "recipe": {"id": "cyberpunk-2077", "name": "Cyberpunk 2077",
                   "store": "steam", "steam_appid": 1091500},
        "game_found": found,
        "components": components,
        "has_profile": False,
        "profile_installed": False,
        "mod_installed": False,
    }


class DashboardModelTests(unittest.TestCase):
    def test_no_game_is_neutral(self):
        result = snapshot(None)
        self.assertEqual(result["game"][1], "Choose a game")
        self.assertEqual(result["vr"][1], "Not run")

    def test_detected_game_never_claims_vr(self):
        result = snapshot(row())
        self.assertEqual(result["game"][1], "Game detected")
        self.assertNotIn("VR Ready", str(result))
        self.assertEqual(result["vr"][1], "Not run")

    def test_missing_game_is_not_detected(self):
        result = snapshot(row(found=False))
        self.assertEqual(result["game"][1], "Not detected")
        self.assertEqual(result["game"][3], "warning")

    def test_mods_required_ok_but_vr_port_later(self):
        verification = {
            "rows": [{"status": "ok"}] * 14 + [{"status": "missing"}],
            "ok": 14, "total": 15, "ready": True,
            "required_bad": [], "later_bad": [{"phase": 2, "name": "CyberpunkVR Port"}]
        }
        card = snapshot(row(), verification=verification)["mods"]
        self.assertEqual(card[1], "14 / 15 installed")
        self.assertIn("later-stage", card[2])
        self.assertNotEqual(card[3], "success")

    def test_required_mod_missing_is_warning(self):
        verification = {
            "rows": [{"status": "missing"}], "ok": 0, "total": 1,
            "required_bad": [{"name": "RED4ext"}], "later_bad": [],
        }
        card = snapshot(row(), verification=verification)["mods"]
        self.assertIn("1 required", card[2])
        self.assertEqual(card[3], "warning")

    def test_all_tracked_files_is_not_a_vr_gameplay_test(self):
        verification = {
            "rows": [{"status": "ok"}], "ok": 1, "total": 1,
            "required_bad": [], "later_bad": []
        }
        self.assertIn("gameplay not tested", snapshot(row(), verification=verification)["mods"][2])

    def test_no_nexus_result_is_not_current(self):
        self.assertEqual(snapshot(row())["updates"][1], "Not checked")

    def test_updates_counts_and_uncertainty(self):
        updates = [{"status": x} for x in (
            ["update"] * 4 + ["current"] * 9 + ["unknown"] + ["not_installed"])]
        card = snapshot(row(), update_items=updates)["updates"]
        self.assertEqual(card[1], "4 updates")
        self.assertIn("9 current", card[2])
        self.assertIn("1 need review", card[2])
        self.assertIn("1 not installed", card[2])

    def test_empty_update_response_cannot_claim_all_current(self):
        self.assertEqual(snapshot(row(), update_items=[])["updates"][1], "Not checked")

    def test_single_update_has_singular_label(self):
        self.assertEqual(snapshot(row(), update_items=[{"status": "update"}])["updates"][1],
                         "1 update")

    def test_unknown_versions_are_not_current(self):
        card = snapshot(row(), update_items=[{"status": "unknown"}])["updates"]
        self.assertEqual(card[1], "Needs review")

    def test_not_installed_updates_are_pending_not_update(self):
        card = snapshot(row(), update_items=[{"status": "not_installed"}])["updates"]
        self.assertEqual(card[1], "Install pending")

    def test_successful_preflight_does_not_claim_live_vr(self):
        result = snapshot(row(), preflight={"ready": True, "rows": [
            {"name": "OpenXR", "ok": True, "required": True}]})["vr"]
        self.assertEqual(result[1], "Local checks passed")
        self.assertIn("Headset rendering not verified", result[2])

    def test_failing_preflight_has_warning(self):
        result = snapshot(row(), preflight={"ready": False, "rows": [
            {"name": "OpenXR", "ok": False, "required": True}]})["vr"]
        self.assertEqual(result[1], "Needs attention")
        self.assertEqual(result[3], "warning")

    def test_profile_only_game_is_supported(self):
        sample = row()
        sample["components"] = None
        sample["has_profile"] = True
        sample["profile_installed"] = True
        self.assertEqual(snapshot(sample)["mods"][1], "Installed")

    def test_guided_game_is_supported(self):
        sample = row()
        sample["components"] = None
        self.assertEqual(snapshot(sample)["mods"][1], "Guided setup")


class QtDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.patches = [
            mock.patch.object(HubWindow, "check_updates"),
            mock.patch.object(HubWindow, "scan_setup"),
            mock.patch.object(HubUpdateController, "startup"),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.win = HubWindow()
        self.win.show()
        self.app.processEvents()
        self.addCleanup(self.win.close)

    def test_four_actual_cards_and_original_game_tabs(self):
        self.assertIsInstance(self.win.game_dashboard, GameDashboard)
        self.assertEqual(set(self.win.game_dashboard.cards), {"game", "mods", "updates", "vr"})
        self.assertEqual(self.win.game_details_tabs.tabText(0), "Overview")
        self.assertEqual(self.win.game_details_tabs.tabText(4), "Compatibility")
        self.assertEqual(self.win.game_details_tabs.tabText(5), "Controller Bindings")
        self.assertEqual(self.win.game_dashboard.cards["vr"].value.text(), "Not run")

    def test_game_change_refreshes_all_cards(self):
        cyberpunk = next(i for i, x in enumerate(self.win.rows) if x["recipe"]["id"] == "cyberpunk-2077")
        valheim = next(i for i, x in enumerate(self.win.rows) if x["recipe"]["id"] == "valheim")
        self.win.select_launcher_game(cyberpunk)
        self.assertEqual(self.win.game_banner.heading.text(), "Cyberpunk 2077")
        self.win.select_launcher_game(valheim)
        self.assertEqual(self.win.game_banner.heading.text(), "Valheim")
        self.assertIn("Mod", self.win.game_dashboard.cards["mods"].heading.text())
        self.assertEqual(self.win.game_dashboard.cards["vr"].value.text(), "Not run")

    def test_preflight_card_only_updates_on_explicit_check(self):
        self.assertFalse(self.win.preflight_results)
        self.win.preflight_results["cyberpunk-2077"] = {"ready": True, "rows": []}
        cyberpunk = next(i for i, x in enumerate(self.win.rows) if x["recipe"]["id"] == "cyberpunk-2077")
        self.win.select_launcher_game(cyberpunk)
        self.assertEqual(self.win.game_dashboard.cards["vr"].value.text(), "Local checks passed")
        self.win.refresh()
        self.assertEqual(self.win.game_dashboard.cards["vr"].value.text(), "Not run")

    def test_1200px_window_keeps_cards_and_setup_accessible(self):
        self.win.resize(1200, 750)
        self.app.processEvents()
        widths = [card.width() for card in self.win.game_dashboard.cards.values()]
        self.assertGreaterEqual(min(widths), 145)
        self.assertTrue(self.win.game_details_tabs.isVisible())
        self.assertGreater(self.win.game_details_tabs.height(), 140)
        self.assertTrue(self.win.sidebar.game_list.isVisible())

    def test_hero_uses_local_art_or_fallback_without_network(self):
        self.assertIsInstance(self.win.game_banner, GameBanner)
        cyberpunk = next(i for i, x in enumerate(self.win.rows) if x["recipe"]["id"] == "cyberpunk-2077")
        self.win.select_launcher_game(cyberpunk)
        self.assertGreaterEqual(self.win.game_banner.minimumHeight(), 140)
        self.assertFalse(self.win.game_banner.grab().isNull())


if __name__ == "__main__":
    unittest.main()
