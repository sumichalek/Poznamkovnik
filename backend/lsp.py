"""Small local bridge between the Development panel and language servers.

The language servers only analyse a temporary mirror of a project.  They never
run code from the project and are kept out of the application data directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import select
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlparse


LSP_START_TIMEOUT_SECONDS = 3.0
LSP_REQUEST_TIMEOUT_SECONDS = 1.4
MAX_LSP_SOURCE_BYTES = 2_000_000
MAX_LSP_WORKSPACE_FILES = 500
MAX_LSP_WORKSPACE_BYTES = 12 * 1024 * 1024
MAX_LSP_RESULT_LOCATIONS = 500
MAX_LSP_WORKSPACE_EDIT_FILES = 500
MAX_LSP_WORKSPACE_EDITS = 20_000
MAX_LSP_SESSIONS = 12
LSP_SESSION_IDLE_SECONDS = 15 * 60
SUPPORTED_OPERATIONS = {"completion", "definition", "references", "symbols", "prepareRename", "rename"}
LANGUAGE_SERVER_DEFINITIONS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "c": ("clangd", "clangd", ("--background-index=false", "--clang-tidy=false")),
    "cpp": ("clangd", "clangd", ("--background-index=false", "--clang-tidy=false")),
    "python": ("python-lsp-server", "pylsp", ()),
    "javascript": ("TypeScript Language Server", "typescript-language-server", ("--stdio",)),
    "php": ("Intelephense", "intelephense", ("--stdio",)),
    "csharp": ("csharp-ls", "csharp-ls", ()),
    "java": ("Eclipse JDT LS", "jdtls", ()),
    "bash": ("Bash Language Server", "bash-language-server", ("start",)),
    "ruby": ("Ruby LSP", "ruby-lsp", ()),
    "asm": ("asm-lsp", "asm-lsp", ()),
    "go": ("gopls", "gopls", ()),
    "rust": ("rust-analyzer", "rust-analyzer", ()),
}


class LanguageServiceError(ValueError):
    """A local language server did not provide a usable answer."""


def _server_command(language: str) -> list[str] | None:
    definition = LANGUAGE_SERVER_DEFINITIONS.get(language)
    if not definition:
        return None
    _, executable_name, arguments = definition
    executable = shutil.which(executable_name)
    return [executable, *arguments] if executable else None


def _safe_relative_path(value: Any) -> PurePosixPath:
    path = PurePosixPath(str(value or ""))
    if not path.parts or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise LanguageServiceError("Jazykový server dostal neplatnú cestu súboru.")
    return path


def _limited_source(value: Any) -> str:
    source = str(value or "")
    if len(source.encode("utf-8", errors="replace")) > MAX_LSP_SOURCE_BYTES:
        raise LanguageServiceError("Súbor je na analýzu jazykovým serverom príliš veľký.")
    return source


class _LspSession:
    """One serial stdio JSON-RPC conversation with a single language server."""

    def __init__(self, command: list[str], root: Path, language: str) -> None:
        self.command = command
        self.root = root
        self.language = language
        self.process: subprocess.Popen[bytes] | None = None
        self._buffer = b""
        self._next_request_id = 1
        self._documents: dict[str, tuple[int, str]] = {}
        self._workspace_sources: dict[str, str] = {}
        self._compile_commands = ""
        self._last_used = time.monotonic()
        self._lock = threading.RLock()

    def last_used(self) -> float:
        with self._lock:
            return self._last_used

    def close(self, *, remove_workspace: bool = False) -> None:
        with self._lock:
            process = self.process
            try:
                if process and process.poll() is None:
                    self._send({"jsonrpc": "2.0", "id": self._next_id(), "method": "shutdown", "params": None})
                    self._send({"jsonrpc": "2.0", "method": "exit", "params": {}})
                    process.terminate()
                    process.wait(timeout=0.3)
            except (OSError, subprocess.SubprocessError):
                try:
                    process.kill()
                except OSError:
                    pass
            finally:
                self.process = None
                self._documents.clear()
                self._workspace_sources.clear()
                self._compile_commands = ""
                self._buffer = b""
                for stream in (process.stdin, process.stdout, process.stderr) if process else ():
                    if stream is None:
                        continue
                    try:
                        stream.close()
                    except OSError:
                        pass
                if remove_workspace:
                    shutil.rmtree(self.root, ignore_errors=True)

    def query(
        self,
        files: list[dict[str, Any]],
        filename: str,
        source: str,
        operation: str,
        line: int,
        column: int,
        new_name: str = "",
    ) -> dict[str, Any]:
        with self._lock:
            self._last_used = time.monotonic()
            try:
                self._write_workspace(files, filename, source)
                self._ensure_started()
                uri = (self.root / _safe_relative_path(filename)).resolve().as_uri()
                self._sync_document(uri, source)
                position = {"line": max(0, line - 1), "character": max(0, column - 1)}
                params: dict[str, Any] = {"textDocument": {"uri": uri}}
                if operation == "completion":
                    params.update({"position": position, "context": {"triggerKind": 1}})
                    result = self._request("textDocument/completion", params)
                    return {"items": self._completion_items(result)}
                if operation == "definition":
                    params["position"] = position
                    return {"locations": self._locations(self._request("textDocument/definition", params))}
                if operation == "references":
                    params.update({"position": position, "context": {"includeDeclaration": True}})
                    return {"locations": self._locations(self._request("textDocument/references", params))}
                if operation == "symbols":
                    return {"symbols": self._symbols(self._request("textDocument/documentSymbol", params))}
                if operation == "prepareRename":
                    params["position"] = position
                    return {"range": self._range(self._request("textDocument/prepareRename", params))}
                if operation == "rename":
                    if not new_name:
                        raise LanguageServiceError("Pre jazykový server chýba nový názov symbolu.")
                    params.update({"position": position, "newName": new_name})
                    return {"workspaceEdits": self._workspace_edits(self._request("textDocument/rename", params))}
                raise LanguageServiceError("Jazykový server dostal neznámu operáciu.")
            finally:
                self._last_used = time.monotonic()

    def _write_workspace(self, files: list[dict[str, Any]], active_filename: str, active_source: str) -> None:
        if len(files) > MAX_LSP_WORKSPACE_FILES:
            raise LanguageServiceError("Projekt má na analýzu jazykovým serverom príliš veľa súborov.")
        if not self._workspace_sources:
            shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True, exist_ok=True)
        active_path = _safe_relative_path(active_filename).as_posix()
        sources: dict[str, str] = {}
        total_bytes = 0
        for item in files:
            if not isinstance(item, dict):
                continue
            relative = _safe_relative_path(item.get("title"))
            content = active_source if relative.as_posix() == active_path else _limited_source(item.get("content"))
            total_bytes += len(content.encode("utf-8", errors="replace"))
            if total_bytes > MAX_LSP_WORKSPACE_BYTES:
                raise LanguageServiceError("Projekt je na analýzu jazykovým serverom príliš veľký.")
            sources[relative.as_posix()] = content
        if active_path not in sources:
            raise LanguageServiceError("Aktívny súbor jazykového servera sa v projekte nenašiel.")

        for relative, content in sources.items():
            target = (self.root / _safe_relative_path(relative)).resolve()
            try:
                target.relative_to(self.root.resolve())
            except ValueError as error:
                raise LanguageServiceError("Jazykový server dostal neplatnú cestu súboru.") from error
            if self._workspace_sources.get(relative) != content or not target.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
        for relative in set(self._workspace_sources) - set(sources):
            (self.root / _safe_relative_path(relative)).unlink(missing_ok=True)
        self._workspace_sources = sources

        if self.language in {"c", "cpp"}:
            compiler = "clang++" if self.language == "cpp" else "clang"
            standard = "c++20" if self.language == "cpp" else "c17"
            compile_commands = [
                {
                    "directory": str(self.root),
                    "file": str(self.root / path),
                    "arguments": [compiler, f"-std={standard}", "-I", str(self.root), "-fsyntax-only", str(self.root / path)],
                }
                for path in sorted(sources)
                if Path(path).suffix.lower() in ({".cc", ".cp", ".cxx", ".cpp"} if self.language == "cpp" else {".c"})
            ]
            serialized = json.dumps(compile_commands, separators=(",", ":"))
            if serialized != self._compile_commands:
                (self.root / "compile_commands.json").write_text(serialized, encoding="utf-8")
                self._compile_commands = serialized

    def _ensure_started(self) -> None:
        if self.process and self.process.poll() is None:
            return
        self.close()
        try:
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=self.root,
                env={"PATH": os.environ.get("PATH", ""), "HOME": str(self.root), "LANG": "C.UTF-8"},
                start_new_session=True,
                bufsize=0,
            )
        except OSError as error:
            self.process = None
            raise LanguageServiceError("Jazykový server sa nepodarilo spustiť.") from error
        try:
            self._request(
                "initialize",
                {
                    "processId": os.getpid(),
                    "rootUri": self.root.resolve().as_uri(),
                    "workspaceFolders": [{"uri": self.root.resolve().as_uri(), "name": "projekt"}],
                    "capabilities": {
                        "workspace": {"configuration": True, "workspaceFolders": True},
                        "textDocument": {
                            "completion": {"completionItem": {"snippetSupport": True}},
                            "definition": {"linkSupport": True},
                        },
                    },
                    "initializationOptions": {"fallbackFlags": ["-I", str(self.root)]}
                    if self.language in {"c", "cpp"}
                    else {},
                },
                timeout=LSP_START_TIMEOUT_SECONDS,
            )
            self._notify("initialized", {})
        except LanguageServiceError:
            self.close()
            raise

    def _sync_document(self, uri: str, source: str) -> None:
        current = self._documents.get(uri)
        if current is None:
            self._documents[uri] = (1, source)
            self._notify(
                "textDocument/didOpen",
                {"textDocument": {"uri": uri, "languageId": self.language, "version": 1, "text": source}},
            )
            return
        version, previous_source = current
        if source == previous_source:
            return
        next_version = version + 1
        self._documents[uri] = (next_version, source)
        self._notify(
            "textDocument/didChange",
            {
                "textDocument": {"uri": uri, "version": next_version},
                "contentChanges": [{"text": source}],
            },
        )

    def _request(self, method: str, params: dict[str, Any], *, timeout: float = LSP_REQUEST_TIMEOUT_SECONDS) -> Any:
        request_id = self._next_id()
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while True:
            message = self._read_message(deadline)
            if message is None:
                self.close()
                raise LanguageServiceError("Jazykový server odpovedá príliš dlho.")
            if message.get("id") == request_id:
                if "error" in message:
                    detail = message.get("error") if isinstance(message.get("error"), dict) else {}
                    raise LanguageServiceError(str(detail.get("message") or "Jazykový server vrátil chybu."))
                return message.get("result")
            if "method" in message and "id" in message:
                self._reply_to_server_request(message)

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _send(self, payload: dict[str, Any]) -> None:
        process = self.process
        if not process or process.poll() is not None or not process.stdin:
            raise LanguageServiceError("Jazykový server už nebeží.")
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        try:
            process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
            process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            raise LanguageServiceError("Spojenie s jazykovým serverom sa prerušilo.") from error

    def _read_message(self, deadline: float) -> dict[str, Any] | None:
        marker = b"\r\n\r\n"
        while marker not in self._buffer:
            if not self._read_chunk(deadline):
                return None
        header, self._buffer = self._buffer.split(marker, 1)
        length = 0
        for line in header.decode("ascii", errors="replace").split("\r\n"):
            name, _, value = line.partition(":")
            if name.lower() == "content-length":
                try:
                    length = int(value.strip())
                except ValueError as error:
                    raise LanguageServiceError("Jazykový server poslal neplatnú odpoveď.") from error
        if length < 1 or length > 16 * 1024 * 1024:
            raise LanguageServiceError("Jazykový server poslal príliš veľkú odpoveď.")
        while len(self._buffer) < length:
            if not self._read_chunk(deadline):
                return None
        body, self._buffer = self._buffer[:length], self._buffer[length:]
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LanguageServiceError("Jazykový server poslal neplatné JSON dáta.") from error
        if not isinstance(value, dict):
            raise LanguageServiceError("Jazykový server poslal neplatnú odpoveď.")
        return value

    def _read_chunk(self, deadline: float) -> bool:
        process = self.process
        if not process or not process.stdout or process.poll() is not None:
            raise LanguageServiceError("Jazykový server sa neočakávane skončil.")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        readable, _, _ = select.select([process.stdout], [], [], remaining)
        if not readable:
            return False
        try:
            chunk = os.read(process.stdout.fileno(), 64 * 1024)
        except OSError as error:
            raise LanguageServiceError("Jazykový server sa neočakávane skončil.") from error
        if not chunk:
            raise LanguageServiceError("Jazykový server sa neočakávane skončil.")
        self._buffer += chunk
        return True

    def _reply_to_server_request(self, message: dict[str, Any]) -> None:
        method = str(message.get("method") or "")
        params = message.get("params")
        if method == "workspace/configuration" and isinstance(params, dict):
            result: Any = [{} for _ in params.get("items", [])]
        elif method == "workspace/workspaceFolders":
            result = [{"uri": self.root.resolve().as_uri(), "name": "projekt"}]
        else:
            result = None
        self._send({"jsonrpc": "2.0", "id": message["id"], "result": result})

    def _next_id(self) -> int:
        value = self._next_request_id
        self._next_request_id += 1
        return value

    def _relative_path_from_uri(self, value: Any) -> str:
        parsed = urlparse(str(value or ""))
        if parsed.scheme != "file":
            return ""
        try:
            path = Path(unquote(parsed.path)).resolve()
            return path.relative_to(self.root.resolve()).as_posix()
        except (OSError, ValueError):
            return ""

    def _locations(self, result: Any) -> list[dict[str, Any]]:
        entries = result if isinstance(result, list) else [result]
        locations: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            uri = entry.get("uri") or entry.get("targetUri")
            location_range = entry.get("range") or entry.get("targetSelectionRange") or entry.get("targetRange")
            if not isinstance(location_range, dict):
                continue
            start = location_range.get("start") if isinstance(location_range.get("start"), dict) else {}
            path = self._relative_path_from_uri(uri)
            if not path:
                continue
            locations.append(
                {
                    "path": path,
                    "line": int(start.get("line") or 0) + 1,
                    "column": int(start.get("character") or 0) + 1,
                }
            )
        return locations[:MAX_LSP_RESULT_LOCATIONS]

    @staticmethod
    def _range(value: Any) -> dict[str, int] | None:
        if not isinstance(value, dict):
            return None
        range_value = value.get("range") if isinstance(value.get("range"), dict) else value
        start = range_value.get("start") if isinstance(range_value.get("start"), dict) else {}
        end = range_value.get("end") if isinstance(range_value.get("end"), dict) else {}
        if not start or not end:
            return None
        return {
            "startLine": int(start.get("line") or 0) + 1,
            "startColumn": int(start.get("character") or 0) + 1,
            "endLine": int(end.get("line") or 0) + 1,
            "endColumn": int(end.get("character") or 0) + 1,
        }

    def _workspace_edits(self, result: Any) -> list[dict[str, Any]]:
        if not isinstance(result, dict):
            return []
        changes: list[tuple[Any, Any]] = []
        changed_files = result.get("changes")
        if isinstance(changed_files, dict):
            changes.extend(changed_files.items())
        document_changes = result.get("documentChanges")
        if isinstance(document_changes, list):
            for change in document_changes:
                if not isinstance(change, dict):
                    continue
                document = change.get("textDocument") if isinstance(change.get("textDocument"), dict) else {}
                changes.append((document.get("uri"), change.get("edits")))

        grouped: dict[str, list[dict[str, Any]]] = {}
        total_edits = 0
        for uri, edits in changes:
            path = self._relative_path_from_uri(uri)
            if not path or not isinstance(edits, list):
                continue
            target = grouped.setdefault(path, [])
            for edit in edits:
                if not isinstance(edit, dict):
                    continue
                range_value = self._range(edit.get("range"))
                if not range_value:
                    continue
                new_text = str(edit.get("newText") or "")
                if len(new_text.encode("utf-8", errors="replace")) > MAX_LSP_SOURCE_BYTES:
                    raise LanguageServiceError("Jazykový server navrhol príliš veľkú úpravu.")
                target.append({**range_value, "newText": new_text})
                total_edits += 1
                if total_edits > MAX_LSP_WORKSPACE_EDITS:
                    raise LanguageServiceError("Jazykový server navrhol príliš veľa úprav.")
        output = [
            {"path": path, "edits": edits}
            for path, edits in grouped.items()
            if edits
        ]
        if len(output) > MAX_LSP_WORKSPACE_EDIT_FILES:
            raise LanguageServiceError("Jazykový server navrhol úpravy v príliš veľa súboroch.")
        return output

    def _completion_items(self, result: Any) -> list[dict[str, Any]]:
        entries = result.get("items", []) if isinstance(result, dict) else result
        if not isinstance(entries, list):
            return []
        items: list[dict[str, Any]] = []
        for entry in entries[:300]:
            if not isinstance(entry, dict):
                continue
            label = str(entry.get("label") or "").strip()
            if not label:
                continue
            text_edit = entry.get("textEdit") if isinstance(entry.get("textEdit"), dict) else {}
            insert_text = text_edit.get("newText") or entry.get("insertText") or label
            detail = str(entry.get("detail") or "").replace("\n", " ").strip()
            documentation = entry.get("documentation")
            if isinstance(documentation, dict):
                documentation = documentation.get("value")
            items.append(
                {
                    "label": label,
                    "insertText": str(insert_text),
                    "snippet": int(entry.get("insertTextFormat") or 1) == 2,
                    "detail": detail[:500],
                    "documentation": str(documentation or "")[:2_000],
                    "kind": int(entry.get("kind") or 0),
                    "sortText": str(entry.get("sortText") or label),
                }
            )
        return items

    def _symbols(self, result: Any) -> list[dict[str, Any]]:
        entries = result if isinstance(result, list) else []
        symbols: list[dict[str, Any]] = []

        def append(entries_to_visit: list[Any]) -> None:
            for entry in entries_to_visit:
                if not isinstance(entry, dict):
                    continue
                selection = entry.get("selectionRange") or entry.get("range")
                start = selection.get("start") if isinstance(selection, dict) else {}
                symbols.append(
                    {
                        "name": str(entry.get("name") or ""),
                        "detail": str(entry.get("detail") or ""),
                        "kind": int(entry.get("kind") or 0),
                        "line": int(start.get("line") or 0) + 1,
                        "column": int(start.get("character") or 0) + 1,
                    }
                )
                children = entry.get("children")
                if isinstance(children, list):
                    append(children)

        append(entries)
        return [symbol for symbol in symbols if symbol["name"]][:500]


class LanguageService:
    """Keeps short-lived project-scoped language-server sessions."""

    def __init__(
        self,
        work_root: Path | None = None,
        *,
        server_commands: dict[str, list[str]] | None = None,
        max_sessions: int = MAX_LSP_SESSIONS,
        session_idle_seconds: float = LSP_SESSION_IDLE_SECONDS,
    ) -> None:
        self.work_root = (work_root or Path(tempfile.gettempdir()) / "poznamkovnik-lsp").resolve()
        self.server_commands = server_commands or {}
        self.max_sessions = max(1, int(max_sessions))
        self.session_idle_seconds = max(0.0, float(session_idle_seconds))
        self._sessions: dict[tuple[str, str, str], _LspSession] = {}
        self._lock = threading.Lock()

    def close(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.close(remove_workspace=True)

    def status(self) -> dict[str, dict[str, str | bool]]:
        values: dict[str, dict[str, str | bool]] = {}
        for language, (label, _, _) in LANGUAGE_SERVER_DEFINITIONS.items():
            command = self._command_for(language)
            values[language] = {
                "available": bool(command),
                "server": label,
                "message": f"Jazykový server {label} je pripravený."
                if command
                else f"Jazykový server {label} nie je nainštalovaný.",
            }
        return values

    def request(self, user_id: str, document: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        language = str(document.get("language") or "")
        operation = str(data.get("operation") or "")
        if operation not in SUPPORTED_OPERATIONS:
            raise LanguageServiceError("Neznáma operácia jazykového servera.")
        command = self._command_for(language)
        if not command:
            return {
                "available": False,
                "message": "Pre tento jazyk ešte nie je nainštalovaný jazykový server.",
                "items": [],
                "locations": [],
                "symbols": [],
            }
        source = _limited_source(data.get("source", document.get("source", "")))
        try:
            line = max(1, int(data.get("line") or 1))
            column = max(1, int(data.get("column") or 1))
        except (TypeError, ValueError) as error:
            raise LanguageServiceError("Pozícia v zdrojovom kóde nie je platná.") from error
        project_id = str(document.get("projectId") or "")
        if not project_id:
            raise LanguageServiceError("Projekt jazykového servera sa nenašiel.")
        new_name = str(data.get("newName") or "").strip()
        if operation == "rename" and (not new_name or len(new_name) > 200):
            raise LanguageServiceError("Nový názov pre jazykový server nie je platný.")
        key = (str(user_id), project_id, language)
        session, obsolete = self._session_for(key, command)
        for candidate in obsolete:
            candidate.close(remove_workspace=True)
        try:
            result = session.query(
                document.get("files") if isinstance(document.get("files"), list) else [],
                str(document.get("filename") or ""),
                source,
                operation,
                line,
                column,
                new_name,
            )
        except LanguageServiceError as error:
            self._discard_session(key, session)
            return {
                "available": True,
                "message": str(error),
                "items": [],
                "locations": [],
                "symbols": [],
                "workspaceEdits": [],
            }
        return {"available": True, "message": "", **result}

    def _session_for(self, key: tuple[str, str, str], command: list[str]) -> tuple[_LspSession, list[_LspSession]]:
        obsolete: list[_LspSession] = []
        now = time.monotonic()
        with self._lock:
            for session_key, candidate in list(self._sessions.items()):
                if now - candidate.last_used() >= self.session_idle_seconds:
                    obsolete.append(self._sessions.pop(session_key))
            session = self._sessions.get(key)
            if session is None:
                while len(self._sessions) >= self.max_sessions:
                    oldest_key = min(self._sessions, key=lambda item: self._sessions[item].last_used())
                    obsolete.append(self._sessions.pop(oldest_key))
                digest = hashlib.sha256("\x00".join(key).encode("utf-8")).hexdigest()[:32]
                root = self.work_root / digest
                session = _LspSession(command, root, key[2])
                self._sessions[key] = session
        return session, obsolete

    def _discard_session(self, key: tuple[str, str, str], session: _LspSession) -> None:
        with self._lock:
            if self._sessions.get(key) is session:
                self._sessions.pop(key)
        session.close(remove_workspace=True)

    def _command_for(self, language: str) -> list[str] | None:
        command = self.server_commands.get(language)
        return list(command) if command else _server_command(language)
