"""Exercise existing removal only inside private transaction fixtures.
Candidate allowlist is scoped to tests; never exported to production.
"""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from vrhub import ervr_transaction_review as er, offline_transaction as tx, bepinex, hub

class ErvrLifecycleReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        archive=os.getenv("NANNERS_TEST_ERVR_ARCHIVE")
        if not archive:
            raise unittest.SkipTest("Explicit ERVR archive fixture not supplied")
        cls.archive=Path(archive).read_bytes()

    def snapshot(self,root):
        return {str(p.relative_to(root)): (p.stat().st_mode,p.read_bytes() if p.is_file() else None)
                for p in root.rglob("*") if p.is_file() or p.is_dir()}

    def remove(self,f,*,candidate=True):
        base=tx._assert_fixture(f)/"installed"
        state=base/"hub/state.json"
        original=bepinex.payload_path
        def allowed(name,rid):
            return name in er.OWNED|er.ADD if rid=="elden-ring" and candidate else original(name,rid)
        # Existing writer is called only against internally generated paths.
        with patch.object(hub,"state_file",return_value=state),patch.object(bepinex,"payload_path",side_effect=allowed):
            return bepinex.uninstall("elden-ring")

    def test_candidate_removal_and_original_restore(self):
        with er.rehearsal(self.archive) as f:
            tx.execute(f,tx.build_plan(f))
            base=f.root/"installed"
            state=json.loads((base/"hub/state.json").read_bytes())
            record=state["elden-ring"]
            backup=Path(record["backup"])
            backup_before=self.snapshot(backup)
            config=base/"Game/ERVR/ERVR.ini"
            config.write_bytes(b"custom controller settings")
            (base/"Game/ERVR/ERVR.log").write_bytes(b"runtime log")
            removed=self.remove(f)
            self.assertEqual(len(removed),17)
            self.assertEqual(config.read_bytes(),b"previous backup")
            self.assertEqual((backup/"user-modified/Game/ERVR/ERVR.ini").read_bytes(),b"custom controller settings")
            for name,entry in backup_before.items():
                self.assertEqual(self.snapshot(backup)[name],entry)
            for n in (er.OWNED|er.ADD)-{"Game/ERVR/ERVR.ini"}:
                self.assertFalse((base/n).exists())
            self.assertFalse((base/er.EXCLUDE).exists())
            self.assertEqual((base/"Game/ERVR/ERVR.log").read_bytes(),b"runtime log")
            self.assertEqual((base/"prefix/save.sl2").read_bytes(),b"synthetic save")
            self.assertEqual((base/"Game/unrelated.txt").read_bytes(),b"foreign mod sentinel")
            self.assertEqual(json.loads((base/"hub/state.json").read_bytes()),{"subnautica":state["subnautica"]})

    def test_production_allowlist_still_blocks(self):
        with er.rehearsal(self.archive) as f:
            tx.execute(f,tx.build_plan(f))
            base=f.root/"installed"
            before=self.snapshot(base/"Game")
            with self.assertRaisesRegex(RuntimeError,"inventory paths"):
                self.remove(f,candidate=False)
            self.assertEqual(self.snapshot(base/"Game"),before)

    def test_refusals(self):
        for fault in ("binary","backup","inventory","foreign-path"):
            with self.subTest(fault=fault),er.rehearsal(self.archive) as f:
                tx.execute(f,tx.build_plan(f))
                base=f.root/"installed";sp=base/"hub/state.json"
                s=json.loads(sp.read_bytes());r=s["elden-ring"]
                if fault=="binary": (base/"Game/ERVR/bhaptics_library.dll").write_bytes(b"changed")
                elif fault=="backup": (Path(r["backup"])/"files/Game/ERVR/ERVR.ini").write_bytes(b"corrupt")
                elif fault=="inventory":
                    r["files"].pop();sp.write_text(json.dumps(s))
                else:
                    r["file_hashes"]["Game/eldenring.exe"]="0"*64;sp.write_text(json.dumps(s))
                before=self.snapshot(base/"Game");raw=sp.read_bytes()
                with self.assertRaises(RuntimeError): self.remove(f)
                self.assertEqual(self.snapshot(base/"Game"),before)
                self.assertEqual(sp.read_bytes(),raw)

    def test_publication_failure_restores_payload(self):
        with er.rehearsal(self.archive) as f:
            tx.execute(f,tx.build_plan(f))
            base=f.root/"installed"
            before=self.snapshot(base/"Game");raw=(base/"hub/state.json").read_bytes()
            with patch.object(bepinex,"_save",side_effect=OSError("fixture publication failure")):
                with self.assertRaises(OSError): self.remove(f)
            self.assertEqual(self.snapshot(base/"Game"),before)
            self.assertEqual((base/"hub/state.json").read_bytes(),raw)
