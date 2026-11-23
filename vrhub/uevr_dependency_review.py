# SPDX-License-Identifier: GPL-3.0-only
"""Read-only UEVR dependency review and offline Fatekeeper backend staging."""
from dataclasses import dataclass
from hashlib import sha256
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
    digest = profile_safety._digest(paths[0])
    pins = recipe.get("archive_pins", {})
    if pins and digest != pins.get("uevr"):
        raise RuntimeError("Choose the official UEVR Nightly 1133 uevr.zip. Its checksum did not match.")
    snapshot = profile_safety._snapshot(dest)
    if recipe["id"] == "fatekeeper" and snapshot["files"].get("UEVRBackend.dll", {}).get(
            "sha256") == FATEKEEPER_BACKEND_SHA256:
        backend_status += " The installed backend already matches the tested build."
    profile = hub.review_profile_install(recipe, paths[1], steam_roots)
    if pins and profile.archive_sha256 != pins.get("profile"):
        raise RuntimeError("Choose Fatekeeper VR Profile v1.0.4. Its checksum did not match.")
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
    if pins:
        backend_status = (
            "Verified Nightly 1133 and Fatekeeper profile v1.0.4. "
            "Installation requires the verified joeyhodge backend. Debug symbols are omitted."
        )
        if snapshot["files"].get("UEVRBackend.dll", {}).get("sha256") == FATEKEEPER_BACKEND_SHA256:
            backend_status += " The installed backend already matches."
    blockers = list(profile.blocked)
    if snapshot["exists"] or recipe["id"] in hub.state():
        blockers.append("Existing injector directory or Hub record requires separate recovery review. No injector backup or replacement is authorized.")
    if recipe["id"] == "hogwarts-legacy" and not set(tags[0]).intersection(tags[1]):
        blockers.append("Matching Hogwarts Legacy injector/profile release is not established. Do not mix release bundles without compatibility review.")
    return DependencyReview(recipe["name"], str(paths[0]), digest, str(dest), rels,
                            size, len(snapshot["files"]), len(snapshot["dirs"]),
                            snapshot["bytes"], profile, tuple(tags), tuple(blockers), backend_status)
