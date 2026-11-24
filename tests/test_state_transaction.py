# SPDX-License-Identifier: GPL-3.0-only
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from threading import Thread
from unittest.mock import patch

from vrhub import hub, pak, bepinex, profile_safety, state_transaction, fatekeeper_commit


class StateTransactionTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix='nanners-fk4-', dir='/tmp')))
        self.state = self.root / 'state.json'
        self.state.write_text('{"other": {"installed_at": 1}}')
        self.enterContext(patch.object(hub, 'state_file', return_value=self.state))

    def test_nested_dispatch_and_separate_state(self):
        with state_transaction.locked(self.state):
            with hub._gameroot_lock(), state_transaction.locked(self.state):
                with state_transaction.locked(self.root / 'other.json'):
                    pass
        with state_transaction.locked(self.state):
            pass

    def test_other_process_cannot_enter_any_handler_while_fatekeeper_locked(self):
        before = self.state.read_bytes()
        code = '''import sys
from pathlib import Path
from vrhub import hub, pak, bepinex, profile_safety, state_transaction
from unittest.mock import patch
with patch.object(hub,'state_file',return_value=Path(sys.argv[1])):
 for factory in (hub._gameroot_lock,pak._locked,bepinex.locked,profile_safety._lock):
  try:
   with factory(): raise AssertionError('entered competing handler')
  except RuntimeError as e: assert 'Another Hub' in str(e),e
 try: hub.mark_current({'id':'other'})
 except RuntimeError as e: assert 'Another Hub' in str(e),e
 else: raise AssertionError('state writer entered')
'''
        with fatekeeper_commit._locked(fatekeeper_commit._fixture_destination(self.root)):
            result = subprocess.run([sys.executable, '-B', '-c', code, str(self.state)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.state.read_bytes(), before)
        self.assertEqual(hub.mark_current({'id':'other'}), ['other'])

    def test_other_thread_cannot_enter_and_lock_released_on_error(self):
        errors = []
        def worker():
            try:
                with pak._locked(): errors.append('entered')
            except RuntimeError as exc: errors.append(str(exc))
        with self.assertRaisesRegex(ValueError, 'abort'):
            with bepinex.locked():
                t=Thread(target=worker); t.start(); t.join(5)
                self.assertFalse(t.is_alive())
                self.assertEqual(len(errors), 1)
                self.assertIn('Another Hub', errors[0])
                raise ValueError('abort')
        with pak._locked(): pass

    def test_symlink_lock_refused(self):
        target=self.root/'unrelated'; target.write_bytes(b'preserve')
        (self.root/'.state.json.transaction.lock').symlink_to(target)
        with self.assertRaises(OSError):
            with state_transaction.locked(self.state): pass
        self.assertEqual(target.read_bytes(), b'preserve')
