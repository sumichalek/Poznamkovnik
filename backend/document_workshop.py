from __future__ import annotations

import os
import io
import json
import hashlib
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
import zipfile
import posixpath
from html import escape
from pathlib import Path
from typing import Any, BinaryIO, Callable

from PIL import Image, UnidentifiedImageError
from pypdf import PageObject, PdfReader, PdfWriter, Transformation
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image as FlowableImage, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from .source_text import _HtmlTextParser, _decode_text

from .database import Database, ValidationError
from .files import FileStore


SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/tiff", "image/gif"}
SUPPORTED_OFFICE_EXTENSIONS = {
    ".csv", ".doc", ".docx", ".ods", ".odt", ".odp", ".ppt", ".pptx", ".rtf", ".txt", ".xls", ".xlsx"
}
SUPPORTED_EPUB_EXTENSIONS = {".epub"}
MAX_DOCUMENT_PAGES = 500
OFFICE_CONVERSION_TIMEOUT_SECONDS = 60
OCR_TIMEOUT_SECONDS = 10 * 60
STAGED_INPUT_MAX_AGE_SECONDS = 24 * 60 * 60
DOCUMENT_PROJECT_TRANSFER_FORMAT = "poznamkovnik-document-project"
DOCUMENT_PROJECT_TRANSFER_VERSION = 1
MAX_DOCUMENT_PROJECT_TRANSFER_BYTES = 512 * 1024 * 1024
MAX_DOCUMENT_PROJECT_TRANSFER_UNPACKED_BYTES = 768 * 1024 * 1024
MAX_DOCUMENT_PROJECT_TRANSFER_MANIFEST_BYTES = 1 * 1024 * 1024
A4_PAGE_SIZES = {
    "a4-portrait": (595.276, 841.890),
    "a4-landscape": (841.890, 595.276),
}


class DocumentWorkshop:
    """Creates a new PDF from immutable source attachments or uploaded images/PDFs."""

    def __init__(
        self,
        root: Path,
        database: Database,
        files: FileStore,
        source_indexer: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.root = root
        self.database = database
        self.files = files
        self.source_indexer = source_indexer
        self.thumbnails_dir = root / "thumbnails"
        self.previews_dir = root / "previews"
        self.stages_dir = root / "stages"
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)
        self.previews_dir.mkdir(parents=True, exist_ok=True)
        self.stages_dir.mkdir(parents=True, exist_ok=True)
        self._build_jobs: dict[str, dict[str, Any]] = {}
        self._build_jobs_lock = threading.Lock()

    @staticmethod
    def supports(file_info: dict[str, Any]) -> bool:
        mime_type = str(file_info.get("mime_type") or file_info.get("mimeType") or "").lower()
        filename = str(file_info.get("original_name") or file_info.get("originalName") or "").lower()
        return (
            mime_type == "application/pdf"
            or filename.endswith(".pdf")
            or mime_type in SUPPORTED_IMAGE_TYPES
            or Path(filename).suffix in SUPPORTED_OFFICE_EXTENSIONS
            or mime_type == "application/epub+zip"
            or Path(filename).suffix in SUPPORTED_EPUB_EXTENSIONS
        )

    @staticmethod
    def requires_conversion(file_info: dict[str, Any]) -> bool:
        filename = str(file_info.get("original_name") or file_info.get("originalName") or "").lower()
        return Path(filename).suffix in SUPPORTED_OFFICE_EXTENSIONS | SUPPORTED_EPUB_EXTENSIONS

    @staticmethod
    def _is_epub(file_info: dict[str, Any]) -> bool:
        mime_type = str(file_info.get("mime_type") or file_info.get("mimeType") or "").lower()
        filename = str(file_info.get("original_name") or file_info.get("originalName") or "").lower()
        return mime_type == "application/epub+zip" or Path(filename).suffix == ".epub"

    def convert_to_pdf(self, file_info: dict[str, Any]) -> Path:
        if self._is_epub(file_info):
            return self.convert_epub_to_pdf(file_info)
        return self.convert_office_to_pdf(file_info)

    def convert_epub_to_pdf(self, file_info: dict[str, Any]) -> Path:
        """Typeset an EPUB spine into a stable internal PDF while retaining the original EPUB."""
        blob_hash = str(file_info.get("blob_hash") or file_info.get("blobHash") or "")
        source = self.files.path_for_hash(blob_hash)
        if not source.is_file():
            raise ValidationError("Obsah vybraného EPUB sa nenašiel.")
        destination = self.files.tmp_dir / f"{uuid.uuid4().hex}.pdf"
        completed = False
        try:
            with zipfile.ZipFile(source) as archive:
                entries = archive.infolist()
                if len(entries) > 10_000 or sum(item.file_size for item in entries) > 768 * 1024 * 1024:
                    raise ValidationError("EPUB je po rozbalení príliš veľký.")
                try:
                    from xml.etree import ElementTree
                    container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
                    rootfile = container.find(".//{*}rootfile")
                    root_name = str(rootfile.get("full-path")) if rootfile is not None else ""
                    package = ElementTree.fromstring(archive.read(root_name))
                except (KeyError, ElementTree.ParseError, AttributeError) as error:
                    raise ValidationError("EPUB nemá čitateľnú štruktúru knihy.") from error
                package_dir = posixpath.dirname(root_name)
                manifest = {
                    str(item.get("id") or ""): str(item.get("href") or "")
                    for item in package.findall(".//{*}manifest/{*}item")
                }
                spine = [str(item.get("idref") or "") for item in package.findall(".//{*}spine/{*}itemref")]
                chapters: list[tuple[str, list[bytes]]] = []
                for item_id in spine[:500]:
                    href = manifest.get(item_id, "")
                    if not href:
                        continue
                    entry = posixpath.normpath(posixpath.join(package_dir, href.split("#", 1)[0]))
                    if entry.startswith("../") or entry.startswith("/"):
                        continue
                    try:
                        raw_chapter = archive.read(entry)
                        decoded_chapter = _decode_text(raw_chapter)
                        parser = _HtmlTextParser()
                        parser.feed(decoded_chapter)
                    except KeyError:
                        continue
                    text = parser.text().strip()
                    if text:
                        images: list[bytes] = []
                        chapter_dir = posixpath.dirname(entry)
                        for match in re.finditer(r"<img\b[^>]*\bsrc\s*=\s*['\"]([^'\"]+)['\"]", decoded_chapter, re.I):
                            image_entry = posixpath.normpath(posixpath.join(chapter_dir, match.group(1).split("#", 1)[0]))
                            if image_entry.startswith("../") or image_entry.startswith("/"):
                                continue
                            try:
                                payload = archive.read(image_entry)
                                if 0 < len(payload) <= 20 * 1024 * 1024:
                                    with Image.open(io.BytesIO(payload)) as candidate:
                                        candidate.verify()
                                    images.append(payload)
                            except (KeyError, OSError, UnidentifiedImageError):
                                continue
                        chapters.append((text, images))
            if not chapters:
                raise ValidationError("EPUB neobsahuje čitateľné kapitoly.")
            styles = getSampleStyleSheet()
            story: list[Any] = []
            for chapter_index, (chapter, chapter_images) in enumerate(chapters):
                if chapter_index:
                    story.append(PageBreak())
                paragraphs = [part.strip() for part in re.split(r"\n\s*\n|\n", chapter) if part.strip()]
                for paragraph_index, paragraph in enumerate(paragraphs):
                    style = styles["Heading2"] if paragraph_index == 0 and len(paragraph) < 180 else styles["BodyText"]
                    story.append(Paragraph(escape(paragraph).replace("\n", "<br/>"), style))
                    story.append(Spacer(1, 8))
                for payload in chapter_images:
                    image_stream = io.BytesIO(payload)
                    illustration = FlowableImage(image_stream)
                    scale = min(1.0, 480 / max(1.0, illustration.imageWidth), 620 / max(1.0, illustration.imageHeight))
                    illustration.drawWidth *= scale
                    illustration.drawHeight *= scale
                    story.extend((Spacer(1, 10), illustration, Spacer(1, 10)))
            SimpleDocTemplate(
                str(destination), pagesize=A4, rightMargin=48, leftMargin=48, topMargin=54, bottomMargin=54,
                title=str(file_info.get("original_name") or file_info.get("originalName") or "EPUB"),
            ).build(story)
            completed = True
            return destination
        except zipfile.BadZipFile as error:
            raise ValidationError("Vybraný súbor nie je čitateľný EPUB.") from error
        except OSError as error:
            raise ValidationError("EPUB sa nepodarilo pripraviť na prevod.") from error
        finally:
            if not completed or (destination.exists() and destination.stat().st_size == 0):
                destination.unlink(missing_ok=True)

    @staticmethod
    def ocr_status() -> dict[str, Any]:
        executable = shutil.which("ocrmypdf")
        tesseract = shutil.which("tesseract")
        languages: list[str] = []
        if tesseract:
            try:
                result = subprocess.run(
                    [tesseract, "--list-langs"], capture_output=True, text=True, timeout=10, check=False
                )
                languages = [line.strip() for line in result.stdout.splitlines()[1:] if line.strip()]
            except (OSError, subprocess.TimeoutExpired):
                languages = []
        available = bool(executable and tesseract)
        return {
            "available": available,
            "languages": languages,
            "message": "OCR je pripravené." if available else "OCR vyžaduje lokálne nástroje OCRmyPDF a Tesseract.",
        }

    def apply_ocr(
        self, source: Path, mode: str, languages: Any, *, cancel_event: threading.Event | None = None
    ) -> None:
        if mode == "off":
            return
        if mode not in {"auto", "force"}:
            raise ValidationError("Režim OCR nie je platný.")
        status = self.ocr_status()
        if not status["available"]:
            raise ValidationError(str(status["message"]))
        requested = [str(item).strip() for item in languages] if isinstance(languages, list) else ["slk", "eng"]
        installed = set(status["languages"])
        selected = [item for item in requested if item and item in installed][:8]
        if not selected:
            fallback = "eng" if "eng" in installed else next(iter(installed), "")
            selected = [fallback] if fallback else []
        if not selected:
            raise ValidationError("Tesseract nemá nainštalovaný žiadny jazyk OCR.")
        destination = self.files.tmp_dir / f"{uuid.uuid4().hex}-ocr.pdf"
        command = [
            str(shutil.which("ocrmypdf")), "--output-type", "pdf", "--deskew", "--rotate-pages",
            "--language", "+".join(selected), "--skip-text" if mode == "auto" else "--force-ocr",
            str(source), str(destination),
        ]
        try:
            with tempfile.TemporaryFile() as error_output:
                process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=error_output)
                started = time.monotonic()
                while process.poll() is None:
                    if cancel_event and cancel_event.wait(0.2):
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=3)
                        raise ValidationError("OCR bolo zrušené.")
                    if time.monotonic() - started > OCR_TIMEOUT_SECONDS:
                        process.kill()
                        process.wait(timeout=3)
                        raise ValidationError("OCR trvalo príliš dlho a bolo zastavené.")
                    if not cancel_event:
                        time.sleep(0.2)
                if process.returncode:
                    error_output.seek(0)
                    raise subprocess.CalledProcessError(
                        process.returncode, command, stderr=error_output.read()
                    )
            if not destination.is_file() or destination.stat().st_size == 0:
                raise ValidationError("OCR nevytvorilo čitateľné PDF.")
            destination.replace(source)
        except subprocess.CalledProcessError as error:
            message = error.stderr.decode("utf-8", errors="replace").strip()[-800:]
            raise ValidationError(f"OCR sa nepodarilo dokončiť. {message}".strip()) from error
        finally:
            destination.unlink(missing_ok=True)

    def start_build_job(self, user_id: str, project_id: str, data: Any) -> dict[str, Any]:
        settings = dict(data) if isinstance(data, dict) else {"title": str(data or "")}
        job_id = uuid.uuid4().hex
        cancel_event = threading.Event()
        job = {
            "id": job_id, "userId": user_id, "projectId": project_id, "status": "queued",
            "phase": "Čaká na spracovanie", "progress": 0, "error": "", "source": None,
            "cancelEvent": cancel_event, "createdAt": time.time(),
        }
        with self._build_jobs_lock:
            expiry = time.time() - 24 * 60 * 60
            self._build_jobs = {
                key: value for key, value in self._build_jobs.items()
                if value["status"] in {"queued", "running", "cancelling"} or value["createdAt"] >= expiry
            }
            active = sum(
                1 for item in self._build_jobs.values()
                if item["userId"] == user_id and item["status"] in {"queued", "running", "cancelling"}
            )
            if active >= 2:
                raise ValidationError("Naraz môžu bežať najviac dve úlohy vytvorenia dokumentu.")
            self._build_jobs[job_id] = job
        threading.Thread(
            target=self._run_build_job, args=(job_id, user_id, project_id, settings),
            name=f"document-build-{job_id[:8]}", daemon=True,
        ).start()
        return self.build_job(user_id, project_id, job_id)

    def _run_build_job(self, job_id: str, user_id: str, project_id: str, settings: dict[str, Any]) -> None:
        with self._build_jobs_lock:
            job = self._build_jobs[job_id]
            job.update(status="running", phase="Skladám výsledné PDF", progress=10)
            cancel_event = job["cancelEvent"]
        try:
            settings["_cancelEvent"] = cancel_event
            settings["_phaseCallback"] = lambda phase: self._set_build_job_phase(job_id, phase)
            source = self.build_source(user_id, project_id, settings)
            with self._build_jobs_lock:
                job = self._build_jobs[job_id]
                if cancel_event.is_set():
                    job.update(status="cancelled", phase="Zrušené", progress=0)
                else:
                    job.update(status="completed", phase="Hotovo", progress=100, source=source)
        except Exception as error:
            with self._build_jobs_lock:
                job = self._build_jobs[job_id]
                cancelled = cancel_event.is_set()
                job.update(
                    status="cancelled" if cancelled else "failed",
                    phase="Zrušené" if cancelled else "Spracovanie zlyhalo",
                    progress=0,
                    error="" if cancelled else str(error),
                )

    def _set_build_job_phase(self, job_id: str, phase: str) -> None:
        progress = 20
        if phase.startswith("Rozpoznávam"):
            progress = 45
        elif phase.startswith("Ukladám"):
            progress = 90
        with self._build_jobs_lock:
            if job_id in self._build_jobs:
                self._build_jobs[job_id].update(phase=phase, progress=progress)

    def build_job(self, user_id: str, project_id: str, job_id: str) -> dict[str, Any]:
        with self._build_jobs_lock:
            job = self._build_jobs.get(job_id)
            if not job or job["userId"] != user_id or job["projectId"] != project_id:
                raise KeyError("Úloha vytvorenia dokumentu neexistuje.")
            return {key: job[key] for key in ("id", "status", "phase", "progress", "error", "source")}

    def cancel_build_job(self, user_id: str, project_id: str, job_id: str) -> dict[str, Any]:
        with self._build_jobs_lock:
            job = self._build_jobs.get(job_id)
            if not job or job["userId"] != user_id or job["projectId"] != project_id:
                raise KeyError("Úloha vytvorenia dokumentu neexistuje.")
            if job["status"] in {"queued", "running"}:
                job["status"] = "cancelling"
                job["phase"] = "Zastavujem OCR"
                job["progress"] = 0
                job["cancelEvent"].set()
        return self.build_job(user_id, project_id, job_id)

    def convert_office_to_pdf(self, file_info: dict[str, Any]) -> Path:
        """Convert a supported office file into an isolated temporary PDF with LibreOffice."""
        if not self.requires_conversion(file_info):
            raise ValidationError("Tento súbor netreba prevádzať do PDF.")
        blob_hash = str(file_info.get("blob_hash") or file_info.get("blobHash") or "")
        source = self.files.path_for_hash(blob_hash)
        if not source.is_file():
            raise ValidationError("Obsah vybraného súboru sa nenašiel.")

        temporary_pdf = self.files.tmp_dir / f"{uuid.uuid4().hex}.pdf"
        work_dir = Path(tempfile.mkdtemp(prefix="office-convert-", dir=self.files.tmp_dir))
        output_dir = work_dir / "output"
        profile_dir = work_dir / "profile"
        runtime_dir = work_dir / "runtime"
        original_name = str(file_info.get("original_name") or file_info.get("originalName") or "dokument")
        input_path = work_dir / f"input{Path(original_name).suffix.lower()}"
        output_dir.mkdir()
        profile_dir.mkdir()
        runtime_dir.mkdir()
        try:
            # Blob storage deliberately uses hashes without extensions; LibreOffice needs the extension to detect its format.
            shutil.copyfile(source, input_path)
            subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--nologo",
                    "--nodefault",
                    "--nolockcheck",
                    "--nofirststartwizard",
                    f"-env:UserInstallation={profile_dir.as_uri()}",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(output_dir),
                    str(input_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=OFFICE_CONVERSION_TIMEOUT_SECONDS,
                env={
                    **os.environ,
                    "HOME": str(work_dir / "home"),
                    "XDG_CONFIG_HOME": str(work_dir / "config"),
                    "XDG_CACHE_HOME": str(work_dir / "cache"),
                    "XDG_RUNTIME_DIR": str(runtime_dir),
                },
            )
            pdfs = [path for path in output_dir.glob("*.pdf") if path.is_file() and path.stat().st_size > 0]
            if len(pdfs) != 1:
                raise ValidationError("LibreOffice z dokumentu nevytvoril čitateľné PDF.")
            shutil.copyfile(pdfs[0], temporary_pdf)
            return temporary_pdf
        except subprocess.TimeoutExpired as error:
            raise ValidationError("Prevod dokumentu trval príliš dlho a bol zastavený.") from error
        except FileNotFoundError as error:
            raise ValidationError("Prevod kancelárskych dokumentov nie je na serveri dostupný.") from error
        except subprocess.CalledProcessError as error:
            raise ValidationError("LibreOffice nedokázal tento dokument previesť do PDF.") from error
        except OSError as error:
            raise ValidationError("Kancelársky dokument sa nepodarilo pripraviť na prevod.") from error
        finally:
            if not temporary_pdf.is_file():
                temporary_pdf.unlink(missing_ok=True)
            shutil.rmtree(work_dir, ignore_errors=True)

    def page_count(self, file_info: dict[str, Any]) -> int:
        if not self.supports(file_info) or self.requires_conversion(file_info):
            raise ValidationError("Dielňa podporuje PDF, obrázky a vybrané dokumenty po lokálnom prevode.")
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

    def prepare_input(
        self,
        user_id: str,
        project_id: str,
        file_info: dict[str, Any],
        maximum_bytes: int,
        *,
        source_id: str = "",
        source_file_id: str = "",
    ) -> dict[str, Any]:
        """Prepare an input outside a project so the user can choose its pages first."""
        self._cleanup_staged_inputs()
        # This also verifies that the project belongs to the active user.
        self.database.document_project_detail(user_id, project_id)
        raw_hash = str(file_info.get("blobHash") or file_info.get("blob_hash") or "")
        raw_name = str(file_info.get("originalName") or file_info.get("original_name") or "dokument")
        raw_mime = str(file_info.get("mimeType") or file_info.get("mime_type") or "application/octet-stream")
        raw_size = int(file_info.get("sizeBytes") or file_info.get("size_bytes") or 0)
        processing_info: dict[str, Any] = {
            "blobHash": raw_hash,
            "originalName": raw_name,
            "mimeType": raw_mime,
            "sizeBytes": raw_size,
        }
        temporary_pdf: Path | None = None
        owned_blobs = {raw_hash} if bool(file_info.get("created")) and raw_hash else set()
        try:
            if not self.supports(file_info):
                raise ValidationError("Dielňa podporuje PDF, obrázky a vybrané kancelárske dokumenty.")
            if self.requires_conversion(file_info):
                temporary_pdf = self.convert_to_pdf(file_info)
                with temporary_pdf.open("rb") as converted:
                    processing_info = self.files.store_upload(
                        converted,
                        f"{Path(raw_name).stem or 'dokument'}.pdf",
                        "application/pdf",
                        maximum_bytes=maximum_bytes,
                    )
                if processing_info["created"]:
                    owned_blobs.add(str(processing_info["blobHash"]))

            page_count = self.page_count(processing_info)
            input_data: dict[str, Any] = {
                "id": str(uuid.uuid4()),
                "sourceId": source_id,
                "sourceFileId": source_file_id,
                "blobHash": str(processing_info["blobHash"]),
                "originalName": raw_name,
                "mimeType": str(processing_info["mimeType"]),
                "sizeBytes": int(processing_info["sizeBytes"]),
                "pageCount": page_count,
            }
            converted = temporary_pdf is not None
            if converted:
                input_data.update(
                    {
                        "originalBlobHash": raw_hash,
                        "originalMimeType": raw_mime,
                        "originalSizeBytes": raw_size,
                    }
                )

            stage_id = uuid.uuid4().hex
            stage = {
                "id": stage_id,
                "userId": user_id,
                "projectId": project_id,
                "createdAt": time.time(),
                "input": input_data,
                "ownedBlobs": sorted(owned_blobs),
            }
            self._write_stage(stage)
            return {
                "id": stage_id,
                "projectId": project_id,
                "originalName": raw_name,
                "mimeType": str(processing_info["mimeType"]),
                "pageCount": page_count,
                "converted": converted,
            }
        except Exception:
            self._delete_unreferenced_blobs(owned_blobs)
            raise
        finally:
            if temporary_pdf:
                temporary_pdf.unlink(missing_ok=True)

    def confirm_prepared_input(
        self, user_id: str, project_id: str, stage_id: str, page_indices: Any
    ) -> dict[str, Any]:
        self._cleanup_staged_inputs()
        stage = self._read_stage(user_id, project_id, stage_id)
        input_data = dict(stage["input"])
        input_data["pageIndices"] = page_indices
        detail, orphaned = self.database.add_document_input(user_id, project_id, input_data)
        for blob_hash in orphaned:
            self.files.delete_blob(blob_hash)
        self._stage_path(stage_id).unlink(missing_ok=True)
        return detail

    def discard_prepared_input(self, user_id: str, project_id: str, stage_id: str) -> None:
        stage = self._read_stage(user_id, project_id, stage_id)
        self._stage_path(stage_id).unlink(missing_ok=True)
        self._delete_unreferenced_blobs(set(stage.get("ownedBlobs", [])))

    def _stage_path(self, stage_id: str) -> Path:
        if len(stage_id) != 32 or any(character not in "0123456789abcdef" for character in stage_id):
            raise ValidationError("Príprava vstupu dokumentu neexistuje.")
        return self.stages_dir / f"{stage_id}.json"

    def _write_stage(self, stage: dict[str, Any]) -> None:
        destination = self._stage_path(str(stage["id"]))
        temporary = destination.with_suffix(".tmp")
        try:
            temporary.write_text(json.dumps(stage, ensure_ascii=True), encoding="utf-8")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    def _read_stage(self, user_id: str, project_id: str, stage_id: str) -> dict[str, Any]:
        path = self._stage_path(stage_id)
        try:
            stage = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValidationError("Príprava vstupu dokumentu už nie je dostupná.") from error
        if not isinstance(stage, dict) or stage.get("userId") != user_id or stage.get("projectId") != project_id:
            raise ValidationError("Príprava vstupu dokumentu už nie je dostupná.")
        if not isinstance(stage.get("input"), dict):
            raise ValidationError("Príprava vstupu dokumentu nie je platná.")
        return stage

    def _cleanup_staged_inputs(self) -> None:
        deadline = time.time() - STAGED_INPUT_MAX_AGE_SECONDS
        for path in self.stages_dir.glob("*.json"):
            try:
                stage = json.loads(path.read_text(encoding="utf-8"))
                created_at = float(stage.get("createdAt", 0))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                path.unlink(missing_ok=True)
                continue
            if created_at > deadline:
                continue
            path.unlink(missing_ok=True)
            if isinstance(stage, dict):
                self._delete_unreferenced_blobs(set(stage.get("ownedBlobs", [])))

    def _delete_unreferenced_blobs(self, blob_hashes: set[str]) -> None:
        for blob_hash in self.database.unreferenced_blob_hashes(blob_hashes):
            self.files.delete_blob(blob_hash)

    def thumbnail(self, user_id: str, project_id: str, page_id: str) -> Path:
        page = self.database.document_page_file(user_id, project_id, page_id)
        cache_dir = self.thumbnails_dir / project_id
        cache_dir.mkdir(parents=True, exist_ok=True)
        crop_values = self._crop_values(page)
        destination = cache_dir / (
            f"{page_id}-{int(page.get('rotation', 0))}-{'-'.join(str(value) for value in crop_values)}.jpg"
        )
        if destination.is_file():
            return destination
        for stale in cache_dir.glob(f"{page_id}-*.jpg"):
            stale.unlink(missing_ok=True)
        temporary = self.files.tmp_dir / f"{uuid.uuid4().hex}.pdf"
        try:
            writer = PdfWriter()
            self._append_page(writer, page, {
                # A page preview is intentionally independent of the eventual output sheet.
                # Reformatting a large project must not force every thumbnail to be rendered again.
                "outputPageSize": "keep",
                "imageDpi": 144,
            })
            with temporary.open("wb") as output:
                writer.write(output)
            self._render_pdf_page(temporary, 1, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    def crop_preview(self, user_id: str, project_id: str, page_id: str) -> Path:
        """Render the uncropped, rotated source page used by the visual crop editor."""
        page = self.database.document_page_file(user_id, project_id, page_id)
        cache_dir = self.thumbnails_dir / project_id
        cache_dir.mkdir(parents=True, exist_ok=True)
        rotation = int(page.get("rotation", 0))
        destination = cache_dir / f"crop-preview-{page_id}-{rotation}.jpg"
        if destination.is_file():
            return destination
        for stale in cache_dir.glob(f"crop-preview-{page_id}-*.jpg"):
            stale.unlink(missing_ok=True)
        preview_page = {
            **page,
            "crop_top": 0,
            "crop_right": 0,
            "crop_bottom": 0,
            "crop_left": 0,
        }
        temporary = self.files.tmp_dir / f"{uuid.uuid4().hex}.pdf"
        try:
            writer = PdfWriter()
            self._append_page(writer, preview_page, {"outputPageSize": "keep", "imageDpi": page.get("image_dpi", 144)})
            with temporary.open("wb") as output:
                writer.write(output)
            self._render_pdf_page(temporary, 1, destination, scale_to=760)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    def build_source(self, user_id: str, project_id: str, data: Any) -> dict[str, Any]:
        detail = self.database.document_project_detail(user_id, project_id)
        all_pages = detail["pages"]
        if not all_pages:
            raise ValidationError("Projekt ešte neobsahuje žiadnu stranu.")
        settings = data if isinstance(data, dict) else {"title": data}
        requested_page_ids = settings.get("pageIds")
        if requested_page_ids is None:
            pages = all_pages
            selected_page_ids: list[str] = []
        elif isinstance(requested_page_ids, list):
            selected_page_ids = [str(page_id).strip() for page_id in requested_page_ids if str(page_id).strip()]
            if not selected_page_ids:
                raise ValidationError("Vyber aspoň jednu stranu pre nový zdroj.")
            if len(selected_page_ids) != len(set(selected_page_ids)):
                raise ValidationError("Výber strán obsahuje duplicitné položky.")
            known_page_ids = {str(page["id"]) for page in all_pages}
            if any(page_id not in known_page_ids for page_id in selected_page_ids):
                raise ValidationError("Niektorá vybraná strana už v projekte neexistuje.")
            selected_ids = set(selected_page_ids)
            # Preserve the currently visible project order instead of trusting client order.
            pages = [page for page in all_pages if str(page["id"]) in selected_ids]
        else:
            raise ValidationError("Výber strán pre nový zdroj nie je platný.")
        used_input_ids = {str(page.get("inputId") or "") for page in pages}
        used_inputs = [item for item in detail["inputs"] if str(item.get("id") or "") in used_input_ids]
        output_detail = {**detail, "pages": pages}
        output_title = str(settings.get("title") or "").strip()[:240] or str(detail["project"]["title"]).strip() or "Nový projekt PDF"
        description = str(settings.get("description") or "").strip()[:10_000]
        tags = settings.get("tags") if isinstance(settings.get("tags"), list) else []
        temporary = self.files.tmp_dir / f"{uuid.uuid4().hex}.pdf"
        source_id = str(uuid.uuid4())
        try:
            phase_callback = settings.get("_phaseCallback")
            if callable(phase_callback):
                phase_callback("Skladám výsledné PDF")
            self._write_pdf(output_detail, temporary)
            ocr_mode = str(settings.get("ocrMode") or "off")
            if callable(phase_callback) and ocr_mode != "off":
                phase_callback("Rozpoznávam text a vytváram textovú vrstvu")
            self.apply_ocr(
                temporary, ocr_mode, settings.get("ocrLanguages"), cancel_event=settings.get("_cancelEvent")
            )
            cancel_event = settings.get("_cancelEvent")
            if cancel_event is not None and cancel_event.is_set():
                raise ValidationError("OCR bolo zrušené.")
            if callable(phase_callback):
                phase_callback("Ukladám výsledný zdroj")
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
                        "description": description or (
                            f"PDF vytvorené v Dielni PDF z vybraných strán. Počet výstupných strán: {len(pages)}."
                            if selected_page_ids else f"PDF vytvorené v Dielni PDF. Počet výstupných strán: {len(pages)}."
                        ),
                        "tags": tags,
                        "metadata": {
                            "documentWorkshop": {
                                "projectId": project_id,
                                "inputCount": len(used_inputs),
                                "pageCount": len(pages),
                                "selectedPageCount": len(selected_page_ids) or len(pages),
                                "outputPageSize": detail["project"].get("outputPageSize", "keep"),
                                "imageDpi": detail["project"].get("imageDpi", 144),
                                "pageNumberPosition": detail["project"].get("pageNumberPosition", "none"),
                                "pageNumberStart": detail["project"].get("pageNumberStart", 1),
                                "ocrMode": ocr_mode,
                                "inputs": [
                                    {
                                        "name": item["originalName"],
                                        "sourceId": item.get("sourceId", ""),
                                        "sourceTitle": item.get("sourceTitle", ""),
                                    }
                                    for item in used_inputs
                                ],
                            }
                        },
                    },
                )
                result = self.database.add_source_file(user_id, source["id"], str(uuid.uuid4()), file_info)
                if self.source_indexer is not None:
                    try:
                        self.source_indexer(user_id, result)
                    except Exception:
                        # The generated PDF is still valid if optional text indexing fails.
                        pass
                source_ids = {str(page.get("sourceId") or "") for page in pages}
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
                                "note": "Výstup vytvorený v Dielni PDF.",
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

    def export_project(self, user_id: str, project_id: str) -> tuple[Path, str]:
        """Write one portable archive for an unfinished Dielňa PDF project."""
        detail = self.database.document_project_detail(user_id, project_id)
        project = detail["project"]
        transfer_inputs: list[dict[str, Any]] = []
        archive_files: list[tuple[str, Path]] = []

        for index, item in enumerate(detail["inputs"], start=1):
            working_hash = str(item.get("blobHash") or "")
            working_path = self.files.path_for_hash(working_hash)
            if not working_path.is_file():
                raise ValidationError(f"Obsah súboru „{item.get('originalName', 'dokument')}“ sa nenašiel.")
            working_mime = str(item.get("mimeType") or "application/octet-stream")
            working_name = f"vstup-{index:03d}{self._transfer_suffix(working_mime, item.get('originalName'))}"
            working_entry = f"inputs/{working_name}"
            page_count = self.page_count(
                {"blobHash": working_hash, "mimeType": working_mime, "originalName": working_name}
            )
            transfer_input: dict[str, Any] = {
                "id": str(item["id"]),
                "originalName": str(item.get("originalName") or "dokument"),
                "mimeType": working_mime,
                "sizeBytes": int(item.get("sizeBytes") or working_path.stat().st_size),
                "workingName": working_name,
                "workingFile": working_entry,
                "pageCount": page_count,
                "originalMimeType": str(item.get("originalMimeType") or ""),
                "originalSizeBytes": int(item.get("originalSizeBytes") or 0),
            }
            archive_files.append((working_entry, working_path))

            original_hash = str(item.get("originalBlobHash") or "")
            if original_hash and original_hash != working_hash:
                original_path = self.files.path_for_hash(original_hash)
                if not original_path.is_file():
                    raise ValidationError(f"Pôvodný súbor „{item.get('originalName', 'dokument')}“ sa nenašiel.")
                original_entry = f"originals/{index:03d}{self._transfer_suffix(item.get('originalMimeType'), item.get('originalName'))}"
                transfer_input["originalFile"] = original_entry
                archive_files.append((original_entry, original_path))
            transfer_inputs.append(transfer_input)

        manifest = {
            "format": DOCUMENT_PROJECT_TRANSFER_FORMAT,
            "version": DOCUMENT_PROJECT_TRANSFER_VERSION,
            "project": {
                "title": str(project.get("title") or "Nový projekt PDF"),
                "outputPageSize": str(project.get("outputPageSize") or "keep"),
                "imageDpi": int(project.get("imageDpi") or 144),
                "pageNumberPosition": str(project.get("pageNumberPosition") or "none"),
                "pageNumberStart": int(project.get("pageNumberStart") or 1),
            },
            "inputs": transfer_inputs,
            "pages": [
                {
                    "inputId": str(page["inputId"]),
                    "inputPageIndex": int(page["inputPageIndex"]),
                    "orderIndex": int(page["orderIndex"]),
                    "rotation": int(page.get("rotation") or 0),
                    "cropTop": int(page.get("cropTop") or 0),
                    "cropRight": int(page.get("cropRight") or 0),
                    "cropBottom": int(page.get("cropBottom") or 0),
                    "cropLeft": int(page.get("cropLeft") or 0),
                }
                for page in detail["pages"]
            ],
        }
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="dielna-pdf-", suffix=".zip", dir=self.files.tmp_dir
        )
        os.close(descriptor)
        archive_path = Path(temporary_name)
        try:
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, separators=(",", ":")))
                for entry, source in archive_files:
                    archive.write(source, entry)
            return archive_path, f"{self._filename(str(project.get('title') or 'projekt-dielne'))}-dielna-pdf.zip"
        except Exception:
            archive_path.unlink(missing_ok=True)
            raise

    def import_project(self, user_id: str, stream: BinaryIO, filename: str) -> dict[str, Any]:
        """Restore an independent project from the portable Dielňa PDF archive."""
        if Path(filename).suffix.lower() != ".zip":
            raise ValidationError("Vyber ZIP archív exportovaný z Dielne PDF.")
        owned_blobs: set[str] = set()
        try:
            with zipfile.ZipFile(stream) as archive:
                manifest, archive_entries = self._read_project_transfer_manifest(archive)
                raw_inputs = manifest["inputs"]
                raw_pages = manifest["pages"]
                input_ids: set[str] = set()
                input_id_map: dict[str, str] = {}
                imported_inputs: list[dict[str, Any]] = []
                maximum_file_bytes = self.database.source_file_max_bytes(user_id)

                for index, item in enumerate(raw_inputs, start=1):
                    if not isinstance(item, dict):
                        raise ValidationError("Archív obsahuje neplatný vstup projektu.")
                    source_input_id = str(item.get("id") or "").strip()
                    working_file = str(item.get("workingFile") or "")
                    working_name = str(item.get("workingName") or "")
                    working_mime = str(item.get("mimeType") or "")
                    if not source_input_id or source_input_id in input_ids or not working_file or not working_name:
                        raise ValidationError("Archív obsahuje neplatný vstup projektu.")
                    info = archive_entries.get(working_file)
                    if not info or info.file_size > maximum_file_bytes:
                        raise ValidationError("Vstup projektu prekračuje povolenú veľkosť alebo v archíve chýba.")
                    with archive.open(info) as source:
                        stored_working = self.files.store_upload(
                            source,
                            working_name,
                            working_mime,
                            maximum_bytes=maximum_file_bytes,
                        )
                    if stored_working["created"]:
                        owned_blobs.add(str(stored_working["blobHash"]))
                    page_count = self.page_count(stored_working)
                    try:
                        declared_page_count = int(item.get("pageCount"))
                    except (TypeError, ValueError) as error:
                        raise ValidationError("Archív obsahuje neplatný počet strán vstupu.") from error
                    if declared_page_count != page_count:
                        raise ValidationError("Vstup v archíve nemá očakávaný počet strán.")

                    original_hash = ""
                    original_size = 0
                    original_mime = str(item.get("originalMimeType") or "")
                    original_file = str(item.get("originalFile") or "")
                    if original_file:
                        original_info = archive_entries.get(original_file)
                        if not original_info or original_info.file_size > maximum_file_bytes:
                            raise ValidationError("Pôvodný súbor vstupu prekračuje povolenú veľkosť alebo v archíve chýba.")
                        with archive.open(original_info) as source:
                            stored_original = self.files.store_upload(
                                source,
                                str(item.get("originalName") or "dokument"),
                                original_mime,
                                maximum_bytes=maximum_file_bytes,
                            )
                        if stored_original["created"]:
                            owned_blobs.add(str(stored_original["blobHash"]))
                        original_hash = str(stored_original["blobHash"])
                        original_size = int(stored_original["sizeBytes"])
                    input_id_map[source_input_id] = str(uuid.uuid4())
                    input_ids.add(source_input_id)
                    imported_inputs.append(
                        {
                            "id": input_id_map[source_input_id],
                            "blobHash": str(stored_working["blobHash"]),
                            "originalBlobHash": original_hash,
                            "originalName": str(item.get("originalName") or working_name),
                            "mimeType": str(stored_working["mimeType"]),
                            "sizeBytes": int(stored_working["sizeBytes"]),
                            "originalMimeType": original_mime,
                            "originalSizeBytes": original_size,
                            "pageCount": page_count,
                        }
                    )

                imported_pages: list[dict[str, Any]] = []
                if not isinstance(raw_pages, list) or len(raw_pages) > 2_000:
                    raise ValidationError("Archív obsahuje priveľa alebo neplatné strany projektu.")
                for item in raw_pages:
                    if not isinstance(item, dict):
                        raise ValidationError("Archív obsahuje neplatnú stranu projektu.")
                    old_input_id = str(item.get("inputId") or "")
                    if old_input_id not in input_id_map:
                        raise ValidationError("Archív obsahuje stranu bez zodpovedajúceho vstupu.")
                    imported_pages.append(
                        {
                            "id": str(uuid.uuid4()),
                            "inputId": input_id_map[old_input_id],
                            "inputPageIndex": item.get("inputPageIndex"),
                            "orderIndex": item.get("orderIndex"),
                            "rotation": item.get("rotation", 0),
                            "cropTop": item.get("cropTop", 0),
                            "cropRight": item.get("cropRight", 0),
                            "cropBottom": item.get("cropBottom", 0),
                            "cropLeft": item.get("cropLeft", 0),
                        }
                    )
                if raw_inputs and not imported_pages:
                    raise ValidationError("Archív neobsahuje žiadnu stranu vstupných dokumentov.")
                return self.database.import_document_project(
                    user_id,
                    {
                        "id": str(uuid.uuid4()),
                        "project": manifest["project"],
                        "inputs": imported_inputs,
                        "pages": imported_pages,
                    },
                )
        except zipfile.BadZipFile as error:
            raise ValidationError("Vybraný súbor nie je čitateľný ZIP archív Dielne PDF.") from error
        except Exception:
            self._delete_unreferenced_blobs(owned_blobs)
            raise

    @staticmethod
    def _transfer_suffix(mime_type: Any, original_name: Any) -> str:
        normalized_mime = str(mime_type or "").lower()
        known = {
            "application/pdf": ".pdf",
            "image/gif": ".gif",
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/tiff": ".tiff",
            "image/webp": ".webp",
        }
        if normalized_mime in known:
            return known[normalized_mime]
        suffix = Path(str(original_name or "")).suffix.lower()
        return suffix if 1 < len(suffix) <= 12 and re.fullmatch(r"\.[a-z0-9]+", suffix) else ".bin"

    def _read_project_transfer_manifest(
        self, archive: zipfile.ZipFile
    ) -> tuple[dict[str, Any], dict[str, zipfile.ZipInfo]]:
        entries: dict[str, zipfile.ZipInfo] = {}
        total_unpacked = 0
        for info in archive.infolist():
            name = info.filename
            path = Path(name)
            if (
                info.is_dir()
                or not name
                or name in entries
                or name.startswith(("/", "\\"))
                or ".." in path.parts
                or info.flag_bits & 0x1
            ):
                raise ValidationError("Archív projektu má neplatnú štruktúru.")
            total_unpacked += int(info.file_size)
            if total_unpacked > MAX_DOCUMENT_PROJECT_TRANSFER_UNPACKED_BYTES:
                raise ValidationError("Rozbalený projekt Dielne PDF je príliš veľký.")
            entries[name] = info
        manifest_info = entries.get("manifest.json")
        if not manifest_info or manifest_info.file_size > MAX_DOCUMENT_PROJECT_TRANSFER_MANIFEST_BYTES:
            raise ValidationError("Archív projektu neobsahuje platný manifest.")
        try:
            with archive.open(manifest_info) as source:
                raw_manifest = source.read(MAX_DOCUMENT_PROJECT_TRANSFER_MANIFEST_BYTES + 1)
            manifest = json.loads(raw_manifest.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, OSError) as error:
            raise ValidationError("Manifest projektu Dielne PDF nie je čitateľný.") from error
        if (
            not isinstance(manifest, dict)
            or manifest.get("format") != DOCUMENT_PROJECT_TRANSFER_FORMAT
            or manifest.get("version") != DOCUMENT_PROJECT_TRANSFER_VERSION
            or not isinstance(manifest.get("project"), dict)
            or not isinstance(manifest.get("inputs"), list)
            or len(manifest["inputs"]) > 500
            or not isinstance(manifest.get("pages"), list)
        ):
            raise ValidationError("Archív nie je kompatibilný projekt Dielne PDF.")
        expected_entries = {"manifest.json"}
        for item in manifest["inputs"]:
            if not isinstance(item, dict):
                raise ValidationError("Archív obsahuje neplatný vstup projektu.")
            for key in ("workingFile", "originalFile"):
                value = str(item.get(key) or "")
                if value:
                    if value not in entries or not value.startswith(("inputs/", "originals/")):
                        raise ValidationError("Archív odkazuje na chýbajúci alebo neplatný súbor.")
                    expected_entries.add(value)
        if set(entries) != expected_entries:
            raise ValidationError("Archív projektu obsahuje neznáme súbory.")
        return manifest, entries

    def preview(self, user_id: str, project_id: str) -> tuple[Path, str]:
        """Build a short-lived cached PDF preview without creating a source record."""
        detail = self.database.document_project_detail(user_id, project_id)
        if not detail["pages"]:
            raise ValidationError("Projekt ešte neobsahuje žiadnu stranu.")
        project_token = hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:16]
        preview_token = self._preview_token(detail)
        destination = self.previews_dir / f"preview-{project_token}-{preview_token}.pdf"
        if not destination.is_file():
            temporary = self.files.tmp_dir / f"{uuid.uuid4().hex}.pdf"
            try:
                self._write_pdf(detail, temporary)
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
            self._prune_project_previews(project_token, keep=4)
        title = str(detail["project"].get("title") or "Náhľad výsledného PDF")
        return destination, f"{self._filename(title)}.pdf"

    def discard_project_previews(self, project_id: str) -> None:
        project_token = hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:16]
        for preview in self.previews_dir.glob(f"preview-{project_token}-*.pdf"):
            preview.unlink(missing_ok=True)

    def _preview_token(self, detail: dict[str, Any]) -> str:
        project = detail["project"]
        pages = detail["pages"]
        payload = {
            "outputPageSize": project.get("outputPageSize", project.get("output_page_size", "keep")),
            "imageDpi": project.get("imageDpi", project.get("image_dpi", 144)),
            "pageNumberPosition": project.get("pageNumberPosition", project.get("page_number_position", "none")),
            "pageNumberStart": project.get("pageNumberStart", project.get("page_number_start", 1)),
            "pages": [
                {
                    "id": page.get("id"),
                    "blobHash": page.get("blobHash", page.get("blob_hash")),
                    "inputPageIndex": page.get("inputPageIndex", page.get("input_page_index", 0)),
                    "rotation": page.get("rotation", 0),
                    "cropTop": page.get("cropTop", page.get("crop_top", 0)),
                    "cropRight": page.get("cropRight", page.get("crop_right", 0)),
                    "cropBottom": page.get("cropBottom", page.get("crop_bottom", 0)),
                    "cropLeft": page.get("cropLeft", page.get("crop_left", 0)),
                }
                for page in pages
            ],
        }
        serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:24]

    def _prune_project_previews(self, project_token: str, *, keep: int) -> None:
        previews = sorted(
            self.previews_dir.glob(f"preview-{project_token}-*.pdf"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for preview in previews[keep:]:
            preview.unlink(missing_ok=True)

    def _write_pdf(self, detail: dict[str, Any], destination: Path) -> None:
        writer = PdfWriter()
        for page_index, page in enumerate(detail["pages"]):
            self._append_page(writer, page, detail["project"])
            self._append_page_number(writer.pages[-1], page_index, detail["project"])
        with destination.open("wb") as output:
            writer.write(output)

    def _append_page(self, writer: PdfWriter, page: dict[str, Any], project: dict[str, Any]) -> None:
        source = self.files.path_for_hash(str(page.get("blobHash") or page.get("blob_hash") or ""))
        if not source.is_file():
            raise ValidationError(f"Obsah súboru „{page.get('originalName', 'dokument')}“ sa nenašiel.")
        rotation = int(page.get("rotation", 0))
        input_page_index = int(page.get("inputPageIndex", page.get("input_page_index", 0)))
        if self._is_pdf(page):
            try:
                pdf_page = PdfReader(str(source)).pages[input_page_index]
            except Exception as error:
                raise ValidationError(f"Stranu zo súboru „{page.get('originalName', 'PDF')}“ sa nepodarilo načítať.") from error
            self._crop_pdf_page(pdf_page, page)
            self._rotate_pdf_page(pdf_page, rotation)
            self._append_output_page(writer, pdf_page, project)
            return

        try:
            with Image.open(source) as image:
                image.seek(input_page_index)
                rendered = image.convert("RGB")
                rendered = self._crop_image(rendered, page)
                if rotation:
                    rendered = rendered.rotate(-rotation, expand=True)
                with tempfile.NamedTemporaryFile(suffix=".pdf", dir=self.files.tmp_dir, delete=False) as converted:
                    converted_path = Path(converted.name)
                try:
                    rendered.save(converted_path, format="PDF", resolution=float(self._image_dpi(project)))
                    self._append_output_page(writer, PdfReader(str(converted_path)).pages[0], project)
                finally:
                    converted_path.unlink(missing_ok=True)
        except (OSError, UnidentifiedImageError) as error:
            raise ValidationError(f"Obrázok „{page.get('originalName', 'obrázok')}“ sa nepodarilo spracovať.") from error

    @staticmethod
    def _crop_values(page: dict[str, Any]) -> tuple[int, int, int, int]:
        return (
            int(page.get("cropTop", page.get("crop_top", 0))),
            int(page.get("cropRight", page.get("crop_right", 0))),
            int(page.get("cropBottom", page.get("crop_bottom", 0))),
            int(page.get("cropLeft", page.get("crop_left", 0))),
        )

    def _crop_pdf_page(self, pdf_page: PageObject, page: dict[str, Any]) -> None:
        top, right, bottom, left = self._crop_values(page)
        if not any((top, right, bottom, left)):
            return
        crop_box = pdf_page.cropbox
        lower_left_x, lower_left_y = (float(value) for value in crop_box.lower_left)
        upper_right_x, upper_right_y = (float(value) for value in crop_box.upper_right)
        width = upper_right_x - lower_left_x
        height = upper_right_y - lower_left_y
        pdf_page.cropbox.lower_left = (lower_left_x + width * left / 100, lower_left_y + height * bottom / 100)
        pdf_page.cropbox.upper_right = (upper_right_x - width * right / 100, upper_right_y - height * top / 100)

    def _crop_image(self, image: Image.Image, page: dict[str, Any]) -> Image.Image:
        top, right, bottom, left = self._crop_values(page)
        if not any((top, right, bottom, left)):
            return image
        width, height = image.size
        crop_left = round(width * left / 100)
        crop_top = round(height * top / 100)
        crop_right = width - round(width * right / 100)
        crop_bottom = height - round(height * bottom / 100)
        if crop_right <= crop_left or crop_bottom <= crop_top:
            raise ValidationError("Orezanie by odstránilo celú obrazovú stranu.")
        return image.crop((crop_left, crop_top, crop_right, crop_bottom))

    @staticmethod
    def _image_dpi(project: dict[str, Any]) -> int:
        try:
            dpi = int(project.get("imageDpi", project.get("image_dpi", 144)))
        except (TypeError, ValueError):
            return 144
        return dpi if dpi in {144, 200, 300} else 144

    @staticmethod
    def _output_page_size(project: dict[str, Any]) -> tuple[float, float] | None:
        page_size = str(project.get("outputPageSize", project.get("output_page_size", "keep")))
        return A4_PAGE_SIZES.get(page_size)

    def _append_output_page(self, writer: PdfWriter, pdf_page: PageObject, project: dict[str, Any]) -> None:
        output_size = self._output_page_size(project)
        if not output_size:
            writer.add_page(pdf_page)
            return
        lower_left_x, lower_left_y = (float(value) for value in pdf_page.cropbox.lower_left)
        width = float(pdf_page.cropbox.width)
        height = float(pdf_page.cropbox.height)
        if width <= 0 or height <= 0:
            raise ValidationError("Strana má neplatné rozmery.")
        target_width, target_height = output_size
        scale = min(target_width / width, target_height / height)
        offset_x = (target_width - width * scale) / 2
        offset_y = (target_height - height * scale) / 2
        canvas = PageObject.create_blank_page(width=target_width, height=target_height)
        transform = Transformation().scale(scale).translate(
            offset_x - lower_left_x * scale,
            offset_y - lower_left_y * scale,
        )
        canvas.merge_transformed_page(pdf_page, transform, expand=False)
        writer.add_page(canvas)

    @staticmethod
    def _page_number_position(project: dict[str, Any]) -> str:
        position = str(project.get("pageNumberPosition", project.get("page_number_position", "none")))
        return position if position in {"bottom-left", "bottom-center", "bottom-right"} else "none"

    @staticmethod
    def _page_number_start(project: dict[str, Any]) -> int:
        try:
            number = int(project.get("pageNumberStart", project.get("page_number_start", 1)))
        except (TypeError, ValueError):
            return 1
        return min(1_000_000, max(1, number))

    def _append_page_number(self, page: PageObject, page_index: int, project: dict[str, Any]) -> None:
        position = self._page_number_position(project)
        if position == "none":
            return
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        if width <= 0 or height <= 0:
            return
        label = str(self._page_number_start(project) + page_index)
        overlay_data = io.BytesIO()
        overlay = Canvas(overlay_data, pagesize=(width, height), pageCompression=1)
        overlay.setFillColorRGB(0.18, 0.18, 0.18)
        overlay.setFont("Helvetica", 9)
        baseline = 16
        margin = 20
        if position == "bottom-left":
            overlay.drawString(margin, baseline, label)
        elif position == "bottom-right":
            overlay.drawRightString(width - margin, baseline, label)
        else:
            overlay.drawCentredString(width / 2, baseline, label)
        overlay.save()
        overlay_data.seek(0)
        page.merge_page(PdfReader(overlay_data).pages[0])

    @staticmethod
    def _rotate_pdf_page(page: Any, rotation: int) -> None:
        if not rotation:
            return
        if hasattr(page, "rotate"):
            page.rotate(rotation)
        else:
            page.rotate_clockwise(rotation)
        if hasattr(page, "transfer_rotation_to_content"):
            page.transfer_rotation_to_content()

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
    def _render_pdf_page(source: Path, page_number: int, destination: Path, *, scale_to: int = 340) -> None:
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
                    str(scale_to),
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
