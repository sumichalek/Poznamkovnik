from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO

from .database import Database, ValidationError
from .files import BackgroundStore, FileStore


BACKUP_FORMAT = "poznamkovnik-backup"
BACKUP_FORMAT_VERSION = 1
MAX_BACKUP_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
MAX_BACKUP_CONTENT_BYTES = 2 * 1024 * 1024 * 1024
MAX_BACKUP_MEMBERS = 60_000
SNAPSHOT_RETENTION = 5
AUTOMATIC_BACKUP_POLL_SECONDS = 60
AUTOMATIC_BACKUP_RETRY_DELAY = timedelta(minutes=15)
LOW_DISK_SPACE_BYTES = 512 * 1024 * 1024


class BackupError(ValidationError):
    """Záložný archív nemá bezpečný alebo podporovaný tvar."""


@dataclass(frozen=True)
class BackupArtifact:
    identifier: str
    path: Path
    filename: str
    created_at: str
    temporary: bool


class BackupManager:
    def __init__(self, root: Path, database: Database, files: FileStore, backgrounds: BackgroundStore) -> None:
        self.root = root
        self.database = database
        self.files = files
        self.backgrounds = backgrounds
        self.tmp_dir = root / "tmp"
        self.snapshots_dir = root / "restore-snapshots"
        self.automatic_snapshots_dir = root / "automatic-snapshots"
        self._lock = threading.RLock()
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.automatic_snapshots_dir.mkdir(parents=True, exist_ok=True)

    def create_download(self, user_id: str, username: str) -> BackupArtifact:
        with self._lock:
            return self._create_archive(user_id, username)

    def restore_upload(self, user_id: str, username: str, stream: BinaryIO) -> dict[str, Any]:
        with self._lock:
            upload_path = self._temporary_path(".zip")
            staging_dir = Path(tempfile.mkdtemp(prefix="restore-", dir=self.tmp_dir))
            try:
                self._copy_stream(stream, upload_path, MAX_BACKUP_ARCHIVE_BYTES)
                snapshot, blob_paths, background_path = self._read_archive(upload_path, staging_dir)
                safety_copy = self._create_archive(user_id, username, directory=self._snapshot_directory(user_id))
                previous_background = self.database.background_preference(user_id)
                next_background = snapshot.get("preferences", {}).get("background_filename", "")

                self._install_blobs(blob_paths)
                self._install_background(user_id, background_path, snapshot)
                self.database.restore_backup_snapshot(user_id, snapshot)
                self._remove_replaced_background(user_id, previous_background, str(next_background))
                self._prune_snapshots(user_id)

                return {
                    "safetyBackup": {
                        "id": safety_copy.identifier,
                        "filename": safety_copy.filename,
                        "createdAt": safety_copy.created_at,
                    },
                    "counts": {
                        "libraries": len(snapshot.get("libraries", [])),
                        "sources": len(snapshot.get("sources", [])),
                        "musicTracks": len(snapshot.get("musicTracks", [])),
                        "tasks": len(snapshot.get("tasks", [])),
                        "calendarEvents": len(snapshot.get("calendarEvents", [])),
                    },
                }
            finally:
                upload_path.unlink(missing_ok=True)
                shutil.rmtree(staging_dir, ignore_errors=True)

    def preview_upload(self, user_id: str, stream: BinaryIO) -> dict[str, Any]:
        with self._lock:
            upload_path = self._temporary_path(".zip")
            try:
                self._copy_stream(stream, upload_path, MAX_BACKUP_ARCHIVE_BYTES)
                return self._preview_archive_for_user(user_id, upload_path)
            finally:
                upload_path.unlink(missing_ok=True)

    def preview_automatic_snapshot(self, user_id: str, snapshot_id: str) -> dict[str, Any]:
        with self._lock:
            path = self._snapshot_path(self._automatic_snapshot_directory(user_id), snapshot_id, "automatickej zálohy")
            return self._preview_archive_for_user(user_id, path)

    def verify_automatic_snapshot(self, user_id: str, snapshot_id: str) -> dict[str, Any]:
        with self._lock:
            directory = self._automatic_snapshot_directory(user_id)
            path = self._snapshot_path(directory, snapshot_id, "automatickej zálohy")
            verified_at = self._timestamp()
            try:
                preview = self._preview_archive_for_user(user_id, path)
                verification = {
                    "status": "verified",
                    "verifiedAt": verified_at,
                    "summary": preview["backup"],
                }
            except BackupError as error:
                verification = {"status": "error", "verifiedAt": verified_at, "error": str(error)}
                self._write_verification(directory, snapshot_id, verification)
                raise
            self._write_verification(directory, snapshot_id, verification)
            return verification

    def snapshot_for_download(self, user_id: str, snapshot_id: str) -> BackupArtifact:
        with self._lock:
            path = self._snapshot_path(self._snapshot_directory(user_id), snapshot_id, "ochrannej kópie")
            return BackupArtifact(snapshot_id, path, f"Poznamkovnik-ochranna-kopia-{snapshot_id}.zip", "", False)

    def automatic_overview(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            snapshots = []
            paths = self._automatic_snapshot_paths(user_id)
            directory = self._automatic_snapshot_directory(user_id)
            for path in paths:
                identifier = path.stem
                created_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat()
                snapshots.append(
                    {
                        "id": identifier,
                        "filename": f"Poznamkovnik-automaticka-zaloha-{identifier}.zip",
                        "createdAt": created_at,
                        "sizeBytes": path.stat().st_size,
                        "verification": self._read_verification(directory, identifier),
                    }
                )
            disk = shutil.disk_usage(self.root)
            return {
                "settings": self.database.automatic_backup_preferences(user_id),
                "snapshots": snapshots,
                "storage": {
                    "snapshotCount": len(paths),
                    "usedBytes": sum(path.stat().st_size for path in paths),
                    "freeBytes": disk.free,
                    "lowSpace": disk.free < LOW_DISK_SPACE_BYTES,
                },
            }

    def create_automatic_snapshot(self, user_id: str, username: str, retention_count: int) -> BackupArtifact:
        with self._lock:
            artifact = self._create_archive(user_id, username, directory=self._automatic_snapshot_directory(user_id))
            self.verify_automatic_snapshot(user_id, artifact.identifier)
            self._prune_automatic_snapshots(user_id, retention_count)
            return artifact

    def prune_automatic_snapshots(self, user_id: str, retention_count: int) -> None:
        with self._lock:
            self._prune_automatic_snapshots(user_id, retention_count)

    def automatic_snapshot_for_download(self, user_id: str, snapshot_id: str) -> BackupArtifact:
        with self._lock:
            path = self._snapshot_path(self._automatic_snapshot_directory(user_id), snapshot_id, "automatickej zálohy")
            return BackupArtifact(snapshot_id, path, f"Poznamkovnik-automaticka-zaloha-{snapshot_id}.zip", "", False)

    def restore_automatic_snapshot(self, user_id: str, username: str, snapshot_id: str) -> dict[str, Any]:
        with self._lock:
            path = self._snapshot_path(self._automatic_snapshot_directory(user_id), snapshot_id, "automatickej zálohy")
            with path.open("rb") as source:
                return self.restore_upload(user_id, username, source)

    def delete_automatic_snapshot(self, user_id: str, snapshot_id: str) -> None:
        with self._lock:
            directory = self._automatic_snapshot_directory(user_id)
            path = self._snapshot_path(directory, snapshot_id, "automatickej zálohy")
            path.unlink()
            self._verification_path(directory, snapshot_id).unlink(missing_ok=True)

    def discard_temporary(self, artifact: BackupArtifact) -> None:
        if artifact.temporary:
            artifact.path.unlink(missing_ok=True)

    def _create_archive(self, user_id: str, username: str, *, directory: Path | None = None) -> BackupArtifact:
        snapshot = self.database.backup_snapshot(user_id)
        self._prepare_background(snapshot, user_id)
        created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        timestamp = created_at.replace("+00:00", "Z").replace("-", "").replace(":", "")
        identifier = uuid.uuid4().hex
        username_label = self._filename_label(username)
        filename = f"Poznamkovnik-zaloha-{username_label}-{timestamp}.zip"
        if directory:
            path = directory / f"{identifier}.zip"
        else:
            path = self._temporary_path(".zip")

        manifest = {
            "format": BACKUP_FORMAT,
            "formatVersion": BACKUP_FORMAT_VERSION,
            "createdAt": created_at,
            "application": "Poznamkovnik",
        }
        blob_hashes = sorted(
            {
                str(row.get("blob_hash", ""))
                for key in ("sourceFiles", "musicTracks")
                for row in snapshot.get(key, [])
                if isinstance(row, dict)
            }
        )
        for blob_hash in blob_hashes:
            path_for_blob = self.files.path_for_hash(blob_hash)
            if not path_for_blob.is_file():
                raise BackupError("Zálohu nemožno vytvoriť, pretože chýba jedna z príloh.")

        try:
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, separators=(",", ":")))
                archive.writestr("data.json", json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")))
                for blob_hash in blob_hashes:
                    archive.write(self.files.path_for_hash(blob_hash), f"files/blobs/{blob_hash}")
                background_filename = str(snapshot.get("preferences", {}).get("background_filename", ""))
                if background_filename:
                    archive.write(self.backgrounds.path_for(user_id, background_filename), "background/custom")
        except Exception:
            path.unlink(missing_ok=True)
            raise

        return BackupArtifact(identifier, path, filename, created_at, directory is None)

    def _read_archive(self, archive_path: Path, staging_dir: Path) -> tuple[dict[str, Any], dict[str, Path], Path | None]:
        try:
            archive = zipfile.ZipFile(archive_path)
        except (OSError, zipfile.BadZipFile) as error:
            raise BackupError("Vybraný súbor nie je platná záloha Poznámkovníka.") from error

        with archive:
            members = archive.infolist()
            if len(members) > MAX_BACKUP_MEMBERS:
                raise BackupError("Záloha obsahuje príliš veľa súborov.")
            total_size = sum(member.file_size for member in members)
            if total_size > MAX_BACKUP_CONTENT_BYTES:
                raise BackupError("Rozbalená záloha je príliš veľká.")
            names = {member.filename for member in members}
            if "manifest.json" not in names or "data.json" not in names:
                raise BackupError("V zálohe chýbajú základné dáta.")
            if len(names) != len(members):
                raise BackupError("Záloha obsahuje duplicitné súbory.")
            if any(not self._safe_member_name(name) for name in names):
                raise BackupError("Záloha obsahuje neplatnú cestu k súboru.")

            manifest = self._read_json_member(archive, "manifest.json")
            if manifest.get("format") != BACKUP_FORMAT or manifest.get("formatVersion") != BACKUP_FORMAT_VERSION:
                raise BackupError("Táto verzia zálohy nie je podporovaná.")
            snapshot = self._read_json_member(archive, "data.json")
            if not isinstance(snapshot, dict):
                raise BackupError("Záloha neobsahuje platné dáta.")

            expected_blobs = self._snapshot_blob_hashes(snapshot)
            archive_blobs = {name.rsplit("/", 1)[-1] for name in names if name.startswith("files/blobs/")}
            if archive_blobs != expected_blobs:
                raise BackupError("Súbory príloh v zálohe nesúhlasia s jej dátami.")

            blob_paths: dict[str, Path] = {}
            blobs_dir = staging_dir / "blobs"
            blobs_dir.mkdir(parents=True, exist_ok=True)
            file_sizes = self._blob_sizes(snapshot)
            for blob_hash in expected_blobs:
                destination = blobs_dir / blob_hash
                self._extract_member(archive, f"files/blobs/{blob_hash}", destination, blob_hash, file_sizes.get(blob_hash, -1))
                blob_paths[blob_hash] = destination

            background_path = None
            preferences = snapshot.get("preferences")
            if not isinstance(preferences, dict):
                raise BackupError("Záloha neobsahuje platné nastavenia.")
            if preferences.get("background_filename"):
                if "background/custom" not in names:
                    raise BackupError("V zálohe chýba vlastné pozadie.")
                background_path = staging_dir / "background"
                self._extract_member(archive, "background/custom", background_path, "", -1)
                self._normalize_restored_background(snapshot, background_path)
            elif "background/custom" in names:
                raise BackupError("Záloha obsahuje neočakávané vlastné pozadie.")

        return snapshot, blob_paths, background_path

    def _preview_archive_for_user(self, user_id: str, archive_path: Path) -> dict[str, Any]:
        staging_dir = Path(tempfile.mkdtemp(prefix="backup-check-", dir=self.tmp_dir))
        try:
            snapshot, _, _ = self._read_archive(archive_path, staging_dir)
            return {
                "backup": self._snapshot_summary(snapshot),
                "current": self._snapshot_summary(self.database.backup_snapshot(user_id)),
            }
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

    def _snapshot_summary(self, snapshot: dict[str, Any]) -> dict[str, int]:
        def count(key: str) -> int:
            value = snapshot.get(key, [])
            return len(value) if isinstance(value, list) else 0

        elements = snapshot.get("elements", [])
        if not isinstance(elements, list):
            elements = []
        return {
            "libraries": count("libraries"),
            "folders": sum(1 for item in elements if isinstance(item, dict) and item.get("type") == "folder"),
            "notes": sum(1 for item in elements if isinstance(item, dict) and item.get("type") == "note"),
            "articles": sum(1 for item in elements if isinstance(item, dict) and item.get("type") == "article"),
            "sources": count("sources"),
            "files": len(self._snapshot_blob_hashes(snapshot)),
            "musicTracks": count("musicTracks"),
            "tasks": count("tasks"),
            "calendarEvents": count("calendarEvents"),
            "tutorialPages": count("tutorialPages"),
        }

    def _prepare_background(self, snapshot: dict[str, Any], user_id: str) -> None:
        preferences = snapshot.get("preferences")
        if not isinstance(preferences, dict):
            snapshot["preferences"] = {}
            return
        filename = str(preferences.get("background_filename", ""))
        if filename and not self.backgrounds.path_for(user_id, filename).is_file():
            preferences.update(
                {
                    "background_filename": "",
                    "background_mime_type": "",
                    "background_version": "",
                    "background_preset": "",
                }
            )

    def _install_blobs(self, blobs: dict[str, Path]) -> None:
        for blob_hash, source in blobs.items():
            destination = self.files.path_for_hash(blob_hash)
            if destination.is_file():
                if self._file_hash(destination) != blob_hash:
                    raise BackupError("Úložisko obsahuje poškodenú prílohu s rovnakým identifikátorom.")
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, destination)

    def _install_background(self, user_id: str, background_path: Path | None, snapshot: dict[str, Any]) -> None:
        if not background_path:
            return
        preferences = snapshot["preferences"]
        destination = self.backgrounds.path_for(user_id, str(preferences["background_filename"]))
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(background_path, destination)

    def _remove_replaced_background(self, user_id: str, previous: dict[str, Any], next_filename: str) -> None:
        previous_filename = str(previous.get("filename", "")) if previous.get("kind") == "custom" else ""
        if previous_filename and previous_filename != next_filename:
            self.backgrounds.delete(user_id, previous_filename)

    def _normalize_restored_background(self, snapshot: dict[str, Any], path: Path) -> None:
        digest = self._file_hash(path)
        with path.open("rb") as source:
            signature = source.read(16)
        mime_type, extension = self.backgrounds._image_type(signature)
        if not mime_type:
            raise BackupError("Vlastné pozadie v zálohe nie je podporovaný obrázok.")
        snapshot["preferences"].update(
            {
                "background_filename": f"background-{digest}{extension}",
                "background_mime_type": mime_type,
                "background_version": digest[:24],
                "background_preset": "",
            }
        )

    def _extract_member(
        self, archive: zipfile.ZipFile, name: str, destination: Path, expected_hash: str, expected_size: int
    ) -> None:
        digest = hashlib.sha256()
        size = 0
        with archive.open(name) as source, destination.open("wb") as target:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BACKUP_CONTENT_BYTES:
                    raise BackupError("Súbor v zálohe je príliš veľký.")
                digest.update(chunk)
                target.write(chunk)
        if expected_hash and digest.hexdigest() != expected_hash:
            raise BackupError("Kontrolný súčet prílohy v zálohe nesedí.")
        if expected_size >= 0 and size != expected_size:
            raise BackupError("Veľkosť prílohy v zálohe nesedí.")

    def _snapshot_blob_hashes(self, snapshot: dict[str, Any]) -> set[str]:
        result: set[str] = set()
        for key in ("sourceFiles", "musicTracks"):
            records = snapshot.get(key, [] if key == "musicTracks" else None)
            if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
                raise BackupError("Záloha nemá platný zoznam príloh.")
            for record in records:
                blob_hash = str(record.get("blob_hash", "")).lower()
                if len(blob_hash) != 64 or any(character not in "0123456789abcdef" for character in blob_hash):
                    raise BackupError("Záloha obsahuje neplatný kontrolný súčet prílohy.")
                result.add(blob_hash)
        return result

    def _blob_sizes(self, snapshot: dict[str, Any]) -> dict[str, int]:
        sizes: dict[str, int] = {}
        for key in ("sourceFiles", "musicTracks"):
            records = snapshot.get(key, [] if key == "musicTracks" else None)
            if not isinstance(records, list):
                raise BackupError("Záloha nemá platný zoznam príloh.")
            for record in records:
                if not isinstance(record, dict):
                    raise BackupError("Záloha nemá platný zoznam príloh.")
                blob_hash = str(record.get("blob_hash", "")).lower()
                try:
                    size = int(record.get("size_bytes", -1))
                except (TypeError, ValueError) as error:
                    raise BackupError("Príloha v zálohe nemá platnú veľkosť.") from error
                if size < 0:
                    raise BackupError("Príloha v zálohe nemá platnú veľkosť.")
                if blob_hash in sizes and sizes[blob_hash] != size:
                    raise BackupError("Záloha obsahuje nekonzistentnú prílohu.")
                sizes[blob_hash] = size
        return sizes

    @staticmethod
    def _read_json_member(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
        try:
            with archive.open(name) as source:
                value = json.load(source)
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise BackupError("Záloha obsahuje neplatné JSON dáta.") from error
        if not isinstance(value, dict):
            raise BackupError("Záloha obsahuje neplatné JSON dáta.")
        return value

    @staticmethod
    def _copy_stream(source: BinaryIO, destination: Path, maximum: int) -> None:
        size = 0
        try:
            with destination.open("wb") as target:
                while chunk := source.read(1024 * 1024):
                    size += len(chunk)
                    if size > maximum:
                        raise BackupError("Záložný archív je príliš veľký.")
                    target.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    @staticmethod
    def _safe_member_name(name: str) -> bool:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or name.endswith("/"):
            return False
        return name in {"manifest.json", "data.json", "background/custom"} or (
            name.startswith("files/blobs/") and len(path.parts) == 3
        )

    @staticmethod
    def _file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    def _snapshot_directory(self, user_id: str) -> Path:
        return self._user_directory(self.snapshots_dir, user_id)

    def _automatic_snapshot_directory(self, user_id: str) -> Path:
        return self._user_directory(self.automatic_snapshots_dir, user_id)

    @staticmethod
    def _user_directory(parent: Path, user_id: str) -> Path:
        safe_user_id = Path(user_id).name
        if safe_user_id != user_id:
            raise BackupError("Neplatný používateľ zálohy.")
        path = parent / safe_user_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _snapshot_path(self, directory: Path, snapshot_id: str, label: str) -> Path:
        if not snapshot_id or Path(snapshot_id).name != snapshot_id or not snapshot_id.isalnum():
            raise BackupError(f"Neplatný identifikátor {label}.")
        path = directory / f"{snapshot_id}.zip"
        if not path.is_file():
            raise KeyError(f"{label.capitalize()} sa nenašla.")
        return path

    def _prune_snapshots(self, user_id: str) -> None:
        snapshots = sorted(self._snapshot_directory(user_id).glob("*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in snapshots[SNAPSHOT_RETENTION:]:
            path.unlink(missing_ok=True)

    def _automatic_snapshot_paths(self, user_id: str) -> list[Path]:
        return sorted(
            self._automatic_snapshot_directory(user_id).glob("*.zip"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    def _prune_automatic_snapshots(self, user_id: str, retention_count: int) -> None:
        for path in self._automatic_snapshot_paths(user_id)[max(1, retention_count):]:
            path.unlink(missing_ok=True)
            self._verification_path(path.parent, path.stem).unlink(missing_ok=True)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @staticmethod
    def _verification_path(directory: Path, snapshot_id: str) -> Path:
        return directory / f"{snapshot_id}.verification.json"

    def _read_verification(self, directory: Path, snapshot_id: str) -> dict[str, Any] | None:
        path = self._verification_path(directory, snapshot_id)
        try:
            with path.open("r", encoding="utf-8") as source:
                value = json.load(source)
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(value, dict) or value.get("status") not in {"verified", "error"}:
            return None
        return value

    def _write_verification(self, directory: Path, snapshot_id: str, verification: dict[str, Any]) -> None:
        destination = self._verification_path(directory, snapshot_id)
        temporary = destination.with_suffix(".tmp")
        try:
            temporary.write_text(json.dumps(verification, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    def _temporary_path(self, suffix: str) -> Path:
        descriptor, filename = tempfile.mkstemp(prefix="backup-", suffix=suffix, dir=self.tmp_dir)
        os.close(descriptor)
        return Path(filename)

    @staticmethod
    def _filename_label(username: str) -> str:
        label = "".join(character if character.isalnum() else "-" for character in username).strip("-")
        return label[:48] or "pouzivatel"


class AutomaticBackupScheduler:
    def __init__(self, database: Database, backups: BackupManager, *, poll_seconds: int = AUTOMATIC_BACKUP_POLL_SECONDS) -> None:
        self.database = database
        self.backups = backups
        self.poll_seconds = poll_seconds
        self._stop_event = threading.Event()
        self._run_lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="automatic-backups", daemon=True)
        self._thread.start()

    def run_once(self) -> None:
        if not self._run_lock.acquire(blocking=False):
            return
        try:
            now = datetime.now(timezone.utc)
            for user in self.database.automatic_backup_candidates():
                if not bool(user.get("automatic_backup_enabled", True)):
                    continue
                interval_hours = int(user.get("automatic_backup_interval_hours", 24))
                if interval_hours not in {6, 24, 168}:
                    interval_hours = 24
                if not self._backup_is_due(user, now, interval_hours):
                    continue
                try:
                    retention_count = max(3, min(50, int(user.get("automatic_backup_retention_count", 14))))
                    self.backups.create_automatic_snapshot(user["id"], user["username"], retention_count)
                    self.database.record_automatic_backup_result(user["id"], succeeded=True)
                except Exception as error:  # Keep the server running even when a background backup cannot be made.
                    try:
                        self.database.record_automatic_backup_result(user["id"], succeeded=False, error=str(error))
                    except Exception:
                        continue
        finally:
            self._run_lock.release()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.run_once()
            self._stop_event.wait(self.poll_seconds)

    @staticmethod
    def _backup_is_due(user: dict[str, Any], now: datetime, interval_hours: int) -> bool:
        previous = AutomaticBackupScheduler._parse_timestamp(user.get("last_auto_backup_at"))
        if previous and now - previous < timedelta(hours=interval_hours):
            return False
        last_attempt = AutomaticBackupScheduler._parse_timestamp(user.get("last_auto_backup_attempt_at"))
        return not last_attempt or now - last_attempt >= min(AUTOMATIC_BACKUP_RETRY_DELAY, timedelta(hours=interval_hours))

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
