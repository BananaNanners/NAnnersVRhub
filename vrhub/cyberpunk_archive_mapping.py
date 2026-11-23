# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-W: strict, READ-ONLY Cyberpunk game-root ZIP target mapping.

Metadata inspection only. No extraction, archive mutation, mod installation,
ownership adoption, backups or live game writes. A complete mapping means that
all REGULAR ZIP MEMBERS were mapped to recipe game-root targets at THIS review,
not that the archive came from Nexus, is compatible with the installed game,
or may be applied. All live update gates remain closed.
"""
from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from . import hub, install_review, installed_integrity

GAME = "cyberpunk-2077"
MAX_FILES = install_review.MAX_ZIP_ENTRIES


class MappingBlocked(ValueError):
    """Untrusted/unmapped Cyberpunk game-root archive, always non-executable."""


def map_checked_zip(recipe, component, archive):
    """Inspect ZIP central directory only; return normalized relative targets.

    The caller must still independently verify the candidate's stable SHA-256
    and its selection from an on-demand scan. This function checks archive
    metadata and unique component identity without reading member contents.
    """
    if (not isinstance(recipe, dict) or recipe.get("id") != GAME
            or recipe.get("method") != "gameroot"
            or not isinstance(recipe.get("components"), list)
            or not isinstance(component, dict)):
        raise MappingBlocked("Unsupported game or component mapping.")
    cid = str(component.get("id", ""))
    known = {str(c.get("nexus_mod")): c for c in recipe["components"]}
    if len(known) != 15 or cid not in known or not cid.isdecimal():
        raise MappingBlocked("Cyberpunk component identity is incomplete.")
    path = Path(archive)
    if (not path.is_absolute() or path.suffix.casefold() != ".zip"
            or path.is_symlink() or not path.is_file()
            or any(parent.is_symlink() for parent in path.parents)):
        raise MappingBlocked("ZIP candidate is not a safely located regular file.")
    identified = hub._component_for(recipe, path.name)
    if identified is None or str(identified.get("nexus_mod")) != cid:
        raise MappingBlocked(
            "Archive filename does not uniquely identify the expected Nexus component.")
    try:
        # This rejects ZIP traversal, encrypted entries, symlink/device types,
        # casefold duplicate names and excessive declared sizes *before* mapping.
        try:
            install_review._zip_preflight(path)
        except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
            raise MappingBlocked(
                "ZIP security preflight rejected an unsafe, ambiguous or oversized member."
            ) from exc
        with zipfile.ZipFile(path) as z:
            try:
                regular = hub._zip_members(z)
            except (RuntimeError, ValueError) as exc:
                raise MappingBlocked("ZIP contains duplicate member names.") from exc
            if not 0 < len(regular) <= MAX_FILES:
                raise MappingBlocked("ZIP has no bounded regular-file inventory.")
            names = [Path(norm) for norm in regular.values()]
            # Reuse the real installer path normalization (single wrapper and
            # canonical top-level game folder case), but forbid silent ignores.
            try:
                mapping = hub._plan_gameroot(
                    names, path.name, recipe.get("root_dirs"))
            except (RuntimeError, ValueError) as exc:
                raise MappingBlocked(
                    "Archive wrapper or root directory layout is unsupported.") from exc
            try:
                hub._validate_component_plan(known[cid], mapping, path.name)
            except (RuntimeError, ValueError) as exc:
                raise MappingBlocked(
                    "Required component payload files are missing or misplaced.") from exc
            if len(mapping) != len(regular):
                raise MappingBlocked(
                    "ZIP contains unmapped files; complete update coverage is not proven.")
            output = [dest.as_posix() for _, dest in mapping]
            if len(output) != len(set(n.casefold() for n in output)):
                raise MappingBlocked("Multiple ZIP files map to the same target.")
            names_seen = {name.casefold() for name in output}
            for name in output:
                if installed_integrity._relative(name) is None:
                    raise MappingBlocked("Unsafe game-root destination.")
                parts = name.casefold().split("/")
                if any("/".join(parts[:i]) in names_seen
                       for i in range(1, len(parts))):
                    raise MappingBlocked("File/directory ancestry conflict in the ZIP.")
            return tuple(sorted(output)), {
                "game_id": GAME,
                "component_id": cid,
                "archive_members": len(regular),
                "mapped_targets": len(output),
                "all_regular_members_accounted": True,
                "source_version_authenticated": False,
                "game_build_compatibility_verified": False,
                "legacy_ownership_adopted": False,
                "live_update_authorized": False,
            }
    except MappingBlocked:
        raise
    except (OSError, RuntimeError, ValueError, KeyError,
            zipfile.BadZipFile, install_review.PlanRejected) as exc:
        # Don't surface archive-controlled filenames or local absolute paths.
        raise MappingBlocked(
            "Cyberpunk ZIP metadata, member paths or required-file shape "
            "failed the read-only mapping checks.") from exc



def rehearse_synthetic_archive_mapping():
    """Disposable ZIP metadata rehearsal. Real game, Nexus, state untouched."""
    recipe = hub.load_recipes()[GAME]
    with tempfile.TemporaryDirectory(
            prefix="nanners-dev5d3w-cyber-zip-") as temp:
        base = Path(temp)
        def make(name, entries):
            file = base / name
            with zipfile.ZipFile(file, "w", zipfile.ZIP_DEFLATED) as z:
                for member, data in entries:
                    z.writestr(member, data)
            return file

        direct = make("CET-107-fixture.zip", [
            ("BIN/x64/plugins/fixture.asi", b"INVENTED-CET")])
        wrapped = make("CyberpunkVR-Port-30093-fixture.zip", [
            ("Wrapper/red4ext/plugins/CyberpunkVR_Stereo/"
             "CyberpunkVR_Stereo.dll", b"INVENTED-VR"),
            ("Wrapper/r6/scripts/fixture.reds", b"INVENTED-SCRIPT")])
        mapped_a, a = map_checked_zip(
            recipe, {"id":"107"}, direct)
        mapped_b, b = map_checked_zip(
            recipe, {"id":"30093"}, wrapped)
        invalid = (
            ("CET-107-2380-fixture.zip",
             [("bin/x64/plugins/fixture.asi", b"ambiguous")], "107"),
            ("CET-107-readme-fixture.zip",
             [("bin/x64/plugins/fixture.asi", b"valid"),
              ("README.txt", b"unmapped")], "107"),
            ("CET-107-traversal-fixture.zip",
             [("../outside.dll", b"unsafe")], "107"),
            ("VRPort-30093-missing-fixture.zip",
             [("red4ext/plugins/incorrect.dll", b"incomplete")], "30093"),
        )
        refused = 0
        for filename, entries, cid in invalid:
            source=make(filename, entries)
            try:
                map_checked_zip(recipe, {"id":cid}, source)
            except MappingBlocked:
                refused += 1
        if (len(mapped_a) != 1 or len(mapped_b) != 2 or refused != 4
                or not a["all_regular_members_accounted"]
                or not b["all_regular_members_accounted"]):
            raise MappingBlocked("Synthetic ZIP fixture rehearsal incomplete.")
    return {
        "fixture_only":True,
        "successful_archive_maps":2,
        "mapped_destination_paths":3,
        "blocked_archives":refused,
        "direct_and_wrapper_layouts":True,
        "all_regular_members_accounted_for_successes":True,
        "real_archive_source_authenticated":False,
        "real_game_compatibility_verified":False,
        "real_game_files_modified":False,
        "live_update_authorized":False,
        "temporary_fixture_discarded":not base.exists(),
    }
