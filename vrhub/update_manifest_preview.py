# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-U — preservation-aware previews, NEVER executable update plans.

compare_fixture() accepts invented bytes only. preview_from_review() accepts
sampled real read-only safety records only: it cannot certify an exact mapping.
Neither path touches real game files, state, archives, or backups.
"""
from __future__ import annotations
import hashlib
import re
from . import download_planner, installed_integrity, offline_transaction as tx
from . import preservation_decisions as policy

SUPPORTED = frozenset(("valheim","subnautica","elden-ring","fatekeeper",
                       "hogwarts-legacy","cyberpunk-2077"))
HELD = frozenset(("preservation_hold","changed_owned_hold","untracked_collision",
                  "cross_component_collision","case_collision","path_collision",
                  "retirement_hold"))
SHA = re.compile(r"[0-9a-f]{64}\Z")
SCHEMA = 1


def _path(value):
    if installed_integrity._relative(value) is None:
        raise ValueError("Unsafe manifest-relative file path.")
    return value


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _policy(game_id, worksheet):
    if worksheet is None:
        return {}
    if (not isinstance(worksheet, dict) or worksheet.get("game_id") != game_id
            or worksheet.get("live_update_authorized") is not False
            or worksheet.get("choices_saved") is not False
            or worksheet.get("real_compatibility_verified") is not False
            or worksheet.get("recorded_file_hashes_rewritten") is not False
            or worksheet.get("manual_files_adopted") is not False
            or not isinstance(worksheet.get("rows"), list)
            or len(worksheet["rows"]) > tx.MAX_FILES):
        raise ValueError("Cross-game or executable preservation choices.")
    out = {}
    for row in worksheet["rows"]:
        if (not isinstance(row, dict)
                or not isinstance(row.get("component_id"), str)
                or row.get("draft_decision") not in policy.DECISIONS
                or row.get("replacement_authorized") is not False
                or row.get("selection_saved") is not False
                or row.get("recorded_sha_rewritten") is not False
                or row.get("fresh_verified_backup") is not False
                or row.get("real_compatibility_verified") is not False):
            raise ValueError("Unsafe preservation row.")
        key = (row["component_id"], _path(row.get("relative_file")).casefold())
        if key in out:
            raise ValueError("Duplicated preservation decision.")
        out[key] = row["draft_decision"]
    return out


def _names(items):
    if len(items) > tx.MAX_FILES:
        raise ValueError("Excessive fixture files.")
    normalized = {}
    for name in items:
        key = _path(name).casefold()
        if key in normalized:
            raise ValueError("Case-colliding fixture source files.")
        normalized[key] = name
    return normalized


def compare_fixture(game_id, installed, incoming, owners, candidate_owners,
                    recorded_sha256, *, worksheet=None, retirements=()):
    """Compare synthetic bytes without writing, adopting, or authorizing."""
    if (game_id not in SUPPORTED or not all(isinstance(x, dict) for x in (
            installed, incoming, owners, candidate_owners, recorded_sha256))
            or not installed or not incoming
            or len(installed) + len(incoming) > tx.MAX_FILES):
        raise ValueError("Incomplete or excessive synthetic fixture.")
    before = _names(installed)
    after = _names(incoming)
    if (set(owners) != set(recorded_sha256)
            or not set(owners).issubset(installed)
            or set(candidate_owners) != set(incoming)
            or any(not isinstance(v, str) or not v or len(v) > 64
                   for v in [*owners.values(), *candidate_owners.values()])):
        raise ValueError("Missing or inconsistent owner attribution.")
    if (not isinstance(retirements, (tuple,list))
            or len(retirements) > tx.MAX_FILES
            or len(set(retirements)) != len(retirements)):
        raise ValueError("Invalid removal proposal.")
    for name in retirements:
        _path(name)
        if name not in owners or name in incoming:
            raise ValueError("Retirement must name an owned file omitted by candidate.")
    if any(not isinstance(x, bytes) or len(x) > tx.MAX_FILE_BYTES
           for x in [*installed.values(), *incoming.values()]):
        raise ValueError("Fixture data must be bounded bytes, never paths.")
    if sum(map(len, [*installed.values(), *incoming.values()])) > tx.MAX_TOTAL_BYTES:
        raise ValueError("Synthetic fixture bytes exceed limit.")
    if any(not isinstance(v,str) or SHA.fullmatch(v) is None
           for v in recorded_sha256.values()):
        raise ValueError("Invalid recorded SHA evidence.")
    choices = _policy(game_id, worksheet)
    valid_choices = {(cid,name.casefold()) for name,cid in owners.items()}
    if not set(choices).issubset(valid_choices):
        raise ValueError("Decision has no owned matching file.")
    counts = {key:0 for key in ("add","replace","unchanged","preserve_untouched",*sorted(HELD))}
    rows, used = [], set()
    for name,data in sorted(incoming.items()):
        cid = candidate_owners[name]
        original = before.get(name.casefold())
        old_data = installed.get(original) if original is not None else None
        old_owner = owners.get(original)
        old_sha = _sha(old_data) if old_data is not None else None
        segments=name.split("/")
        ancestors={"/".join(segments[:i]).casefold() for i in range(1,len(segments))}
        descendant = any(x.startswith(name.casefold()+"/") for x in [*before,*after])
        if any(x in before or x in after for x in ancestors) or descendant:
            action="path_collision"
        elif original is not None and original != name:
            action="case_collision"
        elif original is None:
            action="add"
        elif old_owner is None:
            action="untracked_collision"
        elif old_owner != cid:
            action="cross_component_collision"
        elif _sha(old_data) != recorded_sha256[original]:
            action="changed_owned_hold"
        elif (cid,name.casefold()) in choices:
            action="preservation_hold"
        elif old_data == data:
            action="unchanged"
        else:
            action="replace"
        counts[action]+=1
        if original is not None:
            used.add(original)
        rows.append({
            "path":name,"candidate_owner":cid,"current_owner":old_owner,
            "before_sha256":old_sha,"candidate_sha256":_sha(data),
            "hypothetical_after_sha256":(
                _sha(data) if action in ("add","replace") else old_sha),
            "action":action,"hold":action in HELD,
            "decision":choices.get((cid,name.casefold())),
            "actual_file_modified":False,"live_authorized":False,
        })
    for name,data in sorted(installed.items()):
        if name in used:
            continue
        action="retirement_hold" if name in retirements else "preserve_untouched"
        counts[action]+=1
        rows.append({
            "path":name,"candidate_owner":None,"current_owner":owners.get(name),
            "before_sha256":_sha(data),"candidate_sha256":None,
            "hypothetical_after_sha256":_sha(data),"action":action,
            "hold":action in HELD,"decision":None,
            "actual_file_modified":False,"live_authorized":False,
        })
    return {
        "schema":SCHEMA,"game_id":game_id,"evidence_level":"synthetic_complete",
        "status":"SYNTHETIC BEFORE/AFTER ONLY — LIVE UPDATE DISABLED",
        "rows":sorted(rows,key=lambda r:(r["path"].casefold(),r["action"])),
        "counts":counts,"files_before":len(installed),
        "candidate_files":len(incoming),
        "holds":sum(counts[k] for k in HELD),
        "fixture_only":True,"files_modified":False,"backups_created":False,
        "preservation_enforced":False,"real_compatibility_verified":False,
        "live_update_authorized":False,"executable_plan":None,
    }


def preview_from_review(recipe, safety, worksheet):
    """Never infer a complete real destination map from capped samples."""
    if (not isinstance(recipe,dict) or not isinstance(recipe.get("id"),str)
            or not isinstance(safety,dict) or safety.get("game_id")!=recipe["id"]
            or safety.get("authorized") is not False
            or safety.get("has_live_install_plan") is not False
            or not isinstance(worksheet,dict)
            or worksheet.get("game_id")!=recipe["id"]
            or worksheet.get("live_update_authorized") is not False
            or worksheet.get("choices_saved") is not False
            or worksheet.get("real_compatibility_verified") is not False):
        raise ValueError("Untrusted or cross-game review inputs.")
    components=download_planner.plan_components(recipe)
    expected={str(x["id"]) for x in components if str(x["id"])!="guide"}
    raw=safety.get("rows")
    if not isinstance(raw,list) or len(raw)!=len(expected):
        raise ValueError("Incomplete safety dependency coverage.")
    indexed={}
    for row in raw:
        if (not isinstance(row,dict) or not isinstance(row.get("id"),str)
                or row["id"] not in expected or row["id"] in indexed
                or row.get("eligible") is not False
                or row.get("backups_verified_for_update") is not False):
            raise ValueError("Conflicting or executable safety evidence.")
        count=row.get("future_destinations")
        sample=row.get("future_sample")
        if (count is not None and (type(count) is not int or not 1<=count<=tx.MAX_FILES)
                or not isinstance(sample,list) or len(sample)>16
                or (count is None and sample)
                or (count is not None and len(sample)>count)):
            raise ValueError("Incomplete or unsafe destination sample.")
        for name in sample:
            _path(name)
        for key in ("ownership_conflicts","untracked_collisions"):
            arr=row.get(key)
            if (not isinstance(arr,list) or len(arr)>16
                    or any(not isinstance(v,str) or len(v)>4096 for v in arr)):
                raise ValueError("Malformed collision summary.")
        indexed[row["id"]]=row
    if set(indexed)!=expected:
        raise ValueError("Missing dependency safety row.")
    # Positive evidence of overlap between TWO candidate samples is a real
    # conflict hint. Lack of overlap in bounded samples is never clearance.
    sample_seen={}
    future_sample_overlaps={cid:[] for cid in indexed}
    for cid,row in indexed.items():
        within=set()
        for name in row["future_sample"]:
            key=name.casefold()
            if key in within:
                raise ValueError("Duplicate destination inside component sample.")
            within.add(key)
            previous=sample_seen.get(key)
            if previous is not None and previous != cid:
                future_sample_overlaps[previous].append(name)
                future_sample_overlaps[cid].append(name)
            else:
                sample_seen[key]=cid
    choices=_policy(recipe["id"],worksheet)
    output=[]
    for comp in components:
        cid=str(comp["id"])
        if cid not in indexed:
            output.append({
                "id":cid,"name":comp["name"],"status":"manual_or_guide",
                "current_managed_count":None,"candidate_count":None,
                "sample_paths":[],"known_conflicts":[],
                "preservation_review_count":0,
                "next_step":"Use the existing manual guide; no mapped update.",
                "live_update_authorized":False,
            })
            continue
        data=indexed[cid]
        collisions=(list(data["ownership_conflicts"])+
                    list(data["untracked_collisions"])+
                    ["Shared sampled future target: "+name
                     for name in future_sample_overlaps[cid]])
        protected=sum(k[0]==cid for k in choices)
        if collisions:
            status="known_conflict"
            next_step="Resolve recorded and untracked ownership conflicts first."
        elif protected:
            status="preservation_review"
            next_step="Review protected modifications against complete candidate mappings."
        elif data["future_destinations"] is None:
            status="mapping_incomplete"
            next_step="Establish complete verified ZIP-to-target mapping first."
        else:
            status="sample_only"
            next_step="The mapped sample is NOT a complete before/after update manifest."
        output.append({
            "id":cid,"name":comp["name"],"status":status,
            "current_managed_count":data.get("current_managed"),
            "candidate_count":data["future_destinations"],
            "sample_paths":list(data["future_sample"]),
            "known_conflicts":collisions,
            "preservation_review_count":protected,
            "next_step":next_step,"live_update_authorized":False,
        })
    return {
        "schema":SCHEMA,"game_id":recipe["id"],
        "evidence_level":"real_readonly_samples",
        "status":"INCOMPLETE REAL DESTINATION EVIDENCE — LIVE UPDATE DISABLED",
        "rows":output,
        "counts":{x:sum(row["status"]==x for row in output)
                  for x in ("known_conflict","preservation_review",
                            "mapping_incomplete","sample_only","manual_or_guide")},
        "candidate_mapping_complete":False,
        "no_real_before_after_hash_comparison":True,
        "files_read_or_modified":False,"backups_created":False,
        "real_compatibility_verified":False,"live_update_authorized":False,
        "executable_plan":None,
    }


def rehearse_six_fixture_previews():
    """Six invented manifests; do not read user state, archives, or game paths."""
    from . import pinned_staging, uevr_profile_staging, cyberpunk_staging, hub
    examples={}
    for game in ("valheim","subnautica","elden-ring"):
        build,specs,archives,old,managed=pinned_staging._scenario(game)
        stage=pinned_staging.prepare_fixture(game,build,specs,archives,old,managed=managed)
        candidate_owners={r["path"]:r["package_id"] for r in stage.destination_rows}
        owners={n:candidate_owners.get(n,specs[0]["id"]) for n in managed}
        examples[game]=compare_fixture(
            game,old,stage.incoming,owners,candidate_owners,
            {n:_sha(old[n]) for n in managed})
    for game in ("fatekeeper","hogwarts-legacy"):
        stage=uevr_profile_staging._scenario(game)
        examples[game]=compare_fixture(
            game,stage.current,stage.candidate,
            {n:"profile" for n in stage.current},
            {n:"profile" for n in stage.candidate},
            stage.recorded_sha256,retirements=stage.explicit_removals)
    recipe=hub.load_recipes()["cyberpunk-2077"]
    stage=cyberpunk_staging.prepare_fixture(
        recipe,**cyberpunk_staging._scenario(recipe))
    examples[stage.game_id]=compare_fixture(
        stage.game_id,stage.installed,stage.incoming,
        stage.current_owners,
        {r["path"]:r["owner"] for r in stage.destination_rows},
        {n:_sha(stage.installed[n]) for n in stage.current_owners})
    return {
        "fixture_only":True,"games":len(examples),
        "families":{"pinned":3,"uevr":2,"cyberpunk":1},
        "holds":sum(r["holds"] for r in examples.values()),
        "uevr_retirements_blocked":all(
            examples[g]["counts"]["retirement_hold"]==1
            for g in ("fatekeeper","hogwarts-legacy")),
        "manual_files_preserved":all(
            examples[g]["counts"]["preserve_untouched"]>=1
            for g in ("valheim","subnautica","elden-ring","cyberpunk-2077")),
        "examples":examples,"real_game_files_modified":False,
        "real_compatibility_verified":False,
        "live_update_authorized":False,"executable_plan":None,
    }
