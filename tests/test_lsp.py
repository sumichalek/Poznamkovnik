from __future__ import annotations

import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from backend.lsp import LANGUAGE_SERVER_DEFINITIONS, LanguageService


FAKE_LANGUAGE_SERVER = r'''
import json
import sys


def receive():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line == b"\r\n":
            break
        name, value = line.decode("ascii").split(":", 1)
        headers[name.lower()] = value.strip()
    return json.loads(sys.stdin.buffer.read(int(headers["content-length"])).decode("utf-8"))


def reply(message_id, result):
    body = json.dumps({"jsonrpc": "2.0", "id": message_id, "result": result}).encode("utf-8")
    sys.stdout.buffer.write(b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body)
    sys.stdout.buffer.flush()


while True:
    message = receive()
    if message is None:
        break
    method = message.get("method")
    message_id = message.get("id")
    if method == "exit":
        break
    if message_id is None:
        continue
    if method == "initialize":
        reply(message_id, {"capabilities": {}})
    elif method == "textDocument/completion":
        reply(message_id, {"items": [{"label": "greet", "insertText": "greet(${1:name})", "insertTextFormat": 2, "kind": 3}]})
    elif method == "textDocument/definition":
        uri = message["params"]["textDocument"]["uri"]
        reply(message_id, {"uri": uri, "range": {"start": {"line": 1, "character": 4}, "end": {"line": 1, "character": 9}}})
    elif method == "textDocument/references":
        uri = message["params"]["textDocument"]["uri"]
        reply(message_id, [{"uri": uri, "range": {"start": {"line": 1, "character": 4}, "end": {"line": 1, "character": 9}}}])
    elif method == "textDocument/documentSymbol":
        reply(message_id, [{"name": "greet", "detail": "void greet(void)", "kind": 12, "selectionRange": {"start": {"line": 1, "character": 4}, "end": {"line": 1, "character": 9}}}])
    elif method == "textDocument/prepareRename":
        reply(message_id, {"start": {"line": 1, "character": 5}, "end": {"line": 1, "character": 10}})
    elif method == "textDocument/rename":
        uri = message["params"]["textDocument"]["uri"]
        reply(message_id, {"changes": {uri: [{"range": {"start": {"line": 1, "character": 5}, "end": {"line": 1, "character": 10}}, "newText": message["params"]["newName"]}]}})
    else:
        reply(message_id, None)
'''


class LanguageServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="poznamkovnik-lsp-test-", dir="/tmp"))
        self.server_path = self.root / "fake_language_server.py"
        self.server_path.write_text(textwrap.dedent(FAKE_LANGUAGE_SERVER), encoding="utf-8")
        self.service = LanguageService(
            self.root / "workspace",
            server_commands={"c": [sys.executable, str(self.server_path)]},
        )
        self.document = {
            "projectId": "project-c",
            "language": "c",
            "filename": "src/main.c",
            "source": "#include \"helper.h\"\nvoid greet(void) {}\n",
            "files": [
                {"title": "src/main.c", "content": "#include \"helper.h\"\nvoid greet(void) {}\n"},
                {"title": "include/helper.h", "content": "void greet(void);\n"},
            ],
        }

    def tearDown(self) -> None:
        self.service.close()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_completion_definition_references_and_symbols_use_json_rpc(self) -> None:
        completion = self.service.request("tester", self.document, {
            "operation": "completion", "source": self.document["source"], "line": 2, "column": 7,
        })
        self.assertTrue(completion["available"])
        self.assertEqual(completion["items"][0]["label"], "greet")
        self.assertTrue(completion["items"][0]["snippet"])

        definition = self.service.request("tester", self.document, {
            "operation": "definition", "source": self.document["source"], "line": 2, "column": 7,
        })
        self.assertEqual(definition["locations"], [{"path": "src/main.c", "line": 2, "column": 5}])

        references = self.service.request("tester", self.document, {
            "operation": "references", "source": self.document["source"], "line": 2, "column": 7,
        })
        self.assertEqual(references["locations"], [{"path": "src/main.c", "line": 2, "column": 5}])

        symbols = self.service.request("tester", self.document, {
            "operation": "symbols", "source": self.document["source"], "line": 1, "column": 1,
        })
        self.assertEqual(symbols["symbols"][0]["name"], "greet")

        prepared = self.service.request("tester", self.document, {
            "operation": "prepareRename", "source": self.document["source"], "line": 2, "column": 7,
        })
        self.assertEqual(prepared["range"], {"startLine": 2, "startColumn": 6, "endLine": 2, "endColumn": 11})

        renamed = self.service.request("tester", self.document, {
            "operation": "rename", "source": self.document["source"], "line": 2, "column": 7, "newName": "welcome",
        })
        self.assertEqual(renamed["workspaceEdits"], [{
            "path": "src/main.c",
            "edits": [{"startLine": 2, "startColumn": 6, "endLine": 2, "endColumn": 11, "newText": "welcome"}],
        }])

    def test_unsupported_language_returns_a_quiet_fallback(self) -> None:
        document = {**self.document, "language": "asm"}
        result = self.service.request("tester", document, {"operation": "completion", "line": 1, "column": 1})
        self.assertFalse(result["available"])
        self.assertEqual(result["items"], [])

    def test_session_limit_discards_the_old_process_and_workspace(self) -> None:
        self.service.close()
        self.service = LanguageService(
            self.root / "workspace",
            server_commands={"c": [sys.executable, str(self.server_path)]},
            max_sessions=1,
            session_idle_seconds=60,
        )
        self.service.request("tester", self.document, {
            "operation": "symbols", "source": self.document["source"], "line": 1, "column": 1,
        })
        first_session = next(iter(self.service._sessions.values()))
        self.assertTrue(first_session.root.exists())

        second_document = {**self.document, "projectId": "another-project"}
        self.service.request("tester", second_document, {
            "operation": "symbols", "source": second_document["source"], "line": 1, "column": 1,
        })

        self.assertEqual(len(self.service._sessions), 1)
        self.assertFalse(first_session.root.exists())
        self.assertTrue(next(iter(self.service._sessions.values())).root.exists())

    def test_status_exposes_go_and_rust_only_with_their_server_commands(self) -> None:
        self.service.close()
        self.service = LanguageService(
            self.root / "workspace",
            server_commands={
                "go": [sys.executable, str(self.server_path)],
                "rust": [sys.executable, str(self.server_path)],
            },
        )
        status = self.service.status()
        self.assertTrue(status["go"]["available"])
        self.assertEqual(status["go"]["server"], "gopls")
        self.assertTrue(status["rust"]["available"])
        self.assertEqual(status["rust"]["server"], "rust-analyzer")

    def test_registered_language_servers_are_visible_and_javascript_uses_the_bridge(self) -> None:
        self.service.close()
        self.service = LanguageService(
            self.root / "workspace",
            server_commands={"javascript": [sys.executable, str(self.server_path)]},
        )
        status = self.service.status()
        self.assertEqual(set(status), set(LANGUAGE_SERVER_DEFINITIONS))
        self.assertTrue(status["javascript"]["available"])
        self.assertEqual(status["javascript"]["server"], "TypeScript Language Server")

        document = {
            "projectId": "project-js",
            "language": "javascript",
            "filename": "main.js",
            "source": "function greet() {}\n",
            "files": [{"title": "main.js", "content": "function greet() {}\n"}],
        }
        result = self.service.request("tester", document, {
            "operation": "completion", "source": document["source"], "line": 1, "column": 10,
        })
        self.assertTrue(result["available"])
        self.assertEqual(result["items"][0]["label"], "greet")


if __name__ == "__main__":
    unittest.main()
