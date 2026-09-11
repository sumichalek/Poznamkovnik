"""Bezpečne obmedzené spúšťanie krátkych príkladov C v Bubblewrape."""

from __future__ import annotations

import os
import re
import selectors
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any


MAX_SOURCE_BYTES = 200 * 1024
MAX_INPUT_BYTES = 64 * 1024
MAX_ARGUMENT_BYTES = 8 * 1024
MAX_ARGUMENT_COUNT = 32
MAX_OUTPUT_BYTES = 64 * 1024
# Modern C++ headers can make the compiler create an object or a temporary file
# larger than the program-output cap. The compiled program still keeps that cap.
COMPILE_FILE_LIMIT_BYTES = 8 * 1024 * 1024
COMPILE_TIMEOUT_SECONDS = 4.0
RUN_TIMEOUT_SECONDS = 2.0
MEMORY_LIMIT_BYTES = 128 * 1024 * 1024
# V8 si pri štarte rezervuje väčší adresný priestor než potrebuje krátky skript.
NODE_MEMORY_LIMIT_BYTES = 1024 * 1024 * 1024
NODE_MAX_OLD_SPACE_MB = 96
COMPILED_LANGUAGE_MEMORY_LIMIT_BYTES = 1024 * 1024 * 1024
JAVA_MAX_HEAP_MB = 96
JAVA_MAX_METASPACE_MB = 96
MAX_PROCESS_COUNT = 16
MAX_BINARY_INSPECTION_SYMBOLS = 80


class CodeRunnerError(ValueError):
    """Kód alebo dostupný sandbox nespĺňa podmienky spustenia."""


class CCodeRunner:
    CPU_LIMIT_SECONDS = 3
    OPEN_FILE_LIMIT = 32

    def __init__(self) -> None:
        self.gcc_path = shutil.which("gcc")
        self.bwrap_path = shutil.which("bwrap")
        self.unshare_path = shutil.which("unshare")
        self.prlimit_path = shutil.which("prlimit")
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
        if not self.prlimit_path:
            return {"available": False, "message": "Bezpečná skúšobňa vyžaduje nástroj prlimit z util-linux."}
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

    def _execute(
        self,
        command: list[str],
        workspace: Path,
        *,
        timeout: float,
        stdin_path: Path | None = None,
        memory_limit: int = MEMORY_LIMIT_BYTES,
        file_limit: int = MAX_OUTPUT_BYTES,
        environment: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        sandbox_command = self._sandbox_command(
            workspace, command, environment=environment, memory_limit=memory_limit, file_limit=file_limit
        )
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
                )
            except (OSError, subprocess.SubprocessError) as error:
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

    def _sandbox_command(
        self,
        workspace: Path,
        command: list[str],
        *,
        environment: dict[str, str] | None = None,
        memory_limit: int = MEMORY_LIMIT_BYTES,
        file_limit: int = MAX_OUTPUT_BYTES,
    ) -> list[str]:
        if not self.bwrap_path:
            raise CodeRunnerError("Bezpečný sandbox nie je dostupný.")
        if not self.unshare_path:
            raise CodeRunnerError("Bezpečný sieťový sandbox nie je dostupný.")
        if not self.prlimit_path:
            raise CodeRunnerError("Nástroj prlimit na bezpečné obmedzenie procesov nie je dostupný.")
        # Apply limits in an executable, not a Python preexec_fn in the threaded server.
        arguments = [
            self.prlimit_path,
            f"--cpu={self.CPU_LIMIT_SECONDS}",
            f"--as={memory_limit}",
            f"--fsize={file_limit}",
            f"--nofile={self.OPEN_FILE_LIMIT}",
            "--",
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
        for key, value in (environment or {}).items():
            arguments.extend(["--setenv", key, value])
        for system_path in ("/usr", "/bin", "/lib", "/lib64", "/etc"):
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
                # Limit the mapped user, not the host user's entire process count.
                self.prlimit_path,
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

    BUILD_PROFILES = {"debug", "release"}
    LANGUAGE_DEFINITIONS = {
        "c": {"label": "C", "tool": "gcc", "filename": "main.c", "compile": True},
        "cpp": {"label": "C++", "tool": "g++", "filename": "main.cpp", "compile": True},
        "python": {"label": "Python", "tool": "python3", "filename": "main.py", "compile": False},
        "javascript": {"label": "JavaScript", "tool": "node", "filename": "main.js", "compile": False},
        "ruby": {"label": "Ruby", "tool": "ruby", "filename": "main.rb", "compile": False},
        "perl": {"label": "Perl", "tool": "perl", "filename": "main.pl", "compile": False},
        "php": {"label": "PHP", "tool": "php", "filename": "main.php", "compile": False},
        "csharp": {"label": "C#", "tool": "dotnet", "filename": "Program.cs", "compile": True},
        "asm": {
            "label": "Assembler x86-64",
            "tool": "as",
            "additional_tools": ("ld",),
            "filename": "main.s",
            "compile": True,
        },
        "bash": {"label": "Bash", "tool": "bash", "filename": "main.sh", "compile": False},
        "rust": {"label": "Rust", "tool": "rustc", "filename": "main.rs", "compile": True},
        "go": {"label": "Go", "tool": "go", "filename": "main.go", "compile": True},
        "java": {
            "label": "Java",
            "tool": "javac",
            "additional_tools": ("java",),
            "filename": "Main.java",
            "compile": True,
        },
    }

    def __init__(self) -> None:
        super().__init__()
        self.tool_paths = {
            language: self.gcc_path if language == "c" else shutil.which(str(definition["tool"]))
            for language, definition in self.LANGUAGE_DEFINITIONS.items()
        }
        self.additional_tool_paths = {
            language: {
                tool: shutil.which(tool)
                for tool in definition.get("additional_tools", ())
            }
            for language, definition in self.LANGUAGE_DEFINITIONS.items()
        }
        self.dotnet_target_framework = self._dotnet_target_framework()
        self.binary_inspection_tools = {
            "size": shutil.which("size"),
            "nm": shutil.which("nm"),
        }

    def status(self) -> dict[str, Any]:
        sandbox = super().status()
        languages: dict[str, dict[str, Any]] = {}
        for language, definition in self.LANGUAGE_DEFINITIONS.items():
            tool_path = self.tool_paths.get(language)
            missing_tools = ([] if tool_path else [str(definition["tool"])]) + [
                tool
                for tool, path in self.additional_tool_paths.get(language, {}).items()
                if not path
            ]
            available = bool(sandbox["available"] and not missing_tools)
            if missing_tools:
                joined_tools = ", ".join(missing_tools)
                message = f"Chýba nástroj: {joined_tools}."
            elif not sandbox["available"]:
                message = str(sandbox["message"])
            else:
                message = f"Skúšobňa {definition['label']} je pripravená."
            languages[language] = {"available": available, "message": message}
        missing_inspection_tools = [name for name, path in self.binary_inspection_tools.items() if not path]
        inspection_available = bool(sandbox["available"] and not missing_inspection_tools)
        inspection_message = (
            "Rozbor binárky je pripravený."
            if inspection_available
            else (
                f"Chýba nástroj: {', '.join(missing_inspection_tools)}."
                if missing_inspection_tools
                else str(sandbox["message"])
            )
        )
        return {
            **sandbox,
            "languages": languages,
            "binaryInspection": {"available": inspection_available, "message": inspection_message},
        }

    def run(
        self,
        language: Any,
        source: Any,
        stdin: Any,
        *,
        files: Any = None,
        entry_filename: Any = None,
        execute: bool = True,
        arguments: Any = None,
        build_profile: Any = "debug",
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
        command_arguments = self._command_arguments(arguments)
        profile = str(build_profile or "debug").strip().lower()
        if profile not in self.BUILD_PROFILES:
            raise CodeRunnerError("Neznámy profil zostavenia.")
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
            run_memory_limit = MEMORY_LIMIT_BYTES
            # -g1 keeps source locations while fitting inside the sandbox file-size limit.
            native_profile_flags = ["-O0", "-g1"] if profile == "debug" else ["-O2", "-DNDEBUG"]
            # AddressSanitizer needs a virtual-memory reservation larger than this sandbox permits.
            # UndefinedBehaviorSanitizer remains useful here and reports source locations safely.
            debug_runtime_checks = ["-fsanitize=undefined", "-fno-omit-frame-pointer"] if profile == "debug" else []

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
                        *native_profile_flags,
                        *debug_runtime_checks,
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
                        *native_profile_flags,
                        *debug_runtime_checks,
                        "-I/work",
                        *self._project_include_paths(project_files),
                        *source_paths,
                        "-o",
                        "/work/program",
                    ],
                    workspace,
                    timeout=COMPILE_TIMEOUT_SECONDS,
                    file_limit=COMPILE_FILE_LIMIT_BYTES,
                )
                if compile_result["timedOut"] or compile_result["outputLimited"] or compile_result["exitCode"] != 0:
                    return {"compiled": False, "compile": compile_result, "run": None}
                run_command = ["/work/program"]
                compile_result = {**compile_result, "stdout": compile_result["stdout"] or "Preklad prebehol úspešne."}
            elif language_id == "python":
                compile_result = self._execute(
                    [tool, "-m", "py_compile", entry_path],
                    workspace,
                    timeout=COMPILE_TIMEOUT_SECONDS,
                )
                if compile_result["timedOut"] or compile_result["outputLimited"] or compile_result["exitCode"] != 0:
                    return {"compiled": False, "compile": compile_result, "run": None}
                run_command = [tool, entry_path]
                compile_result = {**compile_result, "stdout": compile_result["stdout"] or "Kontrola syntaxe Pythonu prebehla úspešne."}
            elif language_id == "javascript":
                compile_result = self._execute(
                    [tool, "--check", entry_path],
                    workspace,
                    timeout=COMPILE_TIMEOUT_SECONDS,
                    memory_limit=NODE_MEMORY_LIMIT_BYTES,
                )
                if compile_result["timedOut"] or compile_result["outputLimited"] or compile_result["exitCode"] != 0:
                    return {"compiled": False, "compile": compile_result, "run": None}
                run_command = [tool, f"--max-old-space-size={NODE_MAX_OLD_SPACE_MB}", entry_path]
                run_memory_limit = NODE_MEMORY_LIMIT_BYTES
                compile_result = {**compile_result, "stdout": compile_result["stdout"] or "Kontrola syntaxe JavaScriptu prebehla úspešne."}
            elif language_id == "ruby":
                compile_result = self._execute(
                    [tool, "-c", entry_path],
                    workspace,
                    timeout=COMPILE_TIMEOUT_SECONDS,
                )
                if compile_result["timedOut"] or compile_result["outputLimited"] or compile_result["exitCode"] != 0:
                    return {"compiled": False, "compile": compile_result, "run": None}
                run_command = [tool, entry_path]
                compile_result = {**compile_result, "stdout": compile_result["stdout"] or "Kontrola syntaxe Ruby prebehla úspešne."}
            elif language_id == "perl":
                compile_result = self._execute(
                    [tool, "-c", entry_path],
                    workspace,
                    timeout=COMPILE_TIMEOUT_SECONDS,
                )
                if compile_result["timedOut"] or compile_result["outputLimited"] or compile_result["exitCode"] != 0:
                    return {"compiled": False, "compile": compile_result, "run": None}
                run_command = [tool, entry_path]
                compile_result = {**compile_result, "stdout": compile_result["stdout"] or "Kontrola syntaxe Perlu prebehla úspešne."}
            elif language_id == "php":
                compile_result = self._execute(
                    [tool, "-l", entry_path],
                    workspace,
                    timeout=COMPILE_TIMEOUT_SECONDS,
                )
                if compile_result["timedOut"] or compile_result["outputLimited"] or compile_result["exitCode"] != 0:
                    return {"compiled": False, "compile": compile_result, "run": None}
                run_command = [tool, entry_path]
            elif language_id == "bash":
                compile_result = self._execute(
                    [tool, "-n", entry_path],
                    workspace,
                    timeout=COMPILE_TIMEOUT_SECONDS,
                )
                if compile_result["timedOut"] or compile_result["outputLimited"] or compile_result["exitCode"] != 0:
                    return {"compiled": False, "compile": compile_result, "run": None}
                run_command = [tool, entry_path]
                compile_result = {**compile_result, "stdout": compile_result["stdout"] or "Kontrola syntaxe Bash skriptu prebehla úspešne."}
            elif language_id == "csharp":
                source_paths = [f"/work/{name}" for name, _ in project_files if name.lower().endswith(".cs")]
                if not source_paths:
                    raise CodeRunnerError("Projekt C# nemá zdrojový súbor s príponou .cs.")
                project_name = "PoznamkovnikProgram"
                project_file = workspace / f"{project_name}.csproj"
                project_file.write_text(
                    "\n".join(
                        (
                            '<Project Sdk="Microsoft.NET.Sdk">',
                            "  <PropertyGroup>",
                            "    <OutputType>Exe</OutputType>",
                            f"    <TargetFramework>{self.dotnet_target_framework}</TargetFramework>",
                            f"    <AssemblyName>{project_name}</AssemblyName>",
                            "    <ImplicitUsings>enable</ImplicitUsings>",
                            "    <Nullable>enable</Nullable>",
                            "  </PropertyGroup>",
                            "</Project>",
                            "",
                        )
                    ),
                    encoding="utf-8",
                )
                dotnet_environment = {
                    "DOTNET_CLI_HOME": "/tmp/dotnet",
                    "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
                    "DOTNET_NOLOGO": "1",
                    "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
                    "NUGET_PACKAGES": "/tmp/nuget-packages",
                }
                compile_result = self._execute(
                    [
                        tool,
                        "build",
                        f"/work/{project_name}.csproj",
                        "--configuration",
                        "Debug" if profile == "debug" else "Release",
                        "--output",
                        "/work/build",
                        "--nologo",
                    ],
                    workspace,
                    timeout=COMPILE_TIMEOUT_SECONDS,
                    memory_limit=COMPILED_LANGUAGE_MEMORY_LIMIT_BYTES,
                    environment=dotnet_environment,
                )
                if compile_result["timedOut"] or compile_result["outputLimited"] or compile_result["exitCode"] != 0:
                    return {"compiled": False, "compile": compile_result, "run": None}
                run_command = [tool, f"/work/build/{project_name}.dll"]
                run_memory_limit = COMPILED_LANGUAGE_MEMORY_LIMIT_BYTES
                compile_result = {**compile_result, "stdout": compile_result["stdout"] or "Preklad C# prebehol úspešne."}
            elif language_id == "asm":
                source_paths = [
                    f"/work/{name}"
                    for name, _ in project_files
                    if name.lower().endswith((".s", ".asm"))
                ]
                if not source_paths:
                    raise CodeRunnerError("Projekt assemblera nemá zdrojový súbor s príponou .s alebo .asm.")
                objects: list[str] = []
                compile_steps: list[dict[str, Any]] = []
                for index, source_path in enumerate(source_paths):
                    object_path = f"/work/object-{index}.o"
                    assemble_result = self._execute(
                        [tool, "--64", source_path, "-o", object_path],
                        workspace,
                        timeout=COMPILE_TIMEOUT_SECONDS,
                    )
                    compile_steps.append(assemble_result)
                    if assemble_result["timedOut"] or assemble_result["outputLimited"] or assemble_result["exitCode"] != 0:
                        return {"compiled": False, "compile": self._merge_compile_results(compile_steps), "run": None}
                    objects.append(object_path)
                link_result = self._execute(
                    [str(self.additional_tool_paths[language_id]["ld"]), "-o", "/work/program", *objects],
                    workspace,
                    timeout=COMPILE_TIMEOUT_SECONDS,
                )
                compile_steps.append(link_result)
                compile_result = self._merge_compile_results(compile_steps)
                if link_result["timedOut"] or link_result["outputLimited"] or link_result["exitCode"] != 0:
                    return {"compiled": False, "compile": compile_result, "run": None}
                run_command = ["/work/program"]
            elif language_id == "rust":
                source_paths = [f"/work/{name}" for name, _ in project_files if name.lower().endswith(".rs")]
                if not source_paths:
                    raise CodeRunnerError("Projekt Rust nemá zdrojový súbor s príponou .rs.")
                compile_result = self._execute(
                    [
                        tool,
                        "--edition=2021",
                        "-C",
                        "debuginfo=2" if profile == "debug" else "debuginfo=0",
                        "-C",
                        "opt-level=0" if profile == "debug" else "opt-level=2",
                        entry_path,
                        "-o",
                        "/work/program",
                    ],
                    workspace,
                    timeout=COMPILE_TIMEOUT_SECONDS,
                    memory_limit=COMPILED_LANGUAGE_MEMORY_LIMIT_BYTES,
                )
                if compile_result["timedOut"] or compile_result["outputLimited"] or compile_result["exitCode"] != 0:
                    return {"compiled": False, "compile": compile_result, "run": None}
                run_command = ["/work/program"]
                compile_result = {**compile_result, "stdout": compile_result["stdout"] or "Preklad Rust prebehol úspešne."}
            elif language_id == "go":
                source_paths = [f"/work/{name}" for name, _ in project_files if name.lower().endswith(".go")]
                if not source_paths:
                    raise CodeRunnerError("Projekt Go nemá zdrojový súbor s príponou .go.")
                entry_directory = PurePosixPath(filename).parent
                package_path = "." if str(entry_directory) in {"", "."} else f"./{entry_directory}"
                if not any(name == "go.mod" for name, _ in project_files):
                    (workspace / "go.mod").write_text("module poznamkovnik.local/project\ngo 1.20\n", encoding="utf-8")
                compile_result = self._execute(
                    [tool, "build", *(["-trimpath"] if profile == "release" else []), "-o", "/work/program", package_path],
                    workspace,
                    timeout=COMPILE_TIMEOUT_SECONDS,
                    memory_limit=COMPILED_LANGUAGE_MEMORY_LIMIT_BYTES,
                    environment={
                        "GOCACHE": "/tmp/go-build",
                        "GOMODCACHE": "/tmp/go-mod",
                        "GOPATH": "/tmp/go",
                    },
                )
                if compile_result["timedOut"] or compile_result["outputLimited"] or compile_result["exitCode"] != 0:
                    return {"compiled": False, "compile": compile_result, "run": None}
                run_command = ["/work/program"]
                compile_result = {**compile_result, "stdout": compile_result["stdout"] or "Preklad Go prebehol úspešne."}
            elif language_id == "java":
                source_paths = [f"/work/{name}" for name, _ in project_files if name.lower().endswith(".java")]
                if not source_paths:
                    raise CodeRunnerError("Projekt Java nemá zdrojový súbor s príponou .java.")
                entry_source = next(content for name, content in project_files if name == filename)
                package_match = re.search(r"^\s*package\s+([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*;", entry_source, re.MULTILINE)
                class_name = PurePosixPath(filename).stem
                main_class = f"{package_match.group(1)}.{class_name}" if package_match else class_name
                (workspace / "classes").mkdir()
                compile_result = self._execute(
                    [
                        tool,
                        f"-J-Xmx{JAVA_MAX_HEAP_MB}m",
                        f"-J-XX:MaxMetaspaceSize={JAVA_MAX_METASPACE_MB}m",
                        "-g" if profile == "debug" else "-g:none",
                        "-d",
                        "/work/classes",
                        *source_paths,
                    ],
                    workspace,
                    timeout=COMPILE_TIMEOUT_SECONDS,
                    memory_limit=COMPILED_LANGUAGE_MEMORY_LIMIT_BYTES,
                )
                if compile_result["timedOut"] or compile_result["outputLimited"] or compile_result["exitCode"] != 0:
                    return {"compiled": False, "compile": compile_result, "run": None}
                run_command = [
                    str(self.additional_tool_paths[language_id]["java"]),
                    f"-Xmx{JAVA_MAX_HEAP_MB}m",
                    f"-XX:MaxMetaspaceSize={JAVA_MAX_METASPACE_MB}m",
                    "-cp",
                    "/work/classes",
                    main_class,
                ]
                run_memory_limit = COMPILED_LANGUAGE_MEMORY_LIMIT_BYTES
                compile_result = {**compile_result, "stdout": compile_result["stdout"] or "Preklad Java prebehol úspešne."}
            else:
                raise CodeRunnerError("Tento jazyk ešte nemá bezpečný profil spúšťania.")

            inspection = self._native_binary_inspection(workspace) if language_id in {"c", "cpp", "asm"} else None
            if not execute:
                return {
                    "compiled": True,
                    "compile": compile_result,
                    "run": None,
                    "buildProfile": profile,
                    "inspection": inspection,
                }
            run_result = self._execute(
                [*run_command, *command_arguments],
                workspace,
                timeout=RUN_TIMEOUT_SECONDS,
                stdin_path=input_path,
                memory_limit=run_memory_limit,
            )
            return {
                "compiled": True,
                "compile": compile_result,
                "run": run_result,
                "buildProfile": profile,
                "inspection": inspection,
            }

    def _native_binary_inspection(self, workspace: Path) -> dict[str, Any]:
        size_tool = self.binary_inspection_tools.get("size")
        nm_tool = self.binary_inspection_tools.get("nm")
        if not size_tool or not nm_tool:
            missing = ", ".join(name for name, path in self.binary_inspection_tools.items() if not path)
            return {"available": False, "message": f"Chýba nástroj na rozbor binárky: {missing}."}

        memory_result = self._execute(
            [str(size_tool), "--format=Berkeley", "--radix=10", "/work/program"],
            workspace,
            timeout=1.5,
        )
        section_result = self._execute(
            [str(size_tool), "--format=SysV", "--radix=10", "/work/program"],
            workspace,
            timeout=1.5,
        )
        symbol_result = self._execute(
            [str(nm_tool), "--defined-only", "--demangle", "--size-sort", "-S", "/work/program"],
            workspace,
            timeout=1.5,
        )
        failures = [
            result
            for result in (memory_result, section_result, symbol_result)
            if result["timedOut"] or result["outputLimited"] or result["exitCode"] != 0
        ]
        if failures:
            detail = "\n".join(
                str(result.get("stderr") or result.get("stdout") or "").strip() for result in failures
            ).strip()
            return {
                "available": False,
                "message": detail[:500] or "Rozbor binárky sa nepodarilo dokončiť.",
            }

        memory = self._parse_binary_memory(str(memory_result.get("stdout") or ""))
        sections = self._parse_binary_sections(str(section_result.get("stdout") or ""))
        symbols = self._parse_binary_symbols(str(symbol_result.get("stdout") or ""))
        return {
            "available": True,
            "memory": memory,
            "sections": sections,
            "symbols": symbols,
        }

    @staticmethod
    def _parse_binary_memory(output: str) -> dict[str, int]:
        lines = [line.split() for line in output.splitlines() if line.strip()]
        for fields in lines:
            if len(fields) < 6 or fields[0].lower() == "text":
                continue
            try:
                text_size, data_size, bss_size, total = (int(fields[index], 10) for index in range(4))
            except ValueError:
                continue
            return {"text": text_size, "data": data_size, "bss": bss_size, "total": total}
        return {"text": 0, "data": 0, "bss": 0, "total": 0}

    @staticmethod
    def _parse_binary_sections(output: str) -> list[dict[str, int | str]]:
        sections: list[dict[str, int | str]] = []
        for line in output.splitlines():
            fields = line.split()
            if len(fields) < 3 or fields[0].lower() in {"section", "total"}:
                continue
            try:
                size = int(fields[1], 10)
                address = int(fields[2], 10)
            except ValueError:
                continue
            sections.append({"name": fields[0], "size": size, "address": address})
        return sorted(sections, key=lambda section: int(section["size"]), reverse=True)[:80]

    @staticmethod
    def _parse_binary_symbols(output: str) -> list[dict[str, int | str]]:
        symbols: list[dict[str, int | str]] = []
        expression = re.compile(r"^([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+([A-Za-z?])\s+(.+)$")
        for line in output.splitlines():
            match = expression.match(line.strip())
            if not match:
                continue
            try:
                address = int(match.group(1), 16)
                size = int(match.group(2), 16)
            except ValueError:
                continue
            if not size:
                continue
            symbols.append(
                {
                    "address": address,
                    "size": size,
                    "type": match.group(3),
                    "name": match.group(4),
                }
            )
        return sorted(symbols, key=lambda symbol: int(symbol["size"]), reverse=True)[:MAX_BINARY_INSPECTION_SYMBOLS]

    def _command_arguments(self, arguments: Any) -> list[str]:
        raw_arguments = self._limited_text(arguments, MAX_ARGUMENT_BYTES, "Parametre spúšťania sú príliš dlhé.")
        if not raw_arguments.strip():
            return []
        try:
            parsed = shlex.split(raw_arguments, posix=True)
        except ValueError as error:
            raise CodeRunnerError(f"Parametre spúšťania majú neuzatvorené úvodzovky: {error}") from error
        if len(parsed) > MAX_ARGUMENT_COUNT:
            raise CodeRunnerError(f"Program môže dostať najviac {MAX_ARGUMENT_COUNT} parametrov.")
        return parsed

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

    def _dotnet_target_framework(self) -> str:
        dotnet = self.tool_paths.get("csharp")
        if not dotnet:
            return "net8.0"
        try:
            result = subprocess.run([dotnet, "--version"], capture_output=True, check=False, text=True, timeout=1.5)
        except OSError:
            return "net8.0"
        match = re.match(r"(\d+)\.", result.stdout.strip())
        return f"net{match.group(1)}.0" if match else "net8.0"

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

    @staticmethod
    def _merge_compile_results(results: list[dict[str, Any]]) -> dict[str, Any]:
        if not results:
            return DevelopmentCodeRunner._skipped_compile_result("Preklad neprebehol.")
        stdout = "\n".join(str(result.get("stdout") or "").strip() for result in results if result.get("stdout")).strip()
        stderr = "\n".join(str(result.get("stderr") or "").strip() for result in results if result.get("stderr")).strip()
        last = results[-1]
        return {
            "stdout": stdout or "Preklad prebehol úspešne.",
            "stderr": stderr,
            "exitCode": int(last.get("exitCode", 0)),
            "timedOut": any(bool(result.get("timedOut")) for result in results),
            "outputLimited": any(bool(result.get("outputLimited")) for result in results),
            "durationMs": sum(int(result.get("durationMs", 0)) for result in results),
        }
