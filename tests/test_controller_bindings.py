"""Control evidence, offline rendering, filtering, packaging and real Qt navigation."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

from vrhub import controller_bindings as controls, hub, self_install


class ControllerGuidesTests(unittest.TestCase):
    def test_every_recipe_has_valid_versioned_sourced_guide(self):
        recipes = hub.load_recipes()
        self.assertEqual({p.stem for p in controls.GUIDES.glob('*.toml')}, set(recipes))
        for rid in recipes:
            guide = controls.load(rid)
            with self.subTest(game=rid):
                self.assertTrue(guide['scope'])
                self.assertIn('Sources', controls.html(guide))
                self.assertIn('current bindings are not scanned', controls.plain_text(guide))

    def test_evidence_does_not_promote_mod_defaults_to_local_success(self):
        guide = controls.load('valheim')
        rotation = next(r for s in guide['sections'] for r in s['bindings'] if 'Rotate the selected' in r['action'])
        self.assertEqual(rotation['evidence'], 'default')
        self.assertIn('NOT YET confirmed', rotation['note'])
        guide = controls.load('skyrim-vr-mgo')
        self.assertTrue(all(r['evidence'] == 'dependent' for s in guide['sections'] for r in s['bindings']))
        self.assertIn('3.8', guide['scope'])

    def test_subnautica_keeps_stock_pda_and_tested_drag_without_failed_override(self):
        guide = controls.load('subnautica')
        rows = [r for s in guide['sections'] for r in s['bindings']]
        self.assertEqual(next(r for r in rows if 'PDA' in r['action'])['input'], 'Y · left hand')
        self.assertEqual(next(r for r in rows if 'Assign an inventory' in r['action'])['evidence'], 'tested')
        self.assertFalse(any('system' in r['input'].lower() for r in rows))

    def test_search_matches_context_and_multiple_terms_and_category(self):
        guide = controls.load('valheim')
        found = controls.filtered_sections(guide, 'GRIP rotate', 'Building')
        self.assertEqual(len(found), 1)
        self.assertEqual(len(found[0]['bindings']), 1)
        self.assertIn('right grip', found[0]['bindings'][0]['input'])
        self.assertFalse(controls.filtered_sections(guide, 'rotate', 'Movement'))
        self.assertIn('No matching controls', controls.html(guide, 'no-such-action'))

    def test_rejects_unsafe_links_fake_test_claims_and_path_ids(self):
        original = controls.load('valheim')
        for field, value in [('url','file:///etc/passwd'), ('url','javascript:alert(1)')]:
            guide = copy.deepcopy(original);guide['sources']['upstream'][field] = value
            with self.assertRaises(ValueError):controls.validate(guide, 'valheim')
        guide = copy.deepcopy(original);guide['sections'][0]['bindings'][0]['evidence']='tested'
        with self.assertRaises(ValueError):controls.validate(guide, 'valheim')
        for rid in ['../valheim', '/tmp/game', 'Valheim']:
            with self.assertRaises(ValueError):controls.load(rid)
        self.assertIsNone(controls.load('future-game'))

    def test_html_escapes_content_and_copy_preserves_complete_evidence(self):
        guide = controls.load('valheim');guide['title']='<b>unsafe & title</b>'
        rendered = controls.html(guide)
        self.assertIn('&lt;b&gt;unsafe &amp; title&lt;/b&gt;', rendered)
        self.assertNotIn('<b>unsafe', rendered)
        text = controls.plain_text(guide)
        self.assertIn('Notes and limitations', text)
        self.assertIn('Mod default', text)
        self.assertIn('https://github.com/', text)

    def test_managed_install_includes_all_guides_and_rejects_missing_declared_file(self):
        import tempfile, shutil
        source = Path(__file__).resolve().parents[1]
        version, files = self_install._source_files(source)
        self.assertEqual(sum(p.startswith('vrhub/controls/') for p in files), 9)
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'source'
            shutil.copytree(source/'vrhub', dest/'vrhub', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copy2(source/'pyproject.toml', dest/'pyproject.toml')
            (dest/'vrhub/controls/valheim.toml').unlink()
            with self.assertRaisesRegex(RuntimeError,'Incomplete source folder'):
                self_install._source_files(dest)


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Optional PySide6 is not installed')
class ControllerQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def test_filter_switch_and_copy_full_guide(self):
        from vrhub.controller_gui import ControllerBindingsPage
        page=ControllerBindingsPage()
        try:
            self.assertFalse(page.copy_button.isEnabled())
            page.set_recipe({'id':'valheim'})
            page.category.setCurrentText('Building');page.search.setText('rotate')
            self.assertIn('1 of',page.count.text())
            self.assertNotIn('Toggle map',page.results.toPlainText())
            page.copy_button.click()
            self.assertIn('Toggle map',self.app.clipboard().text())
            self.assertIn('NOT YET confirmed',self.app.clipboard().text())
            page.expand_button.click();self.app.processEvents()
            self.assertIn('Valheim',page.expanded.windowTitle())
            self.assertGreater(page.expanded.width(),700)
            page.expanded.close();self.app.processEvents()
            page.set_recipe({'id':'valheim'})
            self.assertEqual(page.search.text(),'rotate')
            page.set_recipe({'id':'subnautica'})
            self.assertEqual(page.search.text(),'')
            self.assertEqual(page.category.currentText(),'All sections')
            self.assertIn('PDA',page.results.toPlainText())
            page.search.setText('not-a-control');self.assertIn('No matching controls',page.results.toPlainText())
            page.set_recipe(None);self.assertFalse(page.copy_button.isEnabled())
        finally:page.close()

    def test_missing_or_invalid_guide_fails_locally_without_crashing_game_page(self):
        from vrhub.controller_gui import ControllerBindingsPage
        page=ControllerBindingsPage()
        try:
            page.set_recipe({'id':'future-game'})
            self.assertIn('No controller guide',page.results.toPlainText())
            self.assertFalse(page.copy_button.isEnabled())
            with mock.patch.object(controls,'load',side_effect=ValueError('invalid data')):
                page.set_recipe({'id':'valheim'})
            self.assertIn('unavailable',page.results.toPlainText())
            self.assertFalse(page.copy_button.isEnabled())
        finally:page.close()

    def test_all_nine_game_rows_show_their_own_guide_without_state_writes(self):
        from tests.test_workflow_compatibility import SteamWorkflowCompatibilityTests
        from vrhub.gui import HubWindow
        fixture=SteamWorkflowCompatibilityTests();fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        with mock.patch.object(HubWindow,'check_updates'), mock.patch.object(HubWindow,'scan_setup'), \
             mock.patch('vrhub.app_update_gui.HubUpdateController.startup'), \
             mock.patch.object(hub,'_save_state',side_effect=AssertionError('guide must not save game state')):
            window=HubWindow()
            try:
                self.assertEqual(window.game_details_tabs.tabText(2),'Controller bindings')
                window.game_details_tabs.setCurrentIndex(2)
                self.assertEqual(window.table.rowCount(),9)
                for i in range(9):
                    window.table.selectRow(i);self.app.processEvents()
                    guide=window.controller_bindings.guide
                    self.assertEqual(guide['id'],window.current()['id'])
                    self.assertIn(guide['title'],window.controller_bindings.results.toPlainText())
                window.resize(1000,720);window.show();self.app.processEvents()
                self.assertFalse(window.controller_bindings.diagram.grab().isNull())
            finally:window.close();self.app.processEvents()
