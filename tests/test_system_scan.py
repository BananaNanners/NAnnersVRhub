import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vrhub import cli, runtime, system_scan


class RuntimeDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {
            'HOME': str(self.root), 'XDG_CONFIG_HOME': str(self.root / 'config'),
            'XDG_CONFIG_DIRS': str(self.root / 'system'),
        }, clear=True)
        self.env.start()
        self.arch = mock.patch.object(runtime.platform, 'machine', return_value='x86_64')
        self.arch.start()

    def tearDown(self):
        self.arch.stop()
        self.env.stop()
        self.tmp.cleanup()

    def manifest(self, path, library='libwivrn.so', data=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data if data is not None else {
            'file_format_version': '1.0.0', 'runtime': {'library_path': library}}))
        return path

    def test_user_arch_manifest_wins_over_generic_and_system(self):
        base = self.root / 'config/openxr/1'
        self.manifest(base / 'active_runtime.json', 'libmonado.so')
        wanted = self.manifest(base / 'active_runtime.x86_64.json')
        self.manifest(self.root / 'system/openxr/1/active_runtime.json', 'libsteamxr.so')
        self.assertEqual(runtime.active_runtime(), (wanted, 'libwivrn.so'))
        self.assertTrue(runtime.is_wivrn())

    def test_invalid_explicit_override_does_not_fall_back(self):
        self.manifest(self.root / 'config/openxr/1/active_runtime.json')
        forced = self.root / 'missing-wivrn.json'
        os.environ['XR_RUNTIME_JSON'] = str(forced)
        self.assertEqual(runtime.active_runtime(), (forced, ''))
        self.assertFalse(runtime.is_wivrn())

    def test_broken_user_symlink_is_reported_instead_of_system_fallback(self):
        path = self.root / 'config/openxr/1/active_runtime.x86_64.json'
        path.parent.mkdir(parents=True)
        path.symlink_to(self.root / 'missing-wivrn.json')
        self.manifest(self.root / 'system/openxr/1/active_runtime.json')
        self.assertEqual(runtime.active_runtime(), (path, ''))
        self.assertFalse(runtime.is_wivrn())

    def test_malformed_shapes_and_unreadable_manifest_are_invalid(self):
        path = self.root / 'override.json'
        os.environ['XR_RUNTIME_JSON'] = str(path)
        for data in ([], {}, {'runtime': None}, {'runtime': {'library_path': 42}},
                     {'file_format_version': '1.0.0', 'runtime': {'library_path': ''}}):
            with self.subTest(data=data):
                path.write_text(json.dumps(data))
                self.assertEqual(runtime.active_runtime(), (path, ''))
        path.write_text('{not json')
        self.assertEqual(runtime.active_runtime(), (path, ''))
        with mock.patch.object(Path, 'read_text', side_effect=PermissionError('denied')):
            self.assertEqual(runtime.active_runtime(), (path, ''))

    def test_xdg_directory_order_and_etc_fallback(self):
        os.environ['XDG_CONFIG_DIRS'] = f'{self.root}/one:{self.root}/two'
        candidates = runtime.runtime_candidates()
        self.assertEqual(candidates[2].parent, self.root / 'one/openxr/1')
        self.assertEqual(candidates[4].parent, self.root / 'two/openxr/1')
        self.assertEqual(candidates[-1], Path('/etc/openxr/1/active_runtime.json'))


class SystemScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = self.root / 'config'
        self.manifest = self.root / 'wivrn/runtime.json'
        self.manifest.parent.mkdir()
        self.library = self.manifest.parent / 'libwivrn.so'
        self.library.write_bytes(b'fixture (never loaded)')
        self.manifest.write_text(json.dumps({'file_format_version': '1.0.0',
                                            'runtime': {'library_path': './libwivrn.so'}}))
        self.env = mock.patch.dict(os.environ, {
            'HOME': str(self.root), 'XDG_CONFIG_HOME': str(self.config),
            'XR_RUNTIME_JSON': str(self.manifest), 'VRHUB_STEAM_ROOTS': str(self.root / 'steam'),
            'XDG_RUNTIME_DIR': str(self.root / 'run'), 'SECRET_API_KEY': 'do-not-export',
        }, clear=True)
        self.env.start()
        self.libs = mock.patch.object(system_scan.ctypes.util, 'find_library', return_value='fixture.so')
        self.lib_lookup = self.libs.start()
        self.commands = mock.patch.object(system_scan.shutil, 'which', return_value=None)
        self.commands.start()
        self.processes = mock.patch.object(system_scan, '_process_names', return_value={'wivrn-server'})
        self.process_lookup = self.processes.start()

    def tearDown(self):
        self.processes.stop()
        self.commands.stop()
        self.libs.stop()
        self.env.stop()
        self.tmp.cleanup()

    def row(self, report, key):
        return next(r for r in report['rows'] if r['id'] == key)

    def test_valid_host_does_not_claim_headset_or_controller_connection(self):
        report = system_scan.scan()
        self.assertEqual(report['status'], 'HOST CHECKS PASSED')
        self.assertFalse(report['hardware_verified'])
        self.assertEqual(self.row(report, 'runtime_process')['status'], 'ok')
        self.assertEqual(self.row(report, 'headset')['status'], 'unknown')
        self.assertEqual(self.row(report, 'controllers')['status'], 'unknown')
        self.assertEqual(self.row(report, 'runtime_library')['status'], 'ok')
        self.assertIn('UNVERIFIED', system_scan.report_text(report))

    def test_relative_library_uses_symlink_target_directory(self):
        link = self.root / 'active.json'
        link.symlink_to(self.manifest)
        os.environ['XR_RUNTIME_JSON'] = str(link)
        self.assertEqual(self.row(system_scan.scan(), 'runtime_library')['status'], 'ok')

    def test_missing_library_and_runtime_block_host_checks(self):
        self.library.unlink()
        self.assertEqual(system_scan.scan()['status'], 'NOT READY')
        self.manifest.unlink()
        report = system_scan.scan()
        self.assertEqual(report['status'], 'NOT READY')
        self.assertTrue(self.row(report, 'openxr')['action'])

    def test_soname_library_requires_live_verification(self):
        self.manifest.write_text(json.dumps({'file_format_version': '1.0.0',
                                            'runtime': {'library_path': 'libwivrn.so'}}))
        report = system_scan.scan()
        self.assertEqual(report['status'], 'NEEDS CHECKS')
        self.assertEqual(self.row(report, 'runtime_library')['status'], 'unknown')

    def test_missing_loader_is_not_reported_as_passed(self):
        self.lib_lookup.return_value = None
        report = system_scan.scan()
        self.assertEqual(report['status'], 'NEEDS CHECKS')
        self.assertEqual(self.row(report, 'openxr_loader')['status'], 'warning')

    def test_adapter_override_has_precedence_over_openvr_paths(self):
        adapter = self.root / 'xrizer/bin/linux64/vrclient.so'
        adapter.parent.mkdir(parents=True)
        adapter.write_bytes(b'adapter')
        config = self.config / 'openvr/openvrpaths.vrpath'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({'runtime': [str(self.root / 'xrizer')]}))
        self.assertEqual(self.row(system_scan.scan(), 'adapter')['status'], 'ok')
        os.environ['VR_OVERRIDE'] = str(self.root / 'missing-adapter')
        report = system_scan.scan()
        self.assertEqual(self.row(report, 'adapter')['status'], 'warning')
        self.assertIn('VR_OVERRIDE', self.row(report, 'adapter')['detail'])

    def test_bad_adapter_config_and_unknown_process_inventory_do_not_crash(self):
        config = self.config / 'openvr/openvrpaths.vrpath'
        config.parent.mkdir(parents=True)
        config.write_text('{bad')
        self.process_lookup.return_value = None
        report = system_scan.scan()
        self.assertEqual(self.row(report, 'adapter')['status'], 'warning')
        self.assertEqual(self.row(report, 'runtime_process')['status'], 'unknown')

    def test_scan_leaves_files_unchanged_and_excludes_unrelated_secrets(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with mock.patch('subprocess.Popen', side_effect=AssertionError('must not launch')):
            report = system_scan.scan()
        after = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertNotIn('do-not-export', json.dumps(report))
        self.assertEqual(set(report['environment']), {'XR_RUNTIME_JSON'})

    def test_reports_escape_html_from_paths(self):
        os.environ['VR_OVERRIDE'] = '<script>alert(1)</script>'
        rendered = system_scan.report_html(system_scan.scan())
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)

    def test_scan_cli_emits_valid_json_without_loading_recipes(self):
        with mock.patch.object(cli.hub, 'load_recipes', side_effect=AssertionError('must not load')):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = cli.main(['scan', '--json'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())['schema_version'], 2)
        self.library.unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['scan']), 1)

    def telemetry(self, connected, name='Meta Quest 3'):
        return dict(connected=connected, system_name=name if connected else '',
                    source='WiVRn D-Bus HeadsetConnected', detail='Fixture connection state.', sampled_at='fixture')

    def test_typed_connection_can_confirm_server_without_visible_process(self):
        self.process_lookup.return_value = set()
        with mock.patch.object(system_scan.wivrn_status, 'read_status', return_value=self.telemetry(True)):
            report = system_scan.scan()
        self.assertIs(report['live']['server_running'], True)
        self.assertIs(report['live']['headset_connected'], True)
        self.assertTrue(report['live']['headset_connection_verified'])
        self.assertFalse(report['live']['controllers_verified'])
        self.assertFalse(report['hardware_verified'])
        self.assertEqual(self.row(report, 'headset')['status'], 'ok')
        self.assertIn('HEADSET CONNECTED', system_scan.report_text(report))
        self.assertIn('CONTROLLERS UNVERIFIED', system_scan.report_text(report))

    def test_live_refresh_handles_disconnect_and_telemetry_loss_without_stale_status(self):
        with mock.patch.object(system_scan.wivrn_status, 'read_status') as query:
            query.return_value = self.telemetry(True)
            first = system_scan.scan()
            query.return_value = self.telemetry(False)
            disconnected = system_scan.refresh_live(first)
            self.assertIs(first['live']['headset_connected'], True)
            self.assertIs(disconnected['live']['headset_connected'], False)
            self.assertEqual(first['scanned_at'], disconnected['scanned_at'])
            self.assertIn('HEADSET DISCONNECTED', system_scan.report_text(disconnected))
            query.return_value = self.telemetry(None)
            unknown = system_scan.refresh_live(disconnected)
            self.assertIsNone(unknown['live']['headset_connected'])
            self.assertIn('HEADSET UNKNOWN', system_scan.report_html(unknown))
            ids = [r['id'] for r in unknown['rows']]
            self.assertEqual(len(ids), len(set(ids)))

    def test_other_selected_runtime_does_not_use_wivrn_connection_evidence(self):
        self.manifest.write_text(json.dumps({'file_format_version': '1.0.0',
                                            'runtime': {'library_path': 'libsteamxr.so'}}))
        with mock.patch.object(system_scan.wivrn_status, 'read_status') as query:
            report = system_scan.scan()
        query.assert_not_called()
        self.assertEqual(report['runtime'], 'SteamVR')
        self.assertIsNone(report['live']['headset_connected'])

    def test_live_refresh_rescans_after_runtime_override_changes(self):
        first = system_scan.scan()
        os.environ['XR_RUNTIME_JSON'] = str(self.root / 'missing.json')
        report = system_scan.refresh_live(first)
        self.assertEqual(report['status'], 'NOT READY')
        self.assertFalse(report['live']['runtime_selected'])
        self.assertIsNone(report['live']['headset_connected'])

    def test_custom_configured_adapter_also_appears_in_inventory(self):
        adapter = self.root / 'unusual/custom-xrizer/bin/linux64/vrclient.so'
        adapter.parent.mkdir(parents=True)
        adapter.write_bytes(b'fixture')
        os.environ['VR_OVERRIDE'] = str(adapter.parents[2])
        report = system_scan.scan()
        self.assertEqual(self.row(report, 'adapter')['status'], 'ok')
        self.assertEqual(self.row(report, 'xrizer')['status'], 'ok')
        self.assertIn(str(adapter.parents[2]), self.row(report, 'xrizer')['detail'])

    def test_connected_headset_name_is_escaped_in_html_reports(self):
        with mock.patch.object(system_scan.wivrn_status, 'read_status', return_value=self.telemetry(True, '<script>name</script>')):
            report = system_scan.scan()
        self.assertNotIn('<script>', system_scan.report_html(report))
        self.assertIn('&lt;script&gt;', system_scan.report_html(report))

    def test_process_inventory_reads_only_current_user_names(self):
        self.processes.stop()
        proc = self.root / 'proc'
        entry = proc / '123'
        entry.mkdir(parents=True)
        (entry / 'comm').write_text('wivrn-server\n')
        self.assertEqual(system_scan._process_names(proc), {'wivrn-server'})
        self.assertIsNone(system_scan._process_names(self.root / 'missing-proc'))


if __name__ == '__main__':
    unittest.main()
