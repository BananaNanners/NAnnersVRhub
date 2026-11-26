# SPDX-License-Identifier: GPL-3.0-only
"""Disposable managed-update rehearsal; never accepts a live destination."""
from contextlib import contextmanager
import copy
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import zipfile
from . import bepinex, bepinex_recognition as recognition, bepinex_update_manifest as manifest, hub, offline_transaction as tx


def _zip(path, payload, prefix=""):
    with zipfile.ZipFile(path,"w") as z:
        for name,data in sorted(payload.items()):
            z.writestr(prefix+name,data)


def _release(tag, day, path, name):
    return {"tag_name":tag,"published_at":f"2026-10-{day:02}T00:00:00Z",
            "draft":False,"prerelease":False,"assets":[{"name":name,
            "size":path.stat().st_size,"digest":"sha256:"+tx._sha(path.read_bytes())}]}


@contextmanager
def rehearsal(game_id, *, pinned_archives=None):
    """Create synthetic ZIP pairs and schema-accurate ownership in private /tmp.

    The real read-only review is used on fixture paths only. A private recipe
    copy supplies synthetic pins in small mode. Full mode verifies genuine
    baseline archives and generates only a synthetic candidate. No live writes.
    """
    if game_id not in recognition.SUPPORTED:
        raise tx.TransactionBlocked("Unsupported managed update rehearsal.")
    recipe=copy.deepcopy(hub.load_recipes()[game_id])
    cfg=bepinex.policy(recipe)
    role="submersedvr" if game_id=="subnautica" else "vhvr"
    tag, filename=("0.2.2","SubmersedVR_0.2.2.zip") if game_id=="subnautica" else ("v0.11.3","vhvr.zip")
    changed="BepInEx/plugins/update-test.dll"
    removed="BepInEx/plugins/obsolete-test.dll"
    added="BepInEx/plugins/new-folder/new-test.dll"
    config="BepInEx/config/BepInEx.cfg"
    binding=cfg["data"]+"/StreamingAssets/SteamVR/bindings_oculus_touch.json"
    if pinned_archives is not None:
        pinned_archives=tuple(Path(p) for p in pinned_archives)
        if len(pinned_archives)!=len(recipe["packages"]):
            raise tx.TransactionBlocked("Complete pinned pair required.")
        changed="BepInEx/plugins/"+("SubmersedVR.dll" if game_id=="subnautica" else "ValheimVRMod.dll")
        removed=cfg["data"]+"/StreamingAssets/amplify_resources.manifest"
    with tempfile.TemporaryDirectory(prefix="nanners-update-archives-",dir="/tmp") as temp:
        root=Path(temp)
        candidate_folder=root/"candidate"
        candidate_folder.mkdir()
        oldpaths=[]
        payload={}
        packages={}
        if pinned_archives is not None:
            seen=set()
            for source_path in pinned_archives:
                with recognition._archive_snapshot(source_path) as (source,sha,_):
                    pkg,members=bepinex.archive_plan_stream(source,recipe,sha,source_path)
                    rid=pkg["id"]
                    if rid in packages or any(n.casefold() in seen for n in members.values()):
                        raise tx.TransactionBlocked("Overlapping or duplicate pinned package.")
                    with zipfile.ZipFile(source) as z:
                        files={name:z.read(origin) for origin,name in members.items()}
                    seen.update(n.casefold() for n in files)
                    path=root/source_path.name
                    source.seek(0)
                    path.write_bytes(source.read())
                    if tx._sha(path.read_bytes())!=sha:
                        raise tx.TransactionBlocked("Pinned copy digest differs.")
                    oldpaths.append(path)
                    packages[rid]=(path,files)
                    payload.update(files)
            if set(packages)!={p["id"] for p in recipe["packages"]}:
                raise tx.TransactionBlocked("Incomplete pinned pair.")
            if len(payload)!={"subnautica":45,"valheim":135}[game_id]:
                raise tx.TransactionBlocked("Pinned baseline inventory differs.")
        else:
            for pkg in recipe["packages"]:
                rid=pkg["id"]
                files={n:("synthetic pinned "+n).encode() for n in pkg["required_files"]}
                if rid=="loader":
                    files[config]=b"default config"
                if rid==role:
                    files.update({changed:b"old binary",removed:b"obsolete binary"})
                if set(files)&set(payload):
                    raise tx.TransactionBlocked("Overlapping synthetic baseline.")
                payload.update(files)
                path=root/(rid+".zip")
                _zip(path,files,"BepInExPack_Valheim/" if game_id=="valheim" and rid=="loader" else "")
                pkg["sha256"]=tx._sha(path.read_bytes())
                oldpaths.append(path)
                packages[rid]=(path,dict(files))
        oldpath, files=packages[role]
        incoming_payload=dict(files)
        del incoming_payload[removed]
        incoming_payload.update({changed:b"synthetic candidate replacement; not executable" if pinned_archives is not None else b"new binary",added:b"new dependency"})
        candidate=candidate_folder/filename
        _zip(candidate,incoming_payload)
        source=recipe["archive_releases"][role]
        releases=[_release(source["pinned_tag"],1,oldpath,filename),_release(tag,2,candidate,filename)]
        def fetch(repo):
            return releases if repo==source["repo"] else []
        backup="hub/backups/"+game_id+"-"+"a"*32
        original=backup+"/files/winhttp.dll"
        state_name="hub/state.json"
        installed={**payload,config:b"player custom config",binding:b"player custom controls",
                   cfg["exe"]:b"synthetic executable",original:b"historical original",
                   state_name:b"initializing","prefix/save.dat":b"save sentinel",
                   "BepInEx/plugins/unrelated.dll":b"foreign mod sentinel"}
        incoming={changed:incoming_payload[changed],added:incoming_payload[added]}
        with tx.fixture_sandbox(installed,incoming,delete=(removed,),uevr_payload=True) as f:
            base=tx._assert_fixture(f)/"installed"
            state={game_id:{"installer":cfg["marker"],"keep":str(base),
                "files":[str(base/n) for n in sorted(payload)],"file_hashes":{n:tx._sha(v) for n,v in payload.items()},
                "backup":str(base/backup),"originals":["winhttp.dll"],"original_hashes":{"winhttp.dll":tx._sha(installed[original])},
                "retired":[],"installed_at":1,"packages":{rid:{"archive":p.name,"sha256":tx._sha(p.read_bytes()),
                "files":[str(base/n) for n in sorted(data)],"installed_at":1} for rid,(p,data) in packages.items()}},
                "unrelated-game":{"fixture":"unchanged"}}
            tx._write(f,"installed",state_name,tx._json(state))
            tx._save_inventory(f,{n:tx._sha(tx._read(f,"installed",n)) for n in installed})
            def sample():
                # Read state afresh, not a cached fixture record.
                with patch.object(hub,"game_path",return_value=base),patch.object(hub,"state_file",return_value=base/state_name),patch.object(hub,"state",side_effect=lambda:json.loads(tx._read(f,"installed",state_name))):
                    return manifest.review(recipe,oldpaths,candidate_folder,fetch=fetch)
            reviewed=sample()
            if pinned_archives is not None and len(reviewed["rows"])!=len(payload)+1:
                raise tx.TransactionBlocked("Full manifest inventory differs.")
            expected={changed:"Replace",added:"Install",removed:"Remove"}
            def validate_review(result):
                if result["status"]!="Review required" or result["blockers"] or result["write_authorized"] or {r["path"]:r["action"] for r in result["rows"] if r["action"]!="Preserve"}!=expected:
                    raise tx.TransactionBlocked("Fixture update manifest blocked or scope differs.")
                if {r["path"]:r["new_sha256"] for r in result["rows"] if r["action"] in ("Install","Replace")}!={n:tx._sha(v) for n,v in incoming.items()}:
                    raise tx.TransactionBlocked("Manifest and staged payload differ.")
            validate_review(reviewed)
            updated=copy.deepcopy(state)
            record=updated[game_id]
            # Match the legacy installer contract: file_hashes describe the
            # package payload, not customized current bytes. Never rebase a
            # protected setting's expected hash to the player's edits.
            record["file_hashes"]={r["path"]:r["new_sha256"] for r in reviewed["rows"]
                                   if r["action"]!="Remove"}
            record["files"]=[str(base/n) for n in sorted(record["file_hashes"])]
            record["installed_at"]=2
            with recognition._archive_snapshot(candidate) as (_, candidate_sha, _):
                if candidate_sha != releases[1]["assets"][0]["digest"].removeprefix("sha256:"):
                    raise tx.TransactionBlocked("Candidate identity changed before publication.")
            record["packages"][role]={"archive":candidate.name,"sha256":candidate_sha,
                "files":[str(base/r["path"]) for r in reviewed["rows"]
                         if r["component"]==role and r["action"]!="Remove"],
                "installed_at":2}
            if set(record["originals"])-set(record["file_hashes"]):
                raise tx.TransactionBlocked("Historical original ownership would be lost.")
            tx._write(f,"incoming",state_name,tx._json(updated))
            plan=tx.build_plan(f)
            if {r["path"]:r["action"] for r in plan.rows}!={changed:"replace",added:"add",removed:"delete",state_name:"replace"} or plan.rows[-1]["path"]!=state_name:
                raise tx.TransactionBlocked("Transaction scope differs.")
            for row in reviewed["rows"]:
                if row["current_sha256"] != plan.before.get(row["path"]):
                    raise tx.TransactionBlocked("Manifest current bytes differ from fixture plan.")
            if plan.after[state_name]!=tx._sha(tx._json(updated)):
                raise tx.TransactionBlocked("Updated ownership bytes differ from plan.")
            def execute(*,fault=None):
                fresh=sample()
                validate_review(fresh)
                if fresh!=reviewed:
                    raise tx.TransactionBlocked("Reviewed manifest evidence changed.")
                return tx.execute(f,plan,fault=fault)
            yield f,plan,reviewed,execute,candidate
