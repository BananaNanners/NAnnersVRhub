# SPDX-License-Identifier: GPL-3.0-only
"""Independent process managed update interruption, fixture only."""
import dataclasses
import json
import subprocess
import sys
import unittest
from vrhub import bepinex_update_transaction as adapter, offline_transaction as tx, bepinex
from tests.test_bepinex_transaction_review import snapshot

CHILD = """
import json, os, sys
from pathlib import Path
from vrhub import offline_transaction as tx
f=tx.Fixture(Path(sys.argv[1]),sys.argv[2],True)
operation,fault=sys.argv[3:5]
try:
    if operation=="apply":
        # Reconstruct the parent's exact reviewed plan, not a newly approved plan.
        doc=json.loads(sys.stdin.read())
        doc["rows"]=tuple(doc["rows"])
        tx.execute(f,tx.Plan(**doc),fault=fault or None)
    elif operation=="recover":
        tx.recover(f,fault=fault or None)
    elif operation=="rollback":
        tx.rollback(f)
    else:
        raise ValueError("Unknown operation")
except tx.SimulatedCrash:
    os._exit(37)
except tx.RecoveryBlocked:
    os._exit(38)
except tx.TransactionBlocked:
    os._exit(39)
os._exit(0)
"""


class Cases:
    def child(self,f,p,operation,fault="",expected=0):
        result=subprocess.run([sys.executable,"-B","-c",CHILD,str(f.root),f.token,operation,fault],
                              input=json.dumps(dataclasses.asdict(p)),capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,expected,(operation,fault,result.stdout,result.stderr))

    def restored(self,f,before,owners):
        self.assertEqual(snapshot(f),before)
        self.assertEqual(tx._inventory(f),owners)
        self.assertFalse(tx.status(f)["authorized_live_install"])

    def test_apply_interruption_matrix(self):
        with adapter.rehearsal(self.game) as (f,p,_,_,_):
            count=len(p.before)
            self.assertEqual([r["action"] for r in p.rows],["delete","add","replace","replace"])
            self.assertEqual(p.rows[-1]["path"],"hub/state.json")
        points=("after_prepare_start","after_backup_file:1",f"after_backup_file:{count//2}",
                f"after_backup_file:{count}","after_stage_file:2","after_stage_file:3",
                "after_stage_file:4","after_backup","after_replace:1","after_replace:2",
                "after_replace:3","after_replace:4","after_all_files","after_inventory")
        for point in points:
            with self.subTest(point=point),adapter.rehearsal(self.game) as (f,p,_,_,_):
                before,owners=snapshot(f),tx._inventory(f)
                self.child(f,p,"apply",point,37)
                if point.startswith(("after_prepare","after_backup","after_stage")):
                    self.assertEqual(snapshot(f),before)
                if point=="after_backup":
                    for n,h in owners.items():
                        self.assertEqual(tx._sha(tx._read(f,"transaction","backup/"+n)),h)
                if point.startswith("after_replace:"):
                    progress=int(point.rsplit(":",1)[1])
                    for i,row in enumerate(p.rows,1):
                        data=tx._read(f,"installed",row["path"],optional=True)
                        self.assertEqual(None if data is None else tx._sha(data),
                                         row["new"] if i<=progress else row["old"])
                self.child(f,p,"recover")
                self.restored(f,before,owners)
                self.child(f,p,"recover")
                self.restored(f,before,owners)

    def test_interrupted_rollback_matrix(self):
        for point in ("after_rollback:1","after_rollback:2","after_rollback:3",
                      "after_rollback:4","after_directory_cleanup:1"):
            with self.subTest(point=point),adapter.rehearsal(self.game) as (f,p,_,_,_):
                before,owners=snapshot(f),tx._inventory(f)
                self.assertEqual(tx._verify_plan(f,p)["new_dirs"],["BepInEx/plugins/new-folder"])
                self.child(f,p,"apply","after_inventory",37)
                self.child(f,p,"recover",point,37)
                self.assertEqual(tx._read(f,"installed","hub/state.json"),before["hub/state.json"][1])
                self.child(f,p,"recover")
                self.restored(f,before,owners)

    def test_tampered_recovery_evidence(self):
        binding=bepinex.policy(self.game)["data"]+"/StreamingAssets/SteamVR/bindings_oculus_touch.json"
        original="hub/backups/"+self.game+"-"+"a"*32+"/files/winhttp.dll"
        for section,name in (("installed","hub/state.json"),("installed","BepInEx/plugins/update-test.dll"),
                             ("installed","BepInEx/plugins/obsolete-test.dll"),("installed","BepInEx/plugins/new-folder/new-test.dll"),
                             ("installed","BepInEx/config/BepInEx.cfg"),("installed",binding),
                             ("installed","prefix/save.dat"),("installed",original),
                             ("transaction","backup/hub/state.json"),("transaction","journal.json"),
                             ("transaction","inventory.json")):
            with self.subTest(section=section,name=name),adapter.rehearsal(self.game) as (f,p,_,_,_):
                self.child(f,p,"apply","after_inventory",37)
                tx._write(f,section,name,b"external edit")
                before=snapshot(f)
                self.child(f,p,"recover",expected=39 if name in ("journal.json","inventory.json") else 38)
                self.assertEqual(snapshot(f),before)

    def test_committed_requires_explicit_rollback(self):
        with adapter.rehearsal(self.game) as (f,p,_,_,_):
            before,owners=snapshot(f),tx._inventory(f)
            self.child(f,p,"apply")
            committed=snapshot(f)
            self.assertEqual(tx._inventory(f),p.after)
            self.assertEqual(tx._sha(committed["hub/state.json"][1]),p.after["hub/state.json"])
            self.child(f,p,"recover",expected=38)
            self.assertEqual(snapshot(f),committed)
            self.child(f,p,"rollback")
            self.restored(f,before,owners)

    def test_child_rejects_stale_parent_plan(self):
        for section,name in (("incoming","hub/state.json"),("incoming","BepInEx/plugins/update-test.dll"),
                             ("installed","prefix/save.dat"),("installed","BepInEx/plugins/new-folder/new-test.dll")):
            with self.subTest(section=section,name=name),adapter.rehearsal(self.game) as (f,p,_,_,_):
                tx._write(f,section,name,b"external edit")
                before=snapshot(f)
                self.child(f,p,"apply",expected=39)
                self.assertEqual(snapshot(f),before)
                self.assertEqual(tx.status(f)["phase"],"unstarted")


class Subnautica(Cases,unittest.TestCase):
    game="subnautica"


class Valheim(Cases,unittest.TestCase):
    game="valheim"
