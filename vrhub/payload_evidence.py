# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-X: bounded, metadata-only Cyberpunk ZIP payload classification.

Categories are derived from filenames/ZIP metadata, never member contents.
An archive member's *class* is not permission to extract, skip, replace or
execute it. The strict W target mapper is deliberately unchanged: optional,
documentation and unknown members still prevent a complete install mapping.

This module does not read member payloads, write files, authenticate Nexus
releases, verify compatibility, or change real installation evidence.
"""
from __future__ import annotations

from pathlib import Path
import zipfile

from . import hub, install_review, installed_integrity

GAME = "cyberpunk-2077"
DOCUMENT_NAMES = frozenset((
    "readme", "readme.txt", "readme.md", "readme.markdown",
    "license", "license.txt", "license.md",
    "licence", "licence.txt", "licence.md",
    "copying", "copying.txt", "copying.md",
    "changelog", "changelog.txt", "changelog.md",
    "changes.txt", "changes.md",
    "credits.txt", "credits.md",
    "authors.txt", "authors.md",
))
DOCUMENT_FOLDERS = frozenset(("docs", "documentation"))
OPTIONAL_FOLDERS = frozenset((
    "optional", "optionals", "optional files",
    "alternatives", "variants",
))
CLASSES = ("installable", "documentation", "optional", "unknown", "unsafe")
MAX_SAMPLE_PER_CLASS = 4
MAX_LABEL_CHARS = 140


def _blank(component_id):
    return {
        "schema": 1, "game_id": GAME, "component_id": component_id,
        "counts": {name: 0 for name in CLASSES},
        "samples": {name: [] for name in CLASSES},
        "regular_members": None, "mapped_destinations": 0,
        "member_classification_complete": False,
        "metadata_preflight_passed": False,
        "single_wrapper_detected": False,
        "required_payload_contract_exists": False,
        "required_payload_contract_satisfied": False,
        "recognized_documentation_is_noninstallable": True,
        "optional_files_automatically_selected": False,
        "unknown_files_automatically_ignored": False,
        "safe_to_apply": False, "source_authenticated": False,
        "latest_release_verified": False, "game_build_verified": False,
        "runtime_compatibility_verified": False,
        "dependencies_verified": False, "member_crc_verified": False,
        "current_install_ownership_verified": False,
        "fresh_backup_verified": False,
        "live_update_authorized": False,
        "reason": "Candidate has not passed read-only payload classification.",
    }


def _display(name):
    """Do not expose control characters or unbounded untrusted ZIP names."""
    if not isinstance(name, str) or not name.isprintable():
        return "(nonprintable member name)"
    if len(name) > MAX_LABEL_CHARS:
        return name[:MAX_LABEL_CHARS] + "…"
    return name


def _append(result, category, name):
    result["counts"][category] += 1
    if len(result["samples"][category]) < MAX_SAMPLE_PER_CLASS:
        result["samples"][category].append(_display(name))


def _docs_or_optionals(name, wrapper):
    parts = name.casefold().split("/")
    if wrapper and parts and parts[0] == wrapper.casefold():
        parts = parts[1:]
    if not parts:
        return "unknown"
    if (len(parts) == 1 and parts[0] in DOCUMENT_NAMES
            or len(parts) == 2 and parts[0] in DOCUMENT_FOLDERS
            and parts[1] in DOCUMENT_NAMES):
        return "documentation"
    if len(parts) >= 2 and parts[0] in OPTIONAL_FOLDERS:
        return "optional"
    return "unknown"


def classify_zip(recipe, component, archive):
    """Classify all regular ZIP entries as advisory evidence only.

    Uses the same safe metadata preflight and root mapping as the W mapper.
    Unknown or unsafe data is never upgraded to an allowed exclusion. The
    companion safety review binds this report to a newly stable archive hash.
    """
    cid = str(component.get("id", "")) if isinstance(component, dict) else ""
    result = _blank(cid)
    if (not isinstance(recipe, dict) or recipe.get("id") != GAME
            or recipe.get("method") != "gameroot"
            or not isinstance(recipe.get("components"), list)
            or not isinstance(component, dict)):
        result["reason"] = "Cyberpunk recipe/component identity is unavailable."
        return result
    matches = [c for c in recipe["components"]
               if str(c.get("nexus_mod")) == cid]
    if len(matches) != 1 or not cid.isdecimal():
        result["reason"] = "Exact recipe component identity is not established."
        return result
    path = Path(archive)
    if (not path.is_absolute() or path.suffix.lower() != ".zip"
            or path.is_symlink() or not path.is_file()
            or any(parent.is_symlink() for parent in path.parents)):
        result["reason"] = "Candidate ZIP is missing or its file path is unsafe."
        return result
    selected = hub._component_for(recipe, path.name)
    if selected is None or str(selected.get("nexus_mod")) != cid:
        result["reason"] = "ZIP filename does not uniquely identify the component."
        return result

    try:
        install_review._zip_preflight(path)
        result["metadata_preflight_passed"] = True
        with zipfile.ZipFile(path) as z:
            regular = hub._zip_members(z)
            if not 0 < len(regular) <= install_review.MAX_ZIP_ENTRIES:
                raise ValueError("Invalid regular-member count")
            result["regular_members"] = len(regular)
            names = [Path(name) for name in regular.values()]
            try:
                mapped = hub._plan_gameroot(names, path.name, recipe.get("root_dirs"))
            except (RuntimeError, ValueError):
                mapped = []
            mapped_src = {src.as_posix(): dest.as_posix() for src, dest in mapped}
            mapped_valid = (bool(mapped) and
                            len(mapped_src) == len(mapped) and
                            len({v.casefold() for v in mapped_src.values()}) == len(mapped)
                            and all(installed_integrity._relative(dest) is not None
                                    for dest in mapped_src.values()))
            if not mapped_valid:
                mapped_src = {}

            roots = {str(x).casefold() for x in
                     recipe.get("root_dirs", hub.ROOT_DIRS)}
            prefixes = {
                src.parts[0] for src, _ in mapped
                if len(src.parts) >= 3
                and src.parts[0].casefold() not in roots
                and src.parts[1].casefold() in roots
            }
            wrapper = next(iter(prefixes)) if len(prefixes) == 1 else None
            result["single_wrapper_detected"] = wrapper is not None
            required = hub._component_required_files(matches[0])
            result["required_payload_contract_exists"] = bool(required)
            if required and mapped_src:
                actual = {v.casefold() for v in mapped_src.values()}
                result["required_payload_contract_satisfied"] = all(
                    required_path.as_posix().casefold() in actual
                    for required_path in required
                )
            for name in regular.values():
                if name in mapped_src:
                    _append(result, "installable", mapped_src[name])
                else:
                    _append(result, _docs_or_optionals(name, wrapper), name)
            result["mapped_destinations"] = result["counts"]["installable"]
            result["member_classification_complete"] = (
                sum(result["counts"].values()) == len(regular)
                and result["metadata_preflight_passed"])
            if (not mapped_valid and result["counts"]["installable"] == 0):
                result["reason"] = (
                    "No complete supported game-root target mapping; "
                    "documentation/optional labels do not authorize exclusions.")
            elif result["counts"]["unknown"] or result["counts"]["optional"]:
                result["reason"] = (
                    "Optional/unknown ZIP members require component-specific review; "
                    "no files automatically selected or skipped.")
            elif result["counts"]["documentation"]:
                result["reason"] = (
                    "Known documentation members are identified for review; "
                    "strict complete install mapping remains blocked.")
            else:
                result["reason"] = (
                    "Regular ZIP members were classified; compatibility and "
                    "release authenticity remain unverified.")
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile,
            install_review.PlanRejected, KeyError):
        # A failed preflight may not reveal a trustworthy individual unsafe
        # count; never manufacture one or display hostile raw ZIP paths.
        result = _blank(cid)
        result["counts"]["unsafe"] = 1
        result["regular_members"] = None
        result["reason"] = (
            "Unsafe or malformed ZIP metadata: entry inventory unavailable; "
            "unsafe count is a blocking signal, not an exact file total.")
    return result


def rehearse_synthetic_payload_classification():
    """Disposable synthetic ZIPs exercising all categories; no user archives."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix="nanners-dev5d3x-payload-") as root:
        p = Path(root)
        recipe = hub.load_recipes()[GAME]
        def make(name, files):
            candidate = p / name
            with zipfile.ZipFile(candidate, "w", zipfile.ZIP_DEFLATED) as z:
                for rel, payload in files:
                    z.writestr(rel, payload)
            return candidate

        tests = (
            ("CET-107-install.zip", [
                ("bin/x64/plugins/cet.asi", b"synthetic")]),
            ("CET-107-docs.zip", [
                ("Wrapper/bin/x64/plugins/cet.asi", b"synthetic"),
                ("Wrapper/README.md", b"synthetic docs"),
                ("Wrapper/docs/LICENSE.txt", b"synthetic licence")]),
            ("CET-107-optional.zip", [
                ("bin/x64/plugins/cet.asi", b"synthetic"),
                ("Optional/alternate.dll", b"synthetic alternate")]),
            ("CET-107-unknown.zip", [
                ("bin/x64/plugins/cet.asi", b"synthetic"),
                ("setup.exe", b"synthetic unknown")]),
            ("CET-107-unsafe.zip", [
                ("../escape.dll", b"synthetic invalid")]),
        )
        results = [classify_zip(recipe, {"id": "107"}, make(n, members))
                   for n, members in tests]
        if (results[0]["counts"]["installable"] != 1
                or results[1]["counts"]["documentation"] != 2
                or results[2]["counts"]["optional"] != 1
                or results[3]["counts"]["unknown"] != 1
                or results[4]["counts"]["unsafe"] != 1
                or any(r["live_update_authorized"] for r in results)):
            raise RuntimeError("Synthetic payload classification rehearsal failed.")
    return {
        "fixture_only": True, "cases": len(results),
        "classifications": {
            "installable": results[0]["counts"]["installable"],
            "documentation": results[1]["counts"]["documentation"],
            "optional": results[2]["counts"]["optional"],
            "unknown": results[3]["counts"]["unknown"],
            "unsafe": results[4]["counts"]["unsafe"],
        },
        "temporary_fixture_discarded": not p.exists(),
        "real_archive_bytes_read": False,
        "real_game_files_modified": False,
        "source_authenticated": False,
        "game_build_compatibility_verified": False,
        "live_update_authorized": False,
    }
