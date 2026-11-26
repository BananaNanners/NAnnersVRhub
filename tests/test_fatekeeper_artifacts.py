# SPDX-License-Identifier: GPL-3.0-only
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from vrhub.fatekeeper_artifacts import inventory


class RecoveryArtifactTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.store = self.root / "recovery"
        self.store.mkdir(mode=0o700)

    def file(self, path, data=b"synthetic evidence"):
        path.write_bytes(data)
        path.chmod(0o600)

    def snapshot(self):
        return {str(p.relative_to(self.root)): (p.lstat().st_mode,
                os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
                for p in self.root.rglob("*")}

    def classify(self, **kwargs):
        before = self.snapshot()
        result = {r.name: r.kind for r in inventory(self.store, **kwargs)}
        self.assertEqual(self.snapshot(), before)
        return result

    def test_active_history_and_orphan_candidates(self):
        self.file(self.store / "fk4-journal.json")
        self.file(self.store / "fk4.lock")
        active = self.store / "fk4-backup"
        active.mkdir(mode=0o700)
        self.file(active / "state-new")
        old = self.store / ("fk4-backup-" + "a"*32)
        old.mkdir(mode=0o700)
        history = self.store / ("history-" + "b"*32)
        history.mkdir(mode=0o700)
        self.file(history / "fk4-journal.json")
        retained = history / old.name
        retained.mkdir(mode=0o700)
        self.file(retained / "0")
        rows = self.classify(active_backup=active.name)
        self.assertEqual(rows[active.name], "active-backup-candidate")
        self.assertEqual(rows[old.name], "orphan-backup-candidate")
        self.assertEqual(rows[history.name], "history-candidate")
        self.assertEqual(rows["fk4-journal.json"], "journal-candidate")

    def test_incomplete_history_and_residue(self):
        history = self.store / ("history-" + "c"*32)
        history.mkdir(mode=0o700)
        backup = history / "fk4-backup"
        backup.mkdir(mode=0o700)
        self.file(backup / ".state-new-abc")
        self.file(self.store / ".fk4-journal.json-abc")
        rows = self.classify()
        self.assertEqual(rows[history.name], "incomplete-or-unsafe-history")
        self.assertEqual(rows[history.name + "/fk4-backup/.state-new-abc"], "atomic-residue")
        self.assertEqual(rows[".fk4-journal.json-abc"], "atomic-residue")

    def test_staging_hint_does_not_authorize(self):
        backup = self.store / "fk4-backup"
        backup.mkdir(mode=0o700)
        self.file(backup / "0")
        self.assertEqual(self.classify()[backup.name], "orphan-backup-candidate")
        self.assertEqual(self.classify(staging=True)[backup.name], "staging-candidate")
        self.file(backup / "unexpected")
        self.assertEqual(self.classify(staging=True)[backup.name], "unsafe-backup")

    def test_links_and_unknown_files_not_followed(self):
        outside = self.root / "outside"
        self.file(outside)
        (self.store / "fk4-journal.json").symlink_to(outside)
        os.link(outside, self.store / "fk4.lock")
        (self.store / ("history-" + "d"*32)).symlink_to(self.root, target_is_directory=True)
        self.file(self.store / "unknown")
        rows = self.classify()
        self.assertTrue(all(kind == "unsafe-or-unknown" for kind in rows.values()))
        self.assertEqual(len(rows), 4)

    def test_absent_store_and_symlink_ancestor(self):
        missing = self.root / "missing"
        self.assertEqual(inventory(missing), ())
        self.assertFalse(missing.exists())
        link = self.root / "alias"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            inventory(link / "recovery")

    def test_unsafe_mode_and_invalid_hint(self):
        self.store.chmod(0o755)
        with self.assertRaisesRegex(RuntimeError, "Unsafe"):
            inventory(self.store)
        self.store.chmod(0o700)
        with self.assertRaisesRegex(RuntimeError, "Invalid"):
            inventory(self.store, active_backup="../foreign")

    def test_inventory_bound_preserves_every_entry(self):
        for name in ("one", "two", "three"):
            self.file(self.store / name)
        before = self.snapshot()
        with patch("vrhub.fatekeeper_artifacts._MAX_ENTRIES", 2):
            with self.assertRaisesRegex(RuntimeError, "limit exceeded"):
                inventory(self.store)
        self.assertEqual(self.snapshot(), before)

    def test_nested_unsafe_evidence_and_fifo(self):
        backup = self.store / "fk4-backup"
        backup.mkdir(mode=0o700)
        self.file(backup / "0")
        (backup / "0").chmod(0o644)
        os.mkfifo(backup / "1", 0o600)
        rows = self.classify(active_backup=backup.name)
        self.assertEqual(rows[backup.name], "unsafe-backup")
        self.assertEqual(rows[backup.name + "/0"], "unsafe-or-unknown")
        self.assertEqual(rows[backup.name + "/1"], "unsafe-or-unknown")
