# SPDX-License-Identifier: GPL-3.0-only
"""Process-local, single-use development permissions; never a release switch.

Only a private synthetic Steam tree under /tmp can be authorized. This is
an application safety guard, not a security boundary against same-UID code.
"""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
from threading import Lock
from time import monotonic
from uuid import uuid4

from . import hub, profile_safety, steam as steam_discovery
from .uevr_dependency_review import FATEKEEPER_BACKEND_SHA256

PINS = {'uevr': 'a230efac51be0f7eaec77e08add970a89a0513a490ec1a130bfaaa5725f302e3',
        'profile': 'a4abe6e99f9eb9c1822163431c6eb20933f2baa2cc9dc497ed067b8aa5da129b'}


@dataclass(frozen=True)
class Scope:
    root: Path
    steam: Path
    prefix: Path
    state: Path
    injector: Path
    profile: Path
    journal_dir: Path
    identity: tuple


def _directory(path, root):
    profile_safety._safe_destination(path, root)
    if path.resolve() != path or not path.is_dir():
        raise RuntimeError('Scoped directory missing or redirected.')
    info = path.stat()
    if info.st_uid != os.getuid():
        raise RuntimeError('Scoped directory has another owner.')
    return (str(path), info.st_dev, info.st_ino)


def resolve_scope(root):
    root = Path(root)
    if (root.parent != Path('/tmp').resolve() or root.resolve() != root or
            not root.name.startswith('nanners-e6-test-') or not root.is_dir() or
            stat.S_IMODE(root.stat().st_mode) != 0o700):
        raise RuntimeError('Authorization requires a private independent test root.')
    # A lexical /tmp path alone cannot distinguish a bind-mounted live tree.
    # Refuse all mountpoints at or below the private root in this namespace.
    with open('/proc/self/mountinfo', encoding='utf-8') as mounts:
        for line in mounts:
            mountpoint = Path(line.split()[4])
            if mountpoint == root or mountpoint.is_relative_to(root):
                raise RuntimeError('Mounted directory inside scoped test root.')
    steam = root / 'steam'
    prefix = steam / 'steamapps/compatdata/2186990/pfx'
    state = root / 'hub/state.json'
    journal_dir = state.parent / 'fatekeeper-recovery'
    recipe = hub.load_recipes()['fatekeeper']
    if recipe.get('steam_appid') != 2186990 or recipe.get('archive_pins') != PINS:
        raise RuntimeError('Scoped Fatekeeper dependency pins changed.')
    injector = prefix / 'drive_c/uevr'
    profile = prefix / 'drive_c/users/steamuser/AppData' / recipe['profile']['dir']
    game = steam / 'steamapps/common/Fatekeeper'
    anchors = (root, steam, game, prefix, prefix / 'drive_c', state.parent, journal_dir)
    identity = tuple(_directory(p, root) for p in anchors)
    for p in (injector, profile):
        profile_safety._safe_destination(p, root)
    if state.is_symlink() or (state.exists() and (not state.is_file() or state.stat().st_nlink != 1)):
        raise RuntimeError('Unsafe scoped Hub state.')
    for metadata in (steam / 'steamapps/libraryfolders.vdf',
                     steam / 'steamapps/appmanifest_2186990.acf'):
        if metadata.is_symlink() or not metadata.is_file() or metadata.stat().st_nlink != 1:
            raise RuntimeError('Unsafe scoped Steam metadata.')
    if (steam_discovery.steam_libraries([steam]) != [steam] or
            hub.game_path(recipe, [steam]) != game):
        raise RuntimeError('Scoped Steam library or game mismatch.')
    if hub.state_file() != state or hub._pfx(recipe, [steam]) != prefix:
        raise RuntimeError('Scoped Steam or Hub state resolver mismatch.')
    if hub._uevr_dir(recipe, [steam]) != injector or hub.profile_dir(recipe, [steam]) != profile:
        raise RuntimeError('Scoped dependency destination mismatch.')
    return Scope(root, steam, prefix, state, injector, profile, journal_dir, identity)


def review_digest(scope, review):
    if (review.profile.game_id != 'fatekeeper' or review.injector_sha256 != PINS['uevr'] or
            review.profile.archive_sha256 != PINS['profile'] or review.verification_failed or
            review.injector_destination != str(scope.injector) or
            review.profile.destination != str(scope.profile) or not review.file_decisions):
        raise RuntimeError('Review does not match scoped Fatekeeper dependency set.')
    return sha256(json.dumps({'review': asdict(review), 'backend': FATEKEEPER_BACKEND_SHA256},
                             sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@dataclass(frozen=True)
class _Permission:
    scope: Scope
    operation: str
    binding: str
    expires: float
    pid: int


_lock = Lock()
_permissions = {}
# Scoped development provenance is intentionally process-local, like tokens.
# Never infer authority from a journal or backup supplied by the filesystem.
# A restart requires manual review; this is not a same-UID security boundary.
_journal_provenance = {}


def _record_journal(scope, digest):
    """Called only by the authorized transaction writer after durable publish."""
    with _lock:
        _journal_provenance[scope.root] = (os.getpid(), scope, digest)


def _trusted_recovery_digest(scope):
    digest = recovery_digest(scope)
    with _lock:
        provenance = _journal_provenance.get(scope.root)
    if provenance != (os.getpid(), scope, digest):
        raise RuntimeError('Scoped recovery journal changed or lacks authorized transaction provenance; manual review required.')
    return digest


def _issue(scope, operation, binding, ttl):
    if not 0 < ttl <= 300:
        raise RuntimeError('Invalid scoped authorization lifetime.')
    token = uuid4().hex
    with _lock:
        now = monotonic()
        for key in list(_permissions):
            if _permissions[key].expires <= now:
                del _permissions[key]
        _permissions[token] = _Permission(scope, operation, binding, now + ttl, os.getpid())
    return token


def assert_fresh(scope):
    if (scope.injector.exists() or scope.profile.exists() or scope.state.exists() or
            any(scope.journal_dir.iterdir())):
        raise RuntimeError("Scoped first install requires a fresh dependency and state destination.")


def authorize_install(root, review, *, confirmed=False, ttl=120):
    if confirmed is not True:
        raise RuntimeError('Explicit scoped installation approval required.')
    scope = resolve_scope(root)
    assert_fresh(scope)
    return _issue(scope, 'install', review_digest(scope, review), ttl)


def consume(token, root, operation, binding):
    # Burn even on mismatch: a failed attempt cannot be replayed.
    with _lock:
        permission = _permissions.pop(token, None)
    if (permission is None or permission.pid != os.getpid() or
            permission.expires <= monotonic() or permission.operation != operation):
        raise RuntimeError('Missing, expired or consumed scoped authorization.')
    scope = resolve_scope(root)
    if callable(binding):
        binding = binding(scope)
    if permission.scope != scope or permission.binding != binding:
        raise RuntimeError('Scoped authorization destination or review changed.')
    return scope


def recovery_digest(scope):
    """Bind a recovery review to the exact, validated fresh-install journal.

    The transaction engine independently verifies backup and current bytes
    under its lock before any recovery mutation.
    """
    from . import fatekeeper_commit as tx
    destination = tx.Destination(scope.root, scope.prefix, scope.injector,
                                 scope.profile, scope.state, scope.journal_dir)
    raw, _ = tx._read(scope.journal_dir / 'fk4-journal.json')
    if raw is None:
        raise RuntimeError('No scoped recovery journal exists.')
    record = tx._parse_journal(destination, raw)
    if record['phase'] not in {'applying', 'committed', 'recovering'}:
        raise RuntimeError('Scoped transaction is not recoverable.')
    # This development route authorizes fresh installation only. Refuse
    # journals claiming replacement of any pre-existing dependency or state.
    if any(row['old'] is not None for row in record['rows']):
        raise RuntimeError('Scoped recovery requires a fresh-install journal.')
    backup = tx._backup_location(destination, record)
    incoming, _ = tx._read(backup / 'state-new')
    if tx._digest(incoming) != record['rows'][-1]['new']:
        raise RuntimeError('Scoped recovery incoming state evidence changed.')
    return tx._digest(raw)


def authorize_recovery(root, *, expected_journal, confirmed=False, ttl=120):
    if confirmed is not True:
        raise RuntimeError('Explicit scoped recovery approval required.')
    scope = resolve_scope(root)
    binding = _trusted_recovery_digest(scope)
    if binding != expected_journal:
        raise RuntimeError('Scoped recovery review changed.')
    return _issue(scope, 'recover', binding, ttl)
