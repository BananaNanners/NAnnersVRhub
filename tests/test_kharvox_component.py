"""Thin-Hub component transport and installation, with tiny synthetic archives."""
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

from vrhub import kharvox_component as component


class Response(io.BytesIO):
    def __init__(self, content, length=None):
        super().__init__(content)
        self.headers = {'Content-Length': str(len(content) if length is None else length)}

    def geturl(self):
        return 'https://release-assets.githubusercontent.com/fixture'


class ComponentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = self.root/'state'
        self.state.mkdir()
        self.marker = self.state/'runner.json'
        self.marker.write_text('preserve existing runner metadata')

    def archive(self, entries=None):
        path = self.root/'component.tar.gz'
        entries = entries or [(component.ROOT+'/payload/lab.py', 'file', 'fixture')]
        with tarfile.open(path, 'w:gz') as tar:
            for name, kind, data in entries:
                info = tarfile.TarInfo(name)
                if kind == 'file':
                    value = data.encode();info.size = len(value);tar.addfile(info, io.BytesIO(value))
                else:
                    info.type = tarfile.SYMTYPE;info.linkname = data;tar.addfile(info)
        return path

    def pin(self, path):
        for patch in (mock.patch.object(component, 'ARCHIVE_SIZE', path.stat().st_size),
                      mock.patch.object(component, 'ARCHIVE_SHA256', component.installer.digest(path))):
            patch.start();self.addCleanup(patch.stop)

    def preserved(self):
        self.assertEqual(self.marker.read_text(), 'preserve existing runner metadata')

    def test_missing_component_is_read_only_and_instructs_install(self):
        with self.assertRaisesRegex(ValueError, 'not installed'):
            component.verified_payload(self.state)
        self.assertEqual(list(self.state.iterdir()), [self.marker])

    def test_offline_import_and_reuse_preserve_runner_metadata(self):
        archive = self.archive();self.pin(archive)
        with mock.patch.object(component.installer, 'load_engine'), \
             mock.patch.object(component, 'download', side_effect=AssertionError('no network')):
            path = component.ensure_payload(self.state, archive)
            self.assertEqual((path/'lab.py').read_text(), 'fixture')
            self.assertEqual(component.ensure_payload(self.state, self.root/'missing'), path)
        self.preserved()

    def test_bad_hash_or_size_cannot_install_a_component(self):
        archive = self.archive();self.pin(archive);archive.write_bytes(archive.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError, 'pinned'):
            component.ensure_payload(self.state, archive)
        self.assertFalse(component.component_root(self.state).exists());self.preserved()

    def test_incomplete_payload_is_not_activated(self):
        archive = self.archive();self.pin(archive)
        with mock.patch.object(component.installer, 'load_engine', side_effect=ValueError('payload changed')):
            with self.assertRaisesRegex(ValueError, 'payload changed'):
                component.ensure_payload(self.state, archive)
        self.assertFalse(component.component_root(self.state).exists())
        self.assertEqual(list((self.state/'components').iterdir()), []);self.preserved()

    def test_modified_existing_component_is_preserved_for_manual_review(self):
        target = component.payload_dir(self.state);target.mkdir(parents=True);(target/'keep').write_text('changed component')
        with mock.patch.object(component.installer, 'load_engine', side_effect=ValueError('changed')), \
             mock.patch.object(component, 'download', side_effect=AssertionError('no overwrite')):
            with self.assertRaisesRegex(ValueError, 'changed'):
                component.ensure_payload(self.state)
        self.assertEqual((target/'keep').read_text(), 'changed component');self.preserved()

    def test_links_and_traversal_are_rejected_before_extraction(self):
        for entry in [('../escape','file','bad'),('/absolute','file','bad'),('other/lab.py','file','bad'),
                      (component.ROOT+'/link','link','../../escape')]:
            archive = self.archive([entry])
            with mock.patch.object(component, 'check_archive'):
                with self.assertRaisesRegex(ValueError, 'Unsafe'):
                    component.extract(archive, self.state)
            self.preserved()
            self.assertFalse((self.root/'escape').exists())

    def test_expansion_and_free_space_limits_precede_extraction(self):
        archive = self.archive();self.pin(archive)
        with mock.patch.object(component, 'MAX_EXPANDED', 1):
            with self.assertRaisesRegex(ValueError, 'limit'):
                component.extract(archive, self.state)
        with mock.patch.object(component.shutil, 'disk_usage', return_value=mock.Mock(free=0)):
            with self.assertRaisesRegex(ValueError, 'space'):
                component.extract(archive, self.state)
        self.assertFalse((self.state/component.ROOT).exists());self.preserved()

    def test_component_and_cache_symlinks_are_rejected(self):
        (self.state/'components').symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'linked'):
            component.ensure_payload(self.state, self.archive())
        self.preserved()

    def test_component_lock_prevents_two_installers(self):
        with component.component_lock(self.state):
            with self.assertRaisesRegex(ValueError, 'already running'):
                with component.component_lock(self.state):
                    self.fail('second component installer acquired the lock')

    def test_downloader_verifies_and_reuses_cached_archive(self):
        archive = self.archive();self.pin(archive)
        opener = mock.Mock();opener.open.return_value = Response(archive.read_bytes())
        with mock.patch.object(component.urllib.request, 'build_opener', return_value=opener):
            path = component.download(self.state)
            self.assertEqual(path.read_bytes(), archive.read_bytes())
            self.assertEqual(component.download(self.state), path);opener.open.assert_called_once()
        self.preserved()

    def test_truncated_and_oversized_downloads_clean_partial_files(self):
        archive = self.archive();self.pin(archive)
        for body in (archive.read_bytes()[:-1], archive.read_bytes()+b'over'):
            opener = mock.Mock();opener.open.return_value = Response(body, archive.stat().st_size)
            with mock.patch.object(component.urllib.request, 'build_opener', return_value=opener):
                with self.assertRaises(ValueError):component.download(self.state)
            self.assertEqual(list((self.state/'downloads').iterdir()), [])
        self.preserved()

    def test_http_failure_cleans_partial_files(self):
        opener = mock.Mock();opener.open.side_effect = OSError('offline')
        with mock.patch.object(component.urllib.request, 'build_opener', return_value=opener):
            with self.assertRaisesRegex(OSError, 'offline'):component.download(self.state)
        self.assertEqual(list((self.state/'downloads').iterdir()), []);self.preserved()

    def test_non_install_action_never_downloads_missing_component(self):
        with mock.patch.object(component, 'download', side_effect=AssertionError('must be explicit')):
            self.assertEqual(component.main(['probe','--state',str(self.state)]), 1)
        self.preserved()

    def test_cli_forwards_verified_payload_and_shared_state(self):
        with mock.patch.object(component, 'ensure_payload', return_value=self.root/'payload') as install, \
             mock.patch.object(component.installer, 'main', return_value=0) as launch:
            self.assertEqual(component.main(['install','--state',str(self.state),'--bridge-archive',str(self.root/'source.tar.gz')]),0)
            install.assert_called_once_with(self.state,self.root/'source.tar.gz')
            self.assertEqual(launch.call_args.args[0],['install','--payload',str(self.root/'payload'),'--state',str(self.state)])
        self.preserved()


if __name__ == '__main__':
    unittest.main()
