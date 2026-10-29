from __future__ import annotations

import html
import posixpath
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from pypdf import PdfReader

from .database import Database
from .files import FileStore


MAX_INDEXED_FILE_BYTES = 32 * 1024 * 1024
MAX_INDEXED_TEXT_CHARACTERS = 3_000_000
MAX_ARCHIVE_UNPACKED_BYTES = 64 * 1024 * 1024
MAX_EPUB_DOCUMENTS = 160


class _HtmlTextParser(HTMLParser):
    """Small dependency-free HTML to text reader for EPUB and HTML attachments."""

    _BREAK_TAGS = {"address", "article", "blockquote", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "p", "section", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.heading_parts: list[str] = []
        self._heading_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"h1", "h2", "h3", "title"}:
            self._heading_depth += 1
        if tag.lower() in self._BREAK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"h1", "h2", "h3", "title"} and self._heading_depth:
            self._heading_depth -= 1
        if tag.lower() in self._BREAK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)
        if self._heading_depth and not self.heading_parts:
            self.heading_parts.append(data)

    def text(self) -> str:
        return _normalise_text("".join(self.parts))

    def heading(self) -> str:
        return _normalise_text("".join(self.heading_parts))[:300]


def _normalise_text(value: str) -> str:
    value = html.unescape(value or "")
    value = value.replace("\x00", " ")
    value = re.sub(r"[\t\f\v ]+", " ", value)
    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1250", "latin-1"):
        try:
            return _normalise_text(data.decode(encoding))
        except UnicodeDecodeError:
            continue
    return _normalise_text(data.decode("utf-8", errors="replace"))


def _xml_text(element: ElementTree.Element) -> str:
    paragraphs: list[str] = []
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    for paragraph in element.iter(f"{namespace}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t"))
        if text.strip():
            paragraphs.append(text)
    return _normalise_text("\n\n".join(paragraphs))


class SourceTextIndex:
    """Builds a bounded local full-text cache for source attachments.

    Extraction is intentionally best-effort: failed or unsupported attachments are
    remembered so a search never repeatedly attempts to parse the same file.
    """

    def __init__(self, database: Database, files: FileStore) -> None:
        self.database = database
        self.files = files

    def search_source(self, user_id: str, source_id: str, query: str, limit: int = 60) -> dict[str, Any]:
        files = self.database.source_text_files(user_id, source_id)
        for file in files:
            self.ensure_file(user_id, file)
        return {
            "files": self.database.source_text_files(user_id, source_id),
            "results": self.database.search_source_file_text(user_id, source_id, query, limit=limit),
        }

    def read_file(self, user_id: str, source_id: str, file_id: str) -> dict[str, Any]:
        """Return one extracted attachment for the internal reader."""
        files = self.database.source_text_files(user_id, source_id)
        file = next((entry for entry in files if entry["id"] == file_id), None)
        if not file:
            raise KeyError("Príloha neexistuje.")
        self.ensure_file(user_id, file)
        return self.database.source_file_text_content(user_id, source_id, file_id)

    def index_all(self, user_id: str) -> None:
        for file in self.database.source_text_files(user_id):
            self.ensure_file(user_id, file)

    def ensure_file(self, user_id: str, file: dict[str, Any]) -> None:
        status = str(file.get("textIndexStatus") or "pending")
        if status in {"ready", "unsupported", "too_large", "missing", "failed"}:
            return
        path = self.files.path_for_hash(str(file.get("blob_hash") or file.get("blobHash") or ""))
        if not path.is_file():
            self.database.save_source_file_text(user_id, str(file["id"]), status="missing", error="Obsah súboru sa nenašiel.")
            return
        if path.stat().st_size > MAX_INDEXED_FILE_BYTES:
            self.database.save_source_file_text(
                user_id,
                str(file["id"]),
                status="too_large",
                error="Súbor je na textové spracovanie príliš veľký.",
            )
            return
        try:
            content, locations = self._extract(path, file)
        except UnsupportedSourceText as error:
            self.database.save_source_file_text(user_id, str(file["id"]), status="unsupported", error=str(error))
            return
        except Exception as error:
            self.database.save_source_file_text(user_id, str(file["id"]), status="failed", error=f"Text sa nepodarilo načítať: {error}")
            return

        if len(content) > MAX_INDEXED_TEXT_CHARACTERS:
            content = content[:MAX_INDEXED_TEXT_CHARACTERS]
            locations = self._trim_locations(locations, len(content))
        self.database.save_source_file_text(
            user_id,
            str(file["id"]),
            status="ready",
            content=content,
            locations=locations,
        )

    def _extract(self, path: Path, file: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        suffix = Path(str(file.get("original_name") or file.get("originalName") or "")).suffix.lower()
        mime_type = str(file.get("mime_type") or file.get("mimeType") or "").lower()
        if suffix == ".pdf" or mime_type == "application/pdf":
            return self._extract_pdf(path)
        if suffix == ".docx" or mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return self._extract_docx(path)
        if suffix == ".epub" or mime_type == "application/epub+zip":
            return self._extract_epub(path)
        if suffix in {".html", ".htm"} or mime_type in {"text/html", "application/xhtml+xml"}:
            parser = _HtmlTextParser()
            parser.feed(_decode_text(path.read_bytes()))
            return self._one_location(parser.text(), "Obsah")
        if suffix in {".txt", ".md", ".markdown", ".csv", ".json", ".xml", ".log", ".c", ".h", ".py", ".js", ".ts", ".css", ".sh"} or mime_type.startswith("text/"):
            return self._one_location(_decode_text(path.read_bytes()), "Obsah")
        raise UnsupportedSourceText("Pre tento typ súboru zatiaľ nevieme vytiahnuť text.")

    def _extract_pdf(self, path: Path) -> tuple[str, list[dict[str, Any]]]:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise UnsupportedSourceText("PDF je chránené heslom.")
        parts: list[str] = []
        locations: list[dict[str, Any]] = []
        offset = 0
        for number, page in enumerate(reader.pages, start=1):
            text = _normalise_text(page.extract_text() or "")
            if not text:
                continue
            if parts:
                parts.append("\n\n")
                offset += 2
            start = offset
            parts.append(text)
            offset += len(text)
            locations.append({"locator": f"Strana {number}", "start": start, "end": offset})
        return "".join(parts), locations

    def _extract_docx(self, path: Path) -> tuple[str, list[dict[str, Any]]]:
        with zipfile.ZipFile(path) as archive:
            self._validate_archive(archive)
            try:
                root = ElementTree.fromstring(archive.read("word/document.xml"))
            except KeyError as error:
                raise UnsupportedSourceText("Dokument DOCX nemá čitateľný obsah.") from error
        return self._one_location(_xml_text(root), "Dokument")

    def _extract_epub(self, path: Path) -> tuple[str, list[dict[str, Any]]]:
        with zipfile.ZipFile(path) as archive:
            self._validate_archive(archive)
            rootfile = self._epub_rootfile(archive)
            package = ElementTree.fromstring(archive.read(rootfile))
            package_dir = posixpath.dirname(rootfile)
            namespace = "{http://www.idpf.org/2007/opf}"
            manifest = {
                item.get("id", ""): item.get("href", "")
                for item in package.findall(f"{namespace}manifest/{namespace}item")
            }
            spine = [item.get("idref", "") for item in package.findall(f"{namespace}spine/{namespace}itemref")]
            parts: list[str] = []
            locations: list[dict[str, Any]] = []
            offset = 0
            for number, item_id in enumerate(spine[:MAX_EPUB_DOCUMENTS], start=1):
                href = manifest.get(item_id, "")
                if not href:
                    continue
                entry = posixpath.normpath(posixpath.join(package_dir, href))
                try:
                    raw = archive.read(entry)
                except KeyError:
                    continue
                parser = _HtmlTextParser()
                parser.feed(_decode_text(raw))
                text = parser.text()
                if not text:
                    continue
                if parts:
                    parts.append("\n\n")
                    offset += 2
                start = offset
                parts.append(text)
                offset += len(text)
                locations.append({"locator": parser.heading() or f"Kapitola {number}", "start": start, "end": offset})
        if not parts:
            raise UnsupportedSourceText("EPUB neobsahuje čitateľný text.")
        return "".join(parts), locations

    @staticmethod
    def _one_location(content: str, locator: str) -> tuple[str, list[dict[str, Any]]]:
        return content, [{"locator": locator, "start": 0, "end": len(content)}] if content else []

    @staticmethod
    def _validate_archive(archive: zipfile.ZipFile) -> None:
        if sum(entry.file_size for entry in archive.infolist()) > MAX_ARCHIVE_UNPACKED_BYTES:
            raise UnsupportedSourceText("Archív je na textové spracovanie príliš veľký.")

    @staticmethod
    def _epub_rootfile(archive: zipfile.ZipFile) -> str:
        try:
            container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
            rootfile = container.find(".//{*}rootfile")
            if rootfile is not None and rootfile.get("full-path"):
                return str(rootfile.get("full-path"))
        except (KeyError, ElementTree.ParseError):
            pass
        for entry in archive.namelist():
            if entry.lower().endswith(".opf"):
                return entry
        raise UnsupportedSourceText("EPUB nemá čitateľnú štruktúru knihy.")

    @staticmethod
    def _trim_locations(locations: list[dict[str, Any]], length: int) -> list[dict[str, Any]]:
        trimmed: list[dict[str, Any]] = []
        for location in locations:
            start = min(max(0, int(location.get("start", 0))), length)
            end = min(max(start, int(location.get("end", 0))), length)
            if start >= length:
                break
            trimmed.append({"locator": str(location.get("locator") or "Obsah"), "start": start, "end": end})
        return trimmed


class UnsupportedSourceText(ValueError):
    pass
