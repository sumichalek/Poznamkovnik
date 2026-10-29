from __future__ import annotations

import io
import shutil
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter
from PIL import Image

from backend.auth import AuthService
from backend.database import Database
from backend.document_workshop import DocumentWorkshop
from backend.files import FileStore


class DocumentWorkshopTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="poznamkovnik-workshop-", dir="/tmp"))
        self.database = Database(self.root / "poznamkovnik.sqlite3")
        self.database.initialize()
        self.user, _ = AuthService(self.database).setup("Tester", "testovacie-heslo")
        self.files = FileStore(self.root / "files")
        self.workshop = DocumentWorkshop(self.root / "documents", self.database, self.files)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _source_pdf(self) -> tuple[dict[str, object], list[str]]:
        writer = PdfWriter()
        for width in (200, 300, 400):
            writer.add_blank_page(width=width, height=500)
        data = io.BytesIO()
        writer.write(data)
        data.seek(0)
        uploaded = self.files.store_upload(data, "vstup.pdf", "application/pdf")
        source = self.database.create_source(
            self.user["id"],
            {"id": "input-source", "title": "Pôvodný dokument", "kind": "attachment"},
        )
        source = self.database.add_source_file(self.user["id"], source["id"], "input-file", uploaded)
        project = self.database.create_document_project(
            self.user["id"], {"id": "project-test", "title": "Výber strán"}
        )
        detail, _ = self.database.add_document_input(
            self.user["id"],
            project["project"]["id"],
            {
                "id": "input-test",
                "sourceId": source["id"],
                "sourceFileId": "input-file",
                "blobHash": uploaded["blobHash"],
                "originalBlobHash": uploaded["blobHash"],
                "originalName": uploaded["originalName"],
                "mimeType": uploaded["mimeType"],
                "sizeBytes": uploaded["sizeBytes"],
                "originalMimeType": uploaded["mimeType"],
                "originalSizeBytes": uploaded["sizeBytes"],
                "pageCount": 3,
            },
        )
        return source, [page["id"] for page in detail["pages"]]

    def _epub_upload(self) -> dict[str, object]:
        data = io.BytesIO()
        cover = io.BytesIO()
        Image.new("RGB", (80, 120), (48, 110, 92)).save(cover, format="PNG")
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr(
                "META-INF/container.xml",
                '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                '<rootfiles><rootfile full-path="OPS/book.opf" media-type="application/oebps-package+xml"/>'
                '</rootfiles></container>',
            )
            archive.writestr(
                "OPS/book.opf",
                '<package xmlns="http://www.idpf.org/2007/opf"><manifest>'
                '<item id="one" href="one.xhtml" media-type="application/xhtml+xml"/>'
                '<item id="two" href="two.xhtml" media-type="application/xhtml+xml"/>'
                '<item id="cover" href="cover.png" media-type="image/png"/>'
                '</manifest><spine><itemref idref="one"/><itemref idref="two"/></spine></package>',
            )
            archive.writestr("OPS/one.xhtml", "<html><body><h1>Prvá kapitola</h1><img src='cover.png'/><p>Text knihy.</p></body></html>")
            archive.writestr("OPS/two.xhtml", "<html><body><h1>Druhá kapitola</h1><p>Pokračovanie.</p></body></html>")
            archive.writestr("OPS/cover.png", cover.getvalue())
        data.seek(0)
        return self.files.store_upload(data, "kniha.epub", "application/epub+zip")

    def test_epub_is_typeset_as_pdf_and_original_is_retained_in_project(self) -> None:
        project = self.database.create_document_project(
            self.user["id"], {"id": "epub-project", "title": "Elektronická kniha"}
        )
        uploaded = self._epub_upload()
        self.assertTrue(self.workshop.supports(uploaded))
        self.assertTrue(self.workshop.requires_conversion(uploaded))
        stage = self.workshop.prepare_input(
            self.user["id"], project["project"]["id"], uploaded, 20 * 1024 * 1024
        )
        self.assertEqual(stage["originalName"], "kniha.epub")
        self.assertEqual(stage["mimeType"], "application/pdf")
        self.assertTrue(stage["converted"])
        detail = self.workshop.confirm_prepared_input(
            self.user["id"], project["project"]["id"], stage["id"], list(range(stage["pageCount"]))
        )
        self.assertEqual(detail["inputs"][0]["originalMimeType"], "application/epub+zip")
        converted = self.files.path_for_hash(detail["inputs"][0]["blobHash"])
        pages = PdfReader(str(converted)).pages
        text = "\n".join(page.extract_text() or "" for page in pages)
        self.assertIn("Prvá kapitola", text)
        self.assertIn("Druhá kapitola", text)
        self.assertTrue(any(page.images for page in pages))

    def test_ocr_status_is_explicit_even_when_optional_tools_are_missing(self) -> None:
        status = self.workshop.ocr_status()
        self.assertIsInstance(status["available"], bool)
        self.assertIsInstance(status["languages"], list)
        self.assertTrue(status["message"])

    def test_reader_state_is_stored_per_user_and_attachment(self) -> None:
        source, _ = self._source_pdf()
        saved = self.database.save_source_reader_state(
            self.user["id"], source["id"], "input-file",
            {"locator": "Kapitola 2", "scrollOffset": 810, "fontSize": "large",
             "textWidth": "narrow", "bookmarks": ["Kapitola 1", "Kapitola 2"]},
        )
        self.assertEqual(saved["locator"], "Kapitola 2")
        self.assertEqual(saved["scrollOffset"], 810)
        self.assertEqual(saved["fontSize"], "large")
        self.assertEqual(saved["textWidth"], "narrow")
        self.assertEqual(saved["bookmarks"], ["Kapitola 1", "Kapitola 2"])

        snapshot = self.database.backup_snapshot(self.user["id"])
        self.assertEqual(snapshot["sourceReaderStates"][0]["source_file_id"], "input-file")
        self.database.restore_backup_snapshot(self.user["id"], snapshot)
        restored = self.database.source_reader_state(self.user["id"], source["id"], "input-file")
        self.assertEqual(restored, saved)

    def test_built_source_is_immediately_sent_to_text_index(self) -> None:
        self._source_pdf()
        indexed: list[tuple[str, str]] = []
        self.workshop.source_indexer = lambda user_id, source: indexed.append((user_id, source["id"]))
        output = self.workshop.build_source(
            self.user["id"], "project-test", {"title": "Indexovaný výstup", "ocrMode": "off"}
        )
        self.assertEqual(indexed, [(self.user["id"], output["id"])])

    def test_background_build_job_reports_completion(self) -> None:
        self._source_pdf()
        job = self.workshop.start_build_job(
            self.user["id"], "project-test", {"title": "Výstup úlohy", "ocrMode": "off"}
        )
        deadline = time.monotonic() + 5
        while job["status"] not in {"completed", "failed", "cancelled"} and time.monotonic() < deadline:
            time.sleep(0.02)
            job = self.workshop.build_job(self.user["id"], "project-test", job["id"])
        self.assertEqual(job["status"], "completed", job)
        self.assertEqual(job["source"]["title"], "Výstup úlohy")

    def test_background_build_job_can_be_cancelled(self) -> None:
        project = self.database.create_document_project(
            self.user["id"], {"id": "cancel-project", "title": "Zrušenie"}
        )

        def wait_for_cancel(user_id: str, project_id: str, settings: dict[str, object]) -> dict[str, object]:
            event = settings["_cancelEvent"]
            self.assertTrue(event.wait(2))
            raise ValueError("cancelled")

        with patch.object(self.workshop, "build_source", side_effect=wait_for_cancel):
            job = self.workshop.start_build_job(self.user["id"], project["project"]["id"], {})
            self.workshop.cancel_build_job(self.user["id"], project["project"]["id"], job["id"])
            deadline = time.monotonic() + 3
            while job["status"] not in {"completed", "failed", "cancelled"} and time.monotonic() < deadline:
                time.sleep(0.02)
                job = self.workshop.build_job(self.user["id"], project["project"]["id"], job["id"])
        self.assertEqual(job["status"], "cancelled")

    def test_selected_pages_preserve_project_order_and_create_source_link(self) -> None:
        source, page_ids = self._source_pdf()
        detail, _ = self.database.update_document_project(
            self.user["id"],
            "project-test",
            {
                "outputPageSize": "keep",
                "imageDpi": 144,
                "pageNumberPosition": "bottom-center",
                "pageNumberStart": 42,
            },
        )
        self.assertEqual(detail["project"]["pageNumberPosition"], "bottom-center")
        output_source = self.workshop.build_source(
            self.user["id"],
            "project-test",
            {"title": "Vybraný výstup", "pageIds": [page_ids[2], page_ids[0]]},
        )
        metadata = output_source["metadata"]["documentWorkshop"]
        self.assertEqual(metadata["pageCount"], 2)
        self.assertEqual(metadata["selectedPageCount"], 2)
        self.assertEqual(metadata["inputCount"], 1)
        with self.database.connect() as connection:
            blob_hash = connection.execute(
                "SELECT blob_hash FROM source_files WHERE source_id = ?", (output_source["id"],)
            ).fetchone()["blob_hash"]
        result = PdfReader(str(self.files.path_for_hash(blob_hash)))
        self.assertEqual(len(result.pages), 2)
        self.assertEqual([round(float(page.mediabox.width)) for page in result.pages], [200, 400])
        self.assertEqual([page.extract_text().strip() for page in result.pages], ["42", "43"])
        links = self.database.semantic_links_for_target(self.user["id"], "source", output_source["id"])
        self.assertEqual([item["targetId"] for item in links], [source["id"]])
        unchanged = self.database.document_project_detail(self.user["id"], "project-test")
        self.assertEqual(len(unchanged["pages"]), 3)

    def test_output_settings_can_be_undone(self) -> None:
        self._source_pdf()
        self.database.update_document_project(
            self.user["id"],
            "project-test",
            {
                "outputPageSize": "a4-portrait",
                "imageDpi": 300,
                "pageNumberPosition": "bottom-right",
                "pageNumberStart": 7,
            },
        )
        restored = self.database.restore_document_project_history(self.user["id"], "project-test", "undo")
        self.assertEqual(restored["project"]["outputPageSize"], "keep")
        self.assertEqual(restored["project"]["imageDpi"], 144)
        self.assertEqual(restored["project"]["pageNumberPosition"], "none")
        self.assertEqual(restored["project"]["pageNumberStart"], 1)

    def test_project_transfer_restores_files_and_page_edits_without_source_links(self) -> None:
        _, page_ids = self._source_pdf()
        self.database.update_document_project(
            self.user["id"],
            "project-test",
            {
                "outputPageSize": "a4-landscape",
                "imageDpi": 200,
                "pageNumberPosition": "bottom-right",
                "pageNumberStart": 8,
            },
        )
        self.database.update_document_page(
            self.user["id"],
            "project-test",
            page_ids[1],
            {"rotation": 90, "cropTop": 6, "cropRight": 4, "cropBottom": 2, "cropLeft": 3},
        )
        self.database.reorder_document_pages(
            self.user["id"],
            "project-test",
            {"pageIds": [page_ids[2], page_ids[0], page_ids[1]]},
        )

        archive, filename = self.workshop.export_project(self.user["id"], "project-test")
        try:
            self.assertTrue(filename.endswith("-dielna-pdf.zip"))
            with zipfile.ZipFile(archive) as packaged:
                manifest = packaged.read("manifest.json").decode("utf-8")
                self.assertIn('"format":"poznamkovnik-document-project"', manifest)
                self.assertNotIn("input-source", manifest)
            with archive.open("rb") as stream:
                imported = self.workshop.import_project(self.user["id"], stream, filename)
        finally:
            archive.unlink(missing_ok=True)

        self.assertEqual(imported["project"]["title"], "Výber strán")
        self.assertEqual(imported["project"]["outputPageSize"], "a4-landscape")
        self.assertEqual(imported["project"]["imageDpi"], 200)
        self.assertEqual(imported["project"]["pageNumberPosition"], "bottom-right")
        self.assertEqual(imported["project"]["pageNumberStart"], 8)
        self.assertEqual([page["inputPageIndex"] for page in imported["pages"]], [2, 0, 1])
        self.assertEqual(imported["pages"][2]["rotation"], 90)
        self.assertEqual(
            [
                imported["pages"][2]["cropTop"],
                imported["pages"][2]["cropRight"],
                imported["pages"][2]["cropBottom"],
                imported["pages"][2]["cropLeft"],
            ],
            [6, 4, 2, 3],
        )
        self.assertEqual(imported["inputs"][0]["sourceId"], "")
        self.assertEqual(imported["inputs"][0]["sourceFileId"], "")
        self.assertFalse(imported["history"]["canUndo"])
