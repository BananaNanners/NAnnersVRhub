"""Installer policy tests; no Wine, headset, game or network access."""
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

from vrhub import bridge_installer as bridge


class Response(io.BytesIO):
    def __init__(self, data, length=None):
        super().__init__(data)
        self.headers = {'Content-Length': str(len(data) if length is None else length)}

    def geturl(self):
        return 'https://release-assets.githubusercontent.com/fixture'


class InstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = self.root / 'state'
        self.state.mkdir()
        self.engine = mock.Mock()
        self.engine.HERE = self.root / 'payload'
        self.engine.verify_base.return_value = None
        self.engine.read_json.return_value = {'tracked': 'fixture'}

    def archive(self, entries):
        p = self.root / 'base.tar.xz'
        with tarfile.open(p, 'w:xz') as tar:
            for name, kind, content in entries:
                info = tarfile.TarInfo(name)
                if kind == 'file':
                    data = content.encode()
                    info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))
                else:
                    info.type = tarfile.SYMTYPE
                    info.linkname = content
                    tar.addfile(info)
        return p

    def pin(self, path):
        for patch in (mock.patch.object(bridge, 'BASE_SIZE', path.stat().st_size),
                      mock.patch.object(bridge, 'BASE_SHA256', bridge.digest(path))):
            patch.start()
            self.addCleanup(patch.stop)

    def test_payload_inventory_is_pinned_before_import(self):
        with self.assertRaises((ValueError, OSError)):
            bridge.load_engine(self.root / 'absent')
        payload = self.root / 'changed'
        payload.mkdir()
        (payload / 'payload-sha256.json').write_text('{}')
        (payload / 'lab.py').write_text('raise AssertionError("must not execute")')
        with self.assertRaisesRegex(ValueError, 'payload inventory'):
            bridge.load_engine(payload)

    def test_download_verifies_digest_and_reuses_cache_without_network(self):
        archive = self.archive([(bridge.BASE_NAME + '/proton', 'file', 'fixture')])
        self.pin(archive)
        opener = mock.Mock()
        opener.open.return_value = Response(archive.read_bytes())
        with mock.patch.object(bridge.urllib.request, 'build_opener', return_value=opener):
            cached = bridge.download_archive(self.state / 'downloads')
            self.assertEqual(cached.read_bytes(), archive.read_bytes())
            bridge.download_archive(self.state / 'downloads')
            opener.open.assert_called_once()

    def test_wrong_hash_and_truncation_leave_no_installed_download(self):
        archive = self.archive([(bridge.BASE_NAME + '/proton', 'file', 'fixture')])
        self.pin(archive)
        for body in (archive.read_bytes()[:-1], b'x' * archive.stat().st_size):
            opener = mock.Mock()
            opener.open.return_value = Response(body, archive.stat().st_size)
            with mock.patch.object(bridge.urllib.request, 'build_opener', return_value=opener):
                with self.assertRaisesRegex(ValueError, 'pinned upstream'):
                    bridge.download_archive(self.state / 'downloads')
            self.assertEqual(list((self.state / 'downloads').iterdir()), [])

    def test_oversize_and_network_failure_remove_partial_files(self):
        with mock.patch.object(bridge, 'BASE_SIZE', 3):
            opener = mock.Mock()
            opener.open.return_value = Response(b'four', 3)
            with mock.patch.object(bridge.urllib.request, 'build_opener', return_value=opener):
                with self.assertRaisesRegex(ValueError, 'exceeded'):
                    bridge.download_archive(self.state / 'downloads')
        opener.open.side_effect = OSError('offline')
        with mock.patch.object(bridge.urllib.request, 'build_opener', return_value=opener):
            with self.assertRaisesRegex(OSError, 'offline'):
                bridge.download_archive(self.state / 'downloads')
        self.assertEqual(list((self.state / 'downloads').iterdir()), [])

    def test_cache_symlinks_and_downgrade_redirects_are_rejected(self):
        cache = self.state / 'downloads'
        cache.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'linked'):
            bridge.download_archive(cache)
        for url in ('http://github.com/file', 'https://example.com/file', 'https://github.com:444/file'):
            self.assertFalse(bridge.allowed_url(url))
            with self.assertRaisesRegex(ValueError, 'redirect'):
                bridge.ReleaseRedirect().redirect_request(None, None, 302, '', {}, url)

    def test_extraction_keeps_legitimate_internal_library_symlinks(self):
        base = bridge.BASE_NAME
        archive = self.archive([(base + '/lib/a', 'file', 'library'), (base + '/lib/b', 'symlink', 'a')])
        self.pin(archive)
        target = bridge.extract_base(archive, self.state)
        self.assertEqual((target / 'lib/b').read_text(), 'library')

    def test_traversal_external_links_and_foreign_roots_do_not_extract(self):
        for entry in [('../escape', 'file', 'bad'), ('/absolute', 'file', 'bad'),
                      ('other/proton', 'file', 'bad'), (bridge.BASE_NAME + '/link', 'symlink', '../../escape')]:
            archive = self.archive([entry])
            with mock.patch.object(bridge, 'check_archive'):
                with self.assertRaisesRegex(ValueError, 'Unsafe|External'):
                    bridge.extract_base(archive, self.state)
            self.assertEqual(list(self.state.iterdir()), [])

    def test_expansion_limit_and_disk_space_fail_before_extraction(self):
        archive = self.archive([(bridge.BASE_NAME + '/proton', 'file', 'fixture')])
        self.pin(archive)
        with mock.patch.object(bridge, 'MAX_EXPANDED', 1):
            with self.assertRaisesRegex(ValueError, 'limit'):
                bridge.extract_base(archive, self.state)
        with mock.patch.object(bridge.shutil, 'disk_usage', return_value=mock.Mock(free=0)):
            with self.assertRaisesRegex(ValueError, 'free space'):
                bridge.extract_base(archive, self.state)
        self.assertEqual(list(self.state.iterdir()), [])

    def test_matching_runner_is_reused_offline_without_base_or_prepare(self):
        (self.state / 'runner').mkdir()
        self.engine.verify_runner.return_value = self.state / 'runner'
        with mock.patch.object(bridge, 'download_archive', side_effect=AssertionError('must stay offline')):
            bridge.install(self.engine, self.state)
        self.engine.prepare.assert_not_called()
        self.engine.atomic_json.assert_called_once()

    def test_matching_local_base_is_used_without_download(self):
        with mock.patch.object(bridge, 'download_archive', side_effect=AssertionError('must stay offline')):
            bridge.install(self.engine, self.state, self.root / 'base')
        self.engine.prepare.assert_called_once()

    def test_unknown_local_base_falls_back_to_verified_download(self):
        self.engine.verify_base.side_effect = [ValueError('wrong base'), None]
        archive = self.archive([(bridge.BASE_NAME + '/proton', 'file', 'fixture')])
        self.pin(archive)
        with mock.patch.object(bridge, 'download_archive', return_value=archive):
            bridge.install(self.engine, self.state, self.root / 'unsupported-base')
        used = self.engine.prepare.call_args.args[0]
        self.assertEqual(used.name, bridge.BASE_NAME)
        self.assertFalse(used.is_relative_to(self.state))
        self.assertFalse(used.exists())  # Temporary base is cleaned up after cloning.

    def test_install_and_uninstall_reject_linked_runner(self):
        (self.state / 'runner').symlink_to(self.root / 'external')
        with self.assertRaisesRegex(ValueError, 'Linked'):
            bridge.install(self.engine, self.state)
        with self.assertRaisesRegex(ValueError, 'Linked'):
            bridge.uninstall(self.engine, self.state, True)

    def test_uninstall_requires_confirmation_ownership_and_idle_runner(self):
        with self.assertRaisesRegex(ValueError, 'confirm-remove-runner'):
            bridge.uninstall(self.engine, self.state)
        self.engine.read_json.return_value = {}
        with self.assertRaisesRegex(ValueError, 'ownership'):
            bridge.uninstall(self.engine, self.state, True)
        self.engine.read_json.return_value = {'schema_version': 1, 'engine_version': bridge.ENGINE_VERSION,
                                              'runner': str(self.state / 'runner')}
        self.engine.runner_busy.return_value = True
        with self.assertRaisesRegex(ValueError, 'Close DOOM'):
            bridge.uninstall(self.engine, self.state, True)

    def test_uninstall_preserves_logs_downloads_and_external_save(self):
        runner = self.state / 'runner'
        runner.mkdir()
        external = self.root / 'save.dat'
        external.write_text('preserve')
        (runner / 'external-save-link').symlink_to(external)
        log = self.state / 'logs/session.log'
        log.parent.mkdir()
        log.write_text('preserve')
        self.engine.read_json.return_value = {'schema_version': 1, 'engine_version': bridge.ENGINE_VERSION,
                                              'runner': str(runner)}
        self.engine.runner_busy.return_value = False
        bridge.uninstall(self.engine, self.state, True)
        self.assertFalse(runner.exists())
        self.assertEqual(external.read_text(), 'preserve')
        self.assertEqual(log.read_text(), 'preserve')

    def test_lock_prevents_simultaneous_standalone_actions(self):
        with bridge.locked(self.state):
            with self.assertRaisesRegex(ValueError, 'Another bridge action'):
                with bridge.locked(self.state):
                    self.fail('second action acquired the lock')


if __name__ == '__main__':
    unittest.main()
