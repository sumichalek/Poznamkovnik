from __future__ import annotations

import hashlib
import mimetypes
import os
import uuid
from pathlib import Path
from typing import BinaryIO


MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_BACKGROUND_BYTES = 12 * 1024 * 1024
INLINE_MIME_TYPES = {"application/pdf", "text/plain", "text/markdown"}


class UploadError(ValueError):
    """Nahrávaný súbor nevyhovuje limitom."""


class FileStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.blobs_dir = root / "blobs"
        self.tmp_dir = root / "tmp"
        self.blobs_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def store_upload(
        self,
        stream: BinaryIO,
        filename: str,
        declared_mime: str = "",
        *,
        maximum_bytes: int = MAX_UPLOAD_BYTES,
    ) -> dict[str, str | int | bool]:
        original_name = Path(filename or "priloha").name[:240] or "priloha"
        temporary_path = self.tmp_dir / f"{uuid.uuid4().hex}.upload"
        digest = hashlib.sha256()
        size = 0
        try:
            with temporary_path.open("wb") as destination:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > maximum_bytes:
                        maximum_megabytes = maximum_bytes / (1024 * 1024)
                        label = f"{maximum_megabytes:g} MB"
                        raise UploadError(f"Súbor presahuje nastavený limit {label}.")
                    digest.update(chunk)
                    destination.write(chunk)
            blob_hash = digest.hexdigest()
            destination_path = self.path_for_hash(blob_hash)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            created = not destination_path.exists()
            if not created:
                temporary_path.unlink(missing_ok=True)
            else:
                os.replace(temporary_path, destination_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

        guessed_mime, _ = mimetypes.guess_type(original_name)
        mime_type = guessed_mime or declared_mime or "application/octet-stream"
        return {
            "blobHash": blob_hash,
            "originalName": original_name,
            "mimeType": mime_type.split(";", 1)[0].strip().lower(),
            "sizeBytes": size,
            "created": created,
        }

    def path_for_hash(self, blob_hash: str) -> Path:
        return self.blobs_dir / blob_hash[:2] / blob_hash

    def delete_blob(self, blob_hash: str) -> None:
        path = self.path_for_hash(blob_hash)
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass

    @staticmethod
    def can_preview_inline(mime_type: str) -> bool:
        return mime_type in INLINE_MIME_TYPES or mime_type.startswith("image/") and mime_type != "image/svg+xml"


class BackgroundStore:
    """Súkromné úložisko jednej overenej fotografie pre každý účet."""

    _IMAGE_SIGNATURES = (
        (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
        (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
        (b"GIF87a", "image/gif", ".gif"),
        (b"GIF89a", "image/gif", ".gif"),
    )

    def __init__(self, root: Path) -> None:
        self.root = root
        self.tmp_dir = root / "tmp"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def store_upload(self, user_id: str, stream: BinaryIO) -> dict[str, str | bool]:
        temporary_path = self.tmp_dir / f"{uuid.uuid4().hex}.upload"
        digest = hashlib.sha256()
        size = 0
        try:
            with temporary_path.open("wb") as destination:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_BACKGROUND_BYTES:
                        raise UploadError("Fotografia môže mať najviac 12 MB.")
                    digest.update(chunk)
                    destination.write(chunk)

            with temporary_path.open("rb") as uploaded:
                signature = uploaded.read(16)
            mime_type, extension = self._image_type(signature)
            if not mime_type:
                raise UploadError("Vyber fotografiu vo formáte JPEG, PNG, WebP alebo GIF.")

            blob_hash = digest.hexdigest()
            filename = f"background-{blob_hash}{extension}"
            destination_path = self.path_for(user_id, filename)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            created = not destination_path.exists()
            if created:
                os.replace(temporary_path, destination_path)
            else:
                temporary_path.unlink(missing_ok=True)
            return {
                "filename": filename,
                "mimeType": mime_type,
                "version": blob_hash[:24],
                "created": created,
            }
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    def path_for(self, user_id: str, filename: str) -> Path:
        safe_user_id = Path(user_id).name
        safe_filename = Path(filename).name
        if safe_user_id != user_id or safe_filename != filename:
            raise UploadError("Neplatná cesta k fotografii.")
        return self.root / safe_user_id / safe_filename

    def delete(self, user_id: str, filename: str) -> None:
        path = self.path_for(user_id, filename)
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass

    @classmethod
    def _image_type(cls, signature: bytes) -> tuple[str, str]:
        for prefix, mime_type, extension in cls._IMAGE_SIGNATURES:
            if signature.startswith(prefix):
                return mime_type, extension
        if signature.startswith(b"RIFF") and signature[8:12] == b"WEBP":
            return "image/webp", ".webp"
        return "", ""
