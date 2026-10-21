"""Hub integration policy; never run Wine, create a prefix or launch a game."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from vrhub import hub, kharvox_bridge as bridge, log_diagnostics, self_install
from vrhub.bepinex import digest


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = os.environ.get('NANNERS_TEST_BRIDGE_PAYLOAD')
        if not fixture:
            raise unittest.SkipTest('Set NANNERS_TEST_BRIDGE_PAYLOAD to the verified standalone payload for engine integration checks')
        cls.assets = Path(fixture)
        with mock.patch.object(bridge, 'ASSETS', cls.assets):
            cls.lab = bridge.engine()

    def setUp(self):
        patch = mock.patch.object(bridge, 'ASSETS', self.assets);patch.start();self.addCleanup(patch.stop)
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root/'state';self.results = self.state/'logs/probe-results';self.results.mkdir(parents=True)
        self.result = self.results/'fixture.json'
        self.data = {'schema_version':1,'probe_version':'0.1.6','nonce':'fixture','status':'passed','stage':'completed',
                     'failure':'','error_code':0,'xr_requested':True,'openxr_session_created':True,'audit_loaded':True,
                     'audit_failures':0,'instances':2,'enumerations':1,'submissions':3,'mediated_instances':2,
                     'mediated_devices':2,'devices':2,'device_destroys':2,'stripped_devices':1,'queue_acquires':3,
                     'command_begins':3,'command_allocations':4,'command_frees':3,'pool_destroys':3,
                     'tracked_commands':0,'gpu':'mock GPU','runtime':'mock runtime'}
        self.stamp = {'lab_version':'0.1.6','module_sha256':digest(bridge.ASSETS/'bin/winevulkan.dll'),
                      'native_module_sha256':digest(bridge.ASSETS/'bin/wineopenxr.so'),
                      'openxr_session':True,'probe_nonce':'fixture','probe_result':str(self.result)}
        self.write()
        bridge._active.clear()

    def write(self):
        self.result.write_text(json.dumps(self.data));(self.state/'probe-pass.json').write_text(json.dumps(self.stamp))

    def test_bundled_engine_matches_the_user_tested_version_and_inventory(self):
        self.assertEqual(self.lab.VERSION,'0.1.6');self.lab.verify_package()
        self.assertEqual(digest(bridge.ASSETS/'payload-sha256.json'),bridge.PAYLOAD_SHA256)

    def test_full_historical_pass_is_accepted_but_nonce_counts_and_module_changes_are_not(self):
        self.assertEqual(bridge._passed(self.lab,self.state),self.result)
        for key,value in [('probe_nonce','other'),('module_sha256','changed'),('native_module_sha256','changed'),('lab_version','0.1.5')]:
            old=self.stamp[key];self.stamp[key]=value;self.write()
            with self.subTest(key=key),self.assertRaises(ValueError):bridge._passed(self.lab,self.state)
            self.stamp[key]=old
        self.data['command_allocations']=1;self.write()
        with self.assertRaises(ValueError):bridge._passed(self.lab,self.state)

    def test_result_cannot_escape_the_results_folder_or_be_a_symlink(self):
        outside=self.root/'outside.json';outside.write_text(json.dumps(self.data));self.stamp['probe_result']=str(outside);self.write()
        with self.assertRaises(ValueError):bridge._passed(self.lab,self.state)
        self.stamp['probe_result']=str(self.result);self.write();self.result.unlink();self.result.symlink_to(outside)
        with self.assertRaises(ValueError):bridge._passed(self.lab,self.state)

    def test_missing_optional_component_does_not_block_the_other_games(self):
        with mock.patch.object(bridge, 'ASSETS', self.root/'missing'):
            self.assertEqual(len(hub.load_recipes()), 9)
            self.assertFalse(bridge.rows()[0]['ok'])

    def test_missing_inventory_is_rejected_before_import(self):
        with mock.patch.object(bridge,'ASSETS',self.root/'missing'):
            with self.assertRaisesRegex(RuntimeError,'not installed'):bridge.engine()

    def test_preflight_is_read_only_and_does_not_claim_gameplay(self):
        missing=self.root/'not-created'
        with mock.patch.object(bridge,'state_dir',return_value=missing):rows=bridge.rows()
        self.assertFalse(missing.exists());self.assertFalse(rows[-1]['ok'])
        with mock.patch.object(bridge,'state_dir',return_value=self.state),mock.patch.object(self.lab,'verify_runner',return_value=self.state/'runner'),mock.patch.object(bridge,'engine',return_value=self.lab):rows=bridge.rows()
        self.assertTrue(rows[-1]['ok']);self.assertIn('Historical synthetic',rows[-1]['detail'])

    def test_actions_delegate_to_unchanged_engine_with_isolated_python_and_no_shell(self):
        from vrhub import heroic,kharvox
        game=self.root/'DOOM';mod=self.root/'KHARVOX';source=self.root/'source runner'
        config=Path.home()/'.config/heroic'
        with mock.patch.object(kharvox,'_host_plan',return_value=(['must never execute'],{'PROTONPATH':str(source)},str(mod))), \
             mock.patch.object(heroic,'config_root',return_value=config),mock.patch.object(bridge,'state_dir',return_value=self.state), \
             mock.patch.object(bridge,'engine',return_value=self.lab),mock.patch.object(self.lab,'verify_runner',return_value=self.state/'runner'):
            for action in ('prepare','probe','doom'):
                args,env,cwd=bridge.plan({'id':'doom-2016-gog'},game,action)
                self.assertEqual(args[:3],[sys.executable,'-I','-u']);self.assertEqual(args[4],{'prepare':'install','probe':'probe','doom':'launch'}[action])
                self.assertNotIn('--payload',args);self.assertIn(str(self.state),args)
                self.assertEqual(cwd,str(Path(bridge.__file__).parent) if action=='prepare' else str(mod));self.assertNotIn('must never execute',args)
            (self.state/'probe-pass.json').unlink()
            with self.assertRaisesRegex(RuntimeError,'Install and test'):bridge.plan({},game,'doom')

    def test_custom_heroic_root_cannot_launch_a_different_default_prefix(self):
        from vrhub import heroic,kharvox
        with mock.patch.object(kharvox,'_host_plan',return_value=([],{'PROTONPATH':'/source'},'/mod')), \
             mock.patch.object(heroic,'config_root',return_value=self.root/'other-config'):
            with self.assertRaisesRegex(RuntimeError,'native Heroic settings'):bridge.plan({},Path('/game'),'probe')

    def test_only_one_bridge_action_can_run_and_repeating_it_reuses_process(self):
        proc=mock.Mock();proc.poll.return_value=None
        with mock.patch.object(bridge,'state_dir',return_value=self.state),mock.patch.object(bridge,'plan',return_value=(['fixture'],{},str(self.root))), \
             mock.patch('vrhub.heroic_injector.InjectorLaunch',return_value=proc) as start:
            self.assertIs(bridge.start({},None,'prepare'),proc);self.assertIs(bridge.start({},None,'prepare'),proc)
            with self.assertRaisesRegex(RuntimeError,'still running'):bridge.start({},None,'probe')
            start.assert_called_once()

    def test_managed_installer_keeps_the_thin_helpers_and_rejects_missing_python(self):
        source=Path(__file__).resolve().parents[1]
        _,files=self_install._source_files(source)
        for name in ('bridge_installer.py','kharvox_component.py','kharvox_bridge.py'):
            self.assertIn('vrhub/'+name,files)
        self.assertFalse(any('assets/kharvox-lab' in name for name in files))
        dest=self.root/'source';shutil.copytree(source/'vrhub',dest/'vrhub',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(source/'pyproject.toml',dest/'pyproject.toml');(dest/'vrhub/kharvox_component.py').unlink()
        with self.assertRaisesRegex(RuntimeError,'Incomplete source folder'):self_install._source_files(dest)

    def test_sfs_finding_is_historical_and_does_not_claim_exact_cause(self):
        recipe=hub.load_recipes()['doom-2016-gog']
        path=self.root/'KHARVOX.log';path.write_text('[SFS] invalid unordered_map<K, T> key\n')
        report=log_diagnostics.report(recipe,files=[path]);finding=report['logs'][0]['findings'][0]
        self.assertEqual(finding['id'],'kh-sfs-command-state');self.assertIn('alone does not identify',finding['explanation'])


if __name__=='__main__':unittest.main()
