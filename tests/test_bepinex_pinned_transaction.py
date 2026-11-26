# SPDX-License-Identifier: GPL-3.0-only
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from vrhub import bepinex_transaction_review as adapter, offline_transaction as tx, hub, bepinex_repair_review
from tests.test_bepinex_transaction_review import snapshot


class Cases:
    def setUp(self):
        root=os.environ.get("NANNERS_TEST_BEPINEX_ARCHIVES")
        if not root:
            self.skipTest("Explicit pinned archive library required.")
        self.archives=sorted((Path(root)/self.folder).glob("*.zip"))

    def test_complete_pinned_backup_and_rollback(self):
        with adapter.pinned_rehearsal(self.game,self.archives) as (f,p,r):
            before=snapshot(f)
            self.assertEqual(len(r["rows"]),self.count)
            owners=tx._inventory(f)
            result=tx.execute(f,p)
            self.assertEqual(result["fresh_backup_verified"],len(owners))
            for n,h in owners.items():
                self.assertEqual(tx._sha(tx._read(f,"transaction","backup/"+n)),h)
            after=snapshot(f)
            for n,v in before.items():
                if n not in {row["path"] for row in p.rows}:
                    self.assertEqual(after[n],v,n)
            for row in p.rows:
                self.assertEqual(tx._sha(tx._read(f,"installed",row["path"])),row["new"])
            tx.rollback(f)
            self.assertEqual(snapshot(f),before)
            self.assertEqual(tx._inventory(f),owners)
            print("PINNED",self.game,"inventory",len(r["rows"]),"backup",len(owners),flush=True)

    def test_real_schema_drift_blocks_review(self):
        with adapter.pinned_rehearsal(self.game,self.archives) as (f,p,r):
            base=f.root/"installed"
            state=base/"hub/state.json"
            record=json.loads(state.read_bytes())
            record[self.game]["file_hashes"]["winhttp.dll"]="0"*64
            tx._write(f,"installed","hub/state.json",json.dumps(record).encode())
            before=snapshot(f)
            with patch.object(hub,"game_path",return_value=base),patch.object(hub,"state_file",return_value=state):
                review=bepinex_repair_review.review(hub.load_recipes()[self.game],self.archives)
            self.assertEqual(review["status"],"Blocked")
            self.assertEqual(review["ownership_record"],"inconsistent")
            with self.assertRaises(tx.TransactionBlocked):
                tx.execute(f,p)
            self.assertEqual(snapshot(f),before)


class Subnautica(Cases,unittest.TestCase):
    game="subnautica"
    folder="Subnautica"
    count=45


class Valheim(Cases,unittest.TestCase):
    game="valheim"
    folder="Valheim"
    count=135
