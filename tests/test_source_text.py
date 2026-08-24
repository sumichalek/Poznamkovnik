from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from reportlab.pdfgen.canvas import Canvas

from backend.auth import AuthService
from backend.database import Database
from backend.files import FileStore
from backend.source_text import SourceTextIndex


class SourceTextIndexTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="poznamkovnik-source-text-", dir="/tmp"))
        self.database = Database(self.root / "poznamkovnik.sqlite3")
        self.database.initialize()
        self.user, _ = AuthService(self.database).setup("Tester", "testovacie-heslo")
        self.files = FileStore(self.root / "files")
        self.index = SourceTextIndex(self.database, self.files)
        self.source = self.database.create_source(
            self.user["id"], {"id": "text-source", "title": "Textový zdroj", "kind": "book"}
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _add(self, file_id: str, name: str, content: bytes, mime_type: str) -> None:
        uploaded = self.files.store_upload(io.BytesIO(content), name, mime_type)
        self.database.add_source_file(self.user["id"], self.source["id"], file_id, uploaded)

    def test_text_docx_epub_and_pdf_are_indexed_with_locations(self) -> None:
        self._add("plain-file", "poznamky.txt", "Bezpečná práca s textom.".encode(), "text/plain")

        docx = io.BytesIO()
        with zipfile.ZipFile(docx, "w") as archive:
            archive.writestr(
                "word/document.xml",
                """<?xml version='1.0' encoding='UTF-8'?>
                <w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
                  <w:body><w:p><w:r><w:t>Dokument obsahuje ukážkovú kapitolu.</w:t></w:r></w:p></w:body>
                </w:document>""",
            )
        self._add("docx-file", "kapitola.docx", docx.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        epub = io.BytesIO()
        with zipfile.ZipFile(epub, "w") as archive:
            archive.writestr(
                "META-INF/container.xml",
                """<?xml version='1.0'?><container xmlns='urn:oasis:names:tc:opendocument:xmlns:container'>
                <rootfiles><rootfile full-path='OPS/book.opf'/></rootfiles></container>""",
            )
            archive.writestr(
                "OPS/book.opf",
                """<?xml version='1.0'?><package xmlns='http://www.idpf.org/2007/opf'>
                <manifest><item id='chapter' href='chapter.xhtml'/></manifest>
                <spine><itemref idref='chapter'/></spine></package>""",
            )
            archive.writestr("OPS/chapter.xhtml", "<html><body><h1>EPUB kapitola</h1><p>Hľadateľný odsek.</p></body></html>")
        self._add("epub-file", "kniha.epub", epub.getvalue(), "application/epub+zip")

        pdf = io.BytesIO()
        canvas = Canvas(pdf)
        canvas.drawString(72, 720, "PDF strana s overením textu")
        canvas.showPage()
        canvas.drawString(72, 720, "Druhá strana dokumentu")
        canvas.save()
        self._add("pdf-file", "dokument.pdf", pdf.getvalue(), "application/pdf")

        text_results = self.index.search_source(self.user["id"], self.source["id"], "bezpecna")
        self.assertEqual(text_results["results"][0]["fileId"], "plain-file")
        self.assertEqual(text_results["files"][0]["textIndexStatus"], "ready")

        docx_results = self.index.search_source(self.user["id"], self.source["id"], "ukazkovu")
        self.assertEqual(docx_results["results"][0]["fileId"], "docx-file")
        self.assertEqual(docx_results["results"][0]["locator"], "Dokument")

        epub_results = self.index.search_source(self.user["id"], self.source["id"], "hladatelny")
        self.assertEqual(epub_results["results"][0]["fileId"], "epub-file")
        self.assertEqual(epub_results["results"][0]["locator"], "Kapitola 1")

        pdf_results = self.index.search_source(self.user["id"], self.source["id"], "overenim")
        self.assertEqual(pdf_results["results"][0]["fileId"], "pdf-file")
        self.assertEqual(pdf_results["results"][0]["locator"], "Strana 1")

        reader = self.index.read_file(self.user["id"], self.source["id"], "epub-file")
        self.assertEqual(reader["textIndexStatus"], "ready")
        self.assertIn("EPUB kapitola", reader["content"])
        self.assertEqual(reader["locations"][0]["locator"], "Kapitola 1")

    def test_indexed_attachment_content_is_available_in_global_search(self) -> None:
        self._add("global-file", "manual.txt", "Jedinečné hľadateľné spojenie pre globálny katalóg.".encode(), "text/plain")
        self.index.index_all(self.user["id"])
        results = self.database.global_search(self.user["id"], "jedinecne hladatelne")
        self.assertTrue(any(item["type"] == "source_file" and item["id"] == "global-file" for item in results))
