# SPDX-License-Identifier: GPL-3.0-only
"""Target-bound preflight for the pinned Fatekeeper pair installer."""
from dataclasses import dataclass
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
    if (refreshed.profile.fingerprint != review.profile.fingerprint or
            refreshed.injector_snapshot != review.injector_snapshot):
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
    for name, data in payload.items():
        relative = Path(name)
        root = next((root for root in expected_roots if relative.is_relative_to(root)), None)
        if root is None:
            raise RuntimeError("Unexpected Fatekeeper payload path.")
        dest, snapshot = expected_roots[root]
        subpath = relative.relative_to(root)
        current = snapshot["files"].get(subpath.as_posix(), {})
        if current.get("sha256") != sha256(data).hexdigest():
            writes[str(dest / subpath)] = data
    if (profile_safety._snapshot(injector) != injector_before or
            profile_safety._snapshot(profile) != profile_before or hub._load_state() != state):
        raise RuntimeError("Fatekeeper files or Hub records changed during preparation.")
    return PreparedInstall(prefix, injector_before, profile_before, state, writes)
