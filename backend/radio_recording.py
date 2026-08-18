"""Server-side recording of saved internet radio stations."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .database import Database, ValidationError


RECORDING_OUTPUT_MIME_TYPE = "audio/mpeg"
FFMPEG_LOG_LIMIT = 1_200


@dataclass
class ActiveRecording:
    recording_id: str
    user_id: str
    process: subprocess.Popen[bytes]
    partial_path: Path
    final_path: Path
    started_monotonic: float
    schedule_id: str = ""


class RadioRecordingManager:
    """Owns the short-lived ffmpeg processes used for manual radio recordings."""

    def __init__(self, root: Path, database: Database) -> None:
        self.root = root
        self.database = database
        self.ffmpeg_path = shutil.which("ffmpeg")
        self.ffprobe_path = shutil.which("ffprobe")
        self._lock = threading.RLock()
        self._active_by_user: dict[str, ActiveRecording] = {}
        self._stop_requested: set[str] = set()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database.interrupt_running_radio_recordings()
        self.database.interrupt_running_radio_recording_schedules()
        self._remove_partial_files()

    def start(
        self, user_id: str, station_id: str, *, maximum_seconds: int | None = None, schedule_id: str = ""
    ) -> dict[str, Any]:
        if not self.ffmpeg_path:
            raise ValidationError("Nahrávanie rádia vyžaduje nainštalovaný ffmpeg.")
        with self._lock:
            if user_id in self._active_by_user:
                raise ValidationError("Práve už prebieha jedna nahrávka rádia.")

            station = self.database.radio_station_stream(user_id, station_id)
            limits = self.database.radio_recording_limits(user_id)
            if maximum_seconds is None:
                maximum_seconds = limits["maxDurationSeconds"]
            else:
                maximum_seconds = min(limits["maxDurationSeconds"], max(1, int(maximum_seconds)))
            recording_id = str(uuid.uuid4())
            user_root = self._user_directory(user_id)
            final_path = user_root / f"{recording_id}.mp3"
            partial_path = user_root / f"{recording_id}.partial.mp3"
            self.database.create_radio_recording(
                user_id,
                recording_id,
                station_id,
                str(station["title"]),
                final_path.name,
            )
            command = [
                self.ffmpeg_path,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "warning",
                "-i",
                str(station["stream_url"]),
                "-vn",
                "-t",
                str(maximum_seconds),
                "-fs",
                str(limits["maxBytes"]),
                "-c:a",
                "libmp3lame",
                "-b:a",
                "128k",
                "-f",
                "mp3",
                "-y",
                str(partial_path),
            ]
            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                )
            except OSError as error:
                self.database.finish_radio_recording(
                    user_id, recording_id, status="failed", error="Proces ffmpeg sa nepodarilo spustiť."
                )
                raise ValidationError("Nahrávanie rádia sa nepodarilo spustiť.") from error

            active = ActiveRecording(
                recording_id=recording_id,
                user_id=user_id,
                process=process,
                partial_path=partial_path,
                final_path=final_path,
                started_monotonic=time.monotonic(),
                schedule_id=schedule_id,
            )
            self._active_by_user[user_id] = active
            thread = threading.Thread(target=self._watch, args=(active,), name=f"radio-recording-{recording_id[:8]}", daemon=True)
            thread.start()
        library = self.database.music_library(user_id)
        library["recordingId"] = recording_id
        return library

    def stop(self, user_id: str, recording_id: str) -> dict[str, Any]:
        with self._lock:
            active = self._active_by_user.get(user_id)
            if not active or active.recording_id != recording_id:
                raise ValidationError("Táto nahrávka už nebeží.")
            self._stop_requested.add(recording_id)
            self.database.mark_radio_recording_stopping(user_id, recording_id)
            self._terminate(active.process)
        return self.database.music_library(user_id)

    def delete(self, user_id: str, recording_id: str) -> dict[str, Any]:
        with self._lock:
            active = self._active_by_user.get(user_id)
            if active and active.recording_id == recording_id:
                raise ValidationError("Najprv zastav prebiehajúcu nahrávku.")
            recording = self.database.delete_radio_recording(user_id, recording_id)
        self.path_for_recording(user_id, recording).unlink(missing_ok=True)
        return self.database.music_library(user_id)

    def path_for_recording(self, user_id: str, recording: dict[str, Any]) -> Path:
        filename = Path(str(recording.get("filename", ""))).name
        if not filename or not filename.endswith(".mp3"):
            raise ValidationError("Záznam má neplatný názov súboru.")
        return self._user_directory(user_id) / filename

    def _watch(self, active: ActiveRecording) -> None:
        stderr = b""
        try:
            _, stderr = active.process.communicate()
        finally:
            elapsed_seconds = max(0, round(time.monotonic() - active.started_monotonic))
            with self._lock:
                manually_stopped = active.recording_id in self._stop_requested
                self._stop_requested.discard(active.recording_id)
                current = self._active_by_user.get(active.user_id)
                if current and current.recording_id == active.recording_id:
                    self._active_by_user.pop(active.user_id, None)

            size_bytes = active.partial_path.stat().st_size if active.partial_path.is_file() else 0
            if size_bytes > 0:
                try:
                    active.partial_path.replace(active.final_path)
                except OSError as error:
                    self.database.finish_radio_recording(
                        active.user_id,
                        active.recording_id,
                        status="failed",
                        duration_seconds=elapsed_seconds,
                        error=f"Záznam sa nepodarilo dokončiť: {error}",
                    )
                    self._finish_schedule(active, status="failed", error=f"Záznam sa nepodarilo dokončiť: {error}")
                    return
                duration_seconds = self._recording_duration(active.final_path, elapsed_seconds)
                self.database.finish_radio_recording(
                    active.user_id,
                    active.recording_id,
                    status="stopped" if manually_stopped else "completed",
                    size_bytes=size_bytes,
                    duration_seconds=duration_seconds,
                )
                self._finish_schedule(active, status="completed")
                return

            error_text = stderr.decode("utf-8", errors="replace").strip().replace("\n", " ")
            if manually_stopped:
                error_text = "Nahrávanie bolo zastavené skôr, než vznikol záznam."
            elif not error_text:
                error_text = "Stream neposlal žiadne zvukové dáta."
            self.database.finish_radio_recording(
                active.user_id,
                active.recording_id,
                status="failed",
                duration_seconds=elapsed_seconds,
                error=error_text[:FFMPEG_LOG_LIMIT],
            )
            self._finish_schedule(active, status="failed", error=error_text[:FFMPEG_LOG_LIMIT])
            active.partial_path.unlink(missing_ok=True)

    def _finish_schedule(self, active: ActiveRecording, *, status: str, error: str = "") -> None:
        if not active.schedule_id:
            return
        try:
            self.database.finish_radio_recording_schedule(
                active.user_id,
                active.schedule_id,
                status=status,
                recording_id=active.recording_id,
                error=error,
            )
        except (KeyError, ValidationError):
            pass

    def _user_directory(self, user_id: str) -> Path:
        directory = self.root / user_id
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _remove_partial_files(self) -> None:
        for path in self.root.glob("*/*.partial.mp3"):
            path.unlink(missing_ok=True)

    def _recording_duration(self, path: Path, fallback_seconds: int) -> int:
        if not self.ffprobe_path:
            return fallback_seconds
        try:
            result = subprocess.run(
                [
                    self.ffprobe_path,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=8,
            )
            if result.returncode == 0:
                return max(0, round(float(result.stdout.strip())))
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
        return fallback_seconds

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
