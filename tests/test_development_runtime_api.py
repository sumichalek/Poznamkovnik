from __future__ import annotations

import http.client
import json
import subprocess
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from backend.api import AppContext, AppHandler
from backend.tutorial_c_examples import ARGUMENT_LIST, ARGUMENT_NUMBER


class QuietHandler(AppHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


class DevelopmentRuntimeApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-runtime-api-")
        self.addCleanup(temporary.cleanup)
        with patch("backend.api.AutomaticBackupScheduler.start"), patch(
            "backend.api.RadioRecordingScheduler.start"
        ), patch("backend.api.CalendarReminderScheduler.start"):
            self.context = AppContext(Path(__file__).resolve().parents[1], Path(temporary.name))
        self.addCleanup(self.context.development_debugger.close)
        self.addCleanup(self.context.serial_monitor.close)
        self.addCleanup(self.context.language_services.close)
        self.user, self.token = self.context.auth.setup("Runtime Tester", "runtime-test-password")
        self.context.firmware_builder._which = lambda _name: None
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, context=self.context))
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02})
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.assertFalse(self.thread.is_alive())

    def request(self, method: str, path: str, data: dict | None = None) -> tuple[int, dict]:
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=10)
        try:
            connection.request(
                method, path, body=json.dumps(data) if data is not None else None,
                headers={"Cookie": f"poznamkovnik_session={self.token}", "Content-Type": "application/json"},
            )
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def practice_page_id(self) -> str:
        language = next(item for item in self.context.database.list_tutorial_languages(self.user["id"]) if item["code"] == "c")
        detail = self.context.database.tutorial_language_detail(self.user["id"], language["id"])
        return next(page["id"] for page in detail["pages"] if page["title"] == "Polia a ukazovatele")

    def test_workspace_opens_without_firmware_compilers(self) -> None:
        status, result = self.request("GET", "/api/development")
        self.assertEqual(status, 200)
        self.assertIn("projects", result)
        self.assertIn("languages", result["runtime"])
        self.assertIn("serialMonitor", result)
        for target in result["firmwareBuild"]["targets"].values():
            self.assertFalse(target["available"])
            for language in target["languages"].values():
                self.assertFalse(language["available"])
                self.assertIn("toolchain", language["message"])

    def test_workspace_stays_available_after_process_creation_fails(self) -> None:
        for runner in (self.context.development_runner, self.context.development_debugger, self.context.firmware_builder):
            runner.gcc_path = "/usr/bin/gcc"
            runner.bwrap_path = "/usr/bin/bwrap"
            runner.unshare_path = "/usr/bin/unshare"
            runner.prlimit_path = "/usr/bin/prlimit"
        with patch("backend.code_runner.subprocess.Popen", side_effect=subprocess.SubprocessError("child failed")):
            status, result = self.request("GET", "/api/development")
        self.assertEqual(status, 200)
        self.assertFalse(result["runtime"]["available"])
        self.assertFalse(result["debugger"]["available"])
        self.assertTrue(result["runtime"]["message"])

    def test_unavailable_sandbox_is_reported_and_never_runs_source(self) -> None:
        for runner in (
            self.context.c_runner, self.context.development_runner,
            self.context.development_debugger, self.context.firmware_builder,
        ):
            runner.prlimit_path = None
        with patch("backend.code_runner.subprocess.Popen") as launch:
            status, result = self.request("GET", "/api/development")
            self.assertEqual(status, 200)
            self.assertFalse(result["runtime"]["available"])
            status, result = self.request("POST", "/api/tutorial/practice/run", {
                "pageId": self.practice_page_id(), "source": "int main(void){return 0;}",
            })
        self.assertEqual(status, 400)
        self.assertTrue(result["error"])
        launch.assert_not_called()

    def test_concurrent_workspace_requests_do_not_break_startup(self) -> None:
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(lambda _: self.request("GET", "/api/development"), range(3)))
        self.assertTrue(all(status == 200 for status, _ in results))
        self.assertTrue(all("firmwareBuild" in body for _, body in results))

    def test_development_run_returns_a_json_error_if_launch_fails(self) -> None:
        project = self.context.database.create_development_project(
            self.user["id"], {"id": "startup-test", "title": "Startup test", "language": "c"}
        )
        runner = self.context.development_runner
        runner._runtime_status = {"available": True, "message": "ready"}
        runner.gcc_path = runner.tool_paths["c"] = "/usr/bin/gcc"
        runner.bwrap_path = "/usr/bin/bwrap"
        runner.unshare_path = "/usr/bin/unshare"
        runner.prlimit_path = "/usr/bin/prlimit"
        with patch("backend.code_runner.subprocess.Popen", side_effect=subprocess.SubprocessError("child failed")):
            status, result = self.request("POST", f"/api/development/projects/{project['id']}/run", {})
        self.assertEqual(status, 400)
        self.assertTrue(result["error"])

    def test_c_program_runs_through_the_threaded_api(self) -> None:
        runtime = self.context.c_runner.status()
        if not runtime["available"]:
            self.skipTest(runtime["message"])
        status, result = self.request("POST", "/api/tutorial/practice/run", {
            "pageId": self.practice_page_id(),
            "source": '#include <stdio.h>\nint main(void){puts("runtime ok");return 0;}\n',
        })
        self.assertEqual(status, 200)
        self.assertTrue(result["compiled"], result)
        self.assertEqual(result["run"]["exitCode"], 0)
        self.assertEqual(result["run"]["stdout"], "runtime ok\n")

    def test_argument_list_keeps_quotes_empty_arguments_and_shell_metacharacters_as_data(self) -> None:
        runtime = self.context.development_runner.status()["languages"]["c"]
        if not runtime["available"]:
            self.skipTest(runtime["message"])
        project = self.context.database.create_development_project(
            self.user["id"], {"id": "argument-list", "title": "Argument list", "language": "c", "entryContent": ARGUMENT_LIST}
        )
        for arguments, expected in (
            ('"dve slova" "" %s $HOME *.c ; "$(echo ignored)"',
             "arguments=7\nargv[1]=[dve slova]\nargv[2]=[]\nargv[3]=[%s]\nargv[4]=[$HOME]\n"
             "argv[5]=[*.c]\nargv[6]=[;]\nargv[7]=[$(echo ignored)]\n"),
            ("", "arguments=0\n"),
        ):
            status, result = self.request("POST", f"/api/development/projects/{project['id']}/run", {
                "arguments": arguments, "stdin": "42\n",
            })
            self.assertEqual(status, 200)
            self.assertTrue(result["compiled"], result)
            self.assertEqual((result["run"]["exitCode"], result["run"]["stdout"], result["run"]["stderr"]), (0, expected, ""))
        status, result = self.request("POST", f"/api/development/projects/{project['id']}/run", {"arguments": '"unclosed'})
        self.assertEqual(status, 400)
        self.assertTrue(result["error"])

    def test_number_argument_through_development_api_distinguishes_input_failures(self) -> None:
        runtime = self.context.development_runner.status()["languages"]["c"]
        if not runtime["available"]:
            self.skipTest(runtime["message"])
        project = self.context.database.create_development_project(
            self.user["id"], {"id": "argument-number", "title": "Number argument", "language": "c", "entryContent": ARGUMENT_NUMBER}
        )
        for arguments, stdout, stderr in (
            ("-7", "value=-7\n", ""), ('"  +42  "', "value=42\n", ""),
            ("", "", "Usage: number INTEGER\n"), ("42 9", "", "Usage: number INTEGER\n"),
            ('""', "", "Expected one complete decimal integer.\n"),
            ("42x", "", "Expected one complete decimal integer.\n"),
            ("9" * 100, "", "Integer out of range.\n"),
        ):
            with self.subTest(arguments=arguments):
                status, result = self.request("POST", f"/api/development/projects/{project['id']}/run", {
                    "arguments": arguments, "stdin": "999\n",
                })
                self.assertEqual(status, 200)
                self.assertTrue(result["compiled"], result)
                self.assertEqual(result["run"]["exitCode"] == 0, not stderr, result)
                self.assertEqual((result["run"]["stdout"], result["run"]["stderr"]), (stdout, stderr))
