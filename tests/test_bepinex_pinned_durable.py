# SPDX-License-Identifier: GPL-3.0-only
"""Full pinned payload recovery across independent process exits."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from vrhub import bepinex_transaction_review as adapter, offline_transaction as tx, hub, bepinex_repair_review
from tests.test_bepinex_durable_review import Cases as DurableCases
from tests.test_bepinex_transaction_review import snapshot


class PinnedCases(DurableCases):
    def setUp(self):
        root = os.environ.get("NANNERS_TEST_BEPINEX_ARCHIVES")
        if not root:
            self.skipTest("Explicit pinned archive library required.")
        self.archives = sorted((Path(root)/self.folder).glob("*.zip"))

    def rehearsal(self):
        return adapter.pinned_rehearsal(self.game, self.archives)

    def backup_faults(self):
        return ("after_backup_file:1", f"after_backup_file:{self.backups//2}",
                f"after_backup_file:{self.backups}")

    def original_backup(self, f):
        base = f.root/"installed"
        record = json.loads((base/"hub/state.json").read_bytes())[self.game]
        return str((Path(record["backup"])/"files/winhttp.dll").relative_to(base))

    def expected_new_dirs(self):
        return []

    def test_existing_directory_not_removed(self):
        with self.rehearsal() as (f, plan, review):
            before, owners = snapshot(f), tx._inventory(f)
            self.assertEqual(tx._verify_plan(f, plan)["new_dirs"], [])
            self.assertIn("BepInEx/core", before)
            self.child(f, "apply", "after_all_files", 37)
            # No cleanup is necessary, so this fault must not fire.
            self.child(f, "recover", "after_directory_cleanup:1", 0)
            self.assertEqual(snapshot(f), before)
            self.assertEqual(tx._inventory(f), owners)

    def test_recovered_schema_and_full_backup(self):
        with self.rehearsal() as (f, plan, review):
            before = snapshot(f)
            owners = tx._inventory(f)
            self.assertEqual(len(review["rows"]), self.count)
            self.assertEqual(len(owners), self.backups)
            self.child(f, "apply", "after_inventory", 37)
            for name, sha in owners.items():
                self.assertEqual(tx._sha(tx._read(f, "transaction", "backup/"+name)), sha)
            self.child(f, "recover", "", 0)
            self.assertEqual(snapshot(f), before)
            self.assertEqual(tx._inventory(f), owners)
            base = f.root/"installed"
            with patch.object(hub, "game_path", return_value=base), patch.object(hub, "state_file", return_value=base/"hub/state.json"):
                recovered = bepinex_repair_review.review(hub.load_recipes()[self.game], self.archives)
            self.assertEqual(recovered["rows"], review["rows"])
            self.assertEqual(recovered["ownership_record"], "consistent-record")
            self.assertEqual(recovered["backup_status"], "originals-match")
            self.assertFalse(recovered["write_authorized"])
            print("FULL PINNED RECOVERY", self.game, self.count, self.backups, flush=True)


class Subnautica(PinnedCases, unittest.TestCase):
    game, folder, count, backups = "subnautica", "Subnautica", 45, 49


class Valheim(PinnedCases, unittest.TestCase):
    game, folder, count, backups = "valheim", "Valheim", 135, 139
