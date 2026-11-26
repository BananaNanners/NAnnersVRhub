# SPDX-License-Identifier: GPL-3.0-only
"""Full genuine pinned baseline with synthetic candidate; no live destination."""
import os
import json
from collections import Counter
from pathlib import Path
from unittest.mock import patch
import unittest
from vrhub import bepinex_update_transaction as adapter, offline_transaction as tx, hub, bepinex, bepinex_recognition as recognition
from tests.test_bepinex_transaction_review import snapshot
from tests.test_bepinex_update_durable import Cases as DurableCases


class Cases:
    def rehearsal(self):
        root=os.environ.get("NANNERS_TEST_BEPINEX_ARCHIVES")
        if not root:
            self.skipTest("Explicit pinned archive fixture source required.")
        paths=tuple(sorted((Path(root)/self.folder).glob("*.zip")))
        return adapter.rehearsal(self.game,pinned_archives=paths)

    def test_full_commit_and_exact_rollback(self):
        with self.rehearsal() as (f,p,r,execute,candidate):
            before=snapshot(f)
            old=json.loads(before["hub/state.json"][1])
            self.assertEqual(len(old[self.game]["file_hashes"]),self.count)
            self.assertEqual(len(p.before),self.count+5)
            self.assertEqual(Counter(row["action"] for row in r["rows"]),
                             {"Preserve":self.count-2,"Install":1,"Replace":1,"Remove":1})
            result=execute()
            self.assertFalse(result["authorized_live_install"])
            self.assertEqual(result["fresh_backup_verified"],len(before.keys() & p.before.keys()))
            for n,h in p.before.items():
                self.assertEqual(tx._sha(tx._read(f,"transaction","backup/"+n)),h)
            after=snapshot(f)
            changed={row["path"] for row in p.rows}
            for n,v in before.items():
                if n not in changed:
                    self.assertEqual(after[n],v,n)
            for row in p.rows:
                if row["action"]=="delete":
                    self.assertNotIn(row["path"],after)
                else:
                    self.assertEqual(tx._sha(after[row["path"]][1]),row["new"])
            state=json.loads(after["hub/state.json"][1])
            rec=state[self.game]
            self.assertEqual(state["unrelated-game"],old["unrelated-game"])
            for key in ("backup","originals","original_hashes","retired","installer","keep"):
                self.assertEqual(rec[key],old[self.game][key])
            self.assertEqual(rec["packages"]["loader"],old[self.game]["packages"]["loader"])
            role="submersedvr" if self.game=="subnautica" else "vhvr"
            self.assertEqual(rec["packages"][role]["sha256"],tx._sha(candidate.read_bytes()))
            self.assertEqual(rec["file_hashes"],{row["path"]:row["new_sha256"] for row in r["rows"] if row["action"]!="Remove"})
            self.assertEqual(set(rec["files"]),{str(f.root/"installed"/n) for n in rec["file_hashes"]})
            # Independently recognize the resulting record using a private
            # candidate-pinned recipe and the original loader archive.
            recipe=hub.load_recipes()[self.game]
            source=Path(os.environ["NANNERS_TEST_BEPINEX_ARCHIVES"])/self.folder
            loader=next(x for x in source.glob("*.zip") if tx._sha(x.read_bytes())==rec["packages"]["loader"]["sha256"])
            next(pkg for pkg in recipe["packages"] if pkg["id"]==role)["sha256"]=rec["packages"][role]["sha256"]
            base=f.root/"installed"
            with patch.object(hub,"game_path",return_value=base),patch.object(hub,"state_file",return_value=base/"hub/state.json"),patch.object(hub,"state",return_value=state):
                evidence=recognition.recognize(recipe,(loader,candidate))
            self.assertEqual(evidence["ownership_record"],"consistent-record",evidence)
            self.assertEqual(evidence["backup_status"],"originals-match")
            self.assertEqual(len(evidence["rows"]),self.count)
            self.assertFalse(evidence["write_authorized"])
            tx.rollback(f)
            self.assertEqual(snapshot(f),before)
            self.assertEqual(tx._inventory(f),p.before)

    def test_full_persistent_recovery(self):
        for point in ("after_backup_file:1","after_backup","after_replace:1","after_replace:2","after_replace:3","after_replace:4","after_inventory"):
            with self.subTest(point=point),self.rehearsal() as (f,p,r,execute,candidate):
                before,owners=snapshot(f),tx._inventory(f)
                self.child(f,p,"apply",point,37)
                if point.startswith("after_backup"):
                    self.assertEqual(snapshot(f),before)
                if point=="after_backup":
                    for n,h in owners.items():
                        self.assertEqual(tx._sha(tx._read(f,"transaction","backup/"+n)),h)
                self.child(f,p,"recover")
                self.restored(f,before,owners)
                self.child(f,p,"recover")
                self.restored(f,before,owners)

    def test_full_interrupted_rollback_and_tamper(self):
        for point in ("after_rollback:1","after_rollback:4","after_directory_cleanup:1"):
            with self.subTest(point=point),self.rehearsal() as (f,p,r,execute,candidate):
                before,owners=snapshot(f),tx._inventory(f)
                self.child(f,p,"apply","after_inventory",37)
                self.child(f,p,"recover",point,37)
                self.assertEqual(tx._read(f,"installed","hub/state.json"),before["hub/state.json"][1])
                self.child(f,p,"recover")
                self.restored(f,before,owners)
        with self.rehearsal() as (f,p,r,execute,candidate):
            self.child(f,p,"apply","after_inventory",37)
            tx._write(f,"transaction","backup/hub/state.json",b"tampered")
            before=snapshot(f)
            self.child(f,p,"recover",expected=38)
            self.assertEqual(snapshot(f),before)

    def test_full_stale_archive(self):
        with self.rehearsal() as (f,p,r,execute,candidate):
            candidate.write_bytes(b"tampered")
            before=snapshot(f)
            with self.assertRaises(tx.TransactionBlocked):
                execute()
            self.assertEqual(snapshot(f),before)
            self.assertEqual(tx.status(f)["phase"],"unstarted")

    child=DurableCases.child
    restored=DurableCases.restored


class Subnautica(Cases,unittest.TestCase):
    game="subnautica"
    folder="Subnautica"
    count=45


class Valheim(Cases,unittest.TestCase):
    game="valheim"
    folder="Valheim"
    count=135
