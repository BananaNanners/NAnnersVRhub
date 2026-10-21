"""Install the separately versioned bridge without enlarging Hub updates."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import importlib.util
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tarfile
import tempfile
import urllib.request

if __package__:
    from . import bridge_installer as installer
else:  # Hub launches this trusted installed module with Python -I.
    spec = importlib.util.spec_from_file_location('_bridge_installer', Path(__file__).with_name('bridge_installer.py'))
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)

VERSION = '0.2.0'
ROOT = 'NAnners-KHARVOX-Bridge-0.2.0'
ARCHIVE_NAME = ROOT + '-source.tar.gz'
URL = 'https://github.com/BananaNanners/NAnners-KHARVOX-Bridge/releases/download/v0.2.0/' + ARCHIVE_NAME
ARCHIVE_SIZE = 39406366
ARCHIVE_SHA256 = '26dcdbef5588336954676ce2c3023f8b17c11f0263f334610d124f4a514927d0'
MAX_EXPANDED = 128 * 1024**2
MAX_ENTRIES = 1000


def component_root(state):
    return Path(state) / 'components' / ROOT


def payload_dir(state):
    return component_root(state) / 'payload'


def verified_payload(state):
    target = component_root(state)
    if target.is_symlink() or (target.parent.exists() and target.parent.is_symlink()):
        raise ValueError('Linked bridge component directory rejected.')
    path = payload_dir(state)
    if not path.is_dir():
        raise ValueError('The DOOM bridge component is not installed. Use Install VR runner or Import bridge package.')
    installer.load_engine(path)
    return path


@contextmanager
def component_lock(state):
    installer.safe_directory(state)
    fd = os.open(state / '.bridge-component.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('A bridge component installation is already running.') from exc
        yield
    finally:
        os.close(fd)


def check_archive(path):
    if path.is_symlink() or path.stat().st_size != ARCHIVE_SIZE or installer.digest(path) != ARCHIVE_SHA256:
        raise ValueError('Bridge archive does not match the pinned 0.2.0 release. The installed component was not changed.')


def download(state):
    cache = installer.safe_directory(state / 'downloads')
    target = cache / ARCHIVE_NAME
    if target.exists() or target.is_symlink():
        check_archive(target)
        return target
    fd, temporary = tempfile.mkstemp(prefix='bridge-download-', dir=cache)
    try:
        print(f'Downloading bridge {VERSION}: {ARCHIVE_SIZE / 1024**2:.1f} MiB', flush=True)
        request = urllib.request.Request(URL, headers={'User-Agent': 'NAnnersVRhub-bridge/' + VERSION})
        opener = urllib.request.build_opener(installer.ReleaseRedirect())
        with os.fdopen(fd, 'wb') as out, opener.open(request, timeout=40) as response:
            if not installer.allowed_url(response.geturl()):
                raise ValueError('Unexpected bridge download destination.')
            length = response.headers.get('Content-Length')
            if length is not None and int(length) != ARCHIVE_SIZE:
                raise ValueError('Unexpected bridge download size.')
            count = 0
            while block := response.read(1024**2):
                count += len(block)
                if count > ARCHIVE_SIZE:
                    raise ValueError('Bridge download exceeded its expected size.')
                out.write(block)
            out.flush()
            os.fsync(out.fileno())
        check_archive(Path(temporary))
        os.replace(temporary, target)
        print('Bridge archive SHA-256 verified.', flush=True)
        return target
    finally:
        Path(temporary).unlink(missing_ok=True)


def extract(archive, staging):
    check_archive(archive)
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        if len(members) > MAX_ENTRIES:
            raise ValueError('Too many bridge archive entries.')
        names, total = set(), 0
        for member in members:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != ROOT or
                    member.name in names or not (member.isfile() or member.isdir())):
                raise ValueError('Unsafe bridge archive entry: ' + member.name)
            names.add(member.name)
            total += member.size
            if total > MAX_EXPANDED:
                raise ValueError('Bridge archive exceeds its extraction limit.')
        if shutil.disk_usage(staging).free < total + 64 * 1024**2:
            raise ValueError('Not enough space for the bridge component.')
        tar.extractall(staging, members=members, filter='data')
    return staging / ROOT


def ensure_payload(state, archive=None):
    state = Path(state).expanduser().absolute()
    with component_lock(state):
        target = component_root(state)
        if target.exists() or target.is_symlink():
            result = verified_payload(state)
            print('Verified bridge component reused.', flush=True)
            return result
        parent = installer.safe_directory(target.parent)
        archive = Path(archive).expanduser() if archive else download(state)
        check_archive(archive)
        with tempfile.TemporaryDirectory(prefix='bridge-component-', dir=parent) as temporary:
            root = extract(archive, Path(temporary))
            installer.load_engine(root / 'payload')
            os.rename(root, target)
        print('Bridge component installed; existing runner and test history preserved.', flush=True)
        return payload_dir(state)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['fetch', 'install', 'probe', 'launch', 'uninstall'])
    parser.add_argument('--state', type=Path, default=installer.default_state())
    parser.add_argument('--bridge-archive', type=Path, help='Import the exact companion bridge source archive offline')
    args, remaining = parser.parse_known_args(argv)
    try:
        state = args.state.expanduser().absolute()
        if args.action in {'fetch', 'install'}:
            payload = ensure_payload(state, args.bridge_archive)
        else:
            if args.bridge_archive:
                raise ValueError('Import a bridge archive using install or fetch first.')
            payload = verified_payload(state)
        if args.action == 'fetch':
            return 0
        return installer.main([args.action, '--payload', str(payload), '--state', str(state), *remaining])
    except (OSError, ValueError, tarfile.TarError) as exc:
        print('STOP: ' + str(exc) + '\nNo Hub/game files were replaced. Import the matching bridge package if the release is not yet available online.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
