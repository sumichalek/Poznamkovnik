from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from backend.firmware_builder import FirmwareBuildRunner, FIRMWARE_MEMORY_LIMIT_BYTES, MAX_FIRMWARE_ARTIFACT_BYTES


class SimulatedAvrBuilder(FirmwareBuildRunner):
    def __init__(self, artifact_root: Path) -> None:
        tools = {"avr-gcc", "avr-g++", "avr-objcopy", "avr-size"}
        super().__init__(artifact_root, which=lambda name: f"/tools/{name}" if name in tools else None)
        self.commands: list[list[str]] = []
        self.execution_limits: list[dict[str, Any]] = []

    def status(self) -> dict[str, Any]:
        return {
            "targets": {
                "avr-atmega328p": {
                    "languages": {
                        "c": {"available": True, "message": "Pripravené."},
                        "cpp": {"available": True, "message": "Pripravené."},
                        "asm": {"available": True, "message": "Pripravené."},
                    }
                }
            }
        }

    def _execute(self, command: list[str], workspace: Path, **_kwargs: Any) -> dict[str, Any]:
        self.commands.append(command)
        self.execution_limits.append(_kwargs)
        if "--format=SysV" in command:
            return self._result(
                "section                    size      addr\n.text                        120         0\n.data                         12   8388864\n.bss                          24   8388876\n"
            )
        if "-o" in command:
            output = command[command.index("-o") + 1]
            self._work_path(workspace, output).write_bytes(b"object")
        elif command and command[0].endswith("objcopy"):
            self._work_path(workspace, command[-1]).write_bytes(b"artifact")
        return self._result()

    @staticmethod
    def _work_path(workspace: Path, value: str) -> Path:
        return workspace / value.removeprefix("/work/")

    @staticmethod
    def _result(stdout: str = "") -> dict[str, Any]:
        return {"stdout": stdout, "stderr": "", "exitCode": 0, "timedOut": False, "outputLimited": False, "durationMs": 1}


class FirmwareBuildRunnerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="poznamkovnik-firmware-builder-", dir="/tmp"))

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_avr_build_creates_artifacts_and_memory_summary(self) -> None:
        builder = SimulatedAvrBuilder(self.root / "artifacts")
        result = builder.build(
            "user-1",
            "project-1",
            {
                "firmwareTargetId": "avr-atmega328p",
                "language": "c",
                "filename": "src/main.c",
                "source": "int main(void) { for (;;) {} }\n",
                "files": [
                    {"title": "src/main.c", "content": "int main(void) { for (;;) {} }\n"},
                    {"title": "src/device.h", "content": "#define LED 5\n"},
                ],
            },
        )

        self.assertTrue(result["compiled"])
        self.assertEqual([artifact["name"] for artifact in result["artifacts"]], ["firmware.elf", "firmware.hex"])
        self.assertEqual(result["memory"]["flash"]["used"], 132)
        self.assertEqual(result["memory"]["ram"]["used"], 36)
        self.assertIn("-mmcu=atmega328p", builder.commands[0])
        self.assertTrue(any(command[0].endswith("objcopy") for command in builder.commands))
        for limits in builder.execution_limits:
            self.assertEqual(limits["memory_limit"], FIRMWARE_MEMORY_LIMIT_BYTES)
            self.assertEqual(limits["file_limit"], MAX_FIRMWARE_ARTIFACT_BYTES)
        stored = list((self.root / "artifacts").glob("*/firmware.hex"))
        self.assertEqual(len(stored), 1)

        memory_map = builder.memory_map(
            "user-1",
            "project-1",
            {
                "firmwareTargetId": "avr-atmega328p",
                "language": "c",
                "files": [
                    {"title": "src/main.c", "content": "int main(void) { for (;;) {} }\n"},
                    {"title": "src/device.h", "content": "#define LED 5\n"},
                ],
            },
        )
        self.assertTrue(memory_map["fresh"])
        self.assertEqual(memory_map["memory"]["flash"]["used"], 132)
        self.assertEqual(memory_map["memory"]["sections"][0]["name"], ".text")
        self.assertEqual(memory_map["artifacts"][1]["name"], "firmware.hex")

        stale_map = builder.memory_map(
            "user-1",
            "project-1",
            {
                "firmwareTargetId": "avr-atmega328p",
                "language": "c",
                "files": [
                    {"title": "src/main.c", "content": "int main(void) { return 1; }\n"},
                    {"title": "src/device.h", "content": "#define LED 5\n"},
                ],
            },
        )
        self.assertFalse(stale_map["fresh"])

    def test_memory_report_counts_data_in_flash_and_ram(self) -> None:
        memory = FirmwareBuildRunner._memory_report(
            {"flashBytes": 1024, "ramBytes": 256},
            ".text 100 0\n.rodata 20 0\n.data 10 0\n.bss 30 0\n",
        )

        self.assertEqual(memory["flash"]["used"], 130)
        self.assertEqual(memory["ram"]["used"], 40)
