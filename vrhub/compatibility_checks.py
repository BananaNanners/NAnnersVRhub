"""Recipe-driven local evidence for Steam mod and injector workflows.

Only reads files and finds tool paths. It never executes a runner, parses launch
options as shell code, or promotes file presence to gameplay validation.
"""
from pathlib import Path
import re
import shutil

from .schema import RecipeError

PATH_KEYS = {"game_files", "prefix_files"}
BOOL_KEYS = {"recorded_proton", "tracked_install", "tracked_profile", "all_components"}


def validate(checks, source):
    if not isinstance(checks, dict) or set(checks) - (PATH_KEYS | BOOL_KEYS | {"commands"}):
        raise RecipeError(f"{source}: invalid compatibility.checks table or unknown check")
    for key in BOOL_KEYS & checks.keys():
        if not isinstance(checks[key], bool):
            raise RecipeError(f"{source}: compatibility.checks.{key} must be true/false")
    for key in (PATH_KEYS | {"commands"}) & checks.keys():
        items = checks[key]
        if not isinstance(items, list) or any(not isinstance(x, str) or not x.strip() for x in items):
            raise RecipeError(f"{source}: compatibility.checks.{key} must be a list of non-empty strings")
        for item in items:
            path = Path(item.replace('\\', '/'))
            if key in PATH_KEYS and (path.is_absolute() or '..' in path.parts or ':' in item or path == Path('.')):
                raise RecipeError(f"{source}: unsafe compatibility.checks.{key} path")
            if key == 'commands' and not re.fullmatch(r'[A-Za-z0-9_.+-]+', item):
                raise RecipeError(f"{source}: invalid compatibility command name")


def _file_under(path, base):
    try:
        return path.resolve().is_relative_to(base.resolve()) and path.is_file()
    except (OSError, RuntimeError):
        return False


def _recorded_proton(prefix):
    info = prefix.parent / 'config_info'
    try:
        lines = info.read_text(errors='replace').splitlines()
    except OSError:
        return None
    for raw in lines:
        item = raw.strip()
        if not item:
            continue
        path = Path(item)
        candidates = [path if path.name == 'proton' else path / 'proton']
        if '/files/' in item:
            candidates.append(Path(item.split('/files/', 1)[0]) / 'proton')
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
    return None


def _inventory(entry, base, suffix=None):
    """Check a Hub manifest against this install, never another library/prefix."""
    if not isinstance(entry, dict) or not entry.get('files'):
        return 'unknown', 'No non-empty Hub file inventory recorded; manual installations are not fully inventoried.'
    paths = entry['files']
    if not isinstance(paths, list) or any(not isinstance(x, str) or not Path(x).is_absolute() for x in paths):
        return 'unknown', 'Invalid Hub file inventory; cannot establish installation completeness.'
    bad = [path for path in paths if not _file_under(Path(path), base) or (suffix and Path(path).suffix.lower() != suffix)]
    if bad:
        return 'error', f'{len(bad)} of {len(paths)} recorded files are missing, outside the current install, or of the wrong file type. Review this install before reinstalling anything.'
    return 'ok', f'All {len(paths)} recorded files are present under {base}; this does not verify DLL loading or file versions.'


def rows(recipe, game):
    from . import hub
    checks = recipe.get('compatibility', {}).get('checks')
    if checks is None:
        return []
    out = []
    def add(name, status, detail):
        out.append(dict(name=name, status=status, detail=detail))

    prefix = game.parents[1] / 'compatdata' / str(recipe['steam_appid']) / 'pfx' if game else None
    if checks.get('recorded_proton'):
        proton = _recorded_proton(prefix) if prefix and prefix.is_dir() else None
        add('Recorded Proton', 'ok' if proton else 'unknown',
            f'{proton}; recorded by prefix config_info, not a running-process or Steam selection check.' if proton else
            'No existing recorded Proton path resolved from this game prefix. Steam remains the runner source of truth; review its Compatibility setting.')
    for key, base, title in [('game_files', game, 'Game file'), ('prefix_files', prefix, 'Prefix file')]:
        for relative in checks.get(key, []):
            path = base / Path(relative.replace('\\', '/')) if base else None
            present = bool(path and _file_under(path, base))
            add(f'{title}: {relative}', 'ok' if present else 'error',
                (str(path) + (' (present; loading unverified)' if present else ' (missing or outside the current install)'))
                if path else 'Game/prefix not found; this file cannot be checked.')
    for command in checks.get('commands', []):
        found = shutil.which(command)
        add(f'Launch tool: {command}', 'ok' if found else 'error', found or 'Not found on PATH; required by this Hub launch workflow.')
    state = hub.state()
    if checks.get('tracked_install'):
        base = (prefix / 'drive_c/uevr' if recipe.get('method') == 'uevr' and prefix else game)
        suffix = None
        if recipe.get('method', 'file') == 'file' and game:
            base = game / recipe['files'][0]['dest']
            suffix = '.' + recipe['files'][0]['kind']
        status, detail = _inventory(state.get(recipe['id']), base, suffix) if base else ('unknown', 'Game/prefix unavailable.')
        add('Mod install inventory', status, detail)
    if checks.get('tracked_profile'):
        base = prefix / hub.APPDATA / recipe['profile']['dir'] if prefix else None
        status, detail = _inventory(state.get(recipe['id'] + ':profile'), base) if base else ('unknown', 'Game/prefix unavailable.')
        add('UEVR game-profile inventory', status, detail)
    if checks.get('all_components'):
        entry = state.get(recipe['id'], {})
        components = entry.get('components', {})
        for component in recipe.get('components', []):
            record = components.get(str(component['nexus_mod']))
            status, detail = _inventory(record, game) if game else ('unknown', 'Game unavailable.')
            add('VR workflow component: ' + component['name'], status, detail)
        # Unlike the base-game launch guard, a VR compatibility report requires
        # the phase-2 VR port as well as its prerequisites.
        if recipe.get('components'):
            later = hub.verify(recipe)['later_bad']
            add('VR port installation', 'error' if later else 'ok',
                '; '.join(f"{r['name']}: {r['detail']}" for r in later) if later else
                'All phase-2 VR components are recorded and present; live loading remains unverified.')
    for instruction in recipe.get('compatibility', {}).get('manual_checks', []):
        add('Manual review', 'warning', instruction + ' This is not inspected automatically.')
    return out
