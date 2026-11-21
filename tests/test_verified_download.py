# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5B2 strictly approved direct download: never uses a live network here."""
import hashlib
import io
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from vrhub import hub, download_planner as planner
from vrhub import verified_download as d


class DummyResponse(io.BytesIO):
    def __init__(self, payload, headers=None):
        super().__init__(payload)
        self.headers = headers or {"Content-Length": str(len(payload))}
        self.status = 200


class FakeOpener:
    def __init__(self, results):
        self.results = list(results)
        self.requests = []

    def open(self, request, timeout=15):
        self.requests.append(request.full_url)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class VerifiedDownloadTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.folder = self.root / "archives"
        self.folder.mkdir()
        self.payload = b"pinned binary archive fixture" * 32
        self.expected = hashlib.sha256(self.payload).hexdigest()
        self.recipe = {
            "id": "unit-game", "method": "bepinex",
            "packages": [{
                "id": "loader", "name": "Pinned loader",
                "sha256": self.expected,
                "page": "https://github.com/example/project/releases/tag/v1.2.3",
            }]
        }
        self.direct = (
            "https://github.com/example/project/releases/download/"
            "v1.2.3/Pinned-loader.zip")
        self.component = planner.plan_components(self.recipe)[0]

    def authorize(self, url=None, recipe=None, component=None):
        return d.create_authorization(
            recipe or self.recipe, component or self.component,
            url or self.direct, self.folder)

    def test_real_game_packages_are_pinned_or_explicitly_manual(self):
        recipes = hub.load_recipes()
        pinned = []
        unpinned = []
        for rid, recipe in recipes.items():
            for comp in planner.plan_components(recipe):
                eligible, reason = d.source_support(recipe, comp)
                (pinned if eligible else unpinned).append((rid, comp["id"]))
                self.assertIsInstance(reason, str)
        self.assertIn(("valheim", "vhvr"), pinned)
        self.assertIn(("valheim", "loader"), pinned)
        self.assertIn(("subnautica", "submersedvr"), pinned)
        self.assertIn(("subnautica", "loader"), pinned)
        self.assertIn(("cyberpunk-2077", "107"), unpinned)
        self.assertIn(("elden-ring", "ervr"), unpinned)

    def test_authorization_checks_exact_repository_and_tag(self):
        auth = self.authorize()
        self.assertEqual(auth.game_id, "unit-game")
        self.assertEqual(auth.destination_name, "Pinned-loader.zip")
        self.assertEqual(auth.expected_sha256, self.expected)
        self.assertEqual(auth.destination_folder, self.folder)
        self.assertEqual(auth.origin_page, self.component["url"])

    def test_unrelated_repository_tag_and_untrusted_host_rejected(self):
        for value in (
            "https://github.com/other/project/releases/download/v1.2.3/Pinned-loader.zip",
            "https://github.com/example/project/releases/download/v99/Pinned-loader.zip",
            "https://github.com/example/other/releases/download/v1.2.3/Pinned-loader.zip",
            "https://evil.example/releases/download/file.zip",
            "http://github.com/example/project/releases/download/v1.2.3/Pinned-loader.zip",
            "https://user:password@github.com/example/project/releases/download/v1.2.3/Pinned-loader.zip",
            "https://github.com:8443/example/project/releases/download/v1.2.3/Pinned-loader.zip",
            "file:///etc/passwd",
            "https://127.0.0.1/anything",
            "https://github.com/example/project/releases/tag/v1.2.3",
        ):
            with self.subTest(url=value):
                with self.assertRaises(d.DownloadRejected):
                    self.authorize(value)
        self.assertFalse(list(self.folder.iterdir()))

    def test_no_path_traversal_or_unknown_extensions(self):
        for name in ("unsafe.exe", "%2e%2e.zip", "archive.zip%2Fsecret.zip",
                     "not an archive.txt"):
            with self.subTest(name=name):
                url = ("https://github.com/example/project/releases/download/"
                       "v1.2.3/" + name)
                with self.assertRaises(d.DownloadRejected):
                    self.authorize(url)

    def test_nexus_manual_only_even_if_hash_pinned(self):
        recipe = {"id": "elden-ring", "method": "ervr",
                  "packages": [{"id": "ervr", "name": "ERVR",
                                "sha256": self.expected,
                                "page": "https://www.nexusmods.com/eldenring/mods/10711"}]}
        component = planner.plan_components(recipe)[0]
        self.assertFalse(d.source_support(recipe, component)[0])
        with self.assertRaisesRegex(d.DownloadRejected, "manual"):
            self.authorize(recipe=recipe, component=component)

    def test_thunderstore_package_requires_exact_author_and_version(self):
        recipe = {"id": "unit-game", "method": "bepinex",
                  "packages": [{
                      "id": "loader", "name": "Pinned loader",
                      "sha256": self.expected,
                      "page": "https://thunderstore.io/c/valheim/p/denikson/BepInExPack_Valheim/v/5.4.2351/"
                  }]}
        component = planner.plan_components(recipe)[0]
        direct = "https://thunderstore.io/package/download/denikson/BepInExPack_Valheim/5.4.2351/"
        auth = self.authorize(direct, recipe, component)
        self.assertEqual(auth.destination_name, "BepInExPack_Valheim-5.4.2351.zip")
        with self.assertRaises(d.DownloadRejected):
            self.authorize(direct.replace("5.4.2351", "5.4.2352"), recipe, component)

    def test_verified_new_file_created_only_on_matching_hash(self):
        auth = self.authorize()
        opener = FakeOpener([DummyResponse(self.payload)])
        events = []
        result = d.download(
            auth, progress=lambda current,total: events.append((current,total)),
            opener_factory=lambda: opener)
        self.assertEqual(result.file.read_bytes(), self.payload)
        self.assertEqual(result.sha256, self.expected)
        self.assertFalse(result.reused_existing)
        self.assertEqual(result.file.name, "Pinned-loader.zip")
        self.assertEqual(result.file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(events[-1][0], len(self.payload))
        self.assertEqual(list(self.folder.iterdir()), [result.file])
        self.assertEqual(opener.requests, [self.direct])

    def test_existing_matching_file_reused_without_network(self):
        auth = self.authorize()
        existing = self.folder / auth.destination_name
        existing.write_bytes(self.payload)
        opener = FakeOpener([])
        result = d.download(auth, opener_factory=lambda: opener)
        self.assertTrue(result.reused_existing)
        self.assertEqual(existing.read_bytes(), self.payload)
        self.assertEqual(opener.requests, [])

    def test_renamed_matching_archive_reused_without_any_network(self):
        authority = self.authorize()
        existing = self.folder / "Renamed-user-backup.zip"
        existing.write_bytes(self.payload)
        opener = FakeOpener([])
        result = d.download(authority, opener_factory=lambda: opener)
        self.assertEqual(result.file, existing)
        self.assertTrue(result.reused_existing)
        self.assertEqual(opener.requests, [])
        self.assertEqual(list(self.folder.iterdir()), [existing])
        self.assertFalse((self.folder / authority.destination_name).exists())

    def test_symlink_archive_not_used_as_verified_reusable_package(self):
        authority = self.authorize()
        external = self.root / "outside.zip"
        external.write_bytes(self.payload)
        link = self.folder / "shortcut.zip"
        link.symlink_to(external)
        result = d.download(
            authority,
            opener_factory=lambda: FakeOpener([DummyResponse(self.payload)]))
        self.assertEqual(result.file, self.folder / authority.destination_name)
        self.assertFalse(result.reused_existing)
        self.assertEqual(link.resolve(), external)
        self.assertEqual(external.read_bytes(), self.payload)

    def test_existing_bad_file_never_overwritten(self):
        auth = self.authorize()
        existing = self.folder / auth.destination_name
        existing.write_bytes(b"important existing file")
        before = existing.read_bytes()
        with self.assertRaisesRegex(d.DownloadRejected, "NOT overwritten"):
            d.download(auth, opener_factory=lambda: FakeOpener([]))
        self.assertEqual(existing.read_bytes(), before)
        self.assertEqual(list(self.folder.iterdir()), [existing])

    def test_sha_mismatch_discards_partial(self):
        auth = self.authorize()
        with self.assertRaisesRegex(d.DownloadRejected, "did not match"):
            d.download(auth, opener_factory=lambda: FakeOpener([DummyResponse(b"wrong bytes")]))
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_cancel_before_start_and_during_stream(self):
        auth = self.authorize()
        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaises(d.DownloadCancelled):
            d.download(auth, cancel_event=cancelled, opener_factory=lambda: FakeOpener([]))
        cancelled.clear()
        def cancel_progress(current,total):
            cancelled.set()
        payload = self.payload * 8192
        with self.assertRaises(d.DownloadCancelled):
            d.download(auth, cancel_event=cancelled,
                       progress=cancel_progress,
                       opener_factory=lambda: FakeOpener([DummyResponse(payload)]))
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_https_only_known_cdn_redirect_is_accepted(self):
        auth = self.authorize()
        redirect = urllib.error.HTTPError(
            self.direct, 302, "Found",
            {"Location": "https://release-assets.githubusercontent.com/some-opaque-token"},
            None)
        opener = FakeOpener([redirect, DummyResponse(self.payload)])
        result = d.download(auth, opener_factory=lambda: opener)
        self.assertEqual(result.file.read_bytes(), self.payload)
        self.assertEqual(len(opener.requests), 2)

    def test_cross_provider_redirect_is_rejected(self):
        auth = self.authorize()
        redirect = urllib.error.HTTPError(
            self.direct, 302, "Found",
            {"Location": "https://example.com/evil.zip"},
            None)
        with self.assertRaisesRegex(d.DownloadRejected, "outside"):
            d.download(auth, opener_factory=lambda: FakeOpener([redirect]))
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_redirect_to_local_network_is_rejected(self):
        auth = self.authorize()
        for value in ("https://127.0.0.1/archive.zip", "http://localhost/archive.zip",
                      "https://release-assets.githubusercontent.com:1234/asset"):
            redirect = urllib.error.HTTPError(
                self.direct, 302, "Found", {"Location": value}, None)
            with self.subTest(redirect=value):
                with self.assertRaises(d.DownloadRejected):
                    d.download(auth, opener_factory=lambda: FakeOpener([redirect]))
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_large_content_length_rejected_before_writing(self):
        auth = self.authorize()
        response = DummyResponse(b"fake", headers={
            "Content-Length": str(d.MAX_BYTES + 1)})
        with self.assertRaisesRegex(d.DownloadRejected, "exceeds"):
            d.download(auth, opener_factory=lambda: FakeOpener([response]))
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_http_403_stays_manual_no_partial_file(self):
        auth = self.authorize()
        error = urllib.error.HTTPError(
            self.direct, 403, "Forbidden", {}, None)
        with self.assertRaisesRegex(d.DownloadRejected, "authorization"):
            d.download(auth, opener_factory=lambda: FakeOpener([error]))
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_unverified_bad_name_never_touches_folder(self):
        with self.assertRaises(d.DownloadRejected):
            self.authorize(self.direct.replace("Pinned-loader.zip", "../evil.zip"))
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_original_recipe_id_and_digest_must_match(self):
        component = dict(self.component)
        component["name"] = "unrelated"
        with self.assertRaises(d.DownloadRejected):
            self.authorize(component=component)
        altered = dict(self.recipe)
        altered["packages"] = [{**self.recipe["packages"][0], "sha256": "not-a-hash"}]
        with self.assertRaises(d.DownloadRejected):
            self.authorize(recipe=altered)

if __name__ == "__main__":
    unittest.main()
