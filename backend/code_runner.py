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
from pathlib import Path, PurePosixPath
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
        for stream in (process.stdout, process.stderr):
            if stream is None:
                continue
            try:
                selector.unregister(stream)
            except KeyError:
                pass
            stream.close()
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


class DevelopmentCodeRunner(CCodeRunner):
    """Spúšťa malé projekty v rovnakej izolácii ako skúšobňa učebnice."""

    LANGUAGE_DEFINITIONS = {
        "c": {"label": "C", "tool": "gcc", "filename": "main.c", "compile": True},
        "cpp": {"label": "C++", "tool": "g++", "filename": "main.cpp", "compile": True},
        "python": {"label": "Python", "tool": "python3", "filename": "main.py", "compile": False},
        "javascript": {"label": "JavaScript", "tool": "node", "filename": "main.js", "compile": False},
        "php": {"label": "PHP", "tool": "php", "filename": "main.php", "compile": False},
        "csharp": {"label": "C#", "tool": "dotnet", "filename": "Program.cs", "compile": False, "planned": True},
    }

    def __init__(self) -> None:
        super().__init__()
        self.tool_paths = {
            language: self.gcc_path if language == "c" else shutil.which(str(definition["tool"]))
            for language, definition in self.LANGUAGE_DEFINITIONS.items()
        }

    def status(self) -> dict[str, Any]:
        sandbox = super().status()
        languages: dict[str, dict[str, Any]] = {}
        for language, definition in self.LANGUAGE_DEFINITIONS.items():
            planned = bool(definition.get("planned"))
            tool_path = self.tool_paths.get(language)
            available = bool(sandbox["available"] and tool_path and not planned)
            if planned:
                message = "Profil C# pripravíme po bezpečnom nastavení .NET SDK."
            elif not tool_path:
                message = f"Nástroj {definition['tool']} nie je nainštalovaný."
            elif not sandbox["available"]:
                message = str(sandbox["message"])
            else:
                message = f"Skúšobňa {definition['label']} je pripravená."
            languages[language] = {"available": available, "message": message}
        return {**sandbox, "languages": languages}

    def run(
        self,
        language: Any,
        source: Any,
        stdin: Any,
        *,
        files: Any = None,
        entry_filename: Any = None,
    ) -> dict[str, Any]:
        language_id = str(language or "").strip()
        definition = self.LANGUAGE_DEFINITIONS.get(language_id)
        if not definition:
            raise CodeRunnerError("Neznámy jazyk projektu.")
        language_status = self.status()["languages"][language_id]
        if not language_status["available"]:
            raise CodeRunnerError(str(language_status["message"]))
        source_text = self._limited_text(source, MAX_SOURCE_BYTES, "Zdrojový kód je príliš veľký.")
        input_text = self._limited_text(stdin, MAX_INPUT_BYTES, "Vstup programu je príliš veľký.")
        if not source_text.strip():
            raise CodeRunnerError("Zdrojový kód nemôže byť prázdny.")

        with tempfile.TemporaryDirectory(prefix=f"poznamkovnik-{language_id}-") as temporary:
            workspace = Path(temporary)
            filename = self._safe_project_path(entry_filename or definition["filename"])
            project_files = self._project_files(files, filename, source_text)
            self._write_project_files(workspace, project_files)
            input_path = workspace / "stdin.txt"
            input_path.write_text(input_text, encoding="utf-8")
            tool = str(self.tool_paths[language_id])
            entry_path = f"/work/{filename}"

            if language_id == "c":
                source_paths = [f"/work/{name}" for name, _ in project_files if name.lower().endswith(".c")]
                if not source_paths:
                    raise CodeRunnerError("Projekt C nemá zdrojový súbor s príponou .c.")
                compile_result = self._execute(
                    [
                        tool,
                        "-std=c17",
                        "-Wall",
                        "-Wextra",
                        "-Wpedantic",
                        "-Wconversion",
                        "-Wshadow",
                        "-Wformat=2",
                        "-O0",
                        "-I/work",
                        *self._project_include_paths(project_files),
                        *source_paths,
                        "-o",
                        "/work/program",
                    ],
                    workspace,
                    timeout=COMPILE_TIMEOUT_SECONDS,
                )
                if compile_result["timedOut"] or compile_result["outputLimited"] or compile_result["exitCode"] != 0:
                    return {"compiled": False, "compile": compile_result, "run": None}
                run_command = ["/work/program"]
                compile_result = {**compile_result, "stdout": compile_result["stdout"] or "Preklad prebehol úspešne."}
            elif language_id == "cpp":
                source_paths = [
                    f"/work/{name}"
                    for name, _ in project_files
                    if name.lower().endswith((".cpp", ".cc", ".cxx", ".c++"))
                ]
                if not source_paths:
                    raise CodeRunnerError("Projekt C++ nemá zdrojový súbor s príponou .cpp, .cc alebo .cxx.")
                compile_result = self._execute(
                    [
                        tool,
                        "-std=c++20",
                        "-Wall",
                        "-Wextra",
                        "-Wpedantic",
                        "-O0",
                        "-I/work",
                        *self._project_include_paths(project_files),
                        *source_paths,
                        "-o",
                        "/work/program",
                    ],
                    workspace,
                    timeout=COMPILE_TIMEOUT_SECONDS,
                )
                if compile_result["timedOut"] or compile_result["outputLimited"] or compile_result["exitCode"] != 0:
                    return {"compiled": False, "compile": compile_result, "run": None}
                run_command = ["/work/program"]
                compile_result = {**compile_result, "stdout": compile_result["stdout"] or "Preklad prebehol úspešne."}
            elif language_id == "python":
                compile_result = self._skipped_compile_result("Spúšťam Python.")
                run_command = [tool, entry_path]
            elif language_id == "javascript":
                compile_result = self._skipped_compile_result("Spúšťam JavaScript.")
                run_command = [tool, entry_path]
            elif language_id == "php":
                compile_result = self._skipped_compile_result("Spúšťam PHP.")
                run_command = [tool, entry_path]
            else:
                raise CodeRunnerError("Tento jazyk ešte nemá bezpečný profil spúšťania.")

            run_result = self._execute(run_command, workspace, timeout=RUN_TIMEOUT_SECONDS, stdin_path=input_path)
            return {"compiled": True, "compile": compile_result, "run": run_result}

    def _project_files(self, files: Any, entry_filename: str, entry_source: str) -> list[tuple[str, str]]:
        candidates = files if isinstance(files, list) else []
        result: list[tuple[str, str]] = []
        seen: set[str] = set()
        total_size = 0
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            filename = self._safe_project_path(candidate.get("title"))
            content = self._limited_text(candidate.get("content"), MAX_SOURCE_BYTES, "Jeden súbor projektu je príliš veľký.")
            normalized = filename.casefold()
            if normalized in seen:
                raise CodeRunnerError("Projekt obsahuje dva súbory s rovnakým názvom.")
            seen.add(normalized)
            total_size += len(content.encode("utf-8"))
            result.append((filename, content))

        entry_normalized = entry_filename.casefold()
        if entry_normalized not in seen:
            result.append((entry_filename, entry_source))
        else:
            result = [
                (filename, entry_source if filename.casefold() == entry_normalized else content)
                for filename, content in result
            ]
        total_size = sum(len(content.encode("utf-8")) for _, content in result)
        if total_size > MAX_SOURCE_BYTES:
            raise CodeRunnerError("Celý projekt je príliš veľký pre skúšobňu.")
        return result

    @staticmethod
    def _safe_project_path(value: Any) -> str:
        path = PurePosixPath(str(value or "").replace("\\", "/").strip())
        if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
            raise CodeRunnerError("Názov súboru projektu nie je platný.")
        if any(part.startswith(".") for part in path.parts):
            raise CodeRunnerError("Názov súboru projektu nie je platný.")
        return str(path)

    @staticmethod
    def _write_project_files(workspace: Path, files: list[tuple[str, str]]) -> None:
        for filename, content in files:
            target = workspace / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    @staticmethod
    def _project_include_paths(files: list[tuple[str, str]]) -> list[str]:
        directories = sorted({str(PurePosixPath(filename).parent) for filename, _ in files if "/" in filename})
        return [f"-I/work/{directory}" for directory in directories if directory not in {"", "."}]

    @staticmethod
    def _skipped_compile_result(message: str) -> dict[str, Any]:
        return {
            "stdout": message,
            "stderr": "",
            "exitCode": 0,
            "timedOut": False,
            "outputLimited": False,
            "durationMs": 0,
        }
