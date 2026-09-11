"""Isolated, short-lived GDB sessions for C and C++ development projects."""

from __future__ import annotations

import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .code_runner import (
    COMPILED_LANGUAGE_MEMORY_LIMIT_BYTES,
    COMPILE_TIMEOUT_SECONDS,
    MAX_INPUT_BYTES,
    MAX_SOURCE_BYTES,
    CodeRunnerError,
    DevelopmentCodeRunner,
)


DEBUGGER_COMMAND_TIMEOUT_SECONDS = 3.0
DEBUGGER_SESSION_IDLE_SECONDS = 5 * 60
MAX_DEBUGGER_SESSIONS = 2


class DebuggerError(ValueError):
    """The debugger cannot safely complete a requested operation."""


@dataclass
class DebugSession:
    session_id: str
    user_id: str
    project_id: str
    workspace: Path
    process: subprocess.Popen[bytes]
    output: queue.Queue[str | None]
    created_at: float
    last_active_at: float
    token: int = 0


class DevelopmentDebugger(DevelopmentCodeRunner):
    """Runs GDB only inside the same private sandbox as the code runner.

    A session owns a temporary workspace and is deliberately short-lived.  It
    never attaches to an existing process and is discarded after five minutes
    of inactivity, which keeps the debugger from becoming an escape hatch out
    of the execution sandbox.
    """

    SUPPORTED_LANGUAGES = {"c", "cpp"}

    def __init__(self) -> None:
        super().__init__()
        self.gdb_path = shutil.which("gdb")
        self._debug_status: dict[str, Any] | None = None
        self._sessions: dict[str, DebugSession] = {}
        self._lock = threading.RLock()

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._cleanup_expired()
            if self._debug_status is None:
                self._debug_status = self._probe_status()
            return {**self._debug_status, "activeSessions": len(self._sessions)}

    def start(
        self,
        user_id: str,
        project_id: str,
        entry: dict[str, Any],
        *,
        stdin: Any = "",
        arguments: Any = "",
        breakpoints: Any = None,
    ) -> dict[str, Any]:
        status = self.status()
        if not status["available"]:
            raise DebuggerError(str(status["message"]))
        language = str(entry.get("language") or "").strip()
        if language not in self.SUPPORTED_LANGUAGES:
            raise DebuggerError("Krokové ladenie je zatiaľ pripravené pre C a C++.")

        source = self._limited_text(entry.get("source"), MAX_SOURCE_BYTES, "Zdrojový kód je príliš veľký.")
        if not source.strip():
            raise DebuggerError("Zdrojový kód nemôže byť prázdny.")
        input_text = self._limited_text(stdin, MAX_INPUT_BYTES, "Vstup programu je príliš veľký.")
        command_arguments = self._command_arguments(arguments)
        entry_filename = self._safe_project_path(entry.get("filename"))
        project_files = self._project_files(entry.get("files"), entry_filename, source)

        with self._lock:
            self._cleanup_expired()
            while len(self._sessions) >= MAX_DEBUGGER_SESSIONS:
                oldest = min(self._sessions.values(), key=lambda item: item.last_active_at)
                self._stop_session(oldest)

        workspace = Path(tempfile.mkdtemp(prefix=f"poznamkovnik-debug-{language}-"))
        try:
            self._write_project_files(workspace, project_files)
            (workspace / "stdin.txt").write_text(input_text, encoding="utf-8")
            compile_result = self._compile_project(language, project_files, workspace)
            if compile_result["timedOut"] or compile_result["outputLimited"] or compile_result["exitCode"] != 0:
                shutil.rmtree(workspace, ignore_errors=True)
                return {"compiled": False, "compile": compile_result, "session": None}

            session = self._launch_session(user_id, project_id, workspace, command_arguments)
            try:
                self._command(session, "-gdb-set pagination off")
                self._command(session, "-gdb-set confirm off")
                self._command(session, "-gdb-set print pretty on")
                self._command(session, "-environment-cd /work")
                self._command(session, "-file-exec-and-symbols /work/program")
                inserted = self._insert_breakpoints(session, breakpoints, project_files)
                if not inserted:
                    self._command(session, "-break-insert main")
                event = self._command(session, "-exec-run < /work/stdin.txt", wait_for_stop=True)
                snapshot = self._snapshot(session, event)
            except Exception:
                self._stop_session(session)
                raise

            with self._lock:
                self._sessions[session.session_id] = session
            compile_result = {
                **compile_result,
                "stdout": compile_result["stdout"] or "Preklad pre ladenie prebehol úspešne.",
            }
            return {
                "compiled": True,
                "compile": compile_result,
                "session": {"id": session.session_id, **snapshot},
            }
        except Exception:
            if workspace.exists() and not any(item.workspace == workspace for item in self._sessions.values()):
                shutil.rmtree(workspace, ignore_errors=True)
            raise

    def command(self, user_id: str, session_id: str, action: Any) -> dict[str, Any]:
        session = self._session_for(user_id, session_id)
        command = {
            "step": "-exec-step",
            "next": "-exec-next",
            "continue": "-exec-continue",
        }.get(str(action or ""))
        if not command:
            raise DebuggerError("Neznámy príkaz debuggeru.")
        try:
            event = self._command(session, command, wait_for_stop=True)
            return {"session": {"id": session.session_id, **self._snapshot(session, event)}}
        except DebuggerError:
            if session.process.poll() is not None:
                self.stop(user_id, session_id)
            raise

    def stop(self, user_id: str, session_id: str) -> None:
        session = self._session_for(user_id, session_id)
        with self._lock:
            self._stop_session(session)

    def close(self) -> None:
        with self._lock:
            for session in list(self._sessions.values()):
                self._stop_session(session)

    def _probe_status(self) -> dict[str, Any]:
        runtime = super().status()
        if not runtime["available"]:
            return {"available": False, "message": str(runtime["message"])}
        if not self.gdb_path:
            return {"available": False, "message": "Pre krokové ladenie chýba GDB."}
        try:
            with tempfile.TemporaryDirectory(prefix="poznamkovnik-debug-check-") as temporary:
                probe = self._execute(
                    [
                        self.gdb_path,
                        "--batch",
                        "--quiet",
                        "--nx",
                        "-ex",
                        "set pagination off",
                        "-ex",
                        "run",
                        "--args",
                        "/usr/bin/true",
                    ],
                    Path(temporary),
                    timeout=DEBUGGER_COMMAND_TIMEOUT_SECONDS,
                    memory_limit=COMPILED_LANGUAGE_MEMORY_LIMIT_BYTES,
                )
        except (CodeRunnerError, OSError):
            return {"available": False, "message": "Bezpečný debugger sa nepodarilo spustiť."}
        details = "\n".join((str(probe.get("stdout") or ""), str(probe.get("stderr") or ""))).lower()
        if "ptrace" in details or "could not trace" in details:
            return {
                "available": False,
                "message": "Hostiteľ momentálne nepovoľuje debuggeru sledovať bezpečne spustený program.",
            }
        if probe["exitCode"] != 0 or probe["timedOut"] or probe["outputLimited"]:
            return {"available": False, "message": "Bezpečný debugger nie je v tomto prostredí pripravený."}
        return {"available": True, "message": "Krokové ladenie C a C++ je pripravené."}

    def _compile_project(
        self, language: str, project_files: list[tuple[str, str]], workspace: Path
    ) -> dict[str, Any]:
        source_paths = [
            f"/work/{filename}"
            for filename, _ in project_files
            if filename.lower().endswith(".c" if language == "c" else (".cpp", ".cc", ".cxx", ".c++"))
        ]
        if not source_paths:
            suffix = ".c" if language == "c" else ".cpp, .cc alebo .cxx"
            raise DebuggerError(f"Projekt nemá zdrojový súbor s príponou {suffix}.")
        compiler = str(self.tool_paths[language])
        standard = "-std=c17" if language == "c" else "-std=c++20"
        flags = ["-Wall", "-Wextra", "-Wpedantic", "-O0", "-g3", "-fno-omit-frame-pointer"]
        if language == "c":
            flags.extend(["-Wconversion", "-Wshadow", "-Wformat=2"])
        return self._execute(
            [
                compiler,
                standard,
                *flags,
                "-I/work",
                *self._project_include_paths(project_files),
                *source_paths,
                "-o",
                "/work/program",
            ],
            workspace,
            timeout=COMPILE_TIMEOUT_SECONDS,
            memory_limit=COMPILED_LANGUAGE_MEMORY_LIMIT_BYTES,
        )

    def _launch_session(
        self, user_id: str, project_id: str, workspace: Path, arguments: list[str]
    ) -> DebugSession:
        command = [
            str(self.gdb_path),
            "--interpreter=mi2",
            "--quiet",
            "--nx",
            "--args",
            "/work/program",
            *arguments,
        ]
        try:
            process = subprocess.Popen(
                self._sandbox_command(workspace, command, memory_limit=COMPILED_LANGUAGE_MEMORY_LIMIT_BYTES),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=workspace,
                start_new_session=True,
            )
        except (OSError, subprocess.SubprocessError, CodeRunnerError) as error:
            raise DebuggerError("Bezpečný debugger sa nepodarilo spustiť.") from error
        if process.stdin is None or process.stdout is None:
            self._terminate(process)
            raise DebuggerError("Debugger nemá dostupné komunikačné kanály.")
        messages: queue.Queue[str | None] = queue.Queue()

        def collect() -> None:
            try:
                for line in iter(process.stdout.readline, b""):
                    messages.put(line.decode("utf-8", errors="replace").rstrip("\r\n"))
            finally:
                messages.put(None)

        threading.Thread(target=collect, name="poznamkovnik-gdb", daemon=True).start()
        now = time.monotonic()
        return DebugSession(str(uuid.uuid4()), user_id, project_id, workspace, process, messages, now, now)

    def _insert_breakpoints(
        self, session: DebugSession, values: Any, files: list[tuple[str, str]]
    ) -> bool:
        if not isinstance(values, list):
            return False
        valid_files = {filename for filename, _ in files}
        inserted = False
        for value in values[:24]:
            if not isinstance(value, dict):
                continue
            try:
                filename = self._safe_project_path(value.get("filename"))
                line = int(value.get("line"))
            except (CodeRunnerError, TypeError, ValueError):
                continue
            if filename not in valid_files or line < 1 or line > 100_000:
                continue
            self._command(session, f"-break-insert /work/{filename}:{line}")
            inserted = True
        return inserted

    def _session_for(self, user_id: str, session_id: str) -> DebugSession:
        with self._lock:
            self._cleanup_expired()
            session = self._sessions.get(str(session_id or ""))
            if not session or session.user_id != user_id:
                raise DebuggerError("Ladiaca relácia už neexistuje.")
            return session

    def _command(self, session: DebugSession, command: str, *, wait_for_stop: bool = False) -> list[str]:
        if session.process.poll() is not None:
            raise DebuggerError("Ladiaca relácia už skončila.")
        assert session.process.stdin is not None
        session.token += 1
        token = session.token
        try:
            session.process.stdin.write(f"{token}{command}\n".encode("utf-8"))
            session.process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            raise DebuggerError("Spojenie s debuggerom sa prerušilo.") from error

        result_prefix = f"{token}^"
        received: list[str] = []
        result_seen = False
        deadline = time.monotonic() + DEBUGGER_COMMAND_TIMEOUT_SECONDS
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DebuggerError("Debugger neodpovedal v časovom limite.")
            try:
                line = session.output.get(timeout=min(remaining, 0.2))
            except queue.Empty:
                continue
            if line is None:
                raise DebuggerError("Ladiaca relácia sa ukončila.")
            received.append(line)
            if line.startswith(result_prefix):
                if "^error" in line:
                    raise DebuggerError(self._mi_message(line) or "Debugger odmietol príkaz.")
                result_seen = True
                if not wait_for_stop:
                    session.last_active_at = time.monotonic()
                    return received
            if wait_for_stop and result_seen and line.startswith("*stopped"):
                session.last_active_at = time.monotonic()
                return received

    def _snapshot(self, session: DebugSession, event: list[str]) -> dict[str, Any]:
        stopped = next((line for line in event if line.startswith("*stopped")), "")
        stop = self._mi_attributes(stopped)
        reason = stop.get("reason", "stopped")
        location = self._location(stop)
        state = "finished" if reason.startswith("exited") else "paused"
        frames: list[dict[str, Any]] = []
        variables: list[dict[str, str]] = []
        transcript = list(event)
        if state == "paused":
            try:
                stack = self._command(session, "-stack-list-frames")
                local_values = self._command(session, "-stack-list-variables --simple-values")
                transcript.extend(stack)
                transcript.extend(local_values)
                frames = self._frames(stack)
                variables = self._variables(local_values)
            except DebuggerError as error:
                transcript.append(str(error))
        return {
            "state": state,
            "reason": reason,
            "location": location,
            "frames": frames,
            "variables": variables,
            "transcript": "\n".join(line for line in transcript if line and line != "(gdb)"),
        }

    def _cleanup_expired(self) -> None:
        deadline = time.monotonic() - DEBUGGER_SESSION_IDLE_SECONDS
        for session in list(self._sessions.values()):
            if session.last_active_at < deadline or session.process.poll() is not None:
                self._stop_session(session)

    def _stop_session(self, session: DebugSession) -> None:
        self._sessions.pop(session.session_id, None)
        if session.process.poll() is None:
            try:
                assert session.process.stdin is not None
                session.process.stdin.write(b"-gdb-exit\n")
                session.process.stdin.flush()
                session.process.wait(timeout=0.3)
            except (AssertionError, BrokenPipeError, OSError, subprocess.TimeoutExpired):
                self._terminate(session.process)
        shutil.rmtree(session.workspace, ignore_errors=True)

    @staticmethod
    def _mi_attributes(value: str) -> dict[str, str]:
        attributes: dict[str, str] = {}
        for match in re.finditer(r'([A-Za-z][A-Za-z0-9_-]*)="((?:\\.|[^"\\])*)"', value):
            attributes[match.group(1)] = DevelopmentDebugger._mi_unescape(match.group(2))
        return attributes

    @staticmethod
    def _mi_unescape(value: str) -> str:
        return (
            value.replace(r"\\", "\\")
            .replace(r'\"', '"')
            .replace(r"\n", "\n")
            .replace(r"\t", "\t")
        )

    @classmethod
    def _location(cls, attributes: dict[str, str]) -> dict[str, Any] | None:
        filename = attributes.get("fullname") or attributes.get("file")
        line = attributes.get("line")
        if not filename or not line or not line.isdigit():
            return None
        return {
            "filename": filename.removeprefix("/work/"),
            "line": int(line),
            "function": attributes.get("func", ""),
        }

    @classmethod
    def _frames(cls, records: list[str]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for record in records:
            for frame in re.findall(r"frame=\{([^{}]*)\}", record):
                attributes = cls._mi_attributes(frame)
                location = cls._location(attributes)
                result.append(
                    {
                        "level": int(attributes.get("level", len(result)) or 0),
                        "function": attributes.get("func", "?"),
                        "location": location,
                    }
                )
        return result[:64]

    @classmethod
    def _variables(cls, records: list[str]) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for record in records:
            for variable in re.findall(r"\{([^{}]*)\}", record):
                attributes = cls._mi_attributes(variable)
                if attributes.get("name"):
                    result.append({"name": attributes["name"], "value": attributes.get("value", "?")})
        return result[:64]

    @staticmethod
    def _mi_message(record: str) -> str:
        return DevelopmentDebugger._mi_attributes(record).get("msg", "")
