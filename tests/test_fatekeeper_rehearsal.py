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
            from vrhub.compatibility_checks import _fatekeeper_inventory
            records = hub._load_state(path=state)
            self.assertEqual(records["fatekeeper"]["files"], [target])
            self.assertEqual(records["fatekeeper:profile"]["files"], [])
            self.assertEqual(set(records["fatekeeper:profile"]["reviewed_dependencies"]),
                             {"config.txt", "plugins/test.dll"})
            self.assertEqual(_fatekeeper_inventory(records["fatekeeper"], injector)[0], "ok")
            self.assertEqual(_fatekeeper_inventory(records["fatekeeper:profile"], profile)[0], "ok")
            from vrhub import installed_integrity, installed_provenance
            recipe = hub.load_recipes()["fatekeeper"]
            integrity = installed_integrity.verify(recipe, state=records)
            self.assertEqual(integrity["status"], "Verified", integrity)
            self.assertEqual(integrity["checked"], 3)
            for cid in ("uevr", "profile"):
                provenance = installed_provenance.evidence(recipe, {"id": cid}, records)
                self.assertTrue(provenance["identified"], provenance)
            (profile / "config.txt").write_bytes(b"customized settings")
            self.assertEqual(installed_integrity.verify(recipe, state=records)["status"], "Verified")
            (profile / "plugins/test.dll").write_bytes(b"tampered")
            self.assertEqual(installed_integrity.verify(recipe, state=records)["status"], "Review")
            (profile / "plugins/test.dll").write_bytes(b"plugin")
            (profile / "config.txt").write_bytes(b"profile")
            (profile / "plugins/test.dll").unlink()
            self.assertEqual(_fatekeeper_inventory(records["fatekeeper:profile"], profile)[0], "error")
            (profile / "plugins/test.dll").write_bytes(b"plugin")
            self.assertEqual((profile / "custom-user.ini").read_bytes(),
                             b"user customization")
            fatekeeper_commit.recover(root)
            self.assertFalse(Path(target).exists())
            self.assertEqual(state.read_bytes(), original_records)
            self.assertEqual((profile / "custom-user.ini").read_bytes(),
                             b"user customization")
            self.assertEqual((injector / "UEVRInjector.exe").read_bytes(),
                             b"injector")

    def managed_repair_fixture(self, *, damage=True):
        from vrhub import fatekeeper_commit as tx, profile_safety
        recipe = hub.load_recipes()["fatekeeper"]
        root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="nanners-a6-", dir=Path.home())))
        prefix = root / "pfx"
        injector = prefix / "drive_c/uevr"
        profile = prefix / "drive_c/users/steamuser/AppData" / recipe["profile"]["dir"]
        prefix.mkdir()
        state = root / "hub/state.json"
        state.parent.mkdir()
        state.write_bytes(b'{"other":{"files":[]}}  ')
        home = root / "home"
        (home / ".local/share").mkdir(parents=True)
        self.enterContext(patch("pathlib.Path.home", return_value=home))
        self.enterContext(patch.multiple(hub, _pfx=lambda *_: prefix, _uevr_dir=lambda *_: injector,
                             profile_dir=lambda *_: profile, state_file=lambda: state))
        stopped = self.enterContext(patch.object(profile_safety, "_assert_game_stopped"))
        self.enterContext(patch.object(tx, "live_install_authorized", return_value=True))
        self.enterContext(patch.multiple(fatekeeper_install, FATEKEEPER_BACKEND_SIZE=len(self.asset),
                               FATEKEEPER_BACKEND_SHA256=sha256(self.asset).hexdigest()))
        tx.install_reviewed(review.build_plan(recipe, self.archives), verified_backend=self.asset)
        backend = injector / "UEVRBackend.dll"
        if damage:
            backend.unlink()
        (profile / "config.txt").write_bytes(b"custom settings")
        (profile / "extra.ini").write_bytes(b"manual file")
        return tx, recipe, root, prefix, state, backend, stopped

    @staticmethod
    def maintenance_inventory(folder):
        return {str(p.relative_to(folder)): (p.lstat().st_mode, p.read_bytes() if p.is_file() else None)
                for p in folder.rglob("*")}

    def test_managed_production_repair_interrupted_and_repeated(self):
        from vrhub import fatekeeper_authorization as auth
        tx, recipe, root, prefix, state, backend, stopped = self.managed_repair_fixture()
        dest = tx._live_destination(None)
        journal = dest.journal_dir / "fk4-journal.json"
        prior = journal.read_bytes()
        old_backup = dest.journal_dir / json.loads(prior)["backup"]
        evidence = self.maintenance_inventory(old_backup)
        before = self.maintenance_inventory(prefix)
        original_state = state.read_bytes()
        plan = review.build_plan(recipe, self.archives)
        write = tx._write
        def interrupt(path, data, mode=0o600):
            write(path, data, mode)
            if path == backend:
                stopped.side_effect = RuntimeError("simulated running game")
        with patch.object(tx, "_write", side_effect=interrupt):
            with self.assertRaisesRegex(RuntimeError, "simulated running game"):
                tx.install_reviewed(plan, verified_backend=self.asset)
        stopped.side_effect = None
        self.assertEqual(json.loads(journal.read_bytes())["phase"], "applying")
        self.assertEqual(state.read_bytes(), original_state)
        self.assertEqual(backend.read_bytes(), self.asset)
        pending = self.maintenance_inventory(root)
        with self.assertRaisesRegex(RuntimeError, "Recover|recover|pending"):
            tx.install_reviewed(review.build_plan(recipe, self.archives), verified_backend=self.asset)
        self.assertEqual(self.maintenance_inventory(root), pending)
        tx.recover_live(approved_review=tx.review_live_recovery())
        self.assertEqual(self.maintenance_inventory(prefix), before)
        self.assertEqual(state.read_bytes(), original_state)
        self.assertEqual(self.maintenance_inventory(old_backup), evidence)
        tx.install_reviewed(review.build_plan(recipe, self.archives), verified_backend=self.asset)
        self.assertEqual(backend.read_bytes(), self.asset)
        self.assertEqual(auth.production_journal(auth.production_authority(dest))[1]["phase"], "committed")
        tx.recover_live(approved_review=tx.review_live_recovery())
        self.assertEqual(self.maintenance_inventory(prefix), before)
        self.assertEqual(state.read_bytes(), original_state)
        self.assertEqual(self.maintenance_inventory(old_backup), evidence)
        self.assertEqual(len(list(dest.journal_dir.glob("history-*"))), 2)

    def test_managed_production_repair_corrupt_previous_backup(self):
        tx, recipe, root, prefix, state, backend, _ = self.managed_repair_fixture()
        dest = tx._live_destination(None)
        journal = dest.journal_dir / "fk4-journal.json"
        record = json.loads(journal.read_bytes())
        backup = dest.journal_dir / record["backup"]
        # The original state existed, so its backup is a real prior-byte row.
        (backup / str(len(record["rows"]) - 1)).write_bytes(b"corrupted prior state")
        before = self.maintenance_inventory(prefix)
        state_before, journal_before = state.read_bytes(), journal.read_bytes()
        from vrhub import fatekeeper_authorization as auth
        ledger = auth._ledger_path(auth.production_authority(dest))
        ledger_before = ledger.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "Previous Fatekeeper backup verification failed"):
            tx.install_reviewed(review.build_plan(recipe, self.archives), verified_backend=self.asset)
        self.assertEqual(self.maintenance_inventory(prefix), before)
        self.assertEqual((state.read_bytes(), journal.read_bytes(), ledger.read_bytes()),
                         (state_before, journal_before, ledger_before))
        self.assertFalse(backend.exists())
        self.assertEqual((backup / str(len(record["rows"]) - 1)).read_bytes(), b"corrupted prior state")

    def test_managed_production_repair_stale_review(self):
        tx, recipe, root, prefix, state, backend, _ = self.managed_repair_fixture()
        plan = review.build_plan(recipe, self.archives)
        (prefix / "drive_c/uevr/UEVRInjector.exe").write_bytes(b"changed after review")
        before = self.maintenance_inventory(root)
        with self.assertRaisesRegex(RuntimeError, "changed"):
            tx.install_reviewed(plan, verified_backend=self.asset)
        self.assertEqual(self.maintenance_inventory(root), before)
        self.assertFalse(backend.exists())

    def test_managed_production_synthetic_version_transition(self):
        from vrhub import fatekeeper_authorization as auth, installed_integrity
        tx, recipe, root, prefix, state, backend, _ = self.managed_repair_fixture(damage=False)
        dest = tx._live_destination(None)
        journal = dest.journal_dir / "fk4-journal.json"
        prior = journal.read_bytes()
        backup = dest.journal_dir / json.loads(prior)["backup"]
        evidence = self.maintenance_inventory(backup)
        old_state = state.read_bytes()
        old_pins = dict(recipe["archive_pins"])
        old_records = json.loads(old_state)
        save = prefix / "unrelated-save.bin"
        save.write_bytes(b"save")
        before = self.maintenance_inventory(prefix)
        v2 = root / "profile-v2.zip"
        with zipfile.ZipFile(v2, "w") as archive:
            archive.writestr("config.txt", b"new defaults")
            archive.writestr("plugins/test.dll", b"plugin v2")
            archive.writestr("plugins/new.dll", b"new plugin")
        archives = [self.archives[0], v2]
        unchanged = self.maintenance_inventory(root)
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            review.build_plan(recipe, archives)
        self.assertEqual(self.maintenance_inventory(root), unchanged)
        # Only this test's in-memory recipe authorizes the synthetic v2.
        recipe["archive_pins"] = {**old_pins, "profile": sha256(v2.read_bytes()).hexdigest()}
        plan = review.build_plan(recipe, archives)
        self.assertIn(("Replace", "Profile", "plugins/test.dll"), plan.file_decisions)
        self.assertIn(("Install", "Profile", "plugins/new.dll"), plan.file_decisions)
        self.assertIn(("Preserve", "Profile", "config.txt"), plan.file_decisions)
        self.assertIn(("Preserve", "Profile", "extra.ini"), plan.file_decisions)
        self.assertIn(("Preserve", "Injector", "UEVRBackend.dll"), plan.file_decisions)
        self.assertIn(("Preserve", "Injector", "UEVRInjector.exe"), plan.file_decisions)
        changed = dest.profile / "plugins/test.dll"
        added = dest.profile / "plugins/new.dll"
        self.assertEqual(set(tx.install_reviewed(plan, verified_backend=self.asset)), {changed, added})
        self.assertEqual(changed.read_bytes(), b"plugin v2")
        self.assertEqual(added.read_bytes(), b"new plugin")
        after = self.maintenance_inventory(prefix)
        self.assertEqual(set(after)-set(before), {str(added.relative_to(prefix))})
        for name, value in before.items():
            if name != str(changed.relative_to(prefix)):
                self.assertEqual(after[name], value)
        records = json.loads(state.read_bytes())
        self.assertEqual(records["other"], old_records["other"])
        self.assertEqual(records["fatekeeper"]["archive_sha256"], old_pins["uevr"])
        self.assertEqual(records["fatekeeper:profile"]["archive_sha256"], recipe["archive_pins"]["profile"])
        self.assertEqual(set(records["fatekeeper:profile"]["files"]),
                         set(old_records["fatekeeper:profile"]["files"]) | {str(added)})
        self.assertEqual(records["fatekeeper:profile"]["reviewed_dependencies"]["plugins/test.dll"]["sha256"],
                         sha256(b"plugin v2").hexdigest())
        self.assertEqual(installed_integrity.verify(recipe, state=records)["status"], "Verified")
        history, = dest.journal_dir.glob("history-*")
        self.assertEqual((history / "fk4-journal.json").read_bytes(), prior)
        self.assertEqual(self.maintenance_inventory(backup), evidence)
        self.assertEqual(self.maintenance_inventory(history / backup.name), evidence)
        unchanged = self.maintenance_inventory(root)
        self.assertEqual(tx.install_reviewed(review.build_plan(recipe, archives), verified_backend=self.asset), [])
        self.assertEqual(self.maintenance_inventory(root), unchanged)
        tx.recover_live(approved_review=tx.review_live_recovery())
        self.assertEqual(self.maintenance_inventory(prefix), before)
        self.assertEqual(state.read_bytes(), old_state)
        self.assertEqual(self.maintenance_inventory(backup), evidence)
        self.assertEqual(auth.production_journal(auth.production_authority(dest))[1]["phase"], "rolled-back")
        # Old pins remain valid for old installed bytes; new pins do not
        # magically turn restored v1 into a verified v2 installation.
        self.assertNotEqual(installed_integrity.verify(recipe, state=json.loads(old_state))["status"], "Verified")
        recipe["archive_pins"] = old_pins
        self.assertEqual(installed_integrity.verify(recipe, state=json.loads(old_state))["status"], "Verified")

    def test_managed_update_interrupted_after_payload_and_state(self):
        from vrhub import fatekeeper_authorization as auth, installed_integrity
        tx, recipe, root, prefix, state, backend, stopped = self.managed_repair_fixture(damage=False)
        dest = tx._live_destination(None)
        journal = dest.journal_dir / "fk4-journal.json"
        old_pins = dict(recipe["archive_pins"])
        old_state = state.read_bytes()
        prior = journal.read_bytes()
        backup = dest.journal_dir / json.loads(prior)["backup"]
        evidence = self.maintenance_inventory(backup)
        changed = dest.profile / "plugins/test.dll"
        added = dest.profile / "plugins/new.dll"
        changed.chmod(0o640)
        (prefix / "save.bin").write_bytes(b"unrelated save")
        before = self.maintenance_inventory(prefix)
        v2 = root / "profile-v2.zip"
        with zipfile.ZipFile(v2, "w") as archive:
            archive.writestr("config.txt", b"new defaults")
            archive.writestr("plugins/test.dll", b"plugin v2")
            archive.writestr("plugins/new.dll", b"new plugin")
        recipe["archive_pins"] = {**old_pins, "profile": sha256(v2.read_bytes()).hexdigest()}
        archives = [self.archives[0], v2]
        write = tx._write
        for boundary in (changed, state):
            with self.subTest(boundary=boundary.name):
                plan = review.build_plan(recipe, archives)
                def interrupt(path, data, mode=0o600):
                    write(path, data, mode)
                    if path == boundary:
                        stopped.side_effect = RuntimeError("simulated running game")
                with patch.object(tx, "_write", side_effect=interrupt):
                    with self.assertRaisesRegex(RuntimeError, "simulated running game"):
                        tx.install_reviewed(plan, verified_backend=self.asset)
                stopped.side_effect = None
                self.assertEqual(json.loads(journal.read_bytes())["phase"], "applying")
                if boundary == state:
                    self.assertEqual(json.loads(state.read_bytes())["fatekeeper:profile"]["archive_sha256"],
                                     recipe["archive_pins"]["profile"])
                else:
                    self.assertEqual(state.read_bytes(), old_state)
                pending = self.maintenance_inventory(root)
                with self.assertRaisesRegex(RuntimeError, "Recover|recover|pending"):
                    tx.install_reviewed(review.build_plan(recipe, archives), verified_backend=self.asset)
                self.assertEqual(self.maintenance_inventory(root), pending)
                tx.recover_live(approved_review=tx.review_live_recovery())
                self.assertEqual(self.maintenance_inventory(prefix), before)
                self.assertEqual(state.read_bytes(), old_state)
                self.assertEqual(self.maintenance_inventory(backup), evidence)
                self.assertEqual(auth.production_journal(auth.production_authority(dest))[1]["phase"], "rolled-back")
                self.assertEqual(installed_integrity.verify({**recipe, "archive_pins": old_pins},
                                                           state=json.loads(old_state))["status"], "Verified")
        tx.install_reviewed(review.build_plan(recipe, archives), verified_backend=self.asset)
        self.assertEqual(changed.read_bytes(), b"plugin v2")
        self.assertEqual(added.read_bytes(), b"new plugin")
        self.assertEqual(installed_integrity.verify(recipe, state=json.loads(state.read_bytes()))["status"], "Verified")
        tx.recover_live(approved_review=tx.review_live_recovery())
        self.assertEqual(self.maintenance_inventory(prefix), before)
        self.assertEqual(state.read_bytes(), old_state)
        histories = list(dest.journal_dir.glob("history-*"))
        self.assertEqual(len(histories), 3)
        original, = [h for h in histories if (h / "fk4-journal.json").read_bytes() == prior]
        self.assertEqual(self.maintenance_inventory(original / backup.name), evidence)

    def test_managed_update_stale_review_refuses_changed_archive_or_settings(self):
        tx, recipe, root, prefix, state, backend, _ = self.managed_repair_fixture(damage=False)
        dest = tx._live_destination(None)
        v2 = root / "profile-v2.zip"
        with zipfile.ZipFile(v2, "w") as archive:
            archive.writestr("config.txt", b"new defaults")
            archive.writestr("plugins/test.dll", b"plugin v2")
        recipe["archive_pins"]["profile"] = sha256(v2.read_bytes()).hexdigest()
        archives = [self.archives[0], v2]
        plan = review.build_plan(recipe, archives)
        original = v2.read_bytes()
        v2.write_bytes(b"tampered")
        before = self.maintenance_inventory(root)
        with self.assertRaisesRegex(RuntimeError, "Invalid UEVR ZIP archive"):
            tx.install_reviewed(plan, verified_backend=self.asset)
        self.assertEqual(self.maintenance_inventory(root), before)
        with zipfile.ZipFile(v2, "w") as archive:
            archive.writestr("config.txt", b"new defaults")
            archive.writestr("plugins/test.dll", b"tampered plugin")
        before = self.maintenance_inventory(root)
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            tx.install_reviewed(plan, verified_backend=self.asset)
        self.assertEqual(self.maintenance_inventory(root), before)
        v2.write_bytes(original)
        plan = review.build_plan(recipe, archives)
        (dest.profile / "config.txt").write_bytes(b"new player settings")
        before = self.maintenance_inventory(root)
        with self.assertRaisesRegex(RuntimeError, "changed"):
            tx.install_reviewed(plan, verified_backend=self.asset)
        self.assertEqual(self.maintenance_inventory(root), before)

    def test_production_history_verifier_preserves_originals(self):
        from vrhub.fatekeeper_artifacts import verify_history
        tx, recipe, root, prefix, state, backend, _ = self.managed_repair_fixture()
        dest = tx._live_destination(None)
        tx.install_reviewed(review.build_plan(recipe, self.archives), verified_backend=self.asset)
        active = json.loads((dest.journal_dir / "fk4-journal.json").read_bytes())
        before = self.maintenance_inventory(root)
        history, = verify_history(dest, active_backup=active["backup"])
        self.assertEqual(history.phase, "committed")
        self.assertEqual(history.backup, "fk4-backup")
        self.assertEqual(self.maintenance_inventory(root), before)
        retained = dest.journal_dir / history.name / history.backup
        original = dest.journal_dir / history.backup
        journal = retained.parent / "fk4-journal.json"
        raw = journal.read_bytes()
        for location in (retained, original):
            file = location / "state-new"
            data = file.read_bytes()
            file.write_bytes(b"corruption")
            before = self.maintenance_inventory(root)
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                verify_history(dest, active_backup=active["backup"])
            self.assertEqual(self.maintenance_inventory(root), before)
            file.write_bytes(data)
            file.unlink()
            before = self.maintenance_inventory(root)
            with self.assertRaisesRegex(RuntimeError, "Missing"):
                verify_history(dest, active_backup=active["backup"])
            self.assertEqual(self.maintenance_inventory(root), before)
            file.write_bytes(data)
            file.chmod(0o600)
            extra = location / "999"
            extra.write_bytes(b"extra")
            extra.chmod(0o600)
            before = self.maintenance_inventory(root)
            with self.assertRaisesRegex(RuntimeError, "membership"):
                verify_history(dest, active_backup=active["backup"])
            self.assertEqual(self.maintenance_inventory(root), before)
            extra.unlink()
        for field, value, error in (("schema", 1, "journal"),
                                    ("identity", {}, "identity"),
                                    ("phase", "applying", "Nonterminal"),
                                    ("backup", "../foreign", "backup location")):
            record = json.loads(raw)
            record[field] = value
            journal.write_text(json.dumps(record))
            before = self.maintenance_inventory(root)
            with self.assertRaisesRegex(RuntimeError, error):
                verify_history(dest, active_backup=active["backup"])
            self.assertEqual(self.maintenance_inventory(root), before)
        journal.write_bytes(raw)
        self.assertEqual(len(verify_history(dest, active_backup=active["backup"])), 1)
        # Historical verification does not replace the active recovery entry point.
        tx.recover_live(approved_review=tx.review_live_recovery())
        self.assertFalse(backend.exists())

    def test_production_history_multiple_generations_and_conflict(self):
        import shutil
        from vrhub.fatekeeper_artifacts import verify_history
        tx, recipe, root, prefix, state, backend, _ = self.managed_repair_fixture()
        dest = tx._live_destination(None)
        for _ in range(2):
            tx.install_reviewed(review.build_plan(recipe, self.archives), verified_backend=self.asset)
            tx.recover_live(approved_review=tx.review_live_recovery())
        tx.install_reviewed(review.build_plan(recipe, self.archives), verified_backend=self.asset)
        active = json.loads((dest.journal_dir / "fk4-journal.json").read_bytes())
        before = self.maintenance_inventory(root)
        histories = verify_history(dest, active_backup=active["backup"])
        self.assertEqual(len(histories), 3)
        self.assertEqual(len({h.backup for h in histories}), 3)
        self.assertEqual(sorted(h.phase for h in histories), ["committed", "rolled-back", "rolled-back"])
        self.assertEqual(self.maintenance_inventory(root), before)
        source = dest.journal_dir / histories[0].name
        duplicate = dest.journal_dir / ("history-" + "f"*32)
        shutil.copytree(source, duplicate)
        journal = duplicate / "fk4-journal.json"
        record = json.loads(journal.read_bytes())
        record["phase"] = "rolled-back" if record["phase"] == "committed" else "committed"
        journal.write_text(json.dumps(record))
        before = self.maintenance_inventory(root)
        with self.assertRaisesRegex(RuntimeError, "Conflicting historical journals"):
            verify_history(dest, active_backup=active["backup"])
        self.assertEqual(self.maintenance_inventory(root), before)

    def test_production_history_unsafe_artifacts_and_independent_recovery(self):
        from vrhub.fatekeeper_artifacts import verify_history
        tx, recipe, root, prefix, state, backend, _ = self.managed_repair_fixture()
        dest = tx._live_destination(None)
        old_prefix = self.maintenance_inventory(prefix)
        old_state = state.read_bytes()
        tx.install_reviewed(review.build_plan(recipe, self.archives), verified_backend=self.asset)
        active = json.loads((dest.journal_dir / "fk4-journal.json").read_bytes())
        history, = verify_history(dest, active_backup=active["backup"])
        folder = dest.journal_dir / history.name
        retained = folder / history.backup
        incomplete = dest.journal_dir / ("history-" + "e"*32)
        incomplete.mkdir(mode=0o700)
        before = self.maintenance_inventory(root)
        with self.assertRaisesRegex(RuntimeError, "Incomplete or unsafe"):
            verify_history(dest, active_backup=active["backup"])
        self.assertEqual(self.maintenance_inventory(root), before)
        incomplete.rmdir()
        for path, mode in ((folder, 0o755), (retained, 0o755),
                           (folder / "fk4-journal.json", 0o644),
                           (retained / "state-new", 0o644)):
            prior = path.stat().st_mode & 0o777
            path.chmod(mode)
            before = self.maintenance_inventory(root)
            with self.assertRaisesRegex(RuntimeError, "Incomplete or unsafe"):
                verify_history(dest, active_backup=active["backup"])
            self.assertEqual(self.maintenance_inventory(root), before)
            path.chmod(prior)
        (retained / "state-new").write_bytes(b"damaged historical copy")
        incomplete.mkdir(mode=0o700)
        historical_before = self.maintenance_inventory(folder)
        original_before = self.maintenance_inventory(dest.journal_dir / history.backup)
        with self.assertRaises(RuntimeError):
            verify_history(dest, active_backup=active["backup"])
        tx.recover_live(approved_review=tx.review_live_recovery())
        self.assertEqual(self.maintenance_inventory(prefix), old_prefix)
        self.assertEqual(state.read_bytes(), old_state)
        self.assertEqual(self.maintenance_inventory(folder), historical_before)
        self.assertEqual(self.maintenance_inventory(dest.journal_dir / history.backup), original_before)
        self.assertTrue(incomplete.is_dir())
        self.assertEqual(list(incomplete.iterdir()), [])
        self.assertEqual(json.loads((dest.journal_dir / "fk4-journal.json").read_bytes())["phase"], "rolled-back")

    def test_production_maintenance_refuses_history_damage_and_unknown_artifacts(self):
        tx, recipe, root, prefix, state, backend, _ = self.managed_repair_fixture()
        dest = tx._live_destination(None)
        before_repair = self.maintenance_inventory(prefix)
        original_state = state.read_bytes()
        tx.install_reviewed(review.build_plan(recipe, self.archives), verified_backend=self.asset)
        history, = dest.journal_dir.glob("history-*")
        historical_backup, = history.glob("fk4-backup*")
        damaged = historical_backup / "state-new"
        original = damaged.read_bytes()
        active = json.loads((dest.journal_dir / "fk4-journal.json").read_bytes())
        active_backup = dest.journal_dir / active["backup"]
        active_file = active_backup / "state-new"
        active_bytes = active_file.read_bytes()
        unknown = dest.journal_dir / "unrecognized"
        orphan = dest.journal_dir / ("fk4-backup-" + "a"*32)
        incomplete = dest.journal_dir / ("history-" + "b"*32)

        def refusal():
            before = self.maintenance_inventory(root)
            with self.assertRaises(RuntimeError):
                tx.install_reviewed(review.build_plan(recipe, self.archives), verified_backend=self.asset)
            self.assertEqual(self.maintenance_inventory(root), before)

        self.assertEqual(tx.install_reviewed(review.build_plan(recipe, self.archives), verified_backend=self.asset), [])
        for path, data in ((damaged, original), (active_file, active_bytes)):
            path.write_bytes(b"damaged")
            refusal()
            path.write_bytes(data)
        for path in (orphan, incomplete):
            path.mkdir(mode=0o700)
            refusal()
            path.rmdir()
        unknown.write_bytes(b"preserve unknown evidence")
        refusal()
        backend.unlink()
        refusal()
        backend.write_bytes(self.asset)
        damaged.write_bytes(b"damaged history")
        before = self.maintenance_inventory(history)
        tx.recover_live(approved_review=tx.review_live_recovery())
        self.assertEqual(self.maintenance_inventory(prefix), before_repair)
        self.assertEqual(state.read_bytes(), original_state)
        self.assertEqual(self.maintenance_inventory(history), before)
        self.assertEqual(unknown.read_bytes(), b"preserve unknown evidence")

    def test_production_history_publication_interruption_blocks_maintenance(self):
        tx, recipe, root, prefix, state, backend, _ = self.managed_repair_fixture()
        dest = tx._live_destination(None)
        # Establish a recoverable repair transaction before interrupting
        # publication of its history during a subsequent synthetic update.
        tx.install_reviewed(review.build_plan(recipe, self.archives), verified_backend=self.asset)
        v2 = root / "profile-v2.zip"
        with zipfile.ZipFile(v2, "w") as archive:
            archive.writestr("config.txt", b"new defaults")
            archive.writestr("plugins/test.dll", b"plugin v2")
        recipe["archive_pins"]["profile"] = sha256(v2.read_bytes()).hexdigest()
        archives = [self.archives[0], v2]
        journal = dest.journal_dir / "fk4-journal.json"
        original_journal = journal.read_bytes()
        original_state = state.read_bytes()
        original_backup = dest.journal_dir / json.loads(original_journal)["backup"]
        backup_before = self.maintenance_inventory(original_backup)
        prefix_before = self.maintenance_inventory(prefix)
        write = tx._write
        def interrupt(path, data, mode=0o600):
            write(path, data, mode)
            if any(part.startswith("history-") for part in path.parts):
                raise OSError("simulated history publication interruption")
        with patch.object(tx, "_write", side_effect=interrupt):
            with self.assertRaisesRegex(OSError, "history publication interruption"):
                tx.install_reviewed(review.build_plan(recipe, archives), verified_backend=self.asset)
        self.assertEqual(journal.read_bytes(), original_journal)
        self.assertEqual(state.read_bytes(), original_state)
        self.assertEqual(self.maintenance_inventory(prefix), prefix_before)
        self.assertEqual(self.maintenance_inventory(original_backup), backup_before)
        history, = [h for h in dest.journal_dir.glob("history-*") if not (h / "fk4-journal.json").exists()]
        self.assertFalse((history / "fk4-journal.json").exists())
        before = self.maintenance_inventory(root)
        with self.assertRaisesRegex(RuntimeError, "Incomplete or unsafe"):
            tx.install_reviewed(review.build_plan(recipe, archives), verified_backend=self.asset)
        self.assertEqual(self.maintenance_inventory(root), before)
        historical_before = self.maintenance_inventory(history)
        tx.recover_live(approved_review=tx.review_live_recovery())
        self.assertEqual(self.maintenance_inventory(history), historical_before)
        self.assertEqual(self.maintenance_inventory(original_backup), backup_before)
        self.assertEqual(json.loads(journal.read_bytes())["phase"], "rolled-back")
        before = self.maintenance_inventory(root)
        with self.assertRaisesRegex(RuntimeError, "Incomplete or unsafe"):
            tx.install_reviewed(review.build_plan(recipe, archives), verified_backend=self.asset)
        self.assertEqual(self.maintenance_inventory(root), before)

    def test_managed_update_omitted_dependency_blocks_without_writes(self):
        from dataclasses import replace
        tx, recipe, root, prefix, state, backend, _ = self.managed_repair_fixture(damage=False)
        dest = tx._live_destination(None)
        v2 = root / "profile-v2.zip"
        with zipfile.ZipFile(v2, "w") as archive:
            archive.writestr("config.txt", b"new defaults")
            archive.writestr("plugins/new.dll", b"new plugin")
        recipe["archive_pins"]["profile"] = sha256(v2.read_bytes()).hexdigest()
        archives = [self.archives[0], v2]
        for missing in (False, True):
            with self.subTest(missing=missing):
                if missing:
                    (dest.profile / "plugins/test.dll").unlink()
                plan = review.build_plan(recipe, archives)
                self.assertTrue(any("plugins/test.dll" in b for b in plan.compatibility_blockers))
                self.assertFalse(any("extra.ini" in b for b in plan.compatibility_blockers))
                if not missing:
                    self.assertIn(("Preserve", "Profile", "plugins/test.dll"), plan.file_decisions)
                before = self.maintenance_inventory(root)
                # Even a forged review without the visible blocker is refreshed.
                with self.assertRaisesRegex(RuntimeError, "compatibility review required"):
                    tx.install_reviewed(replace(plan, compatibility_blockers=()), verified_backend=self.asset)
                self.assertEqual(self.maintenance_inventory(root), before)

    def test_managed_update_invalid_ownership_blocks_without_writes(self):
        tx, recipe, root, prefix, state, backend, _ = self.managed_repair_fixture(damage=False)
        original = state.read_bytes()
        dest = tx._live_destination(None)
        plan = review.build_plan(recipe, self.archives)
        for field, value in (("root", str(root / "foreign")),
                             ("files", [str(root / "foreign.dll")]),
                             ("files", [str(dest.profile / "config.txt")] * 2),
                             ("reviewed_dependencies", {"../escape": {"sha256": "a"*64, "size": 1}}),
                             ("archive_sha256", "invalid")):
            with self.subTest(field=field, value=value):
                records = json.loads(original)
                records["fatekeeper:profile"][field] = value
                state.write_text(json.dumps(records))
                before = self.maintenance_inventory(root)
                refreshed = review.build_plan(recipe, self.archives)
                self.assertTrue(refreshed.compatibility_blockers)
                with self.assertRaisesRegex(RuntimeError, "compatibility review required"):
                    tx.install_reviewed(plan, verified_backend=self.asset)
                self.assertEqual(self.maintenance_inventory(root), before)
        state.write_bytes(original)

    def test_managed_compatibility_dependency_not_owned_and_ownership_only(self):
        folder = Path("/synthetic/profile")
        meta = {"sha256": "a"*64, "size": 1}
        rec = {"installer": "fatekeeper-pair-fk4", "root": str(folder),
               "archive_sha256": "b"*64, "reviewed_dependencies": {"config.txt": meta, "old.dll": meta},
               "files": [str(folder / "owned-only.dll")]}
        blocks = review.managed_compatibility({"fatekeeper:profile": rec}, folder, "Profile", {"config.txt"})
        self.assertEqual(len(blocks), 2)
        self.assertTrue(any("old.dll" in b for b in blocks))
        self.assertTrue(any("owned-only.dll" in b for b in blocks))

    def test_managed_production_repair_cycle(self):
        from vrhub import fatekeeper_commit as tx, fatekeeper_authorization as auth
        from vrhub import profile_safety
        import stat
        recipe = hub.load_recipes()["fatekeeper"]
        with zipfile.ZipFile(self.archives[1], "a") as archive:
            for name in review.FATEKEEPER_LOCAL_PROFILE_FILES - {"config.txt"}:
                archive.writestr(name, b"packaged defaults")
        recipe["archive_pins"]["profile"] = sha256(self.archives[1].read_bytes()).hexdigest()
        root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="nanners-a6-", dir=Path.home())))
        prefix = root / "pfx"
        injector = prefix / "drive_c/uevr"
        profile = prefix / "drive_c/users/steamuser/AppData" / recipe["profile"]["dir"]
        prefix.mkdir()
        state = root / "hub/state.json"
        state.parent.mkdir()
        state.write_bytes(b'{"other":{"files":[]}}  ')
        home = root / "home"
        (home / ".local/share").mkdir(parents=True)
        save = prefix / "unrelated-save.bin"
        save.write_bytes(b"player save")
        def inventory(folder):
            return {str(p.relative_to(folder)): (p.lstat().st_mode, p.read_bytes() if p.is_file() else None)
                    for p in folder.rglob("*")}
        with patch("pathlib.Path.home", return_value=home), \
                patch.multiple(hub, _pfx=lambda *_: prefix, _uevr_dir=lambda *_: injector,
                               profile_dir=lambda *_: profile, state_file=lambda: state), \
                patch.object(profile_safety, "_assert_game_stopped"), \
                patch.object(tx, "live_install_authorized", return_value=True), \
                patch.multiple(fatekeeper_install, FATEKEEPER_BACKEND_SIZE=len(self.asset),
                               FATEKEEPER_BACKEND_SHA256=sha256(self.asset).hexdigest()):
            fresh = review.build_plan(recipe, self.archives)
            self.assertTrue(all(a == "Install" for a, _, _ in fresh.file_decisions))
            tx.install_reviewed(fresh, verified_backend=self.asset)
            destination = tx._live_destination(None)
            self.assertTrue(destination.root.is_relative_to(root))
            journal = destination.journal_dir / "fk4-journal.json"
            original_journal = journal.read_bytes()
            first_backup = destination.journal_dir / json.loads(original_journal)["backup"]
            first_evidence = inventory(first_backup)
            initial_state = state.read_bytes()
            initial = hub._load_state(path=state)
            backend = injector / "UEVRBackend.dll"
            plugin = profile / "plugins/test.dll"
            preserved = [profile / name for name in review.FATEKEEPER_LOCAL_PROFILE_FILES]
            for path in preserved:
                path.write_bytes(b"player settings")
                path.chmod(0o640)
            extra = profile / "extra.ini"
            extra.write_bytes(b"manual addition")
            backend.unlink()
            plugin.write_bytes(b"damaged plugin")
            plugin.chmod(0o640)
            before = inventory(prefix)
            repaired = review.build_plan(recipe, self.archives)
            self.assertIn(("Install", "Injector", "UEVRBackend.dll"), repaired.file_decisions)
            self.assertIn(("Replace", "Profile", "plugins/test.dll"), repaired.file_decisions)
            for path in preserved + [extra]:
                self.assertIn(("Preserve", "Profile", path.relative_to(profile).as_posix()), repaired.file_decisions)
            self.assertEqual(set(tx.install_reviewed(repaired, verified_backend=self.asset)), {backend, plugin})
            self.assertEqual(backend.read_bytes(), self.asset)
            self.assertEqual(plugin.read_bytes(), b"plugin")
            self.assertEqual(stat.S_IMODE(plugin.stat().st_mode), 0o640)
            records = hub._load_state(path=state)
            self.assertEqual(records["other"], initial["other"])
            for key in ("fatekeeper", "fatekeeper:profile"):
                self.assertEqual(set(records[key]["files"]), set(initial[key]["files"]))
            self.assertNotIn(str(extra), records["fatekeeper:profile"]["files"])
            self.assertEqual(inventory(first_backup), first_evidence)
            history, = destination.journal_dir.glob("history-*")
            self.assertEqual((history / "fk4-journal.json").read_bytes(), original_journal)
            self.assertEqual(inventory(history / first_backup.name), first_evidence)
            for path in preserved + [extra, save]:
                self.assertEqual(inventory(prefix)[str(path.relative_to(prefix))], before[str(path.relative_to(prefix))])
            noop = review.build_plan(recipe, self.archives)
            self.assertTrue(all(a == "Preserve" for a, _, _ in noop.file_decisions))
            snapshot = inventory(root)
            with patch.object(tx, "_commit", side_effect=AssertionError("no-op opened transaction")), \
                    patch.object(rehearsal, "build_payload", wraps=rehearsal.build_payload) as payload:
                self.assertEqual(tx.install_reviewed(noop, verified_backend=self.asset), [])
                self.assertEqual(payload.call_args.args[1], self.asset)
            self.assertEqual(inventory(root), snapshot)
            tx.recover_live(approved_review=tx.review_live_recovery())
            self.assertEqual(inventory(prefix), before)
            self.assertEqual(state.read_bytes(), initial_state)
            self.assertEqual(inventory(first_backup), first_evidence)
            self.assertEqual((history / "fk4-journal.json").read_bytes(), original_journal)
            scope = auth.production_authority(destination)
            self.assertEqual(auth.production_journal(scope)[1]["phase"], "rolled-back")

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
            from vrhub import installed_integrity
            self.assertTrue({"imgui.ini", "data/config_default.json"}.issubset(review.FATEKEEPER_LOCAL_PROFILE_FILES))
            records = hub.state()
            self.assertEqual(installed_integrity.verify(recipe, state=records)["status"], "Verified")
            for name in ("imgui.ini", "data/config_default.json"):
                self.assertTrue(records["fatekeeper:profile"]["reviewed_dependencies"][name]["customizable"])
            compatible = review.build_plan(recipe, self.archives)
            self.assertTrue(all(action == "Preserve" for action, _, _ in compatible.file_decisions))
            home = root / "fixture-home"
            (home / ".local/share").mkdir(parents=True)
            with patch("pathlib.Path.home", return_value=home), patch.object(fatekeeper_commit, "live_install_authorized", return_value=True), patch.object(
                fatekeeper_commit, "_commit", side_effect=AssertionError("no-op opened a transaction")
            ), patch.object(review.profile_safety, "_assert_game_stopped"):
                self.assertEqual(fatekeeper_commit.install_reviewed(compatible, verified_backend=self.asset), [])
