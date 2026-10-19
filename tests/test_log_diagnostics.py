import contextlib
from datetime import datetime, timezone
import io
import json
import os
import unittest
from unittest import mock

from vrhub import cli, compatibility, live_tests, log_diagnostics as logs
from tests import test_workflow_compatibility as fixtures


POSE = 'OpenXRManager: xrEndFrame mono submit failed (res=-39)'


class LogDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SteamWorkflowCompatibilityTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.recipe, self.game, self.prefix = self.fixture.cyberpunk()
        self.roots = [self.fixture.steam]
        self.path = self.game / 'bin/x64/cyberpunkvrport.log'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.now = datetime(2026, 10, 18, 21, 0, tzinfo=timezone.utc)

    def write(self, text=POSE):
        self.path.write_text(text, encoding='utf-8')
        os.utime(self.path, (self.now.timestamp(), self.now.timestamp()))
        return self.path

    def report(self, files=None):
        return logs.report(self.recipe, self.roots, files=files, now=self.now)

    def findings(self):
        return self.report()['logs'][0]['findings']

    def test_numeric_pose_error_is_explained_with_bounded_evidence_and_cp_workaround(self):
        self.write('\n'.join([POSE] * 9))
        rep = self.report()
        item = rep['logs'][0]
        finding = item['findings'][0]
        self.assertEqual(rep['status'], 'RECOGNIZED LOG EVIDENCE')
        self.assertEqual(finding['id'], 'xr-pose-invalid')
        self.assertEqual(finding['count'], 9)
        self.assertEqual(len(finding['excerpts']), 3)
        self.assertEqual(finding['excerpts'][-1]['tail_line'], 9)
        self.assertIn('VR menu quad OFF', finding['action'])
        self.assertIn('Enable HUD panel OFF', finding['action'])
        self.assertIn('World-space interactions / dialogs OFF', finding['action'])
        self.assertIn('passthrough', finding['action'])
        self.assertIn('unconfirmed', finding['action'])
        self.assertEqual(item['freshness'], 'RECENT')
        self.assertIn('Historical log evidence only', logs.report_text(rep))

    def test_unrelated_numeric_errors_and_other_codes_are_not_pose_errors(self):
        self.write('disk write failed (res=-39)\nxrEndFrame success (res=-39)\n'
                   'xrEndFrame failed (res=-390)\nxrEndFrame failed (res=-39.0)\n'
                   'xrEndFrame failed (res=-2)\nXR_ERROR_POSE_INVALID_SUFFIX')
        self.assertEqual(self.findings(), [])
        self.assertEqual(self.report()['status'], 'NO KNOWN SIGNATURES FOUND')

    def test_symbolic_results_and_numeric_initialization_failures(self):
        self.write('xrCreateInstance failed result=-51\nXR_ERROR_EXTENSION_NOT_PRESENT\n'
                   'xrCreateSession failed (res=-50)\nXR_ERROR_POSE_INVALID')
        self.assertEqual({f['id'] for f in self.findings()},
                         {'xr-runtime-unavailable','xr-extension-missing','xr-graphics-requirements','xr-pose-invalid'})

    def test_menu_gate_is_information_and_does_not_prove_setting_or_failure(self):
        self.write('Depth gate: active=0 menu=1\nDepth gate: menu=0\nOther menu=1')
        finding = self.findings()[0]
        self.assertEqual(finding['id'], 'cp-menu-depth-gate')
        self.assertEqual(finding['severity'], 'INFO')
        self.assertEqual(finding['count'], 1)
        self.assertIn('does not prove', finding['explanation'])

    def test_manual_selection_replaces_auto_and_is_game_scoped(self):
        self.write()
        other = self.fixture.home / 'selected.log'
        other.write_text('XR_ERROR_RUNTIME_UNAVAILABLE')
        rep = self.report([other])
        self.assertEqual(len(rep['logs']), 1)
        self.assertEqual(rep['logs'][0]['path'], str(other))
        self.assertEqual(rep['logs'][0]['selection'], 'user-selected')
        self.assertIn('user-supplied', rep['discovery_note'])
        recipe = self.fixture.recipes['ready-or-not']
        rep = logs.report(recipe, self.roots, [self.path], self.now)
        finding = rep['logs'][0]['findings'][0]
        self.assertNotIn('F10', finding['action'])
        self.assertNotIn('Menu-related', finding['title'])

    def test_unsupported_auto_path_does_not_search_arbitrary_files(self):
        self.write()
        for rid in ('ready-or-not', 'skyrim-vr-mgo'):
            rep = logs.report(self.fixture.recipes[rid], self.roots, now=self.now)
            self.assertEqual(rep['logs'], [])
            self.assertIn('not configured', rep['discovery_note'])
            self.assertEqual(rep['status'], 'NO READABLE LOG EVIDENCE')

    def test_fatekeeper_uses_own_prefix_profile_log_and_generic_advice(self):
        recipe, game, prefix, _ = self.fixture.fatekeeper()
        path = prefix / 'drive_c/users/steamuser/AppData' / recipe['profile']['dir'] / 'log.txt'
        path.write_text(POSE + '\nDepth gate menu=1')
        rep = logs.report(recipe, self.roots, now=self.now)
        self.assertEqual(rep['logs'][0]['path'], str(path))
        self.assertEqual(len(rep['logs'][0]['findings']), 1)
        self.assertNotIn('F10', rep['logs'][0]['findings'][0]['action'])

    def test_missing_prefix_and_game_are_incomplete_evidence(self):
        recipe = self.fixture.recipes['fatekeeper']
        rep = logs.report(recipe, self.roots)
        self.assertEqual(rep['logs'], [])
        recipe, game, prefix, _ = self.fixture.fatekeeper()
        import shutil
        shutil.rmtree(prefix)
        rep = logs.report(recipe, self.roots)
        self.assertIn('Proton prefix not found', rep['discovery_note'])

    def test_missing_empty_and_clean_logs_never_report_gameplay_pass(self):
        self.assertEqual(self.report()['logs'][0]['status'], 'MISSING')
        self.write('')
        self.assertEqual(self.report()['logs'][0]['status'], 'EMPTY')
        self.write('VR session started successfully')
        rep = self.report()
        self.assertEqual(rep['status'], 'NO KNOWN SIGNATURES FOUND')
        self.assertIn('does not verify', rep['notice'])
        self.assertNotIn('PASSED', logs.report_text(rep))

    def test_stale_and_future_timestamps_do_not_hide_evidence(self):
        self.write()
        for delta, expected in ((-25*3600, 'STALE'), (600, 'FUTURE TIMESTAMP')):
            os.utime(self.path, (self.now.timestamp()+delta, self.now.timestamp()+delta))
            rep = self.report()
            self.assertEqual(rep['logs'][0]['freshness'], expected)
            self.assertEqual(rep['logs'][0]['findings'][0]['count'], 1)
            self.assertIn(expected, logs.report_text(rep))

    def test_large_log_only_reads_tail_and_discards_partial_leading_line(self):
        self.write(POSE + '\n' + ('x' * 1000 + '\n') * 700 + POSE + '\n')
        item = self.report()['logs'][0]
        self.assertEqual(item['bytes_read'], logs.MAX_BYTES)
        self.assertTrue(item['truncated'])
        self.assertEqual(item['findings'][0]['count'], 1)

    def test_line_and_excerpt_limits_are_reported(self):
        self.write(('ok\n' * (logs.MAX_LINES+50)) + (POSE + 'x'*5000))
        item = self.report()['logs'][0]
        self.assertEqual(item['lines_omitted'], 51)
        self.assertEqual(item['long_lines_clipped'], 1)
        self.assertLessEqual(len(item['findings'][0]['excerpts'][0]['text']), 300)

    def test_binary_invalid_utf8_and_utf16_are_handled(self):
        self.path.write_bytes(b'\x00\x01' + POSE.encode())
        self.assertEqual(self.report()['logs'][0]['status'], 'UNREADABLE')
        self.path.write_bytes(b'\xff' + POSE.encode())
        self.assertEqual(len(self.findings()), 1)
        for encoding in ('utf-16', 'utf-16-be'):
            data = (POSE + '\n').encode(encoding)
            if encoding.endswith('be'):
                data = b'\xfe\xff' + data
            self.path.write_bytes(data)
            self.assertEqual(len(self.findings()), 1)

    def test_symlinks_escaped_parent_and_special_files_are_rejected(self):
        real = self.fixture.home / 'real.log'
        real.write_text(POSE)
        self.path.symlink_to(real)
        self.assertEqual(self.report()['logs'][0]['status'], 'UNREADABLE')
        self.assertEqual(self.report([self.path])['logs'][0]['status'], 'UNREADABLE')
        self.path.unlink()
        os.mkfifo(self.path)
        self.assertEqual(self.report()['logs'][0]['status'], 'UNREADABLE')
        self.path.unlink()
        self.path.parent.rmdir()
        self.path.parent.symlink_to(self.fixture.home, target_is_directory=True)
        (self.fixture.home / self.path.name).write_text(POSE)
        item = self.report()['logs'][0]
        self.assertIn('escapes', item['detail'])
        self.assertEqual(item['status'], 'UNREADABLE')

    def test_permission_and_directory_errors_are_visible_per_file(self):
        self.write()
        with mock.patch('vrhub.log_diagnostics.os.open', side_effect=PermissionError('Denied')):
            item = self.report()['logs'][0]
        self.assertEqual(item['status'], 'UNREADABLE')
        self.assertIn('Denied', item['detail'])
        item = self.report([self.path.parent])['logs'][0]
        self.assertEqual(item['status'], 'UNREADABLE')

    def test_file_count_bound_deduplication_and_independent_errors(self):
        self.write()
        for selection in ([], [self.path]*5):
            with self.assertRaises(RuntimeError):
                self.report(selection)
        rep = self.report([self.path, self.path, self.fixture.home/'missing.log'])
        self.assertEqual(len(rep['logs']), 2)
        self.assertEqual(rep['logs'][0]['status'], 'READ')
        self.assertEqual(rep['logs'][1]['status'], 'MISSING')

    def test_no_installer_runtime_settings_or_test_history_mutation(self):
        self.write()
        before = {p: p.read_bytes() for p in self.fixture.home.rglob('*') if p.is_file()}
        compat_before = compatibility.report(self.recipe, self.roots)
        self.report()
        after = {p: p.read_bytes() for p in self.fixture.home.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse(live_tests.history_file().exists())
        compat_after = compatibility.report(self.recipe, self.roots)
        self.assertEqual(compat_before['status'], compat_after['status'])
        self.assertEqual(compat_before['checks'], compat_after['checks'])
        self.assertEqual(compat_after['local_test_count'], 0)

    def test_literal_excerpts_strip_controls_and_are_not_rendered_as_html(self):
        self.write('\x1b[31m' + POSE + ' <script>test</script>\x1b[0m\x07')
        text = logs.report_text(self.report())
        self.assertIn('<script>test</script>', text)
        self.assertNotIn('\x1b', text)
        self.assertNotIn('\x07', text)

    def test_naive_time_is_rejected(self):
        with self.assertRaises(ValueError):
            logs.report(self.recipe, self.roots, now=datetime(2026,10,18))

    def test_fatekeeper_validation_failure_loop_is_recognized_in_bounded_tail(self):
        # Minimal, anonymized reproduction of the submitted failing log.
        self.recipe = self.fixture.recipes['fatekeeper']
        pair = ('[UnrealVR] [error] [VR] xrEndFrame failed: XR_ERROR_VALIDATION_FAILURE\n'
                '[UnrealVR] [error] [VR] xrBeginFrame failed: XR_FRAME_DISCARDED\n')
        self.write('earlier initialization\n' + pair*10000)
        item = self.report([self.path])['logs'][0]
        self.assertTrue(item['truncated'])
        findings = {f['id']:f for f in item['findings']}
        self.assertEqual(set(findings), {'xr-validation-failure','xr-frame-discarded'})
        self.assertEqual(findings['xr-validation-failure']['severity'], 'ERROR')
        self.assertGreater(findings['xr-validation-failure']['count'], 1000)
        self.assertLess(findings['xr-validation-failure']['count'], 10000)
        self.assertEqual(findings['xr-frame-discarded']['severity'], 'INFO')
        self.assertIn('success status',findings['xr-frame-discarded']['explanation'])
        self.assertNotIn('F10',findings['xr-validation-failure']['action'])

    def test_numeric_validation_failure_needs_openxr_failed_call_context(self):
        self.write('xrEndFrame failed (res=-1)\ndisk failed (res=-1)\n'
                   'xrEndFrame failed (res=-10)\nxrEndFrame success (res=-1)\n'
                   'xrEndFrame failed (res=-1.5)')
        findings = self.findings()
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['id'], 'xr-validation-failure')
        self.assertEqual(findings[0]['count'], 1)

    def test_frame_discard_requires_beginframe_context_and_is_informational(self):
        self.write('XR_FRAME_DISCARDED\nother failed: XR_FRAME_DISCARDED\n'
                   'xrBeginFrame returned XR_FRAME_DISCARDED\n'
                   '[error] xrBeginFrame failed: XR_FRAME_DISCARDED')
        findings = self.findings()
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['id'], 'xr-frame-discarded')
        self.assertEqual(findings[0]['severity'], 'INFO')
        self.assertEqual(findings[0]['count'], 2)
        self.assertIn('(+9)',findings[0]['title'])

    def test_hotfix_does_not_change_uevr_config_or_save_history(self):
        recipe, game, prefix, _ = self.fixture.fatekeeper()
        config = prefix / 'drive_c/users/steamuser/AppData' / recipe['profile']['dir'] / 'config.txt'
        config.write_bytes(b'VR_2DScreenMode=true\r\nVR_SynchronizationMode=2\r\n')
        before = config.read_bytes()
        self.write('xrEndFrame failed: XR_ERROR_VALIDATION_FAILURE')
        report = logs.report(recipe,self.roots,files=[self.path])
        self.assertEqual(report['logs'][0]['findings'][0]['id'],'xr-validation-failure')
        self.assertEqual(config.read_bytes(),before)
        self.assertFalse(live_tests.history_file().exists())

    def test_cli_text_json_and_read_availability_exit_codes(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(cli.main(['logs','cyberpunk-2077']), 1)
        self.write()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(cli.main(['logs','cyberpunk-2077','--json']), 0)
        rep = json.loads(output.getvalue())
        self.assertEqual(rep['schema_version'], 1)
        self.assertEqual(rep['logs'][0]['findings'][0]['id'], 'xr-pose-invalid')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(cli.main(['logs','ready-or-not','--file',str(self.path)]), 0)
        self.assertIn('user-selected', output.getvalue())
        self.assertNotIn('F10', output.getvalue())


if __name__ == '__main__':
    unittest.main()
