# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Dev5B2: explicitly approved, digest-pinned HTTPS download to archive library.

No install actions; no cookies, Nexus API bypass or automatic download URLs.
The user must supply a direct release-asset URL and confirm the destination.
Network access is restricted to the package's recorded upstream provider and
its known release CDN. Staging and rename never overwrite an existing archive.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import download_planner

SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")
GITHUB_TAG = re.compile(r"/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/releases/tag/([^/]+)/?\Z")
GITHUB_ASSET = re.compile(r"/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/releases/download/([^/]+)/([^/]+)/?\Z")
THUNDER_PAGE = re.compile(
    r"/c/[^/]+/p/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/v/([A-Za-z0-9_.-]+)/?\Z")
THUNDER_ASSET = re.compile(
    r"/package/download/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?\Z")
VALID_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+() -]{0,179}\Z")
KNOWN_ARCHIVES = (".zip", ".7z", ".rar", ".tar.gz")
GITHUB_CDNS = frozenset({
    "release-assets.githubusercontent.com",
    "objects.githubusercontent.com",
    "github-releases.githubusercontent.com",
})
THUNDER_CDNS = frozenset({
    "gcdn.thunderstore.io",
    "cdn.thunderstore.io",
})
REDIRECTS = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 5
MAX_BYTES = 3 * 1024 * 1024 * 1024
BLOCK_BYTES = 256 * 1024


class DownloadRejected(ValueError):
    """Invalid authorization, URL, source, destination or checksum."""


class DownloadCancelled(Exception):
    """The user requested cancellation. Partial staging is removed."""


@dataclass(frozen=True)
class DownloadAuthorization:
    game_id: str
    component_id: str
    label: str
    origin_page: str
    direct_url: str
    destination_folder: Path
    expected_sha256: str
    destination_name: str


@dataclass(frozen=True)
class DownloadResult:
    file: Path
    sha256: str
    size: int
    reused_existing: bool


def _url(value: str):
    if not isinstance(value, str) or not (0 < len(value) <= 4096):
        raise DownloadRejected("An explicit HTTPS URL is required.")
    try:
        p = urllib.parse.urlsplit(value)
        port = p.port
    except ValueError as exc:
        raise DownloadRejected("Invalid download URL.") from exc
    if (p.scheme != "https" or p.hostname is None or port not in (None, 443)
            or p.username is not None or p.password is not None
            or p.fragment or any(ord(c) < 32 for c in value)):
        raise DownloadRejected("Only normal HTTPS URLs without credentials or custom ports are permitted.")
    host = p.hostname.lower().rstrip(".")
    if not re.fullmatch(r"[a-z0-9.-]+", host) or ".." in host:
        raise DownloadRejected("Invalid download server.")
    return p, host


def _source_identity(page: str):
    p, host = _url(page)
    if host == "github.com":
        m = GITHUB_TAG.fullmatch(p.path)
        if m is None:
            raise DownloadRejected("GitHub source must be a recipe-pinned release tag.")
        return "github", tuple(m.groups())
    if host == "thunderstore.io":
        m = THUNDER_PAGE.fullmatch(p.path)
        if m is None:
            raise DownloadRejected("Thunderstore source must be a recipe-pinned package version.")
        return "thunderstore", tuple(m.groups())
    raise DownloadRejected(
        "This package requires browser/manual download. No verified direct-download source is configured.")


def _verified_request(page: str, direct: str):
    kind, identity = _source_identity(page)
    p, host = _url(direct)
    if kind == "github":
        m = GITHUB_ASSET.fullmatch(p.path)
        if host != "github.com" or not m or tuple(m.groups()[:3]) != identity:
            raise DownloadRejected(
                "Choose a direct release asset from the SAME GitHub repository and pinned tag.")
        return kind, urllib.parse.unquote(m.group(4))
    m = THUNDER_ASSET.fullmatch(p.path)
    if host != "thunderstore.io" or not m or tuple(m.groups()) != identity:
        raise DownloadRejected(
            "Choose the exact pinned Thunderstore package/version download URL.")
    return kind, f"{identity[1]}-{identity[2]}.zip"


def _filename(name: str) -> str:
    if (not VALID_FILENAME.fullmatch(name) or name in {".", ".."}
            or "/" in name or chr(92) in name
            or not name.casefold().endswith(KNOWN_ARCHIVES)):
        raise DownloadRejected("Release asset filename must be a normal archive name.")
    return name


def create_authorization(recipe: dict, component: dict,
                         direct_url: str, folder: Path) -> DownloadAuthorization:
    """Preflight permission without making a network request."""
    rid = download_planner._rid(recipe)
    candidates = download_planner.plan_components(recipe)
    matched = [
        c for c in candidates
        if c["id"] == component.get("id") and c["name"] == component.get("name")
    ]
    if len(matched) != 1:
        raise DownloadRejected("The selected component is not in this game's current recipe.")
    canonical = matched[0]
    digest = canonical.get("sha256")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise DownloadRejected(
            "This component has no recipe-pinned SHA-256 hash. Use Open source and download manually.")
    origin = canonical.get("url", "")
    kind, name = _verified_request(origin, direct_url.strip())
    name = _filename(name)
    folder = download_planner._checked_directory(str(folder), must_exist=True)
    if folder.is_symlink() or not folder.is_dir():
        raise DownloadRejected("The selected archive folder must be an existing ordinary directory.")
    target = folder.resolve() / name
    if target.parent != folder.resolve():
        raise DownloadRejected("The proposed archive destination is outside the selected folder.")
    return DownloadAuthorization(
        rid, canonical["id"], canonical["name"], origin, direct_url.strip(),
        folder.resolve(), digest.lower(), name)


def source_support(recipe: dict, component: dict) -> tuple[bool, str]:
    """A pinned file may be downloaded; Nexus and unpinned UEVR stay manual."""
    try:
        rid = download_planner._rid(recipe)
        candidates = download_planner.plan_components(recipe)
        selected = next(c for c in candidates
                        if c["id"] == component.get("id")
                        and c["name"] == component.get("name"))
        if not SHA256.fullmatch(selected.get("sha256") or ""):
            return False, "No pinned SHA-256 digest; use the manual source link."
        _source_identity(selected.get("url", ""))
        return True, "Eligible for a user-confirmed, SHA-256 verified direct download."
    except (StopIteration, DownloadRejected, ValueError):
        return False, "This source requires browser/manual download."


def _redirect_allowed(kind: str, value: str):
    p, host = _url(value)
    if kind == "github" and host in GITHUB_CDNS:
        return
    if kind == "thunderstore" and host in THUNDER_CDNS:
        return
    raise DownloadRejected("Upstream redirected outside its approved release CDN. Download refused.")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        return None


def _open_release(url, kind, *, opener):
    """Reject all redirects except pinned provider -> known release CDN."""
    current = url
    for hop in range(MAX_REDIRECTS + 1):
        try:
            req = urllib.request.Request(
                current,
                headers={"Accept": "application/octet-stream",
                         "User-Agent": "NAnnersVRhub/0.5.5 (user-confirmed archive download)"})
            response = opener.open(req, timeout=15)
            if getattr(response, "status", 200) != 200:
                response.close()
                raise DownloadRejected("Upstream did not return HTTP 200.")
            return response
        except urllib.error.HTTPError as exc:
            if exc.code not in REDIRECTS:
                if exc.code in (401, 403):
                    raise DownloadRejected(
                        "Upstream authorization required; use the official browser/manual download.") from None
                raise DownloadRejected(f"Upstream refused the download (HTTP {exc.code}).") from None
            if hop == MAX_REDIRECTS:
                raise DownloadRejected("Too many release-asset redirects.") from None
            redirect = exc.headers.get("Location", "")
            if not redirect:
                raise DownloadRejected("Upstream redirect omitted its destination.") from None
            next_url = urllib.parse.urljoin(current, redirect)
            _redirect_allowed(kind, next_url)
            current = next_url
            exc.close()
    raise DownloadRejected("Download exceeded redirect limit.")


def _hash_existing(path: Path, expected: str) -> tuple[bool, int]:
    try:
        st = path.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_BYTES:
            return False, st.st_size
        h = hashlib.sha256()
        with path.open("rb") as inp:
            for chunk in iter(lambda: inp.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest() == expected, st.st_size
    except OSError as exc:
        raise DownloadRejected(f"Cannot safely check existing file: {exc}") from exc


def _reuse_any_pinned_archive(folder: Path, final: Path, expected: str):
    """Avoid duplicate transfers when the pinned archive was renamed locally.

    Bounded, read-only inventory; a filename match is never sufficient.
    """
    try:
        existing, _warning = download_planner._inventory(folder)
    except OSError:
        return None
    budget = MAX_BYTES
    for file in existing:
        if file.path == final or file.size > budget:
            continue
        budget -= file.size
        try:
            matching, size = _hash_existing(file.path, expected)
        except DownloadRejected:
            continue  # archive could have changed during the read-only scan
        if matching:
            return DownloadResult(file.path, expected, size, True)
    return None


def download(authority: DownloadAuthorization, *,
             cancel_event: threading.Event | None = None,
             progress=None, opener_factory=None) -> DownloadResult:
    """Fetch only after explicit UI authorization, verify digest, atomically keep.

    A failed/aborted download removes its own .part file, never an existing
    destination. A matching existing destination is reused without networking.
    """
    cancelled = cancel_event or threading.Event()
    kind, _ = _verified_request(authority.origin_page, authority.direct_url)
    if not SHA256.fullmatch(authority.expected_sha256):
        raise DownloadRejected("Invalid pinned digest.")
    folder = authority.destination_folder
    if not folder.is_dir() or folder.is_symlink():
        raise DownloadRejected("Archive directory is missing or unsafe.")
    name = _filename(authority.destination_name)
    final = folder / name
    if cancelled.is_set():
        raise DownloadCancelled("Download cancelled before starting.")
    if final.exists() or final.is_symlink():
        ok, size = _hash_existing(final, authority.expected_sha256)
        if ok:
            return DownloadResult(final, authority.expected_sha256, size, True)
        raise DownloadRejected(
            "A different archive already occupies this filename. It was NOT overwritten.")
    reused = _reuse_any_pinned_archive(folder, final, authority.expected_sha256)
    if reused is not None:
        return reused
    opener = opener_factory() if opener_factory else urllib.request.build_opener(
        _NoRedirect(), urllib.request.ProxyHandler({}))
    temp_path = None
    response = None
    try:
        response = _open_release(authority.direct_url, kind, opener=opener)
        # Do not trust Content-Length for correctness; stream with a hard cap.
        header = response.headers.get("Content-Length", "")
        try:
            total = int(header) if header else 0
        except (ValueError, TypeError):
            total = 0
        if total > MAX_BYTES:
            raise DownloadRejected("Remote archive exceeds the 3 GiB safety limit.")
        fd, tmp_name = tempfile.mkstemp(prefix=".nannersvrhub-", suffix=".part", dir=folder)
        temp_path = Path(tmp_name)
        os.fchmod(fd, 0o600)
        digest = hashlib.sha256()
        size = 0
        with os.fdopen(fd, "wb") as out:
            while True:
                if cancelled.is_set():
                    raise DownloadCancelled("Download cancelled; partial file discarded.")
                chunk = response.read(BLOCK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    raise DownloadRejected("Remote archive exceeded the safety limit.")
                out.write(chunk)
                digest.update(chunk)
                if progress:
                    progress(size, total)
            out.flush()
            os.fsync(out.fileno())
        if cancelled.is_set():
            raise DownloadCancelled("Download cancelled; partial file discarded.")
        actual = digest.hexdigest()
        if actual != authority.expected_sha256:
            raise DownloadRejected(
                "Downloaded SHA-256 did not match the pinned recipe hash. Partial data discarded.")
        if final.exists() or final.is_symlink():
            ok, existing_size = _hash_existing(final, authority.expected_sha256)
            if ok:
                return DownloadResult(final, authority.expected_sha256, existing_size, True)
            raise DownloadRejected("Destination appeared during download; existing file preserved.")
        # Hard link uses O_EXCL-like non-overwrite semantics. It cannot replace
        # an existing archive, even if another process creates it after the check.
        try:
            os.link(temp_path, final)
        except FileExistsError:
            ok, existing_size = _hash_existing(final, authority.expected_sha256)
            if ok:
                return DownloadResult(final, authority.expected_sha256, existing_size, True)
            raise DownloadRejected("Destination already exists; original archive preserved.")
        return DownloadResult(final, authority.expected_sha256, size, False)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DownloadRejected(f"Network transfer failed; no file installed: {exc}") from exc
    finally:
        if response is not None:
            response.close()
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
