"""GOG prefix isolation, complete KHARVOX package checks and historical logs."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.test_elden_ring import pe
from vrhub import compatibility, controller_bindings, heroic, hub, kharvox, log_diagnostics
from vrhub.handlers import get_handler
from vrhub.schema import RecipeError, validate_recipe


class KharvoxTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.home=Path(tmp.name)
        self.game=self.home/'Games/Heroic/DOOM (2016)';self.game.mkdir(parents=True)
        self.exe=self.game/'DOOMx64vk.exe';self.exe.write_bytes(b'synthetic GOG binary, never execute')
        self.prefix=self.home/'Prefixes/DOOM';(self.prefix/'drive_c/users/steamuser/AppData/Local/Temp').mkdir(parents=True)
        self.save=self.prefix/'save.bin';self.save.write_bytes(b'preserve game save')
        self.runner=self.home/'Proton-CachyOS/proton';self.runner.parent.mkdir();self.runner.write_text('fixture');self.runner.chmod(0o755)
        self.cfg=self.home/'heroic';(self.cfg/'gog_store').mkdir(parents=True);(self.cfg/'GamesConfig').mkdir()
        (self.cfg/'gog_store/installed.json').write_text(json.dumps({'installed':[{'appName':'1390579243','install_path':str(self.game)}]}))
        self.settings={'winePrefix':str(self.prefix),'wineVersion':{'bin':str(self.runner),'type':'proton','name':'Keep this runner'},'enviromentOptions':[{'key':'CUSTOM_TEST','value':'literal $(never execute)'}]}
        self.config=self.cfg/'GamesConfig/1390579243.json';self.write_settings()
        self.root=self.home/'Games/KHARVOX-v1.4';self.root.mkdir()
        for name in kharvox.REQUIRED_FILES:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture '+name.encode())
        for name,version in kharvox.VERSIONS.items():
            (self.root/name).write_bytes(pe(tuple(map(int,version.split('.')))))
        hashes={name:hashlib.sha256((self.root/name).read_bytes()).hexdigest() for name in kharvox.BINARY_HASHES}
        self.state=self.home/'state.json';self.state.write_text('{"other-game":{"fixture":"preserve"}}')
        self.history=self.home/'live-tests.json';self.history.write_text('{"schema_version":1,"games":{}}')
        self.keep={p:p.read_bytes() for p in [self.config,self.save,self.state,self.history,self.exe]}
        env={'HOME':str(self.home),'XDG_CONFIG_HOME':str(self.home/'config'),'NANNERS_HEROIC_CONFIG':str(self.cfg),
             'NANNERS_KHARVOX_DIR':str(self.root),'VRHUB_STATE':str(self.state),'XDG_RUNTIME_DIR':str(self.home/'runtime')}
        for patch in [mock.patch.dict(os.environ,env),mock.patch.object(kharvox,'GOG_SHA256',hashlib.sha256(self.exe.read_bytes()).hexdigest()),
                      mock.patch.object(kharvox,'BINARY_HASHES',hashes),mock.patch.object(kharvox.shutil,'which',return_value='/usr/bin/umu-run')]:
            patch.start();self.addCleanup(patch.stop)
        self.recipe=hub.load_recipes()['doom-2016-gog']
        from vrhub import kharvox_bridge
        kharvox_bridge._active.clear()

    def write_settings(self):
        self.config.write_text(json.dumps({'1390579243':self.settings}))

    def preserved(self):
        for p,data in self.keep.items():self.assertEqual(p.read_bytes(),data,str(p))

    def test_complete_package_and_metadata_checks_are_read_only(self):
        rows=kharvox.package_rows(self.root)
        self.assertTrue(all(r['ok'] for r in rows),rows)
        self.assertTrue(kharvox.game_row(self.game)['ok']);self.assertEqual(hub._pfx(self.recipe),self.prefix)
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        get_handler(self.recipe).preflight_rows(self.recipe,self.game)
        for p,data in before.items():self.assertEqual(p.read_bytes(),data)
        self.preserved()

    def test_missing_shader_changed_binary_and_mixed_versions_fail(self):
        shader=next(self.root/name for name in kharvox.REQUIRED_FILES if name.endswith('.spv'))
        shader.unlink();self.assertTrue(any(not r['ok'] for r in kharvox.package_rows(self.root)))
        shader.write_bytes(b'fixture')
        (self.root/'KharvoxLayer.dll').write_bytes(pe((1,1,1,0)))
        with self.assertRaisesRegex(RuntimeError,'Changed|Expected'):kharvox._host_plan(self.recipe,self.game)
        self.preserved()

    def test_symlinked_binary_or_shader_is_not_accepted(self):
        for name in ['KharvoxLauncher.exe',next(n for n in kharvox.REQUIRED_FILES if n.endswith('.spv'))]:
            p=self.root/name;data=p.read_bytes();p.unlink();p.symlink_to(self.save)
            with self.subTest(name=name),self.assertRaises(RuntimeError):kharvox._host_plan(self.recipe,self.game)
            p.unlink();p.write_bytes(data)
        self.preserved()

    def test_modern_pe_versions_win_over_old_misleading_folder_name(self):
        old=self.home/'Games/KHARVOX-v1.11';old.mkdir();(old/'KharvoxLauncher.exe').write_bytes(pe((1,1,1,0)))
        with mock.patch.dict(os.environ,{'NANNERS_KHARVOX_DIR':''}):
            self.assertEqual(kharvox.directory(),self.root)
        self.preserved()

    def test_explicit_bad_selection_does_not_silently_fall_back(self):
        with mock.patch.dict(os.environ,{'NANNERS_KHARVOX_DIR':str(self.home/'missing')}):
            self.assertEqual(kharvox.directory(),self.home/'missing')
            with self.assertRaises(RuntimeError):kharvox._host_plan(self.recipe,self.game)
        self.preserved()

    def test_saved_selection_and_ambiguous_multiple_packages(self):
        import shutil
        second=self.home/'Downloads/KHARVOX-v1.4';shutil.copytree(self.root,second)
        with mock.patch.dict(os.environ,{'NANNERS_KHARVOX_DIR':''}):
            with self.assertRaisesRegex(RuntimeError,'Several'):kharvox.directory()
            kharvox.choose_directory(second,self.game);self.assertEqual(kharvox.directory(),second)
        # An explicit new GUI choice must win over a stale old environment path.
        self.assertEqual(kharvox.directory(),second)
        with self.assertRaisesRegex(RuntimeError,'outside'):kharvox.choose_directory(self.game,self.game)
        self.preserved()

    def test_launch_plan_reuses_proton_prefix_and_cleans_foreign_steam_state(self):
        env={'WINEPREFIX':'/foreign','PROTONPATH':'/foreign','PROTON_VERB':'runinprefix','STEAM_COMPAT_DATA_PATH':'/foreign',
             'SteamAppId':'611670','SteamGameId':'611670','KHARVOX_ENABLE_LAYER':'1','KHARVOX_DISABLE_LAYER':'1',
             'VK_INSTANCE_LAYERS':'VK_LAYER_KHARVOX_OPENXR:VK_LAYER_MANGOHUD_overlay','VK_LAYER_PATH':str(self.root),
             'PRESSURE_VESSEL_FILESYSTEMS_RW':'/keep-existing'}
        with mock.patch.dict(os.environ,env):args,actual,cwd=kharvox._host_plan(self.recipe,self.game)
        self.assertEqual(args,['/usr/bin/umu-run',str(self.root/'KharvoxLauncher.exe')]);self.assertEqual(cwd,str(self.root))
        self.assertEqual(actual['WINEPREFIX'],str(self.prefix));self.assertEqual(actual['PROTONPATH'],str(self.runner.parent))
        self.assertEqual(actual['STORE'],'gog');self.assertEqual(actual['GAMEID'],'0')
        for key in ['SteamAppId','SteamGameId','STEAM_COMPAT_DATA_PATH','PROTON_VERB','KHARVOX_ENABLE_LAYER','KHARVOX_DISABLE_LAYER','VK_LAYER_PATH']:
            self.assertNotIn(key,actual)
        self.assertEqual(actual['VK_INSTANCE_LAYERS'],'VK_LAYER_MANGOHUD_overlay')
        self.assertEqual(actual['CUSTOM_TEST'],'literal $(never execute)')
        self.assertEqual(actual['PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES'],'1')
        self.assertIn('/keep-existing',actual['PRESSURE_VESSEL_FILESYSTEMS_RW'])
        self.assertIn('/wivrn/comp_ipc',actual['PRESSURE_VESSEL_FILESYSTEMS_RW']);self.preserved()

    def test_saved_env_cannot_redirect_prefix_runner_or_ids(self):
        self.settings['enviromentOptions'] += [{'key':key,'value':'/wrong'} for key in ['WINEPREFIX','PROTONPATH','SteamAppId','STEAM_COMPAT_DATA_PATH']]
        self.write_settings();args,env,cwd=kharvox._host_plan(self.recipe,self.game)
        self.assertEqual(env['WINEPREFIX'],str(self.prefix));self.assertEqual(env['PROTONPATH'],str(self.runner.parent))
        self.assertNotIn('SteamAppId',env)

    def test_nested_prefix_supported_without_creating_or_migrating_it(self):
        import shutil
        shutil.move(self.prefix/'drive_c',self.prefix/'pfx');(self.prefix/'pfx').rename(self.prefix/'temporary')
        (self.prefix/'pfx').mkdir();(self.prefix/'temporary').rename(self.prefix/'pfx/drive_c')
        self.assertEqual(kharvox.prefix(self.recipe),self.prefix/'pfx')
        self.assertEqual(kharvox._host_plan(self.recipe,self.game)[1]['WINEPREFIX'],str(self.prefix))
        (self.prefix/'drive_c').mkdir()
        with self.assertRaisesRegex(RuntimeError,'Both direct'):kharvox.prefix(self.recipe)

    def test_missing_umu_bad_runner_flatpak_and_bad_env_fail_without_launch(self):
        with mock.patch.object(kharvox.shutil,'which',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'umu-run'):kharvox._host_plan(self.recipe,self.game)
        with mock.patch.dict(os.environ,{'FLATPAK_ID':'com.heroicgameslauncher.hgl'}):
            with self.assertRaisesRegex(RuntimeError,'native Heroic'):kharvox._host_plan(self.recipe,self.game)
        self.settings['wineVersion']['bin']=None;self.write_settings()
        with self.assertRaisesRegex(RuntimeError,'Proton'):kharvox._host_plan(self.recipe,self.game)
        self.settings['wineVersion']['bin']=str(self.runner);self.settings['enviromentOptions']=[{'key':'INVALID KEY','value':'x'}];self.write_settings()
        with self.assertRaisesRegex(RuntimeError,'environment'):kharvox._host_plan(self.recipe,self.game)

    def test_wrong_game_binary_is_blocked(self):
        self.exe.write_bytes(b'other build')
        with self.assertRaisesRegex(RuntimeError,'supported GOG'):kharvox._host_plan(self.recipe,self.game)
        self.exe.unlink();(self.game/'DOOMx64.exe').write_bytes(b'OpenGL')
        self.assertFalse(kharvox.game_row(self.game)['ok'])

    def test_launch_reuses_running_launcher_and_retains_bounded_output_wrapper(self):
        process=mock.Mock(pid=123);process.poll.return_value=None
        with mock.patch('vrhub.kharvox_bridge.plan',return_value=(['fixture'],{},str(self.root))), mock.patch('vrhub.heroic_injector.InjectorLaunch',return_value=process) as start:
            self.assertIs(kharvox.launch(self.recipe,self.game),process)
            self.assertIs(kharvox.launch(self.recipe,self.game),process);start.assert_called_once()
        self.preserved()

    def test_flat_launch_stays_with_heroic_without_mod_or_runtime_preflight(self):
        with mock.patch('vrhub.heroic.shutil.which',return_value='/usr/bin/heroic'),mock.patch('vrhub.handlers.subprocess.Popen',return_value=mock.Mock(pid=42)) as start, \
             mock.patch.object(hub,'preflight',side_effect=AssertionError('flat route needs no VR checks')):
            hub.launch_game_play(self.recipe)
        self.assertIn('heroic://launch?appName=1390579243&runner=gog',start.call_args.args[0]);self.preserved()

    def test_diagnostics_do_not_call_legacy_native_false_a_failure(self):
        logs=kharvox.logs(self.recipe)
        logs['main'].write_text('[KHARVOX] requestedRenderer=SFS nativeAttempt=False\n')
        logs['native'].write_text('fixture historical renderer log')
        report=log_diagnostics.report(self.recipe)
        info=next(f for item in report['logs'] for f in item['findings'] if f['id']=='kh-legacy-native')
        self.assertEqual(info['severity'],'INFO');self.assertIn('does not establish',info['explanation'])
        self.assertEqual(len(report['logs']),4);self.assertNotIn('Local gameplay test: SUCCESS',log_diagnostics.report_text(report))
        self.assertEqual(get_handler(self.recipe).bridge_log(self.recipe),logs['main']);self.preserved()

    def test_known_gog_guard_and_layer_refusal_remain_errors(self):
        path=kharvox.logs(self.recipe)['errors'];path.write_text('native render CVar identity changed\nThe KHARVOX layer was not loaded.\n')
        findings=next(x for x in log_diagnostics.report(self.recipe)['logs'] if x['path']==str(path))['findings']
        self.assertEqual({f['id'] for f in findings},{'kh-cvar-identity','kh-layer-not-loaded'})
        self.assertTrue(all(f['severity']=='ERROR' for f in findings));self.preserved()

    def test_prefix_log_symlink_cannot_escape_to_another_game(self):
        log=kharvox.logs(self.recipe)['main'];log.symlink_to(self.save)
        report=log_diagnostics.report(self.recipe)
        item=next(x for x in report['logs'] if x['path']==str(log));self.assertEqual(item['status'],'UNREADABLE');self.preserved()

    def test_compatibility_and_controller_guide_remain_experimental(self):
        with mock.patch('vrhub.runtime.active_runtime',return_value=(None,'')):
            report=compatibility.report(self.recipe)
        self.assertEqual(report['status'],'NOT READY');self.assertIn('USER-REPORTED LIVE TEST',compatibility.report_text(report))
        self.assertIsNone(report['local_test']);self.assertEqual(self.recipe['compatibility']['reference']['tested_on'],'2026-10-21')
        guide=controller_bindings.load('doom-2016-gog')
        self.assertTrue(all(r['evidence']!='tested' for s in guide['sections'] for r in s['bindings']));self.preserved()

    def test_wrong_store_game_and_handler_identity_are_rejected(self):
        for key,value in [('id','another-game'),('heroic_appid','1'),('method','uevr'),('store','heroic-epic')]:
            recipe=copy.deepcopy(self.recipe);recipe[key]=value
            with self.subTest(key=key),self.assertRaises(RecipeError):validate_recipe(recipe)

    @unittest.skipUnless(importlib.util.find_spec('PySide6'),'Optional PySide6 is not installed')
    def test_ninth_game_gui_and_launch_exit_output(self):
        from PySide6.QtWidgets import QApplication
        from vrhub.gui import HubWindow
        app=QApplication.instance() or QApplication([])
        with mock.patch.object(HubWindow,'check_updates'),mock.patch.object(HubWindow,'scan_setup'), \
             mock.patch('vrhub.app_update_gui.HubUpdateController.startup'):
            window=HubWindow()
            try:
                row=next(i for i in range(window.table.rowCount()) if 'DOOM (2016)' in window.table.item(i,0).text())
                window.table.selectRow(row);app.processEvents()
                self.assertEqual(window.table.rowCount(),9);self.assertFalse(window.kharvox_folder_btn.isHidden())
                self.assertFalse(window.doom_prepare_btn.isHidden());self.assertFalse(window.doom_probe_btn.isHidden())
                self.assertFalse(window.install_btn.isEnabled());self.assertFalse(window.inject_btn.isEnabled())
                self.assertEqual(window.game_launch_btn.text(),'Launch DOOM VR');self.assertEqual(window.game_play_btn.text(),'Launch DOOM (flat)')
                with mock.patch('vrhub.gui.QFileDialog.getExistingDirectory',return_value=str(self.root)):
                    window.choose_kharvox_folder()
                self.assertEqual(json.loads(kharvox.settings_file().read_text())['directory'],str(self.root))
                process=mock.Mock();process.poll.return_value=7;process.output_tail.return_value='synthetic launch failed'
                window.show_kharvox_launch(process);app.processEvents()
                from PySide6.QtWidgets import QLabel,QPlainTextEdit
                self.assertTrue(any('code 7' in x.text() for x in window.kharvox_dialog.findChildren(QLabel)))
                self.assertIn('synthetic launch failed',window.kharvox_dialog.findChild(QPlainTextEdit).toPlainText())
                window.kharvox_dialog.close()
                process.poll.return_value=0
                with mock.patch('vrhub.kharvox_bridge.start',return_value=process) as start:
                    window.run_kharvox_bridge('prepare');app.processEvents()
                    start.assert_called_once()
                    self.assertTrue(any('installation completed' in x.text() for x in window.kharvox_dialog.findChildren(QLabel)))
                window.kharvox_dialog.close()
                window.table.selectRow(next(i for i in range(9) if 'Subnautica' in window.table.item(i,0).text()))
                app.processEvents();self.assertTrue(window.kharvox_folder_btn.isHidden())
                self.assertTrue(window.doom_prepare_btn.isHidden());self.assertTrue(window.doom_probe_btn.isHidden())
                self.assertFalse(window.install_btn.isHidden())
            finally:window.close();app.processEvents()
