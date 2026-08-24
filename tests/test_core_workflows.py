from __future__ import annotations

import io
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from backend.auth import AuthError, AuthService
from backend.calendar_reminders import CalendarReminderScheduler
from backend.data_integrity import DataIntegrityService
from backend.database import Database, ValidationError
from backend.files import FileStore
from backend.radio_recording import RadioRecordingManager


class RecordingNotifier:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def send(self, event: dict[str, object]) -> tuple[bool, str]:
        self.events.append(event)
        return True, ""


class FailingNotifier:
    def send(self, event: dict[str, object]) -> tuple[bool, str]:
        raise OSError("Služba oznámení nie je dostupná.")


class WorkspaceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="poznamkovnik-core-", dir="/tmp"))
        self.database = Database(self.root / "poznamkovnik.sqlite3")
        self.database.initialize()
        self.auth = AuthService(self.database)
        self.user, self.token = self.auth.setup("Tester", "testovacie-heslo")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_authentication_lifecycle(self) -> None:
        self.assertEqual(self.auth.session_user(self.token), self.user)
        with self.assertRaises(AuthError):
            self.auth.login("Tester", "nespravne-heslo")
        logged_user, logged_token = self.auth.login("tester", "testovacie-heslo")
        self.assertEqual(logged_user, self.user)
        self.assertEqual(self.auth.session_user(logged_token), self.user)
        self.auth.logout(logged_token)
        self.assertIsNone(self.auth.session_user(logged_token))

    def test_source_links_across_workspace_sections(self) -> None:
        user_id = self.user["id"]
        self.database.replace_workspace(
            user_id,
            {
                "libraries": [
                    {"id": "library-test", "name": "Výskum", "tags": ["test"]},
                ],
                "libraryElements": {
                    "library-test": [
                        {"id": "folder-test", "type": "folder", "title": "Podklady"},
                        {
                            "id": "note-test",
                            "type": "note",
                            "parentId": "folder-test",
                            "title": "Poznámka k zdroju",
                            "content": "Overenie väzieb.",
                            "tags": ["test"],
                        },
                    ]
                },
            },
        )
        source = self.database.create_source(
            user_id,
            {
                "id": "source-test",
                "title": "Overovaný zdroj",
                "kind": "article",
                "description": "Zdroj pre automatický test.",
                "tags": ["test", "zdroj"],
            },
        )
        self.database.link_source_library(user_id, source["id"], "library-test", "Spoločný podklad.")
        self.database.link_source_element(
            user_id,
            source["id"],
            {
                "id": "element-source-test",
                "elementId": "note-test",
                "relationType": "citation",
                "locator": "s. 12",
                "note": "Overenie citácie.",
            },
        )
        task_list = self.database.create_task_list(user_id, {"id": "task-list-test", "title": "Testy"})
        task = self.database.create_task(
            user_id,
            {
                "id": "task-test",
                "title": "Skontrolovať zdroj",
                "description": "Overiť väzbu zdroja na úlohu.",
                "listIds": [task_list["id"]],
                "tags": ["test"],
            },
        )
        self.database.link_task(
            user_id,
            task["id"],
            {"id": "task-source-test", "targetType": "source", "targetId": source["id"]},
        )
        event = self.database.create_calendar_event(
            user_id,
            {
                "id": "calendar-test",
                "title": "Kontrola zdroja",
                "allDay": True,
                "startDate": "2026-09-01",
                "endDate": "2026-09-01",
            },
        )
        self.database.link_calendar_event(
            user_id,
            event["id"],
            {"id": "calendar-source-test", "targetType": "source", "targetId": source["id"]},
        )

        detail = self.database.source_detail(user_id, source["id"])
        self.assertEqual(detail["libraries"], [{"id": "library-test", "name": "Výskum", "note": "Spoločný podklad."}])
        self.assertEqual(detail["elements"][0]["id"], "note-test")
        self.assertEqual(detail["elements"][0]["relationType"], "citation")
        self.assertEqual([item["id"] for item in detail["tasks"]], [task["id"]])
        self.assertEqual([item["id"] for item in detail["calendarEvents"]], [event["id"]])
        task_detail = self.database.task_detail(user_id, task["id"])
        self.assertEqual([item["id"] for item in task_detail["lists"]], [task_list["id"]])
        self.assertEqual(task_detail["lists"][0]["path"], [task_list["title"]])

    def test_data_integrity_reports_missing_source_file(self) -> None:
        user_id = self.user["id"]
        files = FileStore(self.root / "files")
        recording_manager = RadioRecordingManager(self.root / "radio-recordings", self.database)
        integrity = DataIntegrityService(self.database, files, recording_manager)
        source = self.database.create_source(
            user_id,
            {"id": "integrity-source", "title": "Overovaný súbor", "kind": "attachment"},
        )
        uploaded = files.store_upload(io.BytesIO(b"kontrola integrity"), "kontrola.txt", "text/plain")
        self.database.add_source_file(user_id, source["id"], "integrity-file", uploaded)

        healthy = integrity.inspect(user_id)
        self.assertEqual(healthy["status"], "ok")
        self.assertEqual(healthy["checkedFiles"], 1)

        files.path_for_hash(str(uploaded["blobHash"])).unlink()
        damaged = integrity.inspect(user_id)
        self.assertEqual(damaged["status"], "error")
        self.assertEqual(damaged["issues"][0]["kind"], "missing")
        self.assertEqual(damaged["issues"][0]["targetType"], "source")
        self.assertEqual(damaged["issues"][0]["targetId"], source["id"])

    def test_calendar_event_reminder_survives_update_and_backup(self) -> None:
        user_id = self.user["id"]
        event = self.database.create_calendar_event(
            user_id,
            {
                "id": "calendar-reminder-test",
                "title": "Kontrola pripomienky",
                "allDay": False,
                "startDate": "2026-09-01",
                "startTime": "10:00",
                "endDate": "2026-09-01",
                "endTime": "10:30",
                "reminderMinutes": 30,
            },
        )
        self.assertEqual(event["reminderMinutes"], 30)

        updated = self.database.update_calendar_event(user_id, event["id"], {"reminderMinutes": 1_440})
        self.assertEqual(updated["reminderMinutes"], 1_440)
        with self.assertRaises(ValidationError):
            self.database.update_calendar_event(user_id, event["id"], {"reminderMinutes": 1.5})

        self.database.save_preferences(user_id, {"calendarNotificationsEnabled": False})
        snapshot = self.database.backup_snapshot(user_id)
        self.assertEqual(snapshot["calendarEvents"][0]["reminder_minutes"], 1_440)
        self.assertEqual(snapshot["preferences"]["calendar_notifications_enabled"], 0)
        self.database.restore_backup_snapshot(user_id, snapshot)
        restored = self.database.calendar_event_detail(user_id, event["id"])
        self.assertEqual(restored["reminderMinutes"], 1_440)
        self.assertEqual(self.database.preferences(user_id)["calendarNotificationsEnabled"], False)

    def test_recurring_calendar_event_keeps_occurrence_exceptions_and_backup(self) -> None:
        user_id = self.user["id"]
        event = self.database.create_calendar_event(
            user_id,
            {
                "id": "calendar-recurring-test",
                "title": "Týždenná kontrola",
                "allDay": True,
                "startDate": "2026-09-01",
                "endDate": "2026-09-01",
                "recurrenceKind": "weekly",
                "recurrenceInterval": 1,
                "recurrenceUntil": "2026-09-22",
            },
        )
        self.assertEqual(event["recurrenceKind"], "weekly")
        dates = [item["startDate"] for item in self.database.list_calendar_events(user_id, "2026-09-01", "2026-09-30")]
        self.assertEqual(dates, ["2026-09-01", "2026-09-08", "2026-09-15", "2026-09-22"])

        moved = self.database.update_calendar_event(
            user_id,
            event["id"],
            {
                "scope": "occurrence",
                "occurrenceDate": "2026-09-08",
                "title": "Presunutá kontrola",
                "startDate": "2026-09-09",
                "endDate": "2026-09-09",
            },
        )
        self.assertTrue(moved["isOccurrence"])
        self.assertTrue(moved["isOverride"])
        self.assertEqual(moved["startDate"], "2026-09-09")

        self.database.delete_calendar_event(
            user_id, event["id"], scope="occurrence", occurrence_date="2026-09-15"
        )
        occurrences = self.database.list_calendar_events(user_id, "2026-09-01", "2026-09-30")
        self.assertEqual(
            [(item["startDate"], item["title"]) for item in occurrences],
            [
                ("2026-09-01", "Týždenná kontrola"),
                ("2026-09-09", "Presunutá kontrola"),
                ("2026-09-22", "Týždenná kontrola"),
            ],
        )

        snapshot = self.database.backup_snapshot(user_id)
        self.assertEqual(len(snapshot["calendarEventOverrides"]), 2)
        self.database.restore_backup_snapshot(user_id, snapshot)
        restored = self.database.list_calendar_events(user_id, "2026-09-01", "2026-09-30")
        self.assertEqual(
            [(item["startDate"], item["title"]) for item in restored],
            [("2026-09-01", "Týždenná kontrola"), ("2026-09-09", "Presunutá kontrola"), ("2026-09-22", "Týždenná kontrola")],
        )

    def test_recurring_calendar_reminder_is_delivered_for_each_occurrence(self) -> None:
        user_id = self.user["id"]
        notifier = RecordingNotifier()
        scheduler = CalendarReminderScheduler(self.database, notifier)
        event = self.database.create_calendar_event(
            user_id,
            {
                "id": "calendar-recurring-reminder-test",
                "title": "Denná pripomienka",
                "allDay": False,
                "startDate": "2026-09-01",
                "startTime": "09:30",
                "endDate": "2026-09-01",
                "endTime": "10:00",
                "reminderMinutes": 30,
                "recurrenceKind": "daily",
            },
        )
        scheduler.run_once(datetime(2026, 9, 1, 9, 0))
        scheduler.run_once(datetime(2026, 9, 2, 9, 0))
        self.assertEqual([item["id"] for item in notifier.events], [event["id"], event["id"]])
        self.assertEqual([item["occurrenceDate"] for item in notifier.events], ["2026-09-01", "2026-09-02"])

    def test_calendar_reminder_is_delivered_once_and_can_be_disabled(self) -> None:
        user_id = self.user["id"]
        notifier = RecordingNotifier()
        scheduler = CalendarReminderScheduler(self.database, notifier)
        moment = datetime(2026, 9, 1, 9, 0)
        event = self.database.create_calendar_event(
            user_id,
            {
                "id": "calendar-desktop-reminder",
                "title": "Skontrolovať upozornenie",
                "allDay": False,
                "startDate": "2026-09-01",
                "startTime": "09:30",
                "endDate": "2026-09-01",
                "endTime": "10:00",
                "reminderMinutes": 30,
            },
        )

        scheduler.run_once(moment)
        scheduler.run_once(moment)
        self.assertEqual([item["id"] for item in notifier.events], [event["id"]])
        with self.database.connect() as connection:
            delivery = connection.execute(
                "SELECT status FROM calendar_reminder_deliveries WHERE event_id = ?", (event["id"],)
            ).fetchone()
        self.assertEqual(delivery["status"], "sent")

        unavailable_event = self.database.create_calendar_event(
            user_id,
            {
                "id": "calendar-desktop-reminder-unavailable",
                "title": "Nedostupné upozornenie",
                "allDay": False,
                "startDate": "2026-09-01",
                "startTime": "09:30",
                "endDate": "2026-09-01",
                "endTime": "10:00",
                "reminderMinutes": 30,
            },
        )
        CalendarReminderScheduler(self.database, FailingNotifier()).run_once(moment)
        with self.database.connect() as connection:
            unavailable_delivery = connection.execute(
                "SELECT status, error FROM calendar_reminder_deliveries WHERE event_id = ?", (unavailable_event["id"],)
            ).fetchone()
        self.assertEqual(unavailable_delivery["status"], "unavailable")
        self.assertIn("Služba oznámení", unavailable_delivery["error"])

        self.database.save_preferences(user_id, {"calendarNotificationsEnabled": False})
        disabled_event = self.database.create_calendar_event(
            user_id,
            {
                "id": "calendar-desktop-reminder-disabled",
                "title": "Toto sa nezobrazí",
                "allDay": False,
                "startDate": "2026-09-01",
                "startTime": "09:30",
                "endDate": "2026-09-01",
                "endTime": "10:00",
                "reminderMinutes": 30,
            },
        )
        scheduler.run_once(moment)
        self.assertEqual([item["id"] for item in notifier.events], [event["id"]])
        self.assertEqual(self.database.preferences(user_id)["calendarNotificationsEnabled"], False)
        self.assertEqual(disabled_event["id"], "calendar-desktop-reminder-disabled")


class DocumentProjectMigrationTest(unittest.TestCase):
    def test_existing_project_gets_page_number_defaults(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="poznamkovnik-migration-", dir="/tmp"))
        try:
            path = root / "legacy.sqlite3"
            connection = sqlite3.connect(path)
            connection.executescript(
                """
                CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE document_projects (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL,
                    output_page_size TEXT NOT NULL DEFAULT 'keep', image_dpi INTEGER NOT NULL DEFAULT 144,
                    history_position INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                """
            )
            connection.execute("INSERT INTO users VALUES ('user-test', 'Tester', 'hash', '2026-01-01T00:00:00+00:00')")
            connection.execute(
                "INSERT INTO document_projects VALUES ('project-test', 'user-test', 'Starší projekt', 'keep', 144, 0, ?, ?)",
                ("2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
            )
            connection.commit()
            connection.close()

            database = Database(path)
            database.initialize()
            detail = database.document_project_detail("user-test", "project-test")
            self.assertEqual(detail["project"]["pageNumberPosition"], "none")
            self.assertEqual(detail["project"]["pageNumberStart"], 1)
        finally:
            shutil.rmtree(root, ignore_errors=True)
