"""Hub adapter for the unchanged, user-tested KHARVOX lab 0.1.6 engine."""
import importlib.util
import os
from pathlib import Path
import sys
import threading

from .bepinex import digest

VERSION = '0.1.6'
ASSETS = None  # Tests may supply a verified fixture; runtime uses the shared component cache.
PAYLOAD_SHA256 = '7b51d0199a8780937165a023a12c293f5e8f0b95c1196eccacb0ea536a9521ba'
_lock = threading.Lock()
_active = {}


def state_dir():
    # Reuse the exact location used by the tested standalone lab.
    return Path.home() / '.local/share/nanners-kharvox-lab/0.1.0'


def payload_dir():
    from . import kharvox_component
    return ASSETS if ASSETS is not None else kharvox_component.payload_dir(state_dir())


def require_binaries():
    """Only trusted Python helpers are required to start the thin Hub."""
    for name in ('bridge_installer.py', 'kharvox_component.py'):
        if not Path(__file__).with_name(name).is_file():
            raise RuntimeError('Incomplete Hub package: a bridge installer helper is missing.')


def engine():
    from . import bridge_installer
    try:
        return bridge_installer.load_engine(payload_dir())
    except OSError as exc:
        raise RuntimeError('The DOOM bridge component is not installed. Use Install VR runner or Import bridge package.') from exc


def _passed(lab, state):
    stamp = lab.read_json(state / 'probe-pass.json')
    if (stamp.get('lab_version') != VERSION or stamp.get('openxr_session') is not True or
        stamp.get('module_sha256') != digest(lab.HERE / 'bin/winevulkan.dll') or
        stamp.get('native_module_sha256') != digest(lab.HERE / 'bin/wineopenxr.so')):
        raise ValueError('A new DOOM VR bridge test is required for this runner.')
    recorded, nonce = stamp.get('probe_result'), stamp.get('probe_nonce')
    if not isinstance(recorded, str) or not isinstance(nonce, str) or not Path(recorded).resolve().is_relative_to((state / 'logs/probe-results').resolve()):
        raise ValueError('The recorded DOOM bridge result is missing or outside its results folder.')
    lab.validate_result(Path(recorded), nonce, False)
    return Path(recorded)


def rows():
    """Read-only local state; a probe pass is historical synthetic evidence."""
    out = []
    try:
        lab = engine()
        out.append({'name':'DOOM VR bridge package','ok':True,'required':True,
                    'detail':f'Installed lab {VERSION}; files match its pinned inventory. Gameplay is not checked.'})
    except (OSError,ValueError,RuntimeError) as exc:
        return [{'name':'DOOM VR bridge package','ok':False,'required':True,'detail':str(exc)}]
    state = state_dir()
    try:
        runner = lab.verify_runner(state, lab.read_json(lab.HERE / 'base-files.json'))
        out.append({'name':'Isolated DOOM VR runner','ok':True,'required':True,
                    'detail':f'{runner}; pinned runner modules verified. Heroic selection is unchanged.'})
    except (OSError,ValueError,KeyError) as exc:
        out.extend([{'name':'Isolated DOOM VR runner','ok':False,'required':True,
                     'detail':f'Use Install VR runner. {exc}'},
                    {'name':'DOOM VR bridge test','ok':False,'required':True,
                     'detail':'Install the runner, connect WiVRn, then use Test DOOM VR bridge.'}])
        return out
    try:
        result = _passed(lab, state)
        out.append({'name':'DOOM VR bridge test','ok':True,'required':True,
                    'detail':f'Full lab {VERSION} probe recorded: {result}. Historical synthetic test; no current gameplay claim.'})
    except (OSError,ValueError,KeyError) as exc:
        out.append({'name':'DOOM VR bridge test','ok':False,'required':True,
                    'detail':f'Connect WiVRn and use Test DOOM VR bridge. {exc}'})
    return out


def plan(recipe, game, action='doom', bridge_archive=None):
    if action not in {'prepare','probe','doom'}:
        raise RuntimeError('Unknown DOOM VR bridge action.')
    from . import heroic, kharvox
    from . import kharvox_component
    script = Path(kharvox_component.__file__).resolve()
    args = [sys.executable, '-I', '-u', str(script),
            {'prepare':'install', 'probe':'probe', 'doom':'launch'}[action],
            '--state', str(state_dir())]
    # Installation has no game/prefix dependency and never edits Heroic settings.
    if bridge_archive is not None:
        if action != 'prepare':
            raise RuntimeError('Import a bridge archive using Install VR runner first.')
        args += ['--bridge-archive', str(bridge_archive)]
    if action == 'prepare':
        return args, dict(os.environ), str(script.parent)
    lab = engine()
    _, host_env, root = kharvox._host_plan(recipe, game)
    if heroic.config_root().resolve() != (Path.home()/'.config/heroic').resolve():
        raise RuntimeError('The tested DOOM bridge currently requires native Heroic settings in ~/.config/heroic.')
    if action == 'doom':
        try:
            lab.verify_runner(state_dir(), lab.read_json(lab.HERE/'base-files.json'))
            _passed(lab, state_dir())
        except (OSError,ValueError,KeyError) as exc:
            raise RuntimeError(f'Install and test the isolated DOOM VR runner first. {exc}') from exc
    args += ['--kharvox', root, '--game', str(game)]
    return args, dict(os.environ), root


def start(recipe, game, action='doom', bridge_archive=None):
    from .heroic_injector import InjectorLaunch
    key = str(state_dir())
    with _lock:
        previous = _active.get(key)
        if previous and previous[1].poll() is None:
            if previous[0] != action:
                raise RuntimeError('A DOOM VR bridge action is still running. Finish it before starting another.')
            return previous[1]
        args, env, cwd = plan(recipe, game, action, bridge_archive=bridge_archive) if bridge_archive is not None else plan(recipe, game, action)
        launch = InjectorLaunch(args, env, cwd)
        _active[key] = (action, launch)
        return launch


def log_paths():
    logs = state_dir()/'logs'
    return {'launch':logs/'doom-launch.log', 'probe':logs/'probe.log', 'audit':logs/'audit.log'}
