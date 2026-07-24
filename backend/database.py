from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ValidationError(ValueError):
    """Dáta z klienta nemajú očakávaný tvar."""


DEFAULT_MAIN_PANEL_TRANSPARENCY = 20
DEFAULT_WORKSPACE_PANEL_TRANSPARENCY = 24
DEFAULT_EDITOR_SURFACE_TRANSPARENCY = 12
DEFAULT_SOURCE_FILE_MAX_BYTES = 100 * 1024 * 1024
MIN_SOURCE_FILE_MAX_BYTES = 1 * 1024 * 1024
MAX_SOURCE_FILE_MAX_BYTES = 1024 * 1024 * 1024


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    background_filename TEXT NOT NULL DEFAULT '',
                    background_mime_type TEXT NOT NULL DEFAULT '',
                    background_version TEXT NOT NULL DEFAULT '',
                    background_preset TEXT NOT NULL DEFAULT '',
                    main_panel_transparency INTEGER NOT NULL DEFAULT 20,
                    workspace_panel_transparency INTEGER NOT NULL DEFAULT 24,
                    editor_surface_transparency INTEGER NOT NULL DEFAULT 12,
                    source_file_max_bytes INTEGER NOT NULL DEFAULT 104857600,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_token_idx ON sessions(token_hash);

                CREATE TABLE IF NOT EXISTS libraries (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS libraries_user_idx ON libraries(user_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS elements (
                    id TEXT PRIMARY KEY,
                    library_id TEXT NOT NULL REFERENCES libraries(id) ON DELETE CASCADE,
                    type TEXT NOT NULL CHECK(type IN ('folder', 'note', 'article')),
                    parent_id TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS elements_library_idx ON elements(library_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'source',
                    description TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sources_user_idx ON sources(user_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS source_collections (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    parent_id TEXT REFERENCES source_collections(id) ON DELETE SET NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS source_collections_user_parent_idx ON source_collections(user_id, parent_id, title);

                CREATE TABLE IF NOT EXISTS collection_sources (
                    collection_id TEXT NOT NULL REFERENCES source_collections(id) ON DELETE CASCADE,
                    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                    added_at TEXT NOT NULL,
                    PRIMARY KEY(collection_id, source_id)
                );
                CREATE INDEX IF NOT EXISTS collection_sources_source_idx ON collection_sources(source_id);

                CREATE TABLE IF NOT EXISTS source_files (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                    blob_hash TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS source_files_source_idx ON source_files(source_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS source_files_blob_idx ON source_files(blob_hash);

                CREATE TABLE IF NOT EXISTS source_annotations (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                    source_file_id TEXT NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
                    element_id TEXT REFERENCES elements(id) ON DELETE SET NULL,
                    quote TEXT NOT NULL DEFAULT '',
                    locator TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS source_annotations_file_idx ON source_annotations(source_file_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS source_annotations_element_idx ON source_annotations(element_id);

                CREATE TABLE IF NOT EXISTS library_sources (
                    library_id TEXT NOT NULL REFERENCES libraries(id) ON DELETE CASCADE,
                    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                    added_at TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY(library_id, source_id)
                );
                CREATE INDEX IF NOT EXISTS library_sources_source_idx ON library_sources(source_id);

                CREATE TABLE IF NOT EXISTS element_sources (
                    id TEXT PRIMARY KEY,
                    element_id TEXT NOT NULL REFERENCES elements(id) ON DELETE CASCADE,
                    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                    source_file_id TEXT REFERENCES source_files(id) ON DELETE SET NULL,
                    relation_type TEXT NOT NULL DEFAULT 'reference',
                    locator TEXT NOT NULL DEFAULT '',
                    label TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS element_sources_element_idx ON element_sources(element_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS element_sources_source_idx ON element_sources(source_id);
                """
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(user_preferences)")}
            if "background_preset" not in columns:
                connection.execute("ALTER TABLE user_preferences ADD COLUMN background_preset TEXT NOT NULL DEFAULT ''")
            if "main_panel_transparency" not in columns:
                connection.execute(
                    "ALTER TABLE user_preferences ADD COLUMN main_panel_transparency INTEGER NOT NULL DEFAULT 20"
                )
            if "workspace_panel_transparency" not in columns:
                connection.execute(
                    "ALTER TABLE user_preferences ADD COLUMN workspace_panel_transparency INTEGER NOT NULL DEFAULT 24"
                )
            if "editor_surface_transparency" not in columns:
                connection.execute(
                    "ALTER TABLE user_preferences ADD COLUMN editor_surface_transparency INTEGER NOT NULL DEFAULT 12"
                )
            if "source_file_max_bytes" not in columns:
                connection.execute(
                    "ALTER TABLE user_preferences ADD COLUMN source_file_max_bytes INTEGER NOT NULL DEFAULT 104857600"
                )

    def user_count(self) -> int:
        with self.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def background_preference(self, user_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT background_filename, background_mime_type, background_version, background_preset
                FROM user_preferences WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if not row:
            return {"hasBackground": False, "kind": "none", "version": ""}
        if row["background_preset"]:
            return {
                "hasBackground": True,
                "kind": "preset",
                "preset": row["background_preset"],
                "version": f"preset-{row['background_preset']}",
            }
        if not row["background_filename"]:
            return {"hasBackground": False, "kind": "none", "version": ""}
        return {
            "hasBackground": True,
            "kind": "custom",
            "filename": row["background_filename"],
            "mimeType": row["background_mime_type"],
            "version": row["background_version"],
        }

    def preferences(self, user_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT main_panel_transparency, workspace_panel_transparency, editor_surface_transparency, source_file_max_bytes
                FROM user_preferences WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        return {
            "background": self.background_preference(user_id),
            "mainPanelTransparency": int(row["main_panel_transparency"]) if row else DEFAULT_MAIN_PANEL_TRANSPARENCY,
            "workspacePanelTransparency": (
                int(row["workspace_panel_transparency"]) if row else DEFAULT_WORKSPACE_PANEL_TRANSPARENCY
            ),
            "editorSurfaceTransparency": (
                int(row["editor_surface_transparency"]) if row else DEFAULT_EDITOR_SURFACE_TRANSPARENCY
            ),
            "sourceFileMaxBytes": int(row["source_file_max_bytes"]) if row else DEFAULT_SOURCE_FILE_MAX_BYTES,
        }

    def source_file_max_bytes(self, user_id: str) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT source_file_max_bytes FROM user_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return int(row["source_file_max_bytes"]) if row else DEFAULT_SOURCE_FILE_MAX_BYTES

    def save_preferences(self, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        current = self.preferences(user_id)
        main_panel_transparency = self._preference_int(
            data.get("mainPanelTransparency", current["mainPanelTransparency"]),
            "Priehľadnosť hlavných panelov",
            0,
            65,
        )
        workspace_panel_transparency = self._preference_int(
            data.get("workspacePanelTransparency", current["workspacePanelTransparency"]),
            "Priehľadnosť pracovných panelov",
            0,
            65,
        )
        editor_surface_transparency = self._preference_int(
            data.get("editorSurfaceTransparency", current["editorSurfaceTransparency"]),
            "Priehľadnosť plochy editora",
            0,
            65,
        )
        source_file_max_bytes = self._preference_int(
            data.get("sourceFileMaxBytes", current["sourceFileMaxBytes"]),
            "Limit prílohy",
            MIN_SOURCE_FILE_MAX_BYTES,
            MAX_SOURCE_FILE_MAX_BYTES,
        )
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO user_preferences(
                    user_id, main_panel_transparency, workspace_panel_transparency, editor_surface_transparency,
                    source_file_max_bytes, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    main_panel_transparency = excluded.main_panel_transparency,
                    workspace_panel_transparency = excluded.workspace_panel_transparency,
                    editor_surface_transparency = excluded.editor_surface_transparency,
                    source_file_max_bytes = excluded.source_file_max_bytes,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    main_panel_transparency,
                    workspace_panel_transparency,
                    editor_surface_transparency,
                    source_file_max_bytes,
                    now_iso(),
                ),
            )
        return self.preferences(user_id)

    @staticmethod
    def _preference_int(value: Any, label: str, minimum: int, maximum: int) -> int:
        if isinstance(value, bool):
            raise ValidationError(f"{label} musí byť číslo.")
        try:
            numeric = int(value)
        except (TypeError, ValueError) as error:
            raise ValidationError(f"{label} musí byť číslo.") from error
        if numeric < minimum or numeric > maximum:
            raise ValidationError(f"{label} musí byť v rozsahu {minimum} až {maximum}.")
        return numeric

    def save_background_preference(
        self, user_id: str, filename: str, mime_type: str, version: str
    ) -> dict[str, Any]:
        previous = self.background_preference(user_id)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO user_preferences(
                    user_id, background_filename, background_mime_type, background_version, background_preset, updated_at
                )
                VALUES (?, ?, ?, ?, '', ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    background_filename = excluded.background_filename,
                    background_mime_type = excluded.background_mime_type,
                    background_version = excluded.background_version,
                    background_preset = '',
                    updated_at = excluded.updated_at
                """,
                (user_id, filename, mime_type, version, now_iso()),
            )
        return previous

    def save_background_preset(self, user_id: str, preset: str) -> dict[str, Any]:
        if preset not in {"misty-forest", "forest-lake", "calm-ocean", "foggy-mountain"}:
            raise ValidationError("Neznáme predvolené pozadie.")
        previous = self.background_preference(user_id)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO user_preferences(
                    user_id, background_filename, background_mime_type, background_version, background_preset, updated_at
                )
                VALUES (?, '', '', '', ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    background_filename = '',
                    background_mime_type = '',
                    background_version = '',
                    background_preset = excluded.background_preset,
                    updated_at = excluded.updated_at
                """,
                (user_id, preset, now_iso()),
            )
        return previous

    def clear_background_preference(self, user_id: str) -> dict[str, Any]:
        previous = self.background_preference(user_id)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO user_preferences(
                    user_id, background_filename, background_mime_type, background_version, background_preset, updated_at
                )
                VALUES (?, '', '', '', '', ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    background_filename = '',
                    background_mime_type = '',
                    background_version = '',
                    background_preset = '',
                    updated_at = excluded.updated_at
                """,
                (user_id, now_iso()),
            )
        return previous

    def read_workspace(self, user_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            libraries = [
                dict(row)
                for row in connection.execute(
                    "SELECT id, name, created_at AS createdAt FROM libraries WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,),
                )
            ]
            elements: dict[str, list[dict[str, Any]]] = {library["id"]: [] for library in libraries}
            rows = connection.execute(
                """
                SELECT e.id, e.library_id, e.type, e.parent_id, e.title, e.content,
                       e.created_at, e.updated_at
                FROM elements e
                JOIN libraries l ON l.id = e.library_id
                WHERE l.user_id = ?
                ORDER BY e.created_at DESC
                """,
                (user_id,),
            )
            for row in rows:
                element = dict(row)
                library_id = element.pop("library_id")
                element["parentId"] = element.pop("parent_id")
                element["createdAt"] = element.pop("created_at")
                element["updatedAt"] = element.pop("updated_at")
                elements.setdefault(library_id, []).append(element)
        return {"libraries": libraries, "libraryElements": elements}

    def replace_workspace(self, user_id: str, workspace: Any) -> dict[str, Any]:
        if not isinstance(workspace, dict):
            raise ValidationError("Pracovný priestor musí byť objekt.")
        libraries = self._normalize_libraries(workspace.get("libraries"))
        library_elements = self._normalize_elements(workspace.get("libraryElements"), {item["id"] for item in libraries})

        with self.connect() as connection:
            existing_library_ids = {
                row["id"] for row in connection.execute("SELECT id FROM libraries WHERE user_id = ?", (user_id,))
            }
            incoming_library_ids = {library["id"] for library in libraries}
            for library_id in existing_library_ids - incoming_library_ids:
                connection.execute("DELETE FROM libraries WHERE id = ? AND user_id = ?", (library_id, user_id))
            for library in libraries:
                connection.execute(
                    """
                    INSERT INTO libraries(id, user_id, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET name = excluded.name, updated_at = excluded.updated_at
                    WHERE libraries.user_id = excluded.user_id
                    """,
                    (library["id"], user_id, library["name"], library["createdAt"], now_iso()),
                )
            existing_element_ids = {
                row["id"]
                for row in connection.execute(
                    "SELECT e.id FROM elements e JOIN libraries l ON l.id = e.library_id WHERE l.user_id = ?", (user_id,)
                )
            }
            incoming_elements = [
                (library_id, item) for library_id, items in library_elements.items() for item in items
            ]
            incoming_element_ids = {item["id"] for _, item in incoming_elements}
            for element_id in existing_element_ids - incoming_element_ids:
                connection.execute("DELETE FROM elements WHERE id = ?", (element_id,))
            for library_id, item in incoming_elements:
                connection.execute(
                    """
                    INSERT INTO elements(id, library_id, type, parent_id, title, content, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        library_id = excluded.library_id,
                        type = excluded.type,
                        parent_id = excluded.parent_id,
                        title = excluded.title,
                        content = excluded.content,
                        updated_at = excluded.updated_at
                    """,
                    (
                        item["id"],
                        library_id,
                        item["type"],
                        item["parentId"],
                        item["title"],
                        item["content"],
                        item["createdAt"],
                        item["updatedAt"],
                    ),
                )
        return self.read_workspace(user_id)

    def _normalize_libraries(self, value: Any) -> list[dict[str, str]]:
        if not isinstance(value, list):
            raise ValidationError("Zoznam knižníc chýba.")
        if len(value) > 500:
            raise ValidationError("Príliš veľa knižníc.")
        seen_ids: set[str] = set()
        normalized: list[dict[str, str]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            item_id = self._clean_id(item.get("id"))
            name = self._clean_text(item.get("name"), 120)
            if not item_id or not name or item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            normalized.append({"id": item_id, "name": name, "createdAt": self._timestamp(item.get("createdAt"))})
        return normalized

    def _normalize_elements(self, value: Any, library_ids: set[str]) -> dict[str, list[dict[str, str]]]:
        if not isinstance(value, dict):
            raise ValidationError("Obsah knižníc chýba.")
        normalized: dict[str, list[dict[str, str]]] = {}
        all_ids: set[str] = set()
        item_count = 0
        for library_id, items in value.items():
            if library_id not in library_ids or not isinstance(items, list):
                continue
            clean_items: list[dict[str, str]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_count += 1
                if item_count > 10_000:
                    raise ValidationError("Príliš veľa prvkov v pracovnom priestore.")
                item_id = self._clean_id(item.get("id"))
                item_type = item.get("type")
                if not item_id or item_id in all_ids or item_type not in {"folder", "note", "article"}:
                    continue
                all_ids.add(item_id)
                clean_items.append(
                    {
                        "id": item_id,
                        "type": item_type,
                        "parentId": self._clean_id(item.get("parentId")) or "",
                        "title": self._clean_text(item.get("title"), 200),
                        "content": self._clean_text(item.get("content"), 5_000_000),
                        "createdAt": self._timestamp(item.get("createdAt")),
                        "updatedAt": self._timestamp(item.get("updatedAt")),
                    }
                )
            if clean_items:
                known_folders = {item["id"] for item in clean_items if item["type"] == "folder"}
                for item in clean_items:
                    if item["parentId"] not in known_folders or item["parentId"] == item["id"]:
                        item["parentId"] = ""
                normalized[library_id] = clean_items
        return normalized

    @staticmethod
    def _clean_id(value: Any) -> str:
        value = str(value or "").strip()
        return value[:80] if value else ""

    @staticmethod
    def _clean_text(value: Any, maximum: int) -> str:
        return str(value or "").strip()[:maximum]

    @staticmethod
    def _timestamp(value: Any) -> str:
        value = str(value or "").strip()
        return value[:64] if value else now_iso()

    def create_source(self, user_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Zdroj musí byť objekt.")
        source_id = self._clean_id(data.get("id"))
        title = self._clean_text(data.get("title"), 240)
        kind = self._clean_text(data.get("kind"), 40) or "source"
        description = self._clean_text(data.get("description"), 10_000)
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        if not source_id or not title:
            raise ValidationError("Zdroj potrebuje názov.")
        timestamp = now_iso()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO sources(id, user_id, title, kind, description, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (source_id, user_id, title, kind, description, json.dumps(metadata, ensure_ascii=False), timestamp, timestamp),
            )
        return self.source_detail(user_id, source_id)

    def list_sources(self, user_id: str, query: str = "") -> list[dict[str, Any]]:
        search = f"%{query.strip()}%"
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT s.id, s.title, s.kind, s.description, s.metadata_json,
                       s.created_at, s.updated_at,
                       COUNT(DISTINCT ls.library_id) AS library_count,
                       COUNT(DISTINCT es.id) AS element_count,
                       COUNT(DISTINCT sf.id) AS file_count,
                       COUNT(DISTINCT cs.collection_id) AS collection_count
                FROM sources s
                LEFT JOIN library_sources ls ON ls.source_id = s.id
                LEFT JOIN element_sources es ON es.source_id = s.id
                LEFT JOIN source_files sf ON sf.source_id = s.id
                LEFT JOIN collection_sources cs ON cs.source_id = s.id
                WHERE s.user_id = ? AND (s.title LIKE ? OR s.description LIKE ? OR s.metadata_json LIKE ?)
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                """,
                (user_id, search, search, search),
            ).fetchall()
        return [self._source_row(row) for row in rows]

    def list_source_collections(self, user_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT c.id, c.parent_id, c.title, c.created_at, c.updated_at,
                       COUNT(DISTINCT child.id) AS child_count,
                       COUNT(DISTINCT cs.source_id) AS source_count
                FROM source_collections c
                LEFT JOIN source_collections child ON child.parent_id = c.id
                LEFT JOIN collection_sources cs ON cs.collection_id = c.id
                WHERE c.user_id = ?
                GROUP BY c.id
                ORDER BY c.title COLLATE NOCASE
                """,
                (user_id,),
            ).fetchall()
        return [self._source_collection_row(row) for row in rows]

    def source_collection_detail(self, user_id: str, collection_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            collection = self._source_collection(connection, user_id, collection_id)
            child_rows = connection.execute(
                """
                SELECT c.id, c.parent_id, c.title, c.created_at, c.updated_at,
                       COUNT(DISTINCT child.id) AS child_count,
                       COUNT(DISTINCT cs.source_id) AS source_count
                FROM source_collections c
                LEFT JOIN source_collections child ON child.parent_id = c.id
                LEFT JOIN collection_sources cs ON cs.collection_id = c.id
                WHERE c.user_id = ? AND c.parent_id = ?
                GROUP BY c.id
                ORDER BY c.title COLLATE NOCASE
                """,
                (user_id, collection_id),
            ).fetchall()
            source_rows = connection.execute(
                """
                SELECT s.id, s.title, s.kind, s.description, s.metadata_json,
                       s.created_at, s.updated_at,
                       COUNT(DISTINCT ls.library_id) AS library_count,
                       COUNT(DISTINCT es.id) AS element_count,
                       COUNT(DISTINCT sf.id) AS file_count,
                       COUNT(DISTINCT all_cs.collection_id) AS collection_count
                FROM collection_sources cs
                JOIN sources s ON s.id = cs.source_id
                LEFT JOIN library_sources ls ON ls.source_id = s.id
                LEFT JOIN element_sources es ON es.source_id = s.id
                LEFT JOIN source_files sf ON sf.source_id = s.id
                LEFT JOIN collection_sources all_cs ON all_cs.source_id = s.id
                WHERE cs.collection_id = ? AND s.user_id = ?
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                """,
                (collection_id, user_id),
            ).fetchall()
        return {
            "collection": self._source_collection_row(collection),
            "children": [self._source_collection_row(row) for row in child_rows],
            "sources": [self._source_row(row) for row in source_rows],
        }

    def create_source_collection(self, user_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Zbierka musí byť objekt.")
        collection_id = self._clean_id(data.get("id"))
        parent_id = self._clean_id(data.get("parentId")) or None
        title = self._clean_text(data.get("title"), 160)
        if not collection_id or not title:
            raise ValidationError("Zbierka potrebuje názov.")
        timestamp = now_iso()
        with self.connect() as connection:
            if parent_id:
                self._assert_source_collection(connection, user_id, parent_id)
            connection.execute(
                """
                INSERT INTO source_collections(id, user_id, parent_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (collection_id, user_id, parent_id, title, timestamp, timestamp),
            )
        return self.source_collection_detail(user_id, collection_id)

    def update_source_collection(self, user_id: str, collection_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Úprava zbierky musí byť objekt.")
        title = self._clean_text(data.get("title"), 160)
        if not title:
            raise ValidationError("Zbierka potrebuje názov.")
        with self.connect() as connection:
            self._assert_source_collection(connection, user_id, collection_id)
            connection.execute(
                "UPDATE source_collections SET title = ?, updated_at = ? WHERE id = ?",
                (title, now_iso(), collection_id),
            )
        return self.source_collection_detail(user_id, collection_id)

    def delete_source_collection(self, user_id: str, collection_id: str) -> str:
        with self.connect() as connection:
            collection = self._source_collection(connection, user_id, collection_id)
            parent_id = collection["parent_id"] or ""
            connection.execute(
                "UPDATE source_collections SET parent_id = ? WHERE user_id = ? AND parent_id = ?",
                (parent_id or None, user_id, collection_id),
            )
            connection.execute("DELETE FROM source_collections WHERE id = ? AND user_id = ?", (collection_id, user_id))
        return parent_id

    def link_collection_source(self, user_id: str, collection_id: str, source_id: str) -> None:
        with self.connect() as connection:
            self._assert_source_collection(connection, user_id, collection_id)
            self._assert_source(connection, user_id, source_id)
            connection.execute(
                """
                INSERT INTO collection_sources(collection_id, source_id, added_at) VALUES (?, ?, ?)
                ON CONFLICT(collection_id, source_id) DO NOTHING
                """,
                (collection_id, source_id, now_iso()),
            )

    def unlink_collection_source(self, user_id: str, collection_id: str, source_id: str) -> None:
        with self.connect() as connection:
            self._assert_source_collection(connection, user_id, collection_id)
            self._assert_source(connection, user_id, source_id)
            connection.execute(
                "DELETE FROM collection_sources WHERE collection_id = ? AND source_id = ?",
                (collection_id, source_id),
            )

    def source_detail(self, user_id: str, source_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM sources WHERE id = ? AND user_id = ?", (source_id, user_id)
            ).fetchone()
            if not row:
                raise KeyError("Zdroj neexistuje.")
            source = self._source_row(row)
            source["files"] = [
                {
                    "id": file["id"],
                    "originalName": file["original_name"],
                    "mimeType": file["mime_type"],
                    "sizeBytes": file["size_bytes"],
                    "annotationCount": file["annotation_count"],
                    "createdAt": file["created_at"],
                }
                for file in connection.execute(
                    """
                    SELECT sf.*, COUNT(sa.id) AS annotation_count
                    FROM source_files sf
                    LEFT JOIN source_annotations sa ON sa.source_file_id = sf.id
                    WHERE sf.source_id = ?
                    GROUP BY sf.id
                    ORDER BY sf.created_at DESC
                    """,
                    (source_id,),
                )
            ]
            source["libraries"] = [
                {"id": item["id"], "name": item["name"], "note": item["note"]}
                for item in connection.execute(
                    """
                    SELECT l.id, l.name, ls.note
                    FROM library_sources ls JOIN libraries l ON l.id = ls.library_id
                    WHERE ls.source_id = ? AND l.user_id = ? ORDER BY l.name COLLATE NOCASE
                    """,
                    (source_id, user_id),
                )
            ]
            source["collections"] = [
                {
                    "id": item["id"],
                    "title": item["title"],
                    "parentId": item["parent_id"] or "",
                }
                for item in connection.execute(
                    """
                    SELECT c.id, c.title, c.parent_id
                    FROM collection_sources cs
                    JOIN source_collections c ON c.id = cs.collection_id
                    WHERE cs.source_id = ? AND c.user_id = ?
                    ORDER BY c.title COLLATE NOCASE
                    """,
                    (source_id, user_id),
                )
            ]
            source["elements"] = [
                {
                    "linkId": item["link_id"],
                    "id": item["id"],
                    "title": item["title"],
                    "type": item["type"],
                    "libraryId": item["library_id"],
                    "libraryName": item["library_name"],
                    "relationType": item["relation_type"],
                    "locator": item["locator"],
                    "label": item["label"],
                    "note": item["note"],
                    "sourceFileId": item["source_file_id"],
                    "sourceFileName": item["source_file_name"] or "",
                }
                for item in connection.execute(
                    """
                    SELECT es.id AS link_id, e.id, e.title, e.type, e.library_id, l.name AS library_name,
                           es.relation_type, es.locator, es.label, es.note, es.source_file_id,
                           sf.original_name AS source_file_name
                    FROM element_sources es
                    JOIN elements e ON e.id = es.element_id
                    JOIN libraries l ON l.id = e.library_id
                    LEFT JOIN source_files sf ON sf.id = es.source_file_id
                    WHERE es.source_id = ? AND l.user_id = ?
                    ORDER BY es.created_at DESC
                    """,
                    (source_id, user_id),
                )
            ]
            source["annotations"] = [
                self._source_annotation_row(item)
                for item in connection.execute(
                    """
                    SELECT sa.*, sf.original_name AS source_file_name,
                           e.title AS element_title, e.type AS element_type, e.library_id,
                           l.name AS library_name
                    FROM source_annotations sa
                    JOIN source_files sf ON sf.id = sa.source_file_id
                    LEFT JOIN elements e ON e.id = sa.element_id
                    LEFT JOIN libraries l ON l.id = e.library_id
                    WHERE sa.source_id = ?
                    ORDER BY sa.updated_at DESC
                    """,
                    (source_id,),
                )
            ]
        return source

    def update_source(self, user_id: str, source_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Úprava zdroja musí byť objekt.")
        with self.connect() as connection:
            current = connection.execute(
                "SELECT * FROM sources WHERE id = ? AND user_id = ?", (source_id, user_id)
            ).fetchone()
            if not current:
                raise KeyError("Zdroj neexistuje.")
            title = self._clean_text(data.get("title", current["title"]), 240)
            kind = self._clean_text(data.get("kind", current["kind"]), 40) or "source"
            description = self._clean_text(data.get("description", current["description"]), 10_000)
            metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else json.loads(current["metadata_json"])
            if not title:
                raise ValidationError("Zdroj potrebuje názov.")
            connection.execute(
                "UPDATE sources SET title = ?, kind = ?, description = ?, metadata_json = ?, updated_at = ? WHERE id = ?",
                (title, kind, description, json.dumps(metadata, ensure_ascii=False), now_iso(), source_id),
            )
        return self.source_detail(user_id, source_id)

    def delete_source(self, user_id: str, source_id: str) -> list[str]:
        with self.connect() as connection:
            files = connection.execute(
                """
                SELECT sf.blob_hash FROM source_files sf
                JOIN sources s ON s.id = sf.source_id
                WHERE s.id = ? AND s.user_id = ?
                """,
                (source_id, user_id),
            ).fetchall()
            if not connection.execute("SELECT 1 FROM sources WHERE id = ? AND user_id = ?", (source_id, user_id)).fetchone():
                raise KeyError("Zdroj neexistuje.")
            connection.execute("DELETE FROM sources WHERE id = ? AND user_id = ?", (source_id, user_id))
            orphaned = []
            for file in files:
                blob_hash = file["blob_hash"]
                if not connection.execute("SELECT 1 FROM source_files WHERE blob_hash = ?", (blob_hash,)).fetchone():
                    orphaned.append(blob_hash)
        return orphaned

    def link_source_library(self, user_id: str, source_id: str, library_id: str, note: str = "") -> None:
        with self.connect() as connection:
            self._assert_source(connection, user_id, source_id)
            self._assert_library(connection, user_id, library_id)
            connection.execute(
                """
                INSERT INTO library_sources(library_id, source_id, added_at, note) VALUES (?, ?, ?, ?)
                ON CONFLICT(library_id, source_id) DO UPDATE SET note = excluded.note
                """,
                (library_id, source_id, now_iso(), self._clean_text(note, 2_000)),
            )

    def unlink_source_library(self, user_id: str, source_id: str, library_id: str) -> None:
        with self.connect() as connection:
            self._assert_library(connection, user_id, library_id)
            connection.execute("DELETE FROM library_sources WHERE library_id = ? AND source_id = ?", (library_id, source_id))

    def link_source_element(self, user_id: str, source_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Väzba musí byť objekt.")
        element_id = self._clean_id(data.get("elementId"))
        file_id = self._clean_id(data.get("sourceFileId")) or None
        relation_type = self._clean_text(data.get("relationType"), 40) or "reference"
        if relation_type not in {"reference", "citation", "attachment", "evidence", "counterargument", "derived"}:
            raise ValidationError("Neznámy typ väzby.")
        link_id = self._clean_id(data.get("id"))
        if not link_id or not element_id:
            raise ValidationError("Väzba potrebuje prvok.")
        with self.connect() as connection:
            self._assert_source(connection, user_id, source_id)
            self._assert_element(connection, user_id, element_id)
            if file_id and not connection.execute(
                "SELECT 1 FROM source_files WHERE id = ? AND source_id = ?", (file_id, source_id)
            ).fetchone():
                raise ValidationError("Súbor nepatrí k zdroju.")
            connection.execute(
                """
                INSERT INTO element_sources(id, element_id, source_id, source_file_id, relation_type, locator, label, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link_id,
                    element_id,
                    source_id,
                    file_id,
                    relation_type,
                    self._clean_text(data.get("locator"), 300),
                    self._clean_text(data.get("label"), 300),
                    self._clean_text(data.get("note"), 2_000),
                    now_iso(),
                ),
            )
        return self.source_detail(user_id, source_id)

    def unlink_source_element(self, user_id: str, source_id: str, link_id: str) -> None:
        with self.connect() as connection:
            self._assert_source(connection, user_id, source_id)
            connection.execute("DELETE FROM element_sources WHERE id = ? AND source_id = ?", (link_id, source_id))

    def add_source_file(self, user_id: str, source_id: str, file_id: str, file_info: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as connection:
            self._assert_source(connection, user_id, source_id)
            connection.execute(
                """
                INSERT INTO source_files(id, source_id, blob_hash, original_name, mime_type, size_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    source_id,
                    file_info["blobHash"],
                    file_info["originalName"],
                    file_info["mimeType"],
                    file_info["sizeBytes"],
                    now_iso(),
                ),
            )
        return self.source_detail(user_id, source_id)

    def delete_source_file(self, user_id: str, source_id: str, file_id: str) -> tuple[dict[str, Any], str | None]:
        with self.connect() as connection:
            self._assert_source(connection, user_id, source_id)
            file = connection.execute(
                "SELECT blob_hash FROM source_files WHERE id = ? AND source_id = ?", (file_id, source_id)
            ).fetchone()
            if not file:
                raise KeyError("Príloha neexistuje.")
            blob_hash = file["blob_hash"]
            connection.execute("DELETE FROM source_files WHERE id = ? AND source_id = ?", (file_id, source_id))
            still_used = connection.execute("SELECT 1 FROM source_files WHERE blob_hash = ?", (blob_hash,)).fetchone()
        return self.source_detail(user_id, source_id), None if still_used else blob_hash

    def list_source_annotations(self, user_id: str, source_id: str, file_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            self._assert_source(connection, user_id, source_id)
            self._assert_source_file(connection, source_id, file_id)
            rows = connection.execute(
                """
                SELECT sa.*, e.title AS element_title, e.type AS element_type, e.library_id,
                       l.name AS library_name
                FROM source_annotations sa
                LEFT JOIN elements e ON e.id = sa.element_id
                LEFT JOIN libraries l ON l.id = e.library_id
                WHERE sa.source_id = ? AND sa.source_file_id = ?
                ORDER BY sa.updated_at DESC
                """,
                (source_id, file_id),
            ).fetchall()
        return [self._source_annotation_row(row) for row in rows]

    def create_source_annotation(self, user_id: str, source_id: str, file_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Anotácia musí byť objekt.")
        annotation_id = self._clean_id(data.get("id"))
        quote = self._clean_text(data.get("quote"), 10_000)
        locator = self._clean_text(data.get("locator"), 300)
        note = self._clean_text(data.get("note"), 5_000)
        element_id = self._clean_id(data.get("elementId")) or None
        if not annotation_id:
            raise ValidationError("Anotácii chýba identifikátor.")
        if not quote and not note:
            raise ValidationError("Anotácia potrebuje úryvok alebo poznámku.")
        with self.connect() as connection:
            self._assert_source(connection, user_id, source_id)
            self._assert_source_file(connection, source_id, file_id)
            if element_id:
                self._assert_element(connection, user_id, element_id)
            timestamp = now_iso()
            connection.execute(
                """
                INSERT INTO source_annotations(
                    id, source_id, source_file_id, element_id, quote, locator, note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (annotation_id, source_id, file_id, element_id, quote, locator, note, timestamp, timestamp),
            )
        annotations = self.list_source_annotations(user_id, source_id, file_id)
        return next(annotation for annotation in annotations if annotation["id"] == annotation_id)

    def delete_source_annotation(self, user_id: str, source_id: str, file_id: str, annotation_id: str) -> None:
        with self.connect() as connection:
            self._assert_source(connection, user_id, source_id)
            self._assert_source_file(connection, source_id, file_id)
            result = connection.execute(
                "DELETE FROM source_annotations WHERE id = ? AND source_id = ? AND source_file_id = ?",
                (annotation_id, source_id, file_id),
            )
            if result.rowcount != 1:
                raise KeyError("Anotácia neexistuje.")

    def file_for_user(self, user_id: str, file_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT sf.* FROM source_files sf
                JOIN sources s ON s.id = sf.source_id
                WHERE sf.id = ? AND s.user_id = ?
                """,
                (file_id, user_id),
            ).fetchone()
        if not row:
            raise KeyError("Súbor neexistuje.")
        return dict(row)

    def sources_for_element(self, user_id: str, element_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            self._assert_element(connection, user_id, element_id)
            rows = connection.execute(
                """
                SELECT * FROM (
                    SELECT s.id, s.title, s.kind, s.description, s.metadata_json, s.created_at, s.updated_at,
                           es.id AS link_id, es.source_file_id, es.relation_type, es.locator, es.label, es.note,
                           sf.original_name AS source_file_name, es.created_at AS link_created_at
                    FROM element_sources es
                    JOIN sources s ON s.id = es.source_id
                    LEFT JOIN source_files sf ON sf.id = es.source_file_id
                    WHERE es.element_id = ? AND s.user_id = ?

                    UNION ALL

                    SELECT s.id, s.title, s.kind, s.description, s.metadata_json, s.created_at, s.updated_at,
                           sa.id AS link_id, sa.source_file_id, 'annotation' AS relation_type, sa.locator,
                           sa.quote AS label, sa.note, sf.original_name AS source_file_name,
                           sa.created_at AS link_created_at
                    FROM source_annotations sa
                    JOIN sources s ON s.id = sa.source_id
                    JOIN source_files sf ON sf.id = sa.source_file_id
                    WHERE sa.element_id = ? AND s.user_id = ?
                )
                ORDER BY link_created_at DESC
                """,
                (element_id, user_id, element_id, user_id),
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            source = self._source_row(row)
            source["linkId"] = source.pop("link_id")
            source["sourceFileId"] = source.pop("source_file_id")
            source["sourceFileName"] = source.pop("source_file_name") or ""
            source["relationType"] = source.pop("relation_type")
            source.pop("link_created_at", None)
            results.append(source)
        return results

    def sources_for_library(self, user_id: str, library_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            self._assert_library(connection, user_id, library_id)
            rows = connection.execute(
                """
                SELECT s.id, s.title, s.kind, s.description, s.metadata_json, s.created_at, s.updated_at,
                       ls.note, COUNT(DISTINCT sf.id) AS file_count
                FROM library_sources ls
                JOIN sources s ON s.id = ls.source_id
                LEFT JOIN source_files sf ON sf.source_id = s.id
                WHERE ls.library_id = ? AND s.user_id = ?
                GROUP BY s.id
                ORDER BY s.title COLLATE NOCASE
                """,
                (library_id, user_id),
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            source = self._source_row(row)
            source["note"] = source.pop("note")
            results.append(source)
        return results

    def _assert_source(self, connection: sqlite3.Connection, user_id: str, source_id: str) -> None:
        if not connection.execute("SELECT 1 FROM sources WHERE id = ? AND user_id = ?", (source_id, user_id)).fetchone():
            raise KeyError("Zdroj neexistuje.")

    @staticmethod
    def _assert_source_file(connection: sqlite3.Connection, source_id: str, file_id: str) -> None:
        if not connection.execute(
            "SELECT 1 FROM source_files WHERE id = ? AND source_id = ?", (file_id, source_id)
        ).fetchone():
            raise KeyError("Príloha neexistuje.")

    def _source_collection(self, connection: sqlite3.Connection, user_id: str, collection_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT id, parent_id, title, created_at, updated_at FROM source_collections WHERE id = ? AND user_id = ?",
            (collection_id, user_id),
        ).fetchone()
        if not row:
            raise KeyError("Zbierka neexistuje.")
        return row

    def _assert_source_collection(self, connection: sqlite3.Connection, user_id: str, collection_id: str) -> None:
        self._source_collection(connection, user_id, collection_id)

    def _assert_library(self, connection: sqlite3.Connection, user_id: str, library_id: str) -> None:
        if not connection.execute("SELECT 1 FROM libraries WHERE id = ? AND user_id = ?", (library_id, user_id)).fetchone():
            raise KeyError("Knižnica neexistuje.")

    def _assert_element(self, connection: sqlite3.Connection, user_id: str, element_id: str) -> None:
        if not connection.execute(
            """
            SELECT 1 FROM elements e JOIN libraries l ON l.id = e.library_id
            WHERE e.id = ? AND l.user_id = ?
            """,
            (element_id, user_id),
        ).fetchone():
            raise KeyError("Prvok neexistuje.")

    @staticmethod
    def _source_row(row: sqlite3.Row) -> dict[str, Any]:
        source = dict(row)
        source.pop("user_id", None)
        metadata_json = source.pop("metadata_json", "{}")
        try:
            source["metadata"] = json.loads(metadata_json)
        except json.JSONDecodeError:
            source["metadata"] = {}
        source["createdAt"] = source.pop("created_at")
        source["updatedAt"] = source.pop("updated_at")
        if "library_count" in source:
            source["libraryCount"] = source.pop("library_count")
        if "element_count" in source:
            source["elementCount"] = source.pop("element_count")
        if "file_count" in source:
            source["fileCount"] = source.pop("file_count")
        if "collection_count" in source:
            source["collectionCount"] = source.pop("collection_count")
        return source

    @staticmethod
    def _source_collection_row(row: sqlite3.Row) -> dict[str, Any]:
        collection = dict(row)
        collection["parentId"] = collection.pop("parent_id") or ""
        collection["createdAt"] = collection.pop("created_at")
        collection["updatedAt"] = collection.pop("updated_at")
        if "child_count" in collection:
            collection["childCount"] = collection.pop("child_count")
        if "source_count" in collection:
            collection["sourceCount"] = collection.pop("source_count")
        return collection

    @staticmethod
    def _source_annotation_row(row: sqlite3.Row) -> dict[str, Any]:
        annotation = dict(row)
        annotation["sourceId"] = annotation.pop("source_id")
        annotation["sourceFileId"] = annotation.pop("source_file_id")
        annotation["sourceFileName"] = annotation.pop("source_file_name", "") or ""
        annotation["elementId"] = annotation.pop("element_id") or ""
        annotation["elementTitle"] = annotation.pop("element_title") or ""
        annotation["elementType"] = annotation.pop("element_type") or ""
        annotation["libraryId"] = annotation.pop("library_id") or ""
        annotation["libraryName"] = annotation.pop("library_name") or ""
        annotation["createdAt"] = annotation.pop("created_at")
        annotation["updatedAt"] = annotation.pop("updated_at")
        return annotation
