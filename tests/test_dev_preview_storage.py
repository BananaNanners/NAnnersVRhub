# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev preview carry-forward tests; ALL files here are disposable temp data."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vrhub import dev_preview_storage as store, archive_scans, download_planner


def snapshot(rid, folder, scanned_at, count):
    return {
        "folder": str(folder),
        "scanned_at": scanned_at,
        "plan": {
            "game_id": rid, "folder": str(folder), "scanned": count,
            "rows": [{"status": "Not found locally", "file": ""}],
            "verified": 0, "missing": 1,
        },
        "files": {},
    }


class SharedPreviewPersistenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.cache = self.home / ".cache"
        self.cache.mkdir()
        self.prod = self.home / ".local/share/vrhub"
        self.prod.mkdir(parents=True)
        (self.prod / "state.json").write_text('{"production": "preserve"}')
        self.production_sha = (self.prod / "state.json").read_bytes()

        self.default = self.home / "all-archives"
        self.custom = self.home / "cyberpunk-archives"
        self.default.mkdir()
        self.custom.mkdir()
        self.sources = []
        for name in ("nannersvrhub-055-dev5b-state-20261120",
                     "nannersvrhub-055-dev5b2-state-20261120",
                     "nannersvrhub-055-dev5c-state-20261120"):
            directory = self.cache / name
            directory.mkdir()
            (directory / "state.json").write_text(
                json.dumps({"preview": name}))
            self.sources.append(directory)
        self.b1, self.b2, self.c = self.sources
        (self.b1 / "download-folders.json").write_text(json.dumps({
            "schema": 1, "global": None,
            "games": {"cyberpunk-2077": str(self.custom)},
        }))
        (self.b2 / "table-column-layouts.json").write_text(json.dumps({
            "schema": 1, "tables": {"game-library": [310, 130, 170, 90, 140]}
        }))
        self.initial_fixtures = {
            self.b1: {
                "cyberpunk-2077": snapshot(
                    "cyberpunk-2077", self.custom,
                    "2026-11-20T23:15:00+00:00", 8),
                "skyrim-vr-mgo": snapshot(
                    "skyrim-vr-mgo", self.default,
                    "2026-11-20T23:12:00+00:00", 28),
            },
            self.b2: {
                "cyberpunk-2077": snapshot(
                    "cyberpunk-2077", self.default,
                    "2026-11-21T00:30:00+00:00", 28),
                "skyrim-vr-mgo": snapshot(
                    "skyrim-vr-mgo", self.default,
                    "2026-11-21T00:35:00+00:00", 28),
                "fatekeeper": snapshot(
                    "fatekeeper", self.default,
                    "2026-11-21T00:36:00+00:00", 28),
                "hogwarts-legacy": snapshot(
                    "hogwarts-legacy", self.default,
                    "2026-11-21T00:37:00+00:00", 28),
                "ready-or-not": snapshot(
                    "ready-or-not", self.default,
                    "2026-11-21T00:38:00+00:00", 28),
            },
            self.c: {
                "cyberpunk-2077": snapshot(
                    "cyberpunk-2077", self.default,
                    "2026-11-21T02:00:00+00:00", 28),
                "valheim": snapshot(
                    "valheim", self.default,
                    "2026-11-21T01:55:00+00:00", 28),
                "subnautica": snapshot(
                    "subnautica", self.default,
                    "2026-11-21T01:55:00+00:00", 28),
                "elden-ring": snapshot(
                    "elden-ring", self.default,
                    "2026-11-21T02:05:00+00:00", 28),
                "doom-2016-gog": snapshot(
                    "doom-2016-gog", self.default,
                    "2026-11-21T02:06:00+00:00", 28),
                "fatekeeper": snapshot(
                    "fatekeeper", self.default,
                    "2026-11-21T02:07:00+00:00", 28),
            },
        }
        for directory, games in self.initial_fixtures.items():
            (directory / "archive-scan-snapshots.json").write_text(
                json.dumps({"schema": 1, "games": games}))
        patch = mock.patch.object(download_planner, "default_library",
                                  return_value=self.default)
        patch.start()
        self.addCleanup(patch.stop)

    def prepare(self):
        return store.prepare_shared_preview(
            self.home, previous_state=self.c / "state.json",
            source_roots=self.sources)

    def test_merges_nine_games_across_three_development_previews(self):
        report = self.prepare()
        self.assertEqual(report["count"], 9)
        self.assertTrue(report["imported"])
        self.assertEqual(report["source_count"], 3)
        self.assertEqual(len(report["scans"]), 9)
        for name in ("cyberpunk-2077", "doom-2016-gog", "elden-ring",
                     "fatekeeper", "hogwarts-legacy", "ready-or-not",
                     "skyrim-vr-mgo", "subnautica", "valheim"):
            self.assertIn(name, report["scans"])
        self.assertEqual((report["root"] / "state.json").read_text(),
                         (self.c / "state.json").read_text())
        self.assertEqual((self.prod / "state.json").read_bytes(),
                         self.production_sha)

    def test_latest_game_snapshot_chosen_when_effective_folder_matches(self):
        report = self.prepare()
        self.assertEqual(report["scans"]["fatekeeper"]["scanned_at"],
                         "2026-11-21T02:07:00+00:00")
        self.assertEqual(report["scans"]["skyrim-vr-mgo"]["scanned_at"],
                         "2026-11-21T00:35:00+00:00")

    def test_explicit_game_folder_override_and_its_scan_both_survive(self):
        report = self.prepare()
        folder = report["root"] / "download-folders.json"
        preferences = json.loads(folder.read_text())
        self.assertEqual(preferences["games"]["cyberpunk-2077"],
                         str(self.custom))
        self.assertEqual(report["scans"]["cyberpunk-2077"]["folder"],
                         str(self.custom))
        self.assertEqual(report["scans"]["cyberpunk-2077"]["plan"]["scanned"], 8)
        with mock.patch.object(download_planner, "preferences_file",
                               return_value=folder):
            current, source = download_planner.folder_for({"id": "cyberpunk-2077"})
            self.assertEqual(str(current), str(self.custom))
            self.assertEqual(source, "Per-game override")

    def test_preserves_spreadsheet_columns_without_reinitializing(self):
        report = self.prepare()
        data = json.loads((report["root"] /
                           "table-column-layouts.json").read_text())
        self.assertEqual(data["tables"]["game-library"],
                         [310, 130, 170, 90, 140])

    def test_existing_multifolder_history_is_read_without_restore(self):
        self.prepare()
        target=store.shared_directory(self.home)/"archive-scan-snapshots.json"
        old=json.loads(target.read_text())
        upgraded={"schema":2, "games":{rid:[rec] for rid,rec in old["games"].items()}}
        target.write_text(json.dumps(upgraded))
        before=target.read_bytes()
        result=self.prepare()
        self.assertEqual(result["count"], 9)
        self.assertEqual(target.read_bytes(),before)
        self.assertFalse(result["imported"])

    def test_repeat_boot_does_not_replace_saved_scans_or_timestamps(self):
        first = self.prepare()
        file = first["root"] / "archive-scan-snapshots.json"
        before = file.read_bytes()
        stat = file.stat()
        later = self.prepare()
        self.assertFalse(later["imported"])
        self.assertEqual(file.read_bytes(), before)
        self.assertEqual(file.stat().st_mtime_ns, stat.st_mtime_ns)

    def test_fresh_scan_saved_in_shared_store_survives_future_boot(self):
        first = self.prepare()
        destination = first["root"] / "archive-scan-snapshots.json"
        data = json.loads(destination.read_text())
        data["games"]["ready-or-not"]["scanned_at"] = "2026-11-30T10:00:00+00:00"
        destination.write_text(json.dumps(data))
        later = self.prepare()
        self.assertEqual(later["scans"]["ready-or-not"]["scanned_at"],
                         "2026-11-30T10:00:00+00:00")
        self.assertFalse(later["imported"])

    def test_does_not_copy_from_or_overwrite_released_hub_storage(self):
        self.prepare()
        self.assertEqual((self.prod / "state.json").read_bytes(),
                         self.production_sha)
        self.assertFalse((self.prod / "archive-scan-snapshots.json").exists())

    def test_corrupt_source_stops_without_rewriting_source(self):
        bad = self.b2 / "archive-scan-snapshots.json"
        bad.write_text("{broken!")
        before = bad.read_bytes()
        with self.assertRaisesRegex(store.PreviewStorageError, "Cannot migrate"):
            self.prepare()
        self.assertEqual(bad.read_bytes(), before)
        self.assertFalse(
            (store.shared_directory(self.home) /
             "archive-scan-snapshots.json").exists())

    def test_malicious_symlinked_shared_folder_is_refused(self):
        stable = store.shared_directory(self.home)
        stable.parent.mkdir(parents=True, exist_ok=True)
        stable.symlink_to(self.prod, target_is_directory=True)
        with self.assertRaisesRegex(store.PreviewStorageError, "symlink"):
            self.prepare()
        self.assertEqual((self.prod / "state.json").read_bytes(),
                         self.production_sha)

    def test_invalid_existing_stable_snapshot_is_preserved_and_rejected(self):
        target = store.shared_directory(self.home)
        target.mkdir(parents=True)
        bad = target / "archive-scan-snapshots.json"
        bad.write_bytes(b"DO NOT OVERWRITE")
        with self.assertRaises(store.PreviewStorageError):
            self.prepare()
        self.assertEqual(bad.read_bytes(), b"DO NOT OVERWRITE")

    def test_does_not_discover_arbitrary_other_directories(self):
        (self.cache / "other-project").mkdir()
        result = store.discover_previous(self.home)
        self.assertEqual(result, self.sources)

    def test_shared_data_is_private(self):
        report = self.prepare()
        self.assertEqual(report["root"].stat().st_mode & 0o777, 0o700)
        for name in ("state.json", "archive-scan-snapshots.json",
                     "download-folders.json", "table-column-layouts.json"):
            self.assertEqual((report["root"] / name).stat().st_mode & 0o777,
                             0o600)

    def test_legacy_source_files_are_unmodified(self):
        before = {(p, f.name): f.read_bytes()
                  for p in self.sources for f in p.iterdir()
                  if f.is_file()}
        self.prepare()
        after = {(p, f.name): f.read_bytes()
                 for p in self.sources for f in p.iterdir()
                 if f.is_file()}
        self.assertEqual(before, after)

    def test_activation_preserves_host_nexus_source_and_isolates_writes(self):
        from vrhub import launch_environment, updates
        host_config = self.home / "custom-config"
        source = host_config / "vrhub/nexus_key"
        source.parent.mkdir(parents=True)
        source.write_text("fixture-host-key")
        source.chmod(0o600)
        before = source.read_bytes(), source.stat().st_mtime_ns
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(host_config),
                "NEXUS_API_KEY": "", "VRHUB_NEXUS_KEY_FILE": str(source)}),                 mock.patch.object(launch_environment, "_host", None):
            for _ in range(3):
                report = store.activate_desktop_preview(home=self.home)
                self.assertEqual(updates.get_key(), "fixture-host-key")
                self.assertEqual(updates.key_path(),
                                 report["root"] / "config/vrhub/nexus_key")
                self.assertFalse(updates.key_path().exists())
            updates.set_key("fixture-preview-key")
            self.assertEqual(updates.get_key(), "fixture-preview-key")
            updates.clear_key()
            self.assertEqual(updates.get_key(), "fixture-host-key")
            source.chmod(0o644)
            self.assertIsNone(updates.get_key())
            source.chmod(0o600)
            self.assertEqual((source.read_bytes(), source.stat().st_mtime_ns), before)

    def test_activation_missing_host_nexus_key_is_not_required(self):
        from vrhub import launch_environment, updates
        with mock.patch.dict(os.environ, {"NEXUS_API_KEY": ""}),                 mock.patch.object(launch_environment, "_host", None):
            os.environ.pop("XDG_CONFIG_HOME", None)
            report = store.activate_desktop_preview(home=self.home)
            self.assertEqual(updates.key_path(),
                             report["root"] / "config/vrhub/nexus_key")
            self.assertIsNone(updates.get_key())
            self.assertFalse(updates.key_path().exists())

if __name__ == "__main__":
    unittest.main()
