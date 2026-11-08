# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Recent recovery selection is independent of random folder names."""
import json
import os
import shutil
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest import mock
from tests.test_game_saves import SaveFixtures
from vrhub.recovery_discovery import recent_recovery_folders
from vrhub import doom_saves


class RecoveryDiscoveryTests(SaveFixtures, unittest.TestCase):
    def make_records(self, rid, count, *, four=False):
        b,s,t=self.pair(rid)
        root=self.home/'hub/backups';root.mkdir(parents=True,exist_ok=True)
        folders=[]
        for i in range(count):
            # Newest records sort LAST alphabetically. This defeats name order.
            prefix=b.backup_prefix
            if four and i % 2:prefix='doom-saves-'
            folder=root/f'{prefix}{i:04}'
            names=['source-savegame','target-before-savegame']
            if four:names+=['experimental-savegame','heroic-before-savegame']
            for name in names:shutil.copytree(s,folder/name)
            row=b.snapshot(s)
            record=dict(schema=1,status='restored',game_id=rid,operation='restore',
                        created_at=(datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(seconds=i)).isoformat(),
                        source=row,target=row)
            (folder/'restore.json').write_text(json.dumps(record))
            folders.append(folder)
        return b,s,t,root,folders

    def test_newest_128_selected_and_no_copy_lost_to_old_256_row_cap(self):
        b,s,t,root,folders=self.make_records('fatekeeper',130)
        with mock.patch.object(b,'targets',return_value=[t]):report=b.discover(b.recipe)
        copies=[r for r in report['rows'] if r.get('recovery_group')]
        self.assertEqual(len(copies),256)
        self.assertEqual({r['recovery_group'] for r in copies},{str(p) for p in folders[2:]})
        self.assertTrue(all(r['usable'] for r in copies))
        self.assertTrue(any('2 additional backup sets' in n for n in report['notes']))
        self.assertTrue(folders[0].is_dir())

    def test_doom_combines_legacy_and_current_sets_before_limiting(self):
        b,s,t,root,folders=self.make_records('doom-2016-gog',130,four=True)
        with mock.patch.object(b,'targets',return_value=[t]),mock.patch.object(doom_saves,'current_target',return_value=t):
            report=b.discover(b.recipe)
        copies=[r for r in report['rows'] if r.get('recovery_group')]
        self.assertEqual(len(copies),512)
        self.assertEqual({r['recovery_group'] for r in copies},{str(p) for p in folders[2:]})
        self.assertTrue(all(r['usable'] for r in copies))
        self.assertTrue(any('2 additional backup sets' in n for n in report['notes']))

    def test_standalone_doom_discovery_keeps_newest_legacy_copies(self):
        b,s,t,root,folders=self.make_records('doom-2016-gog',260,four=True)
        # Standalone DOOM scans its historical prefix, not generic game backups.
        legacy=[p for p in folders if p.name.startswith('doom-saves-')]
        with mock.patch.object(doom_saves,'current_target',return_value=t):report=doom_saves.discover(b.recipe)
        self.assertTrue(any(r['root']==str(legacy[-1]/'source-savegame') for r in report['rows']))
        self.assertEqual(len(report['rows']),1+4*128)
        self.assertFalse(any(r['root']==str(legacy[0]/'source-savegame') for r in report['rows']))
        self.assertTrue(any('2 additional backup sets' in n for n in report['notes']))

    def test_invalid_missing_linked_metadata_falls_back_without_crashing(self):
        root=self.home/'records';root.mkdir()
        for i,raw in enumerate(('broken','[]','{}','{"schema":1,"created_at":"2026-01-01"}')):
            p=root/str(i);p.mkdir();(p/'restore.json').write_text(raw);os.utime(p,(100+i,100+i))
        linked=root/'linked';linked.mkdir();(linked/'restore.json').symlink_to(root/'0/restore.json');os.utime(linked,(200,200))
        missing=root/'missing';missing.mkdir();os.utime(missing,(300,300))
        selected,omitted,fallback=recent_recovery_folders(root,('*',),2)
        self.assertEqual(selected,[missing,linked]);self.assertEqual(omitted,4);self.assertEqual(fallback,6)

    def test_timezone_offsets_rank_by_instant_not_iso_string(self):
        root=self.home/'records';root.mkdir()
        for name,stamp in [('old','2026-01-02T01:00:00+10:00'),('new','2026-01-01T20:00:00+00:00')]:
            p=root/name;p.mkdir();(p/'restore.json').write_text(json.dumps(dict(schema=1,created_at=stamp)))
        paths,omitted,fallback=recent_recovery_folders(root,('*',),1)
        self.assertEqual(paths,[root/'new']);self.assertEqual(omitted,1);self.assertEqual(fallback,0)

    def test_under_limit_has_no_omission_warning(self):
        b,s,t,root,folders=self.make_records('fatekeeper',2)
        with mock.patch.object(b,'targets',return_value=[t]):report=b.discover(b.recipe)
        self.assertFalse(any('Recovery list limit' in n for n in report['notes']))
