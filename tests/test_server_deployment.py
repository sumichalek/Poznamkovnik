from __future__ import annotations

import hashlib
import json
import os
import pty
import select
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from scripts.server_manage import Deployment, DeploymentCancelled, DeploymentError, UserService, read_json, run
from scripts.server_uninstall import Uninstaller


class FakeService:
    """Exercise Git, snapshots and real HTTP probes without touching systemd or installing packages."""
    def __init__(self):
        self.running = False
        self.payload = {}
        self.starts = 0
        self.stops = 0
        self.fail_release = None
        self.deployment = None

    def active(self):
        return self.running

    def stop(self):
        self.stops += 1
        self.running = False

    def start(self):
        self.starts += 1
        self.running = True
        release = self.deployment.current()
        metadata = read_json(release / ".release.json")
        self.payload = {
            "status": "ok", "version": metadata["tag"][1:], "commit": metadata["commit"],
            "instance": hashlib.sha256(str(self.deployment.data.resolve()).encode()).hexdigest()[:24],
        }
        if release.name == self.fail_release:
            (self.deployment.data / "during-failed-migration.txt").write_text("new incompatible data")
            (self.deployment.data / "preferences.json").write_text('{"font": "broken"}')
            (self.deployment.shared / "config.env").write_text("CHANGED=1\n")
            self.payload["status"] = "failed"

    def reload(self):
        pass

    def enable(self):
        config = self.deployment.config()
        link = self.deployment.unit_dir / "default.target.wants" / config["service"]
        link.parent.mkdir(exist_ok=True)
        link.symlink_to(self.deployment.unit_dir / config["service"])

    def disable(self):
        config = self.deployment.config()
        link = self.deployment.unit_dir / "default.target.wants" / config["service"]
        link.unlink(missing_ok=True)


class ServerDeploymentTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-deploy-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.source = self.base / "source"
        self.source.mkdir()
        run("git", "init", str(self.source))
        run("git", "-C", str(self.source), "config", "user.name", "Deployment Test")
        run("git", "-C", str(self.source), "config", "user.email", "test@example.invalid")
        self.commit_release("v9.0.0")
        self.commit_release("v9.0.1")
        self.service = FakeService()
        service = self.service

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200 if service.running else 503)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(service.payload).encode())

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.deployment = Deployment(
            self.base / "installation", service=self.service, unit_dir=self.base / "units", health_timeout=0.3
        )
        self.service.deployment = self.deployment
        self.environment_patch = patch.object(self.deployment, "prepare_environment")
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)
        self.deployment.initialize(str(self.source), "v9.0.0", "127.0.0.1", self.server.server_port, "test.service", [])
        (self.deployment.data / "preferences.json").write_text('{"font": "large"}')
        (self.deployment.data / ".hidden").write_bytes(b"hidden attachment\x00")
        with closing(sqlite3.connect(self.deployment.data / "poznamkovnik.sqlite3")) as connection, connection:
            connection.execute("CREATE TABLE preferences (name TEXT, value TEXT)")
            connection.execute("INSERT INTO preferences VALUES ('theme', 'dark')")

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def commit_release(self, tag):
        files = {
            ".gitignore": ".venv/\n.release.json\n__pycache__/\n",
            "VERSION": tag[1:] + "\n", "server.py": "pass\n", "index.html": "test",
            "requirements.lock": "", "assets/app.js": "test", "assets/app.css": "test",
        }
        for relative, text in files.items():
            destination = self.source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text)
        run("git", "-C", str(self.source), "add", ".")
        run("git", "-C", str(self.source), "commit", "-m", tag)
        run("git", "-C", str(self.source), "tag", "-a", tag, "-m", tag)

    def test_git_update_and_full_rollback_keep_data_and_settings(self):
        config_file = self.deployment.shared / "config.env"
        config_file.write_text("SETTING=old\n")
        unit = self.deployment.unit_dir / "test.service"
        original_unit = unit.read_text()
        self.deployment.update("v9.0.1")
        self.assertEqual(self.deployment.current().name, "v9.0.1")
        operation = read_json(self.deployment.state_path)
        snapshot = Path(operation["snapshot"])
        manifest = self.deployment.verify_snapshot(snapshot, self.deployment.config())
        self.assertEqual(Path(manifest["previous"]).name, "v9.0.0")
        self.assertIn("settings/config.env", manifest["files"])
        self.assertTrue(self.service.running)
        self.assertTrue((self.deployment.unit_dir / "default.target.wants/test.service").is_symlink())

        config_file.write_text("SETTING=new\n")
        unit.write_text(original_unit + "# changed after deployment\n")
        overrides = self.deployment.unit_dir / "test.service.d"
        overrides.mkdir()
        (overrides / "new.conf").write_text("[Service]\nEnvironment=NEW=1\n")
        (self.deployment.data / "preferences.json").write_text('{"font": "small"}')
        (self.deployment.data / "later.txt").write_text("retained in recovery and fresh snapshot")
        with closing(sqlite3.connect(self.deployment.data / "poznamkovnik.sqlite3")) as connection, connection:
            connection.execute("UPDATE preferences SET value = 'light'")
        backup_count = len(list(self.deployment.backups.iterdir()))

        self.deployment.rollback(snapshot)
        self.assertEqual(self.deployment.current().name, "v9.0.0")
        self.assertEqual((self.deployment.data / "preferences.json").read_text(), '{"font": "large"}')
        self.assertEqual((self.deployment.data / ".hidden").read_bytes(), b"hidden attachment\x00")
        self.assertFalse((self.deployment.data / "later.txt").exists())
        self.assertEqual(config_file.read_text(), "SETTING=old\n")
        self.assertEqual(unit.read_text(), original_unit)
        with closing(sqlite3.connect(self.deployment.data / "poznamkovnik.sqlite3")) as connection, connection:
            self.assertEqual(connection.execute("SELECT value FROM preferences").fetchone()[0], "dark")
        self.assertFalse(overrides.exists())
        self.assertEqual(len(list(self.deployment.backups.iterdir())), backup_count + 1)
        self.assertTrue(any(path.exists() for path in self.deployment.shared.glob("recovery-*/data-after-update/later.txt")))

    def test_failed_start_automatically_restores_old_code_data_and_settings(self):
        self.service.fail_release = "v9.0.1"
        with self.assertRaisesRegex(DeploymentError, "pôvodný stav bol obnovený"):
            self.deployment.update("v9.0.1")
        self.assertEqual(self.deployment.current().name, "v9.0.0")
        self.assertTrue(self.service.running)
        self.assertFalse((self.deployment.data / "during-failed-migration.txt").exists())
        self.assertEqual((self.deployment.data / "preferences.json").read_text(), '{"font": "large"}')
        self.assertFalse((self.deployment.shared / "config.env").exists())
        self.assertEqual(read_json(self.deployment.state_path)["status"], "rolled_back")
        self.assertTrue(list(self.deployment.shared.glob("recovery-*/data-after-update/during-failed-migration.txt")))

    def test_backup_failure_prevents_activation_and_restarts_existing_service(self):
        with patch.object(self.deployment, "snapshot", side_effect=OSError("Disk full")):
            with self.assertRaisesRegex(DeploymentError, "pred aktiváciou"):
                self.deployment.update("v9.0.1")
        self.assertEqual(self.deployment.current().name, "v9.0.0")
        self.assertTrue(self.service.running)
        self.assertEqual(read_json(self.deployment.state_path)["status"], "backup_failed")

    def test_unreadable_snapshot_is_not_marked_as_verified(self):
        before = set(self.deployment.backups.iterdir())
        with patch.object(self.deployment, "_verify_snapshot_payload", side_effect=DeploymentError("Unreadable archive")):
            with self.assertRaisesRegex(DeploymentError, "pred aktiváciou"):
                self.deployment.update("v9.0.1")
        created = set(self.deployment.backups.iterdir()) - before
        self.assertEqual(len(created), 1)
        self.assertFalse((created.pop() / "VERIFIED").exists())
        self.assertEqual(self.deployment.current().name, "v9.0.0")
        self.assertTrue(self.service.running)

    def test_corrupt_settings_snapshot_is_rejected_before_stopping_service(self):
        self.deployment.update("v9.0.1")
        snapshot = Path(read_json(self.deployment.state_path)["snapshot"])
        (snapshot / "settings/service").write_text("corrupt")
        stops = self.service.stops
        with self.assertRaisesRegex(DeploymentError, "Kontrolný súčet"):
            self.deployment.rollback(snapshot)
        self.assertEqual(self.service.stops, stops)
        self.assertTrue(self.service.running)

    def test_dirty_release_and_missing_tag_do_not_stop_server(self):
        stops = self.service.stops
        with self.assertRaises(DeploymentError):
            self.deployment.update("v9.8.7")
        self.assertEqual(self.service.stops, stops)
        (self.deployment.current() / "server.py").write_text("changed")
        with self.assertRaisesRegex(DeploymentError, "lokálne zmeny"):
            self.deployment.update("v9.0.1")
        self.assertEqual(self.service.stops, stops)

    def test_concurrent_update_is_rejected(self):
        with self.deployment.locked():
            with self.assertRaisesRegex(DeploymentError, "iná aktualizácia"):
                self.deployment.update("v9.0.1")

    def test_same_release_never_reinstalls_running_environment(self):
        stops = self.service.stops
        with patch.object(self.deployment, "prepare_environment") as prepare:
            self.deployment.update("v9.0.0")
        prepare.assert_not_called()
        self.assertEqual(self.service.stops, stops)

    def test_external_settings_are_backed_up_and_restored(self):
        external = self.base / "proxy.conf"
        external.write_text("original proxy")
        config = self.deployment.config()
        config["backup_paths"] = [str(external)]
        self.deployment.config_path.write_text(json.dumps(config))
        self.deployment.update("v9.0.1")
        snapshot = Path(read_json(self.deployment.state_path)["snapshot"])
        external.write_text("changed proxy")
        self.deployment.rollback(snapshot)
        self.assertEqual(external.read_text(), "original proxy")

    def test_recover_preinstall_snapshot_allows_retry_without_losing_failed_state(self):
        original = Path(read_json(self.deployment.state_path)["snapshot"])
        backup_count = len(list(self.deployment.backups.iterdir()))
        self.deployment.recover(original)
        self.assertIsNone(self.deployment.current())
        self.assertFalse(self.service.running)
        self.assertFalse((self.deployment.unit_dir / "test.service").exists())
        self.assertEqual(read_json(self.deployment.state_path)["status"], "recovered")
        self.assertEqual(len(list(self.deployment.backups.iterdir())), backup_count + 1)
        self.assertTrue(list(self.deployment.shared.glob("recovery-*/data-after-update/preferences.json")))
        self.deployment.update("v9.0.1")
        self.assertTrue(self.service.running)
        self.assertEqual(self.deployment.current().name, "v9.0.1")

    def test_operator_can_cancel_before_preparation(self):
        stops = self.service.stops
        self.deployment.approval = lambda stage, description: False
        with patch.object(self.deployment, "prepare") as prepare:
            with self.assertRaises(DeploymentCancelled):
                self.deployment.update("v9.0.1")
        prepare.assert_not_called()
        self.assertEqual(self.service.stops, stops)
        self.assertTrue(self.service.running)

    def test_operator_can_cancel_before_service_stop(self):
        stops = self.service.stops
        count = len(list(self.deployment.backups.iterdir()))
        self.deployment.approval = lambda stage, description: stage != "stop_backup"
        with self.assertRaises(DeploymentCancelled):
            self.deployment.update("v9.0.1")
        self.assertEqual(self.service.stops, stops)
        self.assertEqual(len(list(self.deployment.backups.iterdir())), count)
        self.assertEqual(self.deployment.current().name, "v9.0.0")
        self.assertTrue(self.service.running)

    def test_operator_can_keep_verified_backup_without_activating(self):
        self.deployment.approval = lambda stage, description: stage != "activate"
        with patch.object(self.deployment, "restore", wraps=self.deployment.restore) as restore:
            with self.assertRaises(DeploymentCancelled):
                self.deployment.update("v9.0.1")
        restore.assert_not_called()
        state = read_json(self.deployment.state_path)
        self.assertEqual(state["status"], "cancelled")
        self.deployment.verify_snapshot(Path(state["snapshot"]), self.deployment.config())
        self.assertEqual(self.deployment.current().name, "v9.0.0")
        self.assertTrue(self.service.running)

    def test_cancelled_recovery_restarts_unchanged_existing_service(self):
        source = Path(read_json(self.deployment.state_path)["snapshot"])
        self.deployment.approval = lambda stage, description: stage != "activate"
        with self.assertRaises(DeploymentCancelled):
            self.deployment.recover(source)
        self.assertEqual(self.deployment.current().name, "v9.0.0")
        self.assertTrue(self.service.running)
        self.assertTrue((self.deployment.data / "preferences.json").exists())

    def test_first_install_can_leave_autostart_disabled(self):
        source = Path(read_json(self.deployment.state_path)["snapshot"])
        self.deployment.recover(source)
        config = self.deployment.config()
        config["autostart"] = False
        self.deployment.config_path.write_text(json.dumps(config))
        with patch.object(self.service, "enable") as enable:
            self.deployment.update("v9.0.1")
        enable.assert_not_called()
        self.assertTrue(self.service.running)
        self.assertFalse((self.deployment.unit_dir / "default.target.wants/test.service").exists())

    def uninstaller(self, approval=None):
        return Uninstaller(self.deployment.root, service=self.service, unit_dir=self.deployment.unit_dir, approval=approval)

    def test_full_lifecycle_update_restore_uninstall_reinstall_and_restore_again(self):
        deployment = self.deployment
        with closing(sqlite3.connect(deployment.data / "poznamkovnik.sqlite3")) as connection, connection:
            connection.execute("CREATE TABLE users (name TEXT)")
            connection.execute("INSERT INTO users VALUES ('fixture-account')")
        deployment.update("v9.0.1")
        snapshot = Path(read_json(deployment.state_path)["snapshot"])
        (deployment.data / "preferences.json").write_text("new settings")
        deployment.recover(snapshot)
        self.assertEqual(deployment.current().name, "v9.0.0")
        backup_count = len(list(deployment.backups.iterdir()))
        identity = deployment.config()["installation_id"]

        self.uninstaller().uninstall()
        self.assertFalse(self.service.running)
        self.assertFalse(deployment.repository.exists())
        self.assertFalse(deployment.releases.exists())
        self.assertIsNone(deployment.current())
        self.assertFalse((deployment.unit_dir / "test.service").exists())
        self.assertEqual(read_json(deployment.state_path)["status"], "uninstalled")
        deployment.verify_snapshot(snapshot, deployment.config())
        self.assertEqual((deployment.data / "preferences.json").read_text(), '{"font": "large"}')
        self.assertEqual(len(list(deployment.backups.iterdir())), backup_count)

        # Retained origin permits a real Git clone and reconstruction of the needed release.
        deployment.update("v9.0.0")
        self.assertEqual(deployment.config()["installation_id"], identity)
        self.assertTrue(self.service.running)
        self.assertEqual(len(list(deployment.backups.iterdir())), backup_count + 1)
        deployment.recover(snapshot)
        with closing(sqlite3.connect(deployment.data / "poznamkovnik.sqlite3")) as connection:
            self.assertEqual(connection.execute("SELECT name FROM users").fetchone()[0], "fixture-account")

    def test_uninstall_purge_only_removes_validated_installation_root(self):
        unrelated = self.base / "unrelated.txt"
        unrelated.write_text("keep")
        self.uninstaller().uninstall(delete_data=True)
        self.assertFalse(self.deployment.root.exists())
        self.assertFalse(self.service.running)
        self.assertEqual(unrelated.read_text(), "keep")
        self.assertTrue(self.source.exists())

    def test_uninstall_cancel_changes_nothing(self):
        stops = self.service.stops
        state = self.deployment.state_path.read_bytes()
        index = Path(run("git", "-C", str(self.deployment.current()), "rev-parse", "--git-path", "index"))
        index_mtime = index.stat().st_mtime_ns
        with self.assertRaises(DeploymentCancelled):
            self.uninstaller(approval=lambda plan: False).uninstall()
        self.assertEqual(self.service.stops, stops)
        self.assertTrue(self.service.running)
        self.assertEqual(self.deployment.state_path.read_bytes(), state)
        self.assertFalse((self.deployment.shared / "uninstall-state.json").exists())
        self.assertEqual(index.stat().st_mtime_ns, index_mtime)

    def test_uninstall_rejects_foreign_service_before_stopping_anything(self):
        (self.deployment.unit_dir / "test.service").write_text("[Service]\nExecStart=/usr/bin/other\n")
        stops = self.service.stops
        with self.assertRaisesRegex(DeploymentError, "nepatrí"):
            self.uninstaller().uninstall()
        self.assertEqual(self.service.stops, stops)
        self.assertTrue(self.deployment.releases.exists())

    def test_uninstall_failure_is_recorded_and_retry_is_possible(self):
        with patch.object(self.service, "disable", side_effect=DeploymentError("fixture disable failed")):
            with self.assertRaises(DeploymentError):
                self.uninstaller().uninstall()
        self.assertEqual(read_json(self.deployment.state_path)["status"], "uninstall_failed")
        self.assertTrue(self.deployment.releases.exists())
        self.assertTrue(self.deployment.data.exists())
        with self.assertRaisesRegex(DeploymentError, "Odinštalovanie sa nedokončilo"):
            self.deployment.update("v9.0.1")
        self.uninstaller().uninstall()
        self.assertEqual(read_json(self.deployment.state_path)["status"], "uninstalled")

    def test_uninstall_shares_update_lock(self):
        with self.deployment.locked(), self.assertRaisesRegex(DeploymentError, "iná operácia"):
            self.uninstaller().uninstall()
        self.assertTrue(self.service.running)

    def test_uninstall_will_not_delete_local_changes_to_release_code(self):
        code = self.deployment.current() / "server.py"
        code.write_text("# keep my local changes")
        stops = self.service.stops
        with self.assertRaisesRegex(DeploymentError, "lokálne zmeny"):
            self.uninstaller().uninstall()
        self.assertEqual(self.service.stops, stops)
        self.assertEqual(code.read_text(), "# keep my local changes")

    def test_legacy_uninstall_retains_origin_for_reinstallation(self):
        config = self.deployment.config()
        for field in ("installation_id", "installation_root", "repository"):
            config.pop(field)
        self.deployment.config_path.write_text(json.dumps(config))
        (self.deployment.unit_dir / "test.service").write_text(self.deployment.unit_text(config))
        self.uninstaller().uninstall()
        self.assertEqual(self.deployment.config()["repository"], str(self.source))
        self.deployment.update("v9.0.0")
        self.assertTrue(self.service.running)

    def test_access_plan_is_readonly_including_git_indexes(self):
        def inventory():
            return {str(path): (path.lstat().st_mtime_ns, path.read_bytes() if path.is_file() and not path.is_symlink() else None)
                    for root in (self.deployment.root, self.deployment.unit_dir) for path in root.rglob("*")}
        before = inventory()
        stops = self.service.stops
        with patch.object(self.deployment, "prepare") as prepare:
            plan = self.deployment.access_plan("lan")
        self.assertEqual(plan["previousHost"], "127.0.0.1")
        self.assertEqual(plan["host"], "0.0.0.0")
        self.assertEqual(plan["port"], self.server.server_port)
        self.assertEqual(inventory(), before)
        self.assertEqual(self.service.stops, stops)
        prepare.assert_not_called()

    def test_real_access_plan_wizard_and_cli_are_readonly_with_simulated_systemd(self):
        project = Path(__file__).resolve().parents[1]
        # The real read-only helpers discover this isolated user-unit directory.
        units = self.base / "config/systemd/user"
        units.mkdir(parents=True)
        unit = units / "test.service"
        shutil.copyfile(self.deployment.unit_dir / "test.service", unit)
        binaries = self.base / "bin"
        binaries.mkdir()
        systemctl = binaries / "systemctl"
        systemctl.write_text(f'''#!{sys.executable}
import sys
properties = {{'FragmentPath': {str(unit)!r}, 'DropInPaths': '', 'NeedDaemonReload': 'no', 'ActiveState': 'active'}}
for name, value in properties.items():
    if '--property=' + name in sys.argv:
        print(value)
        raise SystemExit(0)
raise SystemExit('Unexpected or mutating systemctl command')
''')
        systemctl.chmod(0o755)
        environment = {**os.environ, "XDG_CONFIG_HOME": str(self.base / "config"),
                       "PATH": str(binaries) + os.pathsep + os.environ.get("PATH", "")}
        def inventory():
            return {str(path): (path.lstat().st_mtime_ns, path.read_bytes() if path.is_file() and not path.is_symlink() else None)
                    for path in self.base.rglob("*")}
        before = inventory()
        for choice, mode in ((1, "local"), (2, "lan")):
            with self.subTest(mode=mode):
                result = subprocess.run(["bash", str(project / "scripts/install.sh"), "--plan"],
                                        input=f"6\n{self.deployment.root}\n{choice}\nn\n", env=environment, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertIn("Iba plán", result.stdout)
                self.assertIn(f"configure-access {mode}", result.stdout)
                result = subprocess.run([sys.executable, "-B", str(project / "scripts/server_manage.py"), "--root", str(self.deployment.root),
                                         "configure-access", mode, "--plan"], env=environment, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["mode"], mode)
                self.assertEqual(inventory(), before)

    def test_access_round_trip_keeps_release_accounts_data_and_identity(self):
        deployment = self.deployment
        with closing(sqlite3.connect(deployment.data / "poznamkovnik.sqlite3")) as connection, connection:
            connection.execute("CREATE TABLE users (name TEXT)")
            connection.execute("INSERT INTO users VALUES ('existing-account')")
        original_config = deployment.config()
        original_unit = (deployment.unit_dir / "test.service").read_bytes()
        database = (deployment.data / "poznamkovnik.sqlite3").read_bytes()
        count = len(list(deployment.backups.iterdir()))

        def approve(stage, description):
            if stage == "activate":
                snapshot = Path(read_json(deployment.state_path)["snapshot"])
                deployment.verify_snapshot(snapshot, deployment.config())
                self.assertFalse(self.service.running)
                self.assertEqual(read_json(snapshot / "settings/server.json"), deployment.config())
                self.assertEqual((snapshot / "settings/service").read_bytes(), (deployment.unit_dir / "test.service").read_bytes())
            return True

        deployment.approval = approve
        with patch.object(deployment, "prepare", side_effect=AssertionError("must not fetch/install a release")):
            deployment.configure_access("lan")
            self.assertEqual(deployment.config(), {**original_config, "host": "0.0.0.0"})
            self.assertIn('--host "0.0.0.0"', (deployment.unit_dir / "test.service").read_text())
            deployment.configure_access("local")
        self.assertEqual(deployment.config(), original_config)
        self.assertEqual((deployment.unit_dir / "test.service").read_bytes(), original_unit)
        self.assertEqual((deployment.data / "poznamkovnik.sqlite3").read_bytes(), database)
        self.assertEqual((deployment.data / "preferences.json").read_text(), '{"font": "large"}')
        self.assertEqual(deployment.current().name, "v9.0.0")
        self.assertEqual(len(list(deployment.backups.iterdir())), count + 2)
        self.assertTrue(self.service.running)

    def test_access_change_backup_failure_preserves_original_settings(self):
        config = self.deployment.config_path.read_bytes()
        unit = (self.deployment.unit_dir / "test.service").read_bytes()
        with patch.object(self.deployment, "snapshot", side_effect=OSError("fixture disk full")):
            with self.assertRaisesRegex(DeploymentError, "pred aktiváciou"):
                self.deployment.configure_access("lan")
        self.assertEqual(self.deployment.config_path.read_bytes(), config)
        self.assertEqual((self.deployment.unit_dir / "test.service").read_bytes(), unit)
        self.assertTrue(self.service.running)

    def test_access_change_failed_health_restores_old_config_and_unit(self):
        config = self.deployment.config_path.read_bytes()
        unit = (self.deployment.unit_dir / "test.service").read_bytes()
        health = self.deployment.health
        def probe(release, settings):
            if settings["host"] == "0.0.0.0":
                raise DeploymentError("fixture health failure")
            return health(release, settings)
        with patch.object(self.deployment, "health", side_effect=probe):
            with self.assertRaisesRegex(DeploymentError, "pôvodný stav bol obnovený"):
                self.deployment.configure_access("lan")
        self.assertEqual(self.deployment.config_path.read_bytes(), config)
        self.assertEqual((self.deployment.unit_dir / "test.service").read_bytes(), unit)
        self.assertEqual(read_json(self.deployment.state_path)["status"], "rolled_back")
        self.assertTrue(self.service.running)

    def test_access_change_unit_write_failure_rolls_back_already_written_config(self):
        config = self.deployment.config_path.read_bytes()
        unit_text = self.deployment.unit_text
        def text(settings):
            if settings["host"] == "0.0.0.0":
                raise OSError("fixture unit write failure")
            return unit_text(settings)
        with patch.object(self.deployment, "unit_text", side_effect=text):
            with self.assertRaisesRegex(DeploymentError, "pôvodný stav bol obnovený"):
                self.deployment.configure_access("lan")
        self.assertEqual(self.deployment.config_path.read_bytes(), config)
        self.assertTrue(self.service.running)

    def test_access_change_preserves_originally_inactive_service_and_autostart(self):
        self.service.stop()
        enabled = self.deployment.unit_dir / "default.target.wants/test.service"
        target = os.readlink(enabled)
        self.deployment.configure_access("lan")
        self.assertFalse(self.service.running)
        self.assertEqual(os.readlink(enabled), target)
        self.assertEqual(self.deployment.config()["host"], "0.0.0.0")

    def test_access_change_can_cancel_before_stop_or_after_verified_backup(self):
        for rejected in ("prepare", "stop_backup", "activate"):
            with self.subTest(stage=rejected):
                stops = self.service.stops
                count = len(list(self.deployment.backups.iterdir()))
                config = self.deployment.config_path.read_bytes()
                self.deployment.approval = lambda stage, description: stage != rejected
                with self.assertRaises(DeploymentCancelled):
                    self.deployment.configure_access("lan")
                self.assertEqual(self.deployment.config_path.read_bytes(), config)
                self.assertTrue(self.service.running)
                self.assertEqual(self.service.stops, stops + (rejected == "activate"))
                self.assertEqual(len(list(self.deployment.backups.iterdir())), count + (rejected == "activate"))

    def test_access_same_mode_does_not_stop_service_or_backup(self):
        stops = self.service.stops
        count = len(list(self.deployment.backups.iterdir()))
        self.deployment.configure_access("local")
        self.assertEqual(self.service.stops, stops)
        self.assertEqual(len(list(self.deployment.backups.iterdir())), count)

    def test_access_change_rejects_foreign_or_dropin_units_without_stopping(self):
        unit = self.deployment.unit_dir / "test.service"
        original = unit.read_text()
        stops = self.service.stops
        unit.write_text("[Service]\nExecStart=/usr/bin/other\n")
        with self.assertRaisesRegex(DeploymentError, "cudzia alebo ručne"):
            self.deployment.configure_access("lan")
        unit.write_text(original)
        dropins = unit.with_name("test.service.d")
        dropins.mkdir()
        (dropins / "override.conf").write_text("[Service]\nExecStart=/usr/bin/other\n")
        with self.assertRaisesRegex(DeploymentError, "drop-ins"):
            self.deployment.configure_access("lan")
        self.assertEqual(self.service.stops, stops)

    def test_access_change_rejects_dirty_release_and_pending_operations(self):
        stops = self.service.stops
        code = self.deployment.current() / "server.py"
        original = code.read_text()
        code.write_text("# changed\n")
        with self.assertRaisesRegex(DeploymentError, "lokálne zmeny"):
            self.deployment.configure_access("lan")
        code.write_text(original)
        for status in ("recovery_required", "backed_up", "uninstall_failed"):
            self.deployment.state(status)
            with self.subTest(status=status), self.assertRaises(DeploymentError):
                self.deployment.configure_access("lan")
        self.assertEqual(self.service.stops, stops)

    def test_access_checks_effective_systemd_unit_not_only_local_file(self):
        config = self.deployment.config()
        unit = str(self.deployment.unit_dir / config["service"])
        with patch.object(self.deployment, "service_override", None), patch.object(UserService, "command", side_effect=[unit, "", "no"]):
            self.deployment.check_access_unit(config)
        for responses in (["/other/unit.service"], [unit, "/etc/systemd/user/service.d/override.conf"], [unit, "", "yes"], [unit, "", ""]):
            with self.subTest(responses=responses), patch.object(self.deployment, "service_override", None), patch.object(UserService, "command", side_effect=responses), self.assertRaises(DeploymentError):
                self.deployment.check_access_unit(config)

    def test_access_service_state_changed_during_stop_approval_is_preserved(self):
        stops = self.service.stops
        config = self.deployment.config_path.read_bytes()
        def approve(stage, description):
            if stage == "stop_backup":
                self.service.running = False  # Another operator stopped it during the prompt.
            return True
        self.deployment.approval = approve
        with self.assertRaisesRegex(DeploymentError, "zmenila stav"):
            self.deployment.configure_access("lan")
        self.assertEqual(self.service.stops, stops)
        self.assertFalse(self.service.running)
        self.assertEqual(self.deployment.config_path.read_bytes(), config)

    def test_access_foreign_unit_created_after_backup_is_not_overwritten_or_started(self):
        unit = self.deployment.unit_dir / "test.service"
        foreign = "[Service]\nExecStart=/usr/bin/other\n"
        config = self.deployment.config_path.read_bytes()
        def approve(stage, description):
            if stage == "activate":
                unit.write_text(foreign)
            return True
        self.deployment.approval = approve
        with self.assertRaisesRegex(DeploymentError, "nepodarilo spustiť"):
            self.deployment.configure_access("lan")
        self.assertEqual(unit.read_text(), foreign)
        self.assertEqual(self.deployment.config_path.read_bytes(), config)
        self.assertFalse(self.service.running)
        self.assertEqual(read_json(self.deployment.state_path)["status"], "recovery_required")

    def test_access_settings_changed_during_approval_are_not_overwritten(self):
        stops = self.service.stops
        def approve(stage, description):
            if stage == "prepare":
                config = self.deployment.config()
                config["autostart"] = False
                self.deployment.config_path.write_text(json.dumps(config))
            return True
        self.deployment.approval = approve
        with self.assertRaisesRegex(DeploymentError, "Počas rozhodovania"):
            self.deployment.configure_access("lan")
        self.assertFalse(self.deployment.config()["autostart"])
        self.assertEqual(self.service.stops, stops)

    def test_access_change_failed_rollback_leaves_service_stopped(self):
        with patch.object(self.deployment, "health", side_effect=DeploymentError("fixture health")), patch.object(self.deployment, "restore", side_effect=OSError("fixture restore")):
            with self.assertRaisesRegex(DeploymentError, "Obnova vyžaduje zásah"):
                self.deployment.configure_access("lan")
        self.assertFalse(self.service.running)
        self.assertEqual(read_json(self.deployment.state_path)["status"], "recovery_required")


class InstallerControlTest(unittest.TestCase):
    @unittest.skipIf(os.geteuid() == 0, "Skutočný sprievodca sa spúšťa pod bežným účtom")
    def test_terminal_user_can_cancel_plan_without_changes(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="poznamkovnik-tty-") as temporary:
            target = Path(temporary) / "trial"
            answers = f"1\n{target}\nv9.0.0\n19111\n1\nn\nn\nn\nn\n"
            master, slave = pty.openpty()
            process = subprocess.Popen(["bash", str(project / "scripts/install.sh")], stdin=slave, stdout=slave, stderr=slave)
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
            self.assertIn("Súhlasíš s týmto plánom", output.decode())
            self.assertFalse(target.exists())

    def test_plan_prints_choices_without_creating_installation(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="poznamkovnik-plan-") as temporary:
            target = Path(temporary) / "trial"
            answers = f"1\n{target}\nv9.0.0\n19111\n2\nn\nn\nn\n"
            result = subprocess.run(
                ["bash", str(project / "scripts/install.sh"), "--plan"], input=answers,
                text=True, capture_output=True, cwd=project,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Iba plán", result.stdout)
            self.assertIn("19111", result.stdout)
            self.assertIn("0.0.0.0", result.stdout)
            self.assertIn("Automatické spúšťanie: nie", result.stdout)
            self.assertFalse(target.exists())

    def test_installer_refuses_piped_execution(self):
        project = Path(__file__).resolve().parents[1]
        result = subprocess.run(["bash", str(project / "scripts/install.sh")], input="a\n" * 20,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("interaktívnom termináli", result.stderr)

    def test_cli_requires_terminal_or_explicit_automation(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="poznamkovnik-confirm-") as temporary:
            target = Path(temporary) / "installation"
            result = subprocess.run(
                [sys.executable, str(project / "scripts/server_manage.py"), "--root", str(target), "init", "v9.0.0"],
                input="a\n" * 20, text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("interaktívnom termináli", result.stderr)
            self.assertFalse(target.exists())

    def test_access_cli_requires_terminal_but_readonly_plan_does_not(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="poznamkovnik-access-cli-") as temporary:
            target = Path(temporary) / "missing"
            args = [sys.executable, "-B", str(project / "scripts/server_manage.py"), "--root", str(target), "configure-access", "local"]
            result = subprocess.run(args, input="a\n" * 20, text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("interaktívnom termináli", result.stderr)
            result = subprocess.run([*args, "--plan"], text=True, capture_output=True)
            self.assertEqual(result.returncode, 1)  # Missing installation, not a TTY error.
            self.assertNotIn("interaktívnom termináli", result.stderr)
            self.assertFalse(target.exists())


class SystemdServiceTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("systemd-analyze"), "systemd parser nie je dostupný")
    def test_generated_unit_is_accepted_by_real_systemd_parser(self):
        with tempfile.TemporaryDirectory(prefix="poznamkovnik-unit-") as temporary:
            for directory in ("installation", "installation with spaces and %"):
                with self.subTest(directory=directory):
                    deployment = Deployment(Path(temporary) / directory)
                    python = deployment.root / "current/.venv/bin/python"
                    python.parent.mkdir(parents=True)
                    python.symlink_to(sys.executable)
                    unit = Path(temporary) / "poznamkovnik-verify.service"
                    unit.write_text(deployment.unit_text({"host": "0.0.0.0", "port": 1111}))
                    result = subprocess.run(
                        ["systemd-analyze", "--user", "verify", str(unit)], capture_output=True, text=True
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_inactive_invalid_unit_does_not_block_restoration(self):
        service = UserService("test.service")
        with patch.object(service, "command", side_effect=["bad-setting", "inactive"]) as command:
            service.stop()
        self.assertNotIn(unittest.mock.call("stop"), command.call_args_list)

    def test_active_invalid_unit_must_still_be_stopped(self):
        service = UserService("test.service")
        with patch.object(service, "command", side_effect=["bad-setting", "active", "", "inactive"]) as command:
            service.stop()
        command.assert_any_call("stop")
