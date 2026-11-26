import os
from pathlib import Path
import unittest
from vrhub import ervr_transaction_review as er, offline_transaction as tx

class ErvrTransactionReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=os.getenv("NANNERS_TEST_ERVR_ARCHIVE")
        if not path:
            raise unittest.SkipTest("Explicit verified ERVR archive fixture not supplied")
        cls.archive=Path(path).read_bytes()
        cls.payload=er.reviewed_payload(cls.archive)
    def snapshot(self,f):
        root=f.root/"installed"
        return {p.relative_to(root).as_posix():(p.stat().st_mode,p.read_bytes() if p.is_file() else None) for p in root.rglob("*")}
    def test_success_and_rollback(self):
        with er.rehearsal(self.archive) as f:
            before=self.snapshot(f); owners=tx._inventory(f)
            plan=tx.build_plan(f)
            self.assertEqual({r["path"] for r in plan.rows},er.REPLACE|er.ADD|{"hub/state.json"})
            self.assertFalse(plan.authorized_live_install)
            result=tx.execute(f,plan)
            self.assertFalse(result["authorized_live_install"])
            after=self.snapshot(f)
            for n in er.REPLACE|er.ADD: self.assertEqual(after[n][1],self.payload[n])
            for n in er.CONFIG|er.PRESERVE|{"hub/backups/ervr-original/sentinel","prefix/save.sl2","Game/unrelated.txt","Game/eldenring.exe"}:
                self.assertEqual(after[n],before[n])
            self.assertNotIn(er.EXCLUDE,after)
            tx.rollback(f)
            self.assertEqual(self.snapshot(f),before)
            self.assertEqual(tx._inventory(f),owners)
    def test_interruptions(self):
        for fault in ("after_prepare_start","after_backup_file:3","after_stage_file:4","after_backup",
                      "after_replace:1","after_replace:7","after_replace:14","after_all_files","after_inventory"):
            with self.subTest(fault=fault),er.rehearsal(self.archive) as f:
                before=self.snapshot(f);owners=tx._inventory(f)
                with self.assertRaises(tx.SimulatedCrash): tx.execute(f,tx.build_plan(f),fault=fault)
                tx.recover(f)
                self.assertEqual(self.snapshot(f),before)
                self.assertEqual(tx._inventory(f),owners)
    def test_changed_config_blocks(self):
        with er.rehearsal(self.archive) as f:
            tx._write(f,"installed","Game/ERVR/ERVR.ini",b"custom")
            with self.assertRaises(tx.TransactionBlocked): tx.build_plan(f)
    def test_foreign_target_blocks(self):
        with er.rehearsal(self.archive) as f:
            tx._write(f,"installed",sorted(er.ADD)[0],b"foreign")
            with self.assertRaises(tx.TransactionBlocked): tx.build_plan(f)
    def test_corrupt_backup_blocks_recovery(self):
        with er.rehearsal(self.archive) as f:
            with self.assertRaises(tx.SimulatedCrash): tx.execute(f,tx.build_plan(f),fault="after_replace:7")
            tx._write(f,"transaction","backup/Game/ERVR/ERVR.dll",b"corrupt")
            before=self.snapshot(f)
            with self.assertRaises(tx.RecoveryBlocked): tx.recover(f)
            self.assertEqual(self.snapshot(f),before)
    def test_bad_archive(self):
        with self.assertRaises(tx.TransactionBlocked): er.reviewed_payload(self.archive[:-1])

    def test_actual_schema_and_integrity_consumer(self):
        import copy,json
        from unittest.mock import patch
        from vrhub import hub,installed_integrity,installed_provenance,bepinex
        with er.rehearsal(self.archive) as f:
            base=f.root/"installed"
            statepath=base/"hub/state.json"
            before=json.loads(statepath.read_bytes())
            recipe=copy.deepcopy(hub.load_recipes()["elden-ring"])
            with patch.object(hub,"game_path",return_value=base):
                self.assertEqual(installed_integrity.verify(recipe,state=before)["status"],"Verified")
                tx.execute(f,tx.build_plan(f))
                after=json.loads(statepath.read_bytes())
                # Candidate recipe exists only in this test; shipped pin unchanged.
                candidate=copy.deepcopy(recipe)
                candidate["packages"][0]["sha256"]=er.RELEASE_SHA256
                candidate["packages"][0]["required_files"]=sorted(er.OWNED|er.ADD)
                candidate["archive_releases"]["ervr"]["pinned_tag"]="v0.9.2"
                result=installed_integrity.verify(candidate,state=after)
                self.assertEqual(result["status"],"Verified")
                self.assertEqual(result["checked"],17)
                self.assertEqual(installed_integrity.verify(recipe,state=after)["status"],"Unknown")
                record=after["elden-ring"]
                self.assertEqual(set(record["file_hashes"]),er.OWNED|er.ADD)
                self.assertEqual(set(record["files"]),set(record["packages"]["ervr"]["files"]))
                self.assertEqual(after["subnautica"],before["subnautica"])
                for key in ("backup","originals","original_hashes","retired"):
                    self.assertEqual(record[key],before["elden-ring"][key])
                self.assertEqual((base/"hub/backups/ervr-original/files/Game/ERVR/ERVR.ini").read_bytes(),b"previous backup")
                self.assertEqual(recipe["packages"][0]["sha256"],er.LEGACY_SHA256)
                # Current production uninstall allowlist does not cover new files.
                self.assertTrue(any(not bepinex.payload_path(n,"elden-ring") for n in er.ADD))
                tx.rollback(f)
                self.assertEqual(json.loads(statepath.read_bytes()),before)
                self.assertEqual(installed_integrity.verify(recipe,state=before)["status"],"Verified")
