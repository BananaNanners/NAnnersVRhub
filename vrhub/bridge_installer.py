#!/usr/bin/env python3
"""NAnners KHARVOX Bridge installer. MIT; unchanged engine has its own licenses."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request

VERSION = '0.2.0'
ENGINE_VERSION = '0.1.6'
PAYLOAD_SHA256 = '7b51d0199a8780937165a023a12c293f5e8f0b95c1196eccacb0ea536a9521ba'
BASE_NAME = 'proton-cachyos-11.0-20260703-slr-x86_64'
BASE_URL = ('https://github.com/CachyOS/proton-cachyos/releases/download/'
            'cachyos-11.0-20260703-slr/' + BASE_NAME + '.tar.xz')
BASE_SIZE = 335059640
BASE_SHA256 = '62ff4b2750180723cc00538608fe687e21d1d91a31ef64ce1a7c9f46c3db310b'
MAX_EXPANDED = 4 * 1024**3
MAX_ENTRIES = 100000


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def load_engine(payload):
    payload = Path(payload)
    manifest = payload / 'payload-sha256.json'
    if payload.is_symlink() or manifest.is_symlink() or digest(manifest) != PAYLOAD_SHA256:
        raise ValueError('Missing or changed bridge payload inventory. Extract the complete package again.')
    for name, expected in json.loads(manifest.read_text()).items():
        p = payload / name
        if p.is_symlink() or not p.resolve().is_relative_to(payload.resolve()) or digest(p) != expected:
            raise ValueError('Missing or changed bridge payload: ' + name)
    spec = importlib.util.spec_from_file_location('_nanners_bridge_engine', payload / 'lab.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def default_state():
    return Path.home() / '.local/share/nanners-kharvox-lab/0.1.0'


def safe_directory(path):
    if path.is_symlink():
        raise ValueError('A linked bridge state/cache directory is not supported: ' + str(path))
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


@contextmanager
def locked(state):
    safe_directory(state)
    fd = os.open(state / '.bridge.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Another bridge action is running. Finish it first.') from exc
        yield
    finally:
        os.close(fd)


def check_archive(path):
    if path.is_symlink() or path.stat().st_size != BASE_SIZE or digest(path) != BASE_SHA256:
        raise ValueError('The base-runner archive does not match the pinned upstream release.')


def allowed_url(url):
    parsed = urllib.parse.urlsplit(url)
    return (parsed.scheme == 'https' and parsed.port in (None, 443) and
            parsed.hostname in {'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'})


class ReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise ValueError('Unexpected base-runner download redirect.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_archive(cache):
    safe_directory(cache)
    target = cache / (BASE_NAME + '.tar.xz')
    if target.exists() or target.is_symlink():
        check_archive(target)
        print('Verified cached upstream base runner.', flush=True)
        return target
    fd, temporary = tempfile.mkstemp(prefix='base-download-', dir=cache)
    try:
        print(f'Downloading pinned base runner: {BASE_SIZE / 1024**2:.1f} MiB', flush=True)
        opener = urllib.request.build_opener(ReleaseRedirect())
        request = urllib.request.Request(BASE_URL, headers={'User-Agent': 'NAnners-KHARVOX-Bridge/' + VERSION})
        with os.fdopen(fd, 'wb') as out, opener.open(request, timeout=40) as response:
            if not allowed_url(response.geturl()):
                raise ValueError('Unexpected base-runner download destination.')
            length = response.headers.get('Content-Length')
            if length is not None and int(length) != BASE_SIZE:
                raise ValueError('Unexpected base-runner download size.')
            received, next_report = 0, 32 * 1024**2
            while block := response.read(1024**2):
                received += len(block)
                if received > BASE_SIZE:
                    raise ValueError('Base-runner download exceeded the expected size.')
                out.write(block)
                if received >= next_report:
                    print(f'Downloaded {received / 1024**2:.0f} / {BASE_SIZE / 1024**2:.0f} MiB', flush=True)
                    next_report += 32 * 1024**2
            out.flush()
            os.fsync(out.fileno())
        check_archive(Path(temporary))
        os.replace(temporary, target)
        print('Upstream archive SHA-256 verified.', flush=True)
        return target
    finally:
        Path(temporary).unlink(missing_ok=True)


def extract_base(archive, destination):
    """Validate all paths/types/links and bounds before extracting official files."""
    check_archive(archive)
    with tarfile.open(archive, 'r:xz') as tar:
        members = tar.getmembers()
        if len(members) > MAX_ENTRIES:
            raise ValueError('Base-runner archive contains too many entries.')
        total, seen = 0, set()
        for member in members:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or '..' in path.parts or not path.parts or
                    path.parts[0] != BASE_NAME or member.name in seen or
                    not (member.isfile() or member.isdir() or member.issym() or member.islnk())):
                raise ValueError('Unsafe base-runner archive entry: ' + member.name)
            seen.add(member.name)
            if member.issym() or member.islnk():
                link = PurePosixPath(member.linkname)
                target = posixpath.normpath(str(path.parent / link) if member.issym() else str(link))
                if link.is_absolute() or target.split('/')[0] != BASE_NAME:
                    raise ValueError('External base-runner archive link: ' + member.name)
            total += member.size
            if total > MAX_EXPANDED:
                raise ValueError('Base-runner archive expands beyond its limit.')
        if shutil.disk_usage(destination).free < total * 2 + 256 * 1024**2:
            raise ValueError('Not enough free space to extract and copy the isolated runner.')
        tar.extractall(destination, members=members, filter='data')
    return destination / BASE_NAME


def mark_owned(engine, state, source):
    engine.atomic_json(state / 'bridge-install.json', {
        'schema_version': 1, 'bridge_version': VERSION, 'engine_version': ENGINE_VERSION,
        'runner': str((state / 'runner').absolute()), 'source': source,
        'base_archive_sha256': BASE_SHA256,
    })


def install(engine, state, base=None, archive=None):
    expected = engine.read_json(engine.HERE / 'base-files.json')
    if (state / 'runner').is_symlink():
        raise ValueError('Linked runner rejected; no files changed.')
    if (state / 'runner').exists():
        try:
            runner = engine.verify_runner(state, expected)
        except (OSError, ValueError, KeyError):
            pass  # Only the engine may upgrade a recognized earlier clone.
        else:
            mark_owned(engine, state, 'reused verified isolated runner')
            print('Existing isolated runner verified and reused: ' + str(runner), flush=True)
            return runner
    if base is not None:
        try:
            engine.verify_base(base, expected)
        except (OSError, ValueError):
            print('Local base does not match; obtaining the pinned upstream release.', flush=True)
        else:
            runner = engine.prepare(base, state, expected)
            mark_owned(engine, state, 'matching local base')
            return runner
    archive = Path(archive) if archive else download_archive(state / 'downloads')
    check_archive(archive)
    with tempfile.TemporaryDirectory(prefix='bridge-base-', dir=state.parent) as temporary:
        base = extract_base(archive, Path(temporary))
        engine.verify_base(base, expected)
        runner = engine.prepare(base, state, expected)
    mark_owned(engine, state, BASE_URL)
    print('Installation complete. Connect WiVRn and run the full bridge test.', flush=True)
    return runner


def uninstall(engine, state, confirm=False):
    if not confirm:
        raise ValueError('Use --confirm-remove-runner to remove only this isolated runner. Logs and game prefixes are preserved.')
    runner = state / 'runner'
    owner_path = state / 'bridge-install.json'
    if owner_path.is_symlink() or runner.is_symlink():
        raise ValueError('Linked runner/ownership record rejected; no files removed.')
    owner = engine.read_json(owner_path)
    if (owner.get('schema_version') != 1 or owner.get('engine_version') != ENGINE_VERSION or
            owner.get('runner') != str(runner.absolute())):
        raise ValueError('This runner has no matching bridge ownership record; no files removed.')
    engine.verify_runner(state, engine.read_json(engine.HERE / 'base-files.json'))
    if engine.runner_busy(runner):
        raise ValueError('Close DOOM, KHARVOX and bridge tests before uninstalling.')
    shutil.rmtree(runner)
    for name in ('bridge-install.json', 'runner.json', 'probe-pass.json'):
        (state / name).unlink(missing_ok=True)
    print('Isolated runner removed. Game files, saves, Heroic settings, logs and cached download were preserved.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'status', 'probe', 'launch', 'uninstall'])
    parser.add_argument('--payload', type=Path, default=Path(__file__).resolve().parent / 'payload')
    parser.add_argument('--state', type=Path, default=default_state())
    parser.add_argument('--base', type=Path, help='Optional matching local base; otherwise download the pinned release')
    parser.add_argument('--archive', type=Path, help='Offline upstream archive; exact size and hash required')
    parser.add_argument('--kharvox', type=Path, default=Path.home() / 'Games/Heroic/KHARVOX-v1.4')
    parser.add_argument('--game', type=Path, default=Path.home() / 'Games/Heroic/DOOM (2016)')
    parser.add_argument('--confirm-remove-runner', action='store_true')
    args = parser.parse_args(argv)
    try:
        engine = load_engine(args.payload)
        state = args.state.expanduser().absolute()
        if state.is_symlink():
            raise ValueError('Linked bridge state is not supported.')
        if args.action == 'status':
            runner = engine.verify_runner(state, engine.read_json(engine.HERE / 'base-files.json'))
            print('Verified isolated runner: ' + str(runner) + '\nThis does not verify current gameplay.')
            return 0
        with locked(state):
            if args.action == 'install':
                base = args.base or Path.home() / '.config/heroic/tools/proton/Proton-CachyOS-latest'
                install(engine, state, base.expanduser(), args.archive)
            elif args.action == 'uninstall':
                uninstall(engine, state, args.confirm_remove_runner)
            else:
                runner = engine.verify_runner(state, engine.read_json(engine.HERE / 'base-files.json'))
                if args.action == 'probe':
                    engine.probe(state, runner, False, args.kharvox.expanduser().resolve())
                else:
                    engine.launch_doom(state, runner, args.kharvox.expanduser().resolve(),
                                       args.game.expanduser().resolve(), engine.heroic_config())
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, tarfile.TarError) as exc:
        print('STOP: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
