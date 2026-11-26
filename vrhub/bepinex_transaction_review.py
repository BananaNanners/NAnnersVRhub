# SPDX-License-Identifier: GPL-3.0-only
"""Synthetic BepInEx repair rehearsal, never a live destination or installer."""
from contextlib import contextmanager
import hashlib
import json
from . import bepinex, bepinex_repair_review, offline_transaction as tx


def _hash(data):
    return hashlib.sha256(data).hexdigest()


@contextmanager
def rehearsal(game_id):
    """Construct synthetic pinned/current bytes, then use the existing engine.

    Historical ownership is distinct from the engine's snapshot inventory.
    No caller-supplied filesystem paths or real archive bytes are accepted.
    """
    if game_id not in ("subnautica", "valheim"):
        raise tx.TransactionBlocked("Unsupported BepInEx rehearsal.")
    data = bepinex.policy(game_id)["data"]
    binding = data + "/StreamingAssets/SteamVR/bindings_oculus_touch.json"
    config = "BepInEx/config/BepInEx.cfg"
    missing = "BepInEx/core/BepInEx.dll"
    changed = "winhttp.dll"
    plugin = "BepInEx/plugins/" + ("SubmersedVR.dll" if game_id=="subnautica" else "ValheimVRMod.dll")
    pinned = {n:("synthetic pinned "+n).encode() for n in (binding,config,missing,changed,plugin)}
    roles = {n:("loader" if n in (config,missing,changed) else "vr") for n in pinned}
    current = {**pinned, config:b"custom settings",binding:b"custom controls",changed:b"modified binary"}
    del current[missing]
    original = "hub/backups/original/files/winhttp.dll"
    record = {"installer":bepinex.policy(game_id)["marker"],
              "historical_hashes":{n:_hash(v) for n,v in pinned.items()},
              "original_hashes":{changed:_hash(b"original loader")},
              "other_game":{"preserve":True}}
    state = (json.dumps(record,sort_keys=True)+"\n").encode()
    installed = {**current,original:b"original loader","hub/state.json":state,
                 "BepInEx/plugins/unrelated.dll":b"unrelated mod",
                 "prefix/save.dat":b"synthetic save"}
    recipe = {"id":game_id,"packages":[{"id":r,"sha256":_hash(r.encode())} for r in ("loader","vr")]}
    evidence = {"status":"Review","ownership_record":"consistent-record","backup_status":"originals-match",
                "conflicts":(),"root":"synthetic","sampled_at":"synthetic","rows":tuple(
                    {"component":roles[n],"path":n,"status":"missing" if n not in current else
                     "matching" if current[n]==v else "modified-settings" if n in (config,binding) else "different",
                     "expected_sha256":_hash(v),"actual_sha256":_hash(current[n]) if n in current else None,
                     "protected_setting":n in (config,binding)} for n,v in pinned.items())}
    review = bepinex_repair_review.from_evidence(recipe,evidence)
    if review["status"]!="Review required" or review["write_authorized"]:
        raise tx.TransactionBlocked("Synthetic review is not eligible.")
    incoming = {r["path"]:pinned[r["path"]] for r in review["rows"] if r["action"].startswith("Proposed")}
    if set(incoming)!={changed,missing}:
        raise tx.TransactionBlocked("Synthetic repair scope differs.")
    # Engine snapshot inventory includes every present fixture file, not a
    # claim of real Hub ownership. This backs up even preserved sentinels.
    with tx.fixture_sandbox(installed,incoming) as fixture:
        plan=tx.build_plan(fixture)
        if {r["path"]:r["action"] for r in plan.rows}!={changed:"replace",missing:"add"}:
            raise tx.TransactionBlocked("Fixture plan differs from reviewed actions.")
        yield fixture,plan,review


@contextmanager
def pinned_rehearsal(game_id, archives):
    """Real pinned payloads in a new private fixture; no live destination.

    Reuse the larger existing fixture bounds (legacy uevr_payload flag).
    Only discovery and state-file location are substituted for recognition.
    No production installer or state publication is invoked.
    """
    from pathlib import Path
    from unittest.mock import patch
    import zipfile
    from . import hub, bepinex_recognition as recognition

    if game_id not in recognition.SUPPORTED:
        raise tx.TransactionBlocked("Unsupported pinned repair rehearsal.")
    recipe = hub.load_recipes()[game_id]
    cfg = bepinex.policy(recipe)
    paths = tuple(Path(p) for p in archives)
    if len(paths) != len(recipe["packages"]):
        raise tx.TransactionBlocked("Complete pinned package pair required.")
    payload, roles, packages = {}, {}, {}
    seen = set()
    for path in paths:
        with recognition._archive_snapshot(path) as (source, sha, _identity):
            pkg, members = bepinex.archive_plan_stream(source, recipe, sha, path)
            role = pkg["id"]
            if role in packages:
                raise tx.TransactionBlocked("Duplicate package role.")
            packages[role] = (path.name, sha, tuple(members.values()))
            with zipfile.ZipFile(source) as z:
                for origin, name in members.items():
                    if name.casefold() in seen:
                        raise tx.TransactionBlocked("Overlapping package destinations.")
                    seen.add(name.casefold())
                    payload[name] = z.read(origin)
                    roles[name] = role
    if set(packages) != {p["id"] for p in recipe["packages"]}:
        raise tx.TransactionBlocked("Incomplete pinned package pair.")
    config = "BepInEx/config/BepInEx.cfg"
    binding = cfg["data"] + "/StreamingAssets/SteamVR/bindings_oculus_touch.json"
    changed, missing = "winhttp.dll", "BepInEx/core/BepInEx.dll"
    current = dict(payload)
    current.update({config:b"synthetic customized config",binding:b"synthetic customized binding",
                    changed:b"synthetic modified loader"})
    del current[missing]
    backup = "hub/backups/" + game_id + "-" + "a"*32
    original = backup + "/files/" + changed
    state_name = "hub/state.json"
    installed = {**current, cfg["exe"]:b"synthetic game executable",
                 original:b"synthetic historical original", state_name:b"initializing",
                 "BepInEx/plugins/unrelated.dll":b"foreign mod sentinel",
                 "prefix/save.dat":b"save sentinel"}
    # All present fixture files are snapshotted; this is NOT a claim of ownership.
    with tx.fixture_sandbox(installed,{n:payload[n] for n in (changed,missing)},
                            uevr_payload=True) as f:
        base = tx._assert_fixture(f)/"installed"
        record = {"installer":cfg["marker"],"keep":str(base),
                  "files":[str(base/n) for n in payload],
                  "backup":str(base/backup),"originals":[changed],"retired":[],
                  "original_hashes":{changed:_hash(installed[original])},
                  "file_hashes":{n:_hash(v) for n,v in payload.items()},"installed_at":1,
                  "packages":{role:{"archive":a,"sha256":sha,"files":[str(base/n) for n in names],
                                    "installed_at":1} for role,(a,sha,names) in packages.items()}}
        state = {game_id:record,"unrelated-game":{"fixture":"unchanged"}}
        tx._write(f,"installed",state_name,(json.dumps(state,sort_keys=True)+"\n").encode())
        tx._target(f,"installed",changed).chmod(0o640)
        tx._save_inventory(f,{n:_hash(tx._read(f,"installed",n)) for n in installed})
        with patch.object(hub,"game_path",return_value=base), patch.object(hub,"state_file",return_value=base/state_name):
            review = bepinex_repair_review.review(recipe,paths)
        if (review["status"]!="Review required" or review["write_authorized"]
                or review["ownership_record"]!="consistent-record"
                or review["backup_status"]!="originals-match"
                or {r["path"]:r["expected_sha256"] for r in review["rows"]}!=record["file_hashes"]
                or {r["path"]:r["action"] for r in review["rows"] if r["action"]!="Preserve"}
                   != {changed:"Proposed replacement",missing:"Proposed restore"}):
            raise tx.TransactionBlocked("Pinned recognition differs from intended repair: "+str(review["blockers"]))
        plan = tx.build_plan(f)
        if {r["path"]:r["new"] for r in plan.rows}!={n:_hash(payload[n]) for n in (changed,missing)}:
            raise tx.TransactionBlocked("Pinned transaction plan differs from review.")
        yield f,plan,review
