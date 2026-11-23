# SPDX-License-Identifier: GPL-3.0-only
"""Rehearse the pinned Fatekeeper installation with the fixture-only transaction."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import json
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
def prepare(archives, installed, *, fetch_backend=fetch_verified_backend, hub_records=None):
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
        with transaction.fixture_sandbox(
            installed, staged, uevr_payload=True, state=hub_records,
        ) as fixture:
            if hub_records is not None:
                payload["hub/state.json"] = _stage_hub_records(fixture, recipe, payload)
            yield fixture, transaction.build_plan(fixture), payload


def _stage_hub_records(fixture, recipe, payload):
    """Use the actual Hub serializer against explicit disposable state paths."""
    before = fixture.root / "installed/hub/state.json"
    after = fixture.root / "incoming/hub/state.json"
    original = hub._load_state(path=before)
    updated = dict(original)
    for key, folder, component in (
        ("fatekeeper", "drive_c/uevr", "uevr"),
        ("fatekeeper:profile", "drive_c/users/steamuser/AppData/" + recipe["profile"]["dir"], "profile"),
    ):
        # Preserve prior recovery metadata in the verified state backup.
        root = fixture.root / "installed" / folder
        updated[key] = {
            "installer": "fatekeeper-pair-preview",
            "root": str(root),
            "files": sorted(str(fixture.root / "installed" / name)
                            for name in payload if name.startswith(folder + "/")),
            "archive_sha256": recipe["archive_pins"][component],
        }
    updated["fatekeeper"]["backend_sha256"] = FATEKEEPER_BACKEND_SHA256
    hub._save_state(updated, path=after)
    return after.read_bytes()


def rehearse_install(archives, verified_backend):
    """Run the real staged payload and record rollback in an isolated fixture."""
    records = {"other-game": {"files": ["untouched"]}}
    with prepare(archives, {}, fetch_backend=lambda: verified_backend, hub_records=records) as (
        fixture, plan, payload
    ):
        transaction.execute(fixture, plan)
        for name, data in payload.items():
            if transaction._read(fixture, "installed", name) != data:
                raise RuntimeError("Installed fixture did not match the reviewed payload.")
        transaction.rollback(fixture)
        restored = transaction._read(fixture, "installed", "hub/state.json")
        if json.loads(restored) != records or transaction._inventory(fixture) != plan.before:
            raise RuntimeError("Fixture rollback did not restore the original Hub records.")
