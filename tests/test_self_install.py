import fcntl
import ctypes
import ctypes.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from vrhub import __version__, guard, hub, self_install as installer

REPO = Path(__file__).resolve().parents[1]


class ManagedInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "Home with spaces"
        self.home.mkdir()
        self.source = self.base / "source"
        self.source.mkdir()
        shutil.copytree(REPO / "vrhub", self.source / "vrhub", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(REPO / "pyproject.toml", self.source / "pyproject.toml")
        self.state = self.home / ".local/share/vrhub/state.json"
        self.state.parent.mkdir(parents=True)
        self.state.write_text('{"saved": "installer record"}\n')
        (self.state.parent / "live-tests.json").write_text('{"history": "preserve byte for byte"}\n')
        (self.state.parent / "backups").mkdir()
        (self.state.parent / "backups/test.bin").write_bytes(b"game backup")
        self.data = {p: p.read_bytes() for p in self.state.parent.rglob("*") if p.is_file()}
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.home), "XDG_DATA_HOME": str(self.home / ".local/share"),
                                                "VRHUB_STATE": str(self.state), "_NANNERSVRHUB_ROOT": ""})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.root = installer.default_root()
        self.probe = mock.patch.object(installer, "_probe", side_effect=self.fake_probe)
        self.probe.start()
        self.addCleanup(self.probe.stop)

    def tearDown(self):
        for path, content in self.data.items():
            self.assertEqual(path.read_bytes(), content, str(path))

    def fake_probe(self, source, python):
        return {"version": installer._version(source / "vrhub"), "recipes": sorted(installer.EXPECTED_RECIPES), "qt": "test fixture"}

    def new_version(self, version):
        old = installer._version(self.source / "vrhub")
        for path in (self.source / "vrhub/__init__.py", self.source / "pyproject.toml"):
            path.write_text(path.read_text().replace(old, version))

    def install(self):
        return installer.install(self.source, self.root)

    def record(self):
        return json.loads((self.root / "installation.json").read_text())

    def invoke(self, name, *args):
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        return subprocess.run([str(self.root / "bin" / name), *args], cwd=self.base,
                              env=env, text=True, capture_output=True, timeout=15)

    def test_clean_install_runs_outside_source_and_has_resources(self):
        result = self.install()
        self.assertEqual(result["version"], __version__)
        record = self.record()
        self.assertIsNone(record["previous"])
        self.assertEqual((self.root / "installation.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.invoke("nannersvrhub", "--version").stdout.strip(), "NAnnersVRhub " + __version__)
        shutil.rmtree(self.source)
        result = self.invoke("nannersvrhub", "info", "fatekeeper")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Fatekeeper", result.stdout)
        for name in ("nannersvrhub", "nannersvrhub-check", "nannersvrhub-manage"):
            self.assertTrue((self.home / ".local/bin" / name).is_symlink())
            self.assertTrue(os.access(self.root / "bin" / name, os.X_OK))
        desktop = self.home / ".local/share/applications/io.github.BananaNanners.NAnnersVRhub.desktop"
        self.assertIn('" --desktop', desktop.read_text())
        self.assertIn(str(self.root / "icon.png"), desktop.read_text())

    def test_install_check_is_read_only(self):
        result = installer.install(self.source, self.root, check_only=True)
        self.assertEqual(result["status"], "CHECK PASSED")
        self.assertFalse(self.root.exists())
        self.assertFalse((self.home / ".local/bin").exists())

    def test_stale_in_app_update_cannot_replace_another_install(self):
        self.install()
        before = self.record()
        self.new_version("0.5.3")
        with self.assertRaisesRegex(RuntimeError, "active Hub version changed"):
            installer.install(self.source, self.root, expected_current="stale-version-id")
        self.assertEqual(self.record(), before)
        self.assertEqual(len(list((self.root / "releases").iterdir())), 1)

    def test_rollback_retains_the_new_recovery_manager(self):
        self.install()
        old = (self.root / "manage.py").read_bytes()
        self.new_version("0.5.3")
        source = self.source / "vrhub/self_install.py"
        source.write_bytes(source.read_bytes() + b"\n# newer independent manager\n")
        self.install()
        new = (self.root / "manage.py").read_bytes()
        self.assertNotEqual(old, new)
        installer.rollback(self.root)
        self.assertEqual((self.root / "manage.py").read_bytes(), new)
        installer.rollback(self.root)
        self.assertEqual((self.root / "manage.py").read_bytes(), new)

    def test_missing_new_declared_recipe_is_rejected(self):
        (self.source / "vrhub/recipes/hogwarts-legacy.toml").unlink()
        with self.assertRaisesRegex(RuntimeError, "hogwarts-legacy"):
            installer._source_files(self.source)

    def test_legacy_four_recipe_archives_remain_verifiable(self):
        (self.source / "vrhub/recipes/hogwarts-legacy.toml").unlink()
        project = self.source / "pyproject.toml"
        project.write_text(project.read_text().split("[tool.nannersvrhub]")[0])
        version, files = installer._source_files(self.source)
        self.assertEqual(version, __version__)
        self.assertIn("vrhub/recipes/fatekeeper.toml", files)

    def test_invalid_declared_recipe_path_is_rejected(self):
        project = self.source / "pyproject.toml"
        project.write_text(project.read_text().replace('"hogwarts-legacy"', '"../escape"'))
        with self.assertRaisesRegex(RuntimeError, "recipe inventory"):
            installer._source_files(self.source)
        self.assertFalse(self.root.exists())

    def test_missing_dependency_creates_no_installation(self):
        with mock.patch.object(installer, "_probe", side_effect=RuntimeError("missing PySide6")):
            with self.assertRaisesRegex(RuntimeError, "PySide6"):
                self.install()
        self.assertFalse(self.root.exists())

    def test_staged_version_mismatch_keeps_old_active_version(self):
        self.install()
        before = self.record()
        self.new_version("0.5.1-dev2")
        def changed(source, python):
            info = self.fake_probe(source, python)
            if source.name.startswith(".staging-"):
                info["version"] = "0.5.1-dev99"
            return info
        with mock.patch.object(installer, "_probe", side_effect=changed):
            with self.assertRaisesRegex(RuntimeError, "version changed"):
                self.install()
        self.assertEqual(self.record(), before)

    def test_upgrade_and_two_way_rollback_preserve_state_and_stable_guard(self):
        self.install()
        first = self.record()["current"]
        guard_path = self.root / "bin/nannersvrhub-check"
        self.new_version("0.5.1-dev2")
        self.install()
        second = self.record()["current"]
        self.assertNotEqual(first, second)
        self.assertEqual(self.record()["previous"], first)
        self.assertIn("0.5.1-dev2", self.invoke("nannersvrhub", "--version").stdout)
        self.assertEqual(installer.rollback(self.root)["version"], __version__)
        self.assertEqual(self.record()["current"], first)
        self.assertEqual(self.record()["previous"], second)
        self.assertIn(__version__, self.invoke("nannersvrhub", "--version").stdout)
        self.assertEqual(installer.rollback(self.root)["version"], "0.5.1-dev2")
        self.assertTrue(guard_path.is_file())
        self.assertTrue((self.root / "releases" / first).is_dir())
        self.assertTrue((self.root / "releases" / second).is_dir())
        code = "import json,sys; from vrhub import hub; print(hub.launch_options(hub.load_recipes()['cyberpunk-2077']))"
        current = self.root / "releases" / self.record()["current"]
        env = {**os.environ, "PYTHONPATH": str(current), "_NANNERSVRHUB_ROOT": str(self.root)}
        output = subprocess.check_output([sys.executable, "-c", code], cwd=self.base, env=env, text=True)
        self.assertIn(str(guard_path), output)
        self.assertNotIn(str(current), output)

    def test_reinstall_keeps_previous_version(self):
        self.install()
        first = self.record()["current"]
        self.new_version("0.5.1-dev2")
        self.install()
        record = self.record()
        self.install()
        self.assertEqual(self.record(), record)
        self.assertEqual(self.record()["previous"], first)

    def test_existing_shortcut_conflict_is_preserved(self):
        path = self.home / ".local/bin/nannersvrhub"
        path.parent.mkdir(parents=True)
        path.write_text("my own launcher")
        with self.assertRaisesRegex(RuntimeError, "preserved"):
            self.install()
        self.assertEqual(path.read_text(), "my own launcher")
        self.assertFalse((self.root / "installation.json").exists())
        self.assertFalse((self.root / "run.py").exists())

    def test_modified_desktop_blocks_upgrade_without_overwriting(self):
        self.install()
        before = (self.root / "installation.json").read_bytes()
        path = self.home / ".local/share/applications/io.github.BananaNanners.NAnnersVRhub.desktop"
        path.write_text(path.read_text() + "# customized\n")
        self.new_version("0.5.1-dev2")
        with self.assertRaisesRegex(RuntimeError, "preserved"):
            self.install()
        self.assertEqual((self.root / "installation.json").read_bytes(), before)
        self.assertTrue(path.read_text().endswith("# customized\n"))

    def test_activation_failure_restores_previous_launchers_and_record(self):
        self.install()
        before = {p: installer._snapshot(p) for p in [self.root / "installation.json", *installer._artifacts(
            self.root, str(Path(sys.executable).absolute()), installer._source_files(self.source)[1])]}
        self.new_version("0.5.1-dev2")
        real_apply = installer._apply
        failed = False

        def fail_once(path, value):
            nonlocal failed
            if path.name == "nannersvrhub-check" and not failed:
                failed = True
                raise OSError("simulated full disk")
            return real_apply(path, value)

        with mock.patch.object(installer, "_apply", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "full disk"):
                self.install()
        for path, snapshot in before.items():
            self.assertEqual(installer._snapshot(path), snapshot, str(path))

    def test_incomplete_or_mismatched_source_is_rejected(self):
        (self.source / "vrhub/recipes/fatekeeper.toml").unlink()
        with self.assertRaisesRegex(RuntimeError, "Incomplete"):
            self.install()
        self.assertFalse(self.root.exists())

    def test_version_mismatch_is_rejected(self):
        path = self.source / "pyproject.toml"
        path.write_text(path.read_text().replace(__version__, "0.5.1-dev99"))
        with self.assertRaisesRegex(RuntimeError, "labels"):
            self.install()

    def test_symlinked_source_is_rejected(self):
        path = self.source / "vrhub/assets/bananananners.png"
        path.unlink()
        path.symlink_to(REPO / "vrhub/assets/bananananners.png")
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            self.install()

    def test_unknown_or_corrupt_installation_record_is_preserved(self):
        self.install()
        path = self.root / "installation.json"
        path.write_text('{"schema": 99}')
        with self.assertRaisesRegex(RuntimeError, "preserved"):
            self.install()
        self.assertEqual(path.read_text(), '{"schema": 99}')

    def test_rollback_refuses_modified_previous_release(self):
        self.install()
        first = self.record()["current"]
        self.new_version("0.5.1-dev2")
        self.install()
        before = self.record()
        (self.root / "releases" / first / "vrhub/__init__.py").write_text("changed")
        with self.assertRaisesRegex(RuntimeError, "changed"):
            installer.rollback(self.root)
        self.assertEqual(self.record(), before)

    def test_standalone_manager_status_survives_broken_app_import(self):
        self.install()
        path = self.root / "releases" / self.record()["current"] / "vrhub/__init__.py"
        path.write_text("raise RuntimeError('broken app')")
        result = self.invoke("nannersvrhub-manage", "status")
        self.assertEqual(result.returncode, 1)
        self.assertIn("changed", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_standalone_manager_can_rollback_broken_current_app(self):
        self.install()
        first = self.record()["current"]
        self.new_version("0.5.1-dev2")
        self.install()
        (self.root / "releases" / self.record()["current"] / "vrhub/__init__.py").write_text("raise RuntimeError('broken app')")
        # This test mocks the dependency probe only, while running the actual
        # independent manager module loaded by file rather than through vrhub.
        import runpy
        manager = runpy.run_path(str(self.root / "manage.py"), run_name="independent_manager")
        manager["rollback"].__globals__["_probe"] = self.fake_probe
        manager["rollback"](self.root)
        self.assertEqual(self.record()["current"], first)
        self.assertIn(__version__, self.invoke("nannersvrhub", "--version").stdout)

    def test_root_and_state_overlap_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "separate"):
            installer.install(self.source, self.state.parent)
        self.assertFalse((self.state.parent / ".owner").exists())

    def test_unowned_root_contents_are_preserved(self):
        self.root.mkdir(parents=True)
        (self.root / "important.txt").write_text("keep")
        with self.assertRaisesRegex(RuntimeError, "not empty"):
            self.install()
        self.assertEqual((self.root / "important.txt").read_text(), "keep")

    def test_lock_prevents_concurrent_activation(self):
        with installer._locked(self.root):
            with self.assertRaisesRegex(RuntimeError, "Another"):
                self.install()

    def test_status_and_unavailable_rollback_do_not_create_root(self):
        self.assertEqual(installer.status(self.root)["status"], "NOT INSTALLED")
        with self.assertRaisesRegex(RuntimeError, "No previous"):
            installer.rollback(self.root)
        self.assertFalse(self.root.exists())

    def test_xdg_app_location_keeps_legacy_data_location(self):
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(self.home / "Other Data")}):
            root = installer.default_root()
            installer.install(self.source, root)
            self.assertTrue((self.home / "Other Data/applications/io.github.BananaNanners.NAnnersVRhub.desktop").is_file())
            self.assertEqual(hub.state_file(), self.state)


class GuardTests(unittest.TestCase):
    def test_missing_mod_blocks_game(self):
        with mock.patch.object(guard.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "missing mod\n", "")), \
             mock.patch.object(guard.shutil, "which", return_value=None), mock.patch.object(guard.os, "execvp") as execute:
            self.assertEqual(guard.main(["cyberpunk-2077", "/game", "arg with spaces"]), 1)
            execute.assert_not_called()

    def test_verification_error_preserves_fail_open_behavior(self):
        with mock.patch.dict(os.environ, {"VRHUB_SKIP_CHECK": ""}), \
             mock.patch.object(guard.subprocess, "run", return_value=subprocess.CompletedProcess([], 2, "", "broken checker")), \
             mock.patch.object(guard.os, "execvp") as execute:
            guard.main(["game", "/game", "arg with spaces"])
            execute.assert_called_once_with("/game", ["/game", "arg with spaces"])

    def test_skip_check_and_argument_preservation(self):
        with mock.patch.dict(os.environ, {"VRHUB_SKIP_CHECK": "1"}), \
             mock.patch.object(guard.subprocess, "run") as run, mock.patch.object(guard.os, "execvp") as execute:
            guard.main(["game", "/game", "$literal", "arg with spaces"])
            run.assert_not_called()
            execute.assert_called_once_with("/game", ["/game", "$literal", "arg with spaces"])

    def test_missing_command_prints_usage(self):
        self.assertEqual(guard.main(["game"]), 2)


class DesktopTests(unittest.TestCase):
    def test_steam_guard_path_is_one_literal_shell_argument(self):
        path = Path('/home/space $100%/"quote"/nannersvrhub-check')
        with mock.patch('vrhub.hub.guard_path', return_value=path):
            options = hub.launch_options({"id": "example", "components": [{"name": "fixture"}]})
        self.assertEqual(shlex.split(options), [str(path), "example", "%command%"])

    def test_exec_escapes_spaces_percent_and_reserved_characters(self):
        self.assertEqual(installer._desktop_exec(Path('/home/User Space/app')), '"/home/User Space/app"')
        self.assertEqual(installer._desktop_exec(Path('/home/100%/app')), '"/home/100%%/app"')
        self.assertEqual(installer._desktop_exec(Path('/home/$test/"app')), '"/home/\\\\$test/\\\\"app"')

    @unittest.skipUnless(ctypes.util.find_library("gio-2.0"), "GIO desktop parser is not installed")
    def test_actual_desktop_launch_handles_percent_and_shell_characters(self):
        gio = ctypes.CDLL(ctypes.util.find_library("gio-2.0"))
        gio.g_desktop_app_info_new_from_filename.argtypes = [ctypes.c_char_p]
        gio.g_desktop_app_info_new_from_filename.restype = ctypes.c_void_p
        gio.g_app_info_launch.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        gio.g_app_info_launch.restype = ctypes.c_int
        gio.g_object_unref.argtypes = [ctypes.c_void_p]
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            root = base / 'Space $100% `tick` "quote" and slash\\'
            executable = root / "bin/nannersvrhub"
            executable.parent.mkdir(parents=True)
            output = base / "launch-arguments.json"
            executable.write_text("#!" + sys.executable + "\nimport json,sys\nfrom pathlib import Path\nPath(" +
                                  repr(str(output)) + ").write_text(json.dumps(sys.argv))\n")
            executable.chmod(0o755)
            artifacts = installer._artifacts(root, sys.executable, {
                "vrhub/self_install.py": b"fixture", "vrhub/assets/bananananners.png": b"fixture"})
            content = next(v[1] for p, v in artifacts.items() if p.suffix == ".desktop")
            desktop = base / "test.desktop"
            desktop.write_bytes(content)
            app = gio.g_desktop_app_info_new_from_filename(str(desktop).encode())
            self.assertTrue(app, "Desktop parser rejected the generated launcher")
            try:
                error = ctypes.c_void_p()
                self.assertTrue(gio.g_app_info_launch(app, None, None, ctypes.byref(error)))
            finally:
                gio.g_object_unref(app)
            deadline = time.monotonic() + 3
            while not output.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertEqual(json.loads(output.read_text()), [str(executable), "--desktop"])


if __name__ == "__main__":
    unittest.main()
