# SPDX-License-Identifier: GPL-3.0-only
"""Rehearse the pinned Fatekeeper installation with the fixture-only transaction."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import urllib.request
import zipfile

from . import hub, offline_transaction as transaction, profile_safety, verified_download
from .uevr_dependency_review import (
    FATEKEEPER_BACKEND_SHA256, FATEKEEPER_BACKEND_SIZE, FATEKEEPER_BACKEND_URL,
    stage_fatekeeper_backend,
)


def fetch_verified_backend():
    page = FATEKEEPER_BACKEND_URL.replace("/download/", "/tag/").rsplit("/", 1)[0]
    kind, name = verified_download._verified_request(page, FATEKEEPER_BACKEND_URL)
    if name != "UEVRBackend.dll":
        raise RuntimeError("Unexpected Fatekeeper backend release asset.")
    opener = urllib.request.build_opener(verified_download._NoRedirect(),
                                         urllib.request.ProxyHandler({}))
    with verified_download._open_release(FATEKEEPER_BACKEND_URL, kind, opener=opener) as asset:
        data = asset.read(FATEKEEPER_BACKEND_SIZE + 1)
    if len(data) != FATEKEEPER_BACKEND_SIZE or transaction._sha(data) != FATEKEEPER_BACKEND_SHA256:
        raise RuntimeError("Fatekeeper backend verification failed.")
    return data


@contextmanager
def prepare(archives, installed, *, fetch_backend=fetch_verified_backend):
    """Prepare a disposable transaction from two pinned archives and the patched backend."""
    recipe = hub.load_recipes()["fatekeeper"]
    with TemporaryDirectory(prefix="nanners-fatekeeper-stage-", dir="/tmp") as temp:
        root = Path(temp)
        copies = []
        for source, role in zip(archives, ("uevr", "profile"), strict=True):
            target = root / (role + ".zip")
            if source.is_symlink() or not source.is_file() or source.stat().st_size > 64 * 1024 * 1024:
                raise RuntimeError("Choose a regular Fatekeeper release ZIP.")
            with source.open("rb") as stream:
                target.write_bytes(stream.read(64 * 1024 * 1024 + 1))
            if profile_safety._digest(target) != recipe["archive_pins"][role]:
                raise RuntimeError("Fatekeeper release archive failed SHA-256 verification.")
            copies.append(target)

        injector = root / "injector"
        injector.mkdir()
        with zipfile.ZipFile(copies[0]) as archive:
            hub._extract(archive, "UEVRInjector.exe", injector)
        backend_path = "drive_c/uevr/UEVRBackend.dll"
        existing_backend = installed.get(backend_path, b"")
        approved = transaction._sha(existing_backend) == FATEKEEPER_BACKEND_SHA256
        stage_fatekeeper_backend(injector, existing_backend if approved else fetch_backend())
        profile = root / "profile"
        with zipfile.ZipFile(copies[1]) as archive:
            names = tuple(sorted(name for _, name in profile_safety._archive_entries(archive)))
        profile_safety._stage_zip(copies[1], profile, names)

        payload = {}
        for directory, prefix in (
            (injector, "drive_c/uevr"),
            (profile, "drive_c/users/steamuser/AppData/" + recipe["profile"]["dir"]),
        ):
            for path in directory.rglob("*"):
                if path.is_file() and not (directory == injector and path.suffix.lower() == ".pdb"):
                    payload[f"{prefix}/{path.relative_to(directory).as_posix()}"] = path.read_bytes()
        staged = {name: data for name, data in payload.items() if installed.get(name) != data}
        with transaction.fixture_sandbox(installed, staged, uevr_payload=True) as fixture:
            yield fixture, transaction.build_plan(fixture), payload
