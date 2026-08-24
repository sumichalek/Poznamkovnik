from __future__ import annotations

import shutil
import subprocess
import threading
from datetime import datetime
from typing import Any

from .database import Database


CALENDAR_REMINDER_POLL_SECONDS = 30


class DesktopNotifier:
    """Small wrapper around the desktop notification service available on Linux."""

    def __init__(self, command: str | None = None) -> None:
        self.command = command if command is not None else shutil.which("notify-send")

    def send(self, event: dict[str, Any]) -> tuple[bool, str]:
        if not self.command:
            return False, "Nástroj notify-send nie je v systéme dostupný."

        title = f"Pripomienka: {event.get('title') or 'Udalosť kalendára'}"
        body = self._body(event)
        try:
            result = subprocess.run(
                [
                    self.command,
                    "--app-name=Poznámkovník",
                    "--urgency=normal",
                    "--expire-time=12000",
                    title,
                    body,
                ],
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return False, str(error)
        if result.returncode == 0:
            return True, ""
        return False, (result.stderr or result.stdout or "Desktopové prostredie upozornenie odmietlo.").strip()

    @staticmethod
    def _body(event: dict[str, Any]) -> str:
        if event.get("allDay"):
            when = f"Celodenná udalosť - {event.get('startDate', '')}"
        else:
            when = f"{event.get('startDate', '')} o {event.get('startTime', '')}"
        description = str(event.get("description") or "").strip().replace("\n", " ")
        if not description:
            return when
        return f"{when}\n{description[:240]}"


class CalendarReminderScheduler:
    """Delivers due calendar reminders even while the browser is closed."""

    def __init__(self, database: Database, notifier: DesktopNotifier) -> None:
        self.database = database
        self.notifier = notifier
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.run_once()
        self._thread = threading.Thread(target=self._run, name="calendar-reminder-scheduler", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.wait(CALENDAR_REMINDER_POLL_SECONDS):
            self.run_once()

    def run_once(self, now: datetime | None = None) -> None:
        for reminder in self.database.claim_due_calendar_reminders(now):
            delivery_error = ""
            try:
                delivered, delivery_error = self.notifier.send(reminder["event"])
            except Exception as error:  # Defensive: an unavailable desktop must not stop the scheduler.
                delivered = False
                delivery_error = str(error)
            self.database.finish_calendar_reminder_delivery(
                str(reminder["userId"]),
                str(reminder["event"]["id"]),
                str(reminder["reminderAt"]),
                delivered=delivered,
                error="" if delivered else delivery_error,
            )
