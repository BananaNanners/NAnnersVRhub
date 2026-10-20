import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import test_hogwarts as fixtures
from vrhub import heroic_epic as epic, hub
from vrhub.schema import RecipeError, validate_recipe


class HeroicDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        env = mock.patch.dict(os.environ, {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / "config"),
                                           "NANNERS_HEROIC_CONFIG": "", "VRHUB_STATE": str(self.home / "state.json")})
        env.start(); self.addCleanup(env.stop)
        self.recipe = hub.load_recipes()["hogwarts-legacy"]

    def fixture(self, **kwargs):
        return fixtures.heroic_fixture(self.home, self.recipe, **kwargs)

    def test_native_heroic_uses_its_settings_and_never_steam(self):
        root, game, prefix, files = self.fixture()
        before = {p: p.read_bytes() for p in files}
        with mock.patch.object(hub, "find_game", side_effect=AssertionError("must not inspect Steam")):
            self.assertEqual(hub.game_path(self.recipe), game)
            self.assertEqual(hub._pfx(self.recipe), prefix)
            self.assertEqual(hub.profile_dir(self.recipe), prefix / hub.APPDATA / self.recipe["profile"]["dir"])
        for path, data in before.items():
            self.assertEqual(path.read_bytes(), data)

    def test_nested_proton_prefix_is_resolved_to_pfx(self):
        _, _, prefix, _ = self.fixture(nested=True)
        self.assertEqual(hub._pfx(self.recipe), prefix)
        self.assertNotEqual(prefix, prefix.parent)

    def test_pfx_alias_to_the_same_prefix_is_not_ambiguous(self):
        _, _, prefix, _ = self.fixture()
        (prefix / "pfx").symlink_to(".", target_is_directory=True)
        self.assertEqual(hub._pfx(self.recipe), prefix)

    def test_flatpak_discovery_launches_the_matching_client(self):
        config = self.home / f".var/app/{epic.FLATPAK_ID}/config/heroic"
        self.fixture(config=config)
        info = epic.context(self.recipe)
        self.assertTrue(info["flatpak"])
        with mock.patch.object(epic.shutil, "which", side_effect=lambda name: "/usr/bin/" + name):
            args = epic.command(info, play=True)
        self.assertEqual(args[:3], ["/usr/bin/flatpak", "run", epic.FLATPAK_ID])
        self.assertIn("runner=legendary", args[-1])

    def test_multiple_installs_require_explicit_config_selection(self):
        native, _, _, _ = self.fixture()
        self.fixture(config=self.home / f".var/app/{epic.FLATPAK_ID}/config/heroic")
        with self.assertRaisesRegex(RuntimeError, "Multiple"):
            epic.context(self.recipe)
        with mock.patch.dict(os.environ, {"NANNERS_HEROIC_CONFIG": str(native)}):
            self.assertEqual(epic.context(self.recipe)["root"], native)

    def test_missing_or_corrupt_metadata_is_not_replaced_with_steam(self):
        with mock.patch.object(hub, "find_game", side_effect=AssertionError("Steam fallback")):
            self.assertIsNone(hub.game_path(self.recipe))
        root, _, _, files = self.fixture()
        files[0].write_text("broken JSON")
        with self.assertRaisesRegex(RuntimeError, "Cannot read"):
            epic.context(self.recipe)
        self.assertEqual(files[0].read_text(), "broken JSON")

    def test_custom_discovery_cannot_launch_another_clients_default_config(self):
        config = self.home / "portable Heroic config"
        self.fixture(config=config)
        with mock.patch.dict(os.environ, {"NANNERS_HEROIC_CONFIG": str(config)}):
            info = epic.context(self.recipe)
            with self.assertRaisesRegex(RuntimeError, "manually"):
                epic.command(info, play=True)

    def test_missing_game_settings_cannot_create_a_prefix(self):
        _, _, prefix, files = self.fixture()
        files[1].unlink()
        with self.assertRaisesRegex(RuntimeError, "metadata"):
            hub._pfx(self.recipe)
        self.assertFalse((prefix / "drive_c/uevr").exists())

    def test_missing_or_ambiguous_prefix_is_rejected(self):
        _, _, prefix, _ = self.fixture()
        (prefix / "pfx/drive_c").mkdir(parents=True)
        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            hub._pfx(self.recipe)
        (prefix / "pfx/drive_c").rmdir()
        import shutil
        shutil.rmtree(prefix / "drive_c")
        with self.assertRaisesRegex(RuntimeError, "missing"):
            hub._pfx(self.recipe)
        self.assertFalse((prefix / "drive_c").exists())

    def test_wine_username_is_used_instead_of_making_steamuser(self):
        _, _, prefix, _ = self.fixture(user="wizard", runner_type="wine")
        expected = prefix / "drive_c/users/wizard/AppData"
        self.assertEqual(epic.appdata(epic.context(self.recipe)), expected)
        self.assertEqual(hub.profile_dir(self.recipe), expected / self.recipe["profile"]["dir"])
        self.assertFalse((prefix / "drive_c/users/steamuser").exists())

    def test_ambiguous_wine_users_and_external_appdata_are_rejected(self):
        _, _, prefix, _ = self.fixture(user="wizard", runner_type="wine")
        second = prefix / "drive_c/users/second/AppData"
        second.mkdir(parents=True)
        with self.assertRaisesRegex(RuntimeError, "cannot be selected safely"):
            epic.appdata(epic.context(self.recipe))
        second.rmdir()
        data = prefix / "drive_c/users/wizard/AppData"
        data.rmdir()
        outside = self.home / "outside"
        outside.mkdir()
        data.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "outside"):
            hub.profile_dir(self.recipe)

    def test_external_injector_folder_is_rejected_before_writing(self):
        _, _, prefix, _ = self.fixture()
        outside = self.home / "outside"
        outside.mkdir()
        (prefix / "drive_c/uevr").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "outside"):
            hub._uevr_dir(self.recipe)
        self.assertEqual(list(outside.iterdir()), [])

    def test_epic_identity_cannot_be_used_as_a_settings_path(self):
        _, _, _, files = self.fixture()
        files[0].write_text(json.dumps({"../other": {"app_name": "../other", "title": "Hogwarts Legacy", "install_path": str(self.home)}}))
        with self.assertRaisesRegex(RuntimeError, "identity"):
            epic.context(self.recipe)

    def test_schema_does_not_accept_steam_runner_checks_for_epic(self):
        import copy
        recipe = copy.deepcopy(self.recipe)
        recipe["compatibility"]["checks"]["recorded_proton"] = True
        with self.assertRaisesRegex(RecipeError, "Steam-specific"):
            validate_recipe(recipe)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "Optional PySide6 is not installed")
class HeroicQtTests(unittest.TestCase):
    def test_guided_injector_dialog_and_store_specific_controls(self):
        from PySide6.QtWidgets import QApplication
        from vrhub.gui import HubWindow, HeroicInjectorDialog
        f = fixtures.HogwartsWorkflowTests()
        f.setUp()
        try:
            f.install()
            from vrhub import app_updates
            app_updates.save_settings(check_on_startup=False)
            app = QApplication.instance() or QApplication([])
            with mock.patch.object(HubWindow, "check_updates"), mock.patch.object(HubWindow, "scan_setup"):
                window = HubWindow()
                row = next(i for i, item in enumerate(window.rows) if item["recipe"]["id"] == "hogwarts-legacy")
                window.table.selectRow(row)
                self.assertEqual(window.inject_btn.text(), "Run UEVR injector")
                self.assertFalse(window.copy_btn.isEnabled())
                self.assertEqual(window.game_play_btn.text(), "Launch in Heroic")
                dialog = HeroicInjectorDialog(f.recipe, window)
                dialog.copy.click()
                self.assertEqual(app.clipboard().text(), str(hub.injector_path(f.recipe)))
                with mock.patch("vrhub.heroic_epic.shutil.which", return_value="/usr/bin/heroic"), \
                        mock.patch("vrhub.gui.subprocess.Popen") as spawn:
                    dialog.open.click()
                self.assertEqual(spawn.call_args.args[0], ["/usr/bin/heroic"])
                dialog.close()
                failed = mock.Mock()
                failed.poll.return_value = 7
                failed.output_tail.return_value = "fixture runner failure"
                dialog = HeroicInjectorDialog(f.recipe, window, launch=failed)
                self.assertIn("code 7", dialog.status.text())
                self.assertEqual(dialog.output.toPlainText(), "fixture runner failure")
                self.assertFalse(dialog.timer.isActive())
                dialog.close()
                with mock.patch("vrhub.gui.hub.launch_injector", return_value=failed) as start, \
                        mock.patch("vrhub.gui.HeroicInjectorDialog") as guide:
                    window.run_injector()
                    start.assert_called_once()
                    self.assertIs(guide.call_args.kwargs["launch"], failed)
                    guide.return_value.exec.assert_called_once()
                with mock.patch("vrhub.gui.hub.launch_injector", side_effect=RuntimeError("fixture unavailable")), \
                        mock.patch("vrhub.gui.HeroicInjectorDialog") as guide:
                    window.run_injector()
                    self.assertIn("fixture unavailable", guide.call_args.kwargs["error"])
                window.close()
                app.processEvents()
        finally:
            f.tearDown()
            f.doCleanups()
