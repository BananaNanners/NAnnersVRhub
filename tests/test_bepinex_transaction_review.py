# SPDX-License-Identifier: GPL-3.0-only
import unittest
from vrhub import bepinex_transaction_review as adapter, offline_transaction as tx


def snapshot(f):
    root=f.root/"installed"
    return {str(p.relative_to(root)):(p.stat().st_mode,p.read_bytes() if p.is_file() else None)
            for p in root.rglob("*")}


class Cases:
    def test_backup_commit_rollback(self):
        with adapter.rehearsal(self.game) as (f,plan,review):
            before=snapshot(f)
            result=tx.execute(f,plan)
            self.assertFalse(result["authorized_live_install"])
            self.assertEqual(result["fresh_backup_verified"],len(plan.before))
            for n,h in plan.before.items():
                self.assertEqual(tx._sha(tx._read(f,"transaction","backup/"+n)),h)
            after=snapshot(f)
            changed={r["path"] for r in plan.rows}
            for n,v in before.items():
                if n not in changed:
                    self.assertEqual(after[n],v,n)
            tx.rollback(f)
            self.assertEqual(snapshot(f),before)

    def test_stale_current_and_incoming(self):
        for section,name in (("installed","hub/state.json"),("installed","winhttp.dll"),
                             ("installed","prefix/save.dat"),("incoming","winhttp.dll"),
                             ("installed","BepInEx/core/BepInEx.dll")):
            with self.subTest(section=section,name=name), adapter.rehearsal(self.game) as (f,p,_):
                tx._write(f,section,name,b"unexpected")
                before=snapshot(f)
                with self.assertRaises(tx.TransactionBlocked):
                    tx.execute(f,p)
                self.assertEqual(snapshot(f),before)
                self.assertEqual(tx.status(f)["phase"],"unstarted")

    def test_verified_backup_before_apply(self):
        with adapter.rehearsal(self.game) as (f,p,_):
            before=snapshot(f)
            with self.assertRaises(tx.SimulatedCrash):
                tx.execute(f,p,fault="after_backup")
            self.assertEqual(snapshot(f),before)
            for n,h in p.before.items():
                self.assertEqual(tx._sha(tx._read(f,"transaction","backup/"+n)),h)
            tx.recover(f)
            self.assertEqual(snapshot(f),before)


class Subnautica(Cases,unittest.TestCase):
    game="subnautica"


class Valheim(Cases,unittest.TestCase):
    game="valheim"


class Scope(unittest.TestCase):
    def test_other_game_refused(self):
        with self.assertRaises(tx.TransactionBlocked):
            with adapter.rehearsal("elden-ring"):
                pass
