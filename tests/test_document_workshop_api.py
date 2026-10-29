from __future__ import annotations

import http.client
import io
import json
import tempfile
import threading
import unittest
import zipfile
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from backend.api import AppContext, AppHandler


class QuietHandler(AppHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


class DocumentWorkshopApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-document-api-")
        self.addCleanup(temporary.cleanup)
        with patch("backend.api.AutomaticBackupScheduler.start"), patch(
            "backend.api.RadioRecordingScheduler.start"
        ), patch("backend.api.CalendarReminderScheduler.start"):
            self.context = AppContext(Path(__file__).resolve().parents[1], Path(temporary.name))
        self.addCleanup(self.context.development_debugger.close)
        self.addCleanup(self.context.serial_monitor.close)
        self.addCleanup(self.context.language_services.close)
        self.user, self.token = self.context.auth.setup("Document Tester", "document-test-password")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, context=self.context))
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02})
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.assertFalse(self.thread.is_alive())

    def request(
        self, method: str, path: str, data: dict | None = None
    ) -> tuple[int, dict]:
        body = json.dumps(data).encode() if data is not None else None
        status, _headers, response = self.raw_request(
            method, path, body, {"Content-Type": "application/json"}
        )
        return status, json.loads(response)

    def raw_request(
        self, method: str, path: str, body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=20)
        request_headers = {"Cookie": f"poznamkovnik_session={self.token}", **(headers or {})}
        try:
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def upload(self, path: str, filename: str, mime_type: str, content: bytes) -> tuple[int, dict]:
        boundary = "poznamkovnik-document-api-boundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        status, _headers, response = self.raw_request(
            "POST", path, body, {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )
        return status, json.loads(response)

    @staticmethod
    def epub() -> bytes:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr(
                "META-INF/container.xml",
                '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                '<rootfiles><rootfile full-path="OPS/book.opf" media-type="application/oebps-package+xml"/>'
                "</rootfiles></container>",
            )
            archive.writestr(
                "OPS/book.opf",
                '<package xmlns="http://www.idpf.org/2007/opf"><manifest>'
                '<item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>'
                '</manifest><spine><itemref idref="chapter"/></spine></package>',
            )
            archive.writestr(
                "OPS/chapter.xhtml",
                "<html><body><h1>Integracna kapitola</h1><p>Jedinecny hladany obsah EPUB.</p></body></html>",
            )
        return output.getvalue()

    def test_epub_build_reader_search_and_backup_restore_over_http(self) -> None:
        status, project = self.request("POST", "/api/documents", {"title": "HTTP EPUB projekt"})
        self.assertEqual(status, 200)
        project_id = project["project"]["id"]

        status, staged = self.upload(
            f"/api/documents/{project_id}/input-stages", "integracia.epub",
            "application/epub+zip", self.epub(),
        )
        self.assertEqual(status, 200, staged)
        stage = staged["stage"]
        self.assertEqual(stage["originalName"], "integracia.epub")
        status, detail = self.request(
            "POST", f"/api/documents/{project_id}/input-stages/{stage['id']}/confirm",
            {"pageIndices": list(range(stage["pageCount"]))},
        )
        self.assertEqual(status, 200, detail)

        ocr_calls: list[tuple[str, tuple[str, ...]]] = []

        def controlled_ocr(source: Path, mode: str, languages: object, **_kwargs: object) -> None:
            selected = tuple(languages) if isinstance(languages, list) else ()
            ocr_calls.append((mode, selected))

        with patch.object(self.context.documents, "apply_ocr", side_effect=controlled_ocr):
            status, built = self.request(
                "POST", f"/api/documents/{project_id}/build",
                {"title": "HTTP EPUB vystup", "ocrMode": "force", "ocrLanguages": ["slk", "eng"]},
            )
        self.assertEqual(status, 200, built)
        self.assertEqual(ocr_calls, [("force", ("slk", "eng"))])
        source = built["source"]
        file_id = source["files"][0]["id"]
        indexed_file = self.context.database.source_text_files(self.user["id"], source["id"])[0]
        self.assertEqual(indexed_file["textIndexStatus"], "ready")

        status, content = self.request(
            "GET", f"/api/sources/{source['id']}/files/{file_id}/content"
        )
        self.assertEqual(status, 200)
        self.assertIn("Jedinecny hladany obsah EPUB", content["content"]["content"])
        reader_state = {
            "locator": "Integracna kapitola", "scrollOffset": 420, "fontSize": "large",
            "textWidth": "narrow", "bookmarks": ["Integracna kapitola"],
        }
        status, saved = self.request(
            "PUT", f"/api/sources/{source['id']}/files/{file_id}/reader-state", reader_state
        )
        self.assertEqual((status, saved["state"]), (200, reader_state))
        status, search = self.request("GET", "/api/search?q=Jedinecny%20hladany")
        self.assertEqual(status, 200)
        self.assertTrue(any(item.get("targetId") == source["id"] for item in search["results"]))

        status, _headers, backup = self.raw_request("GET", "/api/backups/export")
        self.assertEqual(status, 200)
        self.assertTrue(backup.startswith(b"PK"))
        status, deleted = self.request("DELETE", f"/api/sources/{source['id']}")
        self.assertEqual((status, deleted), (200, {"deleted": True}))
        status, restored = self.upload(
            "/api/backups/restore", "integracna-zaloha.zip", "application/zip", backup
        )
        self.assertEqual(status, 200, restored)
        status, restored_source = self.request("GET", f"/api/sources/{source['id']}")
        self.assertEqual(status, 200, restored_source)
        status, restored_state = self.request(
            "GET", f"/api/sources/{source['id']}/files/{file_id}/reader-state"
        )
        self.assertEqual((status, restored_state["state"]), (200, reader_state))

    def test_deployment_health_is_public_and_checks_storage(self) -> None:
        self.token = ""
        status, result = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["version"], self.context.release["version"])
        self.assertNotIn("user", result)
        self.context.files.blobs_dir.rmdir()
        status, result = self.request("GET", "/api/health")
        self.assertEqual(status, 503)
        self.assertIn("error", result)
