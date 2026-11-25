# SPDX-License-Identifier: GPL-3.0-only
"""Current-byte recognition from the pinned pair, never installation ownership.

No downloads, extraction, state migration, recovery or write authorization.
An explicit local archive pair is required; absent evidence stays unknown.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import zipfile

from . import uevr_dependency_review as review
from . import download_planner


def recognize(recipe, archives, steam_roots=None):
    """Read fresh evidence using the same exact manifest as installation review."""
    if recipe.get('id') != 'fatekeeper' or not recipe.get('archive_pins'):
        raise ValueError('Pinned Fatekeeper recipe required.')
    unknown = dict(status='Unknown', components=(), counts={}, source='current-pinned-bytes',
                   ownership_established=False, gameplay_verified=False)
    try:
        paths = tuple(Path(p) for p in archives)
        identities = tuple(download_planner.archive_identity(p) for p in paths)
        before = review.build_plan(recipe, paths, steam_roots)
        # Build twice to reject changes to either archive, root, inventory or
        # legacy state observed during the scan. No staged DLL is necessary.
        after = review.build_plan(recipe, paths, steam_roots)
        if (before != after or tuple(download_planner.archive_identity(p) for p in paths) != identities):
            raise RuntimeError('Installation or archive changed during recognition.')
        return summarize_plan(before)
    except (OSError, RuntimeError, ValueError, TypeError, zipfile.BadZipFile, EOFError) as exc:
        return dict(unknown, detail=str(exc))


def summarize_plan(plan):
    """Describe a just-built review; not permission or historical provenance."""
    unknown = dict(status='Unknown', components=(), counts={}, source='current-pinned-bytes',
                   ownership_established=False, gameplay_verified=False)
    if plan.verification_failed or not plan.file_decisions:
        raise RuntimeError('Complete pinned dependency evidence is unavailable.')
    required = {'Injector': {p for p in plan.injector_files if Path(p).suffix.lower() != '.pdb'},
                'Profile': set(plan.profile.file_names)}
    if not all(required.values()):
        raise RuntimeError('Incomplete dependency inventory.')
    groups = []
    total = Counter()
    for component, names in required.items():
        counts = Counter()
        issues = []
        seen = set()
        for action, role, name in plan.file_decisions:
            if role != component:
                continue
            if name in seen or action not in {'Install','Replace','Preserve'}:
                raise RuntimeError('Invalid dependency review inventory.')
            seen.add(name)
            if name not in names:
                if action != 'Preserve':
                    raise RuntimeError('Unexpected nondependency change.')
                counts['additional'] += 1
            elif action != 'Preserve':
                counts['missing' if action == 'Install' else 'different'] += 1
                issues.append((name, action))
            elif component == 'Profile' and name in review.FATEKEEPER_LOCAL_PROFILE_FILES:
                counts['customizable'] += 1
            else:
                counts['matching'] += 1
        if not names.issubset(seen):
            raise RuntimeError('Incomplete dependency review inventory.')
        total.update(counts)
        groups.append(dict(component=component, required=len(names), counts=dict(counts), issues=tuple(issues)))
    return dict(unknown, status='Review' if total['missing'] or total['different'] else 'Verified existing dependencies',
                sampled_at=datetime.now(timezone.utc).isoformat(), components=tuple(groups), counts={k:total[k] for k in ('matching','customizable','additional','missing','different')},
                detail='Current immutable files compared with pinned ZIP contents and the approved backend digest. Customizable files checked for presence only. No historical release or ownership attribution; no gameplay test.')


def summary_text(result):
    if result.get('status') == 'Unknown':
        return 'Existing dependency recognition: Unknown. ' + result.get('detail', '')
    c = result['counts']
    return (f"{result['status']}: {c['matching']} immutable matches, "
            f"{c['customizable']} protected settings present, {c['additional']} additional files preserved, "
            f"{c['missing']} missing, {c['different']} different. "
            "Current byte evidence only; no ownership, historical release or gameplay verification.")


def archives_from_rows(recipe, rows):
    """Accept only a complete unambiguous current pinned pair, in role order."""
    if recipe.get('id') != 'fatekeeper' or not recipe.get('archive_pins') or len(rows) != 2:
        return ()
    by_id = {r.get('id'): r for r in rows}
    result = []
    for role in ('uevr', 'profile'):
        r = by_id.get(role, {})
        if (r.get('status') != 'Pinned SHA-256 verified' or r.get('ambiguous') or r.get('candidate_incomplete')
                or not r.get('file') or r.get('sha256') != recipe['archive_pins'].get(role)):
            return ()
        result.append(Path(r['file']))
    return tuple(result)
