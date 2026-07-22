from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import BinaryIO


MAX_UPLOAD_BYTES = 100 * 1024 * 1024
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

    def store_upload(self, stream: BinaryIO, filename: str, declared_mime: str = "") -> dict[str, str | int | bool]:
        original_name = Path(filename or "priloha").name[:240] or "priloha"
        temporary_path = self.tmp_dir / f"{uuid.uuid4().hex}.upload"
        digest = hashlib.sha256()
        size = 0
        try:
            with temporary_path.open("wb") as destination:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise UploadError("Súbor môže mať najviac 100 MB.")
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
