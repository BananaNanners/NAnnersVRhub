# SPDX-License-Identifier: GPL-3.0-only
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from vrhub import hub, bepinex_update_review as review
from tests.test_archive_releases import release


class ReviewTests(unittest.TestCase):
    def check_game(self, game, role, tag, name, marker):
        recipe = hub.load_recipes()[game]
        pkg = next(p for p in recipe["packages"] if p["id"] == role)
        source = recipe["archive_releases"][role]
        state = {game:{"installer":marker,"packages":{role:{"sha256":pkg["sha256"],"files":["/fixture/mod.dll"]}}}}
        original = copy.deepcopy((recipe,state))
        old = release(source["pinned_tag"],1,b"old",name)
        old["assets"][0]["digest"] = "sha256:"+pkg["sha256"]
        latest = release(tag,2,b"new",name)
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/name).write_bytes(b"new")
            def fetch(repo):
                return [old,latest] if repo==source["repo"] else []
            def row():
                result=review.review(recipe,folder,state,fetch=fetch)
                self.assertFalse(result["write_authorized"])
                return next(r for r in result["rows"] if r["id"]==role)
            r=row()
            self.assertEqual(r["installed_version"],source["pinned_tag"])
            self.assertEqual(r["pinned_version"],source["pinned_tag"])
            self.assertEqual(r["candidate"]["tag"],tag)
            self.assertEqual(r["candidate"]["sha256"],hashlib.sha256(b"new").hexdigest())
            self.assertFalse(r["installed_bytes_verified"])
            self.assertFalse(r["compatibility_verified"])
            self.assertFalse(r["write_authorized"])
            (folder/name).write_bytes(b"tampered")
            self.assertIsNone(row()["candidate"])
            latest["assets"][0]["digest"]=None
            self.assertEqual(row()["candidate_status"],"Official digest unavailable")
            self.assertEqual((recipe,state),original)

    def test_subnautica(self):
        self.check_game("subnautica","submersedvr","0.2.2","SubmersedVR_0.2.2.zip","submersed-vr-1")

    def test_valheim(self):
        self.check_game("valheim","vhvr","v0.11.3","vhvr.zip","vhvr-1")

    def test_manual_and_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            def unavailable(repo):
                raise OSError("offline")
            rows=review.review(hub.load_recipes()["valheim"],Path(tmp),{},fetch=unavailable)["rows"]
            self.assertEqual(rows[0]["candidate_status"],"Manual release review")
            self.assertEqual(rows[1]["candidate_status"],"Release metadata unavailable")
            self.assertTrue(all(r["installed_version"] is None and r["candidate"] is None for r in rows))

    def test_other_game_refused(self):
        with self.assertRaises(ValueError):
            review.review(hub.load_recipes()["elden-ring"],Path("/unused"),{})
