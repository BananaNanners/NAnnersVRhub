# SPDX-License-Identifier: GPL-3.0-only
"""Read-only verification of the Fatekeeper backend proven in gameplay.

The backend is a standalone DLL. It must not become a third ZIP archive
requirement or an independently authorized write to the working Proton prefix.
"""
import errno
from hashlib import sha256
import os
from pathlib import Path
import stat



def install_update_guidance(result):
    """Player-facing Fatekeeper setup guidance; checking never installs anything."""
    status = result.get("status")
    if status == "verified":
        return (
            "UEVRBackend.dll: Verified pinned build installed. The Hub will preserve "
            "this DLL during the reviewed two-ZIP installation; no separate download."
        )
    if status == "not_installed":
        return (
            "UEVRBackend.dll: Missing. After the two ZIPs are verified, the Hub can "
            "automatically obtain and SHA-256-verify the tested joeyhodge DLL and "
            "install it in Fatekeeper's Proton prefix during an approved, backed-up "
            "installation. No manual DLL copying or third ZIP is needed."
        )
    if "Cannot locate the Fatekeeper Proton prefix" in result.get("detail", ""):
        return (
            "UEVRBackend.dll: Not yet checked — Fatekeeper's Proton prefix is "
            "unavailable. Launch Fatekeeper once from Steam to create the prefix, "
            "then scan the two ZIP archives and review installation."
        )
    return (
        "UEVRBackend.dll: Needs review. The installed backend is not verified as "
        "the gameplay-tested build. Review exact replacements and backup coverage "
        "before approving a change; it will not be silently overwritten."
    )


def check_backend(recipe, *, steam_roots=None):
    """Report pinned-build identity from the actual installed DLL, not Hub timestamps."""
    if recipe.get("id") != "fatekeeper":
        raise ValueError("Pinned Fatekeeper backend verification is game-specific.")

    # Lazy imports avoid the hub -> updates -> status -> hub import cycle.
    from . import hub
    from .uevr_dependency_review import FATEKEEPER_BACKEND_SHA256, FATEKEEPER_BACKEND_SIZE

    try:
        injector = hub._uevr_dir(recipe, steam_roots)
    except (OSError, RuntimeError, ValueError) as exc:
        return {"status": "unknown",
                "detail": f"Cannot locate the Fatekeeper Proton prefix: {exc}. No backend was changed."}

    target = Path(injector) / "UEVRBackend.dll"
    if Path(injector).is_symlink():
        return {"status": "unknown",
                "detail": "The injector folder is a symlink; backend identity needs manual review."}

    fd = None
    try:
        fd = os.open(target, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            return {"status": "unknown",
                    "detail": "UEVRBackend.dll is not a regular file. Do not replace it automatically."}
        if metadata.st_size != FATEKEEPER_BACKEND_SIZE:
            return {"status": "unknown",
                    "detail": "Installed UEVRBackend.dll differs in size from the tested joeyhodge build. "
                              "Review compatibility; no automatic replacement is authorized."}
        digest = sha256()
        while chunk := os.read(fd, 1024 * 1024):
            digest.update(chunk)
        if digest.hexdigest() != FATEKEEPER_BACKEND_SHA256:
            return {"status": "unknown",
                    "detail": "Installed UEVRBackend.dll does not match the tested joeyhodge SHA-256. "
                              "Review compatibility; do not overwrite this file automatically."}
        return {"status": "verified",
                "detail": "Installed UEVRBackend.dll matches the exact size and SHA-256 of the "
                          "joeyhodge build confirmed during Fatekeeper Quest 3 gameplay. "
                          "This verifies local bytes, not Hub ownership or a newer upstream release."}
    except FileNotFoundError:
        return {"status": "not_installed",
                "detail": "UEVRBackend.dll is missing from Fatekeeper's injector folder. "
                          "The verified build is required for this configuration; installation remains gated."}
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            detail = "UEVRBackend.dll is a symlink; its target will not be followed."
        else:
            detail = "UEVRBackend.dll could not be read safely."
        return {"status": "unknown", "detail": detail + " Manual review required; no files changed."}
    finally:
        if fd is not None:
            os.close(fd)
