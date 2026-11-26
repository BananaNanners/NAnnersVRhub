import unittest
from pathlib import Path
from unittest.mock import Mock
from vrhub import hub, updates, bepinex

class ErvrReleaseReview(unittest.TestCase):
    def setUp(self):
        self.recipe = hub.load_recipes()["elden-ring"]
    def check(self, tag="v0.9.2", state=None):
        fetch = Mock(return_value={"tag":tag,"published":"2026-11-16T14:36:19Z",
            "url":"https://github.com/IlyaMez/EldenringVR/releases/tag/"+tag})
        nexus = Mock(side_effect=AssertionError("Nexus must not be queried"))
        rows = updates.check_recipe(self.recipe, state or {}, fetch=fetch, nexus_fetch=nexus, nexus_key=None)
        fetch.assert_called_once_with("IlyaMez/EldenringVR")
        nexus.assert_not_called()
        self.assertEqual(len(rows),1)
        return rows[0]
    def test_new_release_review_without_install_claim(self):
        for state in ({},{"elden-ring":{"installed_at":9999999999}}):
            row=self.check(state=state)
            self.assertEqual(row["status"],"unknown")
            self.assertTrue(row["newer_release"])
            self.assertNotIn("installed_version",row)
            self.assertEqual(updates.release_count([row]),1)
    def test_equal_older_or_unparseable_not_current(self):
        for tag in ("v0.4.0","v0.3.0","nightly"):
            row=self.check(tag)
            self.assertEqual(row["status"],"unknown")
            self.assertFalse(row["newer_release"])
    def test_failure_is_not_current(self):
        row=updates.check_recipe(self.recipe,{},fetch=Mock(side_effect=OSError("offline")))[0]
        self.assertEqual(row["status"],"error")
    def test_install_pin_unchanged(self):
        self.assertEqual(self.recipe["packages"][0]["sha256"],"851221c337d2a365df547b34435246486f4e390a77999b1fe712e764ef33a21a")
        self.assertEqual(set(self.recipe["packages"][0]["required_files"]),bepinex.ERVR_FILES)

class ErvrArchiveRecognition(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.recipe=hub.load_recipes()["elden-ring"]
        self.source=self.recipe["archive_releases"]["ervr"]
    def catalog(self, *items):
        from vrhub import archive_releases
        return archive_releases.asset_catalog(self.source,list(items))
    def release(self, tag="v0.9.2", data=b"new", name=None):
        import hashlib
        return {"tag_name":tag,"published_at":"2026-11-16T14:36:19Z",
                "draft":False,"prerelease":False,"assets":[
                {"name":name or f"ERVR-{tag}.zip","size":len(data),
                 "digest":"sha256:"+hashlib.sha256(data).hexdigest()}]}
    def test_missing_public_baseline_recognizes_newer(self):
        c=self.catalog(self.release())
        self.assertTrue(c["newer_than_pin"])
        self.assertEqual(c["expected"],"v0.9.2")
    def test_exact_tag_asset_and_stable_only(self):
        draft=self.release("v1.0.0"); draft["draft"]=True
        pre=self.release("v2.0.0"); pre["prerelease"]=True
        c=self.catalog(self.release(),draft,pre,self.release("v3.0.0",name="ERVR-v0.9.2.zip"),
                       self.release("v4.0.0",name="ERVR-v4.0.0.zip.sha256"))
        self.assertEqual(len(c["assets"]),1)
    def test_newer_digest_review_only_even_renamed_with_old_pin(self):
        import hashlib
        from vrhub import download_planner as planner
        old=self.folder/"old.zip"; old.write_bytes(b"old")
        self.recipe["packages"][0]["sha256"]=hashlib.sha256(b"old").hexdigest()
        new=self.folder/"renamed.zip"; new.write_bytes(b"new")
        plan=planner.build_plan(self.recipe,self.folder,release_catalogs={"ervr":self.catalog(self.release())})
        row=plan["rows"][0]
        self.assertEqual(row["file"],str(new))
        self.assertTrue(row["release_review"])
        self.assertEqual(row["status"],"Hash mismatch — do not install")
        self.assertEqual(plan["verified"],0)
    def test_missing_digest_and_wrong_bytes_never_promoted(self):
        from vrhub import download_planner as planner
        p=self.folder/"ERVR-v0.9.2.zip"; p.write_bytes(b"wrong")
        for release in (self.release(),self.release(data=b"wrong")):
            if release["assets"][0]["size"]==5:
                release["assets"][0]["digest"]=None
            row=planner.build_plan(self.recipe,self.folder,release_catalogs={"ervr":self.catalog(release)})["rows"][0]
            self.assertFalse(row.get("release_review"))
            self.assertEqual(row["status"],"Hash mismatch — do not install")
