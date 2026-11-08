# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Licensing notices must survive the actual managed payload filter."""
from pathlib import Path
import tomllib
import unittest
from vrhub import self_install

ROOT=Path(__file__).resolve().parents[1]


class LicensePackagingTests(unittest.TestCase):
    def test_managed_payload_retains_full_license_and_existing_mit_notice(self):
        _version,files=self_install._source_files(ROOT)
        self.assertEqual(files['LICENSE'],(ROOT/'LICENSE').read_bytes())
        self.assertEqual(files['vrhub/licenses/GPL-3.0.txt'],files['LICENSE'])
        self.assertIn(b'GNU GENERAL PUBLIC LICENSE',files['LICENSE'])
        self.assertIn(b'Version 3, 29 June 2007',files['LICENSE'])
        self.assertIn(b'MIT License',files['vrhub/licenses/Bridge-Installer-MIT.txt'])
        self.assertIn(b'Permission is hereby granted',files['vrhub/licenses/Bridge-Installer-MIT.txt'])
        self.assertIn('bridge_installer.py',(ROOT/'NOTICE.md').read_text())

    def test_source_package_metadata_includes_license_files(self):
        project=tomllib.loads((ROOT/'pyproject.toml').read_text())
        self.assertEqual(project['project']['license'],{'file':'LICENSE'})
        self.assertIn('licenses/*.txt',project['tool']['setuptools']['package-data']['vrhub'])
        manifest=(ROOT/'MANIFEST.in').read_text()
        self.assertIn('include LICENSE NOTICE.md',manifest)
        self.assertIn('recursive-include vrhub/licenses *.txt',manifest)
