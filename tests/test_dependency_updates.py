"""Dev5D2d — independently identified dependencies and truthful release counts."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEvent
from vrhub import hub, updates, table_columns
from vrhub.mod_updates_gui import ModUpdatesPage, grouped_updates
from vrhub.dashboard_ui import snapshot


def release(repo):
    tag = {"jbusfield/FK_UEVR": "v1.0.4", "jbusfield/HL_UEVR": "v2.1.1",
           "joeyhodge/UEVR": "111726DecadeofUnreal"}[repo]
    return {"tag": tag, "published": "2026-11-21T18:48:05Z",
            "url": "https://github.com/" + repo + "/releases/tag/" + tag}


from tests.fatekeeper_fixtures import recipes as fixture_recipes


class DependencyUpdatesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.recipes = fixture_recipes()

    def records(self, game, installed_at=1792444057):
        return updates.check_recipe(self.recipes[game],
            {game: {"installed_at": installed_at},
             game + ":profile": {"installed_at": installed_at}}, fetch=release)

    def test_fatekeeper_has_one_update_not_two(self):
        rows = self.records("fatekeeper")
        self.assertEqual([r["name"] for r in rows],
                         ["UEVR_FK.zip", "SLASHER-Win64-Shipping.zip"])
        self.assertEqual([r["dependency_type"] for r in rows], ["Mod", "Profile"])
        self.assertEqual([r["status"] for r in rows], ["unknown", "update"])
        self.assertEqual(updates.release_count(rows), 1)

    def test_hogwarts_has_two_release_notifications_without_false_version(self):
        rows = self.records("hogwarts-legacy")
        self.assertEqual([r["name"] for r in rows], ["HogwartsLegacy.zip", "UEVR.zip"])
        self.assertEqual([r["dependency_type"] for r in rows], ["Profile", "Mod"])
        self.assertEqual([r["status"] for r in rows], ["update", "unknown"])
        self.assertTrue(rows[1]["newer_release"])
        self.assertNotIn("installed_version", rows[1])
        self.assertEqual(updates.release_count(rows), 2)
        groups = grouped_updates(self.recipes["hogwarts-legacy"], rows)
        self.assertEqual(groups["review"][0]["status"], "New release — review")
        self.assertEqual(len(groups["update"]), 1)
        card = snapshot({"recipe": self.recipes["hogwarts-legacy"], "game_found": True}, rows)
        self.assertEqual(card["updates"][1], "2 new releases")

    def test_only_newer_upstream_release_counts(self):
        self.assertEqual(updates.release_count(self.records("hogwarts-legacy", 9999999999)), 0)
        rows = updates.check_recipe(self.recipes["hogwarts-legacy"], {}, fetch=release)
        self.assertEqual(updates.release_count(rows), 0)
        self.assertEqual(updates.release_count([{"status":"unknown"}, {"status":"error",
                              "newer_release":True}, {"status":"not_installed"}]), 0)

    def test_hogwarts_profile_comparison_independent_of_injector_timestamp(self):
        rows = updates.check_recipe(self.recipes["hogwarts-legacy"],
            {"hogwarts-legacy":{"installed_at":1},
             "hogwarts-legacy:profile":{"installed_at":9999999999}}, fetch=release)
        self.assertEqual(rows[0]["status"], "current")
        self.assertEqual(updates.release_count(rows), 1)

    def test_update_column_preferences_do_not_rewrite_legacy_layout(self):
        with tempfile.TemporaryDirectory() as folder:
            legacy = Path(folder) / "table-column-layouts.json"
            with patch.object(table_columns, "preferences_file", return_value=legacy):
                table_columns.save_widths("mod-updates", [280, 120, 120, 180, 140])
                before = legacy.read_bytes()
                self.assertEqual(table_columns.load_widths("mod-updates", 6),
                                 [280,120,120,180,140,95])
                table_columns.save_widths("mod-updates", [280,120,120,180,140,105])
                self.assertEqual(legacy.read_bytes(), before)
                self.assertEqual(table_columns.load_widths("mod-updates", 6),
                                 [280,120,120,180,140,105])
                self.assertEqual(table_columns.load_widths("mod-updates", 5),
                                 [280,120,120,180,140])

    def test_native_tables_keep_source_button_and_expose_types(self):
        page = ModUpdatesPage()
        try:
            rows = self.records("hogwarts-legacy")
            page.set_recipe(self.recipes["hogwarts-legacy"], rows)
            table = page.sections["update"].table
            self.assertEqual(table.horizontalHeaderItem(0).text(), "Dependency")
            self.assertEqual(table.horizontalHeader().logicalIndex(1), 5)
            self.assertEqual(table.item(0,0).text(), "HogwartsLegacy.zip")
            self.assertEqual(table.item(0,5).text(), "Profile")
            self.assertEqual(table.cellWidget(0,4).text(), "Open source")
            review = page.sections["review"].table
            self.assertEqual(review.item(0,0).text(), "UEVR.zip")
            self.assertEqual(review.item(0,5).text(), "Mod")
            self.assertIn("1 newer releases to review", page.summary.text())
        finally:
            page.close()
            page.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.app.processEvents()
