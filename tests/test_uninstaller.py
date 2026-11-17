from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts.server_manage import DEFAULT_REPOSITORY, Deployment, DeploymentError
from scripts.server_uninstall import Uninstaller, check_removal_tree


PROJECT = Path(__file__).resolve().parents[1]


class InactiveService:
    def active(self): return False
    def stop(self): pass
    def disable(self): pass
    def reload(self): pass


class UninstallerTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-uninstall-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "installation"
        self.units = self.base / "config/systemd/user"
        self.units.mkdir(parents=True)
        shared = self.root / "shared"
        (shared / "data").mkdir(parents=True)
        (shared / "data/account.txt").write_text("fixture account")
        (shared / "update-backups").mkdir()
        (shared / "update-backups/keep.txt").write_text("fixture backup")
        self.release = self.root / "releases/v9.0.0"
        self.release.mkdir(parents=True)
        (self.release / "server.py").write_text("# fixture")
        (self.root / "current").symlink_to(self.release)
        (self.root / "repository").mkdir()
        (self.root / ".update.lock").touch()
        self.config = {"service": "fixture.service", "port": 19111, "host": "127.0.0.1",
                       "installation_id": "a" * 32, "installation_root": str(self.root), "repository": DEFAULT_REPOSITORY}
        (shared / "server.json").write_text(json.dumps(self.config))
        self.unit = self.units / "fixture.service"
        self.unit.write_text(Deployment(self.root).unit_text(self.config))
        self.uninstaller = Uninstaller(self.root, unit_dir=self.units, service=InactiveService())

    def test_plan_has_no_side_effects(self):
        before = {str(path): path.stat().st_mtime_ns for path in self.base.rglob("*") if not path.is_symlink()}
        with contextlib.redirect_stdout(io.StringIO()):
            self.uninstaller.print_plan(self.uninstaller.plan())
        after = {str(path): path.stat().st_mtime_ns for path in self.base.rglob("*") if not path.is_symlink()}
        self.assertEqual(before, after)

    def test_unknown_root_file_blocks_removal(self):
        (self.root / "unrelated.txt").write_text("keep")
        with self.assertRaisesRegex(DeploymentError, "neznáme súbory"):
            self.uninstaller.uninstall(delete_data=True)
        self.assertTrue(self.unit.exists())

    def test_symlink_in_retained_data_blocks_default_removal(self):
        (self.root / "shared/data/code-link").symlink_to(self.release)
        with self.assertRaisesRegex(DeploymentError, "shared/ obsahuje odkaz"):
            self.uninstaller.uninstall()
        self.assertTrue(self.release.exists())

    def test_purge_does_not_follow_data_symlink(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "keep").write_text("keep")
        (self.root / "shared/data/link").symlink_to(outside)
        self.uninstaller.uninstall(delete_data=True)
        self.assertEqual((outside / "keep").read_text(), "keep")

    def test_symlinked_installation_is_refused(self):
        link = self.base / "alias"
        link.symlink_to(self.root)
        with self.assertRaises(DeploymentError):
            Uninstaller(link)

    def test_bind_mount_is_refused_even_if_ismount_would_miss_it(self):
        mounted = str(self.root / "shared/data/mounted").replace(" ", "\\040")
        with patch("scripts.server_uninstall.Path.read_text", return_value=f"30 20 0:12 / {mounted} rw - ext4 /dev/fixture rw\n"):
            with self.assertRaisesRegex(DeploymentError, "pripojený súborový systém"):
                check_removal_tree(self.root)

    def test_unit_override_and_wrong_identity_are_refused(self):
        override = self.unit.with_name("fixture.service.d")
        override.mkdir()
        with self.assertRaisesRegex(DeploymentError, "doplnky"):
            self.uninstaller.plan()
        override.rmdir()
        self.unit.write_text(self.unit.read_text().replace("a" * 32, "b" * 32))
        with self.assertRaisesRegex(DeploymentError, "iný identifikátor"):
            self.uninstaller.plan()

    def test_system_cleanup_failure_stops_before_code_removal(self):
        def fail(_plan):
            raise DeploymentError("fixture system failure")
        with self.assertRaises(DeploymentError):
            self.uninstaller.uninstall(system_cleanup=fail)
        self.assertFalse(self.unit.exists())
        self.assertTrue(self.release.exists())
        self.assertTrue((self.root / "shared/data/account.txt").exists())
        self.uninstaller.uninstall()
        self.assertFalse(self.release.exists())

    def test_data_is_preserved_and_external_paths_are_never_deleted(self):
        external = self.base / "external-config"
        external.write_text("keep")
        self.config["backup_paths"] = [str(external)]
        (self.root / "shared/server.json").write_text(json.dumps(self.config))
        self.uninstaller.uninstall()
        self.assertEqual(external.read_text(), "keep")
        self.assertEqual((self.root / "shared/data/account.txt").read_text(), "fixture account")
        self.assertEqual((self.root / "shared/update-backups/keep.txt").read_text(), "fixture backup")

    def environment(self):
        binaries = self.base / "bin"
        binaries.mkdir(exist_ok=True)
        systemctl = binaries / "systemctl"
        systemctl.write_text(f'''#!/bin/sh
case "$*" in
  *FragmentPath*) printf '%s\\n' '{self.unit}' ;;
  *ActiveState*) printf 'inactive\\n' ;;
  *LoadState*) printf 'loaded\\n' ;;
esac
exit 0
''')
        systemctl.chmod(0o755)
        return {**os.environ, "PATH": str(binaries) + os.pathsep + os.environ.get("PATH", ""), "XDG_CONFIG_HOME": str(self.units.parents[1])}

    def test_cli_plan_and_wizard_dispatch_write_nothing(self):
        before = {str(path) for path in self.root.rglob("*")}
        result = subprocess.run(["bash", str(PROJECT / "scripts/uninstall.sh"), "--root", str(self.root), "--plan"], text=True, capture_output=True, env=self.environment())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ZACHOVAŤ", result.stdout)
        self.assertIn("Iba plán", result.stdout)
        self.assertEqual(before, {str(path) for path in self.root.rglob("*")})
        result = subprocess.run(["bash", str(PROJECT / "scripts/install.sh"), "--plan"], input=f"5\n{self.root}\n", text=True, capture_output=True, env=self.environment())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Plán odinštalovania", result.stdout)
        self.assertEqual(before, {str(path) for path in self.root.rglob("*")})

    def test_cli_refuses_piping_and_automation(self):
        for extra in [[], ["--yes"]]:
            result = subprocess.run([sys.executable, "-B", str(PROJECT / "scripts/server_uninstall.py"), "--root", str(self.root), *extra], input="a\n", text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertTrue(self.unit.exists())

    def terminal(self, script, arguments, answers):
        master, slave = pty.openpty()
        process = subprocess.Popen(["bash", str(script), "--root", str(self.root), *arguments], stdin=slave, stdout=slave, stderr=slave, env=self.environment(), cwd=self.release)
        os.close(slave)
        output = bytearray()
        try:
            os.write(master, answers.encode())
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if select.select([master], [], [], 0.1)[0]:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk: break
                    output.extend(chunk)
                elif process.poll() is not None:
                    break
            self.assertEqual(process.wait(timeout=2), 0, output.decode(errors="replace"))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)
            os.close(master)
        return output.decode(errors="replace")

    @unittest.skipIf(os.geteuid() == 0, "Sprievodca je používateľský")
    def test_typed_purge_confirmation_is_required(self):
        output = self.terminal(PROJECT / "scripts/uninstall.sh", ["--delete-data"], "a\nwrong-root\n")
        self.assertIn("Cesta nesúhlasí", output)
        self.assertTrue(self.unit.exists())
        self.assertFalse((self.root / "shared/uninstall-state.json").exists())

    @unittest.skipIf(os.geteuid() == 0, "Sprievodca je používateľský")
    def test_running_release_can_remove_its_own_code(self):
        scripts = self.release / "scripts"
        scripts.mkdir()
        for name in ("uninstall.sh", "server_uninstall.py", "install_support.py", "server_manage.py", "system_changes.py"):
            shutil.copyfile(PROJECT / "scripts" / name, scripts / name)
        output = self.terminal(scripts / "uninstall.sh", [], "a\nn\n")
        self.assertIn("Odinštalovanie dokončené", output)
        self.assertFalse(self.release.exists())
        self.assertFalse(self.unit.exists())
        self.assertEqual((self.root / "shared/data/account.txt").read_text(), "fixture account")

    @unittest.skipIf(os.geteuid() == 0, "Sprievodca je používateľský")
    def test_terminal_purge_requires_exact_root_and_removes_only_that_root(self):
        output = self.terminal(PROJECT / "scripts/uninstall.sh", ["--delete-data"], f"a\n{self.root}\nn\n")
        self.assertIn("natrvalo odstránené", output)
        self.assertFalse(self.root.exists())
        self.assertTrue(self.units.exists())
        self.assertFalse(self.unit.exists())


if __name__ == "__main__":
    unittest.main()
