# SPDX-License-Identifier: GPL-3.0-only
import unittest
from vrhub import bepinex_update_transaction as adapter, offline_transaction as tx
from tests.test_bepinex_transaction_review import snapshot


class Cases:
    def test_verified_backup_and_rollback(self):
        with adapter.rehearsal(self.game) as (f,p,r,execute,_):
            before=snapshot(f)
            inventory=tx._inventory(f)
            with self.assertRaises(tx.SimulatedCrash):
                execute(fault="after_backup")
            self.assertEqual(snapshot(f),before)
            for name,digest in p.before.items():
                self.assertEqual(tx._sha(tx._read(f,"transaction","backup/"+name)),digest)
            tx.recover(f)
            self.assertEqual(snapshot(f),before)
            self.assertEqual(tx._inventory(f),inventory)

    def test_commit_and_rollback(self):
        with adapter.rehearsal(self.game) as (f,p,r,execute,_):
            before=snapshot(f)
            result=execute()
            self.assertFalse(result["authorized_live_install"])
            self.assertEqual(result["fresh_backup_verified"],len(p.before))
            self.assertEqual(tx._inventory(f),p.after)
            after=snapshot(f)
            changes={row["path"] for row in p.rows}
            for n,v in before.items():
                if n not in changes:
                    self.assertEqual(after[n],v)
            for row in p.rows:
                n=row["path"]
                if row["action"]=="delete":
                    self.assertNotIn(n,after)
                else:
                    self.assertEqual(tx._sha(after[n][1]),row["new"])
            tx.rollback(f)
            self.assertEqual(snapshot(f),before)
            self.assertEqual(tx._inventory(f),p.before)

    def test_stale_review_or_plan(self):
        for section,name in (("installed","hub/state.json"),("installed","prefix/save.dat"),
                             ("incoming","BepInEx/plugins/update-test.dll"),
                             ("installed","BepInEx/plugins/new-folder/new-test.dll"),
                             ("archive","")):
            with self.subTest(section=section,name=name), adapter.rehearsal(self.game) as (f,p,r,execute,candidate):
                if section=="archive":
                    candidate.write_bytes(b"tampered")
                else:
                    tx._write(f,section,name,b"tampered")
                before=snapshot(f)
                with self.assertRaises(tx.TransactionBlocked):
                    execute()
                self.assertEqual(snapshot(f),before)
                self.assertEqual(tx.status(f)["phase"],"unstarted")


class Subnautica(Cases,unittest.TestCase):
    game="subnautica"


class Valheim(Cases,unittest.TestCase):
    game="valheim"


class Scope(unittest.TestCase):
    def test_other_game_refused(self):
        with self.assertRaises(tx.TransactionBlocked):
            with adapter.rehearsal("elden-ring"):
                pass
