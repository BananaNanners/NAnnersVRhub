# SPDX-License-Identifier: GPL-3.0-only
"""Read-only Nexus credential fallback for isolated development previews."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vrhub import updates


class ReadonlyNexusPreviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "original-source"
        self.preview = self.root / "preview-key"
        self.source.write_text("fixture-secret-from-existing-account\n")
        self.source.chmod(0o600)
        self.environ = mock.patch.dict(
            os.environ, {
                "VRHUB_NEXUS_READONLY_KEY_FILE": str(self.source),
                "VRHUB_NEXUS_KEY_FILE": str(self.preview),
                "NEXUS_API_KEY": "",
            })
        self.environ.start()
        self.addCleanup(self.environ.stop)

    def test_private_readonly_source_works_without_copy(self):
        before = self.source.read_bytes()
        self.assertEqual(updates.get_key(), "fixture-secret-from-existing-account")
        self.assertFalse(self.preview.exists())
        self.assertEqual(before, self.source.read_bytes())

    def test_preview_key_writes_and_deletes_only_isolated_file(self):
        original = self.source.read_bytes()
        updates.set_key("fixture-local-override")
        self.assertEqual(updates.get_key(), "fixture-local-override")
        self.assertEqual(self.preview.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.source.read_bytes(), original)
        updates.clear_key()
        self.assertFalse(self.preview.exists())
        self.assertEqual(updates.get_key(), "fixture-secret-from-existing-account")
        self.assertEqual(self.source.read_bytes(), original)

    def test_readonly_source_cannot_be_writable_key_target(self):
        original = self.source.read_bytes()
        os.environ["VRHUB_NEXUS_KEY_FILE"] = str(self.source)
        with self.assertRaisesRegex(ValueError, "read-only"):
            updates.set_key("not-authorized")
        with self.assertRaisesRegex(ValueError, "read-only"):
            updates.clear_key()
        self.assertEqual(self.source.read_bytes(), original)

    def test_symlinked_writable_key_rejected(self):
        self.preview.symlink_to(self.source)
        with self.assertRaisesRegex(ValueError, "read-only"):
            updates.set_key("not-authorized")
        with self.assertRaisesRegex(ValueError, "read-only"):
            updates.clear_key()
        self.assertEqual(self.source.read_text().strip(),
                         "fixture-secret-from-existing-account")

    def test_symlink_readonly_source_fails_closed(self):
        link = self.root / "key-symlink"
        link.symlink_to(self.source)
        os.environ["VRHUB_NEXUS_READONLY_KEY_FILE"] = str(link)
        self.assertIsNone(updates.get_key())

    def test_insecure_or_foreign_or_missing_sources_fail_closed(self):
        self.source.chmod(0o644)
        self.assertIsNone(updates.get_key())
        self.source.chmod(0o600)
        with mock.patch("vrhub.updates.os.geteuid", return_value=-1):
            self.assertIsNone(updates.get_key())
        os.environ["VRHUB_NEXUS_READONLY_KEY_FILE"] = str(self.root / "not-present")
        self.assertIsNone(updates.get_key())

    def test_empty_and_oversized_or_invalid_encoding_sources_fail_closed(self):
        self.source.write_bytes(b"")
        self.assertIsNone(updates.get_key())
        self.source.write_bytes(b"X" * 4097)
        self.assertIsNone(updates.get_key())
        self.source.write_bytes(b"\xff")
        self.assertIsNone(updates.get_key())

    def test_existing_environment_and_preview_keys_have_priority(self):
        os.environ["NEXUS_API_KEY"] = "fixture-env-override"
        self.assertEqual(updates.get_key(), "fixture-env-override")
        os.environ["NEXUS_API_KEY"] = ""
        updates.set_key("fixture-preview-override")
        self.assertEqual(updates.get_key(), "fixture-preview-override")
        self.source.unlink()
        self.assertEqual(updates.get_key(), "fixture-preview-override")

    def test_preview_suppresses_state_writing_name_cache_refresh(self):
        from vrhub import hub
        from tests.manual_launcher_dev5d3f_preview import suppress_preview_name_cache_updates
        with mock.patch.object(hub, "refresh_component_names") as name_cache:
            suppress_preview_name_cache_updates()
            self.assertEqual(hub.refresh_component_names({"id": "fixture"}), 0)
            name_cache.assert_not_called()

    def test_updates_can_use_fallback_for_readonly_lookup(self):
        observed = []

        def fake_fetch(game, mod_id, key):
            observed.append((game, mod_id, key))
            return {"name": "Fixture mod", "version": "1.2.3"}

        recipe = {"id": "fixture", "updates": [
            {"name": "Fixture mod", "nexus_game": "fixturegame", "nexus_mod": 16}]}
        rows = updates.check_recipe(recipe, {}, nexus_fetch=fake_fetch)
        self.assertEqual(len(rows), 1)
        self.assertNotEqual(rows[0]["status"], "no_key")
        self.assertEqual(observed[0], ("fixturegame", 16,
                                       "fixture-secret-from-existing-account"))
        self.assertFalse(self.preview.exists())
