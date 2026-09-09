"""Isolated cross-compilation for the first supported firmware targets.

The builder only creates artifacts. Programming a board remains a separate,
explicit operation, so compilation never opens serial ports or USB devices.
"""

from __future__ import annotations

import hashlib
import json
import resource
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .code_runner import CodeRunnerError, DevelopmentCodeRunner, MAX_PROCESS_COUNT


FIRMWARE_BUILD_TIMEOUT_SECONDS = 12.0
FIRMWARE_MEMORY_LIMIT_BYTES = 1024 * 1024 * 1024
MAX_FIRMWARE_ARTIFACT_BYTES = 4 * 1024 * 1024


FIRMWARE_BUILD_TARGETS: dict[str, dict[str, Any]] = {
    "avr-atmega328p": {
        "label": "ATmega328P",
        "kind": "avr",
        "languages": ("c", "cpp", "asm"),
        "tools": {
            "c": ("avr-gcc", "avr-objcopy", "avr-size"),
            "cpp": ("avr-g++", "avr-objcopy", "avr-size"),
            "asm": ("avr-gcc", "avr-objcopy", "avr-size"),
        },
        "flashBytes": 32 * 1024,
        "ramBytes": 2 * 1024,
    },
    "stm32f103": {
        "label": "STM32F103C8",
        "kind": "stm32",
        "languages": ("c", "cpp", "asm"),
        "tools": {
            "c": ("arm-none-eabi-gcc", "arm-none-eabi-objcopy", "arm-none-eabi-size"),
            "cpp": ("arm-none-eabi-g++", "arm-none-eabi-objcopy", "arm-none-eabi-size"),
            "asm": ("arm-none-eabi-gcc", "arm-none-eabi-objcopy", "arm-none-eabi-size"),
        },
        "flashBytes": 64 * 1024,
        "ramBytes": 20 * 1024,
    },
}


STM32F103_LINKER_SCRIPT = """ENTRY(Reset_Handler)

MEMORY
{
  FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 64K
  RAM (xrw)   : ORIGIN = 0x20000000, LENGTH = 20K
}

_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
  .isr_vector : { KEEP(*(.isr_vector)) } > FLASH
  .text : { *(.text*) *(.rodata*) _etext = .; } > FLASH
  .data : AT(_etext) { _sdata = .; *(.data*) _edata = .; } > RAM
  _sidata = LOADADDR(.data);
  .bss : { _sbss = .; *(.bss*) *(COMMON) _ebss = .; } > RAM
}
"""


STM32F103_STARTUP = """#include <stdint.h>

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;
int main(void);

void Default_Handler(void);
void Reset_Handler(void);

__attribute__((section(".isr_vector")))
void (*const vector_table[])(void) = {
  (void (*)(void)) &_estack,
  Reset_Handler,
  Default_Handler,
  Default_Handler,
  Default_Handler,
  Default_Handler,
  Default_Handler,
  0, 0, 0, 0,
  Default_Handler,
  Default_Handler,
  0,
  Default_Handler,
  Default_Handler,
};

void Reset_Handler(void) {
  for (uint32_t *source = &_sidata, *target = &_sdata; target < &_edata;) *target++ = *source++;
  for (uint32_t *target = &_sbss; target < &_ebss;) *target++ = 0;
  (void) main();
  for (;;) {}
}

void Default_Handler(void) {
  for (;;) {}
}
"""


class FirmwareBuildRunner(DevelopmentCodeRunner):
    """Builds firmware without running its output or accessing a device."""

    def __init__(self, artifact_root: Path, *, which: Callable[[str], str | None] = shutil.which) -> None:
        super().__init__()
        self._artifact_root = artifact_root
        self._which = which
        self._artifact_lock = threading.RLock()

    def status(self) -> dict[str, Any]:
        sandbox = super().status()
        targets: dict[str, dict[str, Any]] = {}
        for target_id, target in FIRMWARE_BUILD_TARGETS.items():
            languages: dict[str, dict[str, Any]] = {}
            for language in target["languages"]:
                missing = [tool for tool in target["tools"][language] if not self._which(tool)]
                available = bool(sandbox["available"] and not missing)
                if missing:
                    message = f"Chýba toolchain: {', '.join(missing)}."
                elif not sandbox["available"]:
                    message = str(sandbox["message"])
                else:
                    message = "Bezpečné zostavenie je pripravené."
                languages[language] = {"available": available, "message": message}
            targets[target_id] = {
                "available": any(entry["available"] for entry in languages.values()),
                "languages": languages,
            }
        return {"targets": targets}

    def build(self, user_id: str, project_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        target_id = str(entry.get("firmwareTargetId") or "")
        target = FIRMWARE_BUILD_TARGETS.get(target_id)
        language = str(entry.get("language") or "")
        if not target:
            raise CodeRunnerError("Pre tento cieľ firmvéru ešte nie je pripravený reálny build.")
        if language not in target["languages"]:
            raise CodeRunnerError("Zvolený jazyk zatiaľ tento firmvérový build nepodporuje.")
        status = self.status()["targets"][target_id]["languages"][language]
        if not status["available"]:
            raise CodeRunnerError(str(status["message"]))

        source = self._limited_text(entry.get("source"), 200 * 1024, "Zdrojový kód je príliš veľký.")
        if not source.strip():
            raise CodeRunnerError("Zdrojový kód nemôže byť prázdny.")
        entry_filename = self._safe_project_path(entry.get("filename"))
        project_files = self._project_files(entry.get("files"), entry_filename, source)
        source_files = [(name, content) for name, content in project_files if self._source_kind(name)]
        if not source_files:
            raise CodeRunnerError("Projekt firmvéru nemá zdrojový súbor podporovaného typu.")

        with tempfile.TemporaryDirectory(prefix=f"poznamkovnik-firmware-{target['kind']}-") as temporary:
            workspace = Path(temporary)
            self._write_project_files(workspace, project_files)
            (workspace / ".build").mkdir()
            if target["kind"] == "stm32":
                (workspace / "firmware.ld").write_text(STM32F103_LINKER_SCRIPT, encoding="utf-8")
                (workspace / "firmware_startup.c").write_text(STM32F103_STARTUP, encoding="utf-8")
                source_files.append(("firmware_startup.c", STM32F103_STARTUP))

            compile_results, objects = self._compile_sources(target, language, project_files, source_files, workspace)
            failed = next((result for result in compile_results if self._failed(result)), None)
            if failed:
                return {"compiled": False, "compile": self._merge_compile_results(compile_results), "artifacts": [], "memory": None}

            link_result = self._link(target, language, objects, workspace)
            compile_results.append(link_result)
            if self._failed(link_result):
                return {"compiled": False, "compile": self._merge_compile_results(compile_results), "artifacts": [], "memory": None}

            artifact_names = self._create_output_artifacts(target, workspace, compile_results)
            if not artifact_names:
                return {"compiled": False, "compile": self._merge_compile_results(compile_results), "artifacts": [], "memory": None}

            size_result = self._measure(target, workspace)
            compile_results.append(size_result)
            memory = self._memory_report(target, str(size_result.get("stdout") or "")) if not self._failed(size_result) else None
            artifacts = self._store_artifacts(
                user_id,
                project_id,
                workspace,
                artifact_names,
                target_id=target_id,
                source_fingerprint=self.project_fingerprint(entry),
                memory=memory,
            )
            compile = self._merge_compile_results(compile_results)
            compile["stdout"] = "\n".join(
                part for part in [str(compile.get("stdout") or "").strip(), "Firmvér bol zostavený."] if part
            )
            return {
                "compiled": True,
                "compile": compile,
                "artifacts": artifacts,
                "memory": memory,
                "target": {"id": target_id, "label": target["label"]},
            }

    def _compile_sources(
        self,
        target: dict[str, Any],
        project_language: str,
        project_files: list[tuple[str, str]],
        source_files: list[tuple[str, str]],
        workspace: Path,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        results: list[dict[str, Any]] = []
        objects: list[str] = []
        include_paths = self._project_include_paths(project_files)
        for index, (filename, _) in enumerate(source_files):
            source_language = self._source_kind(filename) or project_language
            compiler = self._compiler(target, source_language)
            object_path = f"/work/.build/{index}.o"
            result = self._execute(
                [
                    compiler,
                    *self._compile_flags(target, source_language),
                    "-I/work",
                    *include_paths,
                    "-c",
                    f"/work/{filename}",
                    "-o",
                    object_path,
                ],
                workspace,
                timeout=FIRMWARE_BUILD_TIMEOUT_SECONDS,
                memory_limit=FIRMWARE_MEMORY_LIMIT_BYTES,
            )
            results.append(result)
            if self._failed(result):
                break
            objects.append(object_path)
        return results, objects

    def _link(self, target: dict[str, Any], language: str, objects: list[str], workspace: Path) -> dict[str, Any]:
        linker = self._compiler(target, "cpp" if language == "cpp" else "c")
        if target["kind"] == "avr":
            command = [linker, "-mmcu=atmega328p", "-Wl,--gc-sections", *objects, "-o", "/work/firmware.elf"]
        else:
            command = [
                linker,
                "-mcpu=cortex-m3",
                "-mthumb",
                "-nostdlib",
                "-nostartfiles",
                "-Wl,--gc-sections,-T,/work/firmware.ld",
                *objects,
                "-o",
                "/work/firmware.elf",
            ]
        return self._execute(command, workspace, timeout=FIRMWARE_BUILD_TIMEOUT_SECONDS, memory_limit=FIRMWARE_MEMORY_LIMIT_BYTES)

    def _create_output_artifacts(
        self, target: dict[str, Any], workspace: Path, results: list[dict[str, Any]]
    ) -> list[str]:
        objcopy = self._tool(target, "objcopy")
        commands = [[objcopy, "-O", "ihex", "/work/firmware.elf", "/work/firmware.hex"]]
        if target["kind"] == "avr":
            commands[0][3:3] = ["-R", ".eeprom"]
        else:
            commands.append([objcopy, "-O", "binary", "/work/firmware.elf", "/work/firmware.bin"])
        for command in commands:
            result = self._execute(command, workspace, timeout=FIRMWARE_BUILD_TIMEOUT_SECONDS, memory_limit=FIRMWARE_MEMORY_LIMIT_BYTES)
            results.append(result)
            if self._failed(result):
                return []
        names = ["firmware.elf", "firmware.hex"]
        if target["kind"] == "stm32":
            names.append("firmware.bin")
        if any(not (workspace / name).is_file() for name in names):
            results.append(self._failed_result("Nástroj nevytvoril očakávané artefakty firmvéru."))
            return []
        return names

    def _measure(self, target: dict[str, Any], workspace: Path) -> dict[str, Any]:
        return self._execute(
            [self._tool(target, "size"), "--format=SysV", "--radix=10", "/work/firmware.elf"],
            workspace,
            timeout=FIRMWARE_BUILD_TIMEOUT_SECONDS,
            memory_limit=FIRMWARE_MEMORY_LIMIT_BYTES,
        )

    def _store_artifacts(
        self,
        user_id: str,
        project_id: str,
        workspace: Path,
        names: list[str],
        *,
        target_id: str,
        source_fingerprint: str,
        memory: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        destination = self._artifact_directory(user_id, project_id)
        self._artifact_root.mkdir(parents=True, exist_ok=True)
        with self._artifact_lock:
            with tempfile.TemporaryDirectory(prefix=".firmware-build-", dir=self._artifact_root) as staging_name:
                staging = Path(staging_name)
                artifacts: list[dict[str, Any]] = []
                for name in names:
                    source = workspace / name
                    size = source.stat().st_size
                    if size > MAX_FIRMWARE_ARTIFACT_BYTES:
                        raise CodeRunnerError("Artefakt firmvéru prekročil bezpečný limit veľkosti.")
                    target = staging / name
                    shutil.copyfile(source, target)
                    artifacts.append({"name": name, "bytes": size})
                (staging / "manifest.json").write_text(
                    json.dumps(
                        {
                            "version": 1,
                            "targetId": target_id,
                            "sourceFingerprint": source_fingerprint,
                            "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            "artifacts": artifacts,
                            "memory": memory,
                        },
                        separators=(",", ":"),
                    ),
                    encoding="utf-8",
                )
                if destination.exists():
                    shutil.rmtree(destination)
                staging.replace(destination)
                return artifacts

    def latest_build(self, user_id: str, project_id: str) -> dict[str, Any]:
        """Return metadata for one generated artifact set, never user paths."""

        directory = self._artifact_directory(user_id, project_id)
        manifest_path = directory / "manifest.json"
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as error:
            raise CodeRunnerError("Najprv zostav aktuálny firmvér.") from error
        if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("artifacts"), list):
            raise CodeRunnerError("Uložený artefakt firmvéru nemá platný tvar.")
        artifacts: list[dict[str, Any]] = []
        for item in raw["artifacts"]:
            if not isinstance(item, dict):
                raise CodeRunnerError("Uložený artefakt firmvéru nemá platný tvar.")
            name = str(item.get("name") or "")
            if not name or Path(name).name != name or name not in {"firmware.elf", "firmware.hex", "firmware.bin"}:
                raise CodeRunnerError("Uložený artefakt firmvéru nemá platný tvar.")
            artifact_path = directory / name
            if not artifact_path.is_file() or artifact_path.resolve().parent != directory.resolve():
                raise CodeRunnerError("Uložený artefakt firmvéru chýba.")
            artifacts.append({"name": name, "bytes": artifact_path.stat().st_size})
        return {
            "targetId": str(raw.get("targetId") or ""),
            "sourceFingerprint": str(raw.get("sourceFingerprint") or ""),
            "createdAt": str(raw.get("createdAt") or ""),
            "artifacts": artifacts,
            "memory": self._stored_memory_report(raw.get("memory")),
        }

    def memory_map(self, user_id: str, project_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        """Return the saved build map without opening or reading a device."""

        target_id = str(entry.get("firmwareTargetId") or "")
        target = FIRMWARE_BUILD_TARGETS.get(target_id)
        if not target:
            raise CodeRunnerError("Pre tento cieľ firmvéru ešte nie je pripravená pamäťová mapa.")
        latest = self.latest_build(user_id, project_id)
        if latest["targetId"] != target_id:
            raise CodeRunnerError("Posledný artefakt patrí inému cieľu. Zostav aktuálny firmvér znova.")
        memory = latest.get("memory")
        if not memory:
            raise CodeRunnerError("Posledné zostavenie ešte nemá pamäťovú mapu. Zostav firmvér znova.")
        return {
            "target": {
                "id": target_id,
                "label": str(target["label"]),
                "flashBytes": int(target["flashBytes"]),
                "ramBytes": int(target["ramBytes"]),
            },
            "fresh": latest["sourceFingerprint"] == self.project_fingerprint(entry),
            "createdAt": latest["createdAt"],
            "memory": memory,
            "artifacts": latest["artifacts"],
        }

    def artifact_path(self, user_id: str, project_id: str, name: str) -> Path:
        latest = self.latest_build(user_id, project_id)
        if name not in {str(artifact["name"]) for artifact in latest["artifacts"]}:
            raise CodeRunnerError("Požadovaný artefakt firmvéru neexistuje.")
        return self._artifact_directory(user_id, project_id) / name

    @staticmethod
    def project_fingerprint(entry: dict[str, Any]) -> str:
        digest = hashlib.sha256()
        digest.update(str(entry.get("firmwareTargetId") or "").encode("utf-8"))
        digest.update(b"\x00")
        digest.update(str(entry.get("language") or "").encode("utf-8"))
        digest.update(b"\x00")
        files = entry.get("files") if isinstance(entry.get("files"), list) else []
        for item in sorted((item for item in files if isinstance(item, dict)), key=lambda item: str(item.get("title") or "").casefold()):
            title = str(item.get("title") or "")
            content = str(item.get("content") or "")
            digest.update(title.encode("utf-8"))
            digest.update(b"\x00")
            digest.update(content.encode("utf-8"))
            digest.update(b"\x00")
        return digest.hexdigest()

    def _artifact_directory(self, user_id: str, project_id: str) -> Path:
        identity = f"{user_id}\x00{project_id}".encode("utf-8", errors="ignore")
        return self._artifact_root / hashlib.sha256(identity).hexdigest()

    def _tool(self, target: dict[str, Any], role: str) -> str:
        prefix = "avr" if target["kind"] == "avr" else "arm-none-eabi"
        suffix = {"objcopy": "objcopy", "size": "size"}[role]
        tool = self._which(f"{prefix}-{suffix}")
        if not tool:
            raise CodeRunnerError(f"Chýba nástroj: {prefix}-{suffix}.")
        return tool

    def _compiler(self, target: dict[str, Any], language: str) -> str:
        prefix = "avr" if target["kind"] == "avr" else "arm-none-eabi"
        name = f"{prefix}-g++" if language == "cpp" else f"{prefix}-gcc"
        compiler = self._which(name)
        if not compiler:
            raise CodeRunnerError(f"Chýba nástroj: {name}.")
        return compiler

    @staticmethod
    def _compile_flags(target: dict[str, Any], language: str) -> list[str]:
        if target["kind"] == "avr":
            flags = ["-mmcu=atmega328p", "-ffunction-sections", "-fdata-sections", "-Wall", "-Wextra"]
            if language == "c":
                flags.append("-std=gnu11")
            elif language == "cpp":
                flags.extend(["-std=gnu++14", "-fno-exceptions", "-fno-rtti"])
            else:
                flags.extend(["-x", "assembler-with-cpp"])
            return flags
        flags = [
            "-mcpu=cortex-m3",
            "-mthumb",
            "-ffreestanding",
            "-ffunction-sections",
            "-fdata-sections",
            "-Wall",
            "-Wextra",
        ]
        if language == "c":
            flags.append("-std=gnu11")
        elif language == "cpp":
            flags.extend(["-std=gnu++14", "-fno-exceptions", "-fno-rtti", "-fno-threadsafe-statics"])
        else:
            flags.extend(["-x", "assembler-with-cpp"])
        return flags

    @staticmethod
    def _source_kind(filename: str) -> str | None:
        lower = filename.lower()
        if lower.endswith(".c"):
            return "c"
        if lower.endswith((".cpp", ".cc", ".cxx", ".c++")):
            return "cpp"
        if lower.endswith((".s", ".asm")):
            return "asm"
        return None

    @staticmethod
    def _failed(result: dict[str, Any]) -> bool:
        return bool(result.get("timedOut") or result.get("outputLimited") or result.get("exitCode") != 0)

    @staticmethod
    def _failed_result(message: str) -> dict[str, Any]:
        return {"stdout": "", "stderr": message, "exitCode": 1, "timedOut": False, "outputLimited": False, "durationMs": 0}

    @staticmethod
    def _memory_report(target: dict[str, Any], output: str) -> dict[str, Any]:
        sections = DevelopmentCodeRunner._parse_binary_sections(output)
        flash_used = sum(
            int(section["size"])
            for section in sections
            if str(section["name"]).startswith((".text", ".rodata", ".data", ".init", ".fini", ".isr_vector"))
        )
        ram_used = sum(
            int(section["size"])
            for section in sections
            if str(section["name"]).startswith((".data", ".bss", ".noinit"))
        )
        return {
            "flash": FirmwareBuildRunner._memory_value(flash_used, int(target["flashBytes"])),
            "ram": FirmwareBuildRunner._memory_value(ram_used, int(target["ramBytes"])),
            "sections": sections,
        }

    @staticmethod
    def _stored_memory_report(value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        resources: dict[str, dict[str, int | float]] = {}
        for name in ("flash", "ram"):
            item = value.get(name)
            if not isinstance(item, dict):
                return None
            try:
                used = max(0, int(item.get("used", 0)))
                capacity = max(0, int(item.get("capacity", 0)))
            except (TypeError, ValueError):
                return None
            resources[name] = FirmwareBuildRunner._memory_value(used, capacity)
        sections: list[dict[str, int | str]] = []
        raw_sections = value.get("sections")
        if not isinstance(raw_sections, list):
            return None
        for item in raw_sections[:256]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            try:
                size = max(0, int(item.get("size", 0)))
                address = max(0, int(item.get("address", 0)))
            except (TypeError, ValueError):
                continue
            if name:
                sections.append({"name": name[:160], "size": size, "address": address})
        return {**resources, "sections": sections}

    @staticmethod
    def _memory_value(used: int, capacity: int) -> dict[str, int | float]:
        return {"used": used, "capacity": capacity, "percent": round(used * 100 / capacity, 1) if capacity else 0}

    @staticmethod
    def _limit_process(memory_limit: int = FIRMWARE_MEMORY_LIMIT_BYTES) -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FIRMWARE_ARTIFACT_BYTES, MAX_FIRMWARE_ARTIFACT_BYTES))
        resource.setrlimit(resource.RLIMIT_NOFILE, (48, 48))
        resource.setrlimit(resource.RLIMIT_NPROC, (MAX_PROCESS_COUNT, MAX_PROCESS_COUNT))
