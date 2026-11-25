# SPDX-License-Identifier: GPL-3.0-only
import tempfile
import unittest
import zipfile
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
from vrhub import hub, fatekeeper_recognition as recognition, uevr_dependency_review as review, profile_safety


class RecognitionTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.prefix = root / 'pfx'
        self.injector = self.prefix / 'drive_c/uevr'
        self.profile = self.prefix / 'drive_c/profile'
        self.injector.mkdir(parents=True)
        self.profile.mkdir()
        self.state = root / 'state.json'
        self.state.write_bytes(b'{"other":{"files":["preserve"]}}\n')
        self.archives = [root / 'uevr.zip', root / 'profile.zip']
        for path, files in zip(self.archives, ({'UEVRInjector.exe':b'exe','UEVRBackend.dll':b'bundled','debug.pdb':b'debug'}, {'config.txt':b'default','plugin.dll':b'plugin'})):
            with zipfile.ZipFile(path,'w') as archive:
                for name,data in files.items(): archive.writestr(name,data)
        self.recipe = hub.load_recipes()['fatekeeper']
        self.recipe['archive_pins'] = {role:sha256(path.read_bytes()).hexdigest() for role,path in zip(('uevr','profile'),self.archives)}
        self.enterContext(patch.multiple(hub,_pfx=lambda *_:self.prefix,_uevr_dir=lambda *_:self.injector,profile_dir=lambda *_:self.profile,state_file=lambda:self.state))
        self.enterContext(patch.multiple(review,FATEKEEPER_BACKEND_SHA256=sha256(b'approved').hexdigest(),FATEKEEPER_BACKEND_SIZE=8))
        for base,files in ((self.injector,{'UEVRInjector.exe':b'exe','UEVRBackend.dll':b'approved','debug.pdb':b'local'}),(self.profile,{'config.txt':b'custom','plugin.dll':b'plugin','log.txt':b'user'})):
            for name,data in files.items(): (base/name).write_bytes(data)

    def scan(self):
        return recognition.recognize(self.recipe,self.archives)

    def test_manual_and_legacy_without_writes_or_ownership(self):
        for raw in (self.state.read_bytes(), b'{"fatekeeper":{"files":["legacy"]}}\n'):
            self.state.write_bytes(raw)
            before = [profile_safety._snapshot(p) for p in (self.injector,self.profile)]
            with patch.object(hub,'_save_state',side_effect=AssertionError('no save')):
                result=self.scan()
            self.assertEqual(result['status'],'Verified existing dependencies',result)
            self.assertEqual(result['counts'],dict(matching=3,customizable=1,additional=2,missing=0,different=0))
            self.assertFalse(result['ownership_established']); self.assertFalse(result['gameplay_verified'])
            self.assertEqual(self.state.read_bytes(),raw)
            self.assertEqual([profile_safety._snapshot(p) for p in (self.injector,self.profile)],before)

    def test_missing_backend_and_modified_plugin(self):
        (self.injector/'UEVRBackend.dll').unlink()
        (self.profile/'plugin.dll').write_bytes(b'wrong')
        result=self.scan()
        self.assertEqual(result['status'],'Review',result)
        self.assertEqual(result['counts']['missing'],1)
        self.assertEqual(result['counts']['different'],1)
        self.assertFalse((self.injector/'UEVRBackend.dll').exists())

    def test_missing_customizable_file_is_not_verified(self):
        (self.profile/'config.txt').unlink()
        result=self.scan()
        self.assertEqual(result['status'],'Review',result)
        self.assertEqual(result['counts']['missing'],1)

    def test_bad_archive_and_symlink_are_unknown(self):
        original=self.archives[0].read_bytes()
        self.archives[0].write_bytes(b'bad')
        self.assertEqual(self.scan()['status'],'Unknown')
        self.archives[0].write_bytes(original)
        (self.profile/'plugin.dll').unlink()
        (self.profile/'plugin.dll').symlink_to(self.state)
        self.assertEqual(self.scan()['status'],'Unknown')

    def test_changed_between_reviews_is_unknown(self):
        original=review.build_plan
        calls=0
        def changing(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==2: (self.profile/'plugin.dll').write_bytes(b'changed')
            return original(*args,**kwargs)
        with patch.object(review,'build_plan',side_effect=changing):
            self.assertEqual(self.scan()['status'],'Unknown')
