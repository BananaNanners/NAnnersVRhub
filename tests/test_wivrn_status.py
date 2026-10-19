import subprocess
import unittest
from unittest import mock

from vrhub import wivrn_status


class WiVRnStatusTests(unittest.TestCase):
    def setUp(self):
        self.tool = mock.patch.object(wivrn_status.shutil, 'which', return_value='/usr/bin/busctl')
        self.tool_mock = self.tool.start()
        self.run = mock.patch.object(wivrn_status.subprocess, 'run')
        self.run_mock = self.run.start()

    def tearDown(self):
        self.run.stop()
        self.tool.stop()

    def reply(self, text, code=0, error=''):
        return subprocess.CompletedProcess([], code, stdout=text, stderr=error)

    def test_connected_headset_and_name_with_read_only_no_activation_calls(self):
        self.run_mock.side_effect = [self.reply('v b true\n'), self.reply('v s "Meta Quest 3"\n')]
        status = wivrn_status.read_status()
        self.assertIs(status['connected'], True)
        self.assertEqual(status['system_name'], 'Meta Quest 3')
        self.assertTrue(status['sampled_at'])
        for call in self.run_mock.call_args_list:
            argv = call.args[0]
            self.assertIn('--auto-start=no', argv)
            self.assertIn('--allow-interactive-authorization=no', argv)
            self.assertIn('--user', argv)
            self.assertEqual(argv[argv.index('call') + 3], 'org.freedesktop.DBus.Properties')
            self.assertEqual(argv[argv.index('call') + 4], 'Get')
            self.assertLessEqual(call.kwargs['timeout'], 1.5)
        self.assertEqual([c.args[0][-1] for c in self.run_mock.call_args_list], ['HeadsetConnected', 'SystemName'])

    def test_disconnected_reply_does_not_read_old_headset_metadata(self):
        self.run_mock.return_value = self.reply('v b false')
        status = wivrn_status.read_status()
        self.assertIs(status['connected'], False)
        self.assertEqual(status['system_name'], '')
        self.assertEqual(self.run_mock.call_count, 1)

    def test_missing_busctl_is_unknown_without_launching(self):
        self.tool_mock.return_value = None
        self.assertIsNone(wivrn_status.read_status()['connected'])
        self.run_mock.assert_not_called()

    def test_wrong_type_and_malformed_reply_never_imply_connection(self):
        for text in ('v s "true"', 'v b 1', 'v b FALSE', 'true', 'v b true extra', 'v b', 'v s "bad'):
            with self.subTest(text=text):
                self.run_mock.return_value = self.reply(text)
                self.assertIsNone(wivrn_status.read_status()['connected'])

    def test_timeout_and_exec_error_are_unknown(self):
        for error in (subprocess.TimeoutExpired('busctl', 1.5), OSError('not available')):
            with self.subTest(error=error):
                self.run_mock.side_effect = error
                self.assertIsNone(wivrn_status.read_status()['connected'])

    def test_unavailable_service_permission_error_and_missing_property_are_unknown(self):
        for error in ('org.freedesktop.DBus.Error.ServiceUnknown', 'Access denied', 'Unknown property'):
            with self.subTest(error=error):
                self.run_mock.return_value = self.reply('', 1, error)
                status = wivrn_status.read_status()
                self.assertIsNone(status['connected'])
                self.assertTrue(status['detail'])

    def test_optional_name_failure_preserves_typed_connection_reply(self):
        self.run_mock.side_effect = [self.reply('v b true'), self.reply('', 1, 'Unknown property')]
        status = wivrn_status.read_status()
        self.assertIs(status['connected'], True)
        self.assertEqual(status['system_name'], '')

    def test_failed_query_does_not_retain_an_earlier_connected_sample(self):
        self.run_mock.side_effect = [self.reply('v b true'), self.reply('v s "Quest"'), self.reply('', 1)]
        self.assertIs(wivrn_status.read_status()['connected'], True)
        self.assertIsNone(wivrn_status.read_status()['connected'])

    def test_arbitrary_bus_errors_are_not_exported(self):
        self.run_mock.return_value = self.reply('', 1, 'secret-session-error-content')
        self.assertNotIn('secret-session-error-content', str(wivrn_status.read_status()))


if __name__ == '__main__':
    unittest.main()
