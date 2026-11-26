import hashlib,json,os,subprocess,sys,unittest
from pathlib import Path
from vrhub import ervr_transaction_review as er,offline_transaction as tx
from tests.test_ervr_durable_review import UPDATE_CHILD

class DurableRemoval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=os.getenv("NANNERS_TEST_ERVR_ARCHIVE")
        if not p: raise unittest.SkipTest("Explicit verified ERVR archive required")
        cls.archive=Path(p).read_bytes()
    def snapshot(self,f):
        root=f.root/"installed"
        return {str(p.relative_to(root)):(p.stat().st_mode,hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None) for p in root.rglob("*")}
    def test_commit_restore_and_explicit_rollback(self):
        with er.removal_rehearsal(self.archive) as f:
            base=f.root/"installed"
            (base/"Game/ERVR/ERVR.dll").chmod(0o640)
            before=self.snapshot(f);owners=tx._inventory(f)
            plan=tx.build_plan(f)
            self.assertEqual(sum(r["action"]=="delete" for r in plan.rows),16)
            self.assertEqual(plan.rows[-1]["path"],"hub/state.json")
            self.assertFalse(tx.execute(f,plan)["authorized_live_install"])
            self.assertEqual((base/"Game/ERVR/ERVR.ini").read_bytes(),b"previous backup")
            self.assertNotIn("elden-ring",json.loads((base/"hub/state.json").read_bytes()))
            for n in er.CONFIG:
                self.assertEqual(hashlib.sha256((base/"hub/backups/ervr-original/removal-preserved"/n).read_bytes()).hexdigest(),before[n][1])
            for n in (er.OWNED|er.ADD)-{"Game/ERVR/ERVR.ini"}:
                self.assertFalse((base/n).exists())
            for n in ("Game/eldenring.exe","Game/unrelated.txt","prefix/save.sl2","hub/backups/ervr-original/files/Game/ERVR/ERVR.ini"):
                self.assertEqual(self.snapshot(f)[n],before[n])
            tx.rollback(f)
            self.assertEqual(self.snapshot(f),before)
            self.assertEqual(tx._inventory(f),owners)
    def test_child_interruption(self):
        for point in ("after_backup_file:3","after_backup","after_replace:1","after_replace:8","after_replace:16","after_all_files","after_inventory"):
            with self.subTest(point=point),er.removal_rehearsal(self.archive) as f:
                before=self.snapshot(f);owners=tx._inventory(f)
                result=subprocess.run([sys.executable,"-B","-c",UPDATE_CHILD,str(f.root),f.token,point],capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,37,result.stderr)
                tx.recover(f)
                self.assertEqual(self.snapshot(f),before)
                self.assertEqual(tx._inventory(f),owners)
    def test_reappearing_deleted_file_blocks(self):
        with er.removal_rehearsal(self.archive) as f:
            plan=tx.build_plan(f)
            with self.assertRaises(tx.SimulatedCrash): tx.execute(f,plan,fault="after_replace:1")
            tx._write(f,"installed",plan.rows[0]["path"],b"unexpected user file")
            before=self.snapshot(f)
            with self.assertRaises(tx.RecoveryBlocked): tx.recover(f)
            self.assertEqual(self.snapshot(f),before)
    def test_foreign_deletion_refused(self):
        with self.assertRaises(tx.TransactionBlocked):
            with tx.fixture_sandbox({"foreign":b"x"},{},managed=(),delete=("foreign",)): pass
