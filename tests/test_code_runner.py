from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from backend.code_runner import (
    CCodeRunner,
    CodeRunnerError,
    COMPILE_FILE_LIMIT_BYTES,
    DevelopmentCodeRunner,
    MAX_OUTPUT_BYTES,
    MAX_PROCESS_COUNT,
    MEMORY_LIMIT_BYTES,
)
from backend.firmware_builder import FirmwareBuildRunner, FIRMWARE_MEMORY_LIMIT_BYTES, MAX_FIRMWARE_ARTIFACT_BYTES


class CodeRunnerStartupTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-startup-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def runners(self) -> list[CCodeRunner]:
        return [CCodeRunner(), DevelopmentCodeRunner(), FirmwareBuildRunner(self.root / "artifacts")]

    @staticmethod
    def supply_tools(runner: CCodeRunner) -> None:
        runner.gcc_path = "/usr/bin/gcc"
        runner.bwrap_path = "/usr/bin/bwrap"
        runner.unshare_path = "/usr/bin/unshare"
        runner.prlimit_path = "/usr/bin/prlimit"

    def test_startup_exception_becomes_unavailable_status(self) -> None:
        for runner in self.runners():
            self.supply_tools(runner)
            with self.subTest(runner=type(runner).__name__), patch(
                "backend.code_runner.subprocess.Popen",
                side_effect=subprocess.SubprocessError("Exception occurred in preexec_fn."),
            ) as launch:
                status = runner.status()
                if isinstance(runner, FirmwareBuildRunner):
                    self.assertTrue(status["targets"])
                    self.assertTrue(all(not target["available"] for target in status["targets"].values()))
                else:
                    self.assertFalse(status["available"])
                    self.assertTrue(status["message"])
                runner.status()
                self.assertEqual(launch.call_count, 1)

    def test_launch_error_closes_input_and_is_reported_as_runner_error(self) -> None:
        for error in (OSError("missing executable"), subprocess.SubprocessError("child setup failed")):
            runner = CCodeRunner()
            self.supply_tools(runner)
            stream = io.BytesIO(b"input")
            with self.subTest(error=type(error).__name__), patch.object(Path, "open", return_value=stream), patch(
                "backend.code_runner.subprocess.Popen", side_effect=error
            ), self.assertRaises(CodeRunnerError):
                runner._execute(["/usr/bin/true"], self.root, timeout=1, stdin_path=self.root / "stdin.txt")
            self.assertTrue(stream.closed)

    def test_missing_prlimit_never_starts_a_program(self) -> None:
        runner = CCodeRunner()
        self.supply_tools(runner)
        runner.prlimit_path = None
        with patch.object(runner, "_execute") as execute:
            status = runner.status()
        self.assertFalse(status["available"])
        self.assertIn("prlimit", status["message"])
        execute.assert_not_called()
        with self.assertRaises(CodeRunnerError):
            runner._sandbox_command(self.root, ["/usr/bin/true"])

    def test_execute_preserves_limits_without_a_python_child_callback(self) -> None:
        for runner in self.runners():
            self.supply_tools(runner)
            firmware = isinstance(runner, FirmwareBuildRunner)
            memory = FIRMWARE_MEMORY_LIMIT_BYTES if firmware else MEMORY_LIMIT_BYTES
            file_limit = MAX_FIRMWARE_ARTIFACT_BYTES if firmware else MAX_OUTPUT_BYTES
            with self.subTest(runner=type(runner).__name__):
                with patch("backend.code_runner.subprocess.Popen") as launch, patch.object(
                    runner, "_collect_output", return_value=(b"ok", b"", False, False)
                ):
                    launch.return_value.returncode = 0
                    result = runner._execute(
                        ["/usr/bin/true"], self.root, timeout=1, memory_limit=memory, file_limit=file_limit
                    )
                self.assertEqual(result["stdout"], "ok")
                arguments = launch.call_args.args[0]
                self.assertEqual(arguments[0], "/usr/bin/prlimit")
                self.assertIn(f"--cpu={10 if firmware else 3}", arguments)
                self.assertIn(f"--as={memory}", arguments)
                self.assertIn(f"--fsize={file_limit}", arguments)
                self.assertIn(f"--nofile={48 if firmware else 32}", arguments)
                self.assertNotIn("preexec_fn", launch.call_args.kwargs)
                self.assertTrue(launch.call_args.kwargs["start_new_session"])
                self.assertNotIn("shell", launch.call_args.kwargs)
                self.assertIn("--net", arguments)
                self.assertIn("--clearenv", arguments)
                self.assertIn("--ro-bind", arguments)
                self.assertGreater(arguments.index(f"--nproc={MAX_PROCESS_COUNT}"), arguments.index("/usr/bin/bwrap"))

    def test_native_compile_allowance_does_not_change_program_limits(self) -> None:
        outcome = {"exitCode": 0, "timedOut": False, "outputLimited": False,
                   "stdout": "", "stderr": "", "durationMs": 1}
        runner = DevelopmentCodeRunner()
        for language in ("c", "cpp"):
            for profile in ("debug", "release"):
                for execute_program in (False, True):
                    with self.subTest(language=language, profile=profile, execute=execute_program), patch.object(
                        runner, "status", return_value={"languages": {language: {"available": True}}}
                    ), patch.object(runner, "_execute", return_value=outcome) as execute, patch.object(
                        runner, "_native_binary_inspection", return_value=None
                    ):
                        result = runner.run(language, "int main(void) { return 0; }", "",
                                            execute=execute_program, build_profile=profile)
                    self.assertTrue(result["compiled"])
                    self.assertEqual(execute.call_count, 2 if execute_program else 1)
                    compile_call = execute.call_args_list[0]
                    self.assertEqual(compile_call.kwargs["file_limit"], COMPILE_FILE_LIMIT_BYTES)
                    self.assertEqual("-fsanitize=undefined" in compile_call.args[0], profile == "debug")
                    if execute_program:
                        run_call = execute.call_args_list[1]
                        self.assertEqual(run_call.args[0], ["/work/program"])
                        self.assertEqual(run_call.kwargs.get("file_limit", MAX_OUTPUT_BYTES), MAX_OUTPUT_BYTES)
                        self.assertEqual(run_call.kwargs["memory_limit"], MEMORY_LIMIT_BYTES)

    @unittest.skipUnless(
        all(shutil.which(tool) for tool in ("gcc", "bwrap", "unshare", "prlimit")),
        "Sandbox tools are not installed",
    )
    def test_real_firmware_probe_from_request_threads_does_not_raise(self) -> None:
        def probe(index: int) -> dict:
            return FirmwareBuildRunner(self.root / str(index), which=lambda _name: None).status()

        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(probe, range(3)))
        self.assertEqual(len(results), 3)
        for result in results:
            for target in result["targets"].values():
                self.assertFalse(target["available"])
                for language in target["languages"].values():
                    self.assertFalse(language["available"])
                    self.assertTrue(language["message"])

    @unittest.skipUnless(
        all(shutil.which(tool) for tool in ("gcc", "bwrap", "unshare", "prlimit")),
        "Sandbox tools are not installed",
    )
    def test_rejected_limits_do_not_execute_the_payload(self) -> None:
        runner = CCodeRunner()
        marker = self.root / "must-not-exist"
        with patch.object(runner, "CPU_LIMIT_SECONDS", "invalid", create=True):
            result = runner._execute(["/usr/bin/touch", "/work/must-not-exist"], self.root, timeout=1)
        self.assertNotEqual(result["exitCode"], 0)
        self.assertIn("prlimit", result["stderr"])
        self.assertFalse(marker.exists())


class SandboxLimitsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CCodeRunner()
        status = self.runner.status()
        if not status["available"]:
            self.skipTest(status["message"])
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-limits-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

    def test_real_children_inherit_hard_and_soft_limits(self) -> None:
        script = (
            "import json, resource; "
            "print(json.dumps({name:resource.getrlimit(getattr(resource,'RLIMIT_'+name)) "
            "for name in ('CPU','AS','FSIZE','NOFILE','NPROC')}))"
        )
        for runner in (self.runner, FirmwareBuildRunner(self.root / "artifacts")):
            firmware = isinstance(runner, FirmwareBuildRunner)
            memory = FIRMWARE_MEMORY_LIMIT_BYTES if firmware else MEMORY_LIMIT_BYTES
            file_limit = MAX_FIRMWARE_ARTIFACT_BYTES if firmware else MAX_OUTPUT_BYTES
            with self.subTest(runner=type(runner).__name__):
                result = runner._execute(
                    ["/usr/bin/python3", "-I", "-c", script], self.workspace,
                    timeout=2, memory_limit=memory, file_limit=file_limit,
                )
                self.assertEqual(result["exitCode"], 0, result["stderr"])
                expected = {
                    "CPU": 10 if firmware else 3, "AS": memory, "FSIZE": file_limit,
                    "NOFILE": 48 if firmware else 32, "NPROC": MAX_PROCESS_COUNT,
                }
                self.assertEqual(json.loads(result["stdout"]), {key: [value, value] for key, value in expected.items()})

    def test_host_files_environment_and_network_namespace_stay_isolated(self) -> None:
        host_file = self.root / "host-only.txt"
        host_file.write_text("not mounted", encoding="ascii")
        script = (
            "import json, os, sys; print(json.dumps({"
            "'fileVisible':os.path.exists(sys.argv[1]),"
            "'environment':os.getenv('POZNAMKOVNIK_TEST_SENTINEL'),"
            "'netNamespace':os.stat('/proc/self/ns/net').st_ino,'cwd':os.getcwd()}))"
        )
        with patch.dict(os.environ, {"POZNAMKOVNIK_TEST_SENTINEL": "not inherited"}):
            result = self.runner._execute(
                ["/usr/bin/python3", "-I", "-c", script, str(host_file)], self.workspace, timeout=2
            )
        self.assertEqual(result["exitCode"], 0, result["stderr"])
        result = json.loads(result["stdout"])
        self.assertFalse(result["fileVisible"])
        self.assertIsNone(result["environment"])
        self.assertNotEqual(result["netNamespace"], os.stat("/proc/self/ns/net").st_ino)
        self.assertEqual(result["cwd"], "/work")

    def test_file_size_and_memory_limits_are_enforced(self) -> None:
        result = self.runner._execute(
            ["/usr/bin/python3", "-I", "-c", f"with open('large.bin','wb') as stream:\n stream.write(b'x'*{MAX_OUTPUT_BYTES + 1})"],
            self.workspace, timeout=2,
        )
        self.assertNotEqual(result["exitCode"], 0)
        self.assertLessEqual((self.workspace / "large.bin").stat().st_size, MAX_OUTPUT_BYTES)
        result = self.runner._execute(
            ["/usr/bin/python3", "-I", "-c", f"bytearray({MEMORY_LIMIT_BYTES * 2})"],
            self.workspace, timeout=2,
        )
        self.assertNotEqual(result["exitCode"], 0)
        self.assertIn("MemoryError", result["stderr"])

    def test_timeout_and_output_cap_still_terminate_programs(self) -> None:
        result = self.runner._execute(
            ["/usr/bin/python3", "-I", "-c", "while True: pass"], self.workspace, timeout=0.2
        )
        self.assertTrue(result["timedOut"])
        result = self.runner._execute(
            ["/usr/bin/python3", "-I", "-c", "import os\nwhile True: os.write(1,b'x'*8192)"],
            self.workspace, timeout=2,
        )
        self.assertTrue(result["outputLimited"])
        self.assertLessEqual(len(result["stdout"].encode()), MAX_OUTPUT_BYTES)

    def test_development_c_retains_file_limit_after_compilation(self) -> None:
        source = r"""
#include <signal.h>
#include <stdio.h>
#include <sys/resource.h>
int main(void)
{
    struct rlimit limit;
    if (getrlimit(RLIMIT_FSIZE, &limit) != 0 || signal(SIGXFSZ, SIG_IGN) == SIG_ERR) { return 1; }
    FILE *stream = fopen("large.bin", "wb");
    if (stream == NULL) { return 2; }
    const char chunk[4096] = {0};
    int limited = 0;
    for (unsigned int i = 0; i < BLOCK_COUNT; ++i) {
        if (fwrite(chunk, 1, sizeof chunk, stream) != sizeof chunk) { limited = 1; break; }
    }
    if (fflush(stream) == EOF) { limited = 1; }
    if (fclose(stream) == EOF) { limited = 1; }
    printf("%llu:%llu limited=%d\n", (unsigned long long) limit.rlim_cur,
           (unsigned long long) limit.rlim_max, limited);
    return 0;
}
""".replace("BLOCK_COUNT", str(MAX_OUTPUT_BYTES // 4096 + 1))
        for profile in ("debug", "release"):
            with self.subTest(profile=profile):
                result = DevelopmentCodeRunner().run("c", source, "", build_profile=profile)
                self.assertTrue(result["compiled"], result)
                self.assertEqual(result["run"]["exitCode"], 0, result)
                self.assertEqual(result["run"]["stdout"], f"{MAX_OUTPUT_BYTES}:{MAX_OUTPUT_BYTES} limited=1\n")
                self.assertEqual(result["run"]["stderr"], "")
