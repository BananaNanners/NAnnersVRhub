# SPDX-FileCopyrightText: 2026 NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-N: pinned-package staging in disposable fixtures ONLY.

Real installed games and downloaded archives are deliberately inaccessible:
this API accepts synthetic byte blobs, never source or destination file paths.
It reuses the existing pinned-package ZIP member mapper for three supported
recipe shapes, but its staged files belong ONLY to offline_transaction fixtures.
Neither mapping nor a passing compatibility declaration authorizes an update.
"""
from __future__ import annotations

import hashlib
import io
import re
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from . import bepinex, offline_transaction as tx

SUPPORTED = frozenset(("valheim", "subnautica", "elden-ring"))
MAX_ARCHIVES = 3
MAX_ZIP_BYTES = 32 * 1024 * 1024
MAX_ENTRIES = 1000
MAX_STAGED_FILES = tx.MAX_FILES
MAX_STAGED_BYTES = tx.MAX_TOTAL_BYTES
_NUMERIC_VERSION = re.compile(r"(0|[1-9]\d*)(?:\.(0|[1-9]\d*))*\Z")


class StageBlocked(RuntimeError):
    """No trustworthy *fixture* staging plan can be constructed."""


@dataclass(frozen=True)
class StagedFixture:
    """Synthetic, immutable (by convention) bytes ready for a disposable rehearsal."""
    game_id: str
    installed: dict[str, bytes]
    incoming: dict[str, bytes]
    managed: tuple[str, ...]
    package_rows: tuple[dict, ...]
    destination_rows: tuple[dict, ...]
    game_build: str
    status: str = "Synthetic staging reviewed — NOT live compatible"
    authorized: bool = False
    real_game_compatibility_verified: bool = False
    live_executor_connected: bool = False


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _version(version):
    if not isinstance(version, str) or len(version) > 70 or not _NUMERIC_VERSION.fullmatch(version):
        raise StageBlocked("Version ordering requires plain numeric fixture versions.")
    return tuple(int(x) for x in version.split("."))


def _validate_build(game_build, package):
    if not isinstance(game_build, str) or not game_build or len(game_build) > 80:
        raise StageBlocked("Synthetic game-build identity is missing.")
    allowed = package.get("compatible_builds")
    if (not isinstance(allowed, (list, tuple)) or not allowed or len(allowed) > 20 or
            any(not isinstance(v, str) or not v or len(v) > 80 for v in allowed) or
            game_build not in allowed):
        raise StageBlocked("Game-build compatibility has not been explicitly declared.")
    # This is deliberately never represented as actual game/Proton compatibility.


def _validate_inventory(installed, managed):
    if not isinstance(installed, dict) or not installed:
        raise StageBlocked("Synthetic installed-file inventory is missing.")
    if not isinstance(managed, (tuple, list)):
        raise StageBlocked("Synthetic ownership inventory is missing.")
    try:
        tx._check_names(installed)
        tx._check_names(managed)
    except tx.TransactionBlocked as exc:
        raise StageBlocked("Unsafe or colliding synthetic installed paths.") from exc
    if not set(managed).issubset(installed):
        raise StageBlocked("Cannot silently adopt manually installed files.")
    total = 0
    for name, data in installed.items():
        if not isinstance(data, bytes) or len(data) > tx.MAX_FILE_BYTES:
            raise StageBlocked("Synthetic installed payload is not bounded bytes.")
        total += len(data)
    if total > MAX_STAGED_BYTES:
        raise StageBlocked("Synthetic installed bytes exceed fixture limit.")
    return tuple(managed)


def _check_manifest(game_id, package_specs, archives):
    if game_id not in SUPPORTED:
        raise StageBlocked("Only the three pinned-package recipe shapes are supported.")
    if (not isinstance(package_specs, (tuple, list)) or not package_specs or
            len(package_specs) > MAX_ARCHIVES or
            not isinstance(archives, dict) or len(archives) != len(package_specs)):
        raise StageBlocked("One synthetic archive is required per declared package.")
    ids = []
    for package in package_specs:
        if not isinstance(package, dict):
            raise StageBlocked("Invalid package declaration.")
        cid = package.get("id")
        if (not isinstance(cid, str) or not cid or len(cid) > 80 or
                not isinstance(package.get("required_files"), list) or
                not package["required_files"]):
            raise StageBlocked("Pinned package id and required destination files are mandatory.")
        ids.append(cid)
        if (not isinstance(package.get("sha256"), str) or
                not re.fullmatch(r"[0-9a-f]{64}", package["sha256"])):
            raise StageBlocked("Prospective package must have a precise synthetic SHA-256 pin.")
        if (type(package.get("phase")) is not int or
                package["phase"] < 1 or package["phase"] > MAX_ARCHIVES):
            raise StageBlocked("Dependency phase must be explicit and bounded.")
        installed = _version(package.get("installed_version"))
        new = _version(package.get("future_version"))
        if new <= installed:
            raise StageBlocked("Downgrades or same-version replacements require separate review.")
        required = package.get("requires", [])
        if (not isinstance(required, (tuple, list)) or
                len(required) >= MAX_ARCHIVES or
                any(not isinstance(x, str) or x == cid for x in required) or
                len(set(required)) != len(required)):
            raise StageBlocked("Malformed package dependency list.")
    if len(ids) != len(set(ids)) or len(ids) != len({x.casefold() for x in ids}):
        raise StageBlocked("Duplicate or differently cased package identity.")
    if set(archives) != set(ids):
        raise StageBlocked("Synthetic archive set does not match pinned recipe.")
    positions = {pkg["id"]: i for i, pkg in enumerate(package_specs)}
    stages = {pkg["id"]: pkg["phase"] for pkg in package_specs}
    for pkg in package_specs:
        for required in pkg.get("requires", []):
            if (required not in positions or stages[required] >= pkg["phase"] or
                    positions[required] >= positions[pkg["id"]]):
                raise StageBlocked("Dependency ordering or required package is unresolved.")


def _extract_synthetic_package(game_id, package, raw):
    """Materialize only supplied synthetic bytes under an owned /tmp folder."""
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_ZIP_BYTES:
        raise StageBlocked("ZIP must be bounded, freshly supplied synthetic bytes.")
    if _hash(raw) != package["sha256"]:
        raise StageBlocked("Synthetic ZIP differs from its explicit prospective SHA-256 pin.")
    # The existing parser takes a path. NEVER accept a path from the caller;
    # create it ourselves in a disposable fixture-only staging directory.
    with tempfile.TemporaryDirectory(prefix="nanners-dev5d3n-stage-", dir="/tmp") as temp:
        archive = Path(temp) / "synthetic-pinned-package.zip"
        archive.write_bytes(raw)
        archive.chmod(0o600)
        try:
            _, mapping = bepinex.archive_plan(
                archive, {"id": game_id, "packages": [package]})
            if not mapping:
                raise StageBlocked("Pinned package has no mapped payload files.")
            if len(mapping) > MAX_ENTRIES:
                raise StageBlocked("Package exceeds fixture staging entry limit.")
            stage = {}
            total = 0
            with zipfile.ZipFile(io.BytesIO(raw)) as source:
                for origin, target in sorted(mapping.items()):
                    name = PurePosixPath(target).as_posix()
                    if name in stage:
                        raise StageBlocked("Duplicate fixture destination mapping.")
                    if len(source.getinfo(origin).filename) > 4096:
                        raise StageBlocked("Excessive archive member name.")
                    with source.open(origin) as member:
                        payload = member.read(tx.MAX_FILE_BYTES + 1)
                        if len(payload) > tx.MAX_FILE_BYTES:
                            raise StageBlocked("Staged file exceeds transaction limit.")
                        total += len(payload)
                        if total > MAX_STAGED_BYTES:
                            raise StageBlocked("Staged package exceeds transaction budget.")
                        stage[name] = payload
            if _hash(archive.read_bytes()) != package["sha256"]:
                raise StageBlocked("Synthetic ZIP changed while mapping.")
            return stage
        except (zipfile.BadZipFile, KeyError, ValueError, OSError, RuntimeError) as exc:
            if isinstance(exc, StageBlocked):
                raise
            raise StageBlocked("Synthetic archive failed the existing pinned-package safety parser.") from exc


def prepare_fixture(game_id, game_build, package_specs, archives,
                    installed, *, managed):
    """Build a fail-closed hypothetical pinned update payload (no real paths).

    package_specs must be in declared dependency order, with explicit synthetic
    installed/future versions, phase, compatible builds, SHA pins and required
    ZIP members. Results are not a live installation plan or compatibility proof.
    """
    _check_manifest(game_id, package_specs, archives)
    owned = _validate_inventory(installed, managed)
    prospective = {}
    package_rows = []
    total = sum(len(data) for data in installed.values())
    destination_owner = {}
    for package in package_specs:
        _validate_build(game_build, package)
        cid = package["id"]
        files = _extract_synthetic_package(game_id, package, archives[cid])
        for destination, payload in files.items():
            try:
                tx._relative(destination)
            except tx.TransactionBlocked as exc:
                raise StageBlocked("ZIP maps to an unsafe fixture destination.") from exc
            key = destination.casefold()
            if key in destination_owner:
                raise StageBlocked("Prospective package destinations overlap or differ only in case.")
            if destination in installed and installed[destination] == payload:
                raise StageBlocked("Identical synthetic file needs no replacement; review package manifest.")
            destination_owner[key] = cid
            total += len(payload)
            if total > MAX_STAGED_BYTES:
                raise StageBlocked("Total fixture exceeds staging byte budget.")
            prospective[destination] = payload
        package_rows.append({
            "id": cid, "phase": package["phase"],
            "installed_version": package["installed_version"],
            "future_version": package["future_version"],
            "verified_synthetic_pin": package["sha256"],
            "mapped_files": len(files),
            "compatibility": "Synthetic declared game build matches; real compatibility UNVERIFIED",
            "live_authorized": False,
        })
    if len(prospective) > MAX_STAGED_FILES:
        raise StageBlocked("Too many files for the bounded transaction engine.")
    # Shared Proton/Windows paths may be case-insensitive. Protect *all*
    # existing files, including untracked manual modifications.
    existing_case = {name.casefold(): name for name in installed}
    for destination in prospective:
        other = existing_case.get(destination.casefold())
        if other is not None and (other != destination or other not in owned):
            raise StageBlocked("Destination overlaps an untracked or differently cased file.")
    if len({name.casefold() for name in prospective}) != len(prospective):
        raise StageBlocked("Case-insensitive destination collision.")
    destination_rows = tuple(
        {"path": name, "action": "replace" if name in owned else "add",
         "package_id": destination_owner[name.casefold()],
         "payload_sha256": _hash(payload), "bytes": len(payload)}
        for name, payload in sorted(prospective.items())
    )
    return StagedFixture(
        game_id=game_id, installed=dict(installed),
        incoming=prospective, managed=owned,
        package_rows=tuple(package_rows),
        destination_rows=destination_rows, game_build=game_build,
    )


def _synthetic_zip(files):
    blob = io.BytesIO()
    with zipfile.ZipFile(blob, "w", compression=zipfile.ZIP_DEFLATED) as out:
        for name, body in files.items():
            out.writestr(name, body)
    return blob.getvalue()


def _scenario(game_id):
    """Examples intentionally invented, not actual versions, pins or game builds."""
    old = {
        "winhttp.dll": b"synthetic-old-loader",
        "BepInEx/core/BepInEx.dll": b"synthetic-old-core",
        "BepInEx/plugins/vrmod.dll": b"synthetic-old-vr",
        "BepInEx/config/custom.ini": b"user-settings-must-survive",
    }
    if game_id == "valheim":
        maps = (
            ("loader", {
                "BepInExPack_Valheim/winhttp.dll": b"future-loader",
                "BepInExPack_Valheim/BepInEx/core/BepInEx.dll": b"future-core",
            }, ["winhttp.dll", "BepInEx/core/BepInEx.dll"], 1, []),
            ("vrmod", {
                "BepInEx/plugins/vrmod.dll": b"future-vr",
                "valheim_Data/Managed/SteamVR.dll": b"future-sdk",
            }, ["BepInEx/plugins/vrmod.dll"], 2, ["loader"]),
        )
    elif game_id == "subnautica":
        maps = (
            ("loader", {
                "winhttp.dll": b"future-loader",
                "BepInEx/core/BepInEx.dll": b"future-core",
            }, ["winhttp.dll", "BepInEx/core/BepInEx.dll"], 1, []),
            ("vrmod", {
                "BepInEx/plugins/vrmod.dll": b"future-vr",
                "Subnautica_Data/Managed/SteamVR.dll": b"future-sdk",
            }, ["BepInEx/plugins/vrmod.dll"], 2, ["loader"]),
        )
    else:
        old = {
            "Game/dxgi.dll": b"synthetic-old-reshade",
            "Game/ERVR/ERVR.dll": b"synthetic-old-vr",
            "Game/custom-user.ini": b"user-settings-must-survive",
        }
        maps = (
            ("ervr", {
                "dxgi.dll": b"future-reshade",
                "ERVR/ERVR.dll": b"future-ervr",
            }, ["Game/dxgi.dll", "Game/ERVR/ERVR.dll"], 1, []),
        )
    packages, archives = [], {}
    for cid, contents, required, phase, depends in maps:
        archive = _synthetic_zip(contents)
        archives[cid] = archive
        packages.append({
            "id": cid, "name": "Synthetic " + cid, "sha256": _hash(archive),
            "required_files": required, "installed_version": "1.0.0",
            "future_version": "1.1.0", "phase": phase,
            "requires": depends, "compatible_builds": ["SIMULATED-BUILD-N"],
        })
    return "SIMULATED-BUILD-N", packages, archives, old, tuple(
        n for n in old if "custom" not in n.lower()
    )


def rehearse_pinned_packages():
    """Three completely disposable staging+interruption+rollback rehearsals."""
    results = []
    for game_id in ("valheim", "subnautica", "elden-ring"):
        build, specs, archives, old, managed = _scenario(game_id)
        stage = prepare_fixture(
            game_id, build, specs, archives, old, managed=managed)
        if stage.authorized or stage.real_game_compatibility_verified:
            raise AssertionError("Synthetic review unexpectedly authorized real game.")
        with tx.fixture_sandbox(stage.installed, stage.incoming, managed=stage.managed) as fixture:
            plan = tx.build_plan(fixture)
            if len(plan.rows) != len(stage.destination_rows):
                raise AssertionError("Staged targets differ from fixture transaction.")
            try:
                tx.execute(fixture, plan, fault="after_replace:1")
            except tx.SimulatedCrash:
                pass
            else:
                raise AssertionError("Expected interrupted fixture update.")
            result = tx.recover(fixture)
            if (tx._inventory(fixture) != plan.before or
                    any(tx._read(fixture, "installed", n) != content
                        for n, content in old.items()) or
                    any(tx._read(fixture, "installed", n, optional=True) is not None
                        for n in stage.incoming if n not in old) or
                    tx._snapshot_dirs(fixture) != tx._journal(fixture)["dirs_before"]):
                raise AssertionError("Pinned fixture update recovery did not restore state.")
            results.append({
                "game": game_id, "fixture_only": True,
                "packages": len(stage.package_rows),
                "mapped_destinations": len(stage.destination_rows),
                "synthetic_pin_verified": True,
                "declared_fixture_build_checked": True,
                "rollback_passed": "Rolled back" in result["status"],
                "real_compatibility_verified": False,
                "live_update_authorized": False,
            })
    return {
        "fixture_only": True, "results": results,
        "temporary_fixtures_discarded": True,
        "real_game_files_modified": False,
        "real_game_compatibility_verified": False,
        "live_update_authorized": False,
    }
