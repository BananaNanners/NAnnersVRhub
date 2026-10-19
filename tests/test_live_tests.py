from concurrent.futures import ThreadPoolExecutor
import contextlib
import copy
from datetime import datetime
import io
import json
from pathlib import Path
import unittest
from unittest import mock

from vrhub import cli, compatibility, hub, live_tests
from tests import test_workflow_compatibility as fixtures


class LocalTestHistoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SteamWorkflowCompatibilityTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.recipe, self.game, self.prefix, self.pak = self.fixture.ready_or_not()
        self.roots = [self.fixture.steam]

    def snapshot(self):
        return compatibility.report(self.recipe, self.roots)

    def save(self, result='partial', notes='VR works, HUD disabled; stereo depth not tested.', checks=None):
        return live_tests.record(self.recipe, result, notes,
                                 checks or {'vr_rendering':'passed','head_tracking':'passed'},self.snapshot())

    def test_reading_empty_history_creates_nothing_and_does_not_import_bundled_tests(self):
        before = list(self.fixture.home.rglob('*'))
        self.assertEqual(live_tests.history(self.recipe['id']),[])
        report=self.snapshot()
        self.assertIsNone(report['local_test'])
        self.assertIn('USER-REPORTED LIVE TEST',compatibility.report_text(report))
        self.assertIn('Local gameplay test: NOT RECORDED',compatibility.report_text(report))
        self.assertEqual(before,list(self.fixture.home.rglob('*')))

    def test_record_round_trip_has_explicit_result_notes_and_aware_dates(self):
        entry=self.save()
        loaded=live_tests.history(self.recipe['id'])[0]
        self.assertEqual(entry,loaded)
        self.assertEqual(loaded['outcome'],'partial')
        self.assertIn('HUD disabled',loaded['notes'])
        self.assertIsNotNone(datetime.fromisoformat(loaded['recorded_at']).utcoffset())
        self.assertEqual(datetime.fromisoformat(loaded['recorded_at']),datetime.fromisoformat(loaded['recorded_at_utc']))
        self.assertEqual(loaded['checks']['controller_input'],'not-tested')
        self.assertEqual(loaded['checks']['stereo_depth'],'not-tested')

    def test_success_requires_passed_rendering_and_no_explicit_failed_check(self):
        for checks in ({}, {'vr_rendering':'not-tested'}, {'vr_rendering':'passed','controller_input':'failed'}):
            with self.subTest(checks=checks),self.assertRaises(RuntimeError):
                live_tests.record(self.recipe,'success','',checks,self.snapshot())
        self.assertFalse(live_tests.history_file().exists())
        self.save('success','',{'vr_rendering':'passed'})
        self.assertEqual(live_tests.history(self.recipe['id'])[0]['checks']['stereo_depth'],'not-tested')

    def test_partial_and_failure_require_notes(self):
        for result in ('partial','failure'):
            with self.subTest(result=result),self.assertRaisesRegex(RuntimeError,'Describe'):
                self.save(result,'   ')
        self.assertFalse(live_tests.history_file().exists())

    def test_invalid_input_does_not_write_history(self):
        report=self.snapshot()
        cases=[('invalid','text',{}),('partial','text',{'unknown':'passed'}),
               ('partial','text',{'vr_rendering':'maybe'}),('partial','x'*4001,{})]
        for outcome,notes,checks in cases:
            with self.subTest(outcome=outcome),self.assertRaises(RuntimeError):
                live_tests.record(self.recipe,outcome,notes,checks,report)
        self.assertFalse(live_tests.history_file().exists())

    def test_history_appends_and_latest_failure_is_prominent(self):
        first=self.save('success','First run worked',{'vr_rendering':'passed'})
        second=self.save('failure','Crash after loading',{'vr_rendering':'failed'})
        entries=live_tests.history(self.recipe['id'])
        self.assertEqual([r['id'] for r in entries],[second['id'],first['id']])
        text=compatibility.report_text(self.snapshot())
        self.assertLess(text.index('Local gameplay test: FAILURE'),text.index('Bundled compatibility reference:'))
        self.assertIn('Crash after loading',text)
        self.assertEqual(self.snapshot()['local_test_count'],2)

    def test_games_have_independent_local_histories(self):
        self.save()
        self.assertEqual(live_tests.history('fatekeeper'),[])
        recipe,_,_,_=self.fixture.fatekeeper()
        report=compatibility.report(recipe,self.roots)
        live_tests.record(recipe,'failure','Injector did not open',{'vr_rendering':'failed'},report)
        self.assertEqual(live_tests.history(self.recipe['id'])[0]['outcome'],'partial')
        self.assertEqual(live_tests.history('fatekeeper')[0]['outcome'],'failure')

    def test_save_never_modifies_installer_state_or_recipes(self):
        before=self.fixture.state.read_bytes()
        recipe=copy.deepcopy(self.recipe)
        self.save()
        self.assertEqual(self.fixture.state.read_bytes(),before)
        self.assertEqual(self.recipe,recipe)
        self.assertNotEqual(live_tests.history_file(),self.fixture.state)

    def test_setup_snapshot_stays_historical_after_files_change(self):
        entry=self.save()
        saved=copy.deepcopy(entry['setup'])
        self.pak.unlink()
        report=self.snapshot()
        self.assertEqual(report['status'],'NOT READY')
        self.assertEqual(report['local_test']['setup'],saved)
        self.assertEqual(saved['local_status'],'REVIEW REQUIRED')

    def test_saved_result_cannot_turn_failed_configuration_checks_green(self):
        self.pak.unlink()
        entry=self.save('success','Reporting an earlier session',{'vr_rendering':'passed'})
        self.assertEqual(entry['outcome'],'success')
        self.assertEqual(self.snapshot()['status'],'NOT READY')

    def test_failed_result_cannot_rewrite_bundled_gameplay_reference(self):
        before=copy.deepcopy(self.recipe['compatibility'])
        self.save('failure','No image',{'vr_rendering':'failed'})
        self.assertEqual(self.recipe['compatibility'],before)
        self.assertEqual(self.snapshot()['profile']['validation'],'user-reported')
        self.assertEqual(self.snapshot()['status'],'REVIEW REQUIRED')

    def test_damaged_history_is_visible_and_never_overwritten(self):
        path=live_tests.history_file();path.write_text('{broken')
        report=self.snapshot()
        self.assertTrue(report['local_test_error'])
        self.assertIn('history unavailable',compatibility.report_text(report))
        with self.assertRaises(RuntimeError):self.save()
        self.assertEqual(path.read_text(),'{broken')

    def test_unknown_schema_and_malformed_record_are_preserved(self):
        for data in ({'schema_version':2,'games':{}}, {'schema_version':1,'games':{'ready-or-not':[{}]}}):
            path=live_tests.history_file();path.write_text(json.dumps(data))
            before=path.read_bytes()
            with self.assertRaises(RuntimeError):live_tests.history(self.recipe['id'])
            with self.assertRaises(RuntimeError):self.save()
            self.assertEqual(path.read_bytes(),before)

    def test_atomic_replace_failure_preserves_previous_history(self):
        self.save();before=live_tests.history_file().read_bytes()
        with mock.patch('vrhub.live_tests.os.replace',side_effect=OSError('simulated write failure')):
            with self.assertRaises(OSError):self.save()
        self.assertEqual(live_tests.history_file().read_bytes(),before)
        self.assertEqual(list(live_tests.history_file().parent.glob('.live-tests-*.tmp')),[])

    def test_concurrent_writers_preserve_all_records(self):
        snapshot=self.snapshot()
        def write(index):
            return live_tests.record(self.recipe,'partial',f'Run {index}',{'vr_rendering':'passed'},snapshot)['id']
        with ThreadPoolExecutor(max_workers=6) as pool:ids=list(pool.map(write,range(18)))
        loaded=live_tests.history(self.recipe['id'])
        self.assertEqual(len(loaded),18)
        self.assertEqual({r['id'] for r in loaded},set(ids))

    def test_file_is_private_and_reader_sees_new_file_without_cache(self):
        self.save()
        self.assertEqual(live_tests.history_file().stat().st_mode & 0o777,0o600)
        self.save('failure','New session failed',{'vr_rendering':'failed'})
        self.assertEqual(self.snapshot()['local_test']['outcome'],'failure')

    def test_notes_are_escaped_in_gui_and_copied_as_literal_text(self):
        self.save(notes='<script>unsafe & text</script>')
        report=self.snapshot()
        self.assertIn('<script>',compatibility.report_text(report))
        html=compatibility.report_html(report)
        self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;',html)

    def test_record_rejects_another_games_snapshot(self):
        report=self.snapshot();report['recipe_id']='fatekeeper'
        with self.assertRaisesRegex(RuntimeError,'another game'):
            live_tests.record(self.recipe,'partial','Test',{},report)
        self.assertFalse(live_tests.history_file().exists())

    def test_cli_save_history_json_and_diagnostics(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            result=cli.main(['record-test','ready-or-not','--result','partial','--vr-rendering','passed',
                             '--head-tracking','passed','--notes','Works with limitation','--json'])
        self.assertEqual(result,0)
        self.assertEqual(json.loads(output.getvalue())['outcome'],'partial')
        output=io.StringIO()
        with contextlib.redirect_stdout(output):result=cli.main(['test-history','ready-or-not','--json'])
        self.assertEqual(result,0)
        self.assertEqual(len(json.loads(output.getvalue())['records']),1)
        self.assertIn('Works with limitation',hub.diagnostics(self.recipe,self.roots))

    def test_cli_invalid_success_does_not_write(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(['record-test','ready-or-not','--result','success']),1)
        self.assertFalse(live_tests.history_file().exists())

    def test_history_text_identifies_game_and_keeps_not_tested_fields(self):
        self.save()
        text=live_tests.history_text(self.recipe,live_tests.history(self.recipe['id']))
        self.assertIn('Ready or Not',text)
        self.assertIn('ready-or-not',text)
        self.assertIn('Stereo depth: NOT TESTED',text)
        self.assertIn('historical snapshot',text)

    def test_cyberpunk_workaround_snapshot_survives_local_success(self):
        recipe,_,_=self.fixture.cyberpunk()
        report=compatibility.report(recipe,self.roots)
        entry=live_tests.record(recipe,'success','Immersion works with HUD panels disabled',{'vr_rendering':'passed'},report)
        self.assertEqual(len(entry['setup']['profile_workarounds']),4)
        updated=compatibility.report(recipe,self.roots)
        self.assertIn('WORKAROUND REQUIRED',compatibility.report_text(updated))
        self.assertEqual(updated['local_test']['checks']['stereo_depth'],'not-tested')


if __name__=='__main__':unittest.main()
