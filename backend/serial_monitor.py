"""Explicit, bounded serial monitor sessions for firmware projects.

The monitor opens a configured local character device only after an explicit
request.  It never scans, programs, or resets a board on its own.
"""

from __future__ import annotations

import os
import select
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

try:
    import termios
except ImportError:  # pragma: no cover - the application currently targets POSIX desktops.
    termios = None  # type: ignore[assignment]

from .code_runner import CodeRunnerError


DEFAULT_SERIAL_BAUD_RATE = 115200
MAX_SERIAL_WRITE_BYTES = 8 * 1024
MAX_SERIAL_BUFFER_CHARACTERS = 96 * 1024
SERIAL_BAUD_RATES = (300, 600, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600)


class SerialMonitorError(CodeRunnerError):
    """A user-visible problem while opening, reading, or writing a serial port."""


class SerialDevice(Protocol):
    def read(self, maximum: int) -> bytes: ...

    def write(self, data: bytes) -> int: ...

    def close(self) -> None: ...


class PosixSerialDevice:
    """Small 8N1 serial wrapper that restores terminal settings on close."""

    def __init__(self, file_descriptor: int, original_settings: list[Any]) -> None:
        self._fd = file_descriptor
        self._original_settings = original_settings
        self._closed = False
        self._lock = threading.RLock()

    @classmethod
    def open(cls, port: str, baud_rate: int) -> "PosixSerialDevice":
        if termios is None:
            raise SerialMonitorError("Sériový monitor je dostupný len v lokálnom POSIX prostredí.")
        speed = getattr(termios, f"B{baud_rate}", None)
        if speed is None:
            raise SerialMonitorError("Zvolená prenosová rýchlosť nie je na tomto systéme dostupná.")
        descriptor = -1
        original: list[Any] | None = None
        try:
            descriptor = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            original = termios.tcgetattr(descriptor)
            settings = termios.tcgetattr(descriptor)
            settings[0] = 0
            settings[1] = 0
            control_mask = termios.PARENB | termios.CSTOPB | termios.CSIZE
            if hasattr(termios, "CRTSCTS"):
                control_mask |= termios.CRTSCTS
            settings[2] = (settings[2] & ~control_mask) | termios.CS8 | termios.CREAD | termios.CLOCAL
            settings[3] = 0
            settings[4] = speed
            settings[5] = speed
            settings[6][termios.VMIN] = 0
            settings[6][termios.VTIME] = 0
            termios.tcsetattr(descriptor, termios.TCSANOW, settings)
            return cls(descriptor, original)
        except OSError as error:
            if descriptor >= 0:
                if original is not None:
                    try:
                        termios.tcsetattr(descriptor, termios.TCSANOW, original)
                    except OSError:
                        pass
                os.close(descriptor)
            raise SerialMonitorError("Sériový port sa nepodarilo otvoriť.") from error

    def read(self, maximum: int) -> bytes:
        with self._lock:
            if self._closed:
                return b""
            try:
                readable, _, _ = select.select([self._fd], [], [], 0.15)
                return os.read(self._fd, maximum) if readable else b""
            except BlockingIOError:
                return b""
            except OSError as error:
                if self._closed:
                    return b""
                raise SerialMonitorError("Spojenie so sériovým portom sa prerušilo.") from error

    def write(self, data: bytes) -> int:
        with self._lock:
            if self._closed:
                raise SerialMonitorError("Sériový monitor už nie je pripojený.")
            remaining = memoryview(data)
            total = 0
            try:
                while remaining:
                    _, writable, _ = select.select([], [self._fd], [], 1.0)
                    if not writable:
                        raise SerialMonitorError("Sériový port neprijal odoslané dáta včas.")
                    written = os.write(self._fd, remaining)
                    total += written
                    remaining = remaining[written:]
            except OSError as error:
                raise SerialMonitorError("Zápis do sériového portu zlyhal.") from error
            return total

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                if termios is not None:
                    termios.tcsetattr(self._fd, termios.TCSANOW, self._original_settings)
            except OSError:
                pass
            finally:
                try:
                    os.close(self._fd)
                except OSError:
                    pass


@dataclass
class _SerialSession:
    id: str
    user_id: str
    project_id: str
    port: str
    baud_rate: int
    device: SerialDevice
    opened_at: float = field(default_factory=time.monotonic)
    stop_requested: threading.Event = field(default_factory=threading.Event)
    lock: threading.RLock = field(default_factory=threading.RLock)
    buffer: str = ""
    buffer_offset: int = 0
    received_bytes: int = 0
    sent_bytes: int = 0
    dropped_characters: int = 0
    connected: bool = True
    error: str = ""
    thread: threading.Thread | None = None


class SerialMonitor:
    """Owns per-project monitor sessions and their bounded text buffers."""

    def __init__(self, *, opener: Callable[[str, int], SerialDevice] = PosixSerialDevice.open) -> None:
        self._opener = opener
        self._lock = threading.RLock()
        self._sessions: dict[str, _SerialSession] = {}
        self._projects: dict[tuple[str, str], str] = {}

    def status(self) -> dict[str, Any]:
        available = termios is not None and bool(SERIAL_BAUD_RATES)
        return {
            "available": available,
            "baudRates": list(SERIAL_BAUD_RATES) if available else [],
            "defaultBaudRate": DEFAULT_SERIAL_BAUD_RATE,
            "message": "Sériový monitor je pripravený; port otvorí až explicitné pripojenie."
            if available
            else "Sériový monitor nie je na tomto systéme dostupný.",
        }

    def start(self, user_id: str, project_id: str, entry: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        if str(entry.get("projectKind") or "") != "firmware":
            raise SerialMonitorError("Sériový monitor je určený pre firmvérový projekt.")
        port = self._serial_port(entry.get("firmwareSerialPort"))
        baud_rate = self._baud_rate(data.get("baudRate", entry.get("firmwareSerialBaud", DEFAULT_SERIAL_BAUD_RATE)))
        key = (user_id, project_id)
        with self._lock:
            previous_id = self._projects.get(key)
        if previous_id:
            self.stop(user_id, project_id, previous_id)
        device = self._open(port, baud_rate)
        session = _SerialSession(str(uuid.uuid4()), user_id, project_id, port, baud_rate, device)
        thread = threading.Thread(target=self._read_loop, args=(session,), name=f"serial-monitor-{session.id[:8]}", daemon=True)
        session.thread = thread
        with self._lock:
            self._sessions[session.id] = session
            self._projects[key] = session.id
        thread.start()
        return self.poll(user_id, project_id, session.id, 0)

    def poll(self, user_id: str, project_id: str, session_id: str, cursor: Any) -> dict[str, Any]:
        session = self._session_for(user_id, project_id, session_id)
        try:
            requested_cursor = max(0, int(cursor or 0))
        except (TypeError, ValueError):
            requested_cursor = 0
        with session.lock:
            end_cursor = session.buffer_offset + len(session.buffer)
            reset = requested_cursor < session.buffer_offset
            start_cursor = session.buffer_offset if reset else min(requested_cursor, end_cursor)
            text = session.buffer[start_cursor - session.buffer_offset:]
            return {
                "sessionId": session.id,
                "connected": session.connected and not session.stop_requested.is_set(),
                "port": session.port,
                "baudRate": session.baud_rate,
                "text": text,
                "cursor": end_cursor,
                "reset": reset,
                "receivedBytes": session.received_bytes,
                "sentBytes": session.sent_bytes,
                "droppedCharacters": session.dropped_characters,
                "message": session.error or ("Pripojené." if session.connected else "Sériové spojenie je ukončené."),
            }

    def send(self, user_id: str, project_id: str, session_id: str, data: dict[str, Any]) -> dict[str, Any]:
        session = self._session_for(user_id, project_id, session_id)
        text = str(data.get("text") or "").replace("\x00", "")
        encoded = text.encode("utf-8")
        if not encoded:
            return self.poll(user_id, project_id, session_id, data.get("cursor", 0))
        if len(encoded) > MAX_SERIAL_WRITE_BYTES:
            raise SerialMonitorError("Do sériového portu možno naraz odoslať najviac 8 KB dát.")
        with session.lock:
            if not session.connected or session.stop_requested.is_set():
                raise SerialMonitorError("Sériový monitor už nie je pripojený.")
            written = session.device.write(encoded)
            session.sent_bytes += written
        return self.poll(user_id, project_id, session_id, data.get("cursor", 0))

    def stop(self, user_id: str, project_id: str, session_id: str) -> dict[str, Any]:
        session = self._session_for(user_id, project_id, session_id)
        with self._lock:
            self._sessions.pop(session.id, None)
            if self._projects.get((user_id, project_id)) == session.id:
                self._projects.pop((user_id, project_id), None)
        self._stop_session(session)
        return {"stopped": True}

    def close(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
            self._projects.clear()
        for session in sessions:
            self._stop_session(session)

    def _open(self, port: str, baud_rate: int) -> SerialDevice:
        if not self.status()["available"]:
            raise SerialMonitorError(str(self.status()["message"]))
        try:
            return self._opener(port, baud_rate)
        except SerialMonitorError:
            raise
        except OSError as error:
            raise SerialMonitorError("Sériový port sa nepodarilo otvoriť.") from error

    def _session_for(self, user_id: str, project_id: str, session_id: str) -> _SerialSession:
        with self._lock:
            session = self._sessions.get(str(session_id))
        if not session or session.user_id != user_id or session.project_id != project_id:
            raise SerialMonitorError("Sériový monitor už neexistuje alebo nepatrí tomuto projektu.")
        return session

    @staticmethod
    def _serial_port(value: Any) -> str:
        port = str(value or "")
        path = Path(port)
        if not port.startswith("/dev/") or not path.is_char_device():
            raise SerialMonitorError("Vyber dostupný sériový port v nastavení firmvéru.")
        return port

    @staticmethod
    def _baud_rate(value: Any) -> int:
        try:
            baud_rate = int(value)
        except (TypeError, ValueError) as error:
            raise SerialMonitorError("Prenosová rýchlosť sériového monitora nie je platná.") from error
        if baud_rate not in SERIAL_BAUD_RATES:
            raise SerialMonitorError("Vybraná prenosová rýchlosť nie je podporovaná.")
        return baud_rate

    def _read_loop(self, session: _SerialSession) -> None:
        try:
            while not session.stop_requested.is_set():
                chunk = session.device.read(2048)
                if not chunk:
                    continue
                text = chunk.decode("utf-8", errors="replace")
                with session.lock:
                    session.received_bytes += len(chunk)
                    session.buffer += text
                    overflow = len(session.buffer) - MAX_SERIAL_BUFFER_CHARACTERS
                    if overflow > 0:
                        session.buffer = session.buffer[overflow:]
                        session.buffer_offset += overflow
                        session.dropped_characters += overflow
        except Exception as error:
            with session.lock:
                if not session.stop_requested.is_set():
                    session.error = str(error) or "Spojenie so sériovým portom sa prerušilo."
        finally:
            with session.lock:
                session.connected = False
            try:
                session.device.close()
            except Exception:
                pass

    @staticmethod
    def _stop_session(session: _SerialSession) -> None:
        session.stop_requested.set()
        try:
            session.device.close()
        except Exception:
            pass
        if session.thread and session.thread is not threading.current_thread():
            session.thread.join(timeout=1.0)
        with session.lock:
            session.connected = False
