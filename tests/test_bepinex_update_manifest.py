# SPDX-License-Identifier: GPL-3.0-only
import copy
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from vrhub import hub, bepinex, bepinex_update_manifest as manifest
from tests.test_archive_releases import release


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ManifestTests(unittest.TestCase):
    def exercise(self, game, role, tag, filename):
        recipe = copy.deepcopy(hub.load_recipes()[game])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"game"
            base.mkdir()
            archives=root/"pins"
            archives.mkdir()
            candidate=root/"candidate"
            candidate.mkdir()
            cfg=bepinex.policy(recipe)
            (base/cfg["exe"]).write_bytes(b"exe")
            (base/cfg["data"]).mkdir(exist_ok=True)
            packages={}
            hashes={}
            oldpaths=[]
            changed="BepInEx/plugins/update-test.dll"
            removed="BepInEx/plugins/obsolete-test.dll"
            added="BepInEx/plugins/new-test.dll"
            foreign="BepInEx/plugins/foreign-test.dll"
            config="BepInEx/config/BepInEx.cfg"
            source=recipe["archive_releases"][role]
            for pkg in recipe["packages"]:
                rid=pkg["id"]
                payload={n:b"old:"+n.encode() for n in pkg["required_files"]}
                if rid==role:
                    payload.update({changed:b"old",removed:b"obsolete"})
                if rid=="loader":
                    payload[config]=b"default"
                def writezip(path, data):
                    with zipfile.ZipFile(path,"w") as z:
                        for n,v in data.items():
                            z.writestr(("BepInExPack_Valheim/" if game=="valheim" and rid=="loader" else "")+n,v)
                path=archives/(rid+".zip")
                writezip(path,payload)
                oldpaths.append(path)
                pkg["sha256"]=sha(path.read_bytes())
                packages[rid]={"archive":path.name,"sha256":pkg["sha256"],"files":[str(base/n) for n in payload],"installed_at":1}
                for n,v in payload.items():
                    p=base/n
                    p.parent.mkdir(parents=True,exist_ok=True)
                    p.write_bytes(v)
                    hashes[n]=sha(v)
                if rid==role:
                    old=release(source["pinned_tag"],1,path.read_bytes(),filename)
                    nextpayload=dict(payload)
                    del nextpayload[removed]
                    nextpayload.update({changed:b"new",added:b"new"})
                    target=candidate/filename
                    writezip(target,nextpayload)
                    latest=release(tag,2,target.read_bytes(),filename)
            (base/config).write_bytes(b"player custom")
            backup=root/"hub/backups"/(game+"-"+"a"*32)
            backup.mkdir(parents=True)
            statepath=root/"hub/state.json"
            record={"installer":cfg["marker"],"keep":str(base),"files":[str(base/n) for n in hashes],
                    "file_hashes":hashes,"packages":packages,"backup":str(backup),
                    "originals":[],"original_hashes":{},"retired":[],"installed_at":1}
            state={game:record}
            def fetch(repo):
                return [old,latest] if repo==source["repo"] else []
            def snapshot():
                return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob("*") if p.is_file()}
            def review():
                before=snapshot()
                with patch.object(hub,"game_path",return_value=base),patch.object(hub,"state_file",return_value=statepath),patch.object(hub,"state",return_value=state):
                    result=manifest.review(recipe,oldpaths,candidate,fetch=fetch)
                self.assertEqual(snapshot(),before)
                self.assertFalse(result["write_authorized"])
                if result["status"] == "Blocked":
                    self.assertFalse({r["action"] for r in result["rows"]} & {"Install","Replace","Remove"})
                return result
            result=review()
            self.assertEqual(result["status"],"Review required",result)
            actions={r["path"]:r["action"] for r in result["rows"]}
            self.assertEqual({n:actions[n] for n in (changed,removed,added,config)},
                             {changed:"Replace",removed:"Remove",added:"Install",config:"Preserve"})
            (base/added).write_bytes(b"foreign")
            result=review()
            self.assertEqual(result["status"],"Blocked")
            self.assertEqual(next(r for r in result["rows"] if r["path"]==added)["action"],"Block")
            (base/added).unlink()
            (base/changed).write_bytes(b"modified")
            self.assertEqual(review()["status"],"Blocked")
            (base/changed).write_bytes(b"old")
            record["file_hashes"][changed]="0"*64
            self.assertEqual(review()["status"],"Blocked")
            record["file_hashes"][changed]=sha(b"old")
            # Candidate payload attacks use freshly matching simulated official digests.
            original_payload = dict(nextpayload)
            def candidate_payload(data):
                with zipfile.ZipFile(target,"w") as z:
                    for n,v in data.items():
                        z.writestr(n,v)
                latest.update(release(tag,2,target.read_bytes(),filename))
            for label, data in (
                ("overlap", {**original_payload, config:b"foreign"}),
                ("case rename", {str(Path(n).with_name(Path(n).name.upper())) if n==changed else n:v for n,v in original_payload.items()}),
                ("file directory collision", {**original_payload, added+"/child.dll":b"child"}),
                ("protected addition", {**original_payload,"BepInEx/config/new.cfg":b"new"}),
            ):
                with self.subTest(game=game, attack=label):
                    candidate_payload(data)
                    self.assertEqual(review()["status"],"Blocked")
            candidate_payload({**original_payload, "BepInEx/plugins/new-test.dll":b"new",
                               "BepInEx/Plugins/other.dll":b"case parent"})
            self.assertEqual(review()["status"],"Blocked")
            binding=cfg["data"]+"/StreamingAssets/SteamVR/bindings_oculus_touch.json"
            candidate_payload({**original_payload,binding:b"changed binding"})
            result=review()
            self.assertEqual(result["status"],"Blocked")
            self.assertTrue(any("migration" in b.lower() for b in result["blockers"]))
            candidate_payload(original_payload)
            (base/binding).unlink()
            self.assertEqual(review()["status"],"Blocked")
            (base/binding).write_bytes(b"old:"+binding.encode())
            # Existing case twin, symlink and known conflicting plugin.
            # Keep parent spelling unchanged to exercise target collision.
            twin=(base/added).with_name(Path(added).name.upper())
            twin.write_bytes(b"foreign")
            self.assertEqual(review()["status"],"Blocked")
            twin.unlink()
            (base/added).symlink_to(root/"absent")
            self.assertEqual(review()["status"],"Blocked")
            (base/added).unlink()
            conflict=base/"BepInEx/plugins"/("vrenhancements.dll" if game=="subnautica" else "nested/ValheimVRMod.dll")
            conflict.parent.mkdir(parents=True,exist_ok=True)
            conflict.write_bytes(b"conflict")
            self.assertEqual(review()["status"],"Blocked")
            conflict.unlink()
            record["originals"]=[removed]
            record["original_hashes"]={removed:sha(b"historical")}
            original=backup/"files"/removed
            original.parent.mkdir(parents=True)
            original.write_bytes(b"historical")
            self.assertEqual(review()["status"],"Blocked")
            record["originals"]=[]
            record["original_hashes"]={}
            # Detect changing state even when provider returns the same dict.
            real_recognize=manifest.recognition.recognize
            calls=0
            def drifting(*args,**kwargs):
                nonlocal calls
                result=real_recognize(*args,**kwargs)
                calls+=1
                if calls==2:
                    state["unrelated"]={"changed":True}
                return result
            with patch.object(manifest.recognition,"recognize",side_effect=drifting):
                self.assertEqual(review()["status"],"Blocked")
            state.pop("unrelated")
            # Inject drift after the second recognition sample. Snapshot the
            # external mutation separately; the reviewer itself never writes.
            def drift_review(mutate):
                calls=0
                def drifting(*args,**kwargs):
                    nonlocal calls
                    result=real_recognize(*args,**kwargs)
                    calls+=1
                    if calls==2:
                        mutate()
                    return result
                with patch.object(hub,"game_path",return_value=base),patch.object(hub,"state_file",return_value=statepath),patch.object(hub,"state",return_value=state),patch.object(manifest.recognition,"recognize",side_effect=drifting):
                    result=manifest.review(recipe,oldpaths,candidate,fetch=fetch)
                self.assertEqual(calls,2)
                self.assertEqual(result["status"],"Blocked")
                self.assertFalse({r["action"] for r in result["rows"]}&{"Install","Replace","Remove"})
                self.assertFalse(result["write_authorized"])
            drift_review(lambda:(base/added).write_bytes(b"external"))
            self.assertEqual((base/added).read_bytes(),b"external")
            (base/added).unlink()
            saved=target.read_bytes()
            drift_review(lambda:target.write_bytes(b"external archive edit"))
            self.assertEqual(target.read_bytes(),b"external archive edit")
            target.write_bytes(saved)
            target.write_bytes(b"tampered")
            self.assertEqual(review()["status"],"Blocked")

    def test_subnautica(self):
        self.exercise("subnautica","submersedvr","0.2.2","SubmersedVR_0.2.2.zip")

    def test_valheim(self):
        self.exercise("valheim","vhvr","v0.11.3","vhvr.zip")
