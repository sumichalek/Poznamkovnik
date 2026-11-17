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
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import install_support as support
from scripts.server_manage import DEFAULT_REPOSITORY, DeploymentError, validate_repository


PROJECT = Path(__file__).resolve().parents[1]


class InstallerSupportTest(unittest.TestCase):
    def test_repository_credentials_are_rejected_without_echoing_them(self):
        for value in ["https://person:SECRET@github.com/a/b.git", "https://SECRET@github.com/a/b.git",
                      "https://github.com/a/b.git?token=SECRET", "https://github.com/a/b.git#SECRET"]:
            with self.subTest(value=value), self.assertRaises(DeploymentError) as caught:
                validate_repository(value)
            self.assertNotIn("SECRET", str(caught.exception))

    def test_supported_remote_addresses_and_explicit_local_testing(self):
        for value in [DEFAULT_REPOSITORY, "git@github.com:a/b.git", "ssh://git@github.com/a/b.git", "https://github.com/a/b.git"]:
            self.assertEqual(validate_repository(value), value)
        with self.assertRaises(DeploymentError):
            validate_repository("/tmp/example")
        self.assertEqual(validate_repository("/tmp/example", allow_local=True), "/tmp/example")

    def test_git_check_only_reads_remote_refs(self):
        with patch.object(support, "command", return_value=SimpleNamespace(returncode=0, stdout="commit\trefs/tags/v9.0.0\n")) as command, contextlib.redirect_stdout(io.StringIO()):
            support.check_git(DEFAULT_REPOSITORY, "v9.0.0")
        command.assert_called_once_with("git", "ls-remote", "--exit-code", "--tags", "--", DEFAULT_REPOSITORY, "refs/tags/v9.0.0", timeout=30)

    def test_git_failure_and_missing_tag_are_distinct_and_redacted(self):
        for code, expected in [(2, "tag sa nenašiel"), (128, "DNS/Pi-hole")]:
            with self.subTest(code=code), patch.object(support, "command", return_value=SimpleNamespace(returncode=code, stderr="TOKEN_SECRET", stdout="")), self.assertRaises(DeploymentError) as caught:
                support.check_git(DEFAULT_REPOSITORY, "v9.0.0")
            self.assertIn(expected, str(caught.exception))
            self.assertNotIn("TOKEN_SECRET", str(caught.exception))

    def test_bad_tag_is_rejected_before_network(self):
        with patch.object(support, "command") as command, self.assertRaises(DeploymentError):
            support.check_git(DEFAULT_REPOSITORY, "main")
        command.assert_not_called()

    def test_invalid_existing_origin_does_not_fall_back(self):
        with patch.object(support, "command", return_value=SimpleNamespace(returncode=0, stdout="https://SECRET@github.com/a/b.git")):
            with self.assertRaises(DeploymentError):
                support.repository_url(Path("/tmp/example"))
            self.assertEqual(support.default_repository(Path("/tmp/example")), DEFAULT_REPOSITORY)

    def test_root_rejects_broad_or_symlinked_directories(self):
        for path in [Path("/"), Path.home(), PROJECT]:
            with self.subTest(path=path), self.assertRaises(DeploymentError):
                support.safe_root(str(path))
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            (base / "real").mkdir()
            (base / "link").symlink_to(base / "real", target_is_directory=True)
            with self.assertRaises(DeploymentError):
                support.safe_root(str(base / "link/installation"))

    def test_release_script_infers_custom_installation_root(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "custom"
            script_dir = root / "releases/v9.0.0/scripts"
            script_dir.mkdir(parents=True)
            (root / "shared").mkdir()
            (root / "shared/server.json").write_text("{}")
            self.assertEqual(support.default_root(script_dir), root)

    def test_preflight_port_conflict_does_not_create_root_or_stop_process(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "installation"
            with patch.object(support.socket, "socket", side_effect=OSError("address in use")), self.assertRaisesRegex(DeploymentError, "existujúci proces sa nevypne"):
                support.preflight(target, "127.0.0.1", 19111, "installer-test.service", new=True)
            self.assertFalse(target.exists())

    def test_preflight_refuses_full_disk(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "installation"
            with patch.object(support.shutil, "disk_usage", return_value=SimpleNamespace(free=0)), contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(DeploymentError, "256 MiB"):
                support.preflight(target, "127.0.0.1", 19111, "installer-test.service", new=False)
            self.assertFalse(target.exists())

    def test_backup_list_skips_corrupt_unverified_and_symlinked_entries(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            directory = root / "shared/update-backups"
            directory.mkdir(parents=True)
            good = directory / "before-good"
            good.mkdir()
            (good / "VERIFIED").write_text("marker")
            (good / "manifest.json").write_text(json.dumps({"time": "2026-10-29T12:00:00+00:00", "previous": None}))
            broken = directory / "before-broken"
            broken.mkdir()
            (broken / "VERIFIED").touch()
            (broken / "manifest.json").write_text("invalid json")
            (directory / "before-link").symlink_to(good, target_is_directory=True)
            unverified = directory / "before-unverified"
            unverified.mkdir()
            (unverified / "manifest.json").write_text((good / "manifest.json").read_text())
            self.assertEqual(support.backup_rows(root), [("before-good", "2026-10-29T12:00:00+00:00", "pred prvou inštaláciou")])

    def test_plan_repompts_invalid_inputs_and_never_runs_external_actions(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "trial"
            answers = f"invalid\n1\n{target}\nmain\nv9.0.0\nwrong-port\n19111\n3\n2\ninvalid\nn\nn\nn\n"
            result = subprocess.run(["bash", str(PROJECT / "scripts/install.sh"), "--plan"], input=answers, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Iba plán", result.stdout)
            self.assertIn("Neplatná voľba", result.stdout)
            self.assertIn("Port musí byť", result.stdout)
            self.assertIn("DNS, Pi-hole", result.stdout)
            self.assertFalse(target.exists())

    def test_plan_does_not_create_import_cache_in_clean_bootstrap(self):
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw) / "bootstrap"
            scripts = project / "scripts"
            scripts.mkdir(parents=True)
            for name in ["install.sh", "install_support.py", "server_manage.py"]:
                shutil.copyfile(PROJECT / "scripts" / name, scripts / name)
            (project / "VERSION").write_text("9.0.0\n")
            before = {str(path) for path in project.rglob("*")}
            result = subprocess.run(["bash", str(scripts / "install.sh"), "--plan"], input=f"1\n{raw}/trial\nv9.0.0\n19111\n1\nn\nn\nn\n", text=True, capture_output=True, cwd=raw)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(before, {str(path) for path in project.rglob("*")})


@unittest.skipIf(os.geteuid() == 0, "Používateľský sprievodca odmieta root")
class InstallerTerminalFlowTest(unittest.TestCase):
    """Real Bash prompts in a PTY; helper, manager and system commands are simulated."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-wizard-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.scripts = self.base / "bootstrap/scripts"
        self.scripts.mkdir(parents=True)
        shutil.copyfile(PROJECT / "scripts/install.sh", self.scripts / "install.sh")
        (self.scripts.parent / "VERSION").write_text("9.0.0\n")
        self.target = self.base / "installation"
        self.calls = self.base / "calls.jsonl"
        self.manager_calls = self.base / "manager.json"
        helper = f'''import json, sys
from pathlib import Path
with Path({str(self.calls)!r}).open('a') as stream:
    stream.write(json.dumps(sys.argv[1:]) + '\\n')
action = sys.argv[1]
if action == 'default-root': print({str(self.target)!r})
elif action == 'validate-root': print(sys.argv[2])
elif action in ('default-repository', 'repository'): print({DEFAULT_REPOSITORY!r})
elif action == 'config': print('127.0.0.1\\n19111\\nfixture.service')
elif action == 'backups': print('before-fixture\\t2026-10-29T12:00:00+00:00\\tv9.0.0')
else: print('Simulovaná kontrola: OK')
'''
        (self.scripts / "install_support.py").write_text(helper)
        (self.scripts / "server_manage.py").write_text(f"import json,sys\nfrom pathlib import Path\nPath({str(self.manager_calls)!r}).write_text(json.dumps(sys.argv[1:]))\nraise SystemExit(130)\n")
        binaries = self.base / "bin"
        binaries.mkdir()
        for name in ["git", "systemctl"]:
            target = binaries / name
            target.write_text("#!/bin/sh\nexit 0\n")
            target.chmod(0o755)
        python = binaries / "python3"
        python.write_text(f'#!/bin/sh\nif [ "$1" = -c ]; then exit 0; fi\nexec "{sys.executable}" "$@"\n')
        python.chmod(0o755)
        sudo = binaries / "sudo"
        sudo.write_text("#!/bin/sh\nexit 99\n")
        sudo.chmod(0o755)
        self.environment = {**os.environ, "PATH": str(binaries) + os.pathsep + os.environ.get("PATH", "")}

    def terminal(self, answers):
        master, slave = pty.openpty()
        process = subprocess.Popen(["bash", str(self.scripts / "install.sh")], stdin=slave, stdout=slave, stderr=slave, env=self.environment)
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
                    if not chunk:
                        break
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

    def existing_installation(self):
        shared = self.target / "shared"
        shared.mkdir(parents=True)
        (shared / "server.json").write_text("fixture")

    def test_install_reaches_manager_without_automation_or_sudo(self):
        output = self.terminal(f"1\n{self.target}\nv9.0.0\n19111\n1\nn\nn\nn\na\n")
        args = json.loads(self.manager_calls.read_text())
        self.assertIn("init", args)
        self.assertIn("--no-autostart", args)
        self.assertNotIn("--yes", args)
        self.assertIn("Operácia bola zrušená", output)
        self.assertFalse(self.target.exists())

    def test_successful_manager_returns_to_readable_summary(self):
        manager = self.scripts / "server_manage.py"
        manager.write_text(manager.read_text().replace("SystemExit(130)", "SystemExit(0)"))
        output = self.terminal(f"1\n{self.target}\nv9.0.0\n19111\n1\nn\nn\nn\na\n")
        self.assertIn("Hotovo. Výsledok", output)
        self.assertIn("Sprievodcu znovu otvoríš", output)
        self.assertIn("docs/server-operations.md", output)

    def test_update_preserves_settings_and_checks_read_access(self):
        self.existing_installation()
        self.terminal(f"2\n{self.target}\nv9.0.1\na\n")
        self.assertEqual(json.loads(self.manager_calls.read_text()), ["--root", str(self.target), "update", "v9.0.1"])
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertTrue(any(call[0] == "check-git" for call in calls))
        self.assertEqual((self.target / "shared/server.json").read_text(), "fixture")

    def test_restore_selects_snapshot_without_git_network_check(self):
        self.existing_installation()
        output = self.terminal(f"4\n{self.target}\n99\n1\na\n")
        self.assertIn("Obnova vráti dáta", output)
        self.assertEqual(json.loads(self.manager_calls.read_text()), ["--root", str(self.target), "recover", str(self.target / "shared/update-backups/before-fixture")])
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertFalse(any(call[0] == "check-git" for call in calls))

    def test_diagnostics_declines_network_and_never_calls_manager(self):
        self.terminal(f"3\n{self.target}\nn\n")
        self.assertFalse(self.manager_calls.exists())
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertTrue(any(call[0] == "diagnose" for call in calls))
        self.assertFalse(any(call[0] == "check-git" for call in calls))


if __name__ == "__main__":
    unittest.main()
