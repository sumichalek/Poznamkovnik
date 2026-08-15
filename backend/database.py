from __future__ import annotations

import html
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .tutorial_content import C_EXAMPLES, C_LANGUAGE, C_PAGES


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ValidationError(ValueError):
    """Dáta z klienta nemajú očakávaný tvar."""


DEFAULT_MAIN_PANEL_TRANSPARENCY = 20
DEFAULT_WORKSPACE_PANEL_TRANSPARENCY = 24
DEFAULT_EDITOR_SURFACE_TRANSPARENCY = 12
DEFAULT_MUSIC_PANEL_TRANSPARENCY = 12
DEFAULT_SOURCE_FILE_MAX_BYTES = 100 * 1024 * 1024
MIN_SOURCE_FILE_MAX_BYTES = 1 * 1024 * 1024
MAX_SOURCE_FILE_MAX_BYTES = 1024 * 1024 * 1024
DEFAULT_MUSIC_TRACK_MAX_BYTES = 250 * 1024 * 1024
MIN_MUSIC_TRACK_MAX_BYTES = 1 * 1024 * 1024
MAX_MUSIC_TRACK_MAX_BYTES = 1024 * 1024 * 1024
DEFAULT_AUTOMATIC_BACKUP_ENABLED = True
DEFAULT_AUTOMATIC_BACKUP_INTERVAL_HOURS = 24
DEFAULT_AUTOMATIC_BACKUP_RETENTION_COUNT = 14
AUTOMATIC_BACKUP_INTERVAL_HOURS = {6, 24, 168}
MIN_AUTOMATIC_BACKUP_RETENTION_COUNT = 3
MAX_AUTOMATIC_BACKUP_RETENTION_COUNT = 50
SEARCH_INDEX_VERSION = "2"
MAX_TAGS_PER_ITEM = 20
MAX_TAG_LENGTH = 48
TASK_STATUSES = {"open", "in_progress", "done"}
TASK_PRIORITIES = {"none", "low", "medium", "high"}
TASK_TARGET_TYPES = {"library", "element", "source"}
SEMANTIC_TARGET_TYPES = {"element", "source", "tutorial_page", "task", "calendar_event"}
BACKUP_RECORD_LIMITS = {
    "libraries": 500,
    "elements": 10_000,
    "sources": 10_000,
    "sourceCollections": 10_000,
    "collectionSources": 50_000,
    "sourceFiles": 50_000,
    "musicTracks": 20_000,
    "musicPlaylists": 5_000,
    "musicPlaylistTracks": 100_000,
    "sourceAnnotations": 50_000,
    "librarySources": 50_000,
    "elementSources": 50_000,
    "tasks": 20_000,
    "taskLinks": 50_000,
    "calendarEvents": 20_000,
    "calendarEventLinks": 50_000,
    "semanticLinks": 50_000,
    "tutorialLanguages": 20,
    "tutorialPages": 2_000,
    "tutorialExamples": 5_000,
    "tutorialNotes": 5_000,
    "tutorialExampleDrafts": 5_000,
}


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.search_available = False
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
                    music_panel_transparency INTEGER NOT NULL DEFAULT 12,
                    source_file_max_bytes INTEGER NOT NULL DEFAULT 104857600,
                    music_track_max_bytes INTEGER NOT NULL DEFAULT 262144000,
                    automatic_backup_enabled INTEGER NOT NULL DEFAULT 1,
                    automatic_backup_interval_hours INTEGER NOT NULL DEFAULT 24,
                    automatic_backup_retention_count INTEGER NOT NULL DEFAULT 14,
                    last_auto_backup_at TEXT NOT NULL DEFAULT '',
                    last_auto_backup_attempt_at TEXT NOT NULL DEFAULT '',
                    last_auto_backup_error TEXT NOT NULL DEFAULT '',
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
                    tags_json TEXT NOT NULL DEFAULT '[]',
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
                    tags_json TEXT NOT NULL DEFAULT '[]',
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
                    tags_json TEXT NOT NULL DEFAULT '[]',
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

                CREATE TABLE IF NOT EXISTS music_tracks (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    blob_hash TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL DEFAULT '',
                    album TEXT NOT NULL DEFAULT '',
                    release_year TEXT NOT NULL DEFAULT '',
                    track_number TEXT NOT NULL DEFAULT '',
                    genre TEXT NOT NULL DEFAULT '',
                    duration_seconds REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS music_tracks_user_idx ON music_tracks(user_id, title COLLATE NOCASE, created_at DESC);
                CREATE INDEX IF NOT EXISTS music_tracks_blob_idx ON music_tracks(blob_hash);

                CREATE TABLE IF NOT EXISTS music_playlists (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS music_playlists_user_idx ON music_playlists(user_id, title COLLATE NOCASE);

                CREATE TABLE IF NOT EXISTS music_playlist_tracks (
                    playlist_id TEXT NOT NULL REFERENCES music_playlists(id) ON DELETE CASCADE,
                    track_id TEXT NOT NULL REFERENCES music_tracks(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL DEFAULT 0,
                    added_at TEXT NOT NULL,
                    PRIMARY KEY(playlist_id, track_id)
                );
                CREATE INDEX IF NOT EXISTS music_playlist_tracks_order_idx
                    ON music_playlist_tracks(playlist_id, position, added_at);

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

                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'in_progress', 'done')),
                    priority TEXT NOT NULL DEFAULT 'none' CHECK(priority IN ('none', 'low', 'medium', 'high')),
                    due_date TEXT NOT NULL DEFAULT '',
                    completed_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS tasks_user_status_idx ON tasks(user_id, status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS task_links (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    target_type TEXT NOT NULL CHECK(target_type IN ('library', 'element', 'source')),
                    target_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(task_id, target_type, target_id)
                );
                CREATE INDEX IF NOT EXISTS task_links_task_idx ON task_links(task_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS task_links_target_idx ON task_links(target_type, target_id);

                CREATE TABLE IF NOT EXISTS calendar_events (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    all_day INTEGER NOT NULL DEFAULT 1 CHECK(all_day IN (0, 1)),
                    start_date TEXT NOT NULL,
                    start_time TEXT NOT NULL DEFAULT '',
                    end_date TEXT NOT NULL,
                    end_time TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS calendar_events_user_date_idx
                    ON calendar_events(user_id, start_date, end_date, updated_at DESC);

                CREATE TABLE IF NOT EXISTS calendar_event_links (
                    id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL REFERENCES calendar_events(id) ON DELETE CASCADE,
                    target_type TEXT NOT NULL CHECK(target_type IN ('library', 'element', 'source')),
                    target_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(event_id, target_type, target_id)
                );
                CREATE INDEX IF NOT EXISTS calendar_event_links_event_idx
                    ON calendar_event_links(event_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS calendar_event_links_target_idx
                    ON calendar_event_links(target_type, target_id);

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

                CREATE TABLE IF NOT EXISTS semantic_links (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    first_type TEXT NOT NULL CHECK(first_type IN ('element', 'source', 'tutorial_page', 'task', 'calendar_event')),
                    first_id TEXT NOT NULL,
                    second_type TEXT NOT NULL CHECK(second_type IN ('element', 'source', 'tutorial_page', 'task', 'calendar_event')),
                    second_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL DEFAULT 'related',
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, first_type, first_id, second_type, second_id)
                );
                CREATE INDEX IF NOT EXISTS semantic_links_first_idx ON semantic_links(user_id, first_type, first_id);
                CREATE INDEX IF NOT EXISTS semantic_links_second_idx ON semantic_links(user_id, second_type, second_id);

                CREATE TABLE IF NOT EXISTS tutorial_languages (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    code TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, code)
                );
                CREATE INDEX IF NOT EXISTS tutorial_languages_user_idx ON tutorial_languages(user_id, title);

                CREATE TABLE IF NOT EXISTS tutorial_pages (
                    id TEXT PRIMARY KEY,
                    language_id TEXT NOT NULL REFERENCES tutorial_languages(id) ON DELETE CASCADE,
                    parent_id TEXT REFERENCES tutorial_pages(id) ON DELETE CASCADE,
                    origin TEXT NOT NULL DEFAULT 'builtin' CHECK(origin IN ('builtin', 'custom')),
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    content_json TEXT NOT NULL DEFAULT '{}',
                    position INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS tutorial_pages_language_idx
                    ON tutorial_pages(language_id, parent_id, position, title);

                CREATE TABLE IF NOT EXISTS tutorial_examples (
                    id TEXT PRIMARY KEY,
                    page_id TEXT NOT NULL REFERENCES tutorial_pages(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL,
                    stdin TEXT NOT NULL DEFAULT '',
                    standard TEXT NOT NULL DEFAULT 'c17',
                    position INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS tutorial_examples_page_idx
                    ON tutorial_examples(page_id, position, title);

                CREATE TABLE IF NOT EXISTS tutorial_notes (
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    page_id TEXT NOT NULL REFERENCES tutorial_pages(id) ON DELETE CASCADE,
                    content TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, page_id)
                );

                CREATE TABLE IF NOT EXISTS tutorial_example_drafts (
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    example_id TEXT NOT NULL REFERENCES tutorial_examples(id) ON DELETE CASCADE,
                    source TEXT NOT NULL DEFAULT '',
                    stdin TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, example_id)
                );
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
            if "music_panel_transparency" not in columns:
                connection.execute(
                    "ALTER TABLE user_preferences ADD COLUMN music_panel_transparency INTEGER NOT NULL DEFAULT 12"
                )
            if "source_file_max_bytes" not in columns:
                connection.execute(
                    "ALTER TABLE user_preferences ADD COLUMN source_file_max_bytes INTEGER NOT NULL DEFAULT 104857600"
                )
            if "music_track_max_bytes" not in columns:
                connection.execute(
                    "ALTER TABLE user_preferences ADD COLUMN music_track_max_bytes INTEGER NOT NULL DEFAULT 262144000"
                )
            if "automatic_backup_enabled" not in columns:
                connection.execute(
                    "ALTER TABLE user_preferences ADD COLUMN automatic_backup_enabled INTEGER NOT NULL DEFAULT 1"
                )
            if "automatic_backup_interval_hours" not in columns:
                connection.execute(
                    "ALTER TABLE user_preferences ADD COLUMN automatic_backup_interval_hours INTEGER NOT NULL DEFAULT 24"
                )
            if "automatic_backup_retention_count" not in columns:
                connection.execute(
                    "ALTER TABLE user_preferences ADD COLUMN automatic_backup_retention_count INTEGER NOT NULL DEFAULT 14"
                )
            if "last_auto_backup_at" not in columns:
                connection.execute("ALTER TABLE user_preferences ADD COLUMN last_auto_backup_at TEXT NOT NULL DEFAULT ''")
            if "last_auto_backup_attempt_at" not in columns:
                connection.execute(
                    "ALTER TABLE user_preferences ADD COLUMN last_auto_backup_attempt_at TEXT NOT NULL DEFAULT ''"
                )
            if "last_auto_backup_error" not in columns:
                connection.execute("ALTER TABLE user_preferences ADD COLUMN last_auto_backup_error TEXT NOT NULL DEFAULT ''")
            library_columns = {row["name"] for row in connection.execute("PRAGMA table_info(libraries)")}
            if "tags_json" not in library_columns:
                connection.execute("ALTER TABLE libraries ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'")
            element_columns = {row["name"] for row in connection.execute("PRAGMA table_info(elements)")}
            if "tags_json" not in element_columns:
                connection.execute("ALTER TABLE elements ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'")
            source_columns = {row["name"] for row in connection.execute("PRAGMA table_info(sources)")}
            if "tags_json" not in source_columns:
                connection.execute("ALTER TABLE sources ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'")
            task_columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
            if "tags_json" not in task_columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'")
            calendar_event_columns = {row["name"] for row in connection.execute("PRAGMA table_info(calendar_events)")}
            if "tags_json" not in calendar_event_columns:
                connection.execute("ALTER TABLE calendar_events ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'")
            music_track_columns = {row["name"] for row in connection.execute("PRAGMA table_info(music_tracks)")}
            if "release_year" not in music_track_columns:
                connection.execute("ALTER TABLE music_tracks ADD COLUMN release_year TEXT NOT NULL DEFAULT ''")
            if "track_number" not in music_track_columns:
                connection.execute("ALTER TABLE music_tracks ADD COLUMN track_number TEXT NOT NULL DEFAULT ''")
            if "genre" not in music_track_columns:
                connection.execute("ALTER TABLE music_tracks ADD COLUMN genre TEXT NOT NULL DEFAULT ''")
            tutorial_page_columns = {row["name"] for row in connection.execute("PRAGMA table_info(tutorial_pages)")}
            if "origin" not in tutorial_page_columns:
                connection.execute("ALTER TABLE tutorial_pages ADD COLUMN origin TEXT NOT NULL DEFAULT 'builtin'")
            self._initialize_search_index(connection)

    def _initialize_search_index(self, connection: sqlite3.Connection) -> None:
        try:
            connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS global_search_index
                USING fts5(
                    user_id UNINDEXED,
                    item_type UNINDEXED,
                    item_id UNINDEXED,
                    context_id UNINDEXED,
                    title,
                    content,
                    tokenize = 'unicode61 remove_diacritics 2'
                )
                """
            )
        except sqlite3.OperationalError:
            self.search_available = False
            return

        self.search_available = True
        connection.execute(
            "CREATE TABLE IF NOT EXISTS global_search_index_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        state = connection.execute(
            "SELECT value FROM global_search_index_state WHERE key = 'version'"
        ).fetchone()
        rebuild_required = not state or state["value"] != SEARCH_INDEX_VERSION
        if rebuild_required:
            self._drop_search_triggers(connection)
        connection.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS global_search_libraries_ai AFTER INSERT ON libraries BEGIN
                INSERT INTO global_search_index VALUES (new.user_id, 'library', new.id, '', new.name, new.tags_json);
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_libraries_au AFTER UPDATE ON libraries BEGIN
                DELETE FROM global_search_index WHERE item_type = 'library' AND item_id = old.id;
                INSERT INTO global_search_index VALUES (new.user_id, 'library', new.id, '', new.name, new.tags_json);
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_libraries_ad AFTER DELETE ON libraries BEGIN
                DELETE FROM global_search_index WHERE item_type = 'library' AND item_id = old.id;
            END;

            CREATE TRIGGER IF NOT EXISTS global_search_elements_ai AFTER INSERT ON elements BEGIN
                INSERT INTO global_search_index
                SELECT l.user_id, new.type, new.id, new.library_id, new.title, new.content || ' ' || new.tags_json
                FROM libraries l WHERE l.id = new.library_id;
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_elements_au AFTER UPDATE ON elements BEGIN
                DELETE FROM global_search_index WHERE item_type = old.type AND item_id = old.id;
                INSERT INTO global_search_index
                SELECT l.user_id, new.type, new.id, new.library_id, new.title, new.content || ' ' || new.tags_json
                FROM libraries l WHERE l.id = new.library_id;
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_elements_ad AFTER DELETE ON elements BEGIN
                DELETE FROM global_search_index WHERE item_type = old.type AND item_id = old.id;
            END;

            CREATE TRIGGER IF NOT EXISTS global_search_sources_ai AFTER INSERT ON sources BEGIN
                INSERT INTO global_search_index VALUES (new.user_id, 'source', new.id, new.id, new.title, new.description || ' ' || new.metadata_json || ' ' || new.tags_json);
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_sources_au AFTER UPDATE ON sources BEGIN
                DELETE FROM global_search_index WHERE item_type = 'source' AND item_id = old.id;
                INSERT INTO global_search_index VALUES (new.user_id, 'source', new.id, new.id, new.title, new.description || ' ' || new.metadata_json || ' ' || new.tags_json);
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_sources_ad AFTER DELETE ON sources BEGIN
                DELETE FROM global_search_index WHERE item_type = 'source' AND item_id = old.id;
            END;

            CREATE TRIGGER IF NOT EXISTS global_search_source_collections_ai AFTER INSERT ON source_collections BEGIN
                INSERT INTO global_search_index VALUES (new.user_id, 'source_collection', new.id, new.id, new.title, '');
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_source_collections_au AFTER UPDATE ON source_collections BEGIN
                DELETE FROM global_search_index WHERE item_type = 'source_collection' AND item_id = old.id;
                INSERT INTO global_search_index VALUES (new.user_id, 'source_collection', new.id, new.id, new.title, '');
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_source_collections_ad AFTER DELETE ON source_collections BEGIN
                DELETE FROM global_search_index WHERE item_type = 'source_collection' AND item_id = old.id;
            END;

            CREATE TRIGGER IF NOT EXISTS global_search_source_files_ai AFTER INSERT ON source_files BEGIN
                INSERT INTO global_search_index
                SELECT s.user_id, 'source_file', new.id, new.source_id, new.original_name, new.mime_type
                FROM sources s WHERE s.id = new.source_id;
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_source_files_au AFTER UPDATE ON source_files BEGIN
                DELETE FROM global_search_index WHERE item_type = 'source_file' AND item_id = old.id;
                INSERT INTO global_search_index
                SELECT s.user_id, 'source_file', new.id, new.source_id, new.original_name, new.mime_type
                FROM sources s WHERE s.id = new.source_id;
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_source_files_ad AFTER DELETE ON source_files BEGIN
                DELETE FROM global_search_index WHERE item_type = 'source_file' AND item_id = old.id;
            END;

            CREATE TRIGGER IF NOT EXISTS global_search_music_tracks_ai AFTER INSERT ON music_tracks BEGIN
                INSERT INTO global_search_index VALUES (new.user_id, 'music_track', new.id, new.id, new.title, new.artist || ' ' || new.album || ' ' || new.genre || ' ' || new.original_name);
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_music_tracks_au AFTER UPDATE ON music_tracks BEGIN
                DELETE FROM global_search_index WHERE item_type = 'music_track' AND item_id = old.id;
                INSERT INTO global_search_index VALUES (new.user_id, 'music_track', new.id, new.id, new.title, new.artist || ' ' || new.album || ' ' || new.genre || ' ' || new.original_name);
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_music_tracks_ad AFTER DELETE ON music_tracks BEGIN
                DELETE FROM global_search_index WHERE item_type = 'music_track' AND item_id = old.id;
            END;

            CREATE TRIGGER IF NOT EXISTS global_search_music_playlists_ai AFTER INSERT ON music_playlists BEGIN
                INSERT INTO global_search_index VALUES (new.user_id, 'music_playlist', new.id, new.id, new.title, '');
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_music_playlists_au AFTER UPDATE ON music_playlists BEGIN
                DELETE FROM global_search_index WHERE item_type = 'music_playlist' AND item_id = old.id;
                INSERT INTO global_search_index VALUES (new.user_id, 'music_playlist', new.id, new.id, new.title, '');
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_music_playlists_ad AFTER DELETE ON music_playlists BEGIN
                DELETE FROM global_search_index WHERE item_type = 'music_playlist' AND item_id = old.id;
            END;

            CREATE TRIGGER IF NOT EXISTS global_search_tasks_ai AFTER INSERT ON tasks BEGIN
                INSERT INTO global_search_index VALUES (new.user_id, 'task', new.id, new.id, new.title, new.description || ' ' || new.tags_json);
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_tasks_au AFTER UPDATE ON tasks BEGIN
                DELETE FROM global_search_index WHERE item_type = 'task' AND item_id = old.id;
                INSERT INTO global_search_index VALUES (new.user_id, 'task', new.id, new.id, new.title, new.description || ' ' || new.tags_json);
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_tasks_ad AFTER DELETE ON tasks BEGIN
                DELETE FROM global_search_index WHERE item_type = 'task' AND item_id = old.id;
            END;

            CREATE TRIGGER IF NOT EXISTS global_search_calendar_events_ai AFTER INSERT ON calendar_events BEGIN
                INSERT INTO global_search_index VALUES (new.user_id, 'calendar_event', new.id, new.id, new.title, new.description || ' ' || new.tags_json);
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_calendar_events_au AFTER UPDATE ON calendar_events BEGIN
                DELETE FROM global_search_index WHERE item_type = 'calendar_event' AND item_id = old.id;
                INSERT INTO global_search_index VALUES (new.user_id, 'calendar_event', new.id, new.id, new.title, new.description || ' ' || new.tags_json);
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_calendar_events_ad AFTER DELETE ON calendar_events BEGIN
                DELETE FROM global_search_index WHERE item_type = 'calendar_event' AND item_id = old.id;
            END;

            CREATE TRIGGER IF NOT EXISTS global_search_tutorial_languages_ai AFTER INSERT ON tutorial_languages BEGIN
                INSERT INTO global_search_index VALUES (new.user_id, 'tutorial_language', new.id, new.id, new.title, new.summary);
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_tutorial_languages_au AFTER UPDATE ON tutorial_languages BEGIN
                DELETE FROM global_search_index WHERE item_type = 'tutorial_language' AND item_id = old.id;
                INSERT INTO global_search_index VALUES (new.user_id, 'tutorial_language', new.id, new.id, new.title, new.summary);
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_tutorial_languages_ad AFTER DELETE ON tutorial_languages BEGIN
                DELETE FROM global_search_index WHERE item_type = 'tutorial_language' AND item_id = old.id;
            END;

            CREATE TRIGGER IF NOT EXISTS global_search_tutorial_pages_ai AFTER INSERT ON tutorial_pages BEGIN
                INSERT INTO global_search_index
                SELECT l.user_id, 'tutorial_page', new.id, new.language_id, new.title, new.summary || ' ' || new.content_json
                FROM tutorial_languages l WHERE l.id = new.language_id;
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_tutorial_pages_au AFTER UPDATE ON tutorial_pages BEGIN
                DELETE FROM global_search_index WHERE item_type = 'tutorial_page' AND item_id = old.id;
                INSERT INTO global_search_index
                SELECT l.user_id, 'tutorial_page', new.id, new.language_id, new.title, new.summary || ' ' || new.content_json
                FROM tutorial_languages l WHERE l.id = new.language_id;
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_tutorial_pages_ad AFTER DELETE ON tutorial_pages BEGIN
                DELETE FROM global_search_index WHERE item_type = 'tutorial_page' AND item_id = old.id;
            END;

            CREATE TRIGGER IF NOT EXISTS global_search_tutorial_examples_ai AFTER INSERT ON tutorial_examples BEGIN
                INSERT INTO global_search_index
                SELECT l.user_id, 'tutorial_example', new.id, p.language_id, new.title, new.description || ' ' || new.source
                FROM tutorial_pages p JOIN tutorial_languages l ON l.id = p.language_id WHERE p.id = new.page_id;
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_tutorial_examples_au AFTER UPDATE ON tutorial_examples BEGIN
                DELETE FROM global_search_index WHERE item_type = 'tutorial_example' AND item_id = old.id;
                INSERT INTO global_search_index
                SELECT l.user_id, 'tutorial_example', new.id, p.language_id, new.title, new.description || ' ' || new.source
                FROM tutorial_pages p JOIN tutorial_languages l ON l.id = p.language_id WHERE p.id = new.page_id;
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_tutorial_examples_ad AFTER DELETE ON tutorial_examples BEGIN
                DELETE FROM global_search_index WHERE item_type = 'tutorial_example' AND item_id = old.id;
            END;

            CREATE TRIGGER IF NOT EXISTS global_search_tutorial_notes_ai AFTER INSERT ON tutorial_notes BEGIN
                INSERT INTO global_search_index
                SELECT new.user_id, 'tutorial_note', new.page_id, p.language_id, p.title, new.content
                FROM tutorial_pages p WHERE p.id = new.page_id;
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_tutorial_notes_au AFTER UPDATE ON tutorial_notes BEGIN
                DELETE FROM global_search_index WHERE item_type = 'tutorial_note' AND item_id = old.page_id AND user_id = old.user_id;
                INSERT INTO global_search_index
                SELECT new.user_id, 'tutorial_note', new.page_id, p.language_id, p.title, new.content
                FROM tutorial_pages p WHERE p.id = new.page_id;
            END;
            CREATE TRIGGER IF NOT EXISTS global_search_tutorial_notes_ad AFTER DELETE ON tutorial_notes BEGIN
                DELETE FROM global_search_index WHERE item_type = 'tutorial_note' AND item_id = old.page_id AND user_id = old.user_id;
            END;
            """
        )
        if rebuild_required:
            self._rebuild_search_index(connection)
            connection.execute(
                "INSERT INTO global_search_index_state(key, value) VALUES ('version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (SEARCH_INDEX_VERSION,),
            )

    @staticmethod
    def _drop_search_triggers(connection: sqlite3.Connection) -> None:
        tables = (
            "libraries",
            "elements",
            "sources",
            "source_collections",
            "source_files",
            "music_tracks",
            "music_playlists",
            "tasks",
            "calendar_events",
            "tutorial_languages",
            "tutorial_pages",
            "tutorial_examples",
            "tutorial_notes",
        )
        for table in tables:
            for suffix in ("ai", "au", "ad"):
                connection.execute(f"DROP TRIGGER IF EXISTS global_search_{table}_{suffix}")

    @staticmethod
    def _rebuild_search_index(connection: sqlite3.Connection) -> None:
        connection.execute("DELETE FROM global_search_index")
        connection.executescript(
            """
            INSERT INTO global_search_index
            SELECT user_id, 'library', id, '', name, tags_json FROM libraries;
            INSERT INTO global_search_index
            SELECT l.user_id, e.type, e.id, e.library_id, e.title, e.content || ' ' || e.tags_json
            FROM elements e JOIN libraries l ON l.id = e.library_id;
            INSERT INTO global_search_index
            SELECT user_id, 'source', id, id, title, description || ' ' || metadata_json || ' ' || tags_json FROM sources;
            INSERT INTO global_search_index
            SELECT user_id, 'source_collection', id, id, title, '' FROM source_collections;
            INSERT INTO global_search_index
            SELECT s.user_id, 'source_file', f.id, f.source_id, f.original_name, f.mime_type
            FROM source_files f JOIN sources s ON s.id = f.source_id;
            INSERT INTO global_search_index
            SELECT user_id, 'music_track', id, id, title, artist || ' ' || album || ' ' || genre || ' ' || original_name FROM music_tracks;
            INSERT INTO global_search_index
            SELECT user_id, 'music_playlist', id, id, title, '' FROM music_playlists;
            INSERT INTO global_search_index
            SELECT user_id, 'task', id, id, title, description || ' ' || tags_json FROM tasks;
            INSERT INTO global_search_index
            SELECT user_id, 'calendar_event', id, id, title, description || ' ' || tags_json FROM calendar_events;
            INSERT INTO global_search_index
            SELECT user_id, 'tutorial_language', id, id, title, summary FROM tutorial_languages;
            INSERT INTO global_search_index
            SELECT l.user_id, 'tutorial_page', p.id, p.language_id, p.title, p.summary || ' ' || p.content_json
            FROM tutorial_pages p JOIN tutorial_languages l ON l.id = p.language_id;
            INSERT INTO global_search_index
            SELECT l.user_id, 'tutorial_example', e.id, p.language_id, e.title, e.description || ' ' || e.source
            FROM tutorial_examples e
            JOIN tutorial_pages p ON p.id = e.page_id
            JOIN tutorial_languages l ON l.id = p.language_id;
            INSERT INTO global_search_index
            SELECT n.user_id, 'tutorial_note', n.page_id, p.language_id, p.title, n.content
            FROM tutorial_notes n JOIN tutorial_pages p ON p.id = n.page_id;
            """
        )

    def global_search(self, user_id: str, query: Any, limit: int = 60) -> list[dict[str, Any]]:
        expression = self._search_expression(query)
        if not expression or not self.search_available:
            return []
        maximum = min(100, max(1, int(limit)))
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT item_type, item_id, context_id, title,
                       snippet(global_search_index, 5, '', '', '...', 18) AS preview
                FROM global_search_index
                WHERE user_id = ? AND global_search_index MATCH ?
                ORDER BY bm25(global_search_index), title COLLATE NOCASE
                LIMIT ?
                """,
                (user_id, expression, maximum),
            ).fetchall()
            example_ids = [row["item_id"] for row in rows if row["item_type"] == "tutorial_example"]
            example_page_ids: dict[str, str] = {}
            if example_ids:
                placeholders = ", ".join("?" for _ in example_ids)
                example_rows = connection.execute(
                    f"SELECT id, page_id FROM tutorial_examples WHERE id IN ({placeholders})",
                    example_ids,
                ).fetchall()
                example_page_ids = {row["id"]: row["page_id"] for row in example_rows}
        return [
            {
                "type": row["item_type"],
                "id": row["item_id"],
                "contextId": row["context_id"],
                "targetId": (
                    row["context_id"]
                    if row["item_type"] == "source_file"
                    else example_page_ids.get(row["item_id"], row["item_id"])
                ),
                "title": self._plain_search_text(row["title"]) or "Bez názvu",
                "preview": self._plain_search_text(row["preview"]),
            }
            for row in rows
        ]

    def list_tags(self, user_id: str, query: Any = "", limit: int = 60) -> list[dict[str, Any]]:
        search = self._clean_text(query, MAX_TAG_LENGTH).casefold()
        maximum = min(100, max(1, int(limit)))
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT tags_json FROM libraries WHERE user_id = ?
                UNION ALL SELECT e.tags_json FROM elements e JOIN libraries l ON l.id = e.library_id WHERE l.user_id = ?
                UNION ALL SELECT tags_json FROM sources WHERE user_id = ?
                UNION ALL SELECT tags_json FROM tasks WHERE user_id = ?
                UNION ALL SELECT tags_json FROM calendar_events WHERE user_id = ?
                """,
                (user_id, user_id, user_id, user_id, user_id),
            ).fetchall()

        tags: dict[str, dict[str, Any]] = {}
        for row in rows:
            for tag in self._tags_from_json(row["tags_json"]):
                key = tag.casefold()
                if search and search not in key:
                    continue
                entry = tags.setdefault(key, {"name": tag, "count": 0})
                entry["count"] += 1
        return sorted(tags.values(), key=lambda item: (-item["count"], item["name"].casefold()))[:maximum]

    @staticmethod
    def _search_expression(query: Any) -> str:
        terms = re.findall(r"[^\W_]+", str(query or "")[:400].lower(), flags=re.UNICODE)
        return " AND ".join(f"{term}*" for term in terms[:8])

    @staticmethod
    def _plain_search_text(value: Any) -> str:
        text = html.unescape(str(value or ""))
        text = re.sub(r"<[^>]*>", " ", text)
        text = re.sub(r"[{}\[\]\\\"\",:]", " ", text)
        return re.sub(r"\s+", " ", text).strip()[:420]

    @staticmethod
    def _clean_tags(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        tags: list[str] = []
        seen: set[str] = set()
        for item in value:
            tag = re.sub(r"\s+", " ", str(item or "").strip().lstrip("#"))[:MAX_TAG_LENGTH]
            key = tag.casefold()
            if not tag or key in seen:
                continue
            seen.add(key)
            tags.append(tag)
            if len(tags) == MAX_TAGS_PER_ITEM:
                break
        return tags

    @classmethod
    def _tags_json(cls, value: Any) -> str:
        return json.dumps(cls._clean_tags(value), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def _tags_from_json(cls, value: Any) -> list[str]:
        try:
            return cls._clean_tags(json.loads(str(value or "[]")))
        except (TypeError, json.JSONDecodeError):
            return []

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
                SELECT main_panel_transparency, workspace_panel_transparency, editor_surface_transparency,
                       music_panel_transparency,
                       source_file_max_bytes, music_track_max_bytes
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
            "musicPanelTransparency": (
                int(row["music_panel_transparency"]) if row else DEFAULT_MUSIC_PANEL_TRANSPARENCY
            ),
            "sourceFileMaxBytes": int(row["source_file_max_bytes"]) if row else DEFAULT_SOURCE_FILE_MAX_BYTES,
            "musicTrackMaxBytes": int(row["music_track_max_bytes"]) if row else DEFAULT_MUSIC_TRACK_MAX_BYTES,
        }

    def source_file_max_bytes(self, user_id: str) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT source_file_max_bytes FROM user_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return int(row["source_file_max_bytes"]) if row else DEFAULT_SOURCE_FILE_MAX_BYTES

    def music_track_max_bytes(self, user_id: str) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT music_track_max_bytes FROM user_preferences WHERE user_id = ?", (user_id,)
            ).fetchone()
        return int(row["music_track_max_bytes"]) if row else DEFAULT_MUSIC_TRACK_MAX_BYTES

    def automatic_backup_preferences(self, user_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT automatic_backup_enabled, automatic_backup_interval_hours,
                       automatic_backup_retention_count, last_auto_backup_at,
                       last_auto_backup_attempt_at, last_auto_backup_error
                FROM user_preferences WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if not row:
            return {
                "enabled": DEFAULT_AUTOMATIC_BACKUP_ENABLED,
                "intervalHours": DEFAULT_AUTOMATIC_BACKUP_INTERVAL_HOURS,
                "retentionCount": DEFAULT_AUTOMATIC_BACKUP_RETENTION_COUNT,
                "lastBackupAt": "",
                "lastAttemptAt": "",
                "lastError": "",
            }
        return {
            "enabled": bool(row["automatic_backup_enabled"]),
            "intervalHours": int(row["automatic_backup_interval_hours"]),
            "retentionCount": int(row["automatic_backup_retention_count"]),
            "lastBackupAt": str(row["last_auto_backup_at"]),
            "lastAttemptAt": str(row["last_auto_backup_attempt_at"]),
            "lastError": str(row["last_auto_backup_error"]),
        }

    def save_automatic_backup_preferences(self, user_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Nastavenia automatického zálohovania musia byť objekt.")
        current = self.automatic_backup_preferences(user_id)
        enabled = data.get("enabled", current["enabled"])
        if not isinstance(enabled, bool):
            raise ValidationError("Automatické zálohovanie musí byť zapnuté alebo vypnuté.")
        interval_hours = self._preference_int(
            data.get("intervalHours", current["intervalHours"]), "Interval automatickej zálohy", 1, 168
        )
        if interval_hours not in AUTOMATIC_BACKUP_INTERVAL_HOURS:
            raise ValidationError("Interval automatickej zálohy môže byť 6 hodín, 1 deň alebo 1 týždeň.")
        retention_count = self._preference_int(
            data.get("retentionCount", current["retentionCount"]),
            "Počet automatických záloh",
            MIN_AUTOMATIC_BACKUP_RETENTION_COUNT,
            MAX_AUTOMATIC_BACKUP_RETENTION_COUNT,
        )
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO user_preferences(
                    user_id, automatic_backup_enabled, automatic_backup_interval_hours,
                    automatic_backup_retention_count, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    automatic_backup_enabled = excluded.automatic_backup_enabled,
                    automatic_backup_interval_hours = excluded.automatic_backup_interval_hours,
                    automatic_backup_retention_count = excluded.automatic_backup_retention_count,
                    updated_at = excluded.updated_at
                """,
                (user_id, int(enabled), interval_hours, retention_count, now_iso()),
            )
        return self.automatic_backup_preferences(user_id)

    def automatic_backup_candidates(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT u.id, u.username,
                       COALESCE(p.automatic_backup_enabled, 1) AS automatic_backup_enabled,
                       COALESCE(p.automatic_backup_interval_hours, 24) AS automatic_backup_interval_hours,
                       COALESCE(p.automatic_backup_retention_count, 14) AS automatic_backup_retention_count,
                       COALESCE(p.last_auto_backup_at, '') AS last_auto_backup_at,
                       COALESCE(p.last_auto_backup_attempt_at, '') AS last_auto_backup_attempt_at
                FROM users u
                LEFT JOIN user_preferences p ON p.user_id = u.id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def record_automatic_backup_result(self, user_id: str, *, succeeded: bool, error: str = "") -> None:
        timestamp = now_iso()
        with self.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO user_preferences(user_id, updated_at) VALUES (?, ?)",
                (user_id, timestamp),
            )
            if succeeded:
                connection.execute(
                    """
                    UPDATE user_preferences
                    SET last_auto_backup_at = ?, last_auto_backup_attempt_at = ?, last_auto_backup_error = '', updated_at = ?
                    WHERE user_id = ?
                    """,
                    (timestamp, timestamp, timestamp, user_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE user_preferences
                    SET last_auto_backup_attempt_at = ?, last_auto_backup_error = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (timestamp, str(error).strip()[:600], timestamp, user_id),
                )

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
        music_panel_transparency = self._preference_int(
            data.get("musicPanelTransparency", current["musicPanelTransparency"]),
            "Priehľadnosť prehrávača",
            0,
            65,
        )
        source_file_max_bytes = self._preference_int(
            data.get("sourceFileMaxBytes", current["sourceFileMaxBytes"]),
            "Limit prílohy",
            MIN_SOURCE_FILE_MAX_BYTES,
            MAX_SOURCE_FILE_MAX_BYTES,
        )
        music_track_max_bytes = self._preference_int(
            data.get("musicTrackMaxBytes", current["musicTrackMaxBytes"]),
            "Limit hudobnej skladby",
            MIN_MUSIC_TRACK_MAX_BYTES,
            MAX_MUSIC_TRACK_MAX_BYTES,
        )
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO user_preferences(
                    user_id, main_panel_transparency, workspace_panel_transparency, editor_surface_transparency,
                    music_panel_transparency, source_file_max_bytes, music_track_max_bytes, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    main_panel_transparency = excluded.main_panel_transparency,
                    workspace_panel_transparency = excluded.workspace_panel_transparency,
                    editor_surface_transparency = excluded.editor_surface_transparency,
                    music_panel_transparency = excluded.music_panel_transparency,
                    source_file_max_bytes = excluded.source_file_max_bytes,
                    music_track_max_bytes = excluded.music_track_max_bytes,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    main_panel_transparency,
                    workspace_panel_transparency,
                    editor_surface_transparency,
                    music_panel_transparency,
                    source_file_max_bytes,
                    music_track_max_bytes,
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
                    "SELECT id, name, tags_json, created_at AS createdAt FROM libraries WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,),
                )
            ]
            for library in libraries:
                library["tags"] = self._tags_from_json(library.pop("tags_json", "[]"))
            elements: dict[str, list[dict[str, Any]]] = {library["id"]: [] for library in libraries}
            rows = connection.execute(
                """
                SELECT e.id, e.library_id, e.type, e.parent_id, e.title, e.content, e.tags_json,
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
                element["tags"] = self._tags_from_json(element.pop("tags_json", "[]"))
                elements.setdefault(library_id, []).append(element)
        return {"libraries": libraries, "libraryElements": elements}

    def list_tutorial_languages(self, user_id: str) -> list[dict[str, Any]]:
        self._ensure_builtin_c_tutorial(user_id)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, code, title, summary, created_at, updated_at
                FROM tutorial_languages
                WHERE user_id = ?
                ORDER BY title COLLATE NOCASE
                """,
                (user_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "code": row["code"],
                "title": row["title"],
                "summary": row["summary"],
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
            }
            for row in rows
        ]

    def tutorial_language_detail(self, user_id: str, language_id: str) -> dict[str, Any]:
        self._ensure_builtin_c_tutorial(user_id)
        with self.connect() as connection:
            language = connection.execute(
                """
                SELECT id, code, title, summary, created_at, updated_at
                FROM tutorial_languages WHERE id = ? AND user_id = ?
                """,
                (language_id, user_id),
            ).fetchone()
            if not language:
                raise KeyError("Učebnica neexistuje.")
            page_rows = connection.execute(
                """
                SELECT p.id, p.parent_id, p.origin, p.kind, p.title, p.summary, p.content_json, p.position,
                       p.created_at, p.updated_at, n.content AS note_content, n.updated_at AS note_updated_at
                FROM tutorial_pages p
                LEFT JOIN tutorial_notes n ON n.page_id = p.id AND n.user_id = ?
                WHERE p.language_id = ?
                ORDER BY p.position, p.title COLLATE NOCASE
                """,
                (user_id, language_id),
            ).fetchall()
            example_rows = connection.execute(
                """
                SELECT e.id, e.page_id, e.title, e.description, e.source, e.stdin, e.standard, e.position,
                       e.created_at, e.updated_at, d.source AS draft_source, d.stdin AS draft_stdin,
                       d.updated_at AS draft_updated_at
                FROM tutorial_examples e
                JOIN tutorial_pages p ON p.id = e.page_id
                LEFT JOIN tutorial_example_drafts d ON d.example_id = e.id AND d.user_id = ?
                WHERE p.language_id = ?
                ORDER BY e.position, e.title COLLATE NOCASE
                """,
                (user_id, language_id),
            ).fetchall()

        pages = []
        for row in page_rows:
            try:
                content = json.loads(row["content_json"])
            except json.JSONDecodeError:
                content = {}
            if not isinstance(content, dict):
                content = {}
            pages.append(
                {
                    "id": row["id"],
                    "parentId": row["parent_id"] or "",
                    "origin": row["origin"],
                    "kind": row["kind"],
                    "title": row["title"],
                    "summary": row["summary"],
                    "content": content,
                    "position": row["position"],
                    "note": row["note_content"] or "",
                    "noteUpdatedAt": row["note_updated_at"] or "",
                    "createdAt": row["created_at"],
                    "updatedAt": row["updated_at"],
                }
            )
        examples = [
            {
                "id": row["id"],
                "pageId": row["page_id"],
                "title": row["title"],
                "description": row["description"],
                "source": row["source"],
                "stdin": row["stdin"],
                "draftSource": row["draft_source"] if row["draft_source"] is not None else row["source"],
                "draftStdin": row["draft_stdin"] if row["draft_stdin"] is not None else row["stdin"],
                "draftUpdatedAt": row["draft_updated_at"] or "",
                "standard": row["standard"],
                "position": row["position"],
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
            }
            for row in example_rows
        ]
        return {
            "language": {
                "id": language["id"],
                "code": language["code"],
                "title": language["title"],
                "summary": language["summary"],
                "createdAt": language["created_at"],
                "updatedAt": language["updated_at"],
            },
            "pages": pages,
            "examples": examples,
        }

    def create_tutorial_page(self, user_id: str, language_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Nová časť učebnice má neplatný tvar.")
        page_id = self._clean_id(data.get("id"))
        parent_id = self._clean_id(data.get("parentId")) or None
        kind = self._clean_text(data.get("kind"), 24)
        title = self._clean_text(data.get("title"), 200)
        summary = self._clean_text(data.get("summary"), 2_000)
        lead = self._clean_text(data.get("lead"), 10_000)
        if not page_id or not title:
            raise ValidationError("Nová časť učebnice potrebuje názov.")
        if kind not in {"chapter", "lesson", "reference"}:
            raise ValidationError("Neznámy typ časti učebnice.")
        if not parent_id and kind != "chapter":
            raise ValidationError("Lekciu alebo referenciu vlož do kapitoly.")

        timestamp = now_iso()
        with self.connect() as connection:
            language = connection.execute(
                "SELECT id FROM tutorial_languages WHERE id = ? AND user_id = ?",
                (language_id, user_id),
            ).fetchone()
            if not language:
                raise KeyError("Učebnica neexistuje.")
            if parent_id:
                parent = connection.execute(
                    "SELECT id, kind FROM tutorial_pages WHERE id = ? AND language_id = ?",
                    (parent_id, language_id),
                ).fetchone()
                if not parent:
                    raise KeyError("Nadradená kapitola neexistuje.")
                if parent["kind"] != "chapter":
                    raise ValidationError("Novú časť možno vložiť iba do kapitoly.")
            maximum = connection.execute(
                "SELECT COALESCE(MAX(position), 0) AS maximum FROM tutorial_pages WHERE language_id = ? AND parent_id IS ?",
                (language_id, parent_id),
            ).fetchone()
            position = int(maximum["maximum"]) + 10
            content = {"lead": lead, "sections": []}
            connection.execute(
                """
                INSERT INTO tutorial_pages(
                    id, language_id, parent_id, origin, kind, title, summary, content_json, position, created_at, updated_at
                ) VALUES (?, ?, ?, 'custom', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    page_id,
                    language_id,
                    parent_id,
                    kind,
                    title,
                    summary,
                    json.dumps(content, ensure_ascii=False, separators=(",", ":")),
                    position,
                    timestamp,
                    timestamp,
                ),
            )
        return {
            "id": page_id,
            "parentId": parent_id or "",
            "origin": "custom",
            "kind": kind,
            "title": title,
            "summary": summary,
            "content": content,
            "position": position,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }

    def save_tutorial_note(self, user_id: str, page_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Poznámka má neplatný tvar.")
        content = self._backup_text(data, "content", 200_000)
        now = now_iso()
        with self.connect() as connection:
            self._tutorial_page(connection, user_id, page_id)
            connection.execute(
                """
                INSERT INTO tutorial_notes(user_id, page_id, content, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, page_id) DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at
                """,
                (user_id, page_id, content, now),
            )
        return {"pageId": page_id, "content": content, "updatedAt": now}

    def save_tutorial_example_draft(self, user_id: str, example_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Úprava príkladu má neplatný tvar.")
        source = self._backup_text(data, "source", 200 * 1024)
        stdin = self._backup_text(data, "stdin", 64 * 1024)
        now = now_iso()
        with self.connect() as connection:
            self._tutorial_example(connection, user_id, example_id)
            connection.execute(
                """
                INSERT INTO tutorial_example_drafts(user_id, example_id, source, stdin, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, example_id) DO UPDATE SET
                    source = excluded.source, stdin = excluded.stdin, updated_at = excluded.updated_at
                """,
                (user_id, example_id, source, stdin, now),
            )
        return {"exampleId": example_id, "source": source, "stdin": stdin, "updatedAt": now}

    def tutorial_example(self, user_id: str, example_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = self._tutorial_example(connection, user_id, example_id)
        return {
            "id": row["id"],
            "title": row["title"],
            "source": row["source"],
            "stdin": row["stdin"],
            "standard": row["standard"],
        }

    def _ensure_builtin_c_tutorial(self, user_id: str) -> None:
        default_language_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"poznamkovnik:tutorial:{user_id}:{C_LANGUAGE['code']}"))
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM tutorial_languages WHERE user_id = ? AND code = ?",
                (user_id, C_LANGUAGE["code"]),
            ).fetchone()
            language_id = str(existing["id"]) if existing else default_language_id
            now = now_iso()
            if existing:
                connection.execute(
                    """
                    UPDATE tutorial_languages
                    SET title = ?, summary = ?, updated_at = ?
                    WHERE id = ? AND (title IS NOT ? OR summary IS NOT ?)
                    """,
                    (
                        C_LANGUAGE["title"],
                        C_LANGUAGE["summary"],
                        now,
                        language_id,
                        C_LANGUAGE["title"],
                        C_LANGUAGE["summary"],
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO tutorial_languages(id, user_id, code, title, summary, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (language_id, user_id, C_LANGUAGE["code"], C_LANGUAGE["title"], C_LANGUAGE["summary"], now, now),
                )
            page_ids = {
                page["key"]: str(uuid.uuid5(uuid.UUID(language_id), f"page:{page['key']}"))
                for page in C_PAGES
            }
            connection.executemany(
                """
                INSERT INTO tutorial_pages(
                    id, language_id, parent_id, origin, kind, title, summary, content_json, position, created_at, updated_at
                ) VALUES (?, ?, ?, 'builtin', ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    language_id = excluded.language_id,
                    parent_id = excluded.parent_id,
                    origin = excluded.origin,
                    kind = excluded.kind,
                    title = excluded.title,
                    summary = excluded.summary,
                    content_json = excluded.content_json,
                    position = excluded.position,
                    updated_at = excluded.updated_at
                WHERE tutorial_pages.language_id IS NOT excluded.language_id
                    OR tutorial_pages.parent_id IS NOT excluded.parent_id
                    OR tutorial_pages.origin IS NOT excluded.origin
                    OR tutorial_pages.kind IS NOT excluded.kind
                    OR tutorial_pages.title IS NOT excluded.title
                    OR tutorial_pages.summary IS NOT excluded.summary
                    OR tutorial_pages.content_json IS NOT excluded.content_json
                    OR tutorial_pages.position IS NOT excluded.position
                """,
                [
                    (
                        page_ids[page["key"]],
                        language_id,
                        page_ids.get(page["parent_key"]) or None,
                        page["kind"],
                        page["title"],
                        page["summary"],
                        json.dumps(page["content"], ensure_ascii=False, separators=(",", ":")),
                        int(page["position"]),
                        now,
                        now,
                    )
                    for page in C_PAGES
                ],
            )
            connection.executemany(
                """
                INSERT INTO tutorial_examples(
                    id, page_id, title, description, source, stdin, standard, position, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    page_id = excluded.page_id,
                    title = excluded.title,
                    description = excluded.description,
                    source = excluded.source,
                    stdin = excluded.stdin,
                    standard = excluded.standard,
                    position = excluded.position,
                    updated_at = excluded.updated_at
                WHERE tutorial_examples.page_id IS NOT excluded.page_id
                    OR tutorial_examples.title IS NOT excluded.title
                    OR tutorial_examples.description IS NOT excluded.description
                    OR tutorial_examples.source IS NOT excluded.source
                    OR tutorial_examples.stdin IS NOT excluded.stdin
                    OR tutorial_examples.standard IS NOT excluded.standard
                    OR tutorial_examples.position IS NOT excluded.position
                """,
                [
                    (
                        str(uuid.uuid5(uuid.UUID(language_id), f"example:{example['key']}")),
                        page_ids[example["page_key"]],
                        example["title"],
                        example["description"],
                        example["source"],
                        example.get("stdin", ""),
                        example.get("standard", "c17"),
                        int(example["position"]),
                        now,
                        now,
                    )
                    for example in C_EXAMPLES
                ],
            )

    @staticmethod
    def _tutorial_page(connection: sqlite3.Connection, user_id: str, page_id: str) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT p.* FROM tutorial_pages p
            JOIN tutorial_languages language ON language.id = p.language_id
            WHERE p.id = ? AND language.user_id = ?
            """,
            (page_id, user_id),
        ).fetchone()
        if not row:
            raise KeyError("Téma učebnice neexistuje.")
        return row

    @staticmethod
    def _tutorial_example(connection: sqlite3.Connection, user_id: str, example_id: str) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT e.* FROM tutorial_examples e
            JOIN tutorial_pages p ON p.id = e.page_id
            JOIN tutorial_languages language ON language.id = p.language_id
            WHERE e.id = ? AND language.user_id = ?
            """,
            (example_id, user_id),
        ).fetchone()
        if not row:
            raise KeyError("Príklad učebnice neexistuje.")
        return row

    def backup_snapshot(self, user_id: str) -> dict[str, Any]:
        """Return all user-owned records without account credentials or sessions."""
        with self.connect() as connection:
            def rows(query: str, parameters: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
                return [dict(row) for row in connection.execute(query, parameters or (user_id,)).fetchall()]

            preference = connection.execute(
                """
                SELECT background_filename, background_mime_type, background_version, background_preset,
                       main_panel_transparency, workspace_panel_transparency, editor_surface_transparency,
                       music_panel_transparency,
                       source_file_max_bytes, music_track_max_bytes,
                       automatic_backup_enabled, automatic_backup_interval_hours,
                       automatic_backup_retention_count, updated_at
                FROM user_preferences WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
            return {
                "preferences": dict(preference) if preference else {},
                "libraries": rows(
                    "SELECT id, name, tags_json, created_at, updated_at FROM libraries WHERE user_id = ? ORDER BY created_at"
                ),
                "elements": rows(
                    """
                    SELECT e.id, e.library_id, e.type, e.parent_id, e.title, e.content, e.tags_json, e.created_at, e.updated_at
                    FROM elements e JOIN libraries l ON l.id = e.library_id
                    WHERE l.user_id = ? ORDER BY e.created_at
                    """
                ),
                "sources": rows(
                    """
                    SELECT id, title, kind, description, metadata_json, tags_json, created_at, updated_at
                    FROM sources WHERE user_id = ? ORDER BY created_at
                    """
                ),
                "sourceCollections": rows(
                    """
                    SELECT id, parent_id, title, created_at, updated_at
                    FROM source_collections WHERE user_id = ? ORDER BY created_at
                    """
                ),
                "collectionSources": rows(
                    """
                    SELECT cs.collection_id, cs.source_id, cs.added_at
                    FROM collection_sources cs
                    JOIN source_collections sc ON sc.id = cs.collection_id
                    WHERE sc.user_id = ? ORDER BY cs.added_at
                    """
                ),
                "sourceFiles": rows(
                    """
                    SELECT sf.id, sf.source_id, sf.blob_hash, sf.original_name, sf.mime_type, sf.size_bytes, sf.created_at
                    FROM source_files sf JOIN sources s ON s.id = sf.source_id
                    WHERE s.user_id = ? ORDER BY sf.created_at
                    """
                ),
                "musicTracks": rows(
                    """
                    SELECT id, blob_hash, original_name, mime_type, size_bytes, title, artist, album, release_year,
                           track_number, genre, duration_seconds, created_at, updated_at
                    FROM music_tracks WHERE user_id = ? ORDER BY created_at
                    """
                ),
                "musicPlaylists": rows(
                    "SELECT id, title, created_at, updated_at FROM music_playlists WHERE user_id = ? ORDER BY created_at"
                ),
                "musicPlaylistTracks": rows(
                    """
                    SELECT mpt.playlist_id, mpt.track_id, mpt.position, mpt.added_at
                    FROM music_playlist_tracks mpt
                    JOIN music_playlists mp ON mp.id = mpt.playlist_id
                    WHERE mp.user_id = ? ORDER BY mpt.playlist_id, mpt.position, mpt.added_at
                    """
                ),
                "sourceAnnotations": rows(
                    """
                    SELECT sa.id, sa.source_id, sa.source_file_id, sa.element_id, sa.quote, sa.locator, sa.note,
                           sa.created_at, sa.updated_at
                    FROM source_annotations sa JOIN sources s ON s.id = sa.source_id
                    WHERE s.user_id = ? ORDER BY sa.created_at
                    """
                ),
                "librarySources": rows(
                    """
                    SELECT ls.library_id, ls.source_id, ls.added_at, ls.note
                    FROM library_sources ls JOIN libraries l ON l.id = ls.library_id
                    WHERE l.user_id = ? ORDER BY ls.added_at
                    """
                ),
                "elementSources": rows(
                    """
                    SELECT es.id, es.element_id, es.source_id, es.source_file_id, es.relation_type, es.locator,
                           es.label, es.note, es.created_at
                    FROM element_sources es JOIN elements e ON e.id = es.element_id
                    JOIN libraries l ON l.id = e.library_id
                    WHERE l.user_id = ? ORDER BY es.created_at
                    """
                ),
                "tasks": rows(
                    """
                    SELECT id, title, description, tags_json, status, priority, due_date, completed_at, created_at, updated_at
                    FROM tasks WHERE user_id = ? ORDER BY created_at
                    """
                ),
                "taskLinks": rows(
                    """
                    SELECT tl.id, tl.task_id, tl.target_type, tl.target_id, tl.created_at
                    FROM task_links tl JOIN tasks t ON t.id = tl.task_id
                    WHERE t.user_id = ? ORDER BY tl.created_at
                    """
                ),
                "calendarEvents": rows(
                    """
                    SELECT id, title, description, tags_json, all_day, start_date, start_time, end_date, end_time, created_at, updated_at
                    FROM calendar_events WHERE user_id = ? ORDER BY created_at
                    """
                ),
                "calendarEventLinks": rows(
                    """
                    SELECT cel.id, cel.event_id, cel.target_type, cel.target_id, cel.created_at
                    FROM calendar_event_links cel JOIN calendar_events ce ON ce.id = cel.event_id
                    WHERE ce.user_id = ? ORDER BY cel.created_at
                    """
                ),
                "semanticLinks": rows(
                    """
                    SELECT id, first_type, first_id, second_type, second_id, relation_type, created_at
                    FROM semantic_links WHERE user_id = ? ORDER BY created_at
                    """
                ),
                "tutorialLanguages": rows(
                    """
                    SELECT id, code, title, summary, created_at, updated_at
                    FROM tutorial_languages WHERE user_id = ? ORDER BY created_at
                    """
                ),
                "tutorialPages": rows(
                    """
                    SELECT p.id, p.language_id, p.parent_id, p.origin, p.kind, p.title, p.summary, p.content_json,
                           p.position, p.created_at, p.updated_at
                    FROM tutorial_pages p
                    JOIN tutorial_languages language ON language.id = p.language_id
                    WHERE language.user_id = ? ORDER BY p.position, p.created_at
                    """
                ),
                "tutorialExamples": rows(
                    """
                    SELECT e.id, e.page_id, e.title, e.description, e.source, e.stdin, e.standard,
                           e.position, e.created_at, e.updated_at
                    FROM tutorial_examples e
                    JOIN tutorial_pages p ON p.id = e.page_id
                    JOIN tutorial_languages language ON language.id = p.language_id
                    WHERE language.user_id = ? ORDER BY e.position, e.created_at
                    """
                ),
                "tutorialNotes": rows(
                    """
                    SELECT n.page_id, n.content, n.updated_at
                    FROM tutorial_notes n
                    JOIN tutorial_pages p ON p.id = n.page_id
                    JOIN tutorial_languages language ON language.id = p.language_id
                    WHERE n.user_id = ? AND language.user_id = ? ORDER BY n.updated_at
                    """,
                    (user_id, user_id),
                ),
                "tutorialExampleDrafts": rows(
                    """
                    SELECT d.example_id, d.source, d.stdin, d.updated_at
                    FROM tutorial_example_drafts d
                    JOIN tutorial_examples e ON e.id = d.example_id
                    JOIN tutorial_pages p ON p.id = e.page_id
                    JOIN tutorial_languages language ON language.id = p.language_id
                    WHERE d.user_id = ? AND language.user_id = ? ORDER BY d.updated_at
                    """,
                    (user_id, user_id),
                ),
            }

    def restore_backup_snapshot(self, user_id: str, snapshot: Any) -> None:
        if not isinstance(snapshot, dict):
            raise ValidationError("Záloha neobsahuje platné dáta.")

        optional_backup_keys = {
            "tutorialLanguages",
            "tutorialPages",
            "tutorialExamples",
            "tutorialNotes",
            "tutorialExampleDrafts",
            "semanticLinks",
            "musicTracks",
            "musicPlaylists",
            "musicPlaylistTracks",
        }
        records = {
            key: self._backup_records(snapshot.get(key, [] if key in optional_backup_keys else None), key)
            for key in BACKUP_RECORD_LIMITS
        }
        preferences = snapshot.get("preferences")
        if preferences is None:
            preferences = {}
        if not isinstance(preferences, dict):
            raise ValidationError("Nastavenia v zálohe nemajú platný tvar.")

        libraries = [
            {
                "id": self._backup_id(row, "id"),
                "name": self._backup_text(row, "name", 120),
                "tags_json": self._tags_json(self._tags_from_json(row.get("tags_json"))),
                "created_at": self._timestamp(row.get("created_at")),
                "updated_at": self._timestamp(row.get("updated_at")),
            }
            for row in records["libraries"]
        ]
        library_ids = self._backup_unique_ids(libraries, "knižníc")

        elements = []
        for row in records["elements"]:
            library_id = self._backup_id(row, "library_id")
            if library_id not in library_ids:
                continue
            element_type = self._backup_text(row, "type", 20)
            if element_type not in {"folder", "note", "article"}:
                continue
            elements.append(
                {
                    "id": self._backup_id(row, "id"),
                    "library_id": library_id,
                    "type": element_type,
                    "parent_id": self._clean_id(row.get("parent_id")) or "",
                    "title": self._backup_text(row, "title", 200),
                    "content": self._backup_text(row, "content", 5_000_000),
                    "tags_json": self._tags_json(self._tags_from_json(row.get("tags_json"))),
                    "created_at": self._timestamp(row.get("created_at")),
                    "updated_at": self._timestamp(row.get("updated_at")),
                }
            )
        element_ids = self._backup_unique_ids(elements, "prvkov")
        for element in elements:
            if element["parent_id"] not in element_ids or element["parent_id"] == element["id"]:
                element["parent_id"] = ""

        sources = []
        for row in records["sources"]:
            metadata = row.get("metadata_json", "{}")
            metadata_is_valid = False
            try:
                parsed_metadata = json.loads(metadata) if isinstance(metadata, str) else metadata
                metadata_is_valid = isinstance(parsed_metadata, dict)
            except json.JSONDecodeError:
                parsed_metadata = {}
            if not isinstance(parsed_metadata, dict):
                parsed_metadata = {}
            metadata_json = metadata if isinstance(metadata, str) and metadata_is_valid else json.dumps(
                parsed_metadata, ensure_ascii=False, separators=(",", ":")
            )
            sources.append(
                {
                    "id": self._backup_id(row, "id"),
                    "title": self._backup_text(row, "title", 240),
                    "kind": self._backup_text(row, "kind", 40) or "source",
                    "description": self._backup_text(row, "description", 10_000),
                    "metadata_json": metadata_json,
                    "tags_json": self._tags_json(self._tags_from_json(row.get("tags_json"))),
                    "created_at": self._timestamp(row.get("created_at")),
                    "updated_at": self._timestamp(row.get("updated_at")),
                }
            )
        source_ids = self._backup_unique_ids(sources, "zdrojov")

        collections = []
        for row in records["sourceCollections"]:
            parent_id = self._clean_id(row.get("parent_id")) or None
            collections.append(
                {
                    "id": self._backup_id(row, "id"),
                    "parent_id": parent_id,
                    "title": self._backup_text(row, "title", 240),
                    "created_at": self._timestamp(row.get("created_at")),
                    "updated_at": self._timestamp(row.get("updated_at")),
                }
            )
        collection_ids = self._backup_unique_ids(collections, "zbierok")
        for collection in collections:
            if collection["parent_id"] not in collection_ids or collection["parent_id"] == collection["id"]:
                collection["parent_id"] = None

        source_files = []
        for row in records["sourceFiles"]:
            source_id = self._backup_id(row, "source_id")
            blob_hash = self._backup_blob_hash(row.get("blob_hash"))
            if source_id not in source_ids or not blob_hash:
                continue
            try:
                size_bytes = int(row.get("size_bytes", 0))
            except (TypeError, ValueError):
                continue
            if size_bytes < 0:
                continue
            source_files.append(
                {
                    "id": self._backup_id(row, "id"),
                    "source_id": source_id,
                    "blob_hash": blob_hash,
                    "original_name": self._backup_text(row, "original_name", 240) or "priloha",
                    "mime_type": self._backup_text(row, "mime_type", 160) or "application/octet-stream",
                    "size_bytes": size_bytes,
                    "created_at": self._timestamp(row.get("created_at")),
                }
            )
        source_file_ids = self._backup_unique_ids(source_files, "súborov")

        music_tracks = []
        for row in records["musicTracks"]:
            blob_hash = self._backup_blob_hash(row.get("blob_hash"))
            if not blob_hash:
                continue
            try:
                size_bytes = int(row.get("size_bytes", 0))
                duration_seconds = float(row.get("duration_seconds", 0))
            except (TypeError, ValueError):
                continue
            if size_bytes < 0 or size_bytes > MAX_MUSIC_TRACK_MAX_BYTES or duration_seconds < 0 or duration_seconds > 43_200:
                continue
            original_name = self._backup_text(row, "original_name", 240) or "skladba"
            title = self._backup_text(row, "title", 240).strip() or Path(original_name).stem[:240] or "Skladba"
            music_tracks.append(
                {
                    "id": self._backup_id(row, "id"),
                    "blob_hash": blob_hash,
                    "original_name": original_name,
                    "mime_type": self._backup_text(row, "mime_type", 160) or "audio/mpeg",
                    "size_bytes": size_bytes,
                    "title": title,
                    "artist": self._backup_text(row, "artist", 160),
                    "album": self._backup_text(row, "album", 160),
                    "release_year": self._backup_text(row, "release_year", 12),
                    "track_number": self._backup_text(row, "track_number", 24),
                    "genre": self._backup_text(row, "genre", 120),
                    "duration_seconds": duration_seconds,
                    "created_at": self._timestamp(row.get("created_at")),
                    "updated_at": self._timestamp(row.get("updated_at")),
                }
            )
        music_track_ids = self._backup_unique_ids(music_tracks, "skladieb")

        music_playlists = [
            {
                "id": self._backup_id(row, "id"),
                "title": self._backup_text(row, "title", 160).strip() or "Nový playlist",
                "created_at": self._timestamp(row.get("created_at")),
                "updated_at": self._timestamp(row.get("updated_at")),
            }
            for row in records["musicPlaylists"]
        ]
        music_playlist_ids = self._backup_unique_ids(music_playlists, "playlistov")

        music_playlist_tracks = []
        seen_playlist_tracks: set[tuple[str, str]] = set()
        for row in records["musicPlaylistTracks"]:
            playlist_id = self._clean_id(row.get("playlist_id"))
            track_id = self._clean_id(row.get("track_id"))
            if playlist_id not in music_playlist_ids or track_id not in music_track_ids:
                continue
            key = (playlist_id, track_id)
            if key in seen_playlist_tracks:
                continue
            try:
                position = int(row.get("position", 0))
            except (TypeError, ValueError):
                position = 0
            seen_playlist_tracks.add(key)
            music_playlist_tracks.append(
                {
                    "playlist_id": playlist_id,
                    "track_id": track_id,
                    "position": max(-100_000, min(100_000, position)),
                    "added_at": self._timestamp(row.get("added_at")),
                }
            )

        tasks = []
        for row in records["tasks"]:
            status = self._backup_text(row, "status", 30) or "open"
            priority = self._backup_text(row, "priority", 30) or "none"
            if status not in TASK_STATUSES or priority not in TASK_PRIORITIES:
                continue
            tasks.append(
                {
                    "id": self._backup_id(row, "id"),
                    "title": self._backup_text(row, "title", 240),
                    "description": self._backup_text(row, "description", 10_000),
                    "tags_json": self._tags_json(self._tags_from_json(row.get("tags_json"))),
                    "status": status,
                    "priority": priority,
                    "due_date": self._task_due_date(row.get("due_date")),
                    "completed_at": self._timestamp(row.get("completed_at")) if row.get("completed_at") else "",
                    "created_at": self._timestamp(row.get("created_at")),
                    "updated_at": self._timestamp(row.get("updated_at")),
                }
            )
        task_ids = self._backup_unique_ids(tasks, "úloh")

        calendar_events = []
        for row in records["calendarEvents"]:
            try:
                fields = self._calendar_event_fields(
                    {
                        "title": row.get("title"),
                        "description": row.get("description"),
                        "allDay": bool(row.get("all_day")),
                        "startDate": row.get("start_date"),
                        "startTime": row.get("start_time"),
                        "endDate": row.get("end_date"),
                        "endTime": row.get("end_time"),
                    }
                )
            except ValidationError:
                continue
            calendar_events.append(
                {
                    "id": self._backup_id(row, "id"),
                    "title": fields[0],
                    "description": fields[1],
                    "tags_json": self._tags_json(self._tags_from_json(row.get("tags_json"))),
                    "all_day": fields[2],
                    "start_date": fields[3],
                    "start_time": fields[4],
                    "end_date": fields[5],
                    "end_time": fields[6],
                    "created_at": self._timestamp(row.get("created_at")),
                    "updated_at": self._timestamp(row.get("updated_at")),
                }
            )
        calendar_event_ids = self._backup_unique_ids(calendar_events, "udalostí")

        tutorial_languages = []
        language_codes: set[str] = set()
        for row in records["tutorialLanguages"]:
            code = self._backup_text(row, "code", 48).strip().lower()
            if not code or code in language_codes:
                continue
            language_codes.add(code)
            tutorial_languages.append(
                {
                    "id": self._backup_id(row, "id"),
                    "code": code,
                    "title": self._backup_text(row, "title", 120),
                    "summary": self._backup_text(row, "summary", 2_000),
                    "created_at": self._timestamp(row.get("created_at")),
                    "updated_at": self._timestamp(row.get("updated_at")),
                }
            )
        tutorial_language_ids = self._backup_unique_ids(tutorial_languages, "učebníc")

        tutorial_pages = []
        for row in records["tutorialPages"]:
            language_id = self._clean_id(row.get("language_id"))
            origin = self._backup_text(row, "origin", 16)
            kind = self._backup_text(row, "kind", 24)
            if language_id not in tutorial_language_ids or kind not in {"overview", "chapter", "lesson", "reference"}:
                continue
            content = row.get("content_json", {})
            try:
                parsed_content = json.loads(content) if isinstance(content, str) else content
            except json.JSONDecodeError:
                parsed_content = {}
            if not isinstance(parsed_content, dict):
                parsed_content = {}
            try:
                position = int(row.get("position", 0))
            except (TypeError, ValueError):
                position = 0
            tutorial_pages.append(
                {
                    "id": self._backup_id(row, "id"),
                    "language_id": language_id,
                    "parent_id": self._clean_id(row.get("parent_id")) or None,
                    "origin": "custom" if origin == "custom" else "builtin",
                    "kind": kind,
                    "title": self._backup_text(row, "title", 200),
                    "summary": self._backup_text(row, "summary", 2_000),
                    "content_json": json.dumps(parsed_content, ensure_ascii=False, separators=(",", ":")),
                    "position": max(-100_000, min(100_000, position)),
                    "created_at": self._timestamp(row.get("created_at")),
                    "updated_at": self._timestamp(row.get("updated_at")),
                }
            )
        tutorial_page_ids = self._backup_unique_ids(tutorial_pages, "tém učebnice")
        pages_by_id = {page["id"]: page for page in tutorial_pages}
        for page in tutorial_pages:
            parent = pages_by_id.get(page["parent_id"] or "")
            if not parent or parent["language_id"] != page["language_id"] or parent["id"] == page["id"]:
                page["parent_id"] = None

        tutorial_examples = []
        for row in records["tutorialExamples"]:
            page_id = self._clean_id(row.get("page_id"))
            standard = self._backup_text(row, "standard", 20) or "c17"
            if page_id not in tutorial_page_ids or standard != "c17":
                continue
            try:
                position = int(row.get("position", 0))
            except (TypeError, ValueError):
                position = 0
            tutorial_examples.append(
                {
                    "id": self._backup_id(row, "id"),
                    "page_id": page_id,
                    "title": self._backup_text(row, "title", 200),
                    "description": self._backup_text(row, "description", 2_000),
                    "source": self._backup_text(row, "source", 200 * 1024),
                    "stdin": self._backup_text(row, "stdin", 64 * 1024),
                    "standard": standard,
                    "position": max(-100_000, min(100_000, position)),
                    "created_at": self._timestamp(row.get("created_at")),
                    "updated_at": self._timestamp(row.get("updated_at")),
                }
            )
        tutorial_example_ids = self._backup_unique_ids(tutorial_examples, "príkladov učebnice")
        tutorial_notes = [
            {
                "page_id": self._backup_id(row, "page_id"),
                "content": self._backup_text(row, "content", 200_000),
                "updated_at": self._timestamp(row.get("updated_at")),
            }
            for row in records["tutorialNotes"]
            if self._clean_id(row.get("page_id")) in tutorial_page_ids
        ]
        if len({row["page_id"] for row in tutorial_notes}) != len(tutorial_notes):
            raise ValidationError("Záloha obsahuje duplicitné poznámky učebnice.")
        tutorial_drafts = [
            {
                "example_id": self._backup_id(row, "example_id"),
                "source": self._backup_text(row, "source", 200 * 1024),
                "stdin": self._backup_text(row, "stdin", 64 * 1024),
                "updated_at": self._timestamp(row.get("updated_at")),
            }
            for row in records["tutorialExampleDrafts"]
            if self._clean_id(row.get("example_id")) in tutorial_example_ids
        ]
        if len({row["example_id"] for row in tutorial_drafts}) != len(tutorial_drafts):
            raise ValidationError("Záloha obsahuje duplicitné úpravy príkladov učebnice.")

        def valid_target(target_type: str, target_id: str) -> bool:
            return (
                (target_type == "library" and target_id in library_ids)
                or (target_type == "element" and target_id in element_ids)
                or (target_type == "source" and target_id in source_ids)
            )

        collection_sources = [
            {
                "collection_id": self._backup_id(row, "collection_id"),
                "source_id": self._backup_id(row, "source_id"),
                "added_at": self._timestamp(row.get("added_at")),
            }
            for row in records["collectionSources"]
            if self._clean_id(row.get("collection_id")) in collection_ids and self._clean_id(row.get("source_id")) in source_ids
        ]
        library_sources = [
            {
                "library_id": self._backup_id(row, "library_id"),
                "source_id": self._backup_id(row, "source_id"),
                "added_at": self._timestamp(row.get("added_at")),
                "note": self._backup_text(row, "note", 2_000),
            }
            for row in records["librarySources"]
            if self._clean_id(row.get("library_id")) in library_ids and self._clean_id(row.get("source_id")) in source_ids
        ]
        element_sources = []
        for row in records["elementSources"]:
            element_id = self._clean_id(row.get("element_id"))
            source_id = self._clean_id(row.get("source_id"))
            source_file_id = self._clean_id(row.get("source_file_id")) or None
            if element_id not in element_ids or source_id not in source_ids:
                continue
            if source_file_id and source_file_id not in source_file_ids:
                source_file_id = None
            element_sources.append(
                {
                    "id": self._backup_id(row, "id"),
                    "element_id": element_id,
                    "source_id": source_id,
                    "source_file_id": source_file_id,
                    "relation_type": self._backup_text(row, "relation_type", 40) or "reference",
                    "locator": self._backup_text(row, "locator", 300),
                    "label": self._backup_text(row, "label", 300),
                    "note": self._backup_text(row, "note", 2_000),
                    "created_at": self._timestamp(row.get("created_at")),
                }
            )
        self._backup_unique_ids(element_sources, "väzieb prvkov")

        annotations = []
        for row in records["sourceAnnotations"]:
            source_id = self._clean_id(row.get("source_id"))
            source_file_id = self._clean_id(row.get("source_file_id"))
            if source_id not in source_ids or source_file_id not in source_file_ids:
                continue
            element_id = self._clean_id(row.get("element_id")) or None
            if element_id not in element_ids:
                element_id = None
            annotations.append(
                {
                    "id": self._backup_id(row, "id"),
                    "source_id": source_id,
                    "source_file_id": source_file_id,
                    "element_id": element_id,
                    "quote": self._backup_text(row, "quote", 10_000),
                    "locator": self._backup_text(row, "locator", 300),
                    "note": self._backup_text(row, "note", 5_000),
                    "created_at": self._timestamp(row.get("created_at")),
                    "updated_at": self._timestamp(row.get("updated_at")),
                }
            )
        self._backup_unique_ids(annotations, "anotácií")

        task_links = []
        for row in records["taskLinks"]:
            task_id = self._clean_id(row.get("task_id"))
            target_type = self._clean_id(row.get("target_type"))
            target_id = self._clean_id(row.get("target_id"))
            if task_id not in task_ids or target_type not in TASK_TARGET_TYPES or not valid_target(target_type, target_id):
                continue
            task_links.append(
                {
                    "id": self._backup_id(row, "id"),
                    "task_id": task_id,
                    "target_type": target_type,
                    "target_id": target_id,
                    "created_at": self._timestamp(row.get("created_at")),
                }
            )
        self._backup_unique_ids(task_links, "väzieb úloh")

        calendar_event_links = []
        for row in records["calendarEventLinks"]:
            event_id = self._clean_id(row.get("event_id"))
            target_type = self._clean_id(row.get("target_type"))
            target_id = self._clean_id(row.get("target_id"))
            if event_id not in calendar_event_ids or target_type not in TASK_TARGET_TYPES or not valid_target(target_type, target_id):
                continue
            calendar_event_links.append(
                {
                    "id": self._backup_id(row, "id"),
                    "event_id": event_id,
                    "target_type": target_type,
                    "target_id": target_id,
                    "created_at": self._timestamp(row.get("created_at")),
                }
            )
        self._backup_unique_ids(calendar_event_links, "väzieb udalostí")

        semantic_element_ids = {row["id"] for row in elements if row["type"] in {"note", "article"}}

        def valid_semantic_target(target_type: str, target_id: str) -> bool:
            return (
                (target_type == "element" and target_id in semantic_element_ids)
                or (target_type == "source" and target_id in source_ids)
                or (target_type == "tutorial_page" and target_id in tutorial_page_ids)
                or (target_type == "task" and target_id in task_ids)
                or (target_type == "calendar_event" and target_id in calendar_event_ids)
            )

        semantic_links = []
        semantic_pairs: set[tuple[str, str, str, str]] = set()
        for row in records["semanticLinks"]:
            first_type = self._clean_id(row.get("first_type"))
            first_id = self._clean_id(row.get("first_id"))
            second_type = self._clean_id(row.get("second_type"))
            second_id = self._clean_id(row.get("second_id"))
            if (
                first_type not in SEMANTIC_TARGET_TYPES
                or second_type not in SEMANTIC_TARGET_TYPES
                or not valid_semantic_target(first_type, first_id)
                or not valid_semantic_target(second_type, second_id)
                or (first_type == second_type and first_id == second_id)
            ):
                continue
            if (second_type, second_id) < (first_type, first_id):
                first_type, first_id, second_type, second_id = second_type, second_id, first_type, first_id
            pair = (first_type, first_id, second_type, second_id)
            if pair in semantic_pairs:
                continue
            semantic_pairs.add(pair)
            semantic_links.append(
                {
                    "id": self._backup_id(row, "id"),
                    "first_type": first_type,
                    "first_id": first_id,
                    "second_type": second_type,
                    "second_id": second_id,
                    "relation_type": self._backup_text(row, "relation_type", 40) or "related",
                    "created_at": self._timestamp(row.get("created_at")),
                }
            )
        self._backup_unique_ids(semantic_links, "významových prepojení")

        preference_values = {
            "background_filename": self._backup_text(preferences, "background_filename", 300),
            "background_mime_type": self._backup_text(preferences, "background_mime_type", 160),
            "background_version": self._backup_text(preferences, "background_version", 100),
            "background_preset": self._backup_preset(preferences.get("background_preset")),
            "main_panel_transparency": self._backup_preference(preferences, "main_panel_transparency", DEFAULT_MAIN_PANEL_TRANSPARENCY, 0, 65),
            "workspace_panel_transparency": self._backup_preference(preferences, "workspace_panel_transparency", DEFAULT_WORKSPACE_PANEL_TRANSPARENCY, 0, 65),
            "editor_surface_transparency": self._backup_preference(preferences, "editor_surface_transparency", DEFAULT_EDITOR_SURFACE_TRANSPARENCY, 0, 65),
            "music_panel_transparency": self._backup_preference(preferences, "music_panel_transparency", DEFAULT_MUSIC_PANEL_TRANSPARENCY, 0, 65),
            "source_file_max_bytes": self._backup_preference(
                preferences, "source_file_max_bytes", DEFAULT_SOURCE_FILE_MAX_BYTES, MIN_SOURCE_FILE_MAX_BYTES, MAX_SOURCE_FILE_MAX_BYTES
            ),
            "music_track_max_bytes": self._backup_preference(
                preferences, "music_track_max_bytes", DEFAULT_MUSIC_TRACK_MAX_BYTES,
                MIN_MUSIC_TRACK_MAX_BYTES, MAX_MUSIC_TRACK_MAX_BYTES
            ),
            "automatic_backup_enabled": self._backup_boolean(
                preferences.get("automatic_backup_enabled"), DEFAULT_AUTOMATIC_BACKUP_ENABLED
            ),
            "automatic_backup_interval_hours": self._backup_allowed_preference(
                preferences,
                "automatic_backup_interval_hours",
                DEFAULT_AUTOMATIC_BACKUP_INTERVAL_HOURS,
                AUTOMATIC_BACKUP_INTERVAL_HOURS,
            ),
            "automatic_backup_retention_count": self._backup_preference(
                preferences,
                "automatic_backup_retention_count",
                DEFAULT_AUTOMATIC_BACKUP_RETENTION_COUNT,
                MIN_AUTOMATIC_BACKUP_RETENTION_COUNT,
                MAX_AUTOMATIC_BACKUP_RETENTION_COUNT,
            ),
            "updated_at": self._timestamp(preferences.get("updated_at")),
        }

        with self.connect() as connection:
            connection.execute("PRAGMA defer_foreign_keys = ON")
            connection.execute("DELETE FROM semantic_links WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM tutorial_languages WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM calendar_events WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM music_playlists WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM music_tracks WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM sources WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM source_collections WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM libraries WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM user_preferences WHERE user_id = ?", (user_id,))
            connection.execute(
                """
                INSERT INTO user_preferences(
                    user_id, background_filename, background_mime_type, background_version, background_preset,
                    main_panel_transparency, workspace_panel_transparency, editor_surface_transparency,
                    music_panel_transparency, source_file_max_bytes, music_track_max_bytes,
                    automatic_backup_enabled, automatic_backup_interval_hours,
                    automatic_backup_retention_count, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, *preference_values.values()),
            )
            connection.executemany(
                "INSERT INTO libraries(id, user_id, name, tags_json, created_at, updated_at) VALUES (:id, :user_id, :name, :tags_json, :created_at, :updated_at)",
                [{**row, "user_id": user_id} for row in libraries],
            )
            connection.executemany(
                """
                INSERT INTO elements(id, library_id, type, parent_id, title, content, tags_json, created_at, updated_at)
                VALUES (:id, :library_id, :type, :parent_id, :title, :content, :tags_json, :created_at, :updated_at)
                """,
                elements,
            )
            connection.executemany(
                """
                INSERT INTO sources(id, user_id, title, kind, description, metadata_json, tags_json, created_at, updated_at)
                VALUES (:id, :user_id, :title, :kind, :description, :metadata_json, :tags_json, :created_at, :updated_at)
                """,
                [{**row, "user_id": user_id} for row in sources],
            )
            connection.executemany(
                """
                INSERT INTO source_collections(id, user_id, parent_id, title, created_at, updated_at)
                VALUES (:id, :user_id, :parent_id, :title, :created_at, :updated_at)
                """,
                [{**row, "user_id": user_id} for row in collections],
            )
            connection.executemany(
                "INSERT INTO source_files(id, source_id, blob_hash, original_name, mime_type, size_bytes, created_at) VALUES (:id, :source_id, :blob_hash, :original_name, :mime_type, :size_bytes, :created_at)",
                source_files,
            )
            connection.executemany(
                """
                INSERT INTO music_tracks(
                    id, user_id, blob_hash, original_name, mime_type, size_bytes, title, artist, album,
                    release_year, track_number, genre, duration_seconds, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :blob_hash, :original_name, :mime_type, :size_bytes, :title, :artist, :album,
                    :release_year, :track_number, :genre, :duration_seconds, :created_at, :updated_at
                )
                """,
                [{**row, "user_id": user_id} for row in music_tracks],
            )
            connection.executemany(
                "INSERT INTO music_playlists(id, user_id, title, created_at, updated_at) VALUES (:id, :user_id, :title, :created_at, :updated_at)",
                [{**row, "user_id": user_id} for row in music_playlists],
            )
            connection.executemany(
                "INSERT INTO music_playlist_tracks(playlist_id, track_id, position, added_at) VALUES (:playlist_id, :track_id, :position, :added_at)",
                music_playlist_tracks,
            )
            connection.executemany(
                "INSERT INTO collection_sources(collection_id, source_id, added_at) VALUES (:collection_id, :source_id, :added_at)",
                collection_sources,
            )
            connection.executemany(
                "INSERT INTO library_sources(library_id, source_id, added_at, note) VALUES (:library_id, :source_id, :added_at, :note)",
                library_sources,
            )
            connection.executemany(
                """
                INSERT INTO element_sources(id, element_id, source_id, source_file_id, relation_type, locator, label, note, created_at)
                VALUES (:id, :element_id, :source_id, :source_file_id, :relation_type, :locator, :label, :note, :created_at)
                """,
                element_sources,
            )
            connection.executemany(
                """
                INSERT INTO source_annotations(id, source_id, source_file_id, element_id, quote, locator, note, created_at, updated_at)
                VALUES (:id, :source_id, :source_file_id, :element_id, :quote, :locator, :note, :created_at, :updated_at)
                """,
                annotations,
            )
            connection.executemany(
                """
                INSERT INTO tasks(id, user_id, title, description, tags_json, status, priority, due_date, completed_at, created_at, updated_at)
                VALUES (:id, :user_id, :title, :description, :tags_json, :status, :priority, :due_date, :completed_at, :created_at, :updated_at)
                """,
                [{**row, "user_id": user_id} for row in tasks],
            )
            connection.executemany(
                "INSERT INTO task_links(id, task_id, target_type, target_id, created_at) VALUES (:id, :task_id, :target_type, :target_id, :created_at)",
                task_links,
            )
            connection.executemany(
                """
                INSERT INTO calendar_events(id, user_id, title, description, tags_json, all_day, start_date, start_time, end_date, end_time, created_at, updated_at)
                VALUES (:id, :user_id, :title, :description, :tags_json, :all_day, :start_date, :start_time, :end_date, :end_time, :created_at, :updated_at)
                """,
                [{**row, "user_id": user_id} for row in calendar_events],
            )
            connection.executemany(
                "INSERT INTO calendar_event_links(id, event_id, target_type, target_id, created_at) VALUES (:id, :event_id, :target_type, :target_id, :created_at)",
                calendar_event_links,
            )
            connection.executemany(
                """
                INSERT INTO tutorial_languages(id, user_id, code, title, summary, created_at, updated_at)
                VALUES (:id, :user_id, :code, :title, :summary, :created_at, :updated_at)
                """,
                [{**row, "user_id": user_id} for row in tutorial_languages],
            )
            connection.executemany(
                """
                INSERT INTO tutorial_pages(
                    id, language_id, parent_id, origin, kind, title, summary, content_json, position, created_at, updated_at
                ) VALUES (
                    :id, :language_id, :parent_id, :origin, :kind, :title, :summary, :content_json, :position, :created_at, :updated_at
                )
                """,
                tutorial_pages,
            )
            connection.executemany(
                """
                INSERT INTO tutorial_examples(
                    id, page_id, title, description, source, stdin, standard, position, created_at, updated_at
                ) VALUES (:id, :page_id, :title, :description, :source, :stdin, :standard, :position, :created_at, :updated_at)
                """,
                tutorial_examples,
            )
            connection.executemany(
                "INSERT INTO tutorial_notes(user_id, page_id, content, updated_at) VALUES (:user_id, :page_id, :content, :updated_at)",
                [{**row, "user_id": user_id} for row in tutorial_notes],
            )
            connection.executemany(
                "INSERT INTO tutorial_example_drafts(user_id, example_id, source, stdin, updated_at) VALUES (:user_id, :example_id, :source, :stdin, :updated_at)",
                [{**row, "user_id": user_id} for row in tutorial_drafts],
            )
            connection.executemany(
                """
                INSERT INTO semantic_links(
                    id, user_id, first_type, first_id, second_type, second_id, relation_type, created_at
                ) VALUES (
                    :id, :user_id, :first_type, :first_id, :second_type, :second_id, :relation_type, :created_at
                )
                """,
                [{**row, "user_id": user_id} for row in semantic_links],
            )

    @staticmethod
    def _backup_records(value: Any, label: str) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            raise ValidationError(f"Záloha nemá platný zoznam: {label}.")
        if len(value) > BACKUP_RECORD_LIMITS[label]:
            raise ValidationError(f"Záloha obsahuje príliš veľa záznamov: {label}.")
        if not all(isinstance(item, dict) for item in value):
            raise ValidationError(f"Záloha má neplatné záznamy: {label}.")
        return value

    def _backup_id(self, row: dict[str, Any], key: str) -> str:
        value = self._clean_id(row.get(key))
        if not value:
            raise ValidationError("Záloha obsahuje záznam bez identifikátora.")
        return value

    @staticmethod
    def _backup_text(row: dict[str, Any], key: str, maximum: int) -> str:
        value = row.get(key, "")
        return str(value if value is not None else "")[:maximum]

    @staticmethod
    def _backup_blob_hash(value: Any) -> str:
        digest = str(value or "").strip().lower()
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            return ""
        return digest

    @staticmethod
    def _backup_unique_ids(rows: list[dict[str, Any]], label: str) -> set[str]:
        ids = [row["id"] for row in rows]
        if len(ids) != len(set(ids)):
            raise ValidationError(f"Záloha obsahuje duplicitné identifikátory {label}.")
        return set(ids)

    @staticmethod
    def _backup_preference(row: dict[str, Any], key: str, fallback: int, minimum: int, maximum: int) -> int:
        try:
            value = int(row.get(key, fallback))
        except (TypeError, ValueError):
            return fallback
        return min(maximum, max(minimum, value))

    @staticmethod
    def _backup_allowed_preference(
        row: dict[str, Any], key: str, fallback: int, allowed: set[int]
    ) -> int:
        try:
            value = int(row.get(key, fallback))
        except (TypeError, ValueError):
            return fallback
        return value if value in allowed else fallback

    @staticmethod
    def _backup_boolean(value: Any, fallback: bool) -> int:
        if isinstance(value, bool):
            return int(value)
        if value in {0, 1}:
            return int(value)
        return int(fallback)

    @staticmethod
    def _backup_preset(value: Any) -> str:
        preset = str(value or "")
        return preset if preset in {"", "misty-forest", "forest-lake", "calm-ocean", "foggy-mountain"} else ""

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
                    INSERT INTO libraries(id, user_id, name, tags_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET name = excluded.name, tags_json = excluded.tags_json, updated_at = excluded.updated_at
                    WHERE libraries.user_id = excluded.user_id
                    """,
                    (
                        library["id"],
                        user_id,
                        library["name"],
                        self._tags_json(library["tags"]),
                        library["createdAt"],
                        now_iso(),
                    ),
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
                    INSERT INTO elements(id, library_id, type, parent_id, title, content, tags_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        library_id = excluded.library_id,
                        type = excluded.type,
                        parent_id = excluded.parent_id,
                        title = excluded.title,
                        content = excluded.content,
                        tags_json = excluded.tags_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        item["id"],
                        library_id,
                        item["type"],
                        item["parentId"],
                        item["title"],
                        item["content"],
                        self._tags_json(item["tags"]),
                        item["createdAt"],
                        item["updatedAt"],
                    ),
                )
            connection.execute(
                """
                DELETE FROM semantic_links
                WHERE user_id = ? AND (
                    (first_type = 'element' AND first_id NOT IN (
                      SELECT e.id FROM elements e JOIN libraries l ON l.id = e.library_id WHERE l.user_id = ?
                    ))
                    OR
                    (second_type = 'element' AND second_id NOT IN (
                      SELECT e.id FROM elements e JOIN libraries l ON l.id = e.library_id WHERE l.user_id = ?
                    ))
                )
                """,
                (user_id, user_id, user_id),
            )
            connection.execute(
                """
                DELETE FROM task_links
                WHERE task_id IN (SELECT id FROM tasks WHERE user_id = ?)
                  AND (
                    (target_type = 'library' AND target_id NOT IN (SELECT id FROM libraries WHERE user_id = ?))
                    OR
                    (target_type = 'element' AND target_id NOT IN (
                      SELECT e.id FROM elements e JOIN libraries l ON l.id = e.library_id WHERE l.user_id = ?
                    ))
                  )
                """,
                (user_id, user_id, user_id),
            )
            connection.execute(
                """
                DELETE FROM calendar_event_links
                WHERE event_id IN (SELECT id FROM calendar_events WHERE user_id = ?)
                  AND (
                    (target_type = 'library' AND target_id NOT IN (SELECT id FROM libraries WHERE user_id = ?))
                    OR
                    (target_type = 'element' AND target_id NOT IN (
                      SELECT e.id FROM elements e JOIN libraries l ON l.id = e.library_id WHERE l.user_id = ?
                    ))
                  )
                """,
                (user_id, user_id, user_id),
            )
        return self.read_workspace(user_id)

    def _normalize_libraries(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            raise ValidationError("Zoznam knižníc chýba.")
        if len(value) > 500:
            raise ValidationError("Príliš veľa knižníc.")
        seen_ids: set[str] = set()
        normalized: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            item_id = self._clean_id(item.get("id"))
            name = self._clean_text(item.get("name"), 120)
            if not item_id or not name or item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            normalized.append(
                {
                    "id": item_id,
                    "name": name,
                    "tags": self._clean_tags(item.get("tags")),
                    "createdAt": self._timestamp(item.get("createdAt")),
                }
            )
        return normalized

    def _normalize_elements(self, value: Any, library_ids: set[str]) -> dict[str, list[dict[str, Any]]]:
        if not isinstance(value, dict):
            raise ValidationError("Obsah knižníc chýba.")
        normalized: dict[str, list[dict[str, Any]]] = {}
        all_ids: set[str] = set()
        item_count = 0
        for library_id, items in value.items():
            if library_id not in library_ids or not isinstance(items, list):
                continue
            clean_items: list[dict[str, Any]] = []
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
                        "tags": self._clean_tags(item.get("tags")),
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

    def create_task(self, user_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Úloha musí byť objekt.")
        task_id = self._clean_id(data.get("id"))
        title = self._clean_text(data.get("title"), 240)
        if not task_id or not title:
            raise ValidationError("Úloha potrebuje názov.")
        status = self._task_status(data.get("status", "open"))
        priority = self._task_priority(data.get("priority", "none"))
        timestamp = now_iso()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks(
                    id, user_id, title, description, tags_json, status, priority, due_date, completed_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    user_id,
                    title,
                    self._clean_text(data.get("description"), 10_000),
                    self._tags_json(self._clean_tags(data.get("tags"))),
                    status,
                    priority,
                    self._task_due_date(data.get("dueDate")),
                    timestamp if status == "done" else "",
                    timestamp,
                    timestamp,
                ),
            )
        return self.task_detail(user_id, task_id)

    def list_tasks(self, user_id: str, status: str = "") -> list[dict[str, Any]]:
        status = self._task_status(status) if status else ""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT t.*, COUNT(tl.id) AS link_count
                FROM tasks t
                LEFT JOIN task_links tl ON tl.task_id = t.id
                WHERE t.user_id = ? AND (? = '' OR t.status = ?)
                GROUP BY t.id
                ORDER BY
                    CASE t.status WHEN 'done' THEN 1 ELSE 0 END,
                    CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
                    CASE WHEN t.due_date = '' THEN 1 ELSE 0 END,
                    t.due_date ASC,
                    t.updated_at DESC
                """,
                (user_id, status, status),
            ).fetchall()
        return [self._task_row(row) for row in rows]

    def task_detail(self, user_id: str, task_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            task = self._task(connection, user_id, task_id)
            links = []
            for link in connection.execute(
                "SELECT id, target_type, target_id, created_at FROM task_links WHERE task_id = ? ORDER BY created_at DESC",
                (task_id,),
            ):
                target = self._task_link_target(connection, user_id, link)
                if target:
                    links.append(target)
        result = self._task_row(task)
        result["links"] = links
        return result

    def update_task(self, user_id: str, task_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Úprava úlohy musí byť objekt.")
        with self.connect() as connection:
            current = self._task(connection, user_id, task_id)
            title = self._clean_text(data.get("title", current["title"]), 240)
            if not title:
                raise ValidationError("Úloha potrebuje názov.")
            status = self._task_status(data.get("status", current["status"]))
            priority = self._task_priority(data.get("priority", current["priority"]))
            due_date = self._task_due_date(data.get("dueDate", current["due_date"]))
            description = self._clean_text(data.get("description", current["description"]), 10_000)
            tags = self._clean_tags(data.get("tags", self._tags_from_json(current["tags_json"])))
            completed_at = current["completed_at"] if status == "done" else ""
            if status == "done" and current["status"] != "done":
                completed_at = now_iso()
            connection.execute(
                """
                UPDATE tasks
                SET title = ?, description = ?, tags_json = ?, status = ?, priority = ?, due_date = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (title, description, self._tags_json(tags), status, priority, due_date, completed_at, now_iso(), task_id),
            )
        return self.task_detail(user_id, task_id)

    def delete_task(self, user_id: str, task_id: str) -> None:
        with self.connect() as connection:
            self._task(connection, user_id, task_id)
            self._delete_semantic_links_for_target(connection, user_id, "task", task_id)
            connection.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))

    def link_task(self, user_id: str, task_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Väzba úlohy musí byť objekt.")
        link_id = self._clean_id(data.get("id"))
        target_type = self._task_target_type(data.get("targetType"))
        target_id = self._clean_id(data.get("targetId"))
        if not link_id or not target_id:
            raise ValidationError("Väzba úlohy potrebuje cieľ.")
        with self.connect() as connection:
            self._task(connection, user_id, task_id)
            self._assert_task_target(connection, user_id, target_type, target_id)
            connection.execute(
                """
                INSERT INTO task_links(id, task_id, target_type, target_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(task_id, target_type, target_id) DO NOTHING
                """,
                (link_id, task_id, target_type, target_id, now_iso()),
            )
        return self.task_detail(user_id, task_id)

    def unlink_task(self, user_id: str, task_id: str, link_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            self._task(connection, user_id, task_id)
            result = connection.execute("DELETE FROM task_links WHERE id = ? AND task_id = ?", (link_id, task_id))
            if result.rowcount != 1:
                raise KeyError("Väzba úlohy neexistuje.")
        return self.task_detail(user_id, task_id)

    def tasks_for_target(self, user_id: str, target_type: str, target_id: str) -> list[dict[str, Any]]:
        target_type = self._task_target_type(target_type)
        target_id = self._clean_id(target_id)
        with self.connect() as connection:
            self._assert_task_target(connection, user_id, target_type, target_id)
            rows = connection.execute(
                """
                SELECT t.*, COUNT(all_links.id) AS link_count
                FROM task_links matched
                JOIN tasks t ON t.id = matched.task_id
                LEFT JOIN task_links all_links ON all_links.task_id = t.id
                WHERE matched.target_type = ? AND matched.target_id = ? AND t.user_id = ?
                GROUP BY t.id
                ORDER BY
                    CASE t.status WHEN 'done' THEN 1 ELSE 0 END,
                    CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
                    CASE WHEN t.due_date = '' THEN 1 ELSE 0 END,
                    t.due_date ASC,
                    t.updated_at DESC
                """,
                (target_type, target_id, user_id),
            ).fetchall()
        return [self._task_row(row) for row in rows]

    def calendar_events_for_target(self, user_id: str, target_type: str, target_id: str) -> list[dict[str, Any]]:
        target_type = self._task_target_type(target_type)
        target_id = self._clean_id(target_id)
        with self.connect() as connection:
            self._assert_task_target(connection, user_id, target_type, target_id)
            rows = connection.execute(
                """
                SELECT ce.*
                FROM calendar_event_links matched
                JOIN calendar_events ce ON ce.id = matched.event_id
                WHERE matched.target_type = ? AND matched.target_id = ? AND ce.user_id = ?
                ORDER BY ce.start_date ASC, ce.start_time ASC, ce.end_date ASC, ce.title COLLATE NOCASE
                """,
                (target_type, target_id, user_id),
            ).fetchall()
        return [self._calendar_event_row(row) for row in rows]

    def semantic_targets(self, user_id: str) -> list[dict[str, Any]]:
        self._ensure_builtin_c_tutorial(user_id)
        with self.connect() as connection:
            targets: list[dict[str, Any]] = []
            for row in connection.execute(
                """
                SELECT e.id, e.title, e.type, e.library_id, l.name AS library_name
                FROM elements e JOIN libraries l ON l.id = e.library_id
                WHERE l.user_id = ? AND e.type IN ('note', 'article')
                ORDER BY l.name COLLATE NOCASE, e.title COLLATE NOCASE
                """,
                (user_id,),
            ):
                targets.append(self._semantic_element_target(row))
            for row in connection.execute(
                "SELECT id, title, kind FROM sources WHERE user_id = ? ORDER BY title COLLATE NOCASE", (user_id,)
            ):
                targets.append({"targetType": "source", "targetId": row["id"], "title": row["title"], "subtitle": "Zdroj"})
            for row in connection.execute(
                """
                SELECT p.id, p.title, p.kind, p.language_id, l.title AS language_title
                FROM tutorial_pages p JOIN tutorial_languages l ON l.id = p.language_id
                WHERE l.user_id = ?
                ORDER BY l.title COLLATE NOCASE, p.position, p.title COLLATE NOCASE
                """,
                (user_id,),
            ):
                targets.append(
                    {
                        "targetType": "tutorial_page",
                        "targetId": row["id"],
                        "title": row["title"],
                        "subtitle": f"Učebnica / {row['language_title']}",
                        "languageId": row["language_id"],
                    }
                )
            for row in connection.execute(
                "SELECT id, title, status, due_date FROM tasks WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)
            ):
                targets.append(
                    {
                        "targetType": "task",
                        "targetId": row["id"],
                        "title": row["title"],
                        "subtitle": "Hotová" if row["status"] == "done" else (f"Do {row['due_date']}" if row["due_date"] else "Úloha"),
                        "status": row["status"],
                    }
                )
            for row in connection.execute(
                "SELECT id, title, all_day, start_date, start_time FROM calendar_events WHERE user_id = ? ORDER BY start_date, start_time",
                (user_id,),
            ):
                targets.append(
                    {
                        "targetType": "calendar_event",
                        "targetId": row["id"],
                        "title": row["title"],
                        "subtitle": row["start_date"] if row["all_day"] else f"{row['start_date']} {row['start_time']}",
                    }
                )
        return targets

    def create_semantic_link(self, user_id: str, source_type: str, source_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Prepojenie má neplatný tvar.")
        source_type = self._semantic_target_type(source_type)
        source_id = self._clean_id(source_id)
        target_type = self._semantic_target_type(data.get("targetType"))
        target_id = self._clean_id(data.get("targetId"))
        if not source_id or not target_id or (source_type == target_type and source_id == target_id):
            raise ValidationError("Prepojenie potrebuje dva rozdielne prvky.")
        first_type, first_id, second_type, second_id = (source_type, source_id, target_type, target_id)
        if (second_type, second_id) < (first_type, first_id):
            first_type, first_id, second_type, second_id = second_type, second_id, first_type, first_id
        with self.connect() as connection:
            self._semantic_target(connection, user_id, source_type, source_id)
            target = self._semantic_target(connection, user_id, target_type, target_id)
            link_id = self._clean_id(data.get("id")) or str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO semantic_links(id, user_id, first_type, first_id, second_type, second_id, relation_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'related', ?)
                ON CONFLICT(user_id, first_type, first_id, second_type, second_id) DO NOTHING
                """,
                (link_id, user_id, first_type, first_id, second_type, second_id, now_iso()),
            )
        return target

    def semantic_links_for_target(self, user_id: str, target_type: str, target_id: str) -> list[dict[str, Any]]:
        target_type = self._semantic_target_type(target_type)
        target_id = self._clean_id(target_id)
        with self.connect() as connection:
            self._semantic_target(connection, user_id, target_type, target_id)
            rows = connection.execute(
                """
                SELECT * FROM semantic_links
                WHERE user_id = ? AND ((first_type = ? AND first_id = ?) OR (second_type = ? AND second_id = ?))
                ORDER BY created_at DESC
                """,
                (user_id, target_type, target_id, target_type, target_id),
            ).fetchall()
            results = []
            for row in rows:
                other_type, other_id = (row["second_type"], row["second_id"]) if row["first_type"] == target_type and row["first_id"] == target_id else (row["first_type"], row["first_id"])
                try:
                    target = self._semantic_target(connection, user_id, other_type, other_id)
                except KeyError:
                    connection.execute("DELETE FROM semantic_links WHERE id = ? AND user_id = ?", (row["id"], user_id))
                    continue
                target["linkId"] = row["id"]
                results.append(target)
        return results

    def delete_semantic_link(self, user_id: str, link_id: str) -> None:
        link_id = self._clean_id(link_id)
        with self.connect() as connection:
            result = connection.execute("DELETE FROM semantic_links WHERE id = ? AND user_id = ?", (link_id, user_id))
            if result.rowcount != 1:
                raise KeyError("Prepojenie neexistuje.")

    def relationship_overview(self, user_id: str, target_type: str, target_id: str) -> dict[str, Any]:
        target_type = str(target_type or "").strip()
        if target_type != "library" and target_type not in SEMANTIC_TARGET_TYPES:
            raise ValidationError("Neznámy cieľ prepojení.")
        target_id = self._clean_id(target_id)
        groups: dict[str, list[dict[str, Any]]] = {
            "libraries": [],
            "elements": [],
            "sources": [],
            "tutorial": [],
            "tasks": [],
            "calendar": [],
        }

        def group_name(item: dict[str, Any]) -> str:
            return {
                "library": "libraries",
                "element": "elements",
                "source": "sources",
                "tutorial_page": "tutorial",
                "task": "tasks",
                "calendar_event": "calendar",
            }[item["targetType"]]

        def add(item: dict[str, Any]) -> None:
            group = group_name(item)
            key = (item["targetType"], item["targetId"])
            if key == (target_type, target_id):
                return
            if any((current["targetType"], current["targetId"]) == key for current in groups[group]):
                return
            groups[group].append(item)

        if target_type == "library":
            with self.connect() as connection:
                row = connection.execute(
                    "SELECT id, name FROM libraries WHERE id = ? AND user_id = ?", (target_id, user_id)
                ).fetchone()
            if not row:
                raise KeyError("Knižnica neexistuje.")
            focus = {"targetType": "library", "targetId": row["id"], "title": row["name"], "subtitle": "Knižnica"}
            for source in self.sources_for_library(user_id, target_id):
                add({
                    "targetType": "source",
                    "targetId": source["id"],
                    "title": source["title"],
                    "subtitle": source["kind"],
                })
        else:
            with self.connect() as connection:
                focus = self._semantic_target(connection, user_id, target_type, target_id)

            if target_type == "element":
                unique_sources: dict[str, dict[str, Any]] = {}
                for source in self.sources_for_element(user_id, target_id):
                    unique_sources.setdefault(
                        source["id"],
                        {
                            "targetType": "source",
                            "targetId": source["id"],
                            "title": source["title"],
                            "subtitle": source["kind"],
                        },
                    )
                for source in unique_sources.values():
                    add(source)
            elif target_type == "source":
                source = self.source_detail(user_id, target_id)
                elements: dict[str, dict[str, Any]] = {}
                for element in source["elements"]:
                    element_label = "Článok" if element["type"] == "article" else "Poznámka"
                    elements[element["id"]] = {
                        "targetType": "element",
                        "targetId": element["id"],
                        "title": element["title"] or element_label,
                        "subtitle": f"{element['libraryName']} / {element_label}",
                        "libraryId": element["libraryId"],
                        "elementType": element["type"],
                    }
                for annotation in source["annotations"]:
                    if not annotation.get("elementId") or not annotation.get("elementTitle"):
                        continue
                    element_label = "Článok" if annotation.get("elementType") == "article" else "Poznámka"
                    elements.setdefault(
                        annotation["elementId"],
                        {
                            "targetType": "element",
                            "targetId": annotation["elementId"],
                            "title": annotation["elementTitle"],
                            "subtitle": f"{annotation.get('libraryName') or 'Knižnica'} / {element_label}",
                            "libraryId": annotation.get("libraryId", ""),
                            "elementType": annotation.get("elementType", "note"),
                        },
                    )
                for element in elements.values():
                    add(element)
            elif target_type == "task":
                for link in self.task_detail(user_id, target_id)["links"]:
                    add(link)
            elif target_type == "calendar_event":
                for link in self.calendar_event_detail(user_id, target_id)["links"]:
                    add(link)

            for linked_target in self.semantic_links_for_target(user_id, target_type, target_id):
                add(linked_target)

        if target_type in TASK_TARGET_TYPES:
            for task in self.tasks_for_target(user_id, target_type, target_id):
                add(
                    {
                        "targetType": "task",
                        "targetId": task["id"],
                        "title": task["title"],
                        "subtitle": "Hotová" if task["status"] == "done" else (f"Do {task['dueDate']}" if task["dueDate"] else "Úloha"),
                        "status": task["status"],
                    }
                )
            for event in self.calendar_events_for_target(user_id, target_type, target_id):
                add(
                    {
                        "targetType": "calendar_event",
                        "targetId": event["id"],
                        "title": event["title"],
                        "subtitle": event["startDate"] if event["allDay"] else f"{event['startDate']} {event['startTime']}",
                    }
                )
        return {"focus": focus, "groups": groups}

    def create_calendar_event(self, user_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Udalosť musí byť objekt.")
        event_id = self._clean_id(data.get("id"))
        if not event_id:
            raise ValidationError("Udalosť potrebuje identifikátor.")
        fields = self._calendar_event_fields(data)
        timestamp = now_iso()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO calendar_events(
                    id, user_id, title, description, tags_json, all_day, start_date, start_time, end_date, end_time, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, user_id, fields[0], fields[1], self._tags_json(self._clean_tags(data.get("tags"))), *fields[2:], timestamp, timestamp),
            )
        return self.calendar_event_detail(user_id, event_id)

    def list_calendar_events(self, user_id: str, start_date: str = "", end_date: str = "") -> list[dict[str, Any]]:
        start_date = self._calendar_event_date(start_date, "Začiatok rozsahu") if start_date else ""
        end_date = self._calendar_event_date(end_date, "Koniec rozsahu") if end_date else ""
        if start_date and end_date and end_date < start_date:
            raise ValidationError("Koniec rozsahu kalendára nemôže byť pred začiatkom.")
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM calendar_events
                WHERE user_id = ?
                  AND (? = '' OR end_date >= ?)
                  AND (? = '' OR start_date <= ?)
                ORDER BY start_date ASC, start_time ASC, end_date ASC, title COLLATE NOCASE
                """,
                (user_id, start_date, start_date, end_date, end_date),
            ).fetchall()
        return [self._calendar_event_row(row) for row in rows]

    def calendar_event_detail(self, user_id: str, event_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            event = self._calendar_event(connection, user_id, event_id)
            links = []
            for link in connection.execute(
                "SELECT id, target_type, target_id, created_at FROM calendar_event_links WHERE event_id = ? ORDER BY created_at DESC",
                (event_id,),
            ):
                target = self._task_link_target(connection, user_id, link)
                if target:
                    links.append(target)
        result = self._calendar_event_row(event)
        result["links"] = links
        return result

    def update_calendar_event(self, user_id: str, event_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Úprava udalosti musí byť objekt.")
        with self.connect() as connection:
            current = self._calendar_event(connection, user_id, event_id)
            fields = self._calendar_event_fields(
                data,
                {
                    "title": current["title"],
                    "description": current["description"],
                    "allDay": bool(current["all_day"]),
                    "startDate": current["start_date"],
                    "startTime": current["start_time"],
                    "endDate": current["end_date"],
                    "endTime": current["end_time"],
                },
            )
            tags = self._clean_tags(data.get("tags", self._tags_from_json(current["tags_json"])))
            connection.execute(
                """
                UPDATE calendar_events
                SET title = ?, description = ?, tags_json = ?, all_day = ?, start_date = ?, start_time = ?, end_date = ?, end_time = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (fields[0], fields[1], self._tags_json(tags), *fields[2:], now_iso(), event_id, user_id),
            )
        return self.calendar_event_detail(user_id, event_id)

    def delete_calendar_event(self, user_id: str, event_id: str) -> None:
        with self.connect() as connection:
            self._calendar_event(connection, user_id, event_id)
            self._delete_semantic_links_for_target(connection, user_id, "calendar_event", event_id)
            connection.execute("DELETE FROM calendar_events WHERE id = ? AND user_id = ?", (event_id, user_id))

    def link_calendar_event(self, user_id: str, event_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Väzba udalosti musí byť objekt.")
        link_id = self._clean_id(data.get("id"))
        target_type = self._task_target_type(data.get("targetType"))
        target_id = self._clean_id(data.get("targetId"))
        if not link_id or not target_id:
            raise ValidationError("Väzba udalosti potrebuje cieľ.")
        with self.connect() as connection:
            self._calendar_event(connection, user_id, event_id)
            self._assert_task_target(connection, user_id, target_type, target_id)
            connection.execute(
                """
                INSERT INTO calendar_event_links(id, event_id, target_type, target_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(event_id, target_type, target_id) DO NOTHING
                """,
                (link_id, event_id, target_type, target_id, now_iso()),
            )
        return self.calendar_event_detail(user_id, event_id)

    def unlink_calendar_event(self, user_id: str, event_id: str, link_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            self._calendar_event(connection, user_id, event_id)
            result = connection.execute(
                "DELETE FROM calendar_event_links WHERE id = ? AND event_id = ?", (link_id, event_id)
            )
            if result.rowcount != 1:
                raise KeyError("Väzba udalosti neexistuje.")
        return self.calendar_event_detail(user_id, event_id)

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
                INSERT INTO sources(id, user_id, title, kind, description, metadata_json, tags_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    user_id,
                    title,
                    kind,
                    description,
                    json.dumps(metadata, ensure_ascii=False),
                    self._tags_json(self._clean_tags(data.get("tags"))),
                    timestamp,
                    timestamp,
                ),
            )
        return self.source_detail(user_id, source_id)

    def list_sources(self, user_id: str, query: str = "") -> list[dict[str, Any]]:
        search = f"%{query.strip()}%"
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT s.id, s.title, s.kind, s.description, s.metadata_json, s.tags_json,
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
                WHERE s.user_id = ? AND (s.title LIKE ? OR s.description LIKE ? OR s.metadata_json LIKE ? OR s.tags_json LIKE ?)
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                """,
                (user_id, search, search, search, search),
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
                SELECT s.id, s.title, s.kind, s.description, s.metadata_json, s.tags_json,
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
        source["tasks"] = self.tasks_for_target(user_id, "source", source_id)
        source["calendarEvents"] = self.calendar_events_for_target(user_id, "source", source_id)
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
            tags = self._clean_tags(data.get("tags", self._tags_from_json(current["tags_json"])))
            if not title:
                raise ValidationError("Zdroj potrebuje názov.")
            connection.execute(
                "UPDATE sources SET title = ?, kind = ?, description = ?, metadata_json = ?, tags_json = ?, updated_at = ? WHERE id = ?",
                (title, kind, description, json.dumps(metadata, ensure_ascii=False), self._tags_json(tags), now_iso(), source_id),
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
            self._delete_semantic_links_for_target(connection, user_id, "source", source_id)
            connection.execute("DELETE FROM task_links WHERE target_type = 'source' AND target_id = ?", (source_id,))
            connection.execute("DELETE FROM calendar_event_links WHERE target_type = 'source' AND target_id = ?", (source_id,))
            connection.execute("DELETE FROM sources WHERE id = ? AND user_id = ?", (source_id, user_id))
            orphaned = []
            for file in files:
                blob_hash = file["blob_hash"]
                if not self._blob_is_referenced(connection, blob_hash):
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
            still_used = self._blob_is_referenced(connection, blob_hash)
        return self.source_detail(user_id, source_id), None if still_used else blob_hash

    def music_library(self, user_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            tracks = [
                self._music_track_row(row)
                for row in connection.execute(
                    """
                    SELECT id, original_name, mime_type, size_bytes, title, artist, album, release_year,
                           track_number, genre, duration_seconds, created_at, updated_at
                    FROM music_tracks WHERE user_id = ?
                    ORDER BY created_at DESC, id DESC
                    """,
                    (user_id,),
                )
            ]
            playlists = [
                self._music_playlist_row(row)
                for row in connection.execute(
                    """
                    SELECT mp.id, mp.title, mp.created_at, mp.updated_at, COUNT(mpt.track_id) AS track_count
                    FROM music_playlists mp
                    LEFT JOIN music_playlist_tracks mpt ON mpt.playlist_id = mp.id
                    WHERE mp.user_id = ?
                    GROUP BY mp.id
                    ORDER BY mp.title COLLATE NOCASE, mp.created_at
                    """,
                    (user_id,),
                )
            ]
            playlist_tracks = connection.execute(
                """
                SELECT mpt.playlist_id, mpt.track_id
                FROM music_playlist_tracks mpt
                JOIN music_playlists mp ON mp.id = mpt.playlist_id
                WHERE mp.user_id = ?
                ORDER BY mpt.playlist_id, mpt.position, mpt.added_at
                """,
                (user_id,),
            ).fetchall()
        track_ids_by_playlist: dict[str, list[str]] = {playlist["id"]: [] for playlist in playlists}
        for row in playlist_tracks:
            track_ids_by_playlist.setdefault(row["playlist_id"], []).append(row["track_id"])
        for playlist in playlists:
            playlist["trackIds"] = track_ids_by_playlist.get(playlist["id"], [])
        return {"tracks": tracks, "playlists": playlists}

    def add_music_track(
        self, user_id: str, track_id: str, file_info: dict[str, Any], metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        original_name = self._clean_text(file_info.get("originalName"), 240) or "skladba"
        metadata = metadata if isinstance(metadata, dict) else {}
        title = self._clean_text(metadata.get("title"), 240) or Path(original_name).stem.strip()[:240] or "Skladba"
        artist = self._clean_text(metadata.get("artist"), 160)
        album = self._clean_text(metadata.get("album"), 160)
        release_year = self._clean_text(metadata.get("year"), 12)
        track_number = self._clean_text(metadata.get("trackNumber"), 24)
        genre = self._clean_text(metadata.get("genre"), 120)
        duration = self._music_duration(metadata.get("durationSeconds", 0))
        timestamp = now_iso()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO music_tracks(
                    id, user_id, blob_hash, original_name, mime_type, size_bytes, title, artist, album,
                    release_year, track_number, genre, duration_seconds, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self._clean_id(track_id),
                    user_id,
                    str(file_info["blobHash"]),
                    original_name,
                    self._clean_text(file_info.get("mimeType"), 160) or "audio/mpeg",
                    int(file_info["sizeBytes"]),
                    title,
                    artist,
                    album,
                    release_year,
                    track_number,
                    genre,
                    duration,
                    timestamp,
                    timestamp,
                ),
            )
        return self.music_library(user_id)

    def update_music_track(self, user_id: str, track_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Úprava skladby musí byť objekt.")
        with self.connect() as connection:
            current = self._music_track(connection, user_id, track_id)
            title = self._clean_text(data.get("title", current["title"]), 240)
            if not title:
                raise ValidationError("Skladba potrebuje názov.")
            artist = self._clean_text(data.get("artist", current["artist"]), 160)
            album = self._clean_text(data.get("album", current["album"]), 160)
            release_year = self._clean_text(data.get("year", current["release_year"]), 12)
            track_number = self._clean_text(data.get("trackNumber", current["track_number"]), 24)
            genre = self._clean_text(data.get("genre", current["genre"]), 120)
            duration = self._music_duration(data.get("durationSeconds", current["duration_seconds"]))
            connection.execute(
                """
                UPDATE music_tracks
                SET title = ?, artist = ?, album = ?, release_year = ?, track_number = ?, genre = ?,
                    duration_seconds = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (title, artist, album, release_year, track_number, genre, duration, now_iso(), track_id, user_id),
            )
        return self.music_library(user_id)

    def delete_music_track(self, user_id: str, track_id: str) -> tuple[dict[str, Any], str | None]:
        with self.connect() as connection:
            track = self._music_track(connection, user_id, track_id)
            blob_hash = track["blob_hash"]
            connection.execute("DELETE FROM music_tracks WHERE id = ? AND user_id = ?", (track_id, user_id))
            orphaned_blob = None if self._blob_is_referenced(connection, blob_hash) else blob_hash
        return self.music_library(user_id), orphaned_blob

    def music_track_file(self, user_id: str, track_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            return dict(self._music_track(connection, user_id, track_id))

    def create_music_playlist(self, user_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Playlist musí byť objekt.")
        playlist_id = self._clean_id(data.get("id"))
        title = self._clean_text(data.get("title"), 160)
        if not playlist_id or not title:
            raise ValidationError("Playlist potrebuje názov.")
        timestamp = now_iso()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO music_playlists(id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (playlist_id, user_id, title, timestamp, timestamp),
            )
        return self.music_library(user_id)

    def update_music_playlist(self, user_id: str, playlist_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("Úprava playlistu musí byť objekt.")
        title = self._clean_text(data.get("title"), 160)
        if not title:
            raise ValidationError("Playlist potrebuje názov.")
        with self.connect() as connection:
            self._music_playlist(connection, user_id, playlist_id)
            connection.execute(
                "UPDATE music_playlists SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (title, now_iso(), playlist_id, user_id),
            )
        return self.music_library(user_id)

    def delete_music_playlist(self, user_id: str, playlist_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            self._music_playlist(connection, user_id, playlist_id)
            connection.execute("DELETE FROM music_playlists WHERE id = ? AND user_id = ?", (playlist_id, user_id))
        return self.music_library(user_id)

    def add_music_playlist_track(self, user_id: str, playlist_id: str, track_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            self._music_playlist(connection, user_id, playlist_id)
            self._music_track(connection, user_id, track_id)
            position = int(
                connection.execute(
                    "SELECT COALESCE(MAX(position), -1) + 1 FROM music_playlist_tracks WHERE playlist_id = ?",
                    (playlist_id,),
                ).fetchone()[0]
            )
            connection.execute(
                """
                INSERT INTO music_playlist_tracks(playlist_id, track_id, position, added_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(playlist_id, track_id) DO NOTHING
                """,
                (playlist_id, track_id, position, now_iso()),
            )
            connection.execute("UPDATE music_playlists SET updated_at = ? WHERE id = ?", (now_iso(), playlist_id))
        return self.music_library(user_id)

    def remove_music_playlist_track(self, user_id: str, playlist_id: str, track_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            self._music_playlist(connection, user_id, playlist_id)
            connection.execute(
                "DELETE FROM music_playlist_tracks WHERE playlist_id = ? AND track_id = ?", (playlist_id, track_id)
            )
            connection.execute("UPDATE music_playlists SET updated_at = ? WHERE id = ?", (now_iso(), playlist_id))
        return self.music_library(user_id)

    def reorder_music_playlist(self, user_id: str, playlist_id: str, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict) or not isinstance(data.get("trackIds"), list):
            raise ValidationError("Playlist potrebuje zoznam skladieb.")
        track_ids = [self._clean_id(track_id) for track_id in data["trackIds"]]
        if not all(track_ids) or len(track_ids) != len(set(track_ids)):
            raise ValidationError("Playlist má neplatné alebo duplicitné skladby.")
        with self.connect() as connection:
            self._music_playlist(connection, user_id, playlist_id)
            current_ids = [
                row["track_id"]
                for row in connection.execute(
                    "SELECT track_id FROM music_playlist_tracks WHERE playlist_id = ?", (playlist_id,)
                )
            ]
            if set(track_ids) != set(current_ids):
                raise ValidationError("Poradie nepatrí aktuálnemu playlistu.")
            connection.executemany(
                "UPDATE music_playlist_tracks SET position = ? WHERE playlist_id = ? AND track_id = ?",
                [(position, playlist_id, track_id) for position, track_id in enumerate(track_ids)],
            )
            connection.execute("UPDATE music_playlists SET updated_at = ? WHERE id = ?", (now_iso(), playlist_id))
        return self.music_library(user_id)

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

    def _task(self, connection: sqlite3.Connection, user_id: str, task_id: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)).fetchone()
        if not row:
            raise KeyError("Úloha neexistuje.")
        return row

    def _calendar_event(self, connection: sqlite3.Connection, user_id: str, event_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM calendar_events WHERE id = ? AND user_id = ?", (event_id, user_id)
        ).fetchone()
        if not row:
            raise KeyError("Udalosť neexistuje.")
        return row

    def _calendar_event_fields(self, data: dict[str, Any], current: dict[str, Any] | None = None) -> tuple[str, str, int, str, str, str, str]:
        current = current or {}
        title = self._clean_text(data.get("title", current.get("title", "")), 240)
        if not title:
            raise ValidationError("Udalosť potrebuje názov.")
        description = self._clean_text(data.get("description", current.get("description", "")), 10_000)
        all_day = self._calendar_event_all_day(data.get("allDay", current.get("allDay", True)))
        start_date = self._calendar_event_date(data.get("startDate", current.get("startDate", "")), "Začiatok udalosti")
        end_date = self._calendar_event_date(data.get("endDate", current.get("endDate", start_date)), "Koniec udalosti")
        if end_date < start_date:
            raise ValidationError("Koniec udalosti nemôže byť pred začiatkom.")
        if all_day:
            return title, description, 1, start_date, "", end_date, ""
        start_time = self._calendar_event_time(data.get("startTime", current.get("startTime", "")), "Začiatok udalosti")
        end_time = self._calendar_event_time(data.get("endTime", current.get("endTime", "")), "Koniec udalosti")
        if not start_time or not end_time:
            raise ValidationError("Časovaná udalosť potrebuje začiatok aj koniec.")
        if f"{end_date}T{end_time}" < f"{start_date}T{start_time}":
            raise ValidationError("Koniec udalosti nemôže byť pred začiatkom.")
        return title, description, 0, start_date, start_time, end_date, end_time

    @staticmethod
    def _calendar_event_all_day(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value in {0, 1}:
            return bool(value)
        raise ValidationError("Celodennosť udalosti musí byť pravdivostná hodnota.")

    @staticmethod
    def _calendar_event_date(value: Any, label: str) -> str:
        value = str(value or "").strip()
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError as error:
            raise ValidationError(f"{label} musí mať formát RRRR-MM-DD.") from error

    @staticmethod
    def _calendar_event_time(value: Any, label: str) -> str:
        value = str(value or "").strip()
        if not value:
            return ""
        try:
            return datetime.strptime(value, "%H:%M").strftime("%H:%M")
        except ValueError as error:
            raise ValidationError(f"{label} musí mať čas vo formáte HH:MM.") from error

    @staticmethod
    def _task_status(value: Any) -> str:
        status = str(value or "").strip()
        if status not in TASK_STATUSES:
            raise ValidationError("Neznámy stav úlohy.")
        return status

    @staticmethod
    def _task_priority(value: Any) -> str:
        priority = str(value or "").strip()
        if priority not in TASK_PRIORITIES:
            raise ValidationError("Neznáma priorita úlohy.")
        return priority

    @staticmethod
    def _task_target_type(value: Any) -> str:
        target_type = str(value or "").strip()
        if target_type not in TASK_TARGET_TYPES:
            raise ValidationError("Neznámy cieľ úlohy.")
        return target_type

    @staticmethod
    def _task_due_date(value: Any) -> str:
        due_date = str(value or "").strip()
        if not due_date:
            return ""
        try:
            return date.fromisoformat(due_date).isoformat()
        except ValueError as error:
            raise ValidationError("Termín úlohy musí mať formát RRRR-MM-DD.") from error

    def _assert_task_target(
        self, connection: sqlite3.Connection, user_id: str, target_type: str, target_id: str
    ) -> None:
        if target_type == "library":
            self._assert_library(connection, user_id, target_id)
        elif target_type == "element":
            self._assert_element(connection, user_id, target_id)
        else:
            self._assert_source(connection, user_id, target_id)

    @staticmethod
    def _semantic_target_type(value: Any) -> str:
        target_type = str(value or "").strip()
        if target_type not in SEMANTIC_TARGET_TYPES:
            raise ValidationError("Neznámy cieľ prepojenia.")
        return target_type

    @staticmethod
    def _semantic_element_target(row: sqlite3.Row) -> dict[str, Any]:
        label = "Článok" if row["type"] == "article" else "Poznámka"
        return {
            "targetType": "element",
            "targetId": row["id"],
            "title": row["title"] or label,
            "subtitle": f"{row['library_name']} / {label}",
            "libraryId": row["library_id"],
            "elementType": row["type"],
        }

    def _semantic_target(
        self, connection: sqlite3.Connection, user_id: str, target_type: str, target_id: str
    ) -> dict[str, Any]:
        if target_type == "element":
            row = connection.execute(
                """
                SELECT e.id, e.title, e.type, e.library_id, l.name AS library_name
                FROM elements e JOIN libraries l ON l.id = e.library_id
                WHERE e.id = ? AND l.user_id = ? AND e.type IN ('note', 'article')
                """,
                (target_id, user_id),
            ).fetchone()
            if not row:
                raise KeyError("Text neexistuje.")
            return self._semantic_element_target(row)
        if target_type == "source":
            row = connection.execute("SELECT id, title FROM sources WHERE id = ? AND user_id = ?", (target_id, user_id)).fetchone()
            if not row:
                raise KeyError("Zdroj neexistuje.")
            return {"targetType": "source", "targetId": row["id"], "title": row["title"], "subtitle": "Zdroj"}
        if target_type == "tutorial_page":
            row = connection.execute(
                """
                SELECT p.id, p.title, p.language_id, l.title AS language_title
                FROM tutorial_pages p JOIN tutorial_languages l ON l.id = p.language_id
                WHERE p.id = ? AND l.user_id = ?
                """,
                (target_id, user_id),
            ).fetchone()
            if not row:
                raise KeyError("Stránka učebnice neexistuje.")
            return {"targetType": "tutorial_page", "targetId": row["id"], "title": row["title"], "subtitle": f"Učebnica / {row['language_title']}", "languageId": row["language_id"]}
        if target_type == "task":
            row = connection.execute("SELECT id, title, status, due_date FROM tasks WHERE id = ? AND user_id = ?", (target_id, user_id)).fetchone()
            if not row:
                raise KeyError("Úloha neexistuje.")
            return {"targetType": "task", "targetId": row["id"], "title": row["title"], "subtitle": "Hotová" if row["status"] == "done" else (f"Do {row['due_date']}" if row["due_date"] else "Úloha"), "status": row["status"]}
        row = connection.execute(
            "SELECT id, title, all_day, start_date, start_time FROM calendar_events WHERE id = ? AND user_id = ?",
            (target_id, user_id),
        ).fetchone()
        if not row:
            raise KeyError("Udalosť neexistuje.")
        return {"targetType": "calendar_event", "targetId": row["id"], "title": row["title"], "subtitle": row["start_date"] if row["all_day"] else f"{row['start_date']} {row['start_time']}"}

    @staticmethod
    def _delete_semantic_links_for_target(
        connection: sqlite3.Connection, user_id: str, target_type: str, target_id: str
    ) -> None:
        connection.execute(
            """
            DELETE FROM semantic_links
            WHERE user_id = ?
              AND ((first_type = ? AND first_id = ?) OR (second_type = ? AND second_id = ?))
            """,
            (user_id, target_type, target_id, target_type, target_id),
        )

    def _task_link_target(
        self, connection: sqlite3.Connection, user_id: str, link: sqlite3.Row
    ) -> dict[str, Any] | None:
        target_type = link["target_type"]
        target_id = link["target_id"]
        target: sqlite3.Row | None
        if target_type == "library":
            target = connection.execute(
                "SELECT id, name FROM libraries WHERE id = ? AND user_id = ?", (target_id, user_id)
            ).fetchone()
            if not target:
                return None
            return {
                "id": link["id"],
                "targetType": target_type,
                "targetId": target["id"],
                "title": target["name"],
                "subtitle": "Knižnica",
                "libraryId": target["id"],
            }
        if target_type == "element":
            target = connection.execute(
                """
                SELECT e.id, e.title, e.type, e.library_id, l.name AS library_name
                FROM elements e JOIN libraries l ON l.id = e.library_id
                WHERE e.id = ? AND l.user_id = ?
                """,
                (target_id, user_id),
            ).fetchone()
            if not target:
                return None
            return {
                "id": link["id"],
                "targetType": target_type,
                "targetId": target["id"],
                "title": target["title"],
                "subtitle": f"{target['library_name']} / {'Článok' if target['type'] == 'article' else 'Poznámka'}",
                "libraryId": target["library_id"],
                "elementType": target["type"],
            }
        target = connection.execute(
            "SELECT id, title, kind FROM sources WHERE id = ? AND user_id = ?", (target_id, user_id)
        ).fetchone()
        if not target:
            return None
        return {
            "id": link["id"],
            "targetType": target_type,
            "targetId": target["id"],
            "title": target["title"],
            "subtitle": "Zdroj",
            "sourceKind": target["kind"],
        }

    @staticmethod
    def _assert_source_file(connection: sqlite3.Connection, source_id: str, file_id: str) -> None:
        if not connection.execute(
            "SELECT 1 FROM source_files WHERE id = ? AND source_id = ?", (file_id, source_id)
        ).fetchone():
            raise KeyError("Príloha neexistuje.")

    @staticmethod
    def _music_track(connection: sqlite3.Connection, user_id: str, track_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM music_tracks WHERE id = ? AND user_id = ?", (track_id, user_id)
        ).fetchone()
        if not row:
            raise KeyError("Skladba neexistuje.")
        return row

    @staticmethod
    def _music_playlist(connection: sqlite3.Connection, user_id: str, playlist_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM music_playlists WHERE id = ? AND user_id = ?", (playlist_id, user_id)
        ).fetchone()
        if not row:
            raise KeyError("Playlist neexistuje.")
        return row

    @staticmethod
    def _blob_is_referenced(connection: sqlite3.Connection, blob_hash: str) -> bool:
        return bool(
            connection.execute(
                """
                SELECT 1 FROM source_files WHERE blob_hash = ?
                UNION ALL
                SELECT 1 FROM music_tracks WHERE blob_hash = ?
                LIMIT 1
                """,
                (blob_hash, blob_hash),
            ).fetchone()
        )

    @staticmethod
    def _music_duration(value: Any) -> float:
        if isinstance(value, bool):
            raise ValidationError("Dĺžka skladby musí byť číslo.")
        try:
            duration = float(value)
        except (TypeError, ValueError) as error:
            raise ValidationError("Dĺžka skladby musí byť číslo.") from error
        if not 0 <= duration <= 43_200:
            raise ValidationError("Dĺžka skladby je mimo povoleného rozsahu.")
        return round(duration, 3)

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
    def _task_row(row: sqlite3.Row) -> dict[str, Any]:
        task = dict(row)
        return {
            "id": task["id"],
            "title": task["title"],
            "description": task["description"],
            "tags": Database._tags_from_json(task.get("tags_json", "[]")),
            "status": task["status"],
            "priority": task["priority"],
            "dueDate": task["due_date"],
            "completedAt": task["completed_at"],
            "createdAt": task["created_at"],
            "updatedAt": task["updated_at"],
            "linkCount": int(task.get("link_count") or 0),
        }

    @staticmethod
    def _calendar_event_row(row: sqlite3.Row) -> dict[str, Any]:
        event = dict(row)
        return {
            "id": event["id"],
            "title": event["title"],
            "description": event["description"],
            "tags": Database._tags_from_json(event.get("tags_json", "[]")),
            "allDay": bool(event["all_day"]),
            "startDate": event["start_date"],
            "startTime": event["start_time"],
            "endDate": event["end_date"],
            "endTime": event["end_time"],
            "createdAt": event["created_at"],
            "updatedAt": event["updated_at"],
        }

    @staticmethod
    def _source_row(row: sqlite3.Row) -> dict[str, Any]:
        source = dict(row)
        source.pop("user_id", None)
        metadata_json = source.pop("metadata_json", "{}")
        source["tags"] = Database._tags_from_json(source.pop("tags_json", "[]"))
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

    @staticmethod
    def _music_track_row(row: sqlite3.Row) -> dict[str, Any]:
        track = dict(row)
        return {
            "id": track["id"],
            "originalName": track["original_name"],
            "mimeType": track["mime_type"],
            "sizeBytes": int(track["size_bytes"]),
            "title": track["title"],
            "artist": track["artist"],
            "album": track["album"],
            "year": track["release_year"],
            "trackNumber": track["track_number"],
            "genre": track["genre"],
            "durationSeconds": float(track["duration_seconds"]),
            "createdAt": track["created_at"],
            "updatedAt": track["updated_at"],
        }

    @staticmethod
    def _music_playlist_row(row: sqlite3.Row) -> dict[str, Any]:
        playlist = dict(row)
        return {
            "id": playlist["id"],
            "title": playlist["title"],
            "createdAt": playlist["created_at"],
            "updatedAt": playlist["updated_at"],
            "trackCount": int(playlist.get("track_count") or 0),
        }
