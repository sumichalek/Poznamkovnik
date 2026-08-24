from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter

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
