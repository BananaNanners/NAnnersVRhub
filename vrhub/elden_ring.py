"""Read-only Elden Ring evidence and a fail-closed Steam command adapter.

No game executable is renamed, anti-cheat file changed, or game binary loaded.
The command adapter preserves Steam's selected Proton/prefix and changes only
the validated game-executable argument. Offline settings remain user-reviewed.
"""
import configparser
import os
from pathlib import Path
import struct
import sys

SUPPORTED = {"2.6.2.0", "2.7.1.0"}


def file_version(path):
    """Read PE RT_VERSION / VS_FIXEDFILEINFO with bounded resource traversal."""
    try:
        with Path(path).open('rb') as f:
            size = os.fstat(f.fileno()).st_size
            def read(offset, length):
                if offset < 0 or length < 0 or offset + length > size or length > 8 * 1024 * 1024:
                    raise ValueError('Invalid PE range')
                f.seek(offset)
                data = f.read(length)
                if len(data) != length:
                    raise ValueError('Truncated PE')
                return data
            dos = read(0, 64)
            if dos[:2] != b'MZ':
                return None
            pe = struct.unpack_from('<I', dos, 60)[0]
            header = read(pe, 24)
            if header[:4] != b'PE\0\0':
                return None
            machine, count = struct.unpack_from('<HH', header, 4)
            optional_size = struct.unpack_from('<H', header, 20)[0]
            if machine != 0x8664 or not 1 <= count <= 96 or not 136 <= optional_size <= 4096:
                return None
            optional = read(pe + 24, optional_size)
            if struct.unpack_from('<H', optional)[0] != 0x20b:
                return None
            rva, length = struct.unpack_from('<II', optional, 128)
            if not rva or not 16 <= length <= 8 * 1024 * 1024:
                return None
            sections = read(pe + 24 + optional_size, count * 40)
            mappings = []
            for i in range(count):
                virtual_size, virtual, raw_size, raw = struct.unpack_from('<IIII', sections, i * 40 + 8)
                mappings.append((virtual, raw_size, raw))
            def at(address, amount):
                for virtual, raw_size, raw in mappings:
                    if virtual <= address and address + amount <= virtual + raw_size:
                        return read(raw + address - virtual, amount)
                raise ValueError('Unmapped PE resource')
            resource = at(rva, length)
            def entries(offset):
                if not 0 <= offset <= len(resource) - 16:
                    raise ValueError('Invalid resource directory')
                named, ids = struct.unpack_from('<HH', resource, offset + 12)
                n = named + ids
                if n > 512 or offset + 16 + n * 8 > len(resource):
                    raise ValueError('Invalid resource entries')
                return [struct.unpack_from('<II', resource, offset + 16 + i * 8) for i in range(n)]
            versions = set()
            for kind, directory in entries(0):
                if kind != 16 or not directory & 0x80000000:
                    continue
                for _, names in entries(directory & 0x7fffffff):
                    if not names & 0x80000000:
                        continue
                    for _, data_offset in entries(names & 0x7fffffff):
                        if data_offset & 0x80000000 or data_offset + 16 > len(resource):
                            continue
                        address, amount = struct.unpack_from('<II', resource, data_offset)
                        if not 6 <= amount <= 1024 * 1024:
                            continue
                        data = at(address, amount)
                        total, value_size, value_type = struct.unpack_from('<HHH', data)
                        key = 'VS_VERSION_INFO\0'.encode('utf-16-le')
                        value = (6 + len(key) + 3) & ~3
                        if not value + 52 <= total <= len(data) or value_size < 52 or data[6:6 + len(key)] != key:
                            continue
                        signature, structure, ms, ls = struct.unpack_from('<IIII', data, value)
                        if signature == 0xfeef04bd and structure == 0x10000:
                            versions.add(f'{ms >> 16}.{ms & 0xffff}.{ls >> 16}.{ls & 0xffff}')
            return next(iter(versions)) if len(versions) == 1 else None
    except (OSError, ValueError, struct.error):
        return None


def configuration(game):
    path = game / 'Game/ERVR/ERVR.ini'
    if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(game.resolve()) or path.stat().st_size > 1024 * 1024:
        return None
    config = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        config.read_string(path.read_text(encoding='utf-8-sig'))
        return {'enabled': config.get('General', 'Enabled', fallback='unknown'),
                'runtime': config.get('General', 'VRRuntime', fallback='unknown'),
                'stereo': config.get('VR', 'StereoMode', fallback='unknown')}
    except (OSError, ValueError, configparser.Error):
        return None


def launch_command(command, game):
    """Replace exactly one recognized local game executable, never parse shell."""
    target = game / 'Game/eldenring.exe'
    if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(game.resolve()):
        raise RuntimeError('Game/eldenring.exe is missing or outside this Steam installation.')
    argv = list(command)
    matches = []
    for i, arg in enumerate(argv):
        normalized = arg.replace('\\', '/')
        if normalized[:3].casefold() == 'z:/':
            normalized = normalized[2:]
        p = Path(normalized)
        if p.name.casefold() in {'start_protected_game.exe', 'eldenring.exe'}:
            if not p.is_absolute() or p.resolve().parent != target.parent.resolve():
                raise RuntimeError('Steam command references another game folder; launch was stopped.')
            matches.append(i)
    if len(matches) != 1 or not matches[0]:
        raise RuntimeError('Expected one absolute Steam game executable argument. Wrappers/shell launch strings need manual review; nothing was launched.')
    if any(Path(a.replace('\\', '/')).name.casefold() in {'sh', 'bash', 'dash', 'fish', 'cmd', 'cmd.exe', 'powershell.exe'} for a in argv[:matches[0]]):
        raise RuntimeError('Shell-based launch commands are not supported by this offline adapter.')
    argv[matches[0]] = str(target)
    return argv


def launch(command):
    from . import bepinex, hub
    from .cli import _roots
    recipe = hub.load_recipes()['elden-ring']
    roots = _roots()
    game = hub.game_path(recipe, roots)
    if not game:
        raise RuntimeError('Elden Ring Steam directory was not found.')
    # No skip flag: an absent adapter must never pass the protected command on.
    argv = launch_command(command, game)
    version = file_version(game / 'Game/eldenring.exe')
    if version not in SUPPORTED:
        raise RuntimeError(f'ERVR 0.4.0 requires a reviewed game executable (2.6.2.0 / 2.7.1.0); found {version or "unknown"}. Nothing was launched.')
    if not hub._pfx(recipe, roots).is_dir() or not bepinex.verify(recipe, roots)['ready']:
        raise RuntimeError('Launch the flat game once to create its prefix, then install/verify the pinned ERVR package.')
    entry = hub.state().get('elden-ring', {})
    for name in ['Game/dxgi.dll', 'Game/dinput8.dll', 'Game/ERVR/ERVR.dll']:
        path = bepinex.target(game, name)
        if bepinex.digest(path) != entry.get('file_hashes', {}).get(name):
            raise RuntimeError(f'{name} changed after installation; review the loader before launch.')
    if bepinex.conflicts(game, recipe):
        raise RuntimeError('Conflicting loaders were found; review this installation before launch.')
    print('NAnnersVRhub: launching eldenring.exe directly with Steam’s command. Steam/game offline settings are manual prerequisites, not verified here.', file=sys.stderr)
    os.execvpe(argv[0], argv, os.environ.copy())
    return 0


def main(argv=None):
    try:
        return launch(list(sys.argv[1:] if argv is None else argv))
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f'Elden Ring launch stopped: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
