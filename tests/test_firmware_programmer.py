from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from backend.code_runner import CodeRunnerError
from backend.firmware_programmer import PROGRAM_CONFIRMATION, FirmwareProgrammer


class ArtifactBuilder:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.fingerprint = "fresh-source"
        self.artifact = root / "firmware.hex"
        self.artifact.write_text(":00000001FF\n", encoding="ascii")

    def latest_build(self, _user_id: str, _project_id: str) -> dict[str, Any]:
        return {
            "targetId": "avr-atmega328p",
            "sourceFingerprint": "fresh-source",
            "artifacts": [{"name": "firmware.hex", "bytes": self.artifact.stat().st_size}],
        }

    def project_fingerprint(self, _entry: dict[str, Any]) -> str:
        return self.fingerprint

    def artifact_path(self, _user_id: str, _project_id: str, name: str) -> Path:
        if name != "firmware.hex":
            raise AssertionError("Unexpected artifact")
        return self.artifact


class SimulatedFirmwareProgrammer(FirmwareProgrammer):
    def __init__(self, builder: ArtifactBuilder) -> None:
        super().__init__(builder, which=lambda name: f"/tools/{name}" if name == "avrdude" else None)  # type: ignore[arg-type]
        self.commands: list[list[str]] = []

    def _execute(self, command: list[str]) -> dict[str, Any]:
        self.commands.append(command)
        return {
            "stdout": "avrdude: verified\n",
            "stderr": "",
            "exitCode": 0,
            "timedOut": False,
            "outputLimited": False,
            "durationMs": 7,
        }


class FirmwareProgrammerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="poznamkovnik-firmware-programmer-", dir="/tmp"))
        self.builder = ArtifactBuilder(self.root)
        self.programmer = SimulatedFirmwareProgrammer(self.builder)
        self.entry = {
            "firmwareTargetId": "avr-atmega328p",
            "firmwareProgrammerId": "avr-arduino",
            "firmwareSerialPort": "/dev/null",
            "language": "c",
            "files": [{"title": "main.c", "content": "int main(void) { return 0; }\n"}],
        }

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_confirmed_avr_programming_uses_only_the_generated_hex_artifact(self) -> None:
        prepared = self.programmer.prepare("user-1", "project-1", self.entry)

        result = self.programmer.program(
            "user-1",
            "project-1",
            self.entry,
            {"challenge": prepared["challenge"], "confirmation": PROGRAM_CONFIRMATION},
        )

        self.assertTrue(result["programmed"])
        self.assertEqual(prepared["target"], "ATmega328P")
        self.assertEqual(prepared["artifact"]["name"], "firmware.hex")
        self.assertEqual(self.programmer.commands[0][:7], ["/tools/avrdude", "-p", "atmega328p", "-c", "arduino", "-P", "/dev/null"])
        self.assertIn(f"flash:w:{self.builder.artifact}:i", self.programmer.commands[0])

    def test_changed_source_rejects_a_prepared_programming_challenge(self) -> None:
        prepared = self.programmer.prepare("user-1", "project-1", self.entry)
        self.builder.fingerprint = "changed-source"

        with self.assertRaisesRegex(CodeRunnerError, "zmenil"):
            self.programmer.program(
                "user-1",
                "project-1",
                self.entry,
                {"challenge": prepared["challenge"], "confirmation": PROGRAM_CONFIRMATION},
            )
        self.assertEqual(self.programmer.commands, [])

    def test_changed_artifact_rejects_a_prepared_programming_challenge(self) -> None:
        prepared = self.programmer.prepare("user-1", "project-1", self.entry)
        self.builder.artifact.write_text(":00000001FE\n", encoding="ascii")

        with self.assertRaisesRegex(CodeRunnerError, "artefakt sa od potvrdenia zmenil"):
            self.programmer.program(
                "user-1",
                "project-1",
                self.entry,
                {"challenge": prepared["challenge"], "confirmation": PROGRAM_CONFIRMATION},
            )
        self.assertEqual(self.programmer.commands, [])

    def test_confirmation_phrase_is_required_before_any_programmer_starts(self) -> None:
        prepared = self.programmer.prepare("user-1", "project-1", self.entry)

        with self.assertRaisesRegex(CodeRunnerError, PROGRAM_CONFIRMATION):
            self.programmer.program(
                "user-1",
                "project-1",
                self.entry,
                {"challenge": prepared["challenge"], "confirmation": "yes"},
            )
        self.assertEqual(self.programmer.commands, [])

    def test_stm32_command_is_limited_to_its_binary_artifact_and_uart_profile(self) -> None:
        programmer = FirmwareProgrammer(
            self.builder,  # type: ignore[arg-type]
            which=lambda name: f"/tools/{name}" if name == "stm32flash" else None,
        )
        artifact = self.root / "firmware.bin"
        command = programmer._command("stm32f103", "stm32-uart", "/dev/null", artifact)

        self.assertEqual(
            command,
            ["/tools/stm32flash", "-w", str(artifact), "-v", "-g", "0x0", "-b", "115200", "/dev/null"],
        )
        self.assertEqual(programmer._artifact_name("stm32f103", "stm32-uart"), "firmware.bin")
