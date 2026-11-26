# SPDX-License-Identifier: GPL-3.0-only
"""Disposable pinned-pair recognition; never live game evidence."""
import os
import stat
import unittest
from unittest.mock import patch
from vrhub import bepinex, bepinex_recognition as recognition, hub
from tests import test_subnautica, test_valheim


class RecognitionCases:
    def setUp(self):
        self.f = self.fixture_class()
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()
        self.game = self.f.game
        self.recipe = self.f.recipe
        self.archives = self.f.archives

    def snapshot(self):
        result = {}
        for p in self.f.fixture.home.rglob("*"):
            s = p.lstat()
            result[str(p)] = (stat.S_IMODE(s.st_mode),
                              os.readlink(p) if p.is_symlink() else
                              p.read_bytes() if p.is_file() else None)
        return result

    def scan(self, archives=None):
        before = self.snapshot()
        result = recognition.recognize(self.recipe, self.archives if archives is None else archives,
                                       [self.f.fixture.steam])
        self.assertEqual(before, self.snapshot())
        for key in ("ownership_established", "gameplay_verified", "write_authorized"):
            self.assertIs(result[key], False)
        return result

    def test_empty_and_installed_pair(self):
        result = self.scan()
        self.assertEqual(result["status"], "Review")
        self.assertFalse(result["record_present"])
        self.assertEqual(result["counts"]["missing"], len(result["rows"]))
        self.f.install()
        result = self.scan(list(reversed(self.archives)))
        self.assertEqual(result["status"], "Pinned bytes match")
        self.assertTrue(result["record_present"])
        self.assertEqual(result["counts"]["matching"], len(result["rows"]))
        self.assertEqual({r["component"] for r in result["rows"]},
                         {p["id"] for p in self.recipe["packages"]})
        self.f.assert_preserved()

    def test_matching_without_ownership(self):
        self.f.install()
        state = hub.state()
        del state[self.recipe["id"]]
        hub._save_state(state)
        result = self.scan()
        self.assertEqual(result["status"], "Pinned bytes match")
        self.assertFalse(result["record_present"])

    def test_modified_settings_binary_missing_and_unrelated(self):
        self.f.install()
        (self.game/"winhttp.dll").write_bytes(b"changed loader")
        (self.game/"BepInEx/config/BepInEx.cfg").write_bytes(b"custom settings")
        (self.game/"BepInEx/core/BepInEx.dll").unlink()
        self.f.fixture.file(self.game/"BepInEx/plugins/other.dll")
        result = self.scan()
        self.assertEqual(result["status"], "Review")
        self.assertEqual({k:result["counts"][k] for k in ("different","missing","modified-settings")},
                         {"different":1,"missing":1,"modified-settings":1})
        self.assertNotIn("BepInEx/plugins/other.dll", {r["path"] for r in result["rows"]})
        self.f.assert_preserved()

    def test_wrong_incomplete_duplicate_archives(self):
        for pair in ([], self.archives[:1], [self.archives[0]]*2):
            self.assertEqual(self.scan(pair)["status"], "Unknown")
        self.archives[1].write_bytes(b"not pinned")
        self.assertEqual(self.scan()["status"], "Unknown")

    def test_conflict_requires_review(self):
        self.f.install()
        name = ("BepInEx/plugins/VREnhancements.dll" if self.recipe["id"]=="subnautica"
                else "BepInEx/plugins/duplicate/ValheimVRMod.dll")
        self.f.fixture.file(self.game/name)
        result = self.scan()
        self.assertEqual(result["status"], "Review")
        self.assertTrue(result["conflicts"])

    def test_symlink_hardlink_case_collision(self):
        self.f.install()
        p = self.game/"winhttp.dll"
        data = p.read_bytes()
        outside = self.f.fixture.home/"outside.dll"
        outside.write_bytes(data)
        p.unlink()
        p.symlink_to(outside)
        self.assertEqual(self.scan()["status"], "Unknown")
        p.unlink()
        os.link(outside,p)
        self.assertEqual(self.scan()["status"], "Unknown")
        p.unlink()
        (p.parent/"WINHTTP.DLL").write_bytes(data)
        self.assertEqual(self.scan()["status"], "Unknown")

    def test_changed_between_samples(self):
        self.f.install()
        original = recognition._sample
        calls = []
        def changed(*args):
            result = original(*args)
            calls.append(1)
            if len(calls)==1:
                (self.game/"winhttp.dll").write_bytes(b"external change")
            return result
        with patch.object(recognition,"_sample",side_effect=changed):
            result = recognition.recognize(self.recipe,self.archives,[self.f.fixture.steam])
        self.assertEqual(result["status"], "Unknown")
        self.assertEqual(len(calls),2)
        self.assertFalse(result["write_authorized"])
        self.assertEqual((self.game/"winhttp.dll").read_bytes(),b"external change")

    def test_missing_windows_layout(self):
        (self.game/bepinex.policy(self.recipe)["exe"]).unlink()
        self.assertEqual(self.scan()["status"],"Unknown")


class SubnauticaRecognition(RecognitionCases, unittest.TestCase):
    fixture_class = test_subnautica.SubnauticaTests


class ValheimRecognition(RecognitionCases, unittest.TestCase):
    fixture_class = test_valheim.ValheimTests


class ScopeTests(unittest.TestCase):
    def test_elden_ring_not_enabled(self):
        self.assertEqual(recognition.recognize({"id":"elden-ring"},[])["status"],"Unknown")
