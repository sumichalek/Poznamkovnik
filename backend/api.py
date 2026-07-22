from __future__ import annotations

import cgi
import json
import mimetypes
import uuid
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .auth import AuthError, AuthService, SESSION_DAYS
from .database import Database, ValidationError
from .files import BackgroundStore, FileStore, MAX_BACKGROUND_BYTES, UploadError


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
        except (ValidationError, UploadError) as error:
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

        user = self._require_user()
        if route == ["preferences"] and method == "GET":
            return {"background": self.context.database.background_preference(user["id"])}
        if route == ["preferences", "background"] and method == "POST":
            uploaded = self._read_upload(MAX_BACKGROUND_BYTES + 512 * 1024)
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

        if route == ["sources"] and method == "GET":
            query = parse_qs(request_url.query).get("q", [""])[0]
            return {"sources": self.context.database.list_sources(user["id"], query)}
        if route == ["sources"] and method == "POST":
            data = self._read_json()
            data.setdefault("id", str(uuid.uuid4()))
            return {"source": self.context.database.create_source(user["id"], data)}

        if len(route) >= 2 and route[0] == "sources":
            return self._route_source(method, user["id"], route)
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
            uploaded = self._read_upload()
            file_info = self.context.files.store_upload(uploaded.file, uploaded.filename, uploaded.type)
            try:
                source = self.context.database.add_source_file(user_id, source_id, str(uuid.uuid4()), file_info)
            except Exception:
                if file_info["created"]:
                    self.context.files.delete_blob(str(file_info["blobHash"]))
                raise
            return {"source": source}

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

    def _read_json(self) -> dict[str, Any]:
        content_length = self._content_length(2 * 1024 * 1024)
        content_type = self.headers.get_content_type()
        if content_type != "application/json":
            raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "API očakáva JSON dáta.")
        value = json.loads(self.rfile.read(content_length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "JSON musí byť objekt.")
        return value

    def _read_upload(self, maximum: int = 101 * 1024 * 1024) -> cgi.FieldStorage:
        self._content_length(maximum)
        if self.headers.get_content_type() != "multipart/form-data":
            raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Nahrávanie očakáva multipart formulár.")
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", "")},
        )
        uploaded = form["file"] if "file" in form else None
        if uploaded is None or isinstance(uploaded, list) or not uploaded.filename or not uploaded.file:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Vyber súbor na nahratie.")
        return uploaded

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

    def _send_background(self, user_id: str, *, head_only: bool = False) -> None:
        background = self.context.database.background_preference(user_id)
        if not background["hasBackground"]:
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
