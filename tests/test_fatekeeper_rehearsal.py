# SPDX-License-Identifier: GPL-3.0-only
import json
import tempfile
import unittest
import zipfile
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from vrhub import fatekeeper_install
from vrhub import fatekeeper_rehearsal as rehearsal, hub, offline_transaction as transaction
from vrhub import uevr_dependency_review as review


class FatekeeperRehearsalTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.archives = [root / "uevr.zip", root / "profile.zip"]
        with zipfile.ZipFile(self.archives[0], "w") as archive:
            archive.writestr("UEVRInjector.exe", b"injector")
            archive.writestr("UEVRBackend.dll", b"bundled")
        with zipfile.ZipFile(self.archives[1], "w") as archive:
            archive.writestr("config.txt", b"profile")
            archive.writestr("plugins/test.dll", b"plugin")
        recipe = hub.load_recipes()["fatekeeper"]
        recipe["archive_pins"] = {
            role: sha256(path.read_bytes()).hexdigest()
            for role, path in zip(("uevr", "profile"), self.archives)
        }
        self.backend = "drive_c/uevr/UEVRBackend.dll"
        self.config = "drive_c/users/steamuser/AppData/" + recipe["profile"]["dir"] + "/config.txt"
        self.asset = b"verified"
        digest = sha256(self.asset).hexdigest()
        self.enterContext(patch.object(hub, "load_recipes", return_value={"fatekeeper": recipe}))
        self.enterContext(patch.multiple(review, FATEKEEPER_BACKEND_SIZE=len(self.asset),
                                        FATEKEEPER_BACKEND_SHA256=digest))
        self.enterContext(patch.object(rehearsal, "FATEKEEPER_BACKEND_SHA256", digest))

    def prepare(self, before, fetch=None):
        return rehearsal.prepare(self.archives, before, fetch_backend=fetch or (lambda: self.asset))

    def test_fresh_and_repair_rollback(self):
        for before in ({}, {self.backend: b"outdated", self.config: b"old",
                            self.config + ".custom": b"preserved"}):
            with self.subTest(repair=bool(before)), self.prepare(before) as (fixture, plan, payload):
                transaction.execute(fixture, plan)
                self.assertEqual(transaction._read(fixture, "installed", self.backend), self.asset)
                self.assertIn(self.config.replace("config.txt", "plugins/test.dll"), payload)
                if before:
                    self.assertEqual(transaction._read(fixture, "installed", self.config + ".custom"),
                                     b"preserved")
                transaction.rollback(fixture)
                self.assertEqual(transaction._inventory(fixture), plan.before)
                self.assertEqual(transaction._read(fixture, "installed", self.backend, optional=True),
                                 before.get(self.backend))

    def test_restart_recovers_files_and_inventory(self):
        before = {self.backend: b"outdated", self.config: b"old"}
        with self.prepare(before) as (fixture, plan, _):
            with self.assertRaises(transaction.SimulatedCrash):
                transaction.execute(fixture, plan, fault="after_inventory")
            transaction.recover(fixture)
            self.assertEqual(transaction._inventory(fixture), plan.before)
            for name, data in before.items():
                self.assertEqual(transaction._read(fixture, "installed", name), data)

    def test_preserves_approved_backend_without_fetch(self):
        def fail():
            self.fail("The approved backend should be reused")
        with self.prepare({self.backend: self.asset}, fail) as (_, plan, _):
            self.assertNotIn(self.backend, {row["path"] for row in plan.rows})

    def test_bad_hash_stops_before_transaction(self):
        with self.assertRaisesRegex(RuntimeError, "backend verification failed"):
            with self.prepare({}, lambda: b"incorrect"):
                self.fail("Backend mismatch reached transaction preparation")
        self.archives[0].write_bytes(b"tampered")
        with self.assertRaisesRegex(RuntimeError, "archive failed SHA-256"):
            with self.prepare({}):
                self.fail("Bad archive reached transaction preparation")


    def test_interrupted_repair_restores_hub_serialized_records(self):
        records = {
            "fatekeeper": {"files": ["old"], "backup": "original-backup"},
            "fatekeeper:profile": {"installer": "uevr-profile-2", "backup": "profile-backup"},
            "unrelated": {"files": ["keep"]},
        }
        before = {self.backend: b"old", self.config: b"old-profile"}
        with rehearsal.prepare(self.archives, before, fetch_backend=lambda: self.asset,
                               hub_records=records) as (fixture, plan, payload):
            state = fixture.root / "installed/hub/state.json"
            original = state.read_bytes()
            expected = json.loads(payload["hub/state.json"])
            self.assertEqual(expected["unrelated"], records["unrelated"])
            self.assertTrue(Path(expected["fatekeeper"]["root"]).is_relative_to(fixture.root))
            with self.assertRaises(transaction.SimulatedCrash):
                transaction.execute(fixture, plan, fault="after_inventory")
            self.assertEqual(hub._load_state(path=state), expected)
            transaction.recover(fixture)
            self.assertEqual(state.read_bytes(), original)
            self.assertEqual(hub._load_state(path=state), records)
            self.assertEqual(transaction._inventory(fixture), plan.before)
            self.assertEqual(transaction._read(fixture, "installed", self.backend), b"old")
            self.assertEqual(transaction._read(fixture, "installed", self.config), b"old-profile")


    def test_installer_preflight_targets_reviewed_prefix_and_keeps_matching_backend(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        prefix = root / "pfx"
        injector = prefix / "drive_c/uevr"
        profile = prefix / self.config.removesuffix("/config.txt")
        injector.mkdir(parents=True)
        backend = injector / "UEVRBackend.dll"
        backend.write_bytes(self.asset)
        state_path = root / "state.json"
        hub._save_state({"unrelated": {"files": ["keep"]}}, path=state_path)
        original_state = state_path.read_bytes()
        with patch.multiple(hub, _pfx=lambda *_: prefix, _uevr_dir=lambda *_: injector,
                            profile_dir=lambda *_: profile, state_file=lambda: state_path):
            plan = review.build_plan(hub.load_recipes()["fatekeeper"], self.archives)
            with patch.multiple(fatekeeper_install, FATEKEEPER_BACKEND_SIZE=len(self.asset),
                                FATEKEEPER_BACKEND_SHA256=sha256(self.asset).hexdigest()):
                prepared = fatekeeper_install.prepare_reviewed_install(plan, verified_backend=b"invalid")
            self.assertEqual(prepared.prefix, prefix)
            self.assertNotIn(str(backend), prepared.writes)
            self.assertEqual(prepared.writes[str(profile / "config.txt")], b"profile")
            self.assertEqual(prepared.state, {"unrelated": {"files": ["keep"]}})
            self.assertEqual(state_path.read_bytes(), original_state)
            self.assertEqual(backend.read_bytes(), self.asset)
            self.assertFalse(profile.exists())
            with patch.object(hub, "_uevr_dir", return_value=prefix / "other"):
                with self.assertRaisesRegex(RuntimeError, "installation paths changed"):
                    fatekeeper_install.prepare_reviewed_install(plan)

            backend.write_bytes(b"changed after review")
            with self.assertRaisesRegex(RuntimeError, "installation changed"):
                fatekeeper_install.prepare_reviewed_install(plan)


    def test_existing_setup_missing_only_backend_can_review_install_and_rollback(self):
        """A player never needs to manually copy the missing joeyhodge DLL."""
        from vrhub import fatekeeper_commit

        root = Path(self.enterContext(tempfile.TemporaryDirectory(
            prefix="nanners-fk4-", dir="/tmp")))
        prefix, injector, profile, state = fatekeeper_commit._roots(root)
        injector.mkdir(parents=True)
        profile.mkdir(parents=True)
        (injector / "UEVRInjector.exe").write_bytes(b"injector")
        (profile / "config.txt").write_bytes(b"profile")
        (profile / "plugins").mkdir()
        (profile / "plugins/test.dll").write_bytes(b"plugin")
        (profile / "custom-user.ini").write_bytes(b"user customization")
        state.write_bytes(b'{"unrelated":{"files":["preserve"]}}' + bytes([10]))
        original_records = state.read_bytes()
        with patch.multiple(hub, _pfx=lambda *_: prefix,
                            _uevr_dir=lambda *_: injector,
                            profile_dir=lambda *_: profile,
                            state_file=lambda: state):
            plan = review.build_plan(hub.load_recipes()["fatekeeper"], self.archives)
            self.assertTrue(plan.needs_backend_verification)
            self.assertIn(("Install", "Injector", "UEVRBackend.dll"),
                          plan.file_decisions)
            self.assertIn("No manual DLL copying", plan.backend_status)
            prepared = fatekeeper_install.prepare_reviewed_install(
                plan, verified_backend=self.asset)
            target = str(injector / "UEVRBackend.dll")
            self.assertEqual(prepared.writes, {target: self.asset})
            self.assertFalse((injector / "UEVRBackend.dll").exists())
            fatekeeper_commit.commit(root, prepared)
            self.assertEqual(Path(target).read_bytes(), self.asset)
            self.assertEqual((profile / "custom-user.ini").read_bytes(),
                             b"user customization")
            fatekeeper_commit.recover(root)
            self.assertFalse(Path(target).exists())
            self.assertEqual(state.read_bytes(), original_records)
            self.assertEqual((profile / "custom-user.ini").read_bytes(),
                             b"user customization")
            self.assertEqual((injector / "UEVRInjector.exe").read_bytes(),
                             b"injector")

    def test_smart_preservation_fresh_repair_recovery_and_noop(self):
        from vrhub import fatekeeper_commit

        recipe = hub.load_recipes()["fatekeeper"]
        with zipfile.ZipFile(self.archives[1], "a") as archive:
            for name in review.FATEKEEPER_LOCAL_PROFILE_FILES - {"config.txt"}:
                archive.writestr(name, b"packaged defaults")
        recipe["archive_pins"]["profile"] = sha256(self.archives[1].read_bytes()).hexdigest()
        root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="nanners-fk4-", dir="/tmp")))
        prefix, injector, profile, state = fatekeeper_commit._roots(root)
        prefix.mkdir()
        with patch.multiple(hub, _pfx=lambda *_: prefix, _uevr_dir=lambda *_: injector,
                            profile_dir=lambda *_: profile, state_file=lambda: state):
            fresh = review.build_plan(recipe, self.archives)
            self.assertTrue(all(action == "Install" for action, _, _ in fresh.file_decisions))
            prepared = fatekeeper_install.prepare_reviewed_install(fresh, verified_backend=self.asset)
            fatekeeper_commit.commit(root, prepared)
            for name in review.FATEKEEPER_LOCAL_PROFILE_FILES:
                self.assertTrue((profile / name).is_file())
            fatekeeper_commit.recover(root)
            self.assertFalse(profile.exists())
            self.assertFalse(state.exists())

            for name in review.FATEKEEPER_LOCAL_PROFILE_FILES | {"extra.ini"}:
                path = profile / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"local data")
            injector.mkdir(parents=True)
            (injector / "UEVRBackend.dll").write_bytes(b"outdated")
            state.write_bytes(b'{"unrelated":{}}  ')
            repair = review.build_plan(recipe, self.archives)
            for name in review.FATEKEEPER_LOCAL_PROFILE_FILES | {"extra.ini"}:
                self.assertIn(("Preserve", "Profile", name), repair.file_decisions)
            self.assertIn(("Replace", "Injector", "UEVRBackend.dll"), repair.file_decisions)
            prepared = fatekeeper_install.prepare_reviewed_install(repair, verified_backend=self.asset)
            fatekeeper_commit.commit(root, prepared, interrupt_after_files=True)
            fatekeeper_commit.recover(root)
            self.assertEqual(state.read_bytes(), b'{"unrelated":{}}  ')
            self.assertEqual((injector / "UEVRBackend.dll").read_bytes(), b"outdated")
            fatekeeper_commit.commit(root, prepared)
            self.assertEqual((injector / "UEVRBackend.dll").read_bytes(), self.asset)
            for name in review.FATEKEEPER_LOCAL_PROFILE_FILES | {"extra.ini"}:
                self.assertEqual((profile / name).read_bytes(), b"local data")
            compatible = review.build_plan(recipe, self.archives)
            self.assertTrue(all(action == "Preserve" for action, _, _ in compatible.file_decisions))
            with patch.object(fatekeeper_commit, "live_install_authorized", return_value=True), patch.object(
                fatekeeper_commit, "_commit", side_effect=AssertionError("no-op opened a transaction")
            ), patch.object(review.profile_safety, "_assert_game_stopped"):
                self.assertEqual(fatekeeper_commit.install_reviewed(compatible, verified_backend=self.asset), [])
