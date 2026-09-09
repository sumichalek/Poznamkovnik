"""Explicit, confirmed programming of generated firmware artifacts only."""

from __future__ import annotations

import hashlib
import resource
import secrets
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .code_runner import CCodeRunner, CodeRunnerError, MAX_OUTPUT_BYTES, MAX_PROCESS_COUNT
from .firmware import FIRMWARE_PROGRAMMERS
from .firmware_builder import FIRMWARE_BUILD_TARGETS, FirmwareBuildRunner


PROGRAM_CONFIRMATION = "ZAPISAT"
PROGRAM_CHALLENGE_SECONDS = 120.0
PROGRAM_TIMEOUT_SECONDS = 45.0


class FirmwareProgrammer:
    """Runs a tiny allow-listed programming command only after confirmation."""

    def __init__(self, builder: FirmwareBuildRunner, *, which: Callable[[str], str | None] = shutil.which) -> None:
        self._builder = builder
        self._which = which
        self._lock = threading.RLock()
        self._pending: dict[str, dict[str, Any]] = {}

    def prepare(self, user_id: str, project_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        ready = self._readiness(user_id, project_id, entry)
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._discard_expired()
            self._pending[token] = {
                "userId": user_id,
                "projectId": project_id,
                "targetId": ready["targetId"],
                "programmerId": ready["programmerId"],
                "artifactName": ready["artifact"]["name"],
                "artifactHash": ready["artifactHash"],
                "sourceFingerprint": ready["sourceFingerprint"],
                "expiresAt": time.monotonic() + PROGRAM_CHALLENGE_SECONDS,
            }
        return {
            "challenge": token,
            "expiresInSeconds": int(PROGRAM_CHALLENGE_SECONDS),
            "target": ready["target"],
            "programmer": ready["programmer"],
            "port": ready["port"],
            "artifact": ready["artifact"],
            "confirmation": PROGRAM_CONFIRMATION,
        }

    def program(self, user_id: str, project_id: str, entry: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        token = str(data.get("challenge") or "")
        confirmation = str(data.get("confirmation") or "").strip().upper()
        if confirmation != PROGRAM_CONFIRMATION:
            raise CodeRunnerError(f"Na zápis firmvéru napíš presne {PROGRAM_CONFIRMATION}.")
        with self._lock:
            self._discard_expired()
            challenge = self._pending.pop(token, None)
        if not challenge or challenge["userId"] != user_id or challenge["projectId"] != project_id:
            raise CodeRunnerError("Potvrdenie zápisu vypršalo. Priprav ho ešte raz.")

        ready = self._readiness(user_id, project_id, entry)
        expected = ("targetId", "programmerId", "sourceFingerprint", "artifactHash")
        if any(challenge[key] != ready[key] for key in expected) or challenge["artifactName"] != ready["artifact"]["name"]:
            raise CodeRunnerError("Projekt alebo artefakt sa od potvrdenia zmenil. Priprav zápis ešte raz.")
        result = self._execute(ready["command"])
        output = "\n".join(part for part in (result["stdout"], result["stderr"]) if part).strip()
        return {
            "programmed": result["exitCode"] == 0 and not result["timedOut"] and not result["outputLimited"],
            "result": result,
            "summary": output or ("Zápis firmvéru prebehol úspešne." if result["exitCode"] == 0 else "Zápis firmvéru zlyhal."),
        }

    def _readiness(self, user_id: str, project_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        target_id = str(entry.get("firmwareTargetId") or "")
        programmer_id = str(entry.get("firmwareProgrammerId") or "")
        profiles = FIRMWARE_PROGRAMMERS.get(target_id, ())
        profile = next((item for item in profiles if item.get("id") == programmer_id), None)
        if not profile:
            raise CodeRunnerError("Vyber programátor v nastavení firmvéru.")
        if not profile.get("writeSupported"):
            raise CodeRunnerError("Zápis cez vybraný programátor ešte nie je pripojený.")
        port = str(entry.get("firmwareSerialPort") or "")
        if profile.get("requiresPort"):
            self._validate_serial_port(port)
        else:
            port = ""

        latest = self._builder.latest_build(user_id, project_id)
        source_fingerprint = self._builder.project_fingerprint(entry)
        if latest["targetId"] != target_id or latest["sourceFingerprint"] != source_fingerprint:
            raise CodeRunnerError("Súbory sa zmenili od posledného zostavenia. Najprv znovu zostav firmvér.")
        artifact_name = self._artifact_name(target_id, programmer_id)
        artifact = next((item for item in latest["artifacts"] if item["name"] == artifact_name), None)
        if not artifact:
            raise CodeRunnerError("Posledné zostavenie nevytvorilo potrebný artefakt firmvéru.")
        artifact_path = self._builder.artifact_path(user_id, project_id, artifact_name)
        command = self._command(target_id, programmer_id, port, artifact_path)
        return {
            "targetId": target_id,
            "target": str(FIRMWARE_BUILD_TARGETS.get(target_id, {}).get("label") or target_id),
            "programmerId": programmer_id,
            "programmer": str(profile["label"]),
            "port": port,
            "artifact": artifact,
            "artifactHash": self._file_hash(artifact_path),
            "sourceFingerprint": source_fingerprint,
            "command": command,
        }

    def _command(self, target_id: str, programmer_id: str, port: str, artifact: Path) -> list[str]:
        if target_id == "avr-atmega328p" and programmer_id == "avr-arduino":
            return [
                self._tool("avrdude"),
                "-p",
                "atmega328p",
                "-c",
                "arduino",
                "-P",
                port,
                "-b",
                "115200",
                "-U",
                f"flash:w:{artifact}:i",
            ]
        if target_id == "avr-atmega328p" and programmer_id == "avr-usbasp":
            return [self._tool("avrdude"), "-p", "atmega328p", "-c", "usbasp", "-U", f"flash:w:{artifact}:i"]
        if target_id == "stm32f103" and programmer_id == "stm32-uart":
            return [self._tool("stm32flash"), "-w", str(artifact), "-v", "-g", "0x0", "-b", "115200", port]
        raise CodeRunnerError("Zápis pre vybraný cieľ a programátor ešte nie je pripravený.")

    @staticmethod
    def _artifact_name(target_id: str, programmer_id: str) -> str:
        if target_id == "avr-atmega328p" and programmer_id in {"avr-arduino", "avr-usbasp"}:
            return "firmware.hex"
        if target_id == "stm32f103" and programmer_id == "stm32-uart":
            return "firmware.bin"
        raise CodeRunnerError("Zápis pre vybraný cieľ a programátor ešte nie je pripravený.")

    def _tool(self, name: str) -> str:
        path = self._which(name)
        if not path:
            raise CodeRunnerError(f"Chýba nástroj na zápis: {name}.")
        return path

    @staticmethod
    def _validate_serial_port(port: str) -> None:
        path = Path(port)
        if not port.startswith("/dev/") or not path.is_char_device():
            raise CodeRunnerError("Vybraný sériový port nie je momentálne dostupné zariadenie.")

    def _execute(self, command: list[str]) -> dict[str, Any]:
        started = time.monotonic()
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                preexec_fn=self._limit_process,
            )
        except OSError as error:
            raise CodeRunnerError("Nástroj na zápis sa nepodarilo spustiť.") from error
        stdout, stderr, timed_out, output_limited = CCodeRunner._collect_output(process, PROGRAM_TIMEOUT_SECONDS)
        return {
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "exitCode": process.returncode if process.returncode is not None else -1,
            "timedOut": timed_out,
            "outputLimited": output_limited,
            "durationMs": round((time.monotonic() - started) * 1000),
        }

    def _discard_expired(self) -> None:
        now = time.monotonic()
        expired = [token for token, value in self._pending.items() if value["expiresAt"] <= now]
        for token in expired:
            self._pending.pop(token, None)

    @staticmethod
    def _file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(64 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _limit_process() -> None:
        cpu_limit = int(PROGRAM_TIMEOUT_SECONDS) + 2
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
        resource.setrlimit(resource.RLIMIT_NPROC, (MAX_PROCESS_COUNT, MAX_PROCESS_COUNT))
