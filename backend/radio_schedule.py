"""One-off server-side plans for radio recordings."""

from __future__ import annotations

import threading

from .database import Database, ValidationError
from .radio_recording import RadioRecordingManager


SCHEDULE_POLL_SECONDS = 3


class RadioRecordingScheduler:
    """Starts due radio recordings without requiring an open browser tab."""

    def __init__(self, database: Database, recordings: RadioRecordingManager) -> None:
        self.database = database
        self.recordings = recordings
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.run_once()
        self._thread = threading.Thread(target=self._run, name="radio-recording-scheduler", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.wait(SCHEDULE_POLL_SECONDS):
            self.run_once()

    def run_once(self) -> None:
        for schedule in self.database.claim_due_radio_recording_schedules():
            try:
                result = self.recordings.start(
                    str(schedule["user_id"]),
                    str(schedule["station_id"]),
                    maximum_seconds=int(schedule["duration_seconds"]),
                    schedule_id=str(schedule["id"]),
                )
                self.database.attach_radio_recording_schedule(
                    str(schedule["user_id"]), str(schedule["id"]), str(result["recordingId"])
                )
            except (KeyError, ValidationError, OSError) as error:
                self.database.finish_radio_recording_schedule(
                    str(schedule["user_id"]),
                    str(schedule["id"]),
                    status="failed",
                    error=str(error),
                )
