"""Windows VHVR archive mapping and shared installer isolation; no gameplay claims."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest import mock
import zipfile

from tests import test_workflow_compatibility as fixtures
from vrhub import bepinex, compatibility, hub, log_diagnostics
from vrhub.schema import RecipeError, validate_recipe


class ValheimTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SteamWorkflowCompatibilityTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        recipe, self.game, self.prefix = self.fixture.game('valheim')
        self.recipe = copy.deepcopy(recipe)
        self.fixture.file(self.game/'valheim.exe')
        (self.game/'valheim_Data').mkdir()
        self.fixture.file(self.game/'worlds_local/world.db').write_bytes(b'world fixture')
        self.fixture.file(self.game/'characters_local/character.fch').write_bytes(b'character fixture')
        self.fixture.file(self.game/'BepInEx/plugins/unrelated.dll')
        self.fixture.file(self.game/'BepInEx/patchers/Tobey/unrelated.dll')
        self.fixture.file(self.game/'BepInEx/config/org.bepinex.plugins.valheimvrmod.cfg').write_text('[Immutable]\nflatScreenMode = auto\n')
        self.fixture.record('subnautica', {'installer':'submersed-vr-1', 'fixture':'preserve old inventory'})
        history = self.fixture.state.with_name('live-tests.json')
        history.write_text('{"schema_version":1,"games":{}}')
        self.keep = {p:p.read_bytes() for p in [history,*self.game.rglob('*')] if p.is_file()}
        self.archives = []
        self.contents = []
        for i, package in enumerate(self.recipe['packages']):
            files = {}
            for target in package['required_files']:
                source = 'BepInExPack_Valheim/'+target if i == 0 else target.replace('valheim_Data/', 'Valheim_Data/', 1)
                files[source] = ('fixture '+target).encode()
            if i == 0:
                files.update({'README.md':b'not installed','manifest.json':b'{}',
                              'BepInExPack_Valheim/start_game_bepinex.sh':b'never execute',
                              'BepInExPack_Valheim/doorstop_libs/libdoorstop_x64.so':b'native'})
            else:
                files['BepInEx/plugins/bHaptics/test.tact'] = b'preserve full archive'
                files['Valheim_Data/StreamingAssets/vhvr_custom'] = b'asset bundle'
            self.contents.append(files)
            self.archives.append(self.write_archive(i))

    def write_archive(self, i):
        path = self.fixture.home/f'generic-download-{i}.zip'
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
            for name, data in self.contents[i].items():z.writestr(name,data)
        self.recipe['packages'][i]['sha256'] = bepinex.digest(path)
        return path

    def install(self):
        return hub.install_many(self.recipe,list(reversed(self.archives)),[self.fixture.steam])

    def snapshot(self):
        return {p.relative_to(self.game).as_posix():p.read_bytes() for p in self.game.rglob('*') if p.is_file()}

    def assert_preserved(self):
        for p,data in self.keep.items():self.assertEqual(p.read_bytes(),data,str(p))
        self.assertEqual(hub.state()['subnautica']['fixture'],'preserve old inventory')

    def test_complete_pair_maps_wrapper_and_unity_directory_without_native_startup(self):
        self.install()
        for i, archive in enumerate(self.archives):
            package, plan = bepinex.archive_plan(archive,self.recipe)
            for source,target in plan.items():self.assertEqual((self.game/target).read_bytes(),self.contents[i][source])
        for name in ['Valheim_Data','BepInExPack_Valheim','start_game_bepinex.sh','doorstop_libs','README.md','manifest.json']:
            self.assertFalse((self.game/name).exists(),name)
        self.assertTrue(hub.verify(self.recipe)['ready'])
        inspection = hub.inspect_archive(self.recipe,self.archives[0])
        self.assertEqual(inspection['archive_files'],len(self.contents[0]))
        self.assertEqual(inspection['install_files'],len(self.recipe['packages'][0]['required_files']))
        self.assertEqual(hub.state()['valheim']['installer'],'vhvr-1')
        self.assertEqual(hub.state()['valheim']['retired'],[])
        self.assert_preserved()

    def test_remove_restores_originals_and_keeps_worlds_configs_and_other_mods(self):
        self.fixture.file(self.game/'valheim_Data/Plugins/x86_64/openvr_api.dll').write_bytes(b'original runtime')
        self.fixture.file(self.game/'BepInEx/config/BepInEx.cfg').write_bytes(b'original settings')
        before = self.snapshot()
        self.install();hub.uninstall('valheim')
        self.assertEqual(self.snapshot(),before)
        self.assert_preserved()

    def test_native_only_copy_is_blocked_before_install(self):
        (self.game/'valheim.exe').unlink()
        self.fixture.file(self.game/'valheim.x86_64')
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'Windows Steam copy of Valheim'):
            self.install()
        self.assertEqual(self.snapshot(),before)
        self.assertNotIn('valheim',hub.state())

    def test_case_collision_or_duplicate_manager_plugin_blocks_before_writes(self):
        (self.game/'Valheim_Data').mkdir()
        with self.assertRaisesRegex(RuntimeError,'case collision'):self.install()
        (self.game/'Valheim_Data').rmdir()
        self.fixture.file(self.game/'BepInEx/plugins/OtherManager/ValheimVRMod.dll')
        with self.assertRaisesRegex(RuntimeError,'conflicting or duplicate'):self.install()
        self.assertNotIn('valheim',hub.state())

    def test_package_pair_wrong_hash_and_cross_package_collision_are_blocked(self):
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'BOTH'):
            hub.install_many(self.recipe,self.archives[:1],[self.fixture.steam])
        self.contents[0]['BepInExPack_Valheim/BepInEx/plugins/ValheimVRMod.dll'] = b'collision'
        self.write_archive(0)
        with self.assertRaisesRegex(RuntimeError,'overlap'):self.install()
        self.assertEqual(self.snapshot(),before)
        self.archives[0].write_bytes(b'wrong version')
        with self.assertRaisesRegex(RuntimeError,'not a recognized'):self.install()
        self.assertEqual(self.snapshot(),before)

    def test_wrapper_traversal_and_destination_symlinks_are_blocked(self):
        self.contents[0]['BepInExPack_Valheim/../worlds_local/world.db'] = b'bad'
        self.write_archive(0)
        with self.assertRaisesRegex(RuntimeError,'Unsafe'):self.install()
        del self.contents[0]['BepInExPack_Valheim/../worlds_local/world.db'];self.write_archive(0)
        outside = self.fixture.home/'outside';outside.mkdir()
        (self.game/'valheim_Data/Managed').symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError,'symlink'):self.install()
        self.assertNotIn('valheim',hub.state())

    def test_state_commit_failure_rolls_back_mapped_payloads(self):
        before = self.snapshot()
        with mock.patch.object(bepinex,'_save',side_effect=OSError('fixture state failure')):
            with self.assertRaisesRegex(OSError,'fixture state failure'):self.install()
        self.assertEqual(self.snapshot(),before)
        self.assertNotIn('valheim',hub.state())
        self.assert_preserved()

    def test_changed_settings_are_kept_and_changed_binary_blocks_removal(self):
        self.install()
        binary = self.game/'valheim_Data/Plugins/x86_64/openvr_api.dll'
        data = binary.read_bytes();binary.write_bytes(b'game update')
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'binary files changed'):hub.uninstall('valheim')
        self.assertEqual(self.snapshot(),before)
        binary.write_bytes(data)
        config = self.game/'BepInEx/config/BepInEx.cfg';config.write_bytes(b'user changed loader config')
        backup = Path(hub.state()['valheim']['backup'])
        hub.uninstall('valheim')
        self.assertEqual((backup/'user-modified/BepInEx/config/BepInEx.cfg').read_bytes(),b'user changed loader config')
        self.assert_preserved()

    def test_launch_flags_are_explicit_and_user_config_is_unchanged(self):
        self.install()
        options = hub.launch_options(self.recipe)
        for flag in ['-force-d3d11','-flatScreenMode=false','-ModEnabled=true','-UseVRControls=true','-UseOverlayGui=false',
                     'winhttp=n,b','IMPORT_OPENXR_1_RUNTIMES=1','"$XDG_RUNTIME_DIR/wivrn/comp_ipc"','valheim','%command%']:
            self.assertIn(flag,options)
        self.assertNotIn('-force-vulkan',options)
        with mock.patch('vrhub.handlers.subprocess.Popen') as spawn:
            spawn.return_value.pid=123
            hub.launch_game_play(self.recipe,[self.fixture.steam])
            self.assertIn('steam://launch/892970/dialog',str(spawn.call_args))
        self.assert_preserved()

    def test_inventory_and_logs_do_not_create_gameplay_evidence(self):
        self.install()
        text = compatibility.report_text(compatibility.report(self.recipe,[self.fixture.steam]))
        self.assertIn('USER-REPORTED LIVE TEST',text)
        self.assertIn('2026-10-20',text)
        self.assertIn('rotation',text.lower())
        self.assertNotIn('Local gameplay test: SUCCESS',text)
        log=self.fixture.file(self.game/'BepInEx/LogOutput.log');log.write_text('fixture; no gameplay validation')
        rep=log_diagnostics.report(self.recipe,[self.fixture.steam])
        self.assertEqual(rep['logs'][0]['path'],str(log))
        self.assertEqual(rep['status'],'NO KNOWN SIGNATURES FOUND')
        (self.game/'valheim_Data/StreamingAssets/SteamVR/bindings_oculus_touch.json').unlink()
        self.assertFalse(hub.verify(self.recipe)['ready'])
        self.assertEqual(compatibility.report(self.recipe,[self.fixture.steam])['status'],'NOT READY')

    def test_schema_rejects_mismatched_handlers_appids_and_package_roles(self):
        for key,value in [('steam_appid',264710),('handler','submersed-vr'),('id','subnautica'),('store','heroic-gog')]:
            r=copy.deepcopy(self.recipe);r[key]=value
            with self.subTest(key=key),self.assertRaises(RecipeError):validate_recipe(r)
        r=copy.deepcopy(self.recipe);r['packages'][1]['id']='submersedvr'
        with self.assertRaises(RecipeError):validate_recipe(r)

    @unittest.skipUnless(importlib.util.find_spec('PySide6'),'Optional PySide6 is not installed')
    def test_qt_seventh_game_controls(self):
        from PySide6.QtWidgets import QApplication
        from vrhub.gui import HubWindow
        app=QApplication.instance() or QApplication([])
        with mock.patch.object(HubWindow,'check_updates'),mock.patch.object(HubWindow,'scan_setup'), \
             mock.patch('vrhub.app_update_gui.HubUpdateController.startup'):
            window=HubWindow()
            try:
                self.assertEqual(window.table.rowCount(),9)
                row=next(i for i in range(9) if 'Valheim (' in window.table.item(i,0).text())
                window.table.selectRow(row);app.processEvents()
                self.assertTrue(window.verify_btn.isEnabled());self.assertTrue(window.inspect_btn.isEnabled())
                self.assertFalse(window.inject_btn.isEnabled());self.assertFalse(window.profile_btn.isEnabled())
            finally:window.close();app.processEvents()
