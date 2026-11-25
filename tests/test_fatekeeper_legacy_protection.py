# SPDX-License-Identifier: GPL-3.0-only
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from vrhub import hub, profile_safety, fatekeeper_commit


class LegacyProtectionTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.state = self.root / 'state.json'
        self.file = self.root / 'player.dll'
        self.file.write_bytes(b'keep')
        self.recipe = hub.load_recipes()['fatekeeper']
        self.enterContext(patch.object(hub,'state_file',return_value=self.state))
        self.enterContext(patch.object(hub,'load_recipes',return_value={'fatekeeper':self.recipe}))

    def test_legacy_manual_and_malformed_records_never_remove(self):
        for records in ({}, {'fatekeeper':{'files':[str(self.file)]}}, {'fatekeeper':None}, {'fatekeeper:profile':{'installer':'uevr-profile-2','files':[str(self.file)]}}, {'fatekeeper':{'installer':'gameroot-2','files':[str(self.file)]}}):
            self.state.write_text(json.dumps(records))
            before = self.state.read_bytes()
            for key in ('fatekeeper','fatekeeper:profile'):
                with self.assertRaisesRegex(RuntimeError,'automatic removal blocked'):
                    hub.uninstall(key,profile_confirm=True)
                self.assertEqual(self.state.read_bytes(),before)
                self.assertEqual(self.file.read_bytes(),b'keep')

    def test_either_paired_record_routes_both_keys_to_gated_recovery(self):
        for key in ('fatekeeper','fatekeeper:profile'):
            self.state.write_text(json.dumps({key:{'installer':'fatekeeper-pair-fk4'}}))
            before=self.state.read_bytes()
            for target in ('fatekeeper','fatekeeper:profile'):
                with self.assertRaisesRegex(RuntimeError,'Confirm recovery'):
                    hub.uninstall(target)
                with self.assertRaisesRegex(RuntimeError,'Explicit live Fatekeeper authorization'):
                    hub.uninstall(target,profile_confirm=True)
                self.assertEqual(self.state.read_bytes(),before)

    def test_direct_profile_paths_cannot_bypass_pair(self):
        self.state.write_text('{}')
        self.assertFalse(profile_safety.review_restore('fatekeeper:profile')['ready'])
        with patch.object(profile_safety,'_assert_execution_gate',side_effect=AssertionError('must refuse first')):
            with self.assertRaisesRegex(RuntimeError,'paired recovery'):
                profile_safety.restore('fatekeeper:profile',confirmed=True)
            with self.assertRaisesRegex(RuntimeError,'verified Fatekeeper dependency pair'):
                profile_safety.install(self.recipe,self.file,confirmed=True,approved_fingerprint='x')
        self.assertEqual(self.file.read_bytes(),b'keep')
        self.assertEqual(self.state.read_text(),'{}')
