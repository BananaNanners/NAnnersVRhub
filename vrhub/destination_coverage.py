# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-V: read-only *target coverage*, never real update authorization.

Consumes full, bounded target lists retained transiently by the already
user-triggered pre-update safety parser. It does NOT inspect archives or
files, derive any file destination from a raw filename, or accept an install
plan. Scope is recipe install targets only, not every ZIP member, installed
file, runtime compatibility, or a future release guarantee.
"""
from __future__ import annotations

from . import download_planner, installed_integrity
from . import update_manifest_preview as manifest

SCHEMA = 1
MAX_COMPONENTS = 32
MAX_TARGETS = 2500


def _path(s):
    if installed_integrity._relative(s) is None:
        raise ValueError("Unsafe or noncanonical mapping target.")
    return s


def _ancestors(path):
    parts = path.casefold().split("/")
    return {"/".join(parts[:n]) for n in range(1, len(parts))}


def assess(recipe, safety, preservation, *, validated_manifest=None):
    """Return an advisory coverage audit of on-demand parser output.

    A *complete target list at review* does not establish a complete ZIP
    inventory, absence of manual files, fresh installation hashes, or a safe
    update. Components without a reviewed archive stay unmapped.
    """
    if (not isinstance(recipe, dict) or not isinstance(recipe.get("id"), str)
            or not recipe["id"]):
        raise ValueError("Missing destination-audit recipe.")
    # Reuse U's validated result from the worker, without running its parser
    # a second time. Standalone callers still receive identical validation.
    preview = (validated_manifest if validated_manifest is not None
               else manifest.preview_from_review(recipe, safety, preservation))
    if (not isinstance(preview, dict) or preview.get("game_id") != recipe["id"]
            or preview.get("candidate_mapping_complete") is not False
            or preview.get("evidence_level") != "real_readonly_samples"
            or preview.get("live_update_authorized") is not False
            or preview.get("executable_plan") is not None):
        raise ValueError("Unexpectedly executable real manifest evidence.")
    comps = download_planner.plan_components(recipe)
    if not 0 < len(comps) <= MAX_COMPONENTS:
        raise ValueError("Invalid component count.")
    expected = {str(c["id"]) for c in comps if str(c["id"]) != "guide"}
    source = {r["id"]: r for r in safety["rows"]}
    if set(source) != expected:
        raise ValueError("Incomplete component coverage.")
    choices = preservation.get("rows")
    if not isinstance(choices, list) or len(choices) > MAX_TARGETS:
        raise ValueError("Missing bounded file-preservation worksheet.")
    preserved = {}
    for row in choices:
        if (not isinstance(row, dict) or
                not isinstance(row.get("component_id"), str)
                or row["component_id"] not in expected or
                row.get("draft_decision") not in (
                    "preserve_existing", "investigate_unknown",
                    "consider_future_replacement")
                or row.get("replacement_authorized") is not False
                or row.get("selection_saved") is not False):
            raise ValueError("Untrusted preservation decision.")
        key = (row["component_id"], _path(row.get("relative_file")).casefold())
        if key in preserved:
            raise ValueError("Duplicate protected file.")
        preserved[key] = row
    validated = {}
    for comp in comps:
        cid = str(comp["id"])
        if cid == "guide":
            continue
        row = source[cid]
        paths = row.get("full_target_list")
        parser = row.get("full_target_provenance")
        if not isinstance(paths, list) or len(paths) > MAX_TARGETS:
            raise ValueError("Full target inventory missing or unbounded.")
        if parser is not None and parser not in (
                "pinned_package", "uevr_profile", "cyberpunk_gameroot"):
            raise ValueError("Unrecognized target mapper.")
        supported = (
            parser == "pinned_package" and bool(recipe.get("packages"))
            or parser == "uevr_profile" and recipe.get("method") == "uevr"
            and cid == "profile"
            or parser == "cyberpunk_gameroot"
            and recipe.get("id") == "cyberpunk-2077"
            and recipe.get("method") == "gameroot"
            and cid.isdecimal()
        )
        if parser is not None and not supported:
            raise ValueError("Wrong mapper for component/recipe.")
        if parser is None and paths:
            raise ValueError("Unattributed full target map.")
        future = row.get("future_destinations")
        complete = (
            bool(paths) and bool(parser)
            and type(future) is int and future == len(paths)
        )
        if parser is not None and future is not None and not complete:
            raise ValueError("Inconsistent full target coverage assertion.")
        names = {}
        for item in paths:
            name = _path(item)
            key = name.casefold()
            if key in names:
                raise ValueError("Duplicate/casefold-colliding complete target.")
            names[key] = name
        if any(ancestor in names for name in names for ancestor in _ancestors(name)):
            raise ValueError("File/directory conflict within complete target list.")
        sample = row.get("future_sample")
        if complete and (not isinstance(sample, list) or
                         sample != paths[:len(sample)]):
            raise ValueError("Sample does not match complete target list.")
        validated[cid] = (complete, names, parser)

    conflicts = {cid: set() for cid in validated}
    mapped = {}
    # Count only POSITIVE overlaps. Missing components or bounded target
    # samples cannot certify no conflicts anywhere else in a real game.
    for cid, (complete, names, _) in validated.items():
        if not complete:
            continue
        for key, name in names.items():
            for other_key, (other_cid, other_name) in mapped.items():
                if (key == other_key or key in _ancestors(other_name)
                        or other_key in _ancestors(name)):
                    conflicts[cid].add(name)
                    conflicts[other_cid].add(other_name)
            mapped[key] = (cid, name)

    out = []
    for comp in comps:
        cid = str(comp["id"])
        if cid == "guide":
            out.append({
                "id":cid,"name":str(comp.get("name",cid)),
                "status":"manual", "full_target_count":None,
                "mapped_by":None,"preservation_overlaps":0,
                "cross_component_overlaps":0,"untracked_hints":0,
                "ownership_hints":0,"scope_complete_at_review":False,
                "mapping_future_compatible":False,"live_update_authorized":False,
                "next_step":"Follow the manual guide; no automated file mapping.",
            })
            continue
        row = source[cid]
        complete, names, parser = validated[cid]
        protected = sum((cid,key) in preserved for key in names)
        unmatched = sum(owner == cid and key not in names for owner,key in preserved)
        known = len(conflicts[cid])
        tracked_conflicts = len(row["ownership_conflicts"])
        untracked = len(row["untracked_collisions"])
        if known or tracked_conflicts or untracked:
            status="conflict_review"
            next_step="Review ownership and destination conflicts; no file may be replaced."
        elif protected or unmatched:
            status="preservation_review"
            next_step=("Review overlaps and unlisted modified files. The recommendation "
                       "is NOT an enforced protection or merge policy.")
        elif complete:
            status="target_list_mapped"
            next_step=("Only the recipe's install-target list was mapped at review. "
                       "Verify full archive member accounting, actual ownership, "
                       "new-release compatibility and backups separately.")
        else:
            status="mapping_missing"
            next_step=("Obtain an unambiguous verified candidate and a supported "
                       "read-only parser. Raw ZIP filenames are not destinations.")
        out.append({
            "id":cid,"name":str(comp.get("name",cid)),
            "status":status,"full_target_count":len(names) if complete else None,
            "mapped_by":parser if complete else None,
            "preservation_overlaps":protected,
            "unmapped_preservation_issues":unmatched,
            "cross_component_overlaps":known,
            "untracked_hints":untracked,
            "ownership_hints":tracked_conflicts,
            "scope_complete_at_review":complete,
            # Strict W mapper accounts for every regular ZIP member only.
            # Other metadata and live file ownership still need independent proof.
            "source_file_accounting_complete": (
                complete and parser == "cyberpunk_gameroot"),
            "current_installed_ownership_verified":False,
            "mapping_future_compatible":False,
            "live_update_authorized":False,"next_step":next_step,
        })
    counts = {status:sum(r["status"] == status for r in out)
              for status in ("manual","mapping_missing","target_list_mapped",
                             "preservation_review","conflict_review")}
    return {
        "schema":SCHEMA,"game_id":recipe["id"],
        "status":"Read-only destination coverage — LIVE UPDATE DISABLED",
        "rows":out,"counts":counts,
        "total_dependencies":len(out),
        "complete_recipe_target_lists":sum(
            r["scope_complete_at_review"] for r in out),
        "cross_component_coverage_complete":False,
        "full_archive_member_accounting_proven":False,
        "installed_file_coverage_proven":False,
        "real_compatibility_verified":False,
        "file_preservation_enforced":False,
        "live_update_authorized":False,
        "executable_plan":None,
        "requires_separate_live_approval":True,
    }


def rehearse_synthetic_mapping_coverage():
    """Use six existing invented manifests; no real ZIP or game access."""
    fixtures = manifest.rehearse_six_fixture_previews()
    if (fixtures.get("games") != 6 or not fixtures.get("fixture_only")
            or fixtures.get("live_update_authorized")
            or fixtures.get("real_game_files_modified")):
        raise RuntimeError("Synthetic manifest fixtures were not validated.")
    summaries = {}
    for game, report in fixtures["examples"].items():
        candidate = [r for r in report["rows"] if r["candidate_sha256"] is not None]
        if (not candidate or len(candidate) != report["candidate_files"]
                or any(r["live_authorized"] or r["actual_file_modified"]
                       for r in candidate)):
            raise RuntimeError("Synthetic future target inventory incomplete.")
        summaries[game] = {
            "candidate_targets": len(candidate),
            "holds":report["holds"],
            "fixture_only":True,"live_update_authorized":False,
        }
    return {
        "games":6,"families":fixtures["families"],
        "target_lists":summaries,
        "retirement_holds":2 if fixtures["uevr_retirements_blocked"] else 0,
        "manual_files_preserved":fixtures["manual_files_preserved"],
        "fixture_only":True,"real_file_contents_read":False,
        "live_update_authorized":False,"real_compatibility_verified":False,
    }
