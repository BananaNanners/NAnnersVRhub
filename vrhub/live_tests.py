"""Explicit user-reported gameplay history, independent of installer state.

Reads do not create files. Saves serialize concurrent writers and atomically
replace the history; a malformed existing history is never silently overwritten.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import tempfile
import uuid
from .display_time import local_time

OUTCOMES = {"success": "SUCCESS", "partial": "PARTIAL SUCCESS", "failure": "FAILURE"}
CHECKS = {"vr_rendering": "VR rendering", "head_tracking": "Head tracking",
          "controller_input": "Controller input", "stereo_depth": "Stereo depth"}
STATES = {"passed": "PASSED", "failed": "FAILED", "not-tested": "NOT TESTED"}
MAX_NOTES = 4000


def history_file():
    from .hub import state_file
    return state_file().with_name('live-tests.json')


def validate_result(outcome, notes, checks):
    if not isinstance(outcome, str) or outcome not in OUTCOMES:
        raise RuntimeError('Choose success, partial success, or failure.')
    if not isinstance(notes, str) or len(notes) > MAX_NOTES:
        raise RuntimeError(f'Test notes must be text of at most {MAX_NOTES} characters.')
    if not isinstance(checks, dict) or set(checks) - CHECKS.keys():
        raise RuntimeError('Unknown gameplay check in test record.')
    checks = {key: checks.get(key, 'not-tested') for key in CHECKS}
    if any(not isinstance(value, str) or value not in STATES for value in checks.values()):
        raise RuntimeError('Each gameplay check must be passed, failed, or not tested.')
    if outcome == 'success' and (checks['vr_rendering'] != 'passed' or 'failed' in checks.values()):
        raise RuntimeError('Success requires VR rendering marked Passed and no checks marked Failed. Use Partial success or Failure for other results.')
    if outcome in {'partial', 'failure'} and not notes.strip():
        raise RuntimeError('Describe what worked, failed, or required a workaround in the notes.')
    return checks


def _load():
    path = history_file()
    try:
        if not path.exists():
            return {'schema_version': 1, 'games': {}}
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('games'), dict):
            raise ValueError('unsupported history format')
        for rid, records in data['games'].items():
            if not isinstance(rid, str) or not isinstance(records, list):
                raise ValueError('invalid game history')
            for record in records:
                if not isinstance(record, dict) or not isinstance(record.get('id'), str) or not isinstance(record.get('setup'), dict):
                    raise ValueError('invalid test record')
                if record.get('recipe_id') != rid or not isinstance(record.get('game'), str) or not record['game'].strip():
                    raise ValueError('record belongs to another game')
                _validate_setup(record['setup'])
                when = datetime.fromisoformat(record['recorded_at'])
                utc = datetime.fromisoformat(record['recorded_at_utc'])
                if utc.utcoffset() is None or when.utcoffset() is None:
                    raise ValueError('missing timestamp timezone')
                validate_result(record['outcome'], record['notes'], record['checks'])
        return data
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        raise RuntimeError(f'Cannot read local test history at {path}. Existing history has been preserved; review or restore that file before saving tests.') from exc


def history(recipe_id):
    """Newest entry first; never interpret a bundled recipe reference as local."""
    return deepcopy(list(reversed(_load()['games'].get(recipe_id, []))))


def _validate_setup(setup):
    if not isinstance(setup.get('hub_version'), str) or not isinstance(setup.get('local_status'), str):
        raise ValueError('invalid setup labels')
    findings = setup.get('findings')
    if not isinstance(findings, list) or any(not isinstance(r, dict) or any(
            not isinstance(r.get(key), str) for key in ('name', 'status', 'detail')) for r in findings):
        raise ValueError('invalid setup findings')
    workarounds = setup.get('profile_workarounds')
    if not isinstance(workarounds, list) or any(not isinstance(x, str) for x in workarounds):
        raise ValueError('invalid setup workarounds')


def _setup(report):
    return {'hub_version': report['hub_version'], 'local_status': report['status'],
            'findings': deepcopy(report['checks']),
            'profile_workarounds': list((report.get('profile') or {}).get('workarounds', []))}


@contextmanager
def _writer_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(path) + '.lock', os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def record(recipe, outcome, notes, checks, report):
    checks = validate_result(outcome, notes, checks)
    if report.get('recipe_id') != recipe['id']:
        raise RuntimeError('The test report belongs to another game. Refresh compatibility and retry.')
    now = datetime.now().astimezone()
    entry = {'id': uuid.uuid4().hex, 'recipe_id': recipe['id'], 'game': recipe['name'], 'recorded_at': now.isoformat(),
             'recorded_at_utc': now.astimezone(timezone.utc).isoformat(),
             'outcome': outcome, 'notes': notes.strip(), 'checks': checks,
             'setup': _setup(report)}
    _validate_setup(entry['setup'])
    path = history_file()
    with _writer_lock(path):
        data = _load()  # re-read under the lock; another GUI/CLI writer may have appended
        data['games'].setdefault(recipe['id'], []).append(entry)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                             prefix='.live-tests-', suffix='.tmp', delete=False) as output:
                temporary = Path(output.name)
                json.dump(data, output, indent=2, ensure_ascii=False)
                output.write('\n'); output.flush(); os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return deepcopy(entry)


def record_text(entry, *, include_setup=False):
    lines = [f"Local gameplay test: {OUTCOMES[entry['outcome']]}",
             f"Game: {entry['game']} ({entry['recipe_id']})",
             f"Recorded: {local_time(entry['recorded_at'])}",
             'User reported; this does not automatically verify another session or setup.']
    lines += [f'{label}: {STATES[entry["checks"].get(key, "not-tested")]}' for key, label in CHECKS.items()]
    lines.append('Notes: ' + (entry['notes'] or '(none)'))
    setup = entry['setup']
    lines.append('Local configuration when recorded: ' + str(setup.get('local_status', 'not captured')))
    if include_setup:
        lines.append('Hub version when recorded: ' + str(setup.get('hub_version', 'not captured')))
        lines.append('Local findings at recording (historical snapshot):')
        lines += [f"[{r['status'].upper()}] {r['name']}: {r['detail']}" for r in setup.get('findings', [])]
        if setup.get('profile_workarounds'):
            lines += ['Profile workarounds at recording (not automatically verified):',
                      *['  - ' + x for x in setup['profile_workarounds']]]
    return '\n'.join(lines)


def history_text(recipe, entries):
    return (f"{recipe['name']} — local gameplay test history\n\n" +
            ('\n\n'.join(record_text(r, include_setup=True) for r in entries) if entries else
             'No local gameplay tests recorded. Bundled references are separate.'))
