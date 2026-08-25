from __future__ import annotations

import csv
import io
import math
import posixpath
import re
import zipfile
from pathlib import Path
from typing import Any, Iterable, Iterator
from xml.etree import ElementTree

from .database import Database
from .files import FileStore


MAX_TABLE_FILE_BYTES = 32 * 1024 * 1024
MAX_TABLE_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_TABLE_ROWS = 50_000
MAX_TABLE_COLUMNS = 120
MAX_CELL_CHARACTERS = 5_000
DEFAULT_TABLE_PAGE_SIZE = 160
MAX_TABLE_PAGE_SIZE = 400


class SourceTablePreview:
    """Returns safe, bounded pages from CSV and XLSX source attachments."""

    def __init__(self, database: Database, files: FileStore) -> None:
        self.database = database
        self.files = files

    def read_file(
        self,
        user_id: str,
        source_id: str,
        file_id: str,
        *,
        sheet: str = "",
        offset: int = 0,
        limit: int = DEFAULT_TABLE_PAGE_SIZE,
        query: str = "",
        query_column: int = -1,
        sort_column: int = -1,
        sort_direction: str = "asc",
    ) -> dict[str, Any]:
        file = next(
            (entry for entry in self.database.source_text_files(user_id, source_id) if entry["id"] == file_id),
            None,
        )
        if not file:
            raise KeyError("Príloha neexistuje.")
        response = {
            "fileId": file_id,
            "fileName": file["originalName"],
            "sheets": [],
            "sheet": "",
            "headers": [],
            "rows": [],
            "offset": 0,
            "limit": self._limit(limit),
            "totalRows": 0,
            "hasMore": False,
            "truncated": False,
            "status": "unsupported",
            "error": "Pre tento formát zatiaľ nemáme tabuľkový náhľad.",
        }
        path = self.files.path_for_hash(str(file["blobHash"]))
        if not path.is_file():
            response.update(status="missing", error="Súbor prílohy sa nenašiel.")
            return response
        if path.stat().st_size > MAX_TABLE_FILE_BYTES:
            response.update(status="too_large", error="Súbor je na vstavaný náhľad tabuľky príliš veľký.")
            return response

        suffix = Path(str(file["originalName"])).suffix.lower()
        try:
            if suffix in {".csv", ".tsv"} or str(file["mimeType"]).lower() in {"text/csv", "text/tab-separated-values"}:
                page = self._read_csv(
                    path,
                    suffix=suffix,
                    offset=offset,
                    limit=limit,
                    query=query,
                    query_column=query_column,
                    sort_column=sort_column,
                    sort_direction=sort_direction,
                )
            elif suffix == ".xlsx" or str(file["mimeType"]).lower().endswith("spreadsheetml.sheet"):
                page = self._read_xlsx(
                    path,
                    sheet=sheet,
                    offset=offset,
                    limit=limit,
                    query=query,
                    query_column=query_column,
                    sort_column=sort_column,
                    sort_direction=sort_direction,
                )
            else:
                return response
        except TablePreviewError as error:
            response.update(status="unsupported", error=str(error))
            return response
        except (OSError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as error:
            response.update(status="failed", error=f"Tabuľku sa nepodarilo načítať: {error}")
            return response
        return {**response, **page, "status": "ready", "error": ""}

    def _read_csv(
        self,
        path: Path,
        *,
        suffix: str,
        offset: int,
        limit: int,
        query: str,
        query_column: int,
        sort_column: int,
        sort_direction: str,
    ) -> dict[str, Any]:
        raw = path.read_bytes()
        text = self._decode_text(raw)
        sample = text[:32_000]
        delimiter = "\t" if suffix == ".tsv" else ","
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel_tab if delimiter == "\t" else csv.excel
        rows = ((number, row) for number, row in enumerate(csv.reader(io.StringIO(text), dialect), start=1))
        return {
            "sheets": ["Obsah"],
            "sheet": "Obsah",
            **self._page_rows(
                rows,
                offset=offset,
                limit=limit,
                query=query,
                query_column=query_column,
                sort_column=sort_column,
                sort_direction=sort_direction,
            ),
        }

    def _read_xlsx(
        self,
        path: Path,
        *,
        sheet: str,
        offset: int,
        limit: int,
        query: str,
        query_column: int,
        sort_column: int,
        sort_direction: str,
    ) -> dict[str, Any]:
        with zipfile.ZipFile(path) as archive:
            self._validate_archive(archive)
            sheets = self._xlsx_sheets(archive)
            if not sheets:
                raise TablePreviewError("XLSX neobsahuje žiadny čitateľný hárok.")
            selected_name = sheet if any(name == sheet for name, _ in sheets) else sheets[0][0]
            selected_path = next(entry for name, entry in sheets if name == selected_name)
            shared_strings = self._xlsx_shared_strings(archive)
            rows = self._xlsx_rows(archive, selected_path, shared_strings)
            return {
                "sheets": [name for name, _ in sheets],
                "sheet": selected_name,
                **self._page_rows(
                    rows,
                    offset=offset,
                    limit=limit,
                    query=query,
                    query_column=query_column,
                    sort_column=sort_column,
                    sort_direction=sort_direction,
                ),
            }

    def _page_rows(
        self,
        rows: Iterable[tuple[int, list[str]]],
        *,
        offset: int,
        limit: int,
        query: str,
        query_column: int,
        sort_column: int,
        sort_direction: str,
    ) -> dict[str, Any]:
        safe_offset = max(0, int(offset))
        safe_limit = self._limit(limit)
        query_text = self._normalise_search(query)
        headers: list[str] = []
        matched: list[dict[str, Any]] = []
        matched_rows = 0
        scanned_rows = 0
        filled_cells = 0
        numeric_columns: list[dict[str, Any]] = []
        truncated = False
        header_found = False
        column_count = 0
        safe_query_column = -1

        for row_number, raw_values in rows:
            values = [self._safe_cell(value) for value in raw_values[:MAX_TABLE_COLUMNS]]
            if not header_found:
                if not any(values):
                    continue
                headers = values
                column_count = len(headers)
                safe_query_column = query_column if 0 <= query_column < column_count else -1
                numeric_columns = [self._new_numeric_summary() for _ in range(column_count)]
                header_found = True
                continue

            scanned_rows += 1
            if scanned_rows > MAX_TABLE_ROWS:
                truncated = True
                break
            column_count = max(column_count, len(values))
            while len(numeric_columns) < column_count:
                numeric_columns.append(self._new_numeric_summary())
            values = values + [""] * (column_count - len(values))
            for index, value in enumerate(values):
                if not value:
                    continue
                filled_cells += 1
                number = self._number_value(value)
                if number is None:
                    continue
                column = numeric_columns[index]
                column["count"] += 1
                column["sum"] += number
                column["min"] = number if column["min"] is None else min(column["min"], number)
                column["max"] = number if column["max"] is None else max(column["max"], number)
            searchable = values[safe_query_column] if safe_query_column >= 0 else " ".join(values)
            if query_text and query_text not in self._normalise_search(searchable):
                continue
            matched.append({"rowNumber": row_number, "values": values})
            matched_rows += 1

        if not header_found:
            return {
                "headers": [],
                "rows": [],
                "offset": safe_offset,
                "limit": safe_limit,
                "totalRows": 0,
                "hasMore": False,
                "truncated": False,
                "queryColumn": -1,
                "sortColumn": -1,
                "sortDirection": "",
                "summary": self._empty_summary(),
            }
        headers = self._complete_headers(headers, column_count)
        for row in matched:
            row["values"] = row["values"] + [""] * (column_count - len(row["values"]))
        safe_sort_column = sort_column if 0 <= sort_column < column_count else -1
        safe_sort_direction = "desc" if str(sort_direction).lower() == "desc" else "asc"
        ordered = (
            self._sort_rows(matched, safe_sort_column, safe_sort_direction)
            if safe_sort_column >= 0
            else matched
        )
        selected = ordered[safe_offset:safe_offset + safe_limit]
        return {
            "headers": headers,
            "rows": selected,
            "offset": safe_offset,
            "limit": safe_limit,
            "totalRows": matched_rows,
            "hasMore": truncated or safe_offset + len(selected) < len(ordered),
            "truncated": truncated,
            "queryColumn": safe_query_column,
            "sortColumn": safe_sort_column,
            "sortDirection": safe_sort_direction if safe_sort_column >= 0 else "",
            "summary": self._table_summary(headers, numeric_columns, scanned_rows, filled_cells, truncated),
        }

    def _sort_rows(
        self,
        rows: list[dict[str, Any]],
        column: int,
        direction: str,
    ) -> list[dict[str, Any]]:
        def value(row: dict[str, Any]) -> str:
            return str(row["values"][column] or "").strip()

        present = [row for row in rows if value(row)]
        empty = [row for row in rows if not value(row)]
        numeric = bool(present) and all(self._number_value(value(row)) is not None for row in present)
        if numeric:
            key = lambda row: self._number_value(value(row))
        else:
            key = lambda row: self._normalise_search(value(row))
        return sorted(present, key=key, reverse=direction == "desc") + empty

    @staticmethod
    def _new_numeric_summary() -> dict[str, Any]:
        return {"count": 0, "sum": 0.0, "min": None, "max": None}

    @staticmethod
    def _empty_summary() -> dict[str, Any]:
        return {"rows": 0, "filledCells": 0, "emptyCells": 0, "numericColumns": [], "limited": False}

    @staticmethod
    def _table_summary(
        headers: list[str],
        columns: list[dict[str, Any]],
        rows: int,
        filled_cells: int,
        limited: bool,
    ) -> dict[str, Any]:
        numeric = []
        for index, column in enumerate(columns):
            if not column["count"]:
                continue
            numeric.append({
                "name": headers[index] if index < len(headers) else f"Stĺpec {index + 1}",
                "count": column["count"],
                "min": column["min"],
                "max": column["max"],
                "average": column["sum"] / column["count"],
            })
        return {
            "rows": rows,
            "filledCells": filled_cells,
            "emptyCells": max(0, rows * len(headers) - filled_cells),
            "numericColumns": numeric,
            "limited": limited,
        }

    def _xlsx_sheets(self, archive: zipfile.ZipFile) -> list[tuple[str, str]]:
        workbook_path = "xl/workbook.xml"
        try:
            workbook = ElementTree.fromstring(archive.read(workbook_path))
            relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        except KeyError as error:
            raise TablePreviewError("XLSX nemá čitateľnú štruktúru zošitov.") from error
        targets = {
            relation.get("Id", ""): relation.get("Target", "")
            for relation in relationships.findall("{*}Relationship")
        }
        sheets: list[tuple[str, str]] = []
        for number, element in enumerate(workbook.findall(".//{*}sheets/{*}sheet"), start=1):
            relationship_id = next((value for key, value in element.attrib.items() if key.endswith("}id") or key == "r:id"), "")
            target = targets.get(relationship_id, "")
            if not target:
                continue
            path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
            if not path.startswith("xl/"):
                continue
            sheets.append((element.get("name") or f"Hárok {number}", path))
        return sheets

    def _xlsx_shared_strings(self, archive: zipfile.ZipFile) -> list[str]:
        if "xl/sharedStrings.xml" not in archive.namelist():
            return []
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        strings: list[str] = []
        for item in root.findall("{*}si"):
            strings.append(
                self._safe_cell("".join(node.text or "" for node in item.iter() if self._local_name(node.tag) == "t"))
            )
        return strings

    def _xlsx_rows(
        self,
        archive: zipfile.ZipFile,
        sheet_path: str,
        shared_strings: list[str],
    ) -> Iterator[tuple[int, list[str]]]:
        try:
            stream = archive.open(sheet_path)
        except KeyError as error:
            raise TablePreviewError("Vybraný hárok sa v XLSX nenašiel.") from error
        with stream:
            generated_number = 0
            for _, row in ElementTree.iterparse(stream, events=("end",)):
                if self._local_name(row.tag) != "row":
                    continue
                generated_number += 1
                row_number = int(row.get("r", generated_number) or generated_number)
                values: dict[int, str] = {}
                for cell in row.findall("{*}c"):
                    index = self._xlsx_column_index(cell.get("r", ""))
                    if index is None or index >= MAX_TABLE_COLUMNS:
                        continue
                    values[index] = self._xlsx_cell_value(cell, shared_strings)
                row.clear()
                if values:
                    width = min(MAX_TABLE_COLUMNS, max(values) + 1)
                    yield row_number, [values.get(index, "") for index in range(width)]
                else:
                    yield row_number, []

    @staticmethod
    def _xlsx_cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
        kind = cell.get("t", "")
        if kind == "inlineStr":
            return SourceTablePreview._safe_cell(
                "".join(node.text or "" for node in cell.iter() if SourceTablePreview._local_name(node.tag) == "t")
            )
        value = next((child.text or "" for child in cell if SourceTablePreview._local_name(child.tag) == "v"), "")
        if kind == "s":
            try:
                return shared_strings[int(value)]
            except (IndexError, ValueError):
                return ""
        if kind == "b":
            return "Áno" if value == "1" else "Nie"
        return SourceTablePreview._safe_cell(value)

    @staticmethod
    def _xlsx_column_index(reference: str) -> int | None:
        letters = re.match(r"([A-Za-z]+)", reference or "")
        if not letters:
            return None
        value = 0
        for character in letters.group(1).upper():
            value = value * 26 + ord(character) - ord("A") + 1
        return value - 1

    @staticmethod
    def _complete_headers(headers: list[str], column_count: int) -> list[str]:
        result = headers[:]
        for index in range(column_count):
            if index >= len(result):
                result.append("")
            if not result[index]:
                result[index] = f"Stĺpec {index + 1}"
        return result

    @staticmethod
    def _safe_cell(value: Any) -> str:
        return str(value or "").replace("\x00", " ").strip()[:MAX_CELL_CHARACTERS]

    @staticmethod
    def _normalise_search(value: str) -> str:
        return " ".join(str(value or "").casefold().split())

    @staticmethod
    def _number_value(value: str) -> float | None:
        text = str(value or "").strip().replace("\u00a0", "").replace(" ", "")
        if not text:
            return None
        if "," in text and "." in text:
            if text.rfind(",") > text.rfind("."):
                text = text.replace(".", "").replace(",", ".")
            else:
                text = text.replace(",", "")
        elif "," in text:
            text = text.replace(",", ".")
        try:
            number = float(text)
        except ValueError:
            return None
        return number if math.isfinite(number) else None

    @staticmethod
    def _decode_text(data: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-16", "cp1250", "latin-1"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    @staticmethod
    def _validate_archive(archive: zipfile.ZipFile) -> None:
        if sum(entry.file_size for entry in archive.infolist()) > MAX_TABLE_ARCHIVE_BYTES:
            raise TablePreviewError("XLSX je na vstavaný náhľad príliš veľký.")

    @staticmethod
    def _limit(value: int) -> int:
        return min(MAX_TABLE_PAGE_SIZE, max(20, int(value)))

    @staticmethod
    def _local_name(value: str) -> str:
        return value.rsplit("}", 1)[-1]


class TablePreviewError(ValueError):
    pass
