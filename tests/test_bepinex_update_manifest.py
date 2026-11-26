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
            target.write_bytes(b"tampered")
            self.assertEqual(review()["status"],"Blocked")

    def test_subnautica(self):
        self.exercise("subnautica","submersedvr","0.2.2","SubmersedVR_0.2.2.zip")

    def test_valheim(self):
        self.exercise("valheim","vhvr","v0.11.3","vhvr.zip")
