from __future__ import annotations

import time
import unittest
from collections import deque

from backend.code_runner import CodeRunnerError
from backend.serial_monitor import SerialMonitor


class FakeSerialDevice:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = deque(chunks)
        self.written = b""
        self.closed = False

    def read(self, _maximum: int) -> bytes:
        if self._chunks:
            return self._chunks.popleft()
        time.sleep(0.005)
        return b""

    def write(self, data: bytes) -> int:
        if self.closed:
            raise OSError("closed")
        self.written += data
        return len(data)

    def close(self) -> None:
        self.closed = True


class SerialMonitorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.device = FakeSerialDevice([b"Ahoj", b" zo zariadenia\n"])
        self.monitor = SerialMonitor(opener=lambda _port, _baud: self.device)
        if not self.monitor.status()["available"]:
            self.skipTest("Sériový monitor nie je v tomto prostredí dostupný.")
        self.entry = {
            "projectKind": "firmware",
            "firmwareSerialPort": "/dev/null",
            "firmwareSerialBaud": 115200,
        }

    def tearDown(self) -> None:
        self.monitor.close()

    def test_monitor_reads_writes_and_stops_only_its_explicit_session(self) -> None:
        started = self.monitor.start("user-1", "project-1", self.entry, {"baudRate": 57600})
        session_id = started["sessionId"]
        snapshot = started
        for _ in range(50):
            snapshot = self.monitor.poll("user-1", "project-1", session_id, 0)
            if "Ahoj zo zariadenia" in snapshot["text"]:
                break
            time.sleep(0.01)

        self.assertTrue(snapshot["connected"])
        self.assertEqual(snapshot["baudRate"], 57600)
        self.assertIn("Ahoj zo zariadenia", snapshot["text"])
        self.monitor.send("user-1", "project-1", session_id, {"text": "ping\n", "cursor": snapshot["cursor"]})
        self.assertEqual(self.device.written, b"ping\n")

        with self.assertRaises(CodeRunnerError):
            self.monitor.poll("user-2", "project-1", session_id, 0)

        self.assertEqual(self.monitor.stop("user-1", "project-1", session_id), {"stopped": True})
        self.assertTrue(self.device.closed)

    def test_monitor_rejects_unsupported_baud_before_opening_the_port(self) -> None:
        with self.assertRaisesRegex(CodeRunnerError, "rýchlosť"):
            self.monitor.start("user-1", "project-1", self.entry, {"baudRate": 12345})
        self.assertFalse(self.device.closed)
