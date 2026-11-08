# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Order recovery sets by recorded creation time, never by random folder names.

Ordering is presentation only and does not establish payload integrity or progress.
"""
from datetime import datetime
import heapq
import json


def recent_recovery_folders(root, patterns, limit=128):
    folders = {p for pattern in patterns for p in root.glob(pattern)}
    fallback_count = 0

    def rank(folder):
        nonlocal fallback_count
        try:
            record = folder / 'restore.json'
            if folder.is_symlink() or record.is_symlink() or record.stat().st_size > 8 * 1024**2:
                raise ValueError('Linked or oversized metadata')
            data = json.loads(record.read_text())
            if not isinstance(data, dict) or data.get('schema') != 1:
                raise ValueError('Unknown record')
            stamp = datetime.fromisoformat(data['created_at'])
            if stamp.tzinfo is None:
                raise ValueError('Missing timezone')
            when = stamp.timestamp()
        except (OSError, ValueError, TypeError, KeyError, OverflowError):
            fallback_count += 1
            try:
                when = folder.lstat().st_mtime
            except OSError:
                when = float('-inf')
        return when, str(folder)

    # nlargest keeps the returned payload scan bounded; every record must be
    # considered to determine recency because suffixes are randomly generated.
    selected = heapq.nlargest(limit, folders, key=rank)
    return selected, max(0, len(folders) - len(selected)), fallback_count


def selection_notes(omitted, fallback_count):
    notes = []
    if omitted:
        notes.append(f'Recovery list limit: {omitted} additional backup sets are not shown. '
                     'The 128 most recent sets are listed; no backups were deleted. '
                     'Browse for another source folder to inspect an omitted set.')
    if fallback_count:
        notes.append('Recovery sets without readable creation dates are ordered using folder modification times; '
                     'this does not verify save progress or backup integrity.')
    return notes
