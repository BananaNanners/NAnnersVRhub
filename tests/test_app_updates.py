import copy
import hashlib
import io
import json
import os
import stat
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from unittest import mock

from vrhub import __version__, app_updates as updates, self_install

REPO = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Response(io.BytesIO):
    status = 200

    def __init__(self, data, url, length=None):
        super().__init__(data)
        self.url = url
        self.headers = {"Content-Length": str(len(data) if length is None else length)}

    def geturl(self):
        return self.url


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.state = self.base / "state/state.json"
        self.state.parent.mkdir()
        self.state.write_bytes(b'{"game": "preserve"}\n')
        self.history = self.state.parent / "live-tests.json"
        self.history.write_bytes(b'{"test": "preserve"}\n')
        self.env = mock.patch.dict(os.environ, {"VRHUB_STATE": str(self.state), "XDG_CACHE_HOME": str(self.base / "cache"),
                                                "_NANNERSVRHUB_ROOT": ""})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.version = "0.5.3"
        self.name = f"NAnnersVRhub-{self.version}-source.zip"
        version, files = self_install._source_files(REPO)
        self.files = files
        for name in ("vrhub/__init__.py", "pyproject.toml"):
            self.files[name] = files[name].replace(version.encode(), self.version.encode())
        self.make_release()

    def tearDown(self):
        self.assertEqual(self.state.read_bytes(), b'{"game": "preserve"}\n')
        self.assertEqual(self.history.read_bytes(), b'{"test": "preserve"}\n')

    def make_release(self, entries=None):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            if entries is None:
                for name, data in self.files.items():
                    archive.writestr(f"NAnnersVRhub-{self.version}/{name}", data)
            else:
                for name, data in entries:
                    archive.writestr(name, data)
        self.archive = stream.getvalue()
        self.sums = f"{sha(self.archive)}  {self.name}\n".encode()
        self.metadata = {"id": 12, "tag_name": "v" + self.version, "draft": False, "prerelease": False,
                         "html_url": updates.RELEASES + "/tag/v" + self.version,
                         "published_at": "2026-10-19T13:00:00Z", "body": "Release notes <script>plain text</script>", "assets": []}
        for name, data in ((self.name, self.archive), ("SHA256SUMS", self.sums)):
            self.metadata["assets"].append({"name": name, "size": len(data), "state": "uploaded", "digest": "sha256:" + sha(data),
                "browser_download_url": f"https://github.com/{updates.REPO}/releases/download/v{self.version}/{name}"})

    def response(self, url):
        if url == updates.API:
            return Response(json.dumps(self.metadata).encode(), url)
        if url.endswith("/SHA256SUMS"):
            return Response(self.sums, url)
        if url.endswith("/" + self.name):
            return Response(self.archive, url)
        self.fail("Unexpected network request: " + url)

    def fetch(self):
        with mock.patch.object(updates, "_open", side_effect=self.response):
            return updates.check(force=True)["release"]

    def download(self):
        release = self.fetch()
        with mock.patch.object(updates, "_open", side_effect=self.response):
            return updates.download(release)

    def test_versions_stable_dev_rc_and_multi_digit(self):
        values = ["0.5.2-dev1", "0.5.2-dev10", "0.5.2-rc1", "0.5.2", "0.5.10", "0.6.0", "1.0.0"]
        self.assertEqual(sorted(reversed(values), key=updates.version_key), values)
        self.assertFalse(updates.newer({"version": "0.5.1"}))
        for invalid in ("v0.5.2", "0.05.2", "1.2", "1.2.3+local", "1.2.3-dev0"):
            with self.subTest(invalid=invalid), self.assertRaises(updates.UpdateError):
                updates.version_key(invalid)

    def test_reject_unexpected_release_and_assets(self):
        mutations = [lambda d: d.update(draft=True), lambda d: d.update(prerelease=True),
                     lambda d: d.update(tag_name="v0.5.3-rc1"), lambda d: d.update(html_url="https://github.com/other/repo"),
                     lambda d: d.update(assets=[]), lambda d: d["assets"].append(d["assets"][0]),
                     lambda d: d["assets"][0].update(size=updates.MAX_ARCHIVE + 1),
                     lambda d: d["assets"][0].update(browser_download_url="https://evil.example/update.zip"),
                     lambda d: d["assets"][0].update(digest="sha256:bad"),
                     lambda d: d.update(published_at="2026-01-01T00:00:00")]
        for mutation in mutations:
            data = copy.deepcopy(self.metadata)
            mutation(data)
            with self.subTest(data=data), self.assertRaises(updates.UpdateError):
                updates.parse_release(data)

    def test_https_redirect_constraints(self):
        for url in ("http://github.com/x", "https://evil.example/x", "https://github.com.evil.example/x",
                    "https://user:secret@github.com/x", "https://github.com:444/x"):
            with self.subTest(url=url), self.assertRaises(updates.UpdateError):
                updates._Redirect().redirect_request(urllib.request.Request(updates.API), None, 302, "Found", {}, url)

    def test_rate_limit_and_offline_errors(self):
        for error in (urllib.error.HTTPError(updates.API, 403, "limited", {}, None),
                      urllib.error.HTTPError(updates.API, 429, "limited", {}, None), urllib.error.URLError("offline")):
            with mock.patch("urllib.request.build_opener") as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaises(updates.UpdateError):
                    updates._open(updates.API)

    def test_daily_cache_and_manual_refresh(self):
        self.fetch()
        with mock.patch.object(updates, "_open", side_effect=self.response) as network:
            self.assertTrue(updates.check()["cached"])
            network.assert_not_called()
            self.assertFalse(updates.check(force=True)["cached"])
            self.assertEqual(network.call_count, 1)

    def test_failed_check_preserves_success_and_preferences(self):
        self.fetch()
        updates.save_settings(auto_download=True)
        before = updates.read_settings()
        with mock.patch.object(updates, "_open", side_effect=updates.UpdateError("offline")):
            with self.assertRaises(updates.UpdateError):
                updates.check(force=True)
        after = updates.read_settings()
        for key in ("release", "checked_at", "auto_download", "check_on_startup"):
            self.assertEqual(after[key], before[key])

    def test_automatic_failed_check_waits_for_manual_retry(self):
        with mock.patch.object(updates, "_open", side_effect=updates.UpdateError("offline")) as network:
            with self.assertRaisesRegex(updates.UpdateError, "offline"):
                updates.check()
            with self.assertRaisesRegex(updates.UpdateError, "already attempted"):
                updates.check()
            self.assertEqual(network.call_count, 1)
        self.fetch()  # A manual check still works immediately.

    def test_corrupt_preferences_are_preserved(self):
        updates.settings_path().write_text("not JSON")
        with self.assertRaisesRegex(updates.UpdateError, "preserved"):
            updates.save_settings(auto_download=True)
        self.assertEqual(updates.settings_path().read_text(), "not JSON")

    def test_download_verified_and_recovered_without_execution(self):
        self.files["vrhub/__init__.py"] += b'\nraise RuntimeError("must never execute during download")\n'
        self.make_release()
        with mock.patch.object(self_install, "_probe", side_effect=AssertionError("must not execute")):
            bundle = self.download()
            recovered = updates.saved_download()
        self.assertEqual(bundle, recovered)
        self.assertEqual(Path(bundle["source"]).name, "NAnnersVRhub-0.5.3")
        self.assertEqual(Path(bundle["directory"]).stat().st_mode & 0o777, 0o700)

    def test_checksum_mismatch_discards_download(self):
        release = self.fetch()
        self.archive = bytes([self.archive[0] ^ 1]) + self.archive[1:]
        with mock.patch.object(updates, "_open", side_effect=self.response), self.assertRaisesRegex(updates.UpdateError, "digest"):
            updates.download(release)
        self.assertEqual(list(updates.cache_root().iterdir()), [])

    def test_checksum_file_is_required_even_without_api_digest(self):
        self.sums = ("0" * 64 + "  " + self.name + "\n").encode()
        self.metadata["assets"][1].update(digest=None, size=len(self.sums))
        self.metadata["assets"][0]["digest"] = None
        release = self.fetch()
        with mock.patch.object(updates, "_open", side_effect=self.response), self.assertRaisesRegex(updates.UpdateError, "checksum"):
            updates.download(release)
        self.assertEqual(list(updates.cache_root().iterdir()), [])

    def test_duplicate_checksums_rejected(self):
        with self.assertRaises(updates.UpdateError):
            updates._checksum(self.sums * 2, self.name)

    def test_truncated_oversized_and_cancelled_downloads(self):
        release = self.fetch()
        for content in (self.archive[:-1], self.archive + b"extra"):
            def response(url):
                return Response(content, url, len(self.archive)) if url.endswith(self.name) else self.response(url)
            with mock.patch.object(updates, "_open", side_effect=response), self.assertRaises(updates.UpdateError):
                updates.download(release)
            self.assertEqual(list(updates.cache_root().iterdir()), [])
        cancel = threading.Event()
        with mock.patch.object(updates, "_open", side_effect=self.response):
            with self.assertRaises(updates.Cancelled):
                updates.download(release, cancel=cancel, progress=lambda *_: cancel.set())
        self.assertEqual(list(updates.cache_root().iterdir()), [])

    def test_unsafe_zip_paths_and_symlinks(self):
        prefix = "NAnnersVRhub-0.5.3/"
        symlink = zipfile.ZipInfo(prefix + "link")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        for name in (prefix + "../escape", "/absolute", prefix + "a\\b", prefix + "a/./b", prefix + "a//b", symlink):
            self.make_release([(name, b"target")])
            with self.subTest(name=name), self.assertRaises(updates.UpdateError):
                self.download()
            self.assertEqual(list(updates.cache_root().iterdir()), [])
        self.assertFalse((self.base / "escape").exists())

    def test_zip_count_and_expanded_size_limits(self):
        for constant, limit in (("MAX_ENTRIES", 1), ("MAX_EXPANDED", 1), ("MAX_FILE", 1)):
            with mock.patch.object(updates, constant, limit), self.assertRaises(updates.UpdateError):
                self.download()

    def test_version_mismatch_rejected_without_execution(self):
        self.files["vrhub/__init__.py"] = self.files["vrhub/__init__.py"].replace(b"0.5.3", b"0.5.4")
        self.files["pyproject.toml"] = self.files["pyproject.toml"].replace(b"0.5.3", b"0.5.4")
        self.make_release()
        with self.assertRaisesRegex(updates.UpdateError, "version"):
            self.download()

    def test_tampered_extraction_archive_and_extra_file_rejected(self):
        bundle = self.download()
        source = Path(bundle["source"])
        target = source / "vrhub/__init__.py"
        original = target.read_bytes()
        target.write_bytes(original + b"# changed")
        with self.assertRaises(updates.UpdateError):
            updates.verify_bundle(Path(bundle["directory"]))
        target.write_bytes(original)
        extra = source / "vrhub/extra.py"
        extra.write_text("bad")
        with self.assertRaises(updates.UpdateError):
            updates.saved_download()
        extra.unlink()
        archive = Path(bundle["directory"]) / self.name
        archive.write_bytes(b"x" * len(self.archive))
        with self.assertRaises(updates.UpdateError):
            updates.saved_download()

    def test_source_launch_cannot_install_and_older_release_cannot_install(self):
        bundle = self.download()
        with self.assertRaisesRegex(updates.UpdateError, "install.py"):
            updates.install_bundle(Path(bundle["directory"]))
        with mock.patch.object(updates, "newer", return_value=False):
            with self.assertRaisesRegex(updates.UpdateError, "newer stable"):
                updates.install_bundle(Path(bundle["directory"]))

    def test_verified_bundle_enters_installer_with_current_version_lease(self):
        bundle = self.download()
        with mock.patch.object(updates, "managed_context", return_value=(self.base / "managed", "current-id")), \
                mock.patch.object(self_install, "install", return_value={"status": "INSTALLED"}) as install:
            updates.install_bundle(Path(bundle["directory"]))
        install.assert_called_once_with(Path(bundle["source"]), self.base / "managed", expected_current="current-id")


if __name__ == "__main__":
    unittest.main()
