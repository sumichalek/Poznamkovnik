from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from backend.auth import AuthService
from backend.database import Database
from backend.files import FileStore
from backend.source_tables import SourceTablePreview


class SourceTablePreviewTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="poznamkovnik-source-table-", dir="/tmp"))
        self.database = Database(self.root / "poznamkovnik.sqlite3")
        self.database.initialize()
        self.user, _ = AuthService(self.database).setup("Tester", "testovacie-heslo")
        self.files = FileStore(self.root / "files")
        self.preview = SourceTablePreview(self.database, self.files)
        self.source = self.database.create_source(
            self.user["id"], {"id": "table-source", "title": "Tabuľkový zdroj", "kind": "dataset"}
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _add(self, file_id: str, name: str, content: bytes, mime_type: str) -> None:
        uploaded = self.files.store_upload(io.BytesIO(content), name, mime_type)
        self.database.add_source_file(self.user["id"], self.source["id"], file_id, uploaded)

    def test_csv_preview_keeps_headers_filters_and_row_numbers(self) -> None:
        self._add("csv-file", "sústredenie.csv", "Deň;Minúty;Poznámka\nPondelok;45;Pokojná práca\nUtorok;20;Porada\n".encode(), "text/csv")

        table = self.preview.read_file(self.user["id"], self.source["id"], "csv-file", query="pokojná")

        self.assertEqual(table["status"], "ready")
        self.assertEqual(table["sheet"], "Obsah")
        self.assertEqual(table["headers"], ["Deň", "Minúty", "Poznámka"])
        self.assertEqual(table["rows"][0]["rowNumber"], 2)
        self.assertEqual(table["rows"][0]["values"][2], "Pokojná práca")
        self.assertEqual(table["totalRows"], 1)
        self.assertEqual(table["summary"]["rows"], 2)
        self.assertEqual(table["summary"]["numericColumns"][0]["name"], "Minúty")
        self.assertEqual(table["summary"]["numericColumns"][0]["average"], 32.5)

        filtered = self.preview.read_file(
            self.user["id"], self.source["id"], "csv-file", query="porada", query_column=2
        )
        self.assertEqual(filtered["queryColumn"], 2)
        self.assertEqual(filtered["rows"][0]["values"], ["Utorok", "20", "Porada"])

    def test_xlsx_preview_reads_sheet_and_shared_strings(self) -> None:
        xlsx = io.BytesIO()
        with zipfile.ZipFile(xlsx, "w") as archive:
            archive.writestr(
                "xl/workbook.xml",
                """<workbook xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
                xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'>
                <sheets><sheet name='Merania' sheetId='1' r:id='rId1'/></sheets></workbook>""",
            )
            archive.writestr(
                "xl/_rels/workbook.xml.rels",
                """<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>
                <Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet' Target='worksheets/sheet1.xml'/>
                </Relationships>""",
            )
            archive.writestr(
                "xl/sharedStrings.xml",
                """<sst xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'>
                <si><t>Teplota</t></si><si><t>Miesto</t></si><si><t>Bratislava</t></si></sst>""",
            )
            archive.writestr(
                "xl/worksheets/sheet1.xml",
                """<worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'><sheetData>
                <row r='1'><c r='A1' t='s'><v>0</v></c><c r='B1' t='s'><v>1</v></c></row>
                <row r='2'><c r='A2'><v>24.5</v></c><c r='B2' t='s'><v>2</v></c></row>
                </sheetData></worksheet>""",
            )
        self._add(
            "xlsx-file",
            "merania.xlsx",
            xlsx.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        table = self.preview.read_file(self.user["id"], self.source["id"], "xlsx-file")

        self.assertEqual(table["status"], "ready")
        self.assertEqual(table["sheets"], ["Merania"])
        self.assertEqual(table["headers"], ["Teplota", "Miesto"])
        self.assertEqual(table["rows"], [{"rowNumber": 2, "values": ["24.5", "Bratislava"]}])
        self.assertEqual(table["summary"]["numericColumns"][0]["min"], 24.5)

    def test_csv_preview_sorts_numeric_and_text_columns(self) -> None:
        self._add(
            "sorted-csv",
            "zoradenie.csv",
            "Názov;Hodnota\nZeta;10\nAlfa;2\nPrázdne;\nBeta;30\n".encode(),
            "text/csv",
        )

        numeric = self.preview.read_file(
            self.user["id"],
            self.source["id"],
            "sorted-csv",
            limit=2,
            sort_column=1,
            sort_direction="desc",
        )
        text = self.preview.read_file(
            self.user["id"],
            self.source["id"],
            "sorted-csv",
            sort_column=0,
            sort_direction="asc",
        )

        self.assertEqual([row["values"][1] for row in numeric["rows"]], ["30", "10", "2", ""])
        self.assertFalse(numeric["hasMore"])
        self.assertEqual(numeric["sortColumn"], 1)
        self.assertEqual(numeric["sortDirection"], "desc")
        self.assertEqual([row["values"][0] for row in text["rows"]], ["Alfa", "Beta", "Prázdne", "Zeta"])
