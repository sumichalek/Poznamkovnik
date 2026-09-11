from __future__ import annotations

import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.code_runner import COMPILED_LANGUAGE_MEMORY_LIMIT_BYTES
from backend.debugger import DebuggerError, DevelopmentDebugger


class DevelopmentDebuggerTestCase(unittest.TestCase):
    def test_debugger_launch_keeps_limits_without_a_python_child_callback(self) -> None:
        debugger = DevelopmentDebugger()
        debugger.bwrap_path = "/usr/bin/bwrap"
        debugger.unshare_path = "/usr/bin/unshare"
        debugger.prlimit_path = "/usr/bin/prlimit"
        with tempfile.TemporaryDirectory() as temporary, patch("backend.debugger.subprocess.Popen") as launch:
            launch.return_value.stdin = io.BytesIO()
            launch.return_value.stdout = io.BytesIO()
            session = debugger._launch_session("user-1", "project-1", Path(temporary), [])
            self.assertIsNone(session.output.get(timeout=2))
            session.process.stdin.close()
        self.assertNotIn("preexec_fn", launch.call_args.kwargs)
        self.assertTrue(launch.call_args.kwargs["start_new_session"])
        self.assertEqual(launch.call_args.args[0][0], "/usr/bin/prlimit")
        self.assertIn(f"--as={COMPILED_LANGUAGE_MEMORY_LIMIT_BYTES}", launch.call_args.args[0])

    def test_debugger_reports_child_startup_error(self) -> None:
        debugger = DevelopmentDebugger()
        debugger.bwrap_path = "/usr/bin/bwrap"
        debugger.unshare_path = "/usr/bin/unshare"
        debugger.prlimit_path = "/usr/bin/prlimit"
        with tempfile.TemporaryDirectory() as temporary, patch(
            "backend.debugger.subprocess.Popen", side_effect=subprocess.SubprocessError("child failed")
        ), self.assertRaises(DebuggerError):
            debugger._launch_session("user-1", "project-1", Path(temporary), [])

    def test_mi_stop_location_frames_and_variables_are_read(self) -> None:
        stop = DevelopmentDebugger._mi_attributes(
            '*stopped,reason="breakpoint-hit",frame={addr="0x0000",func="main",file="main.c",fullname="/work/src/main.c",line="12"}'
        )
        self.assertEqual(
            DevelopmentDebugger._location(stop),
            {"filename": "src/main.c", "line": 12, "function": "main"},
        )
        frames = DevelopmentDebugger._frames([
            '3^done,stack=[frame={level="0",addr="0x1",func="main",file="main.c",fullname="/work/main.c",line="12"},'
            'frame={level="1",addr="0x2",func="start",file="start.c",line="3"}]'
        ])
        self.assertEqual(frames[0]["function"], "main")
        self.assertEqual(frames[0]["location"]["line"], 12)
        self.assertEqual(frames[1]["location"]["filename"], "start.c")
        variables = DevelopmentDebugger._variables([
            '4^done,variables=[{name="value",value="7"},{name="word",value="\\\"ahoj\\\""}]'
        ])
        self.assertEqual(variables, [{"name": "value", "value": "7"}, {"name": "word", "value": '"ahoj"'}])
