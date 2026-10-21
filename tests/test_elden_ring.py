"""Pinned payload safety, PE metadata and fail-closed offline command routing."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import unittest
from unittest import mock
import zipfile

from tests import test_workflow_compatibility as workflow_tests
from vrhub import bepinex, compatibility, elden_ring, guard, hub, log_diagnostics, self_install
from vrhub.schema import RecipeError, validate_recipe


def pe(version=(2,7,1,0)):
    """Minimal x64 PE with a real RT_VERSION directory / fixed-file-info value."""
    data=bytearray(0x600);data[:2]=b'MZ';struct.pack_into('<I',data,60,0x80)
    data[0x80:0x84]=b'PE\0\0'
    struct.pack_into('<HH',data,0x84,0x8664,1);struct.pack_into('<H',data,0x94,240)
    struct.pack_into('<H',data,0x98,0x20b);struct.pack_into('<II',data,0x98+128,0x1000,0x400)
    section=0x98+240;data[section:section+8]=b'.rsrc\0\0\0'
    struct.pack_into('<IIII',data,section+8,0x400,0x1000,0x400,0x200)
    for offset,key,dest in [(0,16,0x80000020),(0x20,1,0x80000040),(0x40,0x409,0x60)]:
        struct.pack_into('<HH',data,0x200+offset+12,0,1)
        struct.pack_into('<II',data,0x200+offset+16,key,dest)
    key='VS_VERSION_INFO\0'.encode('utf-16-le');value=(6+len(key)+3)&~3
    blob=bytearray(value+52);struct.pack_into('<HHH',blob,0,len(blob),52,0);blob[6:6+len(key)]=key
    a,b,c,d=version;struct.pack_into('<IIII',blob,value,0xfeef04bd,0x10000,(a<<16)|b,(c<<16)|d)
    struct.pack_into('<IIII',data,0x260,0x1080,len(blob),0,0);data[0x280:0x280+len(blob)]=blob
    return bytes(data)


class EldenRingTests(unittest.TestCase):
    def setUp(self):
        self.f=workflow_tests.SteamWorkflowCompatibilityTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        r,self.game,self.prefix=self.f.game('elden-ring');self.recipe=copy.deepcopy(r)
        self.exe=self.f.file(self.game/'Game/eldenring.exe');self.exe.write_bytes(pe())
        self.protected=self.f.file(self.game/'Game/start_protected_game.exe');self.protected.write_bytes(b'original protected launcher')
        self.save=self.f.file(self.prefix/'drive_c/users/steamuser/AppData/Roaming/EldenRing/save.sl2')
        self.save.write_bytes(b'synthetic save, never load')
        self.history=self.f.state.with_name('live-tests.json');self.history.write_text('{"schema_version":1,"games":{}}')
        self.f.record('subnautica',{'installer':'submersed-vr-1','fixture':'unchanged'})
        self.keep={p:p.read_bytes() for p in [self.exe,self.protected,self.save,self.history]}
        self.entries={n.removeprefix('Game/').replace('/','\\'):('fixture '+n).encode() for n in self.recipe['packages'][0]['required_files']}
        self.entries['ERVR\\ERVR.ini']=b'[General]\nEnabled=true\nVRRuntime=openxr\n[VR]\nStereoMode=full\n'
        self.archive=self.zip()

    def zip(self,entries=None):
        path=self.f.home/'renamed-download.zip'
        with zipfile.ZipFile(path,'w') as z:
            for name,data in (entries if entries is not None else self.entries).items():
                if isinstance(name,zipfile.ZipInfo):z.writestr(name,data)
                else:z.writestr(name,data)
        self.recipe['packages'][0]['sha256']=bepinex.digest(path)
        return path

    def install(self):return hub.install(self.recipe,self.archive,[self.f.steam])

    def preserved(self):
        for p,data in self.keep.items():self.assertEqual(p.read_bytes(),data,str(p))
        self.assertEqual(hub.state()['subnautica']['fixture'],'unchanged')

    def command(self):return ['/selected/proton','waitforexitandrun',str(self.protected),'--literal=$HOME;false']

    def test_pe_resource_version_supported_wrong_and_malformed(self):
        self.assertEqual(elden_ring.file_version(self.exe),'2.7.1.0')
        self.exe.write_bytes(pe((2,6,2,0)));self.assertEqual(elden_ring.file_version(self.exe),'2.6.2.0')
        self.exe.write_bytes(pe((9,9,9,9)));self.assertNotIn(elden_ring.file_version(self.exe),elden_ring.SUPPORTED)
        for data in [b'',b'MZ',pe()[:0x250],b'NOT A PE'+pe(),pe()[:0x80]+b'BAD!'+pe()[0x84:]]:
            self.exe.write_bytes(data);self.assertIsNone(elden_ring.file_version(self.exe))

    def test_installs_ten_normalized_files_and_reports_without_gameplay_claim(self):
        installed=self.install();self.assertEqual(len(installed),10)
        for name,data in self.entries.items():
            self.assertEqual((self.game/'Game'/name.replace('\\','/')).read_bytes(),data)
        self.assertFalse(any('\\' in p.name for p in self.game.rglob('*')))
        self.assertTrue(hub.verify(self.recipe,[self.f.steam])['ready'])
        self.assertEqual(hub.inspect_archive(self.recipe,self.archive)['install_files'],10)
        self.assertEqual(elden_ring.configuration(self.game)['stereo'],'full')
        text=compatibility.report_text(compatibility.report(self.recipe,[self.f.steam]))
        self.assertIn('UNVERIFIED',text);self.assertIn('Dated gameplay reference: none recorded',text)
        self.assertIn('REVIEW REQUIRED',text);self.preserved()

    def test_wrong_digest_or_missing_payload_never_writes_files(self):
        self.recipe['packages'][0]['sha256']='0'*64
        with self.assertRaisesRegex(RuntimeError,'recognized pinned'):self.install()
        entries=dict(self.entries);entries.pop('dinput8.dll');self.zip(entries)
        with self.assertRaisesRegex(RuntimeError,'Incomplete'):self.install()
        self.assertFalse((self.game/'Game/dxgi.dll').exists());self.preserved()

    def test_traversal_case_twin_and_symlink_are_rejected(self):
        for name in ['ERVR\\..\\evil.dll','/absolute.dll','C:\\escape.dll','ERVR\\.\\evil.dll','DXGI.DLL']:
            entries=dict(self.entries);entries[name]=b'unsafe';self.zip(entries)
            with self.subTest(name=name),self.assertRaises(RuntimeError):self.install()
        info=zipfile.ZipInfo('ERVR\\link');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
        self.zip({**self.entries,info:b'/outside'})
        with self.assertRaises(RuntimeError):self.install()
        self.assertFalse((self.game/'Game/dxgi.dll').exists());self.preserved()

    def test_existing_wrappers_configs_and_foreign_runtime_block_install(self):
        for name in ['dxgi.dll','dinput8.dll','ReShade.ini','RealVR64.dll','RealRepo']:
            p=self.game/'Game'/name;p.write_bytes(b'existing mod')
            with self.subTest(name=name),self.assertRaisesRegex(RuntimeError,'conflicting'):self.install()
            self.assertEqual(p.read_bytes(),b'existing mod');p.unlink()
        self.preserved()

    def test_uninstall_reinstall_with_empty_or_log_only_folder(self):
        folder=self.game/'Game/ERVR'
        self.install();hub.uninstall('elden-ring')
        self.assertTrue(folder.is_dir());self.assertEqual(list(folder.iterdir()),[])
        self.assertEqual(bepinex.conflicts(self.game,self.recipe),[])
        self.install();self.assertTrue(hub.verify(self.recipe,[self.f.steam])['ready'])
        log=folder/'ERVR.log';log.write_bytes(b'preserve historical session log\n')
        hub.uninstall('elden-ring')
        self.assertEqual(list(folder.iterdir()),[log])
        self.assertEqual(bepinex.conflicts(self.game,self.recipe),[])
        self.install();self.assertTrue(hub.verify(self.recipe,[self.f.steam])['ready'])
        self.assertEqual(log.read_bytes(),b'preserve historical session log\n')
        hub.uninstall('elden-ring');self.preserved()

    def test_residual_folder_cannot_hide_foreign_payload_or_unsafe_log(self):
        folder=self.game/'Game/ERVR';folder.mkdir()
        for name in ['ERVR.dll','ERVR.ini','other.dll','unknown-file.txt','cache']:
            p=folder/name;p.write_bytes(b'keep foreign content')
            with self.subTest(name=name),self.assertRaisesRegex(RuntimeError,'conflicting'):
                self.install()
            self.assertEqual(p.read_bytes(),b'keep foreign content');p.unlink()
        log=folder/'ERVR.log';log.mkdir()
        with self.assertRaisesRegex(RuntimeError,'conflicting'):self.install()
        log.rmdir();log.symlink_to(self.save)
        with self.assertRaisesRegex(RuntimeError,'conflicting'):self.install()
        log.unlink();folder.rmdir()
        wrong_case=self.game/'Game/ervr';wrong_case.mkdir()
        with self.assertRaises(RuntimeError):self.install()
        self.preserved()

    def test_filesystem_symlink_is_rejected(self):
        outside=self.f.home/'outside';outside.mkdir();(self.game/'Game/ERVR').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(RuntimeError):self.install()
        self.assertEqual(list(outside.iterdir()),[]);self.preserved()

    def test_commit_failure_restores_original_file_and_other_records(self):
        original=self.f.file(self.game/'Game/LICENSE-ReShade.txt');original.write_bytes(b'old license')
        state=self.f.state.read_bytes()
        with mock.patch.object(bepinex,'_save',side_effect=OSError('save failure')):
            with self.assertRaisesRegex(OSError,'save failure'):self.install()
        self.assertEqual(original.read_bytes(),b'old license');self.assertEqual(self.f.state.read_bytes(),state)
        self.assertFalse((self.game/'Game/dxgi.dll').exists());self.preserved()

    def test_removal_restores_originals_preserves_edited_ini_logs_and_saves(self):
        original=self.f.file(self.game/'Game/LICENSE-ReShade.txt');original.write_bytes(b'original license')
        self.install();entry=hub.state()['elden-ring'];config=self.game/'Game/ERVR/ERVR.ini'
        config.write_bytes(config.read_bytes()+b'; personal edit\n');edited=config.read_bytes()
        log=self.f.file(self.game/'Game/ERVR/ERVR.log');log.write_bytes(b'historical runtime output')
        hub.uninstall('elden-ring')
        self.assertEqual(original.read_bytes(),b'original license')
        self.assertEqual((Path(entry['backup'])/'user-modified/Game/ERVR/ERVR.ini').read_bytes(),edited)
        self.assertTrue(log.is_file());self.assertFalse((self.game/'Game/dxgi.dll').exists());self.preserved()

    def test_modified_binary_blocks_removal_and_launch(self):
        self.install();(self.game/'Game/dxgi.dll').write_bytes(b'changed binary')
        with self.assertRaisesRegex(RuntimeError,'binary files changed'):hub.uninstall('elden-ring')
        with mock.patch.object(hub,'load_recipes',return_value={'elden-ring':self.recipe}),mock.patch('os.execvpe') as execute:
            self.assertEqual(elden_ring.main(self.command()),1);execute.assert_not_called()
        self.preserved()

    def test_command_adapter_preserves_runner_arguments_and_never_changes_protected_file(self):
        argv=elden_ring.launch_command(self.command(),self.game)
        self.assertEqual(argv[:2],self.command()[:2]);self.assertEqual(argv[2],str(self.exe));self.assertEqual(argv[3],self.command()[3])
        windows=list(self.command());windows[2]='Z:'+str(self.protected).replace('/','\\')
        self.assertEqual(elden_ring.launch_command(windows,self.game)[2],str(self.exe));self.preserved()

    def test_command_adapter_rejects_foreign_ambiguous_and_shell_commands(self):
        invalid=[['/proton','waitforexitandrun','/elsewhere/start_protected_game.exe'],
                 ['/proton','waitforexitandrun','eldenring.exe'],['/proton','waitforexitandrun',str(self.exe),str(self.protected)],
                 ['/bin/sh','-c','proton waitforexitandrun '+str(self.protected)],
                 ['/bin/sh','-c','/proton','waitforexitandrun',str(self.protected)]]
        for argv in invalid:
            with self.subTest(argv=argv),self.assertRaises(RuntimeError):elden_ring.launch_command(argv,self.game)

    def test_launch_keeps_steam_runner_and_prefix_no_shell(self):
        self.install()
        with mock.patch.dict(os.environ,{'STEAM_COMPAT_DATA_PATH':str(self.prefix.parent)}),mock.patch.object(hub,'load_recipes',return_value={'elden-ring':self.recipe}),mock.patch('os.execvpe') as execute:
            self.assertEqual(guard.main(['elden-ring',*self.command()]),0)
            executable,argv,environment=execute.call_args.args
            self.assertEqual(executable,'/selected/proton');self.assertEqual(argv[2],str(self.exe))
            self.assertEqual(argv[3],self.command()[3]);self.assertEqual(environment['STEAM_COMPAT_DATA_PATH'],str(self.prefix.parent))
        self.preserved()

    def test_unknown_version_stops_even_with_skip_check_flag(self):
        self.install();self.exe.write_bytes(pe((9,9,9,9)))
        with mock.patch.dict(os.environ,{'VRHUB_SKIP_CHECK':'1'}),mock.patch.object(hub,'load_recipes',return_value={'elden-ring':self.recipe}),mock.patch('os.execvpe') as execute:
            self.assertEqual(guard.main(['elden-ring',*self.command()]),1);execute.assert_not_called()

    def test_broken_source_or_managed_guard_cannot_fall_through_to_protected_command(self):
        folder=self.f.home/'isolated';folder.mkdir();marker=folder/'should-not-exist'
        source=Path(__file__).resolve().parents[1]
        shutil.copy2(source/'vrhub-check',folder/'vrhub-check');(folder/'vrhub-check').chmod(0o755)
        environment={**os.environ,'PYTHONPATH':''}
        result=subprocess.run([folder/'vrhub-check','elden-ring','/usr/bin/touch',marker],cwd=folder,env=environment,capture_output=True)
        self.assertNotEqual(result.returncode,0);self.assertFalse(marker.exists())
        (folder/'run.py').write_text(self_install.BOOTSTRAP)
        (folder/'installation.json').write_text('{"schema":1,"current":"absent"}')
        result=subprocess.run([sys.executable,folder/'run.py','guard','elden-ring','/usr/bin/touch',marker],cwd=folder,env=environment,capture_output=True)
        self.assertNotEqual(result.returncode,0);self.assertFalse(marker.exists())
        artifacts=self_install._artifacts(folder,'/missing-hub-python',{'vrhub/self_install.py':b'', 'vrhub/assets/bananananners.png':b''})
        script=folder/'bin/nannersvrhub-check';script.parent.mkdir()
        script.write_bytes(artifacts[script][1]);script.chmod(0o755)
        result=subprocess.run([script,'elden-ring','/usr/bin/touch',marker],cwd=folder,env=environment,capture_output=True)
        self.assertNotEqual(result.returncode,0);self.assertFalse(marker.exists())
        # A real older release imports successfully but knows no ER adapter.
        # Its generic guard's fallback must not receive the protected command.
        old=folder/'releases/old/vrhub';old.mkdir(parents=True)
        (old/'__init__.py').write_text('')
        (old/'guard.py').write_text('import os,sys\ndef main(): os.execvp(sys.argv[2],sys.argv[2:])\n')
        (folder/'installation.json').write_text('{"schema":1,"current":"old"}')
        result=subprocess.run([sys.executable,folder/'run.py','guard','elden-ring','/usr/bin/touch',marker],cwd=folder,env=environment,capture_output=True)
        self.assertNotEqual(result.returncode,0);self.assertFalse(marker.exists())

    def test_log_discovery_and_controller_guide_are_not_live_evidence(self):
        self.install();self.f.file(self.game/'Game/ERVR/ERVR.log').write_text('Active VR backend: openxr\n[reshade] registered as add-on\n')
        self.f.file(self.game/'Game/ReShade.log').write_text('ReShade version 6.8.0.2155')
        report=log_diagnostics.report(self.recipe,[self.f.steam]);self.assertEqual(len(report['logs']),2)
        self.assertEqual(report['status'],'NO KNOWN SIGNATURES FOUND')
        from vrhub import controller_bindings
        guide=controller_bindings.load('elden-ring')
        self.assertTrue(all(r['evidence']=='default' for s in guide['sections'] for r in s['bindings']))

    def test_strict_game_handler_package_schema(self):
        for field,value in [('steam_appid',611670),('handler','valheim-vr'),('method','bepinex'),('store','manual')]:
            recipe=copy.deepcopy(self.recipe);recipe[field]=value
            with self.subTest(field=field),self.assertRaises(RecipeError):validate_recipe(recipe)
        recipe=copy.deepcopy(self.recipe);recipe['packages'].append(recipe['packages'][0])
        with self.assertRaises(RecipeError):validate_recipe(recipe)

    def test_launch_text_has_native_overrides_runtime_import_and_guard(self):
        text=hub.launch_options(self.recipe)
        for required in ['"dxgi,dinput8=n,b"','IMPORT_OPENXR_1_RUNTIMES=1','"$XDG_RUNTIME_DIR/wivrn/comp_ipc"','elden-ring','%command%']:
            self.assertIn(required,text)
        self.assertIsNone(hub.game_play_label(self.recipe))

    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Optional PySide6 is not installed')
    def test_eighth_game_gui_actions_and_sourced_controls(self):
        from PySide6.QtWidgets import QApplication
        from vrhub.gui import HubWindow
        app=QApplication.instance() or QApplication([])
        with mock.patch.object(HubWindow,'check_updates'),mock.patch.object(HubWindow,'scan_setup'), \
             mock.patch('vrhub.app_update_gui.HubUpdateController.startup'):
            window=HubWindow()
            try:
                self.assertEqual(window.table.rowCount(),9)
                row=next(i for i in range(9) if 'Elden Ring (' in window.table.item(i,0).text())
                window.table.selectRow(row);app.processEvents()
                self.assertTrue(window.install_btn.isEnabled())
                self.assertTrue(window.verify_btn.isEnabled());self.assertTrue(window.inspect_btn.isEnabled())
                self.assertFalse(window.inject_btn.isEnabled());self.assertFalse(window.profile_btn.isEnabled())
                self.assertTrue(window.game_play_btn.isHidden())
                text=window.controller_bindings.results.toPlainText()
                self.assertIn('Elden Ring',text);self.assertIn('Mod default',text)
                self.assertIn('UNVERIFIED',window.compat_details.toPlainText())
                self.assertFalse('SUCCESS' in window.compat_details.toPlainText())
            finally:window.close();app.processEvents()
