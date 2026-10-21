"""Public stable Hub releases, bounded downloads and managed upgrades.

This module never imports downloaded code. Only an explicit install calls the
existing installer, whose dependency probes execute the verified application.
GitHub HTTPS/checksums establish transport integrity, not independent signatures.
"""
import fcntl
import hashlib
import http.client
import json
import os
import re
import shutil
import stat
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from . import __version__, hub, self_install

REPO = "BananaNanners/NAnnersVRhub"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES = f"https://github.com/{REPO}/releases"
MAX_ARCHIVE = 32 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
MAX_FILE = 8 * 1024 * 1024  # Full bridge sources are a separate, pinned component.
MAX_ENTRIES = 2000
CHECK_INTERVAL = 24 * 60 * 60
VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-(dev|rc)([1-9]\d*))?\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
HOSTS = {"github.com", "api.github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}


class UpdateError(RuntimeError):
    pass


class Cancelled(UpdateError):
    pass


def version_key(value):
    match = VERSION.fullmatch(value)
    if not match:
        raise UpdateError(f"Unsupported application version: {value}")
    major, minor, patch, stage, number = match.groups()
    return int(major), int(minor), int(patch), {"dev": 0, "rc": 1, None: 2}[stage], int(number or 0)


def newer(release, current=__version__):
    return version_key(release["version"]) > version_key(current)


def _url(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.fragment):
        raise UpdateError("The update server returned an unexpected download address.")
    return url


class _Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, _url(newurl))


def _open(url):
    request = urllib.request.Request(_url(url), headers={"User-Agent": f"NAnnersVRhub/{__version__}",
                                                       "Accept": "application/vnd.github+json" if url == API else "application/octet-stream"})
    try:
        return urllib.request.build_opener(_Redirect()).open(request, timeout=8)
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429):
            raise UpdateError("GitHub limited update requests. Try again later; the installed Hub is unchanged.") from exc
        raise UpdateError(f"GitHub returned HTTP {exc.code}. Try again later.") from exc
    except (OSError, urllib.error.URLError) as exc:
        raise UpdateError("Could not reach GitHub securely. Check your connection and try again.") from exc


def _cancel(event):
    if event is not None and event.is_set():
        raise Cancelled("Download/check cancelled. The installed Hub is unchanged.")


def _read(url, limit, *, size=None, output=None, cancel=None, progress=None):
    _cancel(cancel)
    start, count = time.monotonic(), 0
    chunks = []
    try:
        with _open(url) as response:
            # Redirects are also validated by the opener before making a request.
            _url(response.geturl())
            if response.status != 200:
                raise UpdateError(f"Unexpected update response: HTTP {response.status}")
            length = response.headers.get("Content-Length")
            if length is not None and (int(length) > limit or (size is not None and int(length) != size)):
                raise UpdateError("Download size does not match the release metadata.")
            while True:
                _cancel(cancel)
                if time.monotonic() - start > 120:
                    raise UpdateError("Download timed out. Try again later.")
                data = response.read(min(65536, limit - count + 1))
                if not data:
                    break
                count += len(data)
                if count > limit or (size is not None and count > size):
                    raise UpdateError("The download exceeded its allowed size.")
                if output is not None:
                    output.write(data)
                else:
                    chunks.append(data)
                if progress:
                    progress(count, size or 0)
    except (OSError, urllib.error.URLError, http.client.HTTPException, ValueError) as exc:
        raise UpdateError("The download was interrupted or returned an invalid response. Try again.") from exc
    _cancel(cancel)
    if size is not None and count != size:
        raise UpdateError("The download is incomplete; its size does not match the release.")
    return b"".join(chunks)


def parse_release(data):
    """Accept exactly the project's custom source ZIP and checksum asset."""
    try:
        tag = data["tag_name"]
        version = tag.removeprefix("v")
        if tag != "v" + version or not VERSION.fullmatch(version) or "-" in version:
            raise ValueError("stable tag")
        if data["draft"] is not False or data["prerelease"] is not False or type(data["id"]) is not int or data["id"] <= 0:
            raise ValueError("stable release")
        page = f"{RELEASES}/tag/{tag}"
        if data["html_url"] != page:
            raise ValueError("repository")
        published = datetime.fromisoformat(data["published_at"].replace("Z", "+00:00"))
        if published.tzinfo is None:
            raise ValueError("timestamp")
        result = {"version": version, "id": data["id"], "html_url": page,
                  "published_at": data["published_at"], "body": str(data.get("body") or "")[:20000]}
        for key, name, limit in (("archive", f"NAnnersVRhub-{version}-source.zip", MAX_ARCHIVE),
                                 ("checksums", "SHA256SUMS", 16384)):
            matches = [asset for asset in data["assets"] if asset.get("name") == name]
            if len(matches) != 1:
                raise ValueError(f"missing or duplicate {name}")
            asset = matches[0]
            url = f"https://github.com/{REPO}/releases/download/{tag}/{name}"
            if (asset["browser_download_url"] != url or asset["state"] != "uploaded"
                    or type(asset["size"]) is not int or not 0 < asset["size"] <= limit):
                raise ValueError("asset metadata")
            digest = asset.get("digest")
            if digest is not None and (not isinstance(digest, str) or not digest.startswith("sha256:") or not SHA.fullmatch(digest[7:])):
                raise ValueError("asset digest")
            result[key] = {"name": name, "url": url, "size": asset["size"], "sha256": digest[7:] if digest else None}
        return result
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise UpdateError("The GitHub release is incomplete or has unexpected metadata. No update was installed.") from exc


def settings_path():
    return hub.state_file().parent / "hub-updates.json"


def read_settings():
    path = settings_path()
    if not path.exists() and not path.is_symlink():
        return {"schema": 1, "check_on_startup": True, "auto_download": False}
    try:
        if path.is_symlink():
            raise ValueError("symlink")
        data = json.loads(path.read_text())
        if (data.get("schema") != 1 or type(data.get("check_on_startup")) is not bool
                or type(data.get("auto_download")) is not bool):
            raise ValueError("settings")
        return data
    except (OSError, ValueError, AttributeError) as exc:
        raise UpdateError(f"Update preferences could not be read; the existing file was preserved: {path}") from exc


def save_settings(**changes):
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path.with_suffix(".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = {**read_settings(), **changes}
        self_install._atomic(path, (json.dumps(data, indent=2) + "\n").encode())
    return data


def check(*, force=False, cancel=None):
    settings = read_settings()
    now = datetime.now(timezone.utc)
    if not force and settings.get("release") and settings.get("checked_at"):
        try:
            age = (now - datetime.fromisoformat(settings["checked_at"])).total_seconds()
            if 0 <= age < CHECK_INTERVAL:
                return {"release": parse_release(settings["release"]), "checked_at": settings["checked_at"], "cached": True}
        except (ValueError, TypeError, UpdateError):
            pass
    if not force and settings.get("attempted_at"):
        try:
            age = (now - datetime.fromisoformat(settings["attempted_at"])).total_seconds()
            if 0 <= age < CHECK_INTERVAL:
                raise UpdateError("An automatic check was already attempted today. Choose Check now to retry.")
        except (ValueError, TypeError):
            pass
    _cancel(cancel)
    save_settings(attempted_at=now.isoformat())
    try:
        data = json.loads(_read(API, 1024 * 1024, cancel=cancel))
    except (ValueError, UnicodeError) as exc:
        raise UpdateError("GitHub returned an unreadable release response.") from exc
    release = parse_release(data)
    stamp = now.isoformat()
    save_settings(release=data, checked_at=stamp)
    return {"release": release, "checked_at": stamp, "cached": False}


def cache_root():
    value = os.environ.get("XDG_CACHE_HOME", "")
    base = Path(value) if value and Path(value).is_absolute() else Path.home() / ".cache"
    return base / "nannersvrhub/updates"


def _digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _checksum(data, name):
    try:
        matches = []
        for line in data.decode("ascii").splitlines():
            match = re.fullmatch(r"([a-fA-F0-9]{64}) [ *](.+)", line)
            if match and match[2] == name:
                matches.append(match[1].lower())
        if len(matches) != 1:
            raise ValueError("checksum entry")
        return matches[0]
    except (ValueError, UnicodeError) as exc:
        raise UpdateError("SHA256SUMS does not contain exactly one valid entry for the source ZIP.") from exc


def _members(archive, version):
    expected = f"NAnnersVRhub-{version}"
    result, seen, total = [], set(), 0
    for item in archive.infolist():
        parts = PurePosixPath(item.filename).parts
        mode = item.external_attr >> 16
        name = item.filename.rstrip("/")
        if (not parts or parts[0] != expected or item.orig_filename != item.filename or "\\" in name or ":" in name or name.startswith("/")
                or any(p in ("", ".", "..") for p in name.split("/")) or name in seen
                or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))
                or (stat.S_IFMT(mode) == stat.S_IFDIR and not item.is_dir())
                or item.flag_bits & 1 or item.file_size > MAX_FILE):
            raise UpdateError("The source ZIP contains an unsafe, duplicate or unsupported path.")
        if len(parts) == 1 and not item.is_dir():
            raise UpdateError("The source ZIP has an invalid root folder.")
        seen.add(name)
        total += item.file_size
        result.append(item)
        if len(result) > MAX_ENTRIES or total > MAX_EXPANDED:
            raise UpdateError("The source ZIP exceeds the extraction limits.")
    if not result:
        raise UpdateError("The source ZIP is empty.")
    return result


def verify_bundle(directory):
    """Recheck archive/checksums and every extracted byte before any execution."""
    directory = Path(directory)
    try:
        if directory.is_symlink() or directory.parent.resolve() != cache_root().resolve():
            raise UpdateError("The cached update is outside the Hub update folder.")
        if (directory / "ready.json").is_symlink():
            raise UpdateError("The cached update record must not be a symlink.")
        manifest = json.loads((directory / "ready.json").read_text())
        release = parse_release(manifest["release"])
        archive = directory / release["archive"]["name"]
        sums = directory / "SHA256SUMS"
        for path, asset in ((archive, release["archive"]), (sums, release["checksums"])):
            if path.is_symlink() or not path.is_file() or path.stat().st_size != asset["size"]:
                raise UpdateError("A downloaded update file changed. Download the update again.")
            if asset["sha256"] and _digest(path) != asset["sha256"]:
                raise UpdateError("A GitHub asset digest does not match. Download the update again.")
        if _digest(archive) != _checksum(sums.read_bytes(), archive.name):
            raise UpdateError("The source ZIP checksum does not match. No update was installed.")
        source = directory / "source" / f"NAnnersVRhub-{release['version']}"
        if (directory / "source").is_symlink() or source.is_symlink():
            raise UpdateError("The extracted update folder changed.")
        with zipfile.ZipFile(archive) as z:
            members = _members(z, release["version"])
            expected = set()
            for member in members:
                path = directory / "source" / member.filename
                if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != directory.parent):
                    raise UpdateError("The extracted update contains a symlink.")
                if member.is_dir():
                    if not path.is_dir():
                        raise UpdateError("An extracted update directory changed.")
                else:
                    expected.add(member.filename)
                    if not path.is_file() or path.stat().st_size != member.file_size or path.read_bytes() != z.read(member):
                        raise UpdateError("An extracted update file changed. Download the update again.")
            actual = {str(p.relative_to(directory / "source")) for p in (directory / "source").rglob("*") if not p.is_dir() or p.is_symlink()}
            if actual != expected:
                raise UpdateError("The extracted update contains unexpected files.")
        version, _ = self_install._source_files(source)
        if version != release["version"]:
            raise UpdateError("The source ZIP version does not match its release tag.")
        return {"directory": str(directory), "source": str(source), "release": release}
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, SyntaxError) as exc:
        raise UpdateError("The cached update is incomplete or invalid. Download it again.") from exc


def download(release, *, cancel=None, progress=None):
    # Only release objects revalidated from GitHub metadata are accepted.
    metadata = read_settings().get("release")
    if not metadata or parse_release(metadata) != release:
        raise UpdateError("Check GitHub for updates before downloading this release.")
    root = cache_root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink():
        raise UpdateError("The update cache must not be a symlink.")
    directory = Path(tempfile.mkdtemp(prefix=f"{release['version']}-", dir=root))
    try:
        for key in ("checksums", "archive"):
            asset = release[key]
            path = directory / asset["name"]
            with path.open("xb") as out:
                path.chmod(0o600)
                _read(asset["url"], MAX_ARCHIVE if key == "archive" else 16384, size=asset["size"],
                      output=out, cancel=cancel, progress=progress if key == "archive" else None)
            if asset["sha256"] and _digest(path) != asset["sha256"]:
                raise UpdateError("The downloaded asset does not match its GitHub SHA-256 digest.")
        archive = directory / release["archive"]["name"]
        if _digest(archive) != _checksum((directory / "SHA256SUMS").read_bytes(), archive.name):
            raise UpdateError("The source ZIP checksum does not match. The download was discarded.")
        with zipfile.ZipFile(archive) as z:
            members = _members(z, release["version"])
            for member in members:
                _cancel(cancel)
                path = directory / "source" / member.filename
                if member.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(member) as src, path.open("xb") as out:
                        shutil.copyfileobj(src, out, 65536)
                    path.chmod(0o600)
        self_install._atomic(directory / "ready.json", json.dumps({"release": metadata}).encode())
        result = verify_bundle(directory)
        _cancel(cancel)
        save_settings(download=directory.name)
        return result
    except BaseException:
        shutil.rmtree(directory)
        raise


def saved_download():
    name = read_settings().get("download")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        return None
    return verify_bundle(cache_root() / name)


def managed_context():
    root_value = os.environ.get("_NANNERSVRHUB_ROOT")
    if not root_value:
        raise UpdateError("Install this Hub with install.py, then open its application-menu entry to enable in-app installation.")
    root = Path(root_value).absolute()
    if root.is_symlink() or (root / ".owner").read_text() != self_install.OWNER:
        raise UpdateError("The managed application folder could not be verified.")
    record = self_install._read_record(root)
    if not record or (root / "releases" / record["current"]).resolve() != Path(__file__).resolve().parent.parent:
        raise UpdateError("This running Hub is no longer the active installed version. Restart it before updating.")
    self_install._release(root, record["current"])
    return root, record["current"]


def install_bundle(directory):
    bundle = verify_bundle(directory)
    if not newer(bundle["release"]):
        raise UpdateError("Only a newer stable version can be installed here. Use the rollback manager for older versions.")
    root, current = managed_context()
    return self_install.install(Path(bundle["source"]), root, expected_current=current)


def restart_command():
    # Called after installation; the old process intentionally pins its old code.
    root = Path(os.environ.get("_NANNERSVRHUB_ROOT", ""))
    record = self_install._read_record(root)
    if not record:
        raise UpdateError("No managed Hub launcher is available.")
    self_install._release(root, record["current"])
    return [str(root / "bin/nannersvrhub")]
