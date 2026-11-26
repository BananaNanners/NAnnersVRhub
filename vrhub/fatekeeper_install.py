# SPDX-License-Identifier: GPL-3.0-only
"""Target-bound preflight for the pinned Fatekeeper pair installer."""
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from . import fatekeeper_rehearsal, hub, profile_safety
from . import uevr_dependency_review
from .uevr_dependency_review import FATEKEEPER_BACKEND_SIZE, FATEKEEPER_BACKEND_SHA256


@dataclass(frozen=True)
class PreparedInstall:
    prefix: Path
    injector: dict
    profile: dict
    state: dict
    writes: dict[str, bytes]
    dependencies: dict = field(default_factory=dict)
    archive_pins: dict = field(default_factory=dict)


def prepare_reviewed_install(review, steam_roots=None, *, verified_backend=None):
    """Build the exact write set using Hub-resolved paths without modifying them."""
    recipe = hub.load_recipes()["fatekeeper"]
    prefix = hub._pfx(recipe, steam_roots)
    injector = hub._uevr_dir(recipe, steam_roots)
    profile = hub.profile_dir(recipe, steam_roots)
    if str(injector) != review.injector_destination or str(profile) != review.profile.destination:
        raise RuntimeError("Fatekeeper installation paths changed. Reopen the review.")
    profile_safety._safe_destination(injector, prefix)
    profile_safety._safe_destination(profile, prefix)
    if injector.is_relative_to(profile) or profile.is_relative_to(injector):
        raise RuntimeError("Fatekeeper destinations overlap.")
    archives = (Path(review.injector_archive), Path(review.profile.archive))
    refreshed = uevr_dependency_review.build_plan(recipe, archives, steam_roots)
    if refreshed.compatibility_blockers or review.compatibility_blockers:
        raise RuntimeError("Fatekeeper compatibility review required: " +
                           "; ".join(refreshed.compatibility_blockers or review.compatibility_blockers))
    if (refreshed.profile.fingerprint != review.profile.fingerprint or
            refreshed.injector_snapshot != review.injector_snapshot or
            refreshed.file_decisions != review.file_decisions):
        raise RuntimeError("Fatekeeper installation changed. Reopen the review.")
    injector_before = profile_safety._snapshot(injector)
    profile_before = profile_safety._snapshot(profile)
    state = hub._load_state()
    if injector_before != refreshed.injector_snapshot or (
            profile_safety.build_plan(recipe, archives[1], steam_roots).fingerprint != review.profile.fingerprint):
        raise RuntimeError("Fatekeeper installation changed during preparation.")
    if (review.injector_sha256 != recipe["archive_pins"]["uevr"] or
            review.profile.archive_sha256 != recipe["archive_pins"]["profile"]):
        raise RuntimeError("Fatekeeper review does not match the pinned dependency set.")
    backend = b""
    existing = injector_before["files"].get("UEVRBackend.dll", {})
    if existing.get("sha256") == FATEKEEPER_BACKEND_SHA256 and existing["size"] == FATEKEEPER_BACKEND_SIZE:
        with (injector / "UEVRBackend.dll").open("rb") as stream:
            backend = stream.read(FATEKEEPER_BACKEND_SIZE + 1)
    args = {} if verified_backend is None else {"fetch_backend": lambda: verified_backend}
    payload = fatekeeper_rehearsal.build_payload(archives, backend, **args)
    expected_roots = {
        Path("drive_c/uevr"): (injector, injector_before),
        Path("drive_c/users/steamuser/AppData") / recipe["profile"]["dir"]: (profile, profile_before),
    }
    writes = {}
    dependencies = {}
    for name, data in payload.items():
        relative = Path(name)
        root = next((root for root in expected_roots if relative.is_relative_to(root)), None)
        if root is None:
            raise RuntimeError("Unexpected Fatekeeper payload path.")
        dest, snapshot = expected_roots[root]
        subpath = relative.relative_to(root)
        current = snapshot["files"].get(subpath.as_posix(), {})
        component = "Injector" if dest == injector else "Profile"
        action = uevr_dependency_review.fatekeeper_file_decision(
            component, subpath.as_posix(), current.get("sha256"), sha256(data).hexdigest())
        if (action, component, subpath.as_posix()) not in refreshed.file_decisions:
            raise RuntimeError("Staged Fatekeeper payload differs from the reviewed decisions.")
        dependencies[str(dest / subpath)] = {"sha256": sha256(data).hexdigest(),
                                            "size": len(data),
                                            "customizable": component == "Profile" and
                                            subpath.as_posix() in uevr_dependency_review.FATEKEEPER_LOCAL_PROFILE_FILES}
        if action != "Preserve":
            writes[str(dest / subpath)] = data
    for folder, component in ((injector, "Injector"), (profile, "Profile")):
        incoming = {Path(name).relative_to(folder).as_posix()
                    for name in dependencies if Path(name).is_relative_to(folder)}
        blockers = uevr_dependency_review.managed_compatibility(state, folder, component, incoming)
        if blockers:
            raise RuntimeError("Fatekeeper compatibility review required: " + "; ".join(blockers))
    if len(writes) != sum(action != "Preserve" for action, _, _ in refreshed.file_decisions):
        raise RuntimeError("Staged Fatekeeper write set is incomplete.")
    if (profile_safety._snapshot(injector) != injector_before or
            profile_safety._snapshot(profile) != profile_before or hub._load_state() != state):
        raise RuntimeError("Fatekeeper files or Hub records changed during preparation.")
    return PreparedInstall(prefix, injector_before, profile_before, state, writes, dependencies, dict(recipe["archive_pins"]))
