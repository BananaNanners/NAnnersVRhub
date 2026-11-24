# SPDX-License-Identifier: GPL-3.0-only
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from vrhub import hogwarts_update_pilot as pilot, profile_safety


class HogwartsPilotTests(unittest.TestCase):
    def setUp(self):
        self.baseline = dict.fromkeys(pilot.LOCAL_FILES | {"changed.lua", "same.lua"}, "old")
        self.current = {**self.baseline, **dict.fromkeys(pilot.LOCAL_FILES, "local"), "log.txt": "log"}
        self.incoming = {**self.baseline, "changed.lua": "new", "config_AFW.txt": "optional"}

    def test_classifies_all_paths_without_promoting_optional_config(self):
        rows = pilot.classify(self.current, self.baseline, self.incoming, tuple(self.baseline))
        actions = {name: action for action, name, _ in rows}
        self.assertEqual(actions, {
            **dict.fromkeys(pilot.LOCAL_FILES | {"same.lua", "log.txt"}, "Preserve"),
            "changed.lua": "Replace", "config_AFW.txt": "Install",
        })

    def test_drift_and_case_conflicts_block_review(self):
        with self.assertRaises(RuntimeError):
            pilot.classify({**self.current, "unexpected.lua": "new"}, self.baseline,
                           self.incoming, self.baseline)
        with self.assertRaises(RuntimeError):
            pilot.classify(self.current, self.baseline, self.incoming, ())
        with self.assertRaises(RuntimeError):
            pilot.classify(self.current, self.baseline, {**self.incoming, "CONFIG.TXT": "bad"},
                           self.baseline)

    def test_wrong_archive_hash_stops_before_inspecting_ownership(self):
        base = profile_safety.ProfilePlan(
            "hogwarts-legacy", "Hogwarts Legacy", "HogwartsLegacy.zip", "bad",
            "/tmp/example", (), 0, 0, 0, 0, 0, False, (), "fingerprint",
        )
        with patch.object(profile_safety, "build_plan", return_value=base):
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                pilot.build_review({"id": "hogwarts-legacy"}, Path(base.archive))
        self.assertFalse(replace(base, blocked=(pilot.COMPATIBILITY_BLOCK,)).ready)
