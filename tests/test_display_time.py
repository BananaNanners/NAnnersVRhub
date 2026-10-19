from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import unittest
from unittest import mock

from vrhub import compatibility, display_time, live_tests, log_diagnostics, support_report, system_scan
from tests import test_workflow_compatibility as fixtures


@contextmanager
def local_zone(name):
    # Exercise the real system-local conversion without changing machine settings.
    previous = os.environ.get('TZ')
    os.environ['TZ'] = name
    time.tzset()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop('TZ', None)
        else:
            os.environ['TZ'] = previous
        time.tzset()


class DisplayTimeTests(unittest.TestCase):
    def test_user_reported_utc_timestamp_displays_24_hour_pdt(self):
        with local_zone('America/Los_Angeles'):
            self.assertEqual(display_time.local_time('2026-10-18T23:43:28.596274+00:00'),
                             '2026-10-18 16:43:28 PDT')

    def test_conversion_uses_timestamp_date_for_dst_and_day_rollover(self):
        with local_zone('America/Los_Angeles'):
            self.assertEqual(display_time.local_time('2026-01-02T01:10:00Z'),'2026-01-01 17:10:00 PST')
            self.assertEqual(display_time.local_time('2026-07-02T01:10:00Z'),'2026-07-01 18:10:00 PDT')

    def test_repeated_dst_hour_has_distinct_zone_labels(self):
        with local_zone('America/Los_Angeles'):
            self.assertEqual(display_time.local_time('2026-11-01T08:30:00Z'),'2026-11-01 01:30:00 PDT')
            self.assertEqual(display_time.local_time('2026-11-01T09:30:00Z'),'2026-11-01 01:30:00 PST')

    def test_system_zone_is_used_instead_of_hardcoded_los_angeles(self):
        with local_zone('Asia/Tokyo'):
            self.assertEqual(display_time.local_time('2026-10-18T23:43:28Z'),'2026-10-19 08:43:28 JST')

    def test_naive_timestamp_is_not_assumed_to_have_a_zone(self):
        with local_zone('America/Los_Angeles'):
            self.assertEqual(display_time.local_time('2026-10-18 16:11:14.485'),
                             '2026-10-18 16:11:14 (timezone not recorded)')

    def test_unknown_invalid_timestamps_and_dates_remain_explicit(self):
        for value in (None, ''):
            self.assertIn('not recorded',display_time.local_time(value))
        for value in ('not-a-time','2026-99-99T10:00:00Z',42):
            self.assertIn('invalid timestamp',display_time.local_time(value))
        self.assertIn('timezone not recorded',display_time.local_time('2026-10-18'))

    def test_age_is_computed_without_guessing_a_naive_timezone(self):
        now=datetime(2026,10,18,23,44,0,tzinfo=timezone.utc)
        self.assertEqual(display_time.age_text('2026-10-18T23:43:28Z',now),'32s old')
        self.assertEqual(display_time.age_text('2026-10-18T23:40:00Z',now),'4m 0s old')
        self.assertEqual(display_time.age_text('2026-10-18T21:40:00Z',now),'2h 4m old')
        self.assertEqual(display_time.age_text('2026-10-18T23:45:00Z',now),'timestamp is in the future')
        self.assertEqual(display_time.age_text('2026-10-18 23:43:28',now),'age unknown')

    def test_filename_uses_local_zone_and_safe_characters(self):
        with local_zone('America/Los_Angeles'):
            self.assertEqual(display_time.filename_stamp('2026-10-18T23:43:28Z'),'2026-10-18_16-43-28_PDT')
        self.assertEqual(display_time.filename_stamp(None),'undated')


class ReportPresentationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.SteamWorkflowCompatibilityTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.recipe,self.game,self.prefix=self.fixture.cyberpunk()
        self.roots=[self.fixture.steam]
        self.path=self.fixture.file(self.game/'bin/x64/cyberpunkvrport.log')

    def log_report(self,text):
        self.path.write_text(text)
        return log_diagnostics.report(self.recipe,self.roots,now=datetime(2026,10,18,23,43,28,tzinfo=timezone.utc))

    def test_last_matching_entry_is_retained_when_excerpts_are_omitted(self):
        report=self.log_report('[2026-10-18 16:11:14.419] xrEndFrame failed: XR_ERROR_VALIDATION_FAILURE\n'
                               '[2026-10-18 16:11:14.485] xrEndFrame failed: XR_ERROR_VALIDATION_FAILURE\n'
                               '[2026-10-18 16:15:30.000] unrelated log activity')
        finding=report['logs'][0]['findings'][0]
        self.assertEqual(finding['count'],2)
        self.assertEqual(finding['last_occurrence'],{'tail_line':2,'timestamp':'2026-10-18 16:11:14.485','timezone_recorded':False})
        snapshot={'sections':{'logs':{'data':report}}}
        view=support_report.export_view(snapshot,include_excerpts=False)
        data=view['sections']['logs']['data']
        self.assertEqual(data['logs'][0]['findings'][0]['excerpts'],[])
        self.assertEqual(data['logs'][0]['findings'][0]['last_occurrence'],finding['last_occurrence'])
        with local_zone('America/Los_Angeles'):
            text=log_diagnostics.report_text(data)
        self.assertIn('2026-10-18 16:11:14 (timezone not recorded)',text)
        self.assertIn('Historical log finding',text)
        self.assertNotIn('16:15:30',text)

    def test_missing_last_timestamp_does_not_reuse_an_older_match_time(self):
        report=self.log_report('[2026-10-18 16:11:14] xrEndFrame failed: XR_ERROR_VALIDATION_FAILURE\n'
                               'xrEndFrame failed: XR_ERROR_VALIDATION_FAILURE')
        last=report['logs'][0]['findings'][0]['last_occurrence']
        self.assertIsNone(last['timestamp'])
        self.assertEqual(last['tail_line'],2)

    def test_timezone_aware_log_timestamp_converts_only_for_presentation(self):
        report=self.log_report('[2026-10-18T23:11:14.485+00:00] xrEndFrame failed: XR_ERROR_VALIDATION_FAILURE')
        before=copy.deepcopy(report)
        with local_zone('America/Los_Angeles'):
            text=log_diagnostics.report_text(report)
        self.assertIn('Last matching entry in inspected tail: 2026-10-18 16:11:14 PDT',text)
        self.assertTrue(report['logs'][0]['findings'][0]['last_occurrence']['timezone_recorded'])
        self.assertEqual(report,before)

    def test_invalid_and_absent_log_timestamps_do_not_become_file_modified_times(self):
        for prefix in ('[2026-99-18 16:11:14] ', '', '[16:11:14] '):
            report=self.log_report(prefix+'xrEndFrame failed: XR_ERROR_VALIDATION_FAILURE')
            last=report['logs'][0]['findings'][0]['last_occurrence']
            self.assertIsNone(last['timestamp'])
            self.assertIn('unknown (timestamp not recorded)',log_diagnostics.report_text(report))

    def test_file_order_is_preserved_when_log_clock_moves_backwards(self):
        report=self.log_report('[2026-10-18 16:20:00] xrEndFrame failed: XR_ERROR_VALIDATION_FAILURE\n'
                               '[2026-10-18 16:10:00] xrEndFrame failed: XR_ERROR_VALIDATION_FAILURE')
        self.assertEqual(report['logs'][0]['findings'][0]['last_occurrence']['timestamp'],'2026-10-18 16:10:00')

    def test_last_occurrence_metadata_applies_to_all_finding_types(self):
        report=self.log_report('[2026-10-18 16:10:00] xrEndFrame failed (res=-39)\n'
                               '[2026-10-18 16:11:00] xrBeginFrame failed: XR_FRAME_DISCARDED\n'
                               '[2026-10-18 16:12:00] Depth gate menu=1')
        self.assertEqual(len(report['logs'][0]['findings']),3)
        self.assertTrue(all(f['last_occurrence']['timestamp'] for f in report['logs'][0]['findings']))

    def test_readable_compatibility_and_history_localize_without_changing_json(self):
        config=compatibility.report(self.recipe,self.roots)
        config['sampled_at']='2026-10-18T23:43:28.596274+00:00'
        entry=live_tests.record(self.recipe,'partial','Working with overlay closed.',{'vr_rendering':'passed'},config)
        entry['recorded_at']='2026-10-18T23:43:28.596274+00:00'
        config['local_test']=entry;config['local_test_count']=1
        before=json.dumps(config,sort_keys=True)
        with local_zone('America/Los_Angeles'):
            for text in (compatibility.report_text(config),compatibility.report_html(config),live_tests.record_text(entry)):
                self.assertIn('2026-10-18 16:43:28 PDT',text)
        self.assertEqual(json.dumps(config,sort_keys=True),before)

    def test_host_readable_times_are_local_without_mutating_scan_data(self):
        data=dict(hub_version='fixture',scanned_at='2026-10-18T23:43:28Z',status='HOST CHECKS PASSED',
                  scope='fixture',live=dict(sampled_at='2026-10-18T23:43:28Z',headset_connected=True),rows=[],environment={})
        before=copy.deepcopy(data)
        with local_zone('America/Los_Angeles'):
            self.assertIn('2026-10-18 16:43:28 PDT',system_scan.report_text(data))
            self.assertIn('2026-10-18 16:43:28 PDT',system_scan.report_html(data))
        self.assertEqual(data,before)

    def test_combined_text_explains_captured_snapshot_and_json_keeps_utc(self):
        self.path.write_text('xrEndFrame failed: XR_ERROR_VALIDATION_FAILURE')
        with mock.patch('vrhub.support_report.system_scan.scan',side_effect=RuntimeError('fixture unavailable')):
            snapshot=support_report.collect(self.recipe,self.roots)
        snapshot['collection_finished_at']='2026-10-18T23:43:28.596274+00:00'
        view=support_report.export_view(snapshot,include_excerpts=False)
        before=copy.deepcopy(view)
        with local_zone('America/Los_Angeles'):
            text=support_report.serialize(view)
            self.assertIn('Collection finished: 2026-10-18 16:43:28 PDT',text)
            self.assertIn('Copy/Save export this captured evidence',text)
            self.assertIn('Log excerpts: omitted',text)
        self.assertEqual(json.loads(support_report.serialize(view,True))['collection_finished_at'],'2026-10-18T23:43:28.596274+00:00')
        self.assertEqual(view,before)


if __name__=='__main__':
    unittest.main()
