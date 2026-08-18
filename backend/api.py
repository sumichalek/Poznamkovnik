from __future__ import annotations

import json
import mimetypes
import tempfile
import uuid
from dataclasses import dataclass
from email.message import Message
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import parse_qs, urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .audio_metadata import read_audio_metadata
from .auth import AuthError, AuthService, SESSION_DAYS
from .backups import AutomaticBackupScheduler, BackupArtifact, BackupManager, MAX_BACKUP_ARCHIVE_BYTES
from .code_runner import CCodeRunner, CodeRunnerError
from .database import Database, ValidationError
from .files import BackgroundStore, FileStore, MAX_BACKGROUND_BYTES, UploadError
from .podcast import PodcastFeedError, fetch_podcast_feed
from .radio_recording import RadioRecordingManager
from .radio_schedule import RadioRecordingScheduler


MAX_MULTIPART_HEADER_BYTES = 64 * 1024
MULTIPART_CHUNK_BYTES = 64 * 1024
MULTIPART_MEMORY_THRESHOLD = 2 * 1024 * 1024
MUSIC_FILE_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".oga", ".ogg", ".opus", ".wav", ".weba", ".webm"}
RADIO_STREAM_TIMEOUT_SECONDS = 20
RADIO_STREAM_CHUNK_BYTES = 64 * 1024


@dataclass
class UploadedFile:
    filename: str
    file: BinaryIO
    mime_type: str


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class AppContext:
    def __init__(self, base_dir: Path, data_dir: Path) -> None:
        self.base_dir = base_dir
        self.data_dir = data_dir
        self.database = Database(data_dir / "poznamkovnik.sqlite3")
        self.database.initialize()
        self.auth = AuthService(self.database)
        self.files = FileStore(data_dir / "files")
        self.backgrounds = BackgroundStore(data_dir / "backgrounds")
        self.backups = BackupManager(data_dir / "backups", self.database, self.files, self.backgrounds)
        self.radio_recordings = RadioRecordingManager(data_dir / "radio-recordings", self.database)
        self.radio_schedules = RadioRecordingScheduler(self.database, self.radio_recordings)
        self.radio_schedules.start()
        self.automatic_backups = AutomaticBackupScheduler(self.database, self.backups)
        self.automatic_backups.start()
        self.c_runner = CCodeRunner()


class AppHandler(SimpleHTTPRequestHandler):
    server_version = "Poznamkovnik/1.0"
    context: AppContext

    def __init__(self, *args: Any, context: AppContext, **kwargs: Any) -> None:
        self.context = context
        self._response_cookies: list[str] = []
        super().__init__(*args, directory=context.base_dir, **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self._is_api_request():
            self._handle_api("GET")
            return
        if self._is_private_static_path():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802
        if self._is_api_request():
            self._handle_api("HEAD")
            return
        if self._is_private_static_path():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        super().do_HEAD()

    def do_POST(self) -> None:  # noqa: N802
        if self._is_api_request():
            self._handle_api("POST")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:  # noqa: N802
        if self._is_api_request():
            self._handle_api("PUT")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:  # noqa: N802
        if self._is_api_request():
            self._handle_api("PATCH")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:  # noqa: N802
        if self._is_api_request():
            self._handle_api("DELETE")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _is_api_request(self) -> bool:
        return urlsplit(self.path).path.startswith("/api/")

    def _is_private_static_path(self) -> bool:
        path = urlsplit(self.path).path
        parts = [part for part in Path(path).parts if part not in {"/", "."}]
        blocked = {".git", ".local", "data", "backend", "node_modules", "__pycache__", ".agents", ".codex"}
        return any(part in blocked or part.startswith(".") for part in parts)

    def _handle_api(self, method: str) -> None:
        try:
            result = self._route_api(method)
            if result is not None:
                self._write_json(HTTPStatus.OK, result)
        except ApiError as error:
            self._write_json(error.status, {"error": error.message})
        except (ValidationError, UploadError, CodeRunnerError, PodcastFeedError) as error:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except AuthError as error:
            self._write_json(HTTPStatus.UNAUTHORIZED, {"error": str(error)})
        except KeyError as error:
            self._write_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
        except json.JSONDecodeError:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "Neplatné JSON dáta."})

    def _route_api(self, method: str) -> dict[str, Any] | None:
        request_url = urlsplit(self.path)
        segments = [part for part in request_url.path.split("/") if part]
        if len(segments) < 2:
            raise ApiError(HTTPStatus.NOT_FOUND, "Neznáme API.")
        route = segments[1:]

        if route == ["auth", "status"] and method == "GET":
            user = self.context.auth.session_user(self._session_token())
            return {"authenticated": bool(user), "needsSetup": self.context.database.user_count() == 0, "user": user}
        if route == ["auth", "setup"] and method == "POST":
            data = self._read_json()
            try:
                user, token = self.context.auth.setup(data.get("username"), data.get("password"))
            except AuthError as error:
                if self.context.database.user_count() > 0:
                    raise ApiError(HTTPStatus.CONFLICT, str(error)) from error
                raise
            self._set_session_cookie(token)
            self.context.automatic_backups.run_once()
            return {"authenticated": True, "needsSetup": False, "user": user}
        if route == ["auth", "login"] and method == "POST":
            data = self._read_json()
            user, token = self.context.auth.login(data.get("username"), data.get("password"))
            self._set_session_cookie(token)
            return {"authenticated": True, "needsSetup": False, "user": user}
        if route == ["auth", "logout"] and method == "POST":
            self.context.auth.logout(self._session_token())
            self._clear_session_cookie()
            return {"authenticated": False}
        if route == ["auth", "activity"] and method == "POST":
            user = self.context.auth.touch_session(self._session_token())
            if not user:
                self._clear_session_cookie()
                raise ApiError(HTTPStatus.UNAUTHORIZED, "Pracovná plocha je zamknutá.")
            return {"authenticated": True, "user": user}

        user = self._require_user()
        if route == ["auth", "security"] and method == "GET":
            return self.context.database.security_preferences(user["id"])
        if route == ["auth", "security"] and method == "POST":
            preferences = self.context.database.save_security_preferences(user["id"], self._read_json())
            self.context.auth.mark_session_active(self._session_token())
            return preferences
        if route == ["auth", "password"] and method == "POST":
            data = self._read_json()
            next_password = data.get("newPassword")
            if next_password != data.get("newPasswordConfirmation"):
                raise ApiError(HTTPStatus.BAD_REQUEST, "Nové heslá sa nezhodujú.")
            user, token = self.context.auth.change_password(user["id"], data.get("currentPassword"), next_password)
            self._set_session_cookie(token)
            return {"authenticated": True, "user": user, "sessionsRevoked": True}
        if route == ["tags"] and method == "GET":
            query = parse_qs(request_url.query).get("q", [""])[0]
            return {"tags": self.context.database.list_tags(user["id"], query)}
        if route == ["search"] and method == "GET":
            query = parse_qs(request_url.query).get("q", [""])[0]
            return {"results": self.context.database.global_search(user["id"], query)}
        if route == ["backups"] and method == "GET":
            return self.context.backups.automatic_overview(user["id"])
        if route == ["backups", "settings"] and method == "POST":
            settings = self.context.database.save_automatic_backup_preferences(user["id"], self._read_json())
            self.context.backups.prune_automatic_snapshots(user["id"], settings["retentionCount"])
            self.context.automatic_backups.run_once()
            return {"settings": settings}
        if route == ["backups", "export"] and method == "GET":
            archive = self.context.backups.create_download(user["id"], user["username"])
            self._send_backup_archive(archive)
            return None
        if route == ["backups", "preview"] and method == "POST":
            uploaded = self._read_upload(MAX_BACKUP_ARCHIVE_BYTES + 512 * 1024)
            try:
                return self.context.backups.preview_upload(user["id"], uploaded.file)
            finally:
                uploaded.file.close()
        if route == ["backups", "restore"] and method == "POST":
            uploaded = self._read_upload(MAX_BACKUP_ARCHIVE_BYTES + 512 * 1024)
            try:
                return self.context.backups.restore_upload(user["id"], user["username"], uploaded.file)
            finally:
                uploaded.file.close()
        if len(route) == 5 and route[:3] == ["backups", "snapshots", "automatic"] and route[4] == "preview" and method == "POST":
            return self.context.backups.preview_automatic_snapshot(user["id"], route[3])
        if len(route) == 5 and route[:3] == ["backups", "snapshots", "automatic"] and route[4] == "verify" and method == "POST":
            return self.context.backups.verify_automatic_snapshot(user["id"], route[3])
        if len(route) == 5 and route[:3] == ["backups", "snapshots", "automatic"] and route[4] == "restore" and method == "POST":
            return self.context.backups.restore_automatic_snapshot(user["id"], user["username"], route[3])
        if len(route) == 4 and route[:3] == ["backups", "snapshots", "automatic"] and method == "GET":
            archive = self.context.backups.automatic_snapshot_for_download(user["id"], route[3])
            self._send_backup_archive(archive)
            return None
        if len(route) == 4 and route[:3] == ["backups", "snapshots", "automatic"] and method == "DELETE":
            self.context.backups.delete_automatic_snapshot(user["id"], route[3])
            return {"deleted": True}
        if len(route) == 3 and route[:2] == ["backups", "snapshots"] and method == "GET":
            archive = self.context.backups.snapshot_for_download(user["id"], route[2])
            self._send_backup_archive(archive)
            return None
        if route == ["preferences"] and method == "GET":
            return self.context.database.preferences(user["id"])
        if route == ["preferences"] and method == "POST":
            return self.context.database.save_preferences(user["id"], self._read_json())
        if route == ["preferences", "background", "preset"] and method == "POST":
            data = self._read_json()
            previous = self.context.database.save_background_preset(user["id"], str(data.get("presetId", "")))
            if previous.get("kind") == "custom" and previous.get("filename"):
                self.context.backgrounds.delete(user["id"], str(previous["filename"]))
            return {"background": self.context.database.background_preference(user["id"])}
        if route == ["preferences", "background"] and method == "POST":
            uploaded = self._read_upload(MAX_BACKGROUND_BYTES + 512 * 1024)
            try:
                background = self.context.backgrounds.store_upload(user["id"], uploaded.file)
                try:
                    previous = self.context.database.save_background_preference(
                        user["id"],
                        str(background["filename"]),
                        str(background["mimeType"]),
                        str(background["version"]),
                    )
                except Exception:
                    if background["created"]:
                        self.context.backgrounds.delete(user["id"], str(background["filename"]))
                    raise
                if previous.get("filename") and previous["filename"] != background["filename"]:
                    self.context.backgrounds.delete(user["id"], str(previous["filename"]))
                return {"background": self.context.database.background_preference(user["id"])}
            finally:
                uploaded.file.close()
        if route == ["preferences", "background"] and method == "DELETE":
            previous = self.context.database.clear_background_preference(user["id"])
            if previous.get("filename"):
                self.context.backgrounds.delete(user["id"], str(previous["filename"]))
            return {"background": self.context.database.background_preference(user["id"])}
        if route == ["preferences", "background"] and method in {"GET", "HEAD"}:
            self._send_background(user["id"], head_only=method == "HEAD")
            return None
        if route == ["workspace"] and method == "GET":
            return self.context.database.read_workspace(user["id"])
        if route == ["workspace"] and method == "PUT":
            return self.context.database.replace_workspace(user["id"], self._read_json())

        if route == ["tutorial", "runtime"] and method == "GET":
            return self.context.c_runner.status()
        if route == ["tutorial", "languages"] and method == "GET":
            return {"languages": self.context.database.list_tutorial_languages(user["id"])}
        if len(route) == 3 and route[:2] == ["tutorial", "languages"] and method == "GET":
            return self.context.database.tutorial_language_detail(user["id"], route[2])
        if len(route) == 4 and route[:2] == ["tutorial", "languages"] and route[3] == "pages" and method == "POST":
            data = self._read_json()
            data.setdefault("id", str(uuid.uuid4()))
            return {"page": self.context.database.create_tutorial_page(user["id"], route[2], data)}
        if len(route) == 4 and route[:2] == ["tutorial", "pages"] and route[3] == "note" and method == "PUT":
            return {"note": self.context.database.save_tutorial_note(user["id"], route[2], self._read_json())}
        if len(route) == 4 and route[:2] == ["tutorial", "examples"] and route[3] == "draft" and method == "PUT":
            return {"draft": self.context.database.save_tutorial_example_draft(user["id"], route[2], self._read_json())}
        if len(route) == 4 and route[:2] == ["tutorial", "examples"] and route[3] == "run" and method == "POST":
            example = self.context.database.tutorial_example(user["id"], route[2])
            data = self._read_json()
            source = data.get("source", example["source"])
            stdin = data.get("stdin", example["stdin"])
            standard = data.get("standard", example["standard"])
            return self.context.c_runner.run(source, stdin, standard)

        if route == ["tasks"] and method == "GET":
            status = parse_qs(request_url.query).get("status", [""])[0]
            return {"tasks": self.context.database.list_tasks(user["id"], status)}
        if route == ["tasks"] and method == "POST":
            data = self._read_json()
            data.setdefault("id", str(uuid.uuid4()))
            return {"task": self.context.database.create_task(user["id"], data)}
        if route == ["relationship-targets"] and method == "GET":
            return {"targets": self.context.database.semantic_targets(user["id"])}
        if len(route) == 3 and route[0] == "semantic-links" and method == "GET":
            return {"links": self.context.database.semantic_links_for_target(user["id"], route[1], route[2])}
        if len(route) == 3 and route[0] == "semantic-links" and method == "POST":
            return {"target": self.context.database.create_semantic_link(user["id"], route[1], route[2], self._read_json())}
        if len(route) == 2 and route[0] == "semantic-links" and method == "PATCH":
            self.context.database.update_semantic_link(user["id"], route[1], self._read_json())
            return {"ok": True}
        if len(route) == 2 and route[0] == "semantic-links" and method == "DELETE":
            self.context.database.delete_semantic_link(user["id"], route[1])
            return {"ok": True}
        if len(route) == 3 and route[0] == "relationships" and method == "GET":
            return {"overview": self.context.database.relationship_overview(user["id"], route[1], route[2])}
        if len(route) == 3 and route[0] == "task-links" and method == "GET":
            return {"tasks": self.context.database.tasks_for_target(user["id"], route[1], route[2])}
        if len(route) == 3 and route[0] == "calendar-event-links" and method == "GET":
            return {"events": self.context.database.calendar_events_for_target(user["id"], route[1], route[2])}
        if len(route) >= 2 and route[0] == "tasks":
            return self._route_task(method, user["id"], route)

        if route == ["calendar-events"] and method == "GET":
            query = parse_qs(request_url.query)
            return {
                "events": self.context.database.list_calendar_events(
                    user["id"], query.get("from", [""])[0], query.get("to", [""])[0]
                )
            }
        if route == ["calendar-events"] and method == "POST":
            data = self._read_json()
            data.setdefault("id", str(uuid.uuid4()))
            return {"event": self.context.database.create_calendar_event(user["id"], data)}
        if len(route) >= 2 and route[0] == "calendar-events":
            return self._route_calendar_event(method, user["id"], route)

        if route == ["music"] and method == "GET":
            return self.context.database.music_library(user["id"])
        if route == ["music", "tracks"] and method == "POST":
            maximum = self.context.database.music_track_max_bytes(user["id"])
            uploaded = self._read_upload(maximum + 512 * 1024)
            try:
                file_info = self.context.files.store_upload(
                    uploaded.file,
                    uploaded.filename,
                    uploaded.mime_type,
                    maximum_bytes=maximum,
                )
                if not self._is_audio_upload(file_info):
                    if file_info["created"]:
                        self.context.files.delete_blob(str(file_info["blobHash"]))
                    raise ValidationError("Vyber zvukový súbor vo formáte MP3, OGG, WAV, M4A, FLAC, AAC alebo WebM.")
                try:
                    metadata = read_audio_metadata(self.context.files.path_for_hash(str(file_info["blobHash"])))
                    library = self.context.database.add_music_track(user["id"], str(uuid.uuid4()), file_info, metadata)
                except Exception:
                    if file_info["created"]:
                        self.context.files.delete_blob(str(file_info["blobHash"]))
                    raise
                return library
            finally:
                uploaded.file.close()
        if route == ["music", "playlists"] and method == "POST":
            data = self._read_json()
            data.setdefault("id", str(uuid.uuid4()))
            return self.context.database.create_music_playlist(user["id"], data)
        if route == ["music", "stations"] and method == "POST":
            data = self._read_json()
            data.setdefault("id", str(uuid.uuid4()))
            return self.context.database.create_radio_station(user["id"], data)
        if route == ["music", "podcasts"] and method == "POST":
            data = self._read_json()
            feed = fetch_podcast_feed(data.get("feedUrl"))
            return self.context.database.create_podcast_feed(user["id"], str(uuid.uuid4()), feed)
        if len(route) >= 2 and route[0] == "music":
            return self._route_music(method, user["id"], route)

        if route == ["sources"] and method == "GET":
            query = parse_qs(request_url.query).get("q", [""])[0]
            return {"sources": self.context.database.list_sources(user["id"], query)}
        if route == ["sources"] and method == "POST":
            data = self._read_json()
            data.setdefault("id", str(uuid.uuid4()))
            return {"source": self.context.database.create_source(user["id"], data)}

        if route == ["source-collections"] and method == "GET":
            return {"collections": self.context.database.list_source_collections(user["id"])}
        if route == ["source-collections"] and method == "POST":
            data = self._read_json()
            data.setdefault("id", str(uuid.uuid4()))
            return self.context.database.create_source_collection(user["id"], data)

        if len(route) >= 2 and route[0] == "sources":
            return self._route_source(method, user["id"], route)
        if len(route) >= 2 and route[0] == "source-collections":
            return self._route_source_collection(method, user["id"], route)
        if len(route) == 2 and route[0] == "files" and method in {"GET", "HEAD"}:
            self._send_file(
                user["id"],
                route[1],
                parse_qs(request_url.query).get("download", [""])[0] == "1",
                head_only=method == "HEAD",
            )
            return None
        if len(route) == 3 and route[0] == "elements" and route[2] == "sources" and method == "GET":
            return {"sources": self.context.database.sources_for_element(user["id"], route[1])}
        if len(route) == 3 and route[0] == "libraries" and route[2] == "sources" and method == "GET":
            return {"sources": self.context.database.sources_for_library(user["id"], route[1])}
        raise ApiError(HTTPStatus.NOT_FOUND, "Neznáme API.")

    def _route_task(self, method: str, user_id: str, route: list[str]) -> dict[str, Any]:
        task_id = route[1]
        if len(route) == 2:
            if method == "GET":
                return {"task": self.context.database.task_detail(user_id, task_id)}
            if method == "PATCH":
                return {"task": self.context.database.update_task(user_id, task_id, self._read_json())}
            if method == "DELETE":
                self.context.database.delete_task(user_id, task_id)
                return {"deleted": True}
        if len(route) == 3 and route[2] == "links" and method == "POST":
            data = self._read_json()
            data.setdefault("id", str(uuid.uuid4()))
            return {"task": self.context.database.link_task(user_id, task_id, data)}
        if len(route) == 4 and route[2] == "links" and method == "DELETE":
            return {"task": self.context.database.unlink_task(user_id, task_id, route[3])}
        raise ApiError(HTTPStatus.NOT_FOUND, "Neznámy endpoint úloh.")

    def _route_calendar_event(self, method: str, user_id: str, route: list[str]) -> dict[str, Any]:
        event_id = route[1]
        if len(route) == 2:
            if method == "GET":
                return {"event": self.context.database.calendar_event_detail(user_id, event_id)}
            if method == "PATCH":
                return {"event": self.context.database.update_calendar_event(user_id, event_id, self._read_json())}
            if method == "DELETE":
                self.context.database.delete_calendar_event(user_id, event_id)
                return {"deleted": True}
        if len(route) == 3 and route[2] == "links" and method == "POST":
            data = self._read_json()
            data.setdefault("id", str(uuid.uuid4()))
            return {"event": self.context.database.link_calendar_event(user_id, event_id, data)}
        if len(route) == 4 and route[2] == "links" and method == "DELETE":
            return {"event": self.context.database.unlink_calendar_event(user_id, event_id, route[3])}
        raise ApiError(HTTPStatus.NOT_FOUND, "Neznámy endpoint kalendára.")

    def _route_music(self, method: str, user_id: str, route: list[str]) -> dict[str, Any] | None:
        if len(route) == 4 and route[1] == "tracks" and route[3] == "audio" and method in {"GET", "HEAD"}:
            self._send_music_track(user_id, route[2], head_only=method == "HEAD")
            return None
        if len(route) == 4 and route[1] == "stations" and route[3] == "stream" and method in {"GET", "HEAD"}:
            self._send_radio_station_stream(user_id, route[2], head_only=method == "HEAD")
            return None
        if len(route) == 4 and route[1] == "recordings" and route[3] == "file" and method in {"GET", "HEAD"}:
            download = parse_qs(urlsplit(self.path).query).get("download", [""])[0] == "1"
            self._send_radio_recording(user_id, route[2], download=download, head_only=method == "HEAD")
            return None
        if len(route) == 4 and route[1] == "stations" and route[3] == "recordings" and method == "POST":
            return self.context.radio_recordings.start(user_id, route[2])
        if len(route) == 4 and route[1] == "stations" and route[3] == "recording-schedules" and method == "POST":
            data = self._read_json()
            data.setdefault("id", str(uuid.uuid4()))
            return self.context.database.create_radio_recording_schedule(user_id, route[2], data)
        if len(route) == 4 and route[1] == "recording-schedules" and route[3] == "cancel" and method == "POST":
            return self.context.database.cancel_radio_recording_schedule(user_id, route[2])
        if len(route) == 4 and route[1] == "recording-schedules" and route[3] == "pause" and method == "POST":
            return self.context.database.pause_radio_recording_schedule(user_id, route[2])
        if len(route) == 4 and route[1] == "recording-schedules" and route[3] == "resume" and method == "POST":
            return self.context.database.resume_radio_recording_schedule(user_id, route[2])
        if len(route) == 4 and route[1] == "recordings" and route[3] == "stop" and method == "POST":
            return self.context.radio_recordings.stop(user_id, route[2])
        if len(route) == 3 and route[1] == "recordings" and method == "DELETE":
            return self.context.radio_recordings.delete(user_id, route[2])
        if len(route) == 3 and route[1] == "recording-schedules" and method == "DELETE":
            return self.context.database.delete_radio_recording_schedule(user_id, route[2])
        if len(route) == 3 and route[1] == "tracks":
            if method == "PATCH":
                return self.context.database.update_music_track(user_id, route[2], self._read_json())
            if method == "DELETE":
                library, orphaned_blob = self.context.database.delete_music_track(user_id, route[2])
                if orphaned_blob:
                    self.context.files.delete_blob(orphaned_blob)
                return library
        if len(route) == 3 and route[1] == "playlists":
            if method == "PATCH":
                return self.context.database.update_music_playlist(user_id, route[2], self._read_json())
            if method == "DELETE":
                return self.context.database.delete_music_playlist(user_id, route[2])
        if len(route) == 3 and route[1] == "stations":
            if method == "PATCH":
                return self.context.database.update_radio_station(user_id, route[2], self._read_json())
            if method == "DELETE":
                return self.context.database.delete_radio_station(user_id, route[2])
        if len(route) == 4 and route[1] == "podcasts" and route[3] == "refresh" and method == "POST":
            feed_url = self.context.database.podcast_feed_url(user_id, route[2])
            return self.context.database.refresh_podcast_feed(user_id, route[2], fetch_podcast_feed(feed_url))
        if len(route) == 3 and route[1] == "podcasts" and method == "DELETE":
            return self.context.database.delete_podcast_feed(user_id, route[2])
        if len(route) == 4 and route[1] == "playlists" and route[3] == "order" and method == "PUT":
            return self.context.database.reorder_music_playlist(user_id, route[2], self._read_json())
        if len(route) == 5 and route[1] == "playlists" and route[3] == "tracks":
            if method == "PUT":
                return self.context.database.add_music_playlist_track(user_id, route[2], route[4])
            if method == "DELETE":
                return self.context.database.remove_music_playlist_track(user_id, route[2], route[4])
        raise ApiError(HTTPStatus.NOT_FOUND, "Neznámy hudobný endpoint.")

    def _route_source(self, method: str, user_id: str, route: list[str]) -> dict[str, Any]:
        source_id = route[1]
        if len(route) == 2:
            if method == "GET":
                return {"source": self.context.database.source_detail(user_id, source_id)}
            if method == "PATCH":
                return {"source": self.context.database.update_source(user_id, source_id, self._read_json())}
            if method == "DELETE":
                for blob_hash in self.context.database.delete_source(user_id, source_id):
                    self.context.files.delete_blob(blob_hash)
                return {"deleted": True}

        if len(route) == 3 and route[2] == "files" and method == "POST":
            maximum = self.context.database.source_file_max_bytes(user_id)
            uploaded = self._read_upload(maximum + 512 * 1024)
            try:
                file_info = self.context.files.store_upload(
                    uploaded.file,
                    uploaded.filename,
                    uploaded.mime_type,
                    maximum_bytes=maximum,
                )
                try:
                    source = self.context.database.add_source_file(user_id, source_id, str(uuid.uuid4()), file_info)
                except Exception:
                    if file_info["created"]:
                        self.context.files.delete_blob(str(file_info["blobHash"]))
                    raise
                return {"source": source}
            finally:
                uploaded.file.close()
        if len(route) == 4 and route[2] == "files" and method == "DELETE":
            source, orphaned_blob = self.context.database.delete_source_file(user_id, source_id, route[3])
            if orphaned_blob:
                self.context.files.delete_blob(orphaned_blob)
            return {"source": source}

        if len(route) == 5 and route[2] == "files" and route[4] == "annotations":
            file_id = route[3]
            if method == "GET":
                return {"annotations": self.context.database.list_source_annotations(user_id, source_id, file_id)}
            if method == "POST":
                data = self._read_json()
                data.setdefault("id", str(uuid.uuid4()))
                return {"annotation": self.context.database.create_source_annotation(user_id, source_id, file_id, data)}
        if len(route) == 6 and route[2] == "files" and route[4] == "annotations" and method == "DELETE":
            self.context.database.delete_source_annotation(user_id, source_id, route[3], route[5])
            return {"deleted": True}

        if len(route) == 4 and route[2] == "libraries":
            library_id = route[3]
            if method == "PUT":
                data = self._read_json()
                self.context.database.link_source_library(user_id, source_id, library_id, data.get("note", ""))
                return {"source": self.context.database.source_detail(user_id, source_id)}
            if method == "DELETE":
                self.context.database.unlink_source_library(user_id, source_id, library_id)
                return {"source": self.context.database.source_detail(user_id, source_id)}

        if len(route) == 3 and route[2] == "element-links" and method == "POST":
            data = self._read_json()
            data.setdefault("id", str(uuid.uuid4()))
            return {"source": self.context.database.link_source_element(user_id, source_id, data)}
        if len(route) == 4 and route[2] == "element-links" and method == "DELETE":
            self.context.database.unlink_source_element(user_id, source_id, route[3])
            return {"source": self.context.database.source_detail(user_id, source_id)}
        raise ApiError(HTTPStatus.NOT_FOUND, "Neznámy zdrojový endpoint.")

    def _route_source_collection(self, method: str, user_id: str, route: list[str]) -> dict[str, Any]:
        collection_id = route[1]
        if len(route) == 2:
            if method == "GET":
                return self.context.database.source_collection_detail(user_id, collection_id)
            if method == "PATCH":
                return self.context.database.update_source_collection(user_id, collection_id, self._read_json())
            if method == "DELETE":
                return {"parentId": self.context.database.delete_source_collection(user_id, collection_id)}
        if len(route) == 4 and route[2] == "sources":
            source_id = route[3]
            if method == "PUT":
                self.context.database.link_collection_source(user_id, collection_id, source_id)
                return self.context.database.source_collection_detail(user_id, collection_id)
            if method == "DELETE":
                self.context.database.unlink_collection_source(user_id, collection_id, source_id)
                return self.context.database.source_collection_detail(user_id, collection_id)
        raise ApiError(HTTPStatus.NOT_FOUND, "Neznámy endpoint zbierky zdrojov.")

    def _read_json(self) -> dict[str, Any]:
        content_length = self._content_length(2 * 1024 * 1024)
        content_type = self.headers.get_content_type()
        if content_type != "application/json":
            raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "API očakáva JSON dáta.")
        value = json.loads(self.rfile.read(content_length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "JSON musí byť objekt.")
        return value

    def _read_upload(self, maximum: int = 101 * 1024 * 1024) -> UploadedFile:
        remaining = self._content_length(maximum)
        if self.headers.get_content_type() != "multipart/form-data":
            raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Nahrávanie očakáva multipart formulár.")
        boundary = self.headers.get_param("boundary")
        if not isinstance(boundary, str) or not boundary or len(boundary) > 200:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Nahrávanie nemá platnú multipart hranicu.")
        try:
            boundary_bytes = boundary.encode("ascii")
        except UnicodeEncodeError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Nahrávanie má neplatnú multipart hranicu.") from error

        initial, remaining = self._read_multipart_line(remaining)
        if initial.rstrip(b"\r\n") != b"--" + boundary_bytes:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Nahrávanie nemá očakávaný tvar.")
        headers, remaining = self._read_multipart_headers(remaining)
        filename = self._multipart_filename(headers.get("content-disposition", ""))
        if not filename:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Vyber súbor na nahratie.")

        stream = tempfile.SpooledTemporaryFile(max_size=MULTIPART_MEMORY_THRESHOLD, mode="w+b")
        try:
            self._copy_multipart_file(remaining, boundary_bytes, stream)
            stream.seek(0)
        except Exception:
            stream.close()
            raise
        mime_type = headers.get("content-type", "application/octet-stream").split(";", 1)[0].strip().lower()
        return UploadedFile(filename=filename, file=stream, mime_type=mime_type or "application/octet-stream")

    def _read_multipart_line(self, remaining: int) -> tuple[bytes, int]:
        if remaining <= 0:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Nahrávanie sa neočakávane skončilo.")
        limit = min(remaining, MAX_MULTIPART_HEADER_BYTES + 1)
        line = self.rfile.readline(limit)
        if not line:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Nahrávanie sa neočakávane skončilo.")
        if len(line) > MAX_MULTIPART_HEADER_BYTES or not line.endswith(b"\n"):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Hlavička nahrávania je príliš dlhá alebo neplatná.")
        return line, remaining - len(line)

    def _read_multipart_headers(self, remaining: int) -> tuple[dict[str, str], int]:
        headers: dict[str, str] = {}
        header_bytes = 0
        while True:
            line, remaining = self._read_multipart_line(remaining)
            header_bytes += len(line)
            if header_bytes > MAX_MULTIPART_HEADER_BYTES:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Hlavičky nahrávania sú príliš veľké.")
            if line in {b"\r\n", b"\n"}:
                return headers, remaining
            if b":" not in line:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Hlavička nahrávania je neplatná.")
            name, value = line.split(b":", 1)
            try:
                key = name.decode("ascii").strip().lower()
                parsed_value = value.decode("latin-1").strip()
            except UnicodeDecodeError as error:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Hlavička nahrávania je neplatná.") from error
            if not key or key in headers:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Hlavička nahrávania je neplatná.")
            headers[key] = parsed_value

    @staticmethod
    def _multipart_filename(disposition: str) -> str:
        message = Message()
        message["Content-Disposition"] = disposition
        if message.get_content_disposition() != "form-data":
            return ""
        parameters = dict(message.get_params(header="content-disposition", unquote=True)[1:])
        if parameters.get("name") != "file":
            return ""
        filename = parameters.get("filename")
        return filename if isinstance(filename, str) else ""

    def _copy_multipart_file(self, remaining: int, boundary: bytes, target: BinaryIO) -> None:
        marker = b"\r\n--" + boundary
        buffer = b""
        while remaining:
            chunk = self.rfile.read(min(MULTIPART_CHUNK_BYTES, remaining))
            if not chunk:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Nahrávanie sa neočakávane skončilo.")
            remaining -= len(chunk)
            buffer += chunk
            marker_index = buffer.find(marker)
            if marker_index >= 0:
                target.write(buffer[:marker_index])
                suffix = buffer[marker_index + len(marker):]
                if len(suffix) < 2 and remaining:
                    needed = min(2 - len(suffix), remaining)
                    continuation = self.rfile.read(needed)
                    if len(continuation) != needed:
                        raise ApiError(HTTPStatus.BAD_REQUEST, "Nahrávanie sa neočakávane skončilo.")
                    suffix += continuation
                    remaining -= needed
                if not suffix.startswith(b"--"):
                    self._discard_upload_bytes(remaining)
                    raise ApiError(HTTPStatus.BAD_REQUEST, "Nahrávanie obsahuje viac častí, než sa očakáva.")
                if remaining + len(suffix) > 4:
                    self._discard_upload_bytes(remaining)
                    raise ApiError(HTTPStatus.BAD_REQUEST, "Nahrávanie má neplatné ukončenie.")
                if remaining:
                    continuation = self.rfile.read(remaining)
                    if len(continuation) != remaining:
                        raise ApiError(HTTPStatus.BAD_REQUEST, "Nahrávanie sa neočakávane skončilo.")
                    suffix += continuation
                    remaining = 0
                if suffix not in {b"--", b"--\r\n"}:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "Nahrávanie má neplatné ukončenie.")
                return
            keep = len(marker) + 2
            write_size = len(buffer) - keep
            if write_size > 0:
                target.write(buffer[:write_size])
                buffer = buffer[write_size:]
        raise ApiError(HTTPStatus.BAD_REQUEST, "Nahrávanie nemá ukončenie súboru.")

    def _discard_upload_bytes(self, remaining: int) -> None:
        while remaining:
            chunk = self.rfile.read(min(MULTIPART_CHUNK_BYTES, remaining))
            if not chunk:
                return
            remaining -= len(chunk)

    def _content_length(self, maximum: int) -> int:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Neplatná veľkosť požiadavky.") from error
        if content_length <= 0:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Prázdna požiadavka.")
        if content_length > maximum:
            raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Požiadavka je príliš veľká.")
        return content_length

    def _require_user(self) -> dict[str, str]:
        user = self.context.auth.session_user(self._session_token())
        if not user:
            raise ApiError(HTTPStatus.UNAUTHORIZED, "Prihlásenie vypršalo.")
        return user

    def _session_token(self) -> str | None:
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        morsel = cookie.get("poznamkovnik_session")
        return morsel.value if morsel else None

    def _set_session_cookie(self, token: str) -> None:
        self._response_cookies.append(
            f"poznamkovnik_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age={SESSION_DAYS * 24 * 60 * 60}"
        )

    def _clear_session_cookie(self) -> None:
        self._response_cookies.append("poznamkovnik_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0")

    @staticmethod
    def _is_audio_upload(file_info: dict[str, str | int | bool]) -> bool:
        mime_type = str(file_info.get("mimeType", "")).lower()
        suffix = Path(str(file_info.get("originalName", ""))).suffix.lower()
        return mime_type.startswith("audio/") or mime_type in {"application/ogg", "video/webm"} or suffix in MUSIC_FILE_EXTENSIONS

    def _send_music_track(self, user_id: str, track_id: str, *, head_only: bool = False) -> None:
        track = self.context.database.music_track_file(user_id, track_id)
        path = self.context.files.path_for_hash(str(track["blob_hash"]))
        if not path.is_file():
            raise ApiError(HTTPStatus.NOT_FOUND, "Zvukový súbor sa nenašiel.")
        mime_type = str(track["mime_type"] or mimetypes.guess_type(str(track["original_name"]))[0] or "audio/mpeg")
        self._send_streamed_file(path, mime_type, str(track["original_name"]), head_only=head_only)

    def _send_radio_recording(self, user_id: str, recording_id: str, *, download: bool, head_only: bool = False) -> None:
        recording = self.context.database.radio_recording_file(user_id, recording_id)
        path = self.context.radio_recordings.path_for_recording(user_id, recording)
        if not path.is_file():
            raise ApiError(HTTPStatus.NOT_FOUND, "Súbor nahrávky sa nenašiel.")
        title = str(recording["station_title"]).strip() or "nahrávka-rádia"
        filename = f"{title}.mp3"
        self._send_streamed_file(path, str(recording["mime_type"]), filename, download=download, head_only=head_only)

    def _send_radio_station_stream(self, user_id: str, station_id: str, *, head_only: bool = False) -> None:
        station = self.context.database.radio_station_stream(user_id, station_id)
        request = Request(
            str(station["stream_url"]),
            headers={
                "Accept": "audio/*,application/ogg;q=0.9,*/*;q=0.2",
                "Accept-Encoding": "identity",
                "Icy-MetaData": "0",
                "User-Agent": "Poznamkovnik/1.0 radio player",
            },
        )
        try:
            response = urlopen(request, timeout=RADIO_STREAM_TIMEOUT_SECONDS)
        except HTTPError as error:
            raise ApiError(HTTPStatus.BAD_GATEWAY, f"Stanica odpovedala chybou {error.code}.") from error
        except (URLError, TimeoutError, OSError) as error:
            raise ApiError(HTTPStatus.BAD_GATEWAY, "K streamu stanice sa nepodarilo pripojiť.") from error

        try:
            mime_type = response.headers.get_content_type() or "audio/mpeg"
            if not mime_type.startswith("audio/") and mime_type not in {"application/ogg", "video/webm"}:
                raise ApiError(HTTPStatus.BAD_GATEWAY, "Adresa stanice nevracia zvukový stream.")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime_type)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if head_only:
                return
            while True:
                chunk = response.read(RADIO_STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break
        finally:
            response.close()

    def _send_streamed_file(
        self, path: Path, mime_type: str, filename: str, *, download: bool = False, head_only: bool = False
    ) -> None:
        size = path.stat().st_size
        start = 0
        end = max(0, size - 1)
        status = HTTPStatus.OK
        range_header = self.headers.get("Range", "").strip()
        if range_header:
            try:
                unit, value = range_header.split("=", 1)
                if unit != "bytes" or "," in value:
                    raise ValueError
                first, last = value.split("-", 1)
                if first:
                    start = int(first)
                    end = int(last) if last else end
                elif last:
                    length = int(last)
                    if length <= 0:
                        raise ValueError
                    start = max(0, size - length)
                else:
                    raise ValueError
                if start < 0 or start >= size or end < start:
                    raise ValueError
                end = min(end, size - 1)
                status = HTTPStatus.PARTIAL_CONTENT
            except (ValueError, TypeError):
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return

        length = end - start + 1 if size else 0
        safe_name = filename.replace('"', "")
        self.send_response(status)
        self.send_header("Content-Type", mime_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        disposition = "attachment" if download else "inline"
        self.send_header("Content-Disposition", f'{disposition}; filename="{safe_name}"')
        self.send_header("X-Content-Type-Options", "nosniff")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if head_only or not length:
            return
        with path.open("rb") as source:
            source.seek(start)
            remaining = length
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _send_file(self, user_id: str, file_id: str, download: bool, *, head_only: bool = False) -> None:
        file = self.context.database.file_for_user(user_id, file_id)
        path = self.context.files.path_for_hash(file["blob_hash"])
        if not path.is_file():
            raise ApiError(HTTPStatus.NOT_FOUND, "Obsah súboru sa nenašiel.")
        mime_type = file["mime_type"] or mimetypes.guess_type(file["original_name"])[0] or "application/octet-stream"
        disposition = "attachment" if download or not self.context.files.can_preview_inline(mime_type) else "inline"
        safe_name = file["original_name"].replace('"', "")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Content-Disposition", f'{disposition}; filename="{safe_name}"')
        self.end_headers()
        if head_only:
            return
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                self.wfile.write(chunk)

    def _send_backup_archive(self, archive: BackupArtifact) -> None:
        try:
            if not archive.path.is_file():
                raise ApiError(HTTPStatus.NOT_FOUND, "Záložný archív sa nenašiel.")
            safe_name = archive.filename.replace('"', "")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(archive.path.stat().st_size))
            self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            with archive.path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    self.wfile.write(chunk)
        finally:
            self.context.backups.discard_temporary(archive)

    def _send_background(self, user_id: str, *, head_only: bool = False) -> None:
        background = self.context.database.background_preference(user_id)
        if not background["hasBackground"] or background.get("kind") != "custom":
            raise ApiError(HTTPStatus.NOT_FOUND, "Vlastné pozadie nie je nastavené.")
        path = self.context.backgrounds.path_for(user_id, str(background["filename"]))
        if not path.is_file():
            raise ApiError(HTTPStatus.NOT_FOUND, "Súbor pozadia sa nenašiel.")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", str(background["mimeType"]))
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Content-Disposition", "inline")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if head_only:
            return
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                self.wfile.write(chunk)

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        for cookie in self._response_cookies:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
