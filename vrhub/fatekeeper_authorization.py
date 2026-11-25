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
import re
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
    authority: Path
    authority_identity: tuple


def _directory(path, root):
    profile_safety._safe_destination(path, root)
    if path.resolve() != path or not path.is_dir():
        raise RuntimeError('Scoped directory missing or redirected.')
    info = path.stat()
    if info.st_uid != os.getuid():
        raise RuntimeError('Scoped directory has another owner.')
    return (str(path), info.st_dev, info.st_ino)


def persistent_scope_parent():
    """Fixed disk-backed development namespace; never use live Hub state."""
    return Path.home() / '.local/share/nannersvrhub-recovery-development'


def _private_parent(path):
    if (path.resolve() != path or not path.is_dir() or
            path.stat().st_uid != os.getuid() or
            stat.S_IMODE(path.stat().st_mode) != 0o700):
        raise RuntimeError('Unsafe persistent development storage.')
    return path


def resolve_scope(root):
    root = Path(root)
    persistent = root.parent == persistent_scope_parent()
    if persistent:
        _private_parent(root.parent)
    if ((root.parent != Path('/tmp').resolve() and not persistent) or root.resolve() != root or
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
    authority = (root.parent / 'authority' if persistent else
                 Path(os.environ.get('VRHUB_SCOPED_AUTHORITY_DIR', '')))
    if (((authority.parent != Path('/tmp').resolve() or
          not authority.name.startswith('nanners-e6-authority-')) if not persistent
         else authority != root.parent / 'authority') or
            authority.resolve() != authority or not authority.is_dir() or
            stat.S_IMODE(authority.stat().st_mode) != 0o700):
        raise RuntimeError('Independent private scoped authority directory required.')
    with open('/proc/self/mountinfo', encoding='utf-8') as mounts:
        for line in mounts:
            mountpoint = Path(line.split()[4])
            if mountpoint == authority or mountpoint.is_relative_to(authority):
                raise RuntimeError('Mounted scoped authority directory refused.')
    authority_identity = _directory(authority, authority)
    return Scope(root, steam, prefix, state, injector, profile, journal_dir,
                 identity, authority, authority_identity)


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
# The caller provisions a private authority directory independently of
# the disposable destination. This is an application trust boundary,
# not protection against arbitrary same-UID code editing both stores.
@dataclass(frozen=True)
class ProductionScope:
    root: Path
    prefix: Path
    state: Path
    injector: Path
    profile: Path
    journal_dir: Path
    identity: dict
    authority: Path
    authority_identity: tuple


def _production_authority_path(destination):
    """Validate the fixed store location even when it has not been created."""
    authority = Path.home() / '.local/share/nannersvrhub-transaction-authority'
    parent = authority.parent
    if (parent.resolve() != parent or not parent.is_dir()
            or parent.stat().st_uid != os.getuid()
            or authority.is_relative_to(destination.prefix)
            or authority.is_relative_to(destination.journal_dir)
            or destination.state.is_relative_to(authority)):
        raise RuntimeError('Unsafe production authority storage.')
    return authority


def validate_production_noop(destination):
    """Read-only provenance check, under the shared state transaction lock.

    Legacy verified installs may have no journal or ledger. Do not create
    either store merely to report that no dependency changes are required.
    Any unresolved evidence is a blocker, not an invitation to repair it.
    """
    from . import fatekeeper_commit as tx
    # Keep the pending-journal diagnostic even for unadopted legacy journals.
    profile_safety._safe_destination(destination.journal_dir, destination.root)
    raw, _ = tx._read(destination.journal_dir / 'fk4-journal.json')
    if raw is not None:
        parsed = tx._parse_journal(destination, raw)
        if parsed['phase'] not in {'committed', 'rolled-back'}:
            raise RuntimeError('Recover the existing Fatekeeper transaction before retrying.')
    authority = _production_authority_path(destination)
    if authority.exists() or authority.is_symlink():
        _private_parent(authority)
    ledger = authority / (sha256(str(destination.state).encode()).hexdigest() + '.json')
    # A dangling link must not be interpreted as absence.
    has_ledger = ledger.exists() or ledger.is_symlink()
    if raw is None:
        if has_ledger:
            # Validate existing provenance without provisioning missing stores.
            scope = production_authority(destination)
            production_journal(scope)
            raise RuntimeError('Missing authorized production journal or unfinished staging; manual review required.')
        if destination.journal_dir.exists():
            _directory(destination.journal_dir, destination.root)
            if stat.S_IMODE(destination.journal_dir.stat().st_mode) != 0o700:
                raise RuntimeError('Unsafe production recovery storage.')
            for entry in destination.journal_dir.iterdir():
                info = entry.lstat()
                if (entry.name != 'fk4.lock' or not stat.S_ISREG(info.st_mode)
                        or info.st_uid != os.getuid() or info.st_nlink != 1):
                    raise RuntimeError('Unresolved production recovery evidence; manual review required.')
        return
    scope = production_authority(destination)
    production_journal(scope)
    record = _ledger(scope)
    if record is None or record['staging'] or record['next'] is not None:
        raise RuntimeError('Pending production journal transition; manual review required.')


def production_authority(destination, *, provision=False):
    """Use a fixed private store independent of the journal and prefix.

    Called only inside the gated production path and its state lock.
    """
    from . import fatekeeper_commit as tx
    if not tx.live_install_authorized():
        raise RuntimeError('Explicit live Fatekeeper authorization is required.')
    authority = _production_authority_path(destination)
    parent = authority.parent
    if provision and not authority.exists() and not authority.is_symlink():
        authority.mkdir(mode=0o700)
        tx._sync(parent)
    _private_parent(authority)
    for path in (destination.prefix, destination.state.parent, destination.journal_dir):
        _directory(path, destination.root)
    if stat.S_IMODE(destination.journal_dir.stat().st_mode) != 0o700:
        raise RuntimeError('Unsafe production recovery storage.')
    for path in (destination.state, destination.journal_dir / 'fk4-journal.json'):
        if path.is_symlink() or (path.exists() and
                (not path.is_file() or path.stat().st_uid != os.getuid()
                 or path.stat().st_nlink != 1)):
            raise RuntimeError('Unsafe production transaction evidence.')
    return ProductionScope(destination.root, destination.prefix, destination.state,
                           destination.injector, destination.profile, destination.journal_dir,
                           tx._identity(destination), authority, _directory(authority, authority))


def _assert_scope(scope):
    if isinstance(scope, ProductionScope):
        from . import fatekeeper_commit as tx
        destination = tx.Destination(scope.root, scope.prefix, scope.injector,
                                     scope.profile, scope.state, scope.journal_dir)
        current = production_authority(destination)
    else:
        current = resolve_scope(scope.root)
    if current != scope:
        raise RuntimeError('Scoped authority identity changed.')


def production_journal(scope):
    """Validate existing provenance before a new install or any recovery."""
    from . import fatekeeper_commit as tx
    raw, _ = tx._read(scope.journal_dir / 'fk4-journal.json')
    record = _ledger(scope)
    digest = tx._digest(raw)
    if raw is None:
        if record is not None and not (record['staging'] and record['current'] is None):
            raise RuntimeError('Missing authorized production journal; manual review required.')
        return None, None
    if record is None or digest not in (record['current'], record['next']):
        raise RuntimeError('Production journal lacks authorized transaction provenance; manual review required.')
    destination = tx.Destination(scope.root, scope.prefix, scope.injector,
                                 scope.profile, scope.state, scope.journal_dir)
    parsed = tx._parse_journal(destination, raw)
    if record['next'] is not None and digest == record['current']:
        terminal = dict(parsed, phase='rolled-back')
        if tx._digest(json.dumps(terminal).encode()) == record['next']:
            raise RuntimeError('Pending terminal production journal transition; manual review required.')
    return digest, parsed


def begin_production_staging(scope):
    digest, previous = production_journal(scope)
    if previous is not None and previous['phase'] not in {'committed', 'rolled-back'}:
        raise RuntimeError('Recover the existing Fatekeeper transaction before retrying.')
    record = _ledger(scope)
    if digest is not None:
        # Do not discard an unresolved transition from a prior operation.
        if record['next'] is not None:
            if digest != record['next']:
                raise RuntimeError('Pending production journal transition; manual review required.')
            _save_ledger(scope, digest, None)
        return
    for entry in scope.journal_dir.iterdir():
        info = entry.lstat()
        safe = False
        if entry.name == 'fk4.lock':
            safe = stat.S_ISREG(info.st_mode) and info.st_nlink == 1
        elif record is not None and record['staging'] and re.fullmatch(
                r'fk4-backup(?:-[0-9a-f]{32})?', entry.name):
            safe = stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700
            if safe:
                for child in entry.iterdir():
                    meta = child.lstat()
                    if (not re.fullmatch(r'(?:[0-9]+|state-new|\.(?:[0-9]+|state-new)-[a-zA-Z0-9_]+)', child.name)
                            or not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid()
                            or meta.st_nlink != 1 or stat.S_IMODE(meta.st_mode) != 0o600):
                        safe = False
                        break
        if not safe or info.st_uid != os.getuid():
            raise RuntimeError('Unsafe production staging evidence; manual review required.')
    _save_ledger(scope, None, None, staging=True)


def _ledger_path(scope):
    key = str(scope.state) if isinstance(scope, ProductionScope) else str(scope.root)
    return scope.authority / (sha256(key.encode()).hexdigest() + '.json')


def _scope_binding(scope):
    return json.loads(json.dumps(asdict(scope), default=str))


def _ledger(scope):
    path = _ledger_path(scope)
    _assert_scope(scope)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RuntimeError('Unsafe scoped provenance evidence.') from exc
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600 or
                info.st_size > 65536):
            raise RuntimeError('Unsafe scoped provenance evidence.')
        try:
            def unique_pairs(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError('duplicate authority field')
                    result[key] = value
                return result
            record = json.loads(stream.read(65537), object_pairs_hook=unique_pairs)
        except (ValueError, UnicodeError) as exc:
            raise RuntimeError('Corrupted scoped provenance evidence.') from exc
    if (not isinstance(record, dict) or
            set(record) != {'schema', 'scope', 'current', 'next', 'staging'} or
            record['schema'] != 1 or record['scope'] != _scope_binding(scope) or
            any(value is not None and (not isinstance(value, str) or
                not re.fullmatch('[0-9a-f]{64}', value))
                for value in (record['current'], record['next'])) or
            not isinstance(record['staging'], bool) or
            (record['current'] is None and record['next'] is None and not record['staging']) or
            (record['staging'] and record['current'] is not None)):
        raise RuntimeError('Invalid scoped provenance evidence; manual review required.')
    return record


def _save_ledger(scope, current, next_digest, *, staging=False):
    from . import fatekeeper_commit as tx
    _assert_scope(scope)
    tx._write(_ledger_path(scope), json.dumps({
        'schema': 1, 'scope': _scope_binding(scope),
        'current': current, 'next': next_digest, 'staging': staging,
    }, sort_keys=True).encode())


def _record_journal(scope, stage, previous, digest):
    """Write intent before journal, finalize afterward, under transaction lock."""
    record = _ledger(scope)
    if stage == 'before':
        if record is None:
            if previous is not None:
                raise RuntimeError('Missing authorized transaction provenance.')
        elif ((previous is None and not record['staging']) or
              (previous is not None and previous not in (record['current'], record['next']))):
            raise RuntimeError('Scoped recovery journal changed or lacks provenance.')
        _save_ledger(scope, previous, digest, staging=previous is None)
    elif stage == 'after':
        if record is None or record['current'] != previous or record['next'] != digest:
            raise RuntimeError('Scoped provenance transition changed.')
        _save_ledger(scope, digest, None)
    else:
        raise RuntimeError('Invalid provenance transition.')


def _trusted_recovery_digest(scope):
    digest = recovery_digest(scope)
    record = _ledger(scope)
    if record is None or digest not in (record['current'], record['next']):
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
    if scope.injector.exists() or scope.profile.exists() or scope.state.exists():
        raise RuntimeError("Scoped first install requires a fresh dependency and state destination.")
    record = _ledger(scope)
    entries = tuple(scope.journal_dir.iterdir())
    if record is None and not entries:
        return
    if (record is None or not record['staging'] or record['current'] is not None or
            (scope.journal_dir / 'fk4-journal.json').exists()):
        raise RuntimeError("Scoped first install requires a fresh dependency and state destination.")
    # The trusted writer marked staging before creating any backup. No
    # published journal means no payload write could have started. Preserve
    # all abandoned backup evidence; use a new backup name for every retry.
    for entry in entries:
        info = entry.lstat()
        if entry.name == 'fk4.lock':
            safe = stat.S_ISREG(info.st_mode) and info.st_nlink == 1
        elif re.fullmatch(r'fk4-backup(?:-[0-9a-f]{32})?', entry.name):
            safe = stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700
            if safe:
                for child in entry.iterdir():
                    meta = child.lstat()
                    if (not re.fullmatch(r'(?:state-new|\.state-new-[a-zA-Z0-9_]+)', child.name)
                            or not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid()
                            or meta.st_nlink != 1 or stat.S_IMODE(meta.st_mode) != 0o600):
                        safe = False
                        break
        else:
            safe = False
        if not safe or info.st_uid != os.getuid():
            raise RuntimeError("Unsafe fresh staging evidence; manual review required.")


def begin_staging(scope):
    """Call only after explicit install approval, under the state lock."""
    assert_fresh(scope)
    _save_ledger(scope, None, None, staging=True)


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
