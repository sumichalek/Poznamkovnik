from __future__ import annotations

import re
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter

from .database import Database, ValidationError
from .files import FileStore


SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/tiff", "image/gif"}
MAX_DOCUMENT_PAGES = 500


class DocumentWorkshop:
    """Creates a new PDF from immutable source attachments or uploaded images/PDFs."""

    def __init__(self, root: Path, database: Database, files: FileStore) -> None:
        self.root = root
        self.database = database
        self.files = files
        self.thumbnails_dir = root / "thumbnails"
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def supports(file_info: dict[str, Any]) -> bool:
        mime_type = str(file_info.get("mime_type") or file_info.get("mimeType") or "").lower()
        filename = str(file_info.get("original_name") or file_info.get("originalName") or "").lower()
        return mime_type == "application/pdf" or filename.endswith(".pdf") or mime_type in SUPPORTED_IMAGE_TYPES

    def page_count(self, file_info: dict[str, Any]) -> int:
        if not self.supports(file_info):
            raise ValidationError("Dielňa zatiaľ podporuje PDF a obrázky JPEG, PNG, WebP, TIFF alebo GIF.")
        blob_hash = str(file_info.get("blob_hash") or file_info.get("blobHash") or "")
        path = self.files.path_for_hash(blob_hash)
        if not path.is_file():
            raise ValidationError("Obsah vybraného súboru sa nenašiel.")
        if self._is_pdf(file_info):
            try:
                count = len(PdfReader(str(path)).pages)
            except Exception as error:
                raise ValidationError("PDF sa nepodarilo načítať. Môže byť poškodené alebo chránené heslom.") from error
        else:
            try:
                with Image.open(path) as image:
                    count = int(getattr(image, "n_frames", 1))
            except (OSError, UnidentifiedImageError) as error:
                raise ValidationError("Obrázok sa nepodarilo načítať.") from error
        if not 1 <= count <= MAX_DOCUMENT_PAGES:
            raise ValidationError(f"Jeden vstup môže mať najviac {MAX_DOCUMENT_PAGES} strán.")
        return count

    def thumbnail(self, user_id: str, project_id: str, page_id: str) -> Path:
        page = self.database.document_page_file(user_id, project_id, page_id)
        source = self.files.path_for_hash(str(page["blob_hash"]))
        if not source.is_file():
            raise KeyError("Obsah vstupného súboru sa nenašiel.")
        rotation = int(page["rotation"])
        cache_dir = self.thumbnails_dir / project_id
        cache_dir.mkdir(parents=True, exist_ok=True)
        destination = cache_dir / f"{page_id}-{rotation}.jpg"
        if destination.is_file():
            return destination
        for stale in cache_dir.glob(f"{page_id}-*.jpg"):
            stale.unlink(missing_ok=True)
        temporary = destination.with_suffix(".tmp.jpg")
        if self._is_pdf(page):
            self._render_pdf_page(source, int(page["input_page_index"]) + 1, temporary)
            if rotation:
                self._rotate_image(temporary, destination, rotation)
                temporary.unlink(missing_ok=True)
            else:
                temporary.replace(destination)
        else:
            self._render_image_page(source, int(page["input_page_index"]), rotation, destination)
        return destination

    def build_source(self, user_id: str, project_id: str, title: str) -> dict[str, Any]:
        detail = self.database.document_project_detail(user_id, project_id)
        pages = detail["pages"]
        if not pages:
            raise ValidationError("Projekt ešte neobsahuje žiadnu stranu.")
        output_title = str(title or "").strip()[:240] or str(detail["project"]["title"]).strip() or "Nový dokument"
        temporary = self.files.tmp_dir / f"{uuid.uuid4().hex}.pdf"
        source_id = str(uuid.uuid4())
        try:
            writer = PdfWriter()
            for page in pages:
                self._append_page(writer, page)
            with temporary.open("wb") as output:
                writer.write(output)
            filename = f"{self._filename(output_title)}.pdf"
            with temporary.open("rb") as output:
                file_info = self.files.store_upload(output, filename, "application/pdf")
            try:
                source = self.database.create_source(
                    user_id,
                    {
                        "id": source_id,
                        "title": output_title,
                        "kind": "attachment",
                        "description": f"PDF vytvorené v Dielni dokumentov. Počet výstupných strán: {len(pages)}.",
                        "metadata": {
                            "documentWorkshop": {
                                "projectId": project_id,
                                "inputCount": len(detail["inputs"]),
                                "pageCount": len(pages),
                                "inputs": [
                                    {
                                        "name": item["originalName"],
                                        "sourceId": item.get("sourceId", ""),
                                        "sourceTitle": item.get("sourceTitle", ""),
                                    }
                                    for item in detail["inputs"]
                                ],
                            }
                        },
                    },
                )
                result = self.database.add_source_file(user_id, source["id"], str(uuid.uuid4()), file_info)
                source_ids = {str(item.get("sourceId") or "") for item in detail["inputs"]}
                for input_source_id in source_ids - {"", result["id"]}:
                    try:
                        self.database.create_semantic_link(
                            user_id,
                            "source",
                            result["id"],
                            {
                                "targetType": "source",
                                "targetId": input_source_id,
                                "relationType": "reference",
                                "note": "Výstup vytvorený v Dielni dokumentov.",
                            },
                        )
                    except KeyError:
                        # The source may have been deleted while the PDF was being created.
                        continue
                return result
            except Exception:
                if file_info["created"]:
                    self.files.delete_blob(str(file_info["blobHash"]))
                raise
        finally:
            temporary.unlink(missing_ok=True)

    def _append_page(self, writer: PdfWriter, page: dict[str, Any]) -> None:
        source = self.files.path_for_hash(str(page.get("blobHash") or page.get("blob_hash") or ""))
        if not source.is_file():
            raise ValidationError(f"Obsah súboru „{page.get('originalName', 'dokument')}“ sa nenašiel.")
        rotation = int(page.get("rotation", 0))
        if self._is_pdf(page):
            try:
                pdf_page = PdfReader(str(source)).pages[int(page["inputPageIndex"])]
            except Exception as error:
                raise ValidationError(f"Stranu zo súboru „{page.get('originalName', 'PDF')}“ sa nepodarilo načítať.") from error
            self._rotate_pdf_page(pdf_page, rotation)
            writer.add_page(pdf_page)
            return

        try:
            with Image.open(source) as image:
                image.seek(int(page["inputPageIndex"]))
                rendered = image.convert("RGB")
                if rotation:
                    rendered = rendered.rotate(-rotation, expand=True)
                with tempfile.NamedTemporaryFile(suffix=".pdf", dir=self.files.tmp_dir, delete=False) as converted:
                    converted_path = Path(converted.name)
                try:
                    rendered.save(converted_path, format="PDF", resolution=144.0)
                    writer.add_page(PdfReader(str(converted_path)).pages[0])
                finally:
                    converted_path.unlink(missing_ok=True)
        except (OSError, UnidentifiedImageError) as error:
            raise ValidationError(f"Obrázok „{page.get('originalName', 'obrázok')}“ sa nepodarilo spracovať.") from error

    @staticmethod
    def _rotate_pdf_page(page: Any, rotation: int) -> None:
        if not rotation:
            return
        if hasattr(page, "rotate"):
            page.rotate(rotation)
        else:
            page.rotate_clockwise(rotation)

    @staticmethod
    def _is_pdf(file_info: dict[str, Any]) -> bool:
        mime_type = str(file_info.get("mime_type") or file_info.get("mimeType") or "").lower()
        filename = str(file_info.get("original_name") or file_info.get("originalName") or "").lower()
        return mime_type == "application/pdf" or filename.endswith(".pdf")

    @staticmethod
    def _filename(value: str) -> str:
        result = re.sub(r"[\\/:*?\"<>|]+", "-", value).strip(" .")
        return result[:180] or "dokument"

    @staticmethod
    def _rotate_image(source: Path, destination: Path, rotation: int) -> None:
        with Image.open(source) as image:
            image.convert("RGB").rotate(-rotation, expand=True).save(destination, format="JPEG", quality=82)

    @staticmethod
    def _render_image_page(source: Path, page_index: int, rotation: int, destination: Path) -> None:
        with Image.open(source) as image:
            image.seek(page_index)
            rendered = image.convert("RGB")
            if rotation:
                rendered = rendered.rotate(-rotation, expand=True)
            rendered.thumbnail((260, 340))
            rendered.save(destination, format="JPEG", quality=82)

    @staticmethod
    def _render_pdf_page(source: Path, page_number: int, destination: Path) -> None:
        prefix = destination.with_suffix("")
        try:
            subprocess.run(
                [
                    "pdftoppm",
                    "-f",
                    str(page_number),
                    "-l",
                    str(page_number),
                    "-jpeg",
                    "-scale-to",
                    "340",
                    str(source),
                    str(prefix),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=25,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ValidationError("Náhľad PDF sa nepodarilo vytvoriť.") from error
        rendered = Path(f"{prefix}-{page_number}.jpg")
        if not rendered.is_file():
            raise ValidationError("Náhľad PDF sa nepodarilo vytvoriť.")
        rendered.replace(destination)
