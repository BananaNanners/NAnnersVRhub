# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-P — Cyberpunk multi-component update staging, SYNTHETIC ONLY.

This module is NOT a game-root updater. It takes invented ZIP bytes and
invented managed-file bytes, never real archive, game, state or prefix paths.
Only owned /tmp staging and offline_transaction fixture operations may write.
A successful fixture demonstration is NOT game compatibility or permission.
"""
from __future__ import annotations

import hashlib
import io
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import hub, install_review, offline_transaction as tx

GAME = "cyberpunk-2077"
MAX_ZIP_BYTES = 16 * 1024 * 1024
MAX_COMPONENTS = 15
VERSION = re.compile(r"v?(0|[1-9]\d*)(?:\.(0|[1-9]\d*))*\Z")


class ComponentStageBlocked(RuntimeError):
    """A synthetic candidate is ambiguous or would endanger other files."""


@dataclass(frozen=True)
class StagedBatch:
    game_id: str
    game_build: str
    installed: dict[str, bytes]
    managed: tuple[str, ...]
    incoming: dict[str, bytes]
    current_owners: dict[str, str]
    candidate_rows: tuple[dict, ...]
    destination_rows: tuple[dict, ...]
    status: str = "Synthetic Cyberpunk component staging — LIVE UPDATE DISABLED"
    authorized: bool = False
    real_game_compatibility_verified: bool = False
    live_executor_connected: bool = False


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _version(text):
    if not isinstance(text, str) or len(text) > 80 or VERSION.fullmatch(text) is None:
        raise ComponentStageBlocked("Component versions require explicit numeric test release labels.")
    parts = [int(n) for n in text.removeprefix("v").split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def _names(names):
    try:
        tx._check_names(names)
    except tx.TransactionBlocked as exc:
        raise ComponentStageBlocked("Unsafe or case-colliding game-root paths.") from exc


def _inputs(recipe, installed, owners, recorded, versions, proposals, archives, game_build):
    if (not isinstance(recipe, dict) or recipe.get("id") != GAME or
            recipe.get("method") != "gameroot" or
            not isinstance(recipe.get("components"), list)):
        raise ComponentStageBlocked("Only the approved Cyberpunk recipe shape is supported.")
    recipe_ids = [str(c.get("nexus_mod")) for c in recipe["components"]]
    if (len(recipe_ids) != MAX_COMPONENTS or len(set(recipe_ids)) != MAX_COMPONENTS or
            any(not x.isdecimal() for x in recipe_ids)):
        raise ComponentStageBlocked("Cyberpunk component recipe identity changed; review required.")
    components = {str(c["nexus_mod"]): c for c in recipe["components"]}
    if (not isinstance(installed, dict) or not installed or
            not isinstance(owners, dict) or not owners or
            not isinstance(recorded, dict) or not isinstance(versions, dict)):
        raise ComponentStageBlocked("Complete synthetic installed ownership evidence required.")
    _names(installed)
    _names(owners)
    _names(recorded)
    if (set(owners) != set(recorded) or not set(owners).issubset(installed) or
            any(not isinstance(cid, str) or cid not in components
                for cid in owners.values()) or
            set(versions) != set(owners.values())):
        raise ComponentStageBlocked("Stale or incomplete component ownership/version inventory.")
    if len(owners) != len({name.casefold() for name in owners}):
        raise ComponentStageBlocked("Conflicting component ownership in synthetic installation.")
    try:
        for name, content in installed.items():
            if not isinstance(content, bytes) or len(content) > tx.MAX_FILE_BYTES:
                raise ComponentStageBlocked("Invalid synthetic installed file bytes.")
        for name, cid in owners.items():
            if not isinstance(cid, str) or recorded[name] != _sha(installed[name]):
                raise ComponentStageBlocked("Managed file changed since recorded installation.")
        for version in versions.values():
            _version(version)
    except (TypeError, ValueError, KeyError) as exc:
        raise ComponentStageBlocked("Malformed installed ownership record.") from exc
    if sum(len(content) for content in installed.values()) > tx.MAX_TOTAL_BYTES:
        raise ComponentStageBlocked("Synthetic installed fixture exceeds memory limit.")
    if (not isinstance(proposals, (list, tuple)) or not proposals or
            len(proposals) > MAX_COMPONENTS or not isinstance(archives, dict)):
        raise ComponentStageBlocked("One or more bounded component proposals are required.")
    if (not isinstance(game_build, str) or not game_build or len(game_build) > 80 or
            any(ord(ch) < 32 for ch in game_build)):
        raise ComponentStageBlocked("Synthetic game build is missing.")
    if not all(isinstance(p, dict) and str(p.get("id")) in components for p in proposals):
        raise ComponentStageBlocked("Unknown or malformed Nexus component proposal.")
    ids = [str(p["id"]) for p in proposals]
    if (len(ids) != len(set(ids)) or set(archives) != set(ids) or
            not set(ids).issubset(set(versions))):
        raise ComponentStageBlocked("Duplicate, uninstalled, or missing synthetic component ZIP.")
    order = {x: i for i, x in enumerate(recipe_ids)}
    if ids != sorted(ids, key=order.get):
        raise ComponentStageBlocked("Component batch must follow reviewed recipe ordering.")
    for proposal in proposals:
        cid = str(proposal["id"])
        if (not isinstance(proposal.get("sha256"), str) or
                not re.fullmatch(r"[a-f0-9]{64}", proposal["sha256"]) or
                not isinstance(proposal.get("archive_name"), str) or
                len(proposal["archive_name"]) > 200 or
                "/" in proposal["archive_name"] or chr(92) in proposal["archive_name"] or
                not proposal["archive_name"].lower().endswith(".zip") or
                hub._component_for(recipe, proposal["archive_name"]) != components[cid]):
            raise ComponentStageBlocked("Synthetic ZIP identity must uniquely match its Nexus component.")
        if _version(proposal.get("future_version")) <= _version(versions[cid]):
            raise ComponentStageBlocked("A strictly newer synthetic component version is required.")
        allowed = proposal.get("compatible_builds")
        if (not isinstance(allowed, (tuple, list)) or not allowed or len(allowed) > 20 or
                any(not isinstance(s, str) or not s or len(s) > 80 for s in allowed) or
                game_build not in allowed):
            raise ComponentStageBlocked("Synthetic game-build compatibility is not declared.")
        prerequisites = proposal.get("requires")
        if (not isinstance(prerequisites, (tuple, list)) or
                len(prerequisites) > MAX_COMPONENTS or
                any(not isinstance(x, str) or x == cid or x not in versions
                    for x in prerequisites) or
                len(set(prerequisites)) != len(prerequisites)):
            raise ComponentStageBlocked("Unresolved or undeclared component prerequisite.")
        phase = components[cid].get("phase", 1)
        for dep in prerequisites:
            dep_phase = components[dep].get("phase", 1)
            if dep_phase > phase or (dep in ids and order[dep] >= order[cid]):
                raise ComponentStageBlocked("Dependency order or phase conflicts with recipe.")
        if phase > 1 and not prerequisites:
            raise ComponentStageBlocked("Later-phase mod requires explicit predecessor evidence.")
    return components


def _read_zip(recipe, comp, proposal, raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_ZIP_BYTES:
        raise ComponentStageBlocked("Only bounded, newly supplied synthetic ZIP bytes are supported.")
    if _sha(raw) != proposal["sha256"]:
        raise ComponentStageBlocked("Synthetic ZIP SHA-256 disagrees with declared candidate.")
    with tempfile.TemporaryDirectory(prefix="nanners-dev5d3p-stage-", dir="/tmp") as temp:
        path = Path(temp) / proposal["archive_name"]
        path.write_bytes(raw)
        path.chmod(0o600)
        try:
            install_review._zip_preflight(path)
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                members = hub._zip_members(z)
                if len(members) > tx.MAX_FILES:
                    raise ComponentStageBlocked("Component ZIP has too many payload files.")
                rels = [Path(norm) for norm in members.values()]
                plan = hub._plan_gameroot(
                    rels, proposal["archive_name"], recipe.get("root_dirs"))
                hub._validate_component_plan(comp, plan, proposal["archive_name"])
                if len(plan) != len(members):
                    raise ComponentStageBlocked(
                        "Unmapped ZIP file would be silently ignored; review archive first.")
                lookup = {str(rel): source for source, rel in members.items()}
                payloads = {}
                for source, dest in plan:
                    name = dest.as_posix()
                    _names([name])
                    if name.casefold() in {key.casefold() for key in payloads}:
                        raise ComponentStageBlocked("Duplicate case-insensitive ZIP destination.")
                    with z.open(lookup[source.as_posix()]) as stream:
                        data = stream.read(tx.MAX_FILE_BYTES + 1)
                    if len(data) > tx.MAX_FILE_BYTES:
                        raise ComponentStageBlocked("ZIP file exceeds synthetic destination limit.")
                    payloads[name] = data
                if _sha(path.read_bytes()) != proposal["sha256"]:
                    raise ComponentStageBlocked("Synthetic ZIP changed while staging.")
                return payloads
        except (OSError, RuntimeError, ValueError, KeyError, zipfile.BadZipFile,
                install_review.PlanRejected) as exc:
            if isinstance(exc, ComponentStageBlocked):
                raise
            raise ComponentStageBlocked("Existing game-root ZIP parser rejected synthetic component.") from exc


def prepare_fixture(recipe, *, installed, owners, recorded_sha256,
                    installed_versions, proposals, archives, game_build):
    """Return a review-only staged batch, with zero live filesystem inputs."""
    components = _inputs(recipe, installed, owners, recorded_sha256,
                         installed_versions, proposals, archives, game_build)
    candidates = {}
    rows = []
    destination_owner = {}
    for proposal in proposals:
        cid = str(proposal["id"])
        payloads = _read_zip(recipe, components[cid], proposal, archives[cid])
        if not payloads:
            raise ComponentStageBlocked("Candidate ZIP did not map a component payload.")
        prior = {name for name, owner in owners.items() if owner == cid}
        if not prior.issubset(payloads):
            raise ComponentStageBlocked(
                "New ZIP omits a previously owned component file; explicit retirement not supported.")
        for name, content in payloads.items():
            if name.casefold() in destination_owner:
                raise ComponentStageBlocked("Two component ZIPs overlap a game-root destination.")
            destination_owner[name.casefold()] = cid
            current = {x.casefold(): x for x in installed}.get(name.casefold())
            if current is not None and (current != name or owners.get(name) != cid):
                raise ComponentStageBlocked("Destination overlaps an unrelated or manual mod file.")
            if current is not None and installed[name] == content:
                raise ComponentStageBlocked("Unchanged file needs a separate component update policy.")
            candidates[name] = content
        rows.append({
            "component_id": cid,
            "component_name": components[cid].get("name", cid),
            "phase": components[cid].get("phase", 1),
            "old_version": installed_versions[cid],
            "new_version": proposal["future_version"],
            "source_zip_sha256": proposal["sha256"],
            "files": len(payloads),
            "requires": tuple(proposal["requires"]),
            "status": "Synthetic mapping only — compatibility not proven",
            "authorized": False,
        })
    # Full-path uniqueness alone is insufficient: a target could require a
    # directory where a manually installed file already exists, or two target
    # files could be a parent/child pair on case-insensitive Proton filesystems.
    known = {x.casefold(): x for x in [*installed, *candidates]}
    for name in candidates:
        parts = name.split("/")
        for i in range(1, len(parts)):
            ancestor = "/".join(parts[:i])
            if ancestor.casefold() in known:
                raise ComponentStageBlocked(
                    "Component destination conflicts with an existing file ancestor.")
    if (len(candidates) > tx.MAX_FILES or
            sum(map(len, installed.values())) + sum(map(len, candidates.values()))
            > tx.MAX_TOTAL_BYTES):
        raise ComponentStageBlocked("Combined synthetic transaction exceeds safe limits.")
    files = tuple(
        {"path": name, "owner": destination_owner[name.casefold()],
         "action": "replace" if name in installed else "add",
         "sha256": _sha(data), "bytes": len(data)}
        for name, data in sorted(candidates.items()))
    return StagedBatch(
        GAME, game_build, dict(installed), tuple(sorted(owners)),
        candidates, dict(owners), tuple(rows), files)


def _zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as out:
        for name, content in files.items():
            out.writestr(name, content)
    return buf.getvalue()


def _scenario(recipe):
    # All bytes, versions, build labels and dependency declarations here are
    # invented for tests; NOT actual Cyberpunk mod compatibility guarantees.
    installed = {
        "bin/x64/plugins/cet.dll": b"synthetic-CET-v1",
        "red4ext/plugins/red4ext.dll": b"synthetic-RED4ext-v1",
        "red4ext/plugins/CyberpunkVR_Stereo/CyberpunkVR_Stereo.dll":
            b"synthetic-VRPort-v1",
        "r6/scripts/my-manual-overrides.reds": b"manual-file-keep-forever",
    }
    owners = {
        "bin/x64/plugins/cet.dll": "107",
        "red4ext/plugins/red4ext.dll": "2380",
        "red4ext/plugins/CyberpunkVR_Stereo/CyberpunkVR_Stereo.dll": "30093",
    }
    versions = {"107": "1.0.0", "2380": "1.0.0", "30093": "1.0.0"}
    contents = (
        ("107", "Cyber Engine Tweaks-107-v2.zip",
         {"CET-wrapper/bin/x64/plugins/cet.dll": b"synthetic-CET-v2",
          "CET-wrapper/r6/scripts/cet-new.reds": b"synthetic-helper"},
         ("2380",)),
        ("30093", "CyberpunkVR-Port-30093-v2.zip",
         {"red4ext/plugins/CyberpunkVR_Stereo/CyberpunkVR_Stereo.dll":
              b"synthetic-VRPort-v2",
          "r6/scripts/vr-helper.reds": b"synthetic-vr-helper"},
         ("107", "2380")),
    )
    archives = {}
    proposals = []
    for cid, filename, payload, requires in contents:
        blob = _zip(payload)
        archives[cid] = blob
        proposals.append({
            "id": cid, "archive_name": filename, "sha256": _sha(blob),
            "future_version": "2.0.0",
            "compatible_builds": ("SYNTHETIC-CYBERPUNK-BUILD",),
            "requires": requires,
        })
    return {
        "installed": installed, "owners": owners,
        "recorded_sha256": {name: _sha(installed[name]) for name in owners},
        "installed_versions": versions, "proposals": proposals, "archives": archives,
        "game_build": "SYNTHETIC-CYBERPUNK-BUILD",
    }


def rehearse_cyberpunk_components():
    recipe = hub.load_recipes()[GAME]  # read-only local recipe, not installed state
    example = _scenario(recipe)
    plan = prepare_fixture(recipe, **example)
    with tx.fixture_sandbox(plan.installed, plan.incoming, managed=plan.managed) as fixture:
        pre = tx.build_plan(fixture)
        try:
            tx.execute(fixture, pre, fault="after_replace:2")
        except tx.SimulatedCrash:
            pass
        else:
            raise AssertionError("Expected interrupted synthetic component update.")
        result = tx.recover(fixture)
        if (not result["status"].startswith("Rolled back") or
                tx._inventory(fixture) != pre.before or
                any(tx._read(fixture, "installed", key) != content
                    for key, content in plan.installed.items()) or
                any(tx._read(fixture, "installed", key, optional=True) is not None
                    for key in plan.incoming if key not in plan.installed) or
                tx._snapshot_dirs(fixture) != tx._journal(fixture)["dirs_before"]):
            raise AssertionError("Synthetic multi-component recovery did not restore originals.")
    return {
        "fixture_only": True, "selected_components": ("107", "30093"),
        "other_component_preserved": "2380" in example["installed_versions"],
        "untracked_mod_preserved": True,
        "staged_files": len(plan.destination_rows),
        "component_archives": len(plan.candidate_rows),
        "multi_component_rollback_passed": True,
        "temporary_fixture_discarded": True, "real_game_files_modified": False,
        "real_compatibility_verified": False,
        "live_update_authorized": False,
    }
