import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from vrhub import cli, compatibility, hub
from vrhub.schema import RecipeError, validate_recipe


class SteamWorkflowCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.steam = self.home / 'Steam'
        self.apps = self.steam / 'steamapps'
        self.apps.mkdir(parents=True)
        (self.apps / 'libraryfolders.vdf').write_text('"libraryfolders" {}')
        self.state = self.home / 'state.json'
        self.state.write_text('{}')
        self.proton = self.steam / 'compatibilitytools.d/Existing-Proton/proton'
        self.proton.parent.mkdir(parents=True)
        self.proton.write_text('fixture, never executed')
        lib = self.home / 'libopenxr_wivrn.so'
        lib.write_text('fixture, never loaded')
        manifest = self.home / 'runtime.json'
        manifest.write_text(json.dumps({'file_format_version':'1.0.0','runtime':{'library_path':str(lib)}}))
        env = mock.patch.dict(os.environ, {'XR_RUNTIME_JSON':str(manifest), 'VRHUB_STATE':str(self.state),
                                           'VRHUB_STEAM_ROOTS':str(self.steam)}, clear=False)
        env.start(); self.addCleanup(env.stop)
        tools = mock.patch('vrhub.compatibility_checks.shutil.which', return_value='/usr/bin/protontricks-launch')
        tools.start(); self.addCleanup(tools.stop)
        self.recipes = hub.load_recipes()

    def game(self, rid):
        recipe = self.recipes[rid]
        game = self.apps / 'common' / rid
        game.mkdir(parents=True)
        (self.apps / f'appmanifest_{recipe["steam_appid"]}.acf').write_text('"AppState" { "installdir" "' + rid + '" }')
        prefix = self.apps / 'compatdata' / str(recipe['steam_appid']) / 'pfx'
        prefix.mkdir(parents=True)
        (prefix.parent / 'config_info').write_text(str(self.proton))
        return recipe, game, prefix

    def record(self, key, entry):
        state = json.loads(self.state.read_text())
        state[key] = entry
        self.state.write_text(json.dumps(state))

    def file(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture')
        return path

    def fatekeeper(self):
        recipe, game, prefix = self.game('fatekeeper')
        root = prefix / 'drive_c/uevr'
        files = [self.file(root / name) for name in ('UEVRInjector.exe','UEVRBackend.dll')]
        prof = prefix / hub.APPDATA / recipe['profile']['dir']
        profile_files = [self.file(prof / name) for name in ('config.txt','plugins/fixture.dll')]
        self.record('fatekeeper', {'files':[str(p) for p in files]})
        self.record('fatekeeper:profile', {'files':[str(p) for p in profile_files]})
        return recipe, game, prefix, profile_files

    def ready_or_not(self):
        recipe, game, prefix = self.game('ready-or-not')
        pak = self.file(game / recipe['files'][0]['dest'] / 'VRO-fixture.pak')
        self.record('ready-or-not', {'files':[str(pak)]})
        return recipe, game, prefix, pak

    def cyberpunk(self, port=True):
        recipe, game, prefix = self.game('cyberpunk-2077')
        records = {}
        for component in recipe['components']:
            if not port and component.get('phase',1) == 2:
                continue
            path = game / (component['required_files'][0] if component.get('required_files') else f'fixture-dependencies/{component["nexus_mod"]}.dll')
            self.file(path)
            records[str(component['nexus_mod'])]={'files':[str(path)]}
        self.record(recipe['id'],{'keep':str(game),'components':records})
        return recipe, game, prefix

    def report(self, recipe):
        return compatibility.report(recipe, [self.steam])

    def row(self, recipe, name):
        return next(row for row in self.report(recipe)['checks'] if row['name'] == name)

    def test_all_profiles_have_explicit_gameplay_evidence(self):
        self.assertEqual(len(self.recipes),5)
        for recipe in self.recipes.values():
            self.assertIn('compatibility',recipe)
            self.assertIn('validation',recipe['compatibility'])
        self.assertEqual(self.recipes['cyberpunk-2077']['compatibility']['validation'],'user-reported-workaround')
        self.assertEqual(self.recipes['ready-or-not']['compatibility']['validation'],'user-reported')
        self.assertEqual(self.recipes['fatekeeper']['compatibility']['validation'],'user-reported')
        self.assertEqual(self.recipes['hogwarts-legacy']['compatibility']['validation'],'user-reported')

    def test_skyrim_reference_records_latest_user_test(self):
        profile=self.recipes['skyrim-vr-mgo']['compatibility']
        self.assertEqual(profile['validation'],'user-reported')
        self.assertEqual(profile['reference']['tested_on'],'2026-10-17')
        self.assertIn('Unleashed',profile['reference']['result'])

    def test_fatekeeper_complete_inventory_requires_manual_review(self):
        recipe, _, _, _ = self.fatekeeper()
        report=self.report(recipe)
        self.assertEqual(report['status'],'REVIEW REQUIRED')
        text=compatibility.report_text(report)
        self.assertIn('Gameplay evidence: USER-REPORTED LIVE TEST',text)
        self.assertIn('Test date: 2026-10-17',text)
        self.assertIn('proton-cachyos-slr',text)
        self.assertIn('not inspected automatically',text)

    def test_fatekeeper_missing_injector_backend_or_profile_config_is_not_ready(self):
        recipe, _, prefix, _ = self.fatekeeper()
        for path in [prefix/'drive_c/uevr/UEVRInjector.exe',prefix/'drive_c/uevr/UEVRBackend.dll',
                     prefix/hub.APPDATA/recipe['profile']['dir']/'config.txt']:
            with self.subTest(path=path):
                path.unlink()
                self.assertEqual(self.report(recipe)['status'],'NOT READY')
                self.file(path)

    def test_missing_recorded_profile_plugin_is_detected(self):
        recipe, _, _, files = self.fatekeeper()
        files[-1].unlink()
        self.assertEqual(self.row(recipe,'UEVR game-profile inventory')['status'],'error')

    def test_config_file_alone_cannot_substitute_for_profile_inventory(self):
        recipe, _, _, _ = self.fatekeeper()
        state=json.loads(self.state.read_text());state.pop('fatekeeper:profile');self.state.write_text(json.dumps(state))
        self.assertEqual(self.report(recipe)['status'],'INCOMPLETE')
        self.assertEqual(self.row(recipe,'UEVR game-profile inventory')['status'],'unknown')

    def test_missing_injector_launch_tool_is_error(self):
        recipe, _, _, _ = self.fatekeeper()
        with mock.patch('vrhub.compatibility_checks.shutil.which',return_value=None):
            self.assertEqual(self.row(recipe,'Launch tool: protontricks-launch')['status'],'error')

    def test_ready_or_not_checks_recorded_paks(self):
        recipe, _, _, pak = self.ready_or_not()
        self.assertEqual(self.report(recipe)['status'],'REVIEW REQUIRED')
        pak.unlink()
        self.assertEqual(self.report(recipe)['status'],'NOT READY')

    def test_arbitrary_untracked_pak_does_not_prove_vro_install(self):
        recipe, _, _, _ = self.ready_or_not()
        self.state.write_text('{}')
        self.assertEqual(self.row(recipe,'Mod install inventory')['status'],'unknown')
        self.assertEqual(self.report(recipe)['status'],'INCOMPLETE')

    def test_directory_named_pak_is_not_an_installed_file(self):
        recipe, _, _, pak = self.ready_or_not()
        pak.unlink();pak.mkdir()
        self.assertEqual(self.row(recipe,'Mod install inventory')['status'],'error')

    def test_vro_inventory_wrong_type_or_location_is_error(self):
        recipe, game, _, _ = self.ready_or_not()
        for path in (game/'outside.pak', game/recipe['files'][0]['dest']/'wrong.dll'):
            self.file(path)
            self.record('ready-or-not',{'files':[str(path)]})
            self.assertEqual(self.row(recipe,'Mod install inventory')['status'],'error')

    def test_another_install_or_symlink_cannot_supply_missing_files(self):
        recipe, _, _, pak = self.ready_or_not()
        outside=self.file(self.home/'another-install.pak')
        pak.unlink();pak.symlink_to(outside)
        self.assertEqual(self.row(recipe,'Mod install inventory')['status'],'error')

    def test_cyberpunk_base_game_guard_ready_still_needs_vr_port(self):
        recipe, _, _ = self.cyberpunk(port=False)
        self.assertTrue(hub.preflight(recipe,[self.steam])['ready'])
        self.assertEqual(self.row(recipe,'VR port installation')['status'],'error')
        self.assertEqual(self.report(recipe)['status'],'NOT READY')

    def test_cyberpunk_files_do_not_promote_experimental_gameplay(self):
        recipe, _, _ = self.cyberpunk()
        report=self.report(recipe)
        self.assertEqual(report['status'],'REVIEW REQUIRED')
        self.assertIn('WORKAROUND REQUIRED (experimental)',compatibility.report_text(report))
        self.assertIn('Required workaround',compatibility.report_html(report))
        self.assertIn('reference',report['profile'])
        self.assertEqual(len(report['profile']['workarounds']),4)

    def test_cyberpunk_empty_component_record_cannot_pass(self):
        recipe, _, _ = self.cyberpunk()
        entry=json.loads(self.state.read_text())[recipe['id']]
        entry['components']['107']['files']=[]
        self.record(recipe['id'],entry)
        self.assertEqual(self.report(recipe)['status'],'INCOMPLETE')

    def test_cyberpunk_inventory_from_other_library_is_error(self):
        recipe, _, _ = self.cyberpunk()
        entry=json.loads(self.state.read_text())[recipe['id']]
        entry['components']['107']['files']=[str(self.file(self.home/'other-library/107.dll'))]
        self.record(recipe['id'],entry)
        self.assertEqual(self.row(recipe,'VR workflow component: Cyber Engine Tweaks')['status'],'error')

    def test_missing_recorded_proton_is_unknown_without_guessing_installed_tool(self):
        recipe, _, prefix, _ = self.ready_or_not()
        (prefix.parent/'config_info').unlink()
        self.assertEqual(self.row(recipe,'Recorded Proton')['status'],'unknown')
        self.assertEqual(self.report(recipe)['status'],'INCOMPLETE')

    def test_recorded_proton_files_path_is_resolved(self):
        recipe, _, prefix, _ = self.ready_or_not()
        (prefix.parent/'config_info').write_text(str(self.proton.parent/'files/share/fonts'))
        self.assertIn(str(self.proton),self.row(recipe,'Recorded Proton')['detail'])

    def test_hub_runtime_import_does_not_verify_steam_settings(self):
        recipe, _, _, _ = self.ready_or_not()
        with mock.patch.dict(os.environ,{'PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES':'1'}):
            warnings=[r for r in self.report(recipe)['checks'] if r['status']=='warning']
        self.assertTrue(any('Steam options' in r['detail'] for r in warnings))

    def test_reports_are_read_only_and_never_start_processes(self):
        recipes=[self.fatekeeper()[0],self.ready_or_not()[0],self.cyberpunk()[0]]
        def snapshot():
            return {str(p.relative_to(self.home)):p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        before=snapshot()
        with mock.patch('subprocess.Popen',side_effect=AssertionError('unexpected process')):
            for recipe in recipes:self.report(recipe)
        self.assertEqual(snapshot(),before)

    def test_cli_json_and_diagnostics_for_each_game(self):
        recipes=[self.fatekeeper()[0],self.ready_or_not()[0],self.cyberpunk()[0]]
        for recipe in recipes:
            with self.subTest(recipe=recipe['id']):
                output=io.StringIO()
                with contextlib.redirect_stdout(output):code=cli.main(['compatibility',recipe['id'],'--json'])
                self.assertEqual(code,0)
                self.assertEqual(json.loads(output.getvalue())['status'],'REVIEW REQUIRED')
                self.assertIn('Compatibility report',hub.diagnostics(recipe,[self.steam]))

    def test_profile_schema_rejects_unsafe_file_paths_and_commands(self):
        for key,value in [('prefix_files',['../escape']),('game_files',['/absolute']),
                          ('game_files',['C:/game.dll']),('commands',['tool; echo x']),
                          ('tracked_install','yes'),('unknown',True)]:
            recipe=copy.deepcopy(self.recipes['fatekeeper'])
            recipe['compatibility']['checks'][key]=value
            with self.subTest(key=key),self.assertRaises(RecipeError):validate_recipe(recipe)

    def test_user_reported_evidence_needs_reference_and_valid_status(self):
        for value in ('user-reported','verified',[]):
            recipe=copy.deepcopy(self.recipes['ready-or-not'])
            recipe['compatibility'].pop('reference',None)
            recipe['compatibility']['validation']=value
            with self.subTest(value=value),self.assertRaises(RecipeError):validate_recipe(recipe)

    def test_inventory_empty_or_relative_record_is_unverified(self):
        recipe, _, _, _ = self.ready_or_not()
        for files in ([],['relative.pak'],[42]):
            self.record(recipe['id'],{'files':files})
            self.assertEqual(self.row(recipe,'Mod install inventory')['status'],'unknown')

    def test_profile_inventory_requires_safe_destination(self):
        for path in ('../other', '/outside', 'C:/outside'):
            recipe=copy.deepcopy(self.recipes['fatekeeper'])
            recipe['profile']['dir']=path
            with self.subTest(path=path),self.assertRaises(RecipeError):validate_recipe(recipe)
        recipe=copy.deepcopy(self.recipes['fatekeeper'])
        recipe.pop('profile')
        with self.assertRaises(RecipeError):validate_recipe(recipe)


    def test_workaround_evidence_requires_both_reference_and_instructions(self):
        for field in ('reference','workarounds'):
            recipe=copy.deepcopy(self.recipes['cyberpunk-2077'])
            recipe['compatibility'].pop(field)
            with self.subTest(field=field),self.assertRaises(RecipeError):validate_recipe(recipe)

    def test_workaround_is_prominent_and_never_certifies_stereo_depth(self):
        recipe, _, _ = self.cyberpunk()
        report=self.report(recipe)
        text=compatibility.report_text(report)
        self.assertLess(text.index('Required workaround'),text.index('OpenXR runtime:'))
        self.assertIn('Stereo depth, sustained stability',text)
        self.assertIn('have not been separately validated',text)
        self.assertEqual(report['status'],'REVIEW REQUIRED')


if __name__=='__main__':unittest.main()
