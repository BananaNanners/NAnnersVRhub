"""Real Qt threads and managed activation; synthetic releases, never gameplay evidence."""
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from tests import test_app_updates as fixtures
from vrhub import __version__, app_updates, self_install

QT = importlib.util.find_spec("PySide6") is not None
REPO = Path(__file__).resolve().parents[1]


@unittest.skipUnless(QT, "Optional PySide6 is not installed")
class QtUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from PySide6.QtWidgets import QWidget
        from vrhub.app_update_gui import HubUpdateController
        self.fixture = fixtures.UpdateTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)
        self.window = QWidget()
        self.controller = HubUpdateController(self.window)
        self.addCleanup(self.window.close)
        self.network = mock.patch.object(app_updates, "_open", side_effect=self.fixture.response)
        self.network.start()
        self.addCleanup(self.network.stop)

    def wait(self):
        deadline = time.monotonic() + 15
        while self.controller.busy and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.assertFalse(self.controller.busy, "Update worker did not stop")
        self.app.processEvents()

    def test_check_download_dialog_and_persistent_preferences(self):
        c = self.controller
        c.start("check", True)
        self.wait()
        c.show()
        self.assertIn("0.5.4", c.dialog.versions.text())
        self.assertEqual(c.dialog.notes.toPlainText(), self.fixture.metadata["body"])
        self.assertFalse(c.dialog.install.isEnabled())  # Source run.
        c.dialog.automatic.setChecked(True)
        self.assertTrue(app_updates.read_settings()["auto_download"])
        c.start("download", c.release)
        self.wait()
        self.assertTrue(c.dialog.folder.isEnabled())
        self.assertTrue(c.ready_for_release())
        c.dialog.close()

    def test_opt_in_download_after_check_and_no_automatic_install(self):
        c = self.controller
        c.preference("auto_download", True)
        with mock.patch.object(app_updates, "install_bundle", side_effect=AssertionError("must be explicit")):
            c.startup()
            self.wait()
        self.assertTrue(c.ready_for_release())
        self.assertFalse(c.installed)

    def test_disabled_startup_check_still_restores_saved_download_offline(self):
        self.fixture.download()
        c = self.controller
        c.preference("check_on_startup", False)
        with mock.patch.object(app_updates, "_open", side_effect=AssertionError("network must stay off")):
            c.startup()
            self.wait()
        self.assertTrue(c.ready_for_release())
        self.assertIsNotNone(c.checked_at)

    def test_failed_network_and_close_cancellation_leave_window_usable(self):
        c = self.controller
        with mock.patch.object(app_updates, "_open", side_effect=app_updates.UpdateError("offline")):
            c.start("check", True)
            self.wait()
        c.show()
        self.assertIn("offline", c.dialog.status.text())
        self.assertTrue(c.dialog.check.isEnabled())
        c.start("check", True)
        c.shutdown()
        self.wait()
        self.assertFalse(c.installed)
        c.dialog.close()

    def test_close_hub_waits_for_network_worker(self):
        from vrhub.gui import HubWindow
        entered, release = threading.Event(), threading.Event()
        def slow_response(url):
            entered.set()
            release.wait(2)
            return self.fixture.response(url)
        with mock.patch.object(HubWindow, "check_updates"), mock.patch.object(HubWindow, "scan_setup"), \
                mock.patch.object(app_updates, "_open", side_effect=slow_response):
            window = HubWindow()
            window.show()
            window.hub_updates.start("check", True)
            deadline = time.monotonic() + 5
            while not entered.is_set() and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(.005)
            self.assertTrue(entered.is_set())
            window.close()
            self.assertTrue(window.isVisible())
            release.set()
            while window.isVisible() and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(.005)
            self.assertFalse(window.isVisible())
            self.assertFalse(window.hub_updates.busy)

    def test_actual_managed_gui_upgrade_restart_command_and_rollback(self):
        fixture = self.fixture
        home = fixture.base / "Home with spaces $ and 100%"
        home.mkdir()
        root = home / "App Data/nannersvrhub"
        metadata = fixture.base / "release.json"
        metadata.write_text(json.dumps(fixture.metadata))
        (fixture.base / fixture.name).write_bytes(fixture.archive)
        (fixture.base / "SHA256SUMS").write_bytes(fixture.sums)
        env = {**os.environ, "HOME": str(home), "XDG_DATA_HOME": str(home / "App Data"), "QT_QPA_PLATFORM": "offscreen"}
        env.pop("_NANNERSVRHUB_ROOT", None)
        def run(*args):
            result = subprocess.run([str(x) for x in args], cwd=fixture.base, env=env, text=True, capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout
        run(sys.executable, REPO / "install.py")
        record = json.loads((root / "installation.json").read_text())
        first = record["current"]
        env["_NANNERSVRHUB_ROOT"] = str(root)
        probe = r'''
import io, json, os, sys, time
from pathlib import Path
from unittest import mock
sys.path.insert(0,sys.argv[1])
from PySide6.QtWidgets import QApplication, QMessageBox
from vrhub import __version__, app_updates, hub
from vrhub.gui import HubWindow
base=Path(sys.argv[2]); metadata=json.loads((base/'release.json').read_text())
class Response(io.BytesIO):
 status=200
 def __init__(self,data,url):
  super().__init__(data); self.url=url; self.headers={'Content-Length':str(len(data))}
 def geturl(self): return self.url
def response(url):
 data=json.dumps(metadata).encode() if url==app_updates.API else (base/url.rsplit('/',1)[-1]).read_bytes()
 return Response(data,url)
app_updates.save_settings(check_on_startup=False)
app=QApplication([])
with mock.patch.object(HubWindow,'check_updates'), mock.patch.object(HubWindow,'scan_setup'), mock.patch.object(app_updates,'_open',side_effect=response):
 w=HubWindow(); w.show(); c=w.hub_updates; c.show()
 def wait():
  deadline=time.monotonic()+35
  while c.busy and time.monotonic()<deadline:
   app.processEvents(); time.sleep(.005)
  assert not c.busy,c.message
  app.processEvents()
 assert w.table.rowCount()==9
 c.dialog.check.click(); wait()
 assert c.release['version']=='0.5.4',c.message
 c.dialog.download.click(); wait()
 assert c.dialog.install.isEnabled(),c.message
 with mock.patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):
  c.dialog.install.click()
 wait()
 assert c.installed,c.message
 assert __version__==sys.argv[3]  # Running process stays pinned.
 assert c.dialog.restart.isVisible()
 assert not c.dialog.install.isEnabled()
 with mock.patch('vrhub.app_update_gui.subprocess.Popen') as spawn:
  c.dialog.restart.click()
  assert spawn.call_args.args[0]==[str(Path(os.environ['_NANNERSVRHUB_ROOT'])/'bin/nannersvrhub')]
 assert not w.isVisible()
print('Real managed GUI: check -> download -> verify -> install -> restart: OK')
'''
        output = run(sys.executable, "-I", "-B", "-c", probe, root / "releases" / first, fixture.base, __version__)
        self.assertIn("restart: OK", output)
        self.assertIn("0.5.4", run(root / "bin/nannersvrhub", "--version"))
        self.assertIn("Fatekeeper", run(root / "bin/nannersvrhub", "info", "fatekeeper"))
        after = json.loads((root / "installation.json").read_text())
        self.assertEqual(after["previous"], first)
        run(root / "bin/nannersvrhub-manage", "rollback")
        self.assertIn(__version__, run(root / "bin/nannersvrhub", "--version"))
        run(root / "bin/nannersvrhub-manage", "rollback")
        self.assertIn("0.5.4", run(root / "bin/nannersvrhub", "--version"))
