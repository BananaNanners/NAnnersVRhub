"""Transactional SubmersedVR installation; fixtures are never gameplay evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import stat
import unittest
from unittest import mock
import zipfile

from tests import test_workflow_compatibility as fixtures
from vrhub import compatibility, hub, log_diagnostics, bepinex as subnautica
from vrhub.schema import RecipeError, validate_recipe


class SubnauticaTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SteamWorkflowCompatibilityTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        recipe, self.game, self.prefix = self.fixture.game('subnautica')
        self.recipe = copy.deepcopy(recipe)
        self.fixture.file(self.game / 'Subnautica.exe')
        (self.game / 'Subnautica_Data').mkdir()
        self.fixture.file(self.game / 'SNAppData/SavedGames/slot0000/gameinfo.json')
        self.archives = []
        self.payload = {}
        for i, pack in enumerate(self.recipe['packages']):
            files = {name: ('fixture ' + name).encode() for name in pack['required_files']}
            if i == 0:
                files.update({'BepInEx/config/BepInEx.cfg': b'initial config',
                              'run_bepinex.sh': b'never execute', 'libdoorstop.dylib': b'mac'})
            else:
                files['Subnautica_Data/StreamingAssets/amplify_resources'] = b'complete archive'
            path = self.fixture.home / f'renamed-{i}.zip'
            self.make_zip(path, files)
            pack['sha256'] = subnautica.digest(path)
            self.archives.append(path)
            self.payload.update({k:v for k,v in files.items() if k not in subnautica.OTHER_PLATFORM})
        self.fixture.record('fatekeeper', {'preserve': 'other game'})
        history = self.fixture.state.with_name('live-tests.json')
        history.write_text('{"schema_version":1,"games":{}}')
        self.preserved = {p: p.read_bytes() for p in (history, self.game/'SNAppData/SavedGames/slot0000/gameinfo.json')}

    def make_zip(self, path, files):
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, data in files.items():
                z.writestr(name, data)

    def install(self):
        return hub.install_many(self.recipe, list(reversed(self.archives)), [self.fixture.steam])

    def snapshot(self):
        return {p.relative_to(self.game).as_posix(): p.read_bytes() for p in self.game.rglob('*') if p.is_file()}

    def assert_preserved(self):
        self.assertEqual(hub.state()['fatekeeper'], {'preserve':'other game'})
        for p, data in self.preserved.items():
            self.assertEqual(p.read_bytes(), data)

    def test_complete_pair_preserves_case_bindings_other_games_and_saves(self):
        paths = self.install()
        self.assertEqual(len(paths), len(self.payload))
        for name, data in self.payload.items():
            self.assertEqual((self.game/name).read_bytes(), data)
        self.assertFalse((self.game/'bepinex').exists())
        self.assertFalse((self.game/'run_bepinex.sh').exists())
        self.assertFalse((self.game/'libdoorstop.dylib').exists())
        self.assertTrue(hub.verify(self.recipe)['ready'])
        self.assert_preserved()
        hub.uninstall('subnautica')
        self.assertFalse((self.game/'BepInEx/plugins/SubmersedVR.dll').exists())
        self.assert_preserved()

    def test_original_game_files_and_retired_patcher_are_restored(self):
        originals = {'winhttp.dll':b'original loader', 'Subnautica_Data/Managed/SteamVR.dll':b'vanilla SteamVR',
                     'BepInEx/config/BepInEx.cfg':b'original config',
                     'BepInEx/patchers/Tobey/old.dll':b'legacy', 'BepInEx/plugins/unrelated.dll':b'unrelated'}
        for name, data in originals.items():
            p = self.fixture.file(self.game/name);p.write_bytes(data)
        before = self.snapshot()
        self.install()
        self.assertFalse((self.game/'BepInEx/patchers/Tobey').exists())
        hub.uninstall('subnautica')
        self.assertEqual(self.snapshot(), before)
        self.assert_preserved()

    def test_changed_config_is_preserved_and_original_restored(self):
        config = self.fixture.file(self.game/'BepInEx/config/BepInEx.cfg')
        config.write_bytes(b'original config')
        self.install()
        entry = hub.state()['subnautica']
        config.write_bytes(b'custom settings after game launch')
        hub.uninstall('subnautica')
        self.assertEqual(config.read_bytes(), b'original config')
        self.assertEqual((Path(entry['backup'])/'user-modified/BepInEx/config/BepInEx.cfg').read_bytes(),
                         b'custom settings after game launch')

    def test_changed_game_binary_blocks_removal_before_changes(self):
        self.install()
        (self.game/'Subnautica_Data/Managed/SteamVR.dll').write_bytes(b'Steam updated this')
        before, state = self.snapshot(), self.fixture.state.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'binary files changed'):
            hub.uninstall('subnautica')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.fixture.state.read_bytes(), state)

    def test_missing_original_backup_blocks_removal(self):
        self.fixture.file(self.game/'winhttp.dll')
        self.install()
        entry = hub.state()['subnautica']
        (Path(entry['backup'])/'files/winhttp.dll').unlink()
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, 'backup is missing'):
            hub.uninstall('subnautica')
        self.assertEqual(self.snapshot(), before)

    def test_corrupted_backup_stops_before_removal(self):
        self.fixture.file(self.game/'winhttp.dll')
        self.install()
        entry = hub.state()['subnautica']
        (Path(entry['backup'])/'files/winhttp.dll').write_bytes(b'corrupted backup')
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, 'backup changed'):
            hub.uninstall('subnautica')
        self.assertEqual(self.snapshot(), before)

    def test_one_archive_duplicates_and_wrong_hash_are_rejected(self):
        before = self.snapshot()
        for files in ([self.archives[0]], [self.archives[0]]*2, []):
            with self.subTest(files=files), self.assertRaisesRegex(RuntimeError, 'BOTH'):
                hub.install_many(self.recipe, files, [self.fixture.steam])
            self.assertEqual(self.snapshot(), before)
        self.archives[0].write_bytes(b'wrong release')
        with self.assertRaisesRegex(RuntimeError, 'not a recognized'):
            self.install()
        self.assertEqual(self.snapshot(), before)

    def test_unsafe_archive_paths_and_links_are_rejected(self):
        for name in ('../outside', '/absolute', 'BepInEx/../SNAppData/save', 'BepInEx\\wrong.dll', 'SNAppData/save'):
            with self.subTest(name=name):
                self.make_zip(self.archives[0], {name:b'bad'})
                self.recipe['packages'][0]['sha256'] = subnautica.digest(self.archives[0])
                with self.assertRaises(RuntimeError):
                    self.install()
        with zipfile.ZipFile(self.archives[0], 'w') as z:
            link = zipfile.ZipInfo('BepInEx/linked')
            link.create_system = 3;link.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(link, '/outside')
        self.recipe['packages'][0]['sha256'] = subnautica.digest(self.archives[0])
        with self.assertRaisesRegex(RuntimeError, 'Unsafe'):
            self.install()
        self.assertNotIn('subnautica', hub.state())

    def test_case_collisions_symlinks_and_conflicting_mods_stop_install(self):
        before = self.snapshot()
        (self.game/'bepinex').mkdir()
        with self.assertRaisesRegex(RuntimeError, 'case collision'):
            self.install()
        (self.game/'bepinex').rmdir()
        external = self.fixture.home/'external';external.mkdir()
        (self.game/'BepInEx').symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            self.install()
        (self.game/'BepInEx').unlink()
        plugin = self.fixture.file(self.game/'BepInEx/plugins/VREnhancements.DLL')
        with self.assertRaisesRegex(RuntimeError, 'incompatible'):
            self.install()
        plugin.unlink()
        self.assertEqual(self.snapshot(), before)

    def test_failed_file_write_restores_originals_and_legacy_folder(self):
        self.fixture.file(self.game/'winhttp.dll').write_bytes(b'original')
        self.fixture.file(self.game/'BepInEx/patchers/Tobey/legacy.dll')
        before = self.snapshot()
        original_copy = shutil.copy2
        calls = []
        def failing_copy(src, dst, *args, **kwargs):
            if Path(dst).is_relative_to(self.game):
                calls.append(dst)
                if len(calls) == 3:
                    Path(dst).write_bytes(b'partial write')
                    raise OSError('fixture write failure')
            return original_copy(src, dst, *args, **kwargs)
        with mock.patch.object(subnautica.shutil, 'copy2', side_effect=failing_copy):
            with self.assertRaisesRegex(OSError, 'fixture write failure'):
                self.install()
        self.assertEqual(self.snapshot(), before)
        self.assertNotIn('subnautica', hub.state())

    def test_state_commit_failure_restores_install_and_removal(self):
        self.fixture.file(self.game/'winhttp.dll')
        before, state = self.snapshot(), self.fixture.state.read_bytes()
        with mock.patch.object(subnautica, '_save', side_effect=OSError('state failure')):
            with self.assertRaisesRegex(OSError, 'state failure'):
                self.install()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.fixture.state.read_bytes(), state)
        self.install()
        before, state = self.snapshot(), self.fixture.state.read_bytes()
        with mock.patch.object(subnautica, '_save', side_effect=OSError('state failure')):
            with self.assertRaisesRegex(OSError, 'state failure'):
                hub.uninstall('subnautica')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.fixture.state.read_bytes(), state)

    def test_existing_hub_install_is_not_silently_overwritten(self):
        self.install()
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, 'Remove it first'):
            self.install()
        self.assertEqual(self.snapshot(), before)

    def test_inventory_loss_and_external_symlink_do_not_pass_verify(self):
        self.assertFalse(hub.verify(self.recipe)['ready'])
        self.install()
        file = self.game/'BepInEx/plugins/SubmersedVR.dll'
        data = file.read_bytes();file.unlink()
        self.assertFalse(hub.verify(self.recipe)['ready'])
        outside = self.fixture.file(self.fixture.home/'external.dll');outside.write_bytes(data)
        file.symlink_to(outside)
        self.assertFalse(hub.verify(self.recipe)['ready'])

    def test_presence_does_not_promote_gameplay_or_change_steam_settings(self):
        self.install()
        self.recipe['compatibility'].pop('reference', None)
        self.recipe['compatibility']['validation'] = 'unverified'
        text = compatibility.report_text(compatibility.report(self.recipe, [self.fixture.steam]))
        self.assertIn('UNVERIFIED', text)
        self.assertIn('no dated', text)
        self.assertNotIn('USER-REPORTED LIVE TEST', text)
        options = hub.launch_options(self.recipe)
        for value in ('winhttp=n,b','IMPORT_OPENXR_1_RUNTIMES=1',
                      '"$XDG_RUNTIME_DIR/wivrn/comp_ipc"', '-vrmode openvr', 'subnautica', '%command%'):
            self.assertIn(value, options)
        with mock.patch('vrhub.handlers.subprocess.Popen') as spawn:
            spawn.return_value.pid = 12345
            hub.launch_game_play(self.recipe, [self.fixture.steam])
            self.assertIn('steam://launch/264710/dialog', str(spawn.call_args))

    def test_log_discovery_and_archive_inspection_are_read_only(self):
        log = self.fixture.file(self.game/'BepInEx/LogOutput.log')
        log.write_text('[Info] BepInEx plugin loaded; this is a fixture')
        state = self.fixture.state.read_bytes()
        report = log_diagnostics.report(self.recipe, [self.fixture.steam])
        self.assertEqual(report['logs'][0]['path'], str(log))
        self.assertEqual(report['status'], 'NO KNOWN SIGNATURES FOUND')
        inspected = hub.inspect_archive(self.recipe, self.archives[1])
        self.assertEqual(inspected['install_files'], 8)
        self.assertEqual(self.fixture.state.read_bytes(), state)

    def test_schema_requires_pinned_pair_and_correct_game(self):
        for key, value in [('steam_appid', 1), ('packages', []), ('method', 'gameroot')]:
            recipe = copy.deepcopy(self.recipe);recipe[key] = value
            with self.subTest(key=key), self.assertRaises(RecipeError):
                validate_recipe(recipe)
        recipe = copy.deepcopy(self.recipe);recipe['packages'][0]['required_files'] = ['../save']
        with self.assertRaises(RecipeError):
            validate_recipe(recipe)

    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Optional PySide6 is not installed')
    def test_real_qt_game_controls(self):
        from PySide6.QtWidgets import QApplication, QMessageBox
        from vrhub.gui import HubWindow
        app = QApplication.instance() or QApplication([])
        with mock.patch.object(HubWindow, 'check_updates'), mock.patch.object(HubWindow, 'scan_setup'), \
             mock.patch('vrhub.app_update_gui.HubUpdateController.startup'):
            window = HubWindow()
            try:
                self.assertEqual(window.table.rowCount(), 9)
                row = next(i for i in range(9) if 'Subnautica' in window.table.item(i,0).text())
                window.table.selectRow(row);app.processEvents()
                self.assertTrue(window.verify_btn.isEnabled())
                self.assertTrue(window.inspect_btn.isEnabled())
                self.assertFalse(window.inject_btn.isEnabled())
                self.install()
                (self.game/'Subnautica_Data/Managed/SteamVR.dll').write_bytes(b'updated binary')
                with mock.patch.object(window, 'current', return_value=self.recipe), \
                     mock.patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes), \
                     mock.patch.object(QMessageBox, 'warning') as warning:
                    window.uninstall()
                    self.assertIn('binary files changed', str(warning.call_args))
                    self.assertIn('subnautica', hub.state())
            finally:
                window.close();app.processEvents()
