# SPDX-License-Identifier: GPL-3.0-only
import ctypes as C
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock
from vrhub import steamvr_status as status, system_scan


class SteamVRStatusTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())) / "SteamVR"
        self.client = self.root / "bin/linux64/vrclient.so"
        self.client.parent.mkdir(parents=True)
        self.client.touch()
        (self.client.parent / "libopenvr_api.so").touch()

    def read(self):
        return status.read_status(None, str(self.client), server_observed=True)

    def test_no_server_never_calls_native_child(self):
        with patch.object(status.subprocess, "run") as run:
            self.assertIsNone(status.read_status(None, str(self.client))["connected"])
            run.assert_not_called()

    def test_bounded_child_and_exact_runtime_override(self):
        for connected in (True, False, None):
            value = dict(connected=connected, system_name="Quest" if connected else "", source=status.SOURCE, detail="fixture")
            with patch.object(status.subprocess, "run", return_value=Mock(returncode=0, stdout=json.dumps(value))) as run:
                self.assertEqual(self.read(), value)
                self.assertEqual(run.call_args.kwargs["timeout"], 2.5)
                self.assertEqual(run.call_args.kwargs["env"]["VR_OVERRIDE"], str(self.root))
                self.assertNotIn("VR_PATHREG_OVERRIDE", run.call_args.kwargs["env"])

    def test_failure_timeout_invalid_and_wrong_runtime_are_unknown(self):
        with patch.object(status.subprocess, "run", side_effect=subprocess.TimeoutExpired("fixture", 2.5)):
            self.assertIsNone(self.read()["connected"])
        for code, raw in ((-11, ""), (0, "garbage"), (0, '{"connected":true}')):
            with patch.object(status.subprocess, "run", return_value=Mock(returncode=code, stdout=raw)):
                self.assertIsNone(self.read()["connected"])
        with patch.object(status.subprocess, "run") as run:
            self.assertIsNone(status.read_status(None, str(self.root / "other.so"), server_observed=True)["connected"])
            run.assert_not_called()

    def test_native_background_interface_and_shutdown(self):
        table = (C.c_void_p * 29)()
        query = C.CFUNCTYPE(C.c_bool, C.c_uint32)(lambda index: index == 0)
        def model(index, prop, buf, size, error):
            self.assertEqual((index, prop), (0, 1001))
            C.memmove(buf, b"Quest fixture\0", 14)
            return 14
        prop = C.CFUNCTYPE(C.c_uint32, C.c_uint32, C.c_int, C.c_void_p, C.c_uint32, C.POINTER(C.c_int))(model)
        table[21] = C.cast(query, C.c_void_p).value
        table[28] = C.cast(prop, C.c_void_p).value
        api = Mock()
        api.VR_GetGenericInterface.return_value = C.addressof(table)
        with patch.object(status.C, "CDLL", return_value=api):
            value = status._query(self.client)
        self.assertTrue(value["connected"])
        self.assertEqual(value["system_name"], "Quest fixture")
        self.assertEqual(api.VR_InitInternal2.call_args.args[1], 3)
        self.assertEqual(api.VR_GetGenericInterface.call_args.args[0], b"FnTable:IVRSystem_026")
        api.VR_ShutdownInternal.assert_called_once()
        api.reset_mock()
        api.VR_GetGenericInterface.return_value = None
        with patch.object(status.C, "CDLL", return_value=api):
            self.assertIsNone(status._query(self.client)["connected"])
        api.VR_ShutdownInternal.assert_called_once()

    def test_scan_connection_evidence_and_stale_clear(self):
        with patch.object(system_scan, "_process_names", return_value={"vrserver"}) as processes:
            for connected in (True, False, None):
                with patch.object(status, "read_status", return_value=dict(connected=connected, system_name="Quest" if connected else "", source=status.SOURCE, detail="fixture")):
                    live, rows = system_scan._live_snapshot("SteamVR", True, None, str(self.client))
                self.assertIs(live["headset_connected"], connected)
                self.assertIs(live["headset_connection_verified"], connected is not None)
                self.assertFalse(live["controllers_verified"])
            processes.return_value = set()
            live, _ = system_scan._live_snapshot("SteamVR", True, None, str(self.client))
            self.assertEqual(live["activity"], "Idle")
            self.assertIsNone(live["headset_connected"])
