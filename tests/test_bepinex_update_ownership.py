# SPDX-License-Identifier: GPL-3.0-only
import json
import unittest
from pathlib import Path
from vrhub import bepinex_update_transaction as adapter, offline_transaction as tx, bepinex_recognition as recognition
from tests.test_bepinex_transaction_review import snapshot


class Cases:
    def test_publication_and_rollback(self):
        with adapter.rehearsal(self.game) as (f,p,r,execute,candidate):
            before=snapshot(f)
            old=json.loads(before["hub/state.json"][1])
            self.assertEqual(p.rows[-1]["path"],"hub/state.json")
            execute()
            after=json.loads(tx._read(f,"installed","hub/state.json"))
            record=after[self.game]
            role="submersedvr" if self.game=="subnautica" else "vhvr"
            self.assertEqual(after["unrelated-game"],old["unrelated-game"])
            for key in ("backup","originals","original_hashes","retired","installer","keep"):
                self.assertEqual(record[key],old[self.game][key])
            self.assertEqual(record["packages"]["loader"],old[self.game]["packages"]["loader"])
            self.assertEqual(record["packages"][role]["sha256"],tx._sha(candidate.read_bytes()))
            self.assertEqual(record["packages"][role]["archive"],candidate.name)
            self.assertEqual(record["installed_at"],2)
            expected={row["path"]:row["new_sha256"] for row in r["rows"] if row["action"]!="Remove"}
            self.assertEqual(record["file_hashes"],expected)
            self.assertEqual(set(record["files"]),{str(f.root/"installed"/n) for n in expected})
            self.assertEqual(set(record["packages"][role]["files"]),{str(f.root/"installed"/row["path"]) for row in r["rows"] if row["component"]==role and row["action"]!="Remove"})
            for row in r["rows"]:
                if row["action"]=="Preserve":
                    self.assertEqual(tx._read(f,"installed",row["path"]),before[row["path"]][1])
                    if recognition.protected_setting(row["path"]):
                        self.assertEqual(record["file_hashes"][row["path"]],row["old_sha256"])
            tx.rollback(f)
            self.assertEqual(snapshot(f),before)
            self.assertEqual(tx._inventory(f),p.before)

    def test_interrupted_publication(self):
        for fault in ("after_replace:3","after_replace:4","after_inventory"):
            with self.subTest(fault=fault),adapter.rehearsal(self.game) as (f,p,r,execute,_):
                before=snapshot(f)
                with self.assertRaises(tx.SimulatedCrash):
                    execute(fault=fault)
                current=tx._read(f,"installed","hub/state.json")
                if fault=="after_replace:3":
                    self.assertEqual(current,before["hub/state.json"][1])
                else:
                    self.assertEqual(tx._sha(current),p.after["hub/state.json"])
                tx.recover(f)
                self.assertEqual(snapshot(f),before)
                self.assertEqual(tx._inventory(f),p.before)

    def test_tampered_publication_refused(self):
        with adapter.rehearsal(self.game) as (f,p,r,execute,_):
            tx._write(f,"incoming","hub/state.json",b'{}')
            before=snapshot(f)
            with self.assertRaises(tx.TransactionBlocked):
                execute()
            self.assertEqual(snapshot(f),before)
            self.assertEqual(tx.status(f)["phase"],"unstarted")


class Subnautica(Cases,unittest.TestCase):
    game="subnautica"


class Valheim(Cases,unittest.TestCase):
    game="valheim"
