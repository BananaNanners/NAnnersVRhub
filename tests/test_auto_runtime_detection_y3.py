# SPDX-License-Identifier: GPL-3.0-only
"""Dev5D3-Y3: automatic SteamVR / WiVRn selection observation, no switching."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtWidgets import QApplication
from vrhub import gui, runtime, system_scan
from vrhub.app_update_gui import HubUpdateController
from tests.manual_launcher_dev5d3y3_preview import PlayerFirstPreview


class RuntimeSwitchReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nanners-y3-runtime-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cfg = self.root/"config/openxr/1"
        self.cfg.mkdir(parents=True)
        self.selector = self.cfg/"active_runtime.json"
        self.steam = self.root/"SteamVR/steamxr_linux64.json"
        self.wivrn = self.root/"WiVRn/wivrn.json"
        self.steam.parent.mkdir(parents=True)
        self.wivrn.parent.mkdir(parents=True)
        self.steam.write_text(json.dumps({"file_format_version":"1.0.0",
                              "runtime":{"library_path":"libsteamxr.so"}}))
        self.wivrn.write_text(json.dumps({"file_format_version":"1.0.0",
                              "runtime":{"library_path":"libwivrn.so"}}))
        self.selector.symlink_to(self.steam)
        for patch in (
            mock.patch.dict(os.environ,{
                "XDG_CONFIG_HOME":str(self.root/"config"),
                "XR_RUNTIME_JSON":str(self.selector),
                "XDG_RUNTIME_DIR":str(self.root/"run")}),
            mock.patch.object(system_scan.ctypes.util,"find_library",return_value="fixture.so"),
            mock.patch.object(system_scan,"_process_names",return_value={"vrserver"}),
            mock.patch.object(system_scan.wivrn_status,"read_status",return_value={
                "connected":True,"system_name":"Synthetic headset",
                "source":"WiVRn D-Bus HeadsetConnected",
                "detail":"Fake status",
                "sampled_at":"fixture"}),
        ):
            patch.start();self.addCleanup(patch.stop)

    def select(self, target):
        self.selector.unlink()
        self.selector.symlink_to(target)

    def row(self, report, key):
        return next(row for row in report["rows"] if row["id"]==key)

    def test_seamless_steamvr_to_wivrn_and_back_without_start_or_change(self):
        with mock.patch.object(system_scan.wivrn_status,"read_status",wraps=system_scan.wivrn_status.read_status) as headset:
            before=self.selector.readlink()
            steam=system_scan.scan()
            self.assertEqual(steam["runtime"],"SteamVR")
            self.assertEqual(steam["selection_target"],str(self.steam))
            self.assertTrue(steam["live"]["server_running"])
            self.assertIsNone(steam["live"]["headset_connected"])
            self.assertIn("SteamVR",self.row(steam,"headset")["detail"])
            self.assertIn("SteamVR server-process observation",steam["scope"])
            headset.assert_not_called()
            self.assertEqual(self.selector.readlink(),before)
            self.select(self.wivrn)
            with mock.patch.object(system_scan,"_process_names",return_value={"wivrn-server"}):
                current=system_scan.refresh_live(steam)
            self.assertEqual(current["runtime"],"WiVRn")
            self.assertEqual(current["selection_target"],str(self.wivrn))
            self.assertTrue(current["live"]["headset_connected"])
            self.assertTrue(current["live"]["server_running"])
            self.assertIn("WiVRn headset connection telemetry",current["scope"])
            headset.assert_called_once()
            self.select(self.steam)
            back=system_scan.refresh_live(current)
            self.assertEqual(back["runtime"],"SteamVR")
            self.assertIsNone(back["live"]["headset_connected"])
            self.assertIs(back["live"]["headset_connection_verified"],False)
            self.assertFalse(back["live"]["controllers_verified"])
            self.assertEqual(self.selector.readlink(),self.steam)

    def test_same_library_but_new_manifest_target_forces_rescan(self):
        second=self.root/"Alternate/steamvr.json"
        second.parent.mkdir()
        second.write_bytes(self.steam.read_bytes())
        first=system_scan.scan()
        self.select(second)
        with mock.patch.object(system_scan,"scan",wraps=system_scan.scan) as rescan:
            refreshed=system_scan.refresh_live(first)
        rescan.assert_called_once()
        self.assertEqual(refreshed["selection_target"],str(second))
        self.assertEqual(refreshed["runtime"],"SteamVR")
        self.assertEqual(refreshed["selection"],first["selection"])

    def test_same_selection_only_refreshes_live_and_never_launches(self):
        initial=system_scan.scan()
        with mock.patch.object(system_scan,"scan",side_effect=AssertionError("full rescan")):
            updated=system_scan.refresh_live(initial)
        self.assertEqual(updated["runtime"],"SteamVR")
        self.assertEqual(updated["scanned_at"],initial["scanned_at"])
        self.assertEqual(updated["selection_target"],initial["selection_target"])

    def test_missing_runtime_becomes_unconfigured_without_wivrn_probe(self):
        previous=system_scan.scan()
        self.selector.unlink()
        with mock.patch.object(system_scan.wivrn_status,"read_status",
                               side_effect=AssertionError("no WiVRn telemetry")):
            report=system_scan.refresh_live(previous)
        self.assertEqual(report["runtime"],"Not configured")
        self.assertEqual(report["status"],"NOT READY")
        self.assertFalse(report["live"]["runtime_selected"])
        self.assertIsNone(report["live"]["headset_connected"])

    def test_readonly_scanner_never_modifies_symlinks_or_opens_xr(self):
        previous=(self.steam.read_bytes(),self.wivrn.read_bytes(),self.selector.readlink())
        with mock.patch("subprocess.Popen",side_effect=AssertionError("must not launch")):
            result=system_scan.scan()
            system_scan.refresh_live(result)
        self.assertEqual(previous,(self.steam.read_bytes(),self.wivrn.read_bytes(),self.selector.readlink()))


class RuntimeSwitchDashboardQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_display_distinguishes_selection_and_runtime_process_and_stale_headset(self):
        with (mock.patch.object(gui.HubWindow,"scan_setup",lambda *a,**k:None),
              mock.patch.object(gui.HubWindow,"check_updates",lambda *a,**k:None),
              mock.patch.object(HubUpdateController,"startup",lambda *a,**k:None)):
            win=PlayerFirstPreview()
            self.addCleanup(win.close)
            win.show()
            sample=system_scan.scan()
            sample["status"]="HOST CHECKS PASSED"
            sample["runtime"]="SteamVR"
            sample["live"]=dict(sample["live"], runtime_selected=True,
                                server_running=False,headset_connected=None)
            win.show_system_report(sample)
            self.assertIn("SteamVR SELECTED",win.runtime_state.text())
            self.assertEqual(win.server_state.text(),"Server: NOT OBSERVED")
            self.assertEqual(win.headset_state.text(),"Headset: UNKNOWN")
            self.assertIn("OpenXR: SteamVR selected",win.scan_summary.text())
            self.assertIn("0.5.5-dev5D3y3",__import__("vrhub.system_scan",fromlist=["report_text"]).report_text(win.scan_report))
            other=copy.deepcopy(sample)
            other["runtime"]="WiVRn"
            other["live"].update(server_running=True,headset_connected=True)
            win.show_system_report(other)
            self.assertIn("WiVRn SELECTED",win.runtime_state.text())
            self.assertEqual(win.server_state.text(),"Server: RUNNING")
            self.assertEqual(win.headset_state.text(),"Headset: CONNECTED")
            self.assertFalse(win.save_scan_btn.isEnabled())
            self.assertFalse(win.allow_guided_installs)
