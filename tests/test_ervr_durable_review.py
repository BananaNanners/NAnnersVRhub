"""Process-boundary evidence, including the known legacy removal recovery gap."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from vrhub import ervr_transaction_review as er, offline_transaction as tx

UPDATE_CHILD = '''
import os,sys
from pathlib import Path
from vrhub import offline_transaction as tx
f=tx.Fixture(Path(sys.argv[1]),sys.argv[2])
try:
    tx.execute(f,tx.build_plan(f),fault=sys.argv[3])
except tx.SimulatedCrash:
    os._exit(37)
os._exit(99)
'''
REMOVE_CHILD = '''
import os,sys
from pathlib import Path
from unittest.mock import patch
from vrhub import offline_transaction as tx, ervr_transaction_review as er, hub,bepinex
f=tx.Fixture(Path(sys.argv[1]),sys.argv[2])
base=tx._assert_fixture(f)/"installed"
state=base/"hub/state.json"
original=bepinex._save
def publish(s):
    if sys.argv[3]=="after-publication":
        original(s)
    os._exit(38)
with patch.object(hub,"state_file",return_value=state),patch.object(bepinex,"payload_path",side_effect=lambda n,r: r=="elden-ring" and n in er.OWNED|er.ADD),patch.object(bepinex,"_save",side_effect=publish):
    bepinex.uninstall("elden-ring")
os._exit(99)
'''
class ErvrDurableReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=os.getenv("NANNERS_TEST_ERVR_ARCHIVE")
        if not p: raise unittest.SkipTest("Explicit ERVR archive required")
        cls.archive=Path(p).read_bytes()
    def snapshot(self,f):
        root=f.root/"installed"
        return {str(p.relative_to(root)):(p.stat().st_mode,hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None) for p in root.rglob("*")}
    def child(self,f,code,point,expected):
        result=subprocess.run([sys.executable,"-B","-c",code,str(f.root),f.token,point],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,expected,(result.stdout,result.stderr))
    def test_update_process_exit_recovery(self):
        for point in ("after_backup_file:3","after_stage_file:4","after_backup","after_replace:7","after_all_files","after_inventory"):
            with self.subTest(point=point),er.rehearsal(self.archive) as f:
                before=self.snapshot(f);owners=tx._inventory(f)
                self.child(f,UPDATE_CHILD,point,37)
                tx.recover(f)
                self.assertEqual(self.snapshot(f),before)
                self.assertEqual(tx._inventory(f),owners)
                self.assertFalse(tx.recover(f)["authorized_live_install"])
    def test_legacy_removal_process_exit_gap(self):
        # Document the gap, not an acceptance test for durable removal.
        for point in ("before-publication","after-publication"):
            with self.subTest(point=point),er.rehearsal(self.archive) as f:
                tx.execute(f,tx.build_plan(f))
                base=f.root/"installed"
                raw=(base/"hub/state.json").read_bytes()
                backup=base/"hub/backups/ervr-original/files/Game/ERVR/ERVR.ini"
                original=backup.read_bytes()
                self.child(f,REMOVE_CHILD,point,38)
                self.assertFalse((base/"Game/ERVR/ERVR.dll").exists())
                self.assertEqual(backup.read_bytes(),original)
                self.assertEqual((base/"Game/ERVR/ERVR.ini").read_bytes(),original)
                state=json.loads((base/"hub/state.json").read_bytes())
                if point=="before-publication":
                    self.assertEqual((base/"hub/state.json").read_bytes(),raw)
                    self.assertIn("elden-ring",state)
                else:
                    self.assertNotIn("elden-ring",state)
                self.assertEqual(tx.status(f)["phase"],"committed")
                with self.assertRaises(tx.RecoveryBlocked): tx.recover(f)
                print("LEGACY REMOVAL GAP",point,"no removal journal",flush=True)
