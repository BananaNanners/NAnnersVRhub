import contextlib
import copy
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

from vrhub import cli, compatibility, hub
from vrhub.schema import RecipeError, validate_recipe


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.steam = self.home / '.local/share/Steam'
        self.apps = self.steam / 'steamapps'
        self.game = self.apps / 'common/SkyrimVR'
        self.game.mkdir(parents=True)
        (self.apps / 'libraryfolders.vdf').write_text('"libraryfolders" {}')
        (self.apps / 'appmanifest_611670.acf').write_text('"AppState" { "installdir" "SkyrimVR" }')
        (self.apps / 'compatdata/611670/pfx').mkdir(parents=True)
        self.prefix = self.apps / 'compatdata/4052365288'
        (self.prefix / 'pfx').mkdir(parents=True)
        self.proton = self.steam / 'compatibilitytools.d/GE-Proton10-14/proton'
        self.proton.parent.mkdir(parents=True)
        self.proton.write_text('fixture')
        (self.prefix / 'config_info').write_text(str(self.proton))
        self.mgo = self.home / 'SkyrimVRMODMGO3.8'
        self.mgo.mkdir()
        (self.mgo / 'ModOrganizer.exe').write_text('fixture')
        self.wanted = "Open Composite XR - Incompatible with VR Performance Kit"
        (self.mgo / 'mods' / self.wanted).mkdir(parents=True)
        self.ini = self.mgo / 'ModOrganizer.ini'
        self.ini.write_text('[General]\nselected_profile=Mad God\n[customExecutables]\n1\\title=SKSEVR\n1\\binary=Z:/game/sksevr_loader.exe\n')
        self.modlist = self.mgo / 'profiles/Mad God/modlist.txt'
        self.modlist.parent.mkdir(parents=True)
        self.modlist.write_text('+' + self.wanted + '\n-VR Performance Kit\n')
        self.vdf = self.steam / 'userdata/123/config/shortcuts.vdf'
        self.vdf.parent.mkdir(parents=True)
        self.shortcut_options('PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES=1 %command%')
        self.manifest = self.home / 'runtime.json'
        self.library = self.home / 'libopenxr_wivrn.so'
        self.library.write_text('fixture')
        self.manifest.write_text(json.dumps({'file_format_version': '1.0.0', 'runtime': {'library_path': str(self.library)}}))
        self.addCleanup(mock.patch.stopall)
        mock.patch('pathlib.Path.home', return_value=self.home).start()
        mock.patch.dict(os.environ, {'NANNERS_MGO_DIR': str(self.mgo), 'XR_RUNTIME_JSON': str(self.manifest),
                                    'VRHUB_STATE': str(self.home / 'state.json'), 'VRHUB_STEAM_ROOTS': str(self.steam)}).start()
        self.recipe = hub.load_recipes()['skyrim-vr-mgo']

    def shortcut_options(self, options):
        def z(x): return str(x).encode() + b'\0'
        data = b'\0' + z('shortcuts') + b'\0' + z('0')
        data += b'\x02' + z('appid') + struct.pack('<I', 4052365288)
        for name, value in [('AppName','MGO'),('Exe',str(self.mgo / 'ModOrganizer.exe')),('LaunchOptions',options)]:
            data += b'\x01' + z(name) + z(value)
        self.vdf.write_bytes(data + b'\x08\x08')

    def report(self):
        return compatibility.report(self.recipe, [self.steam])

    def row(self, name):
        return next(row for row in self.report()['checks'] if row['name'] == name)

    def test_complete_filesystem_fixture_passes_without_claiming_current_gameplay(self):
        report = self.report()
        self.assertEqual(report['status'], 'LOCAL CHECKS PASSED')
        text = compatibility.report_text(report)
        self.assertIn('not a current test', text)
        self.assertIn('do not verify current rendering', text)
        self.assertIn(str(self.prefix / 'pfx'), text)
        self.assertIn('Matches dated reference', text)

    def test_disabled_opencomposite_is_error_even_with_directory(self):
        self.modlist.write_text('-' + self.wanted)
        self.assertEqual(self.row('Active-profile OpenComposite')['status'], 'error')
        self.assertEqual(self.report()['status'], 'NOT READY')

    def test_enabled_performance_kit_conflict_is_error(self):
        self.modlist.write_text('+' + self.wanted + '\n+VR Performance Kit - FSR2')
        self.assertEqual(self.row('Active-profile VR Performance Kit')['status'], 'error')

    def test_disabled_performance_kit_folder_does_not_fail_configuration_checks(self):
        (self.mgo / 'mods/VR Performance Kit').mkdir()
        self.assertEqual(self.row('Active-profile VR Performance Kit')['status'], 'ok')
        self.assertEqual(self.row('VR Performance Kit')['status'], 'ok')
        self.assertEqual(self.report()['status'], 'LOCAL CHECKS PASSED')

    def test_missing_modlist_does_not_infer_enabled_state(self):
        self.modlist.unlink()
        self.assertEqual(self.row('Active-profile OpenComposite')['status'], 'unknown')
        self.assertEqual(self.report()['status'], 'INCOMPLETE')

    def test_duplicate_modlist_entries_are_unknown(self):
        self.modlist.write_text('+' + self.wanted + '\n-' + self.wanted)
        self.assertEqual(self.row('Active-profile OpenComposite')['status'], 'unknown')

    def test_custom_profile_root_never_uses_stale_default_modlist(self):
        self.ini.write_text(self.ini.read_text().replace('[General]', '[General]\nprofiles_directory=/custom'))
        self.assertEqual(self.row('Active-profile OpenComposite')['status'], 'unknown')

    def test_profile_traversal_is_not_read(self):
        self.ini.write_text('[General]\nselected_profile=../../other')
        self.assertEqual(self.row('Active-profile OpenComposite')['status'], 'unknown')

    def test_proton_change_is_review_without_rewriting_configuration(self):
        other = self.steam / 'compatibilitytools.d/Another-Proton/proton'
        other.parent.mkdir(parents=True)
        other.write_text('fixture')
        info = self.prefix / 'config_info'
        info.write_text(str(other))
        self.assertEqual(self.row('MO2 shortcut Proton')['status'], 'warning')
        self.assertEqual(self.report()['status'], 'REVIEW REQUIRED')
        self.assertEqual(info.read_text(), str(other))

    def test_base_game_prefix_cannot_substitute_for_mo2_prefix(self):
        (self.prefix / 'config_info').unlink()
        self.assertEqual(self.row('MO2 shortcut prefix/Proton')['status'], 'error')

    def test_runtime_library_missing_is_error(self):
        self.library.unlink()
        self.assertEqual(self.row('Runtime library file')['status'], 'error')

    def test_wrong_runtime_is_error(self):
        self.manifest.write_text(json.dumps({'file_format_version':'1.0.0','runtime':{'library_path':'libmonado.so'}}))
        self.assertEqual(self.row('Profile runtime')['status'], 'error')

    def test_bad_manifest_clears_prior_pass(self):
        self.assertEqual(self.report()['status'], 'LOCAL CHECKS PASSED')
        self.manifest.write_text('{')
        self.assertEqual(self.report()['status'], 'NOT READY')

    def test_hub_env_does_not_substitute_for_shortcut_launch_options(self):
        self.shortcut_options('%command%')
        with mock.patch.dict(os.environ, {'PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES':'1'}):
            self.assertEqual(self.row('Shortcut runtime import')['status'], 'warning')

    def test_simple_env_wrapper_is_recognized(self):
        self.shortcut_options('env PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES=1 gamemoderun %command%')
        self.assertEqual(self.row('Shortcut runtime import')['status'], 'ok')

    def test_assignment_in_echo_or_complex_shell_is_not_proof(self):
        for text in ['echo PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES=1 %command%',
                     'PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES=1 echo x; %command%',
                     'env PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES=0 %command%',
                     "'unterminated"]:
            with self.subTest(options=text):
                self.shortcut_options(text)
                self.assertEqual(self.row('Shortcut runtime import')['status'], 'warning')

    def test_recipe_without_metadata_has_undocumented_profile(self):
        recipe = hub.load_recipes()['fatekeeper']
        recipe.pop('compatibility')
        report = compatibility.report(recipe)
        self.assertEqual(report['status'], 'NOT DOCUMENTED')
        self.assertIsNone(report['profile'])
        self.assertFalse(report['checks'])

    def test_cli_json_status_and_diagnostics(self):
        for args, status, code in [(['compatibility','skyrim-vr-mgo','--json'],'LOCAL CHECKS PASSED',0),
                                   (['compatibility','fatekeeper','--json'],'NOT READY',1)]:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = cli.main(args)
            self.assertEqual(result,code)
            self.assertEqual(json.loads(output.getvalue())['status'],status)
        self.assertIn('Compatibility report', hub.diagnostics(self.recipe,[self.steam]))

    def test_report_is_read_only_and_starts_no_processes(self):
        def snapshot():
            return {str(p.relative_to(self.home)):p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        before = snapshot()
        with mock.patch('subprocess.Popen', side_effect=AssertionError('unexpected process')):
            self.report()
        self.assertEqual(snapshot(),before)

    def test_html_escapes_local_paths_and_recipe_text(self):
        self.recipe['compatibility']['notes'] = ['<script>unsafe & text</script>']
        rendered = compatibility.report_html(self.report())
        self.assertNotIn('<script>',rendered)
        self.assertIn('&lt;script&gt;',rendered)

    def test_schema_rejects_malformed_profiles_and_reference_dates(self):
        cases = [None, [], {'runtime':'WiVRn'}, copy.deepcopy(self.recipe['compatibility'])]
        cases[-1]['reference']['tested_on']='yesterday'
        for bad in cases:
            recipe = dict(self.recipe, compatibility=bad)
            with self.subTest(bad=bad), self.assertRaises(RecipeError):
                validate_recipe(recipe)

    def test_schema_rejects_contradiction_unknown_fields_and_bad_lists(self):
        for key, value in [('runtime','Monado'),('unknown','x'),('requirements','not a list')]:
            recipe=copy.deepcopy(self.recipe)
            recipe['compatibility'][key]=value
            with self.subTest(key=key), self.assertRaises(RecipeError):
                validate_recipe(recipe)


    def use_reported_modlist(self):
        unleashed = "Open Composite Unleashed for Skyrim VR 171182 5.0.4 2026"
        fsr = "VR Performance Kit - FSR - Use with DLAA"
        cas = "VR Performance Kit - CAS Sharpening - Default"
        for name in (unleashed, fsr, cas):
            (self.mgo / 'mods' / name).mkdir(exist_ok=True)
        self.modlist.write_text(f"-{fsr}\n-{cas}\n+{unleashed}\n-{self.wanted}\n")
        return unleashed, fsr, cas

    def test_user_reported_unleashed_and_disabled_kit_variants_pass(self):
        unleashed, _, _ = self.use_reported_modlist()
        before = self.modlist.read_bytes()
        with mock.patch('subprocess.Popen', side_effect=AssertionError('unexpected process')):
            report = self.report()
        self.assertEqual(report['status'], 'LOCAL CHECKS PASSED')
        row = next(row for row in report['checks'] if row['name'] == 'Active-profile OpenComposite')
        self.assertEqual(row['status'], 'ok')
        self.assertIn(unleashed, row['detail'])
        self.assertEqual(self.modlist.read_bytes(), before)

    def test_unleashed_only_install_does_not_require_old_xr_folder(self):
        self.use_reported_modlist()
        (self.mgo / 'mods' / self.wanted).rmdir()
        self.assertEqual(self.row('MGO OpenComposite')['status'], 'ok')
        self.assertTrue(hub.preflight(self.recipe, [self.steam])['ready'])
        self.assertEqual(self.report()['status'], 'LOCAL CHECKS PASSED')

    def test_enabled_unleashed_requires_its_own_folder(self):
        unleashed, _, _ = self.use_reported_modlist()
        (self.mgo / 'mods' / unleashed).rmdir()
        self.assertEqual(self.row('Active-profile OpenComposite')['status'], 'error')
        self.assertIn('missing', self.row('Active-profile OpenComposite')['detail'])

    def test_both_adapter_variants_enabled_are_reported_for_review(self):
        self.use_reported_modlist()
        self.modlist.write_text(self.modlist.read_text().replace('-' + self.wanted, '+' + self.wanted))
        row = self.row('Active-profile OpenComposite')
        self.assertEqual(row['status'], 'error')
        self.assertIn('Multiple', row['detail'])

    def test_new_fsr_and_cas_conflicts_detected_even_without_folder(self):
        _, fsr, cas = self.use_reported_modlist()
        original = self.modlist.read_text()
        for name in (fsr, cas):
            with self.subTest(name=name):
                (self.mgo / 'mods' / name).rmdir()
                self.modlist.write_text(original.replace('-' + name, '+' + name))
                self.assertEqual(self.row('Active-profile VR Performance Kit')['status'], 'error')
                self.assertEqual(self.row('VR Performance Kit')['status'], 'warning')
                self.assertEqual(self.report()['status'], 'NOT READY')

    def test_disabled_unleashed_does_not_substitute_for_enabled_adapter(self):
        unleashed, _, _ = self.use_reported_modlist()
        self.modlist.write_text(self.modlist.read_text().replace('+' + unleashed, '-' + unleashed))
        row = self.row('Active-profile OpenComposite')
        self.assertEqual(row['status'], 'error')
        self.assertIn('disabled', row['detail'])

    def test_unleashed_base_name_and_numeric_version_suffixes(self):
        from vrhub.handlers import SkyrimVRHandler
        handler = SkyrimVRHandler()
        for name in ('Open Composite Unleashed for Skyrim VR',
                     'Open Composite Unleashed for Skyrim VR 171182 5.0.5 2027'):
            self.assertTrue(handler._is_opencomposite_mod(self.recipe, name))
        for name in ('Open Composite Unleashed for Skyrim VR unrelated',
                     'Open Composite Unleashed for Skyrim VR 171182 backup copy',
                     'Open Composite Unleashed for Other Game 1.0',
                     'Open Composite Unleashed for Skyrim VR/../other'):
            self.assertFalse(handler._is_opencomposite_mod(self.recipe, name))

    def test_preflight_cannot_infer_disabled_conflicts_when_modlist_missing(self):
        self.use_reported_modlist()
        self.modlist.unlink()
        self.assertEqual(self.row('Active-profile VR Performance Kit')['status'], 'unknown')
        row = self.row('VR Performance Kit')
        self.assertEqual(row['status'], 'warning')
        self.assertIn('unverified', row['detail'])


if __name__ == '__main__':
    unittest.main()
