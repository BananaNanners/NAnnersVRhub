# SPDX-License-Identifier: GPL-3.0-only
"""Read-only UEVR dependency review and offline Fatekeeper backend staging."""
from dataclasses import dataclass, field
from hashlib import file_digest, sha256
from tempfile import NamedTemporaryFile
from pathlib import Path
import zipfile

from . import hub, profile_safety, install_review, download_planner

SUPPORTED = {"fatekeeper", "hogwarts-legacy"}

FATEKEEPER_BACKEND_URL = (
    "https://github.com/joeyhodge/UEVR/releases/download/"
    "100526UE58_6RefreshUpdate/UEVRBackend.dll"
)
FATEKEEPER_BACKEND_SHA256 = "b883dd7f0b5e06bff74b42b4fabc66fc7c39c6baff57634d5132abe5b05ed6fc"
FATEKEEPER_BACKEND_SIZE = 15_203_840


# These files can contain local state even though the ZIP ships defaults.
FATEKEEPER_LOCAL_PROFILE_FILES = frozenset({
    "cache/sdk_discovery.json",
    "data/dev/attachments_config_dev.json",
    "config.txt",
    "imgui.ini",
    "data/config_default.json",
})


def fatekeeper_file_decision(component, name, existing_digest, incoming_digest):
    if existing_digest is None:
        return "Install"
    if (existing_digest == incoming_digest or
            component == "Profile" and name in FATEKEEPER_LOCAL_PROFILE_FILES):
        return "Preserve"
    return "Replace"


def _file_decisions(component, incoming, snapshot):
    existing = snapshot["files"]
    return tuple(
        (fatekeeper_file_decision(component, name, existing.get(name, {}).get("sha256"),
                                 incoming[name]) if name in incoming else "Preserve",
         component, name)
        for name in sorted(incoming.keys() | existing.keys())
    )


def managed_compatibility(state, folder, component, incoming):
    """Conservative maintenance check; never adopt or delete omitted files."""
    import re
    key = "fatekeeper" if component == "Injector" else "fatekeeper:profile"
    record = state.get(key)
    if not isinstance(record, dict) or record.get("installer") != "fatekeeper-pair-fk4":
        return ()
    def valid_name(name):
        return (isinstance(name, str) and bool(name) and
                not any(c in name for c in (chr(92), ":", chr(0))) and
                all(part not in ("", ".", "..") for part in name.split("/")))
    manifest = record.get("reviewed_dependencies")
    owned = record.get("files")
    if (record.get("root") != str(folder) or not isinstance(manifest, dict)
            or not manifest or not isinstance(owned, list)
            or not isinstance(record.get("archive_sha256"), str)
            or not re.fullmatch("[0-9a-f]{64}", record["archive_sha256"])):
        return (f"{component}: previous managed installation records need review.",)
    names = set()
    for name, meta in manifest.items():
        if (not valid_name(name) or not isinstance(meta, dict)
                or not isinstance(meta.get("sha256"), str)
                or not re.fullmatch("[0-9a-f]{64}", meta["sha256"])
                or type(meta.get("size")) is not int or meta["size"] < 0):
            return (f"{component}: previous dependency records need review.",)
        names.add(name)
    seen = set()
    for path in owned:
        if not isinstance(path, str) or not path.startswith(str(folder) + "/"):
            return (f"{component}: previous file ownership needs review.",)
        name = path[len(str(folder)) + 1:]
        if not valid_name(name) or name in seen:
            return (f"{component}: previous file ownership needs review.",)
        seen.add(name)
    return tuple(f"{component}: {name} is no longer supplied. Preserved; compatibility review required."
                 for name in sorted((names | seen) - set(incoming)))


def stage_fatekeeper_backend(staging_directory: Path, asset: bytes) -> Path:
    """Replace the backend in a disposable injector staging directory."""
    if len(asset) != FATEKEEPER_BACKEND_SIZE or sha256(asset).hexdigest() != FATEKEEPER_BACKEND_SHA256:
        raise RuntimeError("Fatekeeper backend verification failed. Retry using the approved release asset.")
    if staging_directory.is_symlink() or not staging_directory.is_dir():
        raise RuntimeError("Choose a regular injector staging directory.")
    destination = staging_directory / "UEVRBackend.dll"
    if destination.is_symlink() or not destination.is_file():
        raise RuntimeError("The staged Fatekeeper injector is missing a regular backend file.")
    if (destination.stat().st_size == FATEKEEPER_BACKEND_SIZE
            and profile_safety._digest(destination) == FATEKEEPER_BACKEND_SHA256):
        return destination
    with NamedTemporaryFile(dir=staging_directory, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        try:
            temporary.write(asset)
            temporary.close()
            temporary_path.replace(destination)
        finally:
            temporary_path.unlink(missing_ok=True)
    return destination



@dataclass(frozen=True)
class DependencyReview:
    game_name: str
    injector_archive: str
    injector_sha256: str
    injector_destination: str
    injector_files: tuple[str, ...]
    injector_bytes: int
    existing_files: int
    existing_dirs: int
    existing_bytes: int
    profile: profile_safety.ProfilePlan
    release_tags: tuple[tuple[str, ...], tuple[str, ...]]
    blockers: tuple[str, ...]
    backend_status: str = ""
    needs_backend_verification: bool = False
    injector_snapshot: dict = field(default_factory=dict, repr=False)
    file_decisions: tuple[tuple[str, str, str], ...] = ()
    verification_failed: bool = False
    failed_archives: tuple[str, ...] = ()
    compatibility_blockers: tuple[str, ...] = ()


def build_plan(recipe, archives, steam_roots=None, *, evidence=None):
    if recipe.get("id") not in SUPPORTED or recipe.get("method") != "uevr" or not recipe.get("profile"):
        raise RuntimeError("Unsupported UEVR dependency review.")
    if len(archives) != 2:
        raise RuntimeError("Exactly one injector archive and one profile archive are required.")
    paths = tuple(Path(p) for p in archives)
    identities = tuple(download_planner.archive_identity(p) for p in paths)
    if not all(identities) or len({(i["dev"], i["ino"]) for i in identities}) != 2:
        raise RuntimeError("Two distinct, regular archives are required.")
    if any(i["size"] <= 0 or i["size"] > install_review.MAX_ARCHIVE_BYTES for i in identities):
        raise RuntimeError("Archive is empty or exceeds review limits.")
    prefix = hub._pfx(recipe, steam_roots)
    dest = hub._uevr_dir(recipe, steam_roots)
    profile_dest = hub.profile_dir(recipe, steam_roots)
    profile_safety._safe_destination(dest, prefix)
    profile_safety._safe_destination(profile_dest, prefix)
    if dest.is_relative_to(profile_dest) or profile_dest.is_relative_to(dest):
        raise RuntimeError("Injector and profile destinations overlap.")
    if any(p.is_relative_to(prefix.resolve()) for p in paths):
        raise RuntimeError("Choose archives outside the game's prefix.")
    pins = recipe.get("archive_pins", {}) if recipe["id"] == "fatekeeper" else {}
    digest = profile_safety._digest(paths[0])
    if pins and digest != pins.get("uevr"):
        raise RuntimeError("Choose the official UEVR Nightly 1133 uevr.zip. Its checksum did not match.")
    install_review._zip_preflight(paths[0])
    with zipfile.ZipFile(paths[0]) as z:
        names = hub._zip_members(z)
        anchors = [n for n in names.values() if n.rsplit("/", 1)[-1] == "UEVRInjector.exe"]
        if len(anchors) != 1:
            raise RuntimeError("Expected exactly one UEVRInjector.exe in the injector archive.")
        wrapper = anchors[0][:-len("UEVRInjector.exe")]
        entries = [(orig, name[len(wrapper):]) for orig, name in names.items() if name.startswith(wrapper)]
        rels = tuple(sorted(rel for _, rel in entries))
        folded = {n.casefold() for n in rels}
        if "UEVRBackend.dll" not in rels:
            raise RuntimeError("Injector archive is missing its UEVRBackend.dll.")
        if len(folded) != len(rels) or any(
                "/".join(rel.casefold().split("/")[:i]) in folded
                for rel in rels for i in range(1, len(rel.split("/")))):
            raise RuntimeError("Injector archive contains colliding paths.")
        size = sum(z.getinfo(orig).file_size for orig, _ in entries)
        backend_status = ""
        if recipe["id"] == "fatekeeper":
            member = next(orig for orig, rel in entries if rel == "UEVRBackend.dll")
            verified = False
            if z.getinfo(member).file_size == FATEKEEPER_BACKEND_SIZE:
                with z.open(member) as backend:
                    verified = sha256(backend.read(FATEKEEPER_BACKEND_SIZE + 1)).hexdigest() == FATEKEEPER_BACKEND_SHA256
            backend_status = (
                "Fatekeeper backend matches the build confirmed in gameplay." if verified else
                "Fatekeeper needs the verified backend update before installation. "
                "The backend in this archive differs from the build confirmed in gameplay."
            )
        injector_hashes = {}
        if pins:
            for original, name in entries:
                if name == "UEVRBackend.dll":
                    injector_hashes[name] = FATEKEEPER_BACKEND_SHA256
                elif Path(name).suffix.lower() != ".pdb":
                    with z.open(original) as stream:
                        injector_hashes[name] = file_digest(stream, "sha256").hexdigest()
    snapshot = profile_safety._snapshot(dest)
    if recipe["id"] == "fatekeeper" and snapshot["files"].get("UEVRBackend.dll", {}).get(
            "sha256") == FATEKEEPER_BACKEND_SHA256:
        backend_status += " The installed backend already matches the tested build."
    profile = hub.review_profile_install(recipe, paths[1], steam_roots)
    if pins and profile.archive_sha256 != pins.get("profile"):
        raise RuntimeError("Choose Fatekeeper VR Profile v1.0.4. Its checksum did not match.")
    decisions = ()
    compatibility = ()
    if pins:
        with zipfile.ZipFile(paths[1]) as archive:
            profile_hashes = {}
            for entry, name in profile_safety._archive_entries(archive):
                with archive.open(entry) as stream:
                    profile_hashes[name] = file_digest(stream, "sha256").hexdigest()
        state = hub.state()
        compatibility = (managed_compatibility(state, dest, "Injector", injector_hashes) +
                         managed_compatibility(state, profile_dest, "Profile", profile_hashes))
        decisions = (_file_decisions("Injector", injector_hashes, snapshot) +
                     _file_decisions("Profile", profile_hashes, profile_safety._snapshot(profile_dest)))
    if profile.destination != str(profile_dest):
        raise RuntimeError("Profile destination changed during review.")
    if tuple(download_planner.archive_identity(p) for p in paths) != identities:
        raise RuntimeError("Archive changed during review; rescan.")
    # Release labels are informational only, and must match the bytes reviewed.
    tags = [(), ()]
    if evidence is not None:
        if not isinstance(evidence, (list, tuple)) or len(evidence) != 2:
            raise RuntimeError("Invalid archive scan evidence; rescan.")
        for i, (entry, sha) in enumerate(zip(evidence, (digest, profile.archive_sha256))):
            if not entry:
                continue
            if entry.get("file") != str(paths[i]) or entry.get("identity") != identities[i] or entry.get("sha256") != sha:
                raise RuntimeError("Archive scan evidence changed; rescan before review.")
            tags[i] = tuple(entry.get("tags", ()))
    needs_backend_verification = False
    if pins:
        backend_status = (
            "Verified Nightly 1133 and Fatekeeper profile v1.0.4. "
            "The reviewed installation includes the gameplay-tested joeyhodge "
            "UEVRBackend.dll automatically; download only the two ZIPs. "
            "The Hub checks the backend SHA-256 before any authorized installation. "
            "Debug symbols are omitted."
        )
        if snapshot["files"].get("UEVRBackend.dll", {}).get("sha256") == FATEKEEPER_BACKEND_SHA256:
            backend_status += " Installed backend already matches and will be preserved."
        else:
            backend_status += (
                " The backend is missing or different: the Hub will obtain the "
                "verified DLL for this reviewed transaction, with exact file "
                "decisions, backup and rollback. No manual DLL copying is needed."
            )
            needs_backend_verification = True
    blockers = list(profile.blocked) + list(compatibility)
    if snapshot["exists"] or recipe["id"] in hub.state():
        blockers.append("Existing injector directory or Hub record requires separate recovery review. No injector backup or replacement is authorized.")
    if recipe["id"] == "hogwarts-legacy" and not set(tags[0]).intersection(tags[1]):
        blockers.append("Matching Hogwarts Legacy injector/profile release is not established. Do not mix release bundles without compatibility review.")
    return DependencyReview(recipe["name"], str(paths[0]), digest, str(dest), rels,
                            size, len(snapshot["files"]), len(snapshot["dirs"]),
                            snapshot["bytes"], profile, tuple(tags), tuple(blockers), backend_status, needs_backend_verification, snapshot, decisions, compatibility_blockers=compatibility)


def build_blocked_plan(recipe, rows, steam_roots=None):
    """Show the normal pair review without parsing the failed archive."""
    from .pinned_release_review import build_uevr_hash_review

    failures = build_uevr_hash_review(recipe, rows)
    prefix = hub._pfx(recipe, steam_roots)
    injector = hub._uevr_dir(recipe, steam_roots)
    profile_dest = hub.profile_dir(recipe, steam_roots)
    for dest in (injector, profile_dest):
        profile_safety._safe_destination(dest, prefix)
    existing = profile_safety._snapshot(injector)
    profile_existing = profile_safety._snapshot(profile_dest)
    records = {row["id"]: row for row in rows}
    pins = recipe["archive_pins"]
    profile = profile_safety.ProfilePlan(
        recipe["id"], recipe["name"], records.get("profile", {}).get("file") or "Not supplied",
        pins["profile"], str(profile_dest), (), 0, 0,
        len(profile_existing["files"]), profile_existing["bytes"], len(profile_existing["dirs"]),
        profile_existing["exists"], ("Dependency verification failed.",), "",
    )
    blockers = tuple(
        f"Checksum failed for {path}. Required: {asset} ({version}). Approved source: {source}"
        for path, version, asset, source, _, _ in failures
    )
    return DependencyReview(
        recipe["name"], records.get("uevr", {}).get("file") or "Not supplied",
        pins["uevr"], str(injector), (), 0,
        len(existing["files"]), len(existing["dirs"]), existing["bytes"], profile,
        ((recipe["archive_releases"]["uevr"]["fixed_tag"],),
         (recipe["archive_releases"]["profile"]["fixed_tag"],)),
        blockers, verification_failed=True,
        failed_archives=tuple(path for path, *_ in failures),
    )
