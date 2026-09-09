from __future__ import annotations

import unittest

from backend.debugger import DevelopmentDebugger


class DevelopmentDebuggerTestCase(unittest.TestCase):
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

