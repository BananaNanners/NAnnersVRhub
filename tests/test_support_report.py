import contextlib
import copy
from datetime import datetime
import io
import json
from pathlib import Path
import unittest
from unittest import mock

from vrhub import cli, compatibility, live_tests, support_report
from tests import test_workflow_compatibility as fixtures


class SupportReportTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SteamWorkflowCompatibilityTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.recipe, self.game, self.prefix = self.fixture.cyberpunk()
        self.roots = [self.fixture.steam]
        self.log = self.fixture.file(self.game/'bin/x64/cyberpunkvrport.log')
        self.log.write_text('OpenXRManager: xrEndFrame mono submit failed (res=-39) private-marker\n')
        self.system = dict(schema_version=2,hub_version='fixture',scanned_at='2026-10-18T01:00:00+00:00',
                           status='HOST CHECKS PASSED',runtime='WiVRn',hardware_verified=False,rows=[],
                           live={'sampled_at':'2026-10-18T01:00:01+00:00','headset_connected':True,
                                 'headset_name':'Quest fixture','controllers_verified':False},
                           environment={},scope='Fixture host scan; gameplay unverified.')
        patch = mock.patch('vrhub.support_report.system_scan.scan',side_effect=lambda:copy.deepcopy(self.system))
        self.scan = patch.start()
        self.addCleanup(patch.stop)

    def collect(self, files=None):
        return support_report.collect(self.recipe,self.roots,files)

    def view(self, **kwargs):
        return support_report.export_view(self.collect(),**kwargs)

    def save_test(self,outcome='partial',notes='VR works with HUD panels off; game menu causes passthrough.'):
        return live_tests.record(self.recipe,outcome,notes,{'vr_rendering':'passed'},compatibility.report(self.recipe,self.roots))

    def test_four_sections_keep_timestamps_and_distinct_evidence(self):
        entry = self.save_test()
        snapshot = self.collect()
        self.assertEqual(snapshot['schema_version'],1)
        self.assertEqual(snapshot['collection_status'],'COMPLETE')
        self.assertIsNotNone(datetime.fromisoformat(snapshot['collection_started_at']).utcoffset())
        self.assertEqual(set(snapshot['sections']),{'system','compatibility','logs','gameplay'})
        sections=snapshot['sections']
        self.assertEqual(sections['system']['data']['scanned_at'],self.system['scanned_at'])
        self.assertEqual(sections['gameplay']['data']['latest_test']['id'],entry['id'])
        self.assertEqual(sections['compatibility']['data']['status'],'REVIEW REQUIRED')
        self.assertEqual(sections['logs']['data']['status'],'RECOGNIZED LOG EVIDENCE')
        self.assertFalse(sections['system']['data']['live']['controllers_verified'])
        text=support_report.report_text(support_report.export_view(snapshot))
        for label in ('1. VR system scan','2. Game compatibility','3. Game log evidence','4. Latest local gameplay test'):
            self.assertIn(label,text)
        self.assertEqual(text.count('Local gameplay test: PARTIAL SUCCESS'),1)
        self.assertIn('not a gameplay verdict',text)
        self.assertIn('historical snapshot',text)

    def test_empty_history_does_not_import_bundled_success(self):
        snapshot=self.collect()
        self.assertIsNone(snapshot['sections']['gameplay']['data']['latest_test'])
        self.assertEqual(snapshot['sections']['gameplay']['data']['record_count'],0)
        self.assertFalse(live_tests.history_file().exists())
        self.assertIn('No local gameplay tests recorded',support_report.report_text(support_report.export_view(snapshot)))

    def test_latest_failure_is_preserved_alongside_successful_reference(self):
        self.save_test('success','Earlier session worked.')
        failed=self.save_test('failure','Current session shows passthrough.')
        snapshot=self.collect()
        entry=snapshot['sections']['gameplay']['data']['latest_test']
        self.assertEqual(entry['id'],failed['id'])
        self.assertEqual(entry['outcome'],'failure')
        self.assertEqual(snapshot['sections']['gameplay']['data']['record_count'],2)
        self.assertEqual(snapshot['sections']['compatibility']['data']['status'],'REVIEW REQUIRED')

    def test_only_selected_games_latest_test_is_collected(self):
        self.save_test()
        other=self.fixture.recipes['ready-or-not']
        snapshot=support_report.collect(other,self.roots)
        self.assertIsNone(snapshot['sections']['gameplay']['data']['latest_test'])
        self.assertEqual(snapshot['recipe_id'],'ready-or-not')
        self.assertEqual(snapshot['sections']['logs']['data']['logs'],[])

    def test_recollect_is_fresh_while_exported_snapshot_remains_historical(self):
        first=self.collect()
        before=copy.deepcopy(first)
        self.log.write_text('xrEndFrame failed: XR_ERROR_VALIDATION_FAILURE')
        self.save_test('failure','New test failed.')
        second=self.collect()
        self.assertEqual(self.scan.call_count,2)
        self.assertEqual(first,before)
        self.assertEqual(second['sections']['logs']['data']['logs'][0]['findings'][0]['id'],'xr-validation-failure')
        self.assertEqual(second['sections']['gameplay']['data']['latest_test']['outcome'],'failure')
        self.assertIsNone(first['sections']['gameplay']['data']['latest_test'])

    def test_snapshot_is_detached_from_mutable_recipe_data(self):
        snapshot=self.collect()
        before=copy.deepcopy(snapshot['sections']['compatibility']['data']['profile'])
        self.recipe['compatibility']['notes'].append('Later recipe change')
        self.assertEqual(snapshot['sections']['compatibility']['data']['profile'],before)

    def test_failed_source_does_not_hide_other_sections(self):
        with mock.patch('vrhub.support_report.system_scan.scan',side_effect=OSError('host probe failed')):
            snapshot=self.collect()
        self.assertEqual(snapshot['collection_status'],'PARTIAL')
        self.assertEqual(snapshot['sections']['system']['availability'],'UNAVAILABLE')
        self.assertIn('host probe failed',snapshot['sections']['system']['error'])
        for key in ('compatibility','logs','gameplay'):
            self.assertEqual(snapshot['sections'][key]['availability'],'AVAILABLE')
        self.assertIn('Unavailable: OSError:',support_report.report_text(support_report.export_view(snapshot)))

    def test_failed_compatibility_still_reads_gameplay_history(self):
        entry=self.save_test()
        with mock.patch('vrhub.support_report.compatibility.report',side_effect=RuntimeError('config failed')):
            snapshot=self.collect()
        self.assertEqual(snapshot['collection_status'],'PARTIAL')
        self.assertEqual(snapshot['sections']['gameplay']['data']['latest_test']['id'],entry['id'])

    def test_corrupt_history_remains_visible_and_preserved(self):
        path=live_tests.history_file()
        path.write_text('{broken history')
        snapshot=self.collect()
        self.assertEqual(snapshot['collection_status'],'PARTIAL')
        self.assertEqual(snapshot['sections']['gameplay']['availability'],'UNAVAILABLE')
        self.assertEqual(snapshot['sections']['compatibility']['availability'],'AVAILABLE')
        self.assertEqual(path.read_text(),'{broken history')

    def test_log_exception_and_missing_log_are_distinguished(self):
        with mock.patch('vrhub.support_report.log_diagnostics.report',side_effect=OSError('read failed')):
            snapshot=self.collect()
        self.assertEqual(snapshot['sections']['logs']['availability'],'UNAVAILABLE')
        self.log.unlink()
        snapshot=self.collect()
        self.assertEqual(snapshot['sections']['logs']['availability'],'AVAILABLE')
        self.assertEqual(snapshot['sections']['logs']['data']['status'],'NO READABLE LOG EVIDENCE')
        self.assertEqual(snapshot['collection_status'],'COMPLETE')

    def test_manual_logs_replace_auto_and_invalid_count_does_not_scan(self):
        manual=self.fixture.file(self.fixture.home/'manual.txt')
        manual.write_text('xrEndFrame failed: XR_ERROR_VALIDATION_FAILURE')
        snapshot=self.collect([manual])
        item=snapshot['sections']['logs']['data']['logs'][0]
        self.assertEqual(item['path'],str(manual))
        self.assertEqual(item['selection'],'user-selected')
        self.scan.reset_mock()
        for files in ([],[manual]*5):
            with self.assertRaises(RuntimeError):self.collect(files)
        self.scan.assert_not_called()

    def test_default_home_replacement_is_recursive_and_keeps_sibling_homes(self):
        snapshot=self.collect()
        snapshot['sections']['system']['data']['environment']={'VR_OVERRIDE':'/home/tester/adapter'}
        snapshot['sections']['system']['data']['live']['headset_name']='device at /home/tester'
        snapshot['sections']['logs']['error']='also /home/tester2/sibling Z:\\home\\tester\\logs'
        with mock.patch('vrhub.support_report.Path.home',return_value=Path('/home/tester')):
            view=support_report.export_view(snapshot)
        self.assertEqual(view['sections']['system']['data']['environment']['VR_OVERRIDE'],'~/adapter')
        self.assertEqual(view['sections']['system']['data']['live']['headset_name'],'device at ~')
        self.assertEqual(view['sections']['logs']['error'],'also /home/tester2/sibling Z:~\\logs')
        self.assertEqual(snapshot['sections']['system']['data']['environment']['VR_OVERRIDE'],'/home/tester/adapter')

    def test_unredacted_export_is_explicit_and_does_not_mutate_snapshot(self):
        snapshot=self.collect();before=copy.deepcopy(snapshot)
        with mock.patch('vrhub.support_report.Path.home',return_value=self.fixture.home):
            redacted=support_report.export_view(snapshot)
            full=support_report.export_view(snapshot,replace_home=False)
        self.assertNotIn(str(self.fixture.home),json.dumps(redacted))
        self.assertIn(str(self.fixture.home),json.dumps(full))
        self.assertEqual(snapshot,before)

    def test_excerpt_omission_keeps_counts_actions_and_source_metadata(self):
        snapshot=self.collect()
        view=support_report.export_view(snapshot,include_excerpts=False)
        log=view['sections']['logs']['data']['logs'][0]
        self.assertEqual(log['findings'][0]['excerpts'],[])
        self.assertEqual(log['findings'][0]['count'],1)
        self.assertTrue(log['findings'][0]['action'])
        self.assertEqual(log['modified_at'],snapshot['sections']['logs']['data']['logs'][0]['modified_at'])
        self.assertNotIn('private-marker',support_report.serialize(view))
        self.assertNotIn('private-marker',support_report.serialize(view,True))
        self.assertIn('private-marker',support_report.serialize(support_report.export_view(snapshot)))

    def test_output_is_literal_text_and_json_round_trips(self):
        self.save_test(notes='Literal <script> & notes\x1b[31m\x07')
        view=self.view()
        text=support_report.serialize(view)
        self.assertIn('Literal <script> & notes',text)
        self.assertNotIn('\x1b',text)
        self.assertNotIn('\x07',text)
        self.assertEqual(json.loads(support_report.serialize(view,True)),view)

    def test_collection_and_preview_change_no_files_and_create_no_history(self):
        before={p:p.read_bytes() for p in self.fixture.home.rglob('*') if p.is_file()}
        self.view()
        after={p:p.read_bytes() for p in self.fixture.home.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
        self.assertFalse(live_tests.history_file().exists())

    def test_save_matches_preview_for_text_and_json_and_uses_private_permissions(self):
        view=self.view(include_excerpts=False)
        for json_format in (False,True):
            path=self.fixture.home/('support.json' if json_format else 'support.txt')
            support_report.save(path,view,json_format)
            self.assertEqual(path.read_text(),support_report.serialize(view,json_format))
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertEqual(list(self.fixture.home.glob('.vrhub-support-*')),[])

    def test_existing_destination_and_symlink_are_preserved(self):
        view=self.view()
        path=self.fixture.home/'existing.txt';path.write_text('keep this')
        with self.assertRaises(FileExistsError):support_report.save(path,view)
        link=self.fixture.home/'link.txt';link.symlink_to(path)
        with self.assertRaises(FileExistsError):support_report.save(link,view)
        self.assertEqual(path.read_text(),'keep this')
        self.assertTrue(link.is_symlink())
        self.assertEqual(list(self.fixture.home.glob('.vrhub-support-*')),[])

    def test_failed_save_cleans_temporary_and_creates_no_partial_destination(self):
        target=self.fixture.home/'failed.txt'
        with mock.patch('vrhub.support_report.os.link',side_effect=OSError('simulated failure')):
            with self.assertRaises(OSError):support_report.save(target,self.view())
        self.assertFalse(target.exists())
        self.assertEqual(list(self.fixture.home.glob('.vrhub-support-*')),[])

    def test_cli_json_output_matches_saved_file_with_options(self):
        target=self.fixture.home/'cli-report.json'
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            result=cli.main(['support-report','cyberpunk-2077','--json','--no-excerpts','--output',str(target)])
        self.assertEqual(result,0)
        self.assertEqual(output.getvalue(),target.read_text())
        rep=json.loads(output.getvalue())
        self.assertFalse(rep['export_options']['include_log_excerpts'])
        self.assertEqual(rep['recipe_id'],'cyberpunk-2077')
        self.assertNotIn('private-marker',output.getvalue())

    def test_cli_partial_exit_preserves_usable_report_and_existing_output_is_not_overwritten(self):
        output=io.StringIO()
        with mock.patch('vrhub.support_report.system_scan.scan',side_effect=OSError('probe failed')),contextlib.redirect_stdout(output):
            self.assertEqual(cli.main(['support-report','cyberpunk-2077']),1)
        self.assertIn('3. Game log evidence',output.getvalue())
        existing=self.fixture.home/'keep.txt';existing.write_text('keep')
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(['support-report','cyberpunk-2077','--output',str(existing)]),1)
        self.assertEqual(existing.read_text(),'keep')

    def test_fatekeeper_confirmed_insert_workaround_is_in_profile_without_rewriting_reference(self):
        recipe=self.fixture.recipes['fatekeeper']
        workarounds=' '.join(recipe['compatibility']['workarounds'])
        self.assertIn('2D Screen Mode OFF',workarounds)
        self.assertIn('Insert',workarounds)
        self.assertIn('WayVR',workarounds)
        self.assertEqual(recipe['compatibility']['reference']['tested_on'],'2026-10-17')


if __name__=='__main__':
    unittest.main()
