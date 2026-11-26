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
