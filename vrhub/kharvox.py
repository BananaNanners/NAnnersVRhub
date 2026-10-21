"""KHARVOX 1.4 package checks and native Heroic/GOG launch planning.

Reads metadata only until the user explicitly launches KHARVOX. Never edits the
Heroic prefix, registry, game installation, launcher manifest or mod settings.
"""
import json
import os
from pathlib import Path
import re
import shutil

from . import heroic, self_install
from .bepinex import digest
from .elden_ring import file_version

RELEASE = "https://github.com/CactusVRStudios/KHARVOX/releases/tag/v1.4.0"
ARCHIVE_SHA256 = "83aed75e8b36673a640bf32580bfb3b116884b4db200746e386d4e1d397762f4"
GOG_SHA256 = "a32df8ffa042090f14fe0a200f1c5d7dddf9c947fac223916c252f826f1ecf11"
VERSIONS = {"KharvoxLauncher.exe": "1.4.0.1404", "KharvoxLayer.dll": "1.4.0.1402"}


def settings_file():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config'))) / 'vrhub/kharvox.json'


def regular(root, relative):
    path = root / relative
    return path.is_file() and path.resolve().is_relative_to(root.resolve()) and not any(
        p.is_symlink() for p in (path, *path.parents) if p != root and root in p.parents)


def versions_match(root):
    return all(regular(root, name) and file_version(root/name) == version for name, version in VERSIONS.items())


def directory():
    path = settings_file()
    if path.exists():
        try:
            data = json.loads(path.read_text())
            if not isinstance(data, dict) or not isinstance(data.get('directory'), str) or not Path(data['directory']).is_absolute():
                raise ValueError('invalid path')
            return Path(data['directory'])
        except (ValueError, OSError) as exc:
            raise RuntimeError('Saved KHARVOX folder could not be read. Use Choose KHARVOX folder… to select it again.') from exc
    explicit = os.environ.get('NANNERS_KHARVOX_DIR', '').strip()
    if explicit:
        return Path(explicit).expanduser().absolute()
    candidates = set()
    for parent in [Path.home()/'Games', Path.home()/'Applications', Path.home()/'Downloads', Path.home()]:
        if not parent.is_dir():
            continue
        for path in parent.iterdir():
            if not path.is_dir() or not path.name.casefold().startswith('kharvox'):
                continue
            if (path/'KharvoxLauncher.exe').is_file():
                candidates.add(path.resolve())
            for child in path.iterdir():
                if child.is_dir() and (child/'KharvoxLauncher.exe').is_file():
                    candidates.add(child.resolve())
    current = [p for p in candidates if versions_match(p)]
    if len(current) == 1:
        return current[0]
    if len(current) > 1:
        raise RuntimeError('Several KHARVOX 1.4 folders were found. Use Choose KHARVOX folder… to select the intended copy.')
    # Surface an old/partial extraction in diagnostics, but never launch it.
    return next(iter(candidates)) if len(candidates) == 1 else None


def package_rows(root):
    if not root or not root.is_dir() or root.is_symlink():
        return [{'name':'KHARVOX 1.4 folder','ok':False,'required':True,
                 'detail':'Extract the complete KHARVOX-v1.4.zip outside DOOM and use Choose KHARVOX folder….'}]
    missing = [name for name in REQUIRED_FILES if not regular(root,name)]
    changed = [name for name, sha in BINARY_HASHES.items() if regular(root,name) and digest(root/name) != sha]
    rows = [{'name':'KHARVOX package inventory','ok':not missing,'required':True,
             'detail':f'{len(REQUIRED_FILES)-len(missing)}/{len(REQUIRED_FILES)} files present in {root}; presence is not loading evidence.' +
             (' Missing/unsafe: '+', '.join(missing[:5]) if missing else '')},
            {'name':'KHARVOX release binaries','ok':not missing and not changed,'required':True,
             'detail':'Eight EXE/DLL hashes compared with the inspected 1.4 release; settings/shaders are not version-certified.' +
             (' Changed: '+', '.join(changed) if changed else '')}]
    for name, version in VERSIONS.items():
        found = file_version(root/name) if regular(root,name) else None
        rows.append({'name':'KHARVOX '+name+' version','ok':found == version,'required':True,
                     'detail':f'Expected {version}; found {found or "missing/unknown"}. Metadata only; not loaded.'})
    return rows


def choose_directory(path, game=None):
    path = Path(path).expanduser().absolute()
    if game and path.resolve().is_relative_to(game.resolve()):
        raise RuntimeError('Extract KHARVOX into its own folder outside the DOOM installation.')
    bad = [r['detail'] for r in package_rows(path) if not r['ok']]
    if bad:
        raise RuntimeError('\n'.join(bad))
    self_install._atomic(settings_file(), (json.dumps({'directory':str(path)})+'\n').encode())


def prefix(recipe):
    raw = heroic.game_settings(recipe['heroic_appid']).get('winePrefix')
    if not isinstance(raw,str) or not raw.strip() or not Path(raw).expanduser().is_absolute():
        raise RuntimeError('Heroic has no absolute saved DOOM prefix. Review the game settings in Heroic.')
    base = Path(raw).expanduser().resolve()
    direct, nested = (base/'drive_c').is_dir(), (base/'pfx/drive_c').is_dir()
    if direct and nested and (base/'pfx').resolve() != base:
        raise RuntimeError('Both direct and nested DOOM prefixes exist. Review this ambiguous Heroic layout.')
    if direct:
        return base
    if nested:
        return (base/'pfx').resolve()
    raise RuntimeError('Heroic’s existing DOOM prefix was not found. Launch the flat game once in Heroic first.')


def temp_dir(recipe):
    base = prefix(recipe)
    users = base/'drive_c/users'
    preferred = users/'steamuser/AppData/Local/Temp'
    if (users/'steamuser/AppData').is_dir():
        return preferred
    found = [p/'AppData/Local/Temp' for p in users.iterdir() if p.is_dir() and p.name.casefold() != 'public' and (p/'AppData').is_dir()] if users.is_dir() else []
    if len(found) == 1:
        return found[0]
    raise RuntimeError('The DOOM prefix Windows user is missing or ambiguous; automatic log discovery is unavailable.')


def logs(recipe):
    base = temp_dir(recipe)
    return {k:base/name for k,name in [('main','KHARVOX.log'),('native','KHARVOX-NATIVE-STEREO.log'),
                                     ('errors','KHARVOX-launcher-errors.log'),('intro','KHARVOX-VR-INTRO.log')]}


def game_row(game):
    exe = game/'DOOMx64vk.exe' if game else None
    present = bool(exe and regular(game,'DOOMx64vk.exe'))
    actual = digest(exe) if present else None
    return {'name':'KHARVOX GOG Vulkan executable','ok':actual == GOG_SHA256,'required':True,
            'detail':(f'{exe}; SHA-256 {actual}. Compared with upstream GOG 2025-02-25 profile; not a live test.'
                      if present else 'DOOMx64vk.exe missing; DOOMx64.exe is OpenGL and is not supported by KHARVOX.')}


def _host_plan(recipe, game):
    if os.environ.get('FLATPAK_ID') or '/.var/app/' in str(heroic.config_root()):
        raise RuntimeError('This one-click route supports native Heroic. Use your Heroic/Wine launch workflow for a Flatpak installation.')
    if not game or not game_row(game)['ok']:
        raise RuntimeError('Select the complete, supported GOG DOOM Vulkan installation. Review Preflight; no game files were changed.')
    pfx = prefix(recipe)
    root = directory()
    if not root or root.resolve().is_relative_to(game.resolve()):
        raise RuntimeError('Select a complete KHARVOX 1.4 folder outside DOOM with Choose KHARVOX folder….')
    bad = [r['detail'] for r in package_rows(root) if not r['ok']]
    if bad:
        raise RuntimeError('\n'.join(bad))
    settings = heroic.game_settings(recipe['heroic_appid'])
    wine = settings.get('wineVersion',{})
    binary = wine.get('bin') if isinstance(wine,dict) else None
    runner = Path(binary).expanduser() if isinstance(binary,str) and binary else Path()
    if not isinstance(wine,dict) or wine.get('type') != 'proton' or not runner.is_absolute() or not runner.is_file() or not os.access(runner,os.X_OK) or runner.name != 'proton':
        raise RuntimeError('Heroic’s selected Proton runner is unavailable on the host. Review DOOM’s saved runner in Heroic.')
    umu = shutil.which('umu-run')
    if not umu:
        raise RuntimeError('umu-run was not found. Install/review your native Heroic umu setup before launching KHARVOX.')
    env = dict(os.environ)
    protected = {'WINEPREFIX','WINEARCH','WINESERVER','WINELOADER','WINEDLLOVERRIDES','PROTONPATH','PROTON_VERB',
                 'SteamAppId','SteamGameId','GAMEID','STORE','UMU_NO_PROTON','UMU_CONTAINER_NSENTER'}
    for key in list(env):
        if key.startswith('STEAM_COMPAT_') or key in protected:
            env.pop(key,None)
    options = settings.get('enviromentOptions',[])
    if not isinstance(options,list):
        raise RuntimeError('Heroic’s saved environment is invalid. Review/save it in Heroic first.')
    for row in options:
        if not isinstance(row,dict) or not isinstance(row.get('key'),str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',row['key']) or not isinstance(row.get('value'),str) or '\0' in row['value']:
            raise RuntimeError('Heroic’s saved environment is invalid. Review/save it in Heroic first.')
        if row['key'] not in protected and not row['key'].startswith('STEAM_COMPAT_'):
            value = row['value']
            env[row['key']] = value[1:-1] if len(value)>=2 and value[0] == value[-1] and value[0] in "\"'" else value
    # Keep Windows layer activation in KHARVOX's child, never in host Vulkan.
    env.pop('KHARVOX_ENABLE_LAYER',None)
    env.pop('KHARVOX_DISABLE_LAYER',None)
    layers = [p for p in env.get('VK_INSTANCE_LAYERS','').split(':') if p and p != 'VK_LAYER_KHARVOX_OPENXR']
    if layers: env['VK_INSTANCE_LAYERS'] = ':'.join(layers)
    else: env.pop('VK_INSTANCE_LAYERS',None)
    for key in ['VK_LAYER_PATH','VK_IMPLICIT_LAYER_PATH']:
        if env.get(key) and Path(env[key]).expanduser().resolve() == root.resolve():
            env.pop(key,None)
    env.update(WINEPREFIX=str(Path(settings['winePrefix']).expanduser().resolve()),
               PROTONPATH=str(runner.parent.resolve()), GAMEID='0', STORE='gog', UMU_RUNTIME_UPDATE='0')
    env.setdefault('PRESSURE_VESSEL_IMPORT_OPENXR_1_RUNTIMES','1')
    runtime = env.get('XDG_RUNTIME_DIR')
    if runtime and Path(runtime).is_absolute():
        ipc = str(Path(runtime)/'wivrn/comp_ipc')
        mounts = [p for p in env.get('PRESSURE_VESSEL_FILESYSTEMS_RW','').split(':') if p]
        if ipc not in mounts: mounts.append(ipc)
        env['PRESSURE_VESSEL_FILESYSTEMS_RW'] = ':'.join(mounts)
    return [umu,str(root/'KharvoxLauncher.exe')], env, str(root)


def plan(recipe, game):
    from . import kharvox_bridge
    return kharvox_bridge.plan(recipe, game, 'doom')


def launch(recipe, game):
    from . import kharvox_bridge
    return kharvox_bridge.start(recipe, game, 'doom')

REQUIRED_FILES = ('Fsr1Easu.spv',
 'Fsr1Rcas.spv',
 'HandPbr.frag.spv',
 'HandPbr.vert.spv',
 'KharvoxBhapticsBridge.exe',
 'KharvoxIntro.exe',
 'KharvoxLauncher.exe',
 'KharvoxLauncher.exe.config',
 'KharvoxLayer.dll',
 'KharvoxLayer.json',
 'KharvoxPsvr2Bridge.exe',
 'THIRD_PARTY_NOTICES.md',
 'assets/3D/DOOM_LEFT_HAND_FIST.glb',
 'assets/3D/DOOM_LEFT_HAND_GUN.glb',
 'assets/3D/DOOM_RIGHT_HAND_FIST.glb',
 'assets/3D/DOOM_RIGHT_HAND_GUN.glb',
 'assets/branding/quest-controller-mapping.png',
 'bhaptics_library.dll',
 'hand_models.cfg',
 'hand_models_calibration_default.cfg',
 'hud_flat_calibration_default.cfg',
 'hud_profile_calibration_default.cfg',
 'hud_quad_scale_default.cfg',
 'native_sfs_build.txt',
 'offhand_hud.cfg',
 'offhand_hud_default.cfg',
 'openxr_loader.dll',
 'psvr2_toolkit_capi_loader.dll',
 'sfs-compiler-licenses/README.md',
 'sfs-compiler-licenses/SPIRV-Cross.txt',
 'sfs-compiler-licenses/SPIRV-Tools.txt',
 'sfs-compiler-licenses/glslang.txt',
 'sfs-profile/2047418e3f6ad5a_20d5a8b9b6318ac0_VS.vert.spv',
 'sfs-profile/2047418e3f6ad5a_28ffaf3a937ef73e_VS.vert.spv',
 'sfs-profile/2047418e3f6ad5a_c0894bb81ffa8792_VS.vert.spv',
 'sfs-profile/21bed4cf1ab00661_15f6acac3f23582a_VS.vert.spv',
 'sfs-profile/21bed4cf1ab00661_4f4f05970f873d1e_VS.vert.spv',
 'sfs-profile/21bed4cf1ab00661_55f36d45b0f2c756_VS.vert.spv',
 'sfs-profile/21bed4cf1ab00661_62be81f0629b6db_VS.vert.spv',
 'sfs-profile/21bed4cf1ab00661_6bbf2310aaf14740_VS.vert.spv',
 'sfs-profile/21bed4cf1ab00661_8d0f2cc7d71ce750_VS.vert.spv',
 'sfs-profile/21bed4cf1ab00661_921e68bf0c61a1ae_VS.vert.spv',
 'sfs-profile/21bed4cf1ab00661_9831681b881da961_VS.vert.spv',
 'sfs-profile/21bed4cf1ab00661_a4b236c9ec8ecdf5_VS.vert.spv',
 'sfs-profile/21bed4cf1ab00661_a7c8d14602db51ea_VS.vert.spv',
 'sfs-profile/21bed4cf1ab00661_ba368d33987e1fab_VS.vert.spv',
 'sfs-profile/233ed843b61e7985_1e0f50d3510b7450_VS.vert.spv',
 'sfs-profile/233ed843b61e7985_69a0402263f99195_VS.vert.spv',
 'sfs-profile/233ed843b61e7985_bab563e14dcc1ab7_VS.vert.spv',
 'sfs-profile/23d4de41fcd07b9b_dad36c6fdd6d4e44_PS.frag.spv',
 'sfs-profile/2442216e2e8dd832_8ef075512c556dc4_VS.vert.spv',
 'sfs-profile/2442216e2e8dd832_f14e8592370e4eab_VS.vert.spv',
 'sfs-profile/283ca387dc09090d_b94933317479f6d4_PS.frag.spv',
 'sfs-profile/2bae4272f89ac0d2_d05ae7382167326c_PS.frag.spv',
 'sfs-profile/311480372cb80726_8bb8b80fc1a81bf_PS.frag.spv',
 'sfs-profile/34e3710ff851c869_ee16a5154f27820a_PS.frag.spv',
 'sfs-profile/3bb3c0a11d96264d_3af66ecd7e2ef076_PS.frag.spv',
 'sfs-profile/3bb3c0a11d96264d_ac05c8a6b11e5616_PS.frag.spv',
 'sfs-profile/5b61e96698b2642c_d797792131ee4498_VS.vert.spv',
 'sfs-profile/5d8a0b69a38eb2a0_1613515c70b06cc6_VS.vert.spv',
 'sfs-profile/5d8a0b69a38eb2a0_37b4725b9f3bfe03_VS.vert.spv',
 'sfs-profile/61d26e466ae9911a_PS.frag.spv',
 'sfs-profile/624b45e8d80618d0_585cb84c5f213f73_PS.frag.spv',
 'sfs-profile/7a3ba2e56552169_8be3d2b2be954095_PS.frag.spv',
 'sfs-profile/8afa2beaa03921eb_CS.comp.spv',
 'sfs-profile/a760518252dc0c5e_2a59680d11420c80_VS.vert.spv',
 'sfs-profile/a760518252dc0c5e_6ba027878f733c06_VS.vert.spv',
 'sfs-profile/a760518252dc0c5e_89443ec65ed15df2_VS.vert.spv',
 'sfs-profile/a760518252dc0c5e_VS.vert.spv',
 'sfs-profile/a760518252dc0c5e_a5d10724444790fe_VS.vert.spv',
 'sfs-profile/a760518252dc0c5e_b299d288a841675b_VS.vert.spv',
 'sfs-profile/a760518252dc0c5e_b36110173c2e20c8_VS.vert.spv',
 'sfs-profile/a760518252dc0c5e_c3f687c6960694a6_VS.vert.spv',
 'sfs-profile/a760518252dc0c5e_c93915dfeea3a558_VS.vert.spv',
 'sfs-profile/a760518252dc0c5e_dc70c62b7699bb07_VS.vert.spv',
 'sfs-profile/a760518252dc0c5e_dd9957bdd0bd9a41_VS.vert.spv',
 'sfs-profile/a76c72f0e77a9673_1a7fc7e603c13142_VS.vert.spv',
 'sfs-profile/a76c72f0e77a9673_3c843cf74dd30dae_VS.vert.spv',
 'sfs-profile/a76c72f0e77a9673_5a1547236b00ccc9_VS.vert.spv',
 'sfs-profile/b8760e2cd1c1b304_c8ba6182190585b0_VS.vert.spv',
 'sfs-profile/bafd968ef7df4692_9c2239f93495f67c_VS.vert.spv',
 'sfs-profile/bd75da4d50231e04_PS.frag.spv',
 'sfs-profile/bfe07c0adb6207d7_2b81f08d00340658_VS.vert.spv',
 'sfs-profile/bfe07c0adb6207d7_4e069c65a6ada6d7_VS.vert.spv',
 'sfs-profile/bfe07c0adb6207d7_67418263805b7ad7_VS.vert.spv',
 'sfs-profile/bfe07c0adb6207d7_baa86fe1481a6aa9_VS.vert.spv',
 'sfs-profile/bfe07c0adb6207d7_bf9c8bb65c761c7_VS.vert.spv',
 'sfs-profile/c156871ac68a269b_9d5c49f9201fc59d_VS.vert.spv',
 'sfs-profile/c757868ee21edb47_81c94152c2158ed9_VS.vert.spv',
 'sfs-profile/c757868ee21edb47_8d84038a3d6ad883_VS.vert.spv',
 'sfs-profile/c757868ee21edb47_b75073cf24d7ccd1_VS.vert.spv',
 'sfs-profile/c757868ee21edb47_ceaddd0793773049_VS.vert.spv',
 'sfs-profile/cac490d4f64a1682_ad6bb6042d8d7e1b_VS.vert.spv',
 'sfs-profile/cb1e40aa33c7d93e_3d6d22a061cd1dd9_VS.vert.spv',
 'sfs-profile/d717c54bb16f18c1_32834af21596b7f0_VS.vert.spv',
 'sfs-profile/d717c54bb16f18c1_4588755c9d1dacf9_VS.vert.spv',
 'sfs-profile/d717c54bb16f18c1_53edf66d431edab0_VS.vert.spv',
 'sfs-profile/d717c54bb16f18c1_63812549663dc6_VS.vert.spv',
 'sfs-profile/d717c54bb16f18c1_fb83182bbe99c9da_VS.vert.spv',
 'sfs-profile/d75f7da2605fa4c2_PS.frag.spv',
 'sfs-profile/d7790e0979cc584f_bf99c9e0d91d7f62_VS.vert.spv',
 'sfs-profile/d7790e0979cc584f_e0aec679e58ee8ad_VS.vert.spv',
 'sfs-profile/d7790e0979cc584f_e1885a82fa1d0021_VS.vert.spv',
 'sfs-profile/d7790e0979cc584f_fb6578bc8002b789_VS.vert.spv',
 'sfs-profile/e671b5dec2461b5c_e63b322ea804d721_VS.vert.spv',
 'sfs-profile/e8cec2ff1ad1b03b_CS.comp.spv',
 'sfs-profile/f70ac337f3d62c58_54556c85f0a82dc4_VS.vert.spv',
 'sfs_source_ring',
 'two_hand_weapon_profiles_default.cfg',
 'weapon_pitch_default.cfg',
 'weapon_roll_default.cfg',
 'weapon_yaw_default.cfg')
BINARY_HASHES = {'KharvoxBhapticsBridge.exe': 'b2698c9e1e3c69edc858eeee33d803bbc0eab48c789dfc68ff7ea08faa489e23',
 'KharvoxIntro.exe': 'ca9dcdbeadcddaf7f69cad408987fe2a9b34595f4e95b0a57375bccf13e8dfd9',
 'KharvoxLauncher.exe': '10f2c851a36bb4ae9628feae7fdc878c0e658afcd5d1a33f93bdc5ce45831f8f',
 'KharvoxLayer.dll': '9de993baa77641746aee5c9565e0d4e1b8b8e9a064f1fd62da4f77dea1826763',
 'KharvoxPsvr2Bridge.exe': '11b679d439c533c423aad80dbc7c9705f50ed138c4cdc625ebaf29bf3ec14ac2',
 'bhaptics_library.dll': '909124baed4467aa0c85b1a25bc84065ffc65030f3199c13ea7a18403434ce52',
 'openxr_loader.dll': '5a2b18579a8647ef4dd79aad807af143afee45a1d58dea2186ee22a96dd84516',
 'psvr2_toolkit_capi_loader.dll': 'e366143796fbb90edcb5cfb61afb05c7baa3e27ebaabe209bd7df16a3adced16'}
