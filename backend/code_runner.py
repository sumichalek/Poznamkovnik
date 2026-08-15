"""Bezpečne obmedzené spúšťanie krátkych príkladov C v Bubblewrape."""

from __future__ import annotations

import os
import resource
import selectors
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


MAX_SOURCE_BYTES = 200 * 1024
MAX_INPUT_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
COMPILE_TIMEOUT_SECONDS = 4.0
RUN_TIMEOUT_SECONDS = 2.0
MEMORY_LIMIT_BYTES = 128 * 1024 * 1024
MAX_PROCESS_COUNT = 16


class CodeRunnerError(ValueError):
    """Kód alebo dostupný sandbox nespĺňa podmienky spustenia."""


class CCodeRunner:
    def __init__(self) -> None:
        self.gcc_path = shutil.which("gcc")
        self.bwrap_path = shutil.which("bwrap")
        self.unshare_path = shutil.which("unshare")
        self._runtime_status: dict[str, Any] | None = None

    def status(self) -> dict[str, Any]:
        if self._runtime_status is None:
            self._runtime_status = self._check_runtime()
        return dict(self._runtime_status)

    def run(self, source: Any, stdin: Any, standard: Any = "c17") -> dict[str, Any]:
        status = self.status()
        if not status["available"]:
            raise CodeRunnerError(status["message"])
        if standard != "c17":
            raise CodeRunnerError("Skúšobňa momentálne podporuje štandard C17.")

        source_text = self._limited_text(source, MAX_SOURCE_BYTES, "Zdrojový kód je príliš veľký.")
        input_text = self._limited_text(stdin, MAX_INPUT_BYTES, "Vstup programu je príliš veľký.")
        if not source_text.strip():
            raise CodeRunnerError("Zdrojový kód nemôže byť prázdny.")

        with tempfile.TemporaryDirectory(prefix="poznamkovnik-c-") as temporary:
            workspace = Path(temporary)
            (workspace / "main.c").write_text(source_text, encoding="utf-8")
            (workspace / "stdin.txt").write_text(input_text, encoding="utf-8")

            compile_result = self._execute(
                [
                    str(self.gcc_path),
                    "-std=c17",
                    "-Wall",
                    "-Wextra",
                    "-Wpedantic",
                    "-Wconversion",
                    "-Wshadow",
                    "-Wformat=2",
                    "-O0",
                    "/work/main.c",
                    "-o",
                    "/work/program",
                ],
                workspace,
                timeout=COMPILE_TIMEOUT_SECONDS,
            )
            if compile_result["timedOut"] or compile_result["outputLimited"] or compile_result["exitCode"] != 0:
                return {"compiled": False, "compile": compile_result, "run": None}

            run_result = self._execute(["/work/program"], workspace, timeout=RUN_TIMEOUT_SECONDS, stdin_path=workspace / "stdin.txt")
            return {"compiled": True, "compile": compile_result, "run": run_result}

    def _check_runtime(self) -> dict[str, Any]:
        if not self.gcc_path:
            return {"available": False, "message": "Prekladač GCC nie je nainštalovaný."}
        if not self.bwrap_path:
            return {"available": False, "message": "Bezpečná skúšobňa vyžaduje Bubblewrap (bwrap)."}
        if not self.unshare_path:
            return {"available": False, "message": "Bezpečná skúšobňa vyžaduje nástroj unshare z util-linux."}
        try:
            with tempfile.TemporaryDirectory(prefix="poznamkovnik-c-check-") as temporary:
                result = self._execute(["/usr/bin/true"], Path(temporary), timeout=2.0)
            if result["exitCode"] == 0 and not result["timedOut"]:
                return {"available": True, "message": "Skúšobňa C je pripravená (unshare + Bubblewrap)."}
            detail = (result["stderr"] or result["stdout"]).strip().replace("\n", " ")
            if detail:
                return {
                    "available": False,
                    "message": f"Bezpečný sandbox sa nepodarilo spustiť: {detail[:280]}",
                }
        except (OSError, CodeRunnerError):
            pass
        return {
            "available": False,
            "message": "Bezpečný sandbox Bubblewrap sa na tomto serveri nepodarilo spustiť.",
        }

    def _execute(self, command: list[str], workspace: Path, *, timeout: float, stdin_path: Path | None = None) -> dict[str, Any]:
        sandbox_command = self._sandbox_command(workspace, command)
        started = time.monotonic()
        stdin_handle = stdin_path.open("rb") if stdin_path else subprocess.DEVNULL
        try:
            try:
                process = subprocess.Popen(
                    sandbox_command,
                    stdin=stdin_handle,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=workspace,
                    start_new_session=True,
                    preexec_fn=self._limit_process,
                )
            except OSError as error:
                raise CodeRunnerError("Bezpečný sandbox sa nepodarilo spustiť.") from error
            stdout, stderr, timed_out, output_limited = self._collect_output(process, timeout)
        finally:
            if stdin_path is not None:
                stdin_handle.close()

        return {
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "exitCode": process.returncode if process.returncode is not None else -1,
            "timedOut": timed_out,
            "outputLimited": output_limited,
            "durationMs": round((time.monotonic() - started) * 1000),
        }

    def _sandbox_command(self, workspace: Path, command: list[str]) -> list[str]:
        if not self.bwrap_path:
            raise CodeRunnerError("Bezpečný sandbox nie je dostupný.")
        if not self.unshare_path:
            raise CodeRunnerError("Bezpečný sieťový sandbox nie je dostupný.")
        arguments = [
            self.unshare_path,
            "--user",
            "--map-root-user",
            "--mount",
            "--pid",
            "--fork",
            "--ipc",
            "--uts",
            "--net",
            self.bwrap_path,
            "--new-session",
            "--die-with-parent",
            "--clearenv",
            "--setenv",
            "HOME",
            "/tmp",
            "--setenv",
            "PATH",
            "/usr/bin:/bin",
        ]
        for system_path in ("/usr", "/bin", "/lib", "/lib64"):
            if Path(system_path).exists():
                arguments.extend(["--ro-bind", system_path, system_path])
        arguments.extend(
            [
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--tmpfs",
                "/tmp",
                "--bind",
                str(workspace),
                "/work",
                "--chdir",
                "/work",
                "--",
                "/usr/bin/prlimit",
                f"--nproc={MAX_PROCESS_COUNT}",
                "--",
                *command,
            ]
        )
        return arguments

    @staticmethod
    def _limited_text(value: Any, maximum: int, message: str) -> str:
        text = str(value or "")
        if len(text.encode("utf-8")) > maximum:
            raise CodeRunnerError(message)
        return text

    @staticmethod
    def _limit_process() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))

    @staticmethod
    def _collect_output(process: subprocess.Popen[bytes], timeout: float) -> tuple[bytes, bytes, bool, bool]:
        selector = selectors.DefaultSelector()
        assert process.stdout is not None
        assert process.stderr is not None
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        chunks = {"stdout": bytearray(), "stderr": bytearray()}
        timed_out = False
        output_limited = False
        deadline = time.monotonic() + timeout

        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                CCodeRunner._terminate(process)
                remaining = 0.1
            for key, _ in selector.select(max(0.0, min(remaining, 0.1))):
                data = os.read(key.fileobj.fileno(), 16 * 1024)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                chunks[key.data].extend(data)
                if sum(len(value) for value in chunks.values()) > MAX_OUTPUT_BYTES:
                    output_limited = True
                    CCodeRunner._terminate(process)

        try:
            process.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            CCodeRunner._terminate(process)
            process.wait(timeout=0.2)
        selector.close()
        return bytes(chunks["stdout"][:MAX_OUTPUT_BYTES]), bytes(chunks["stderr"][:MAX_OUTPUT_BYTES]), timed_out, output_limited

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
