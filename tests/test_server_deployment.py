from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from scripts.server_manage import Deployment, DeploymentError, UserService, read_json, run


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
