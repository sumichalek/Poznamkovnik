"""Local preflight checks for firmware toolchains and programmers.

This module only discovers local executables.  It intentionally neither opens
serial ports nor writes to a device; those operations need an explicit,
separate programming workflow.
"""

from __future__ import annotations

import shutil
from glob import glob
from collections.abc import Callable
from typing import Any


ToolGroup = tuple[tuple[str, ...], ...]


FIRMWARE_TOOLCHAINS: dict[str, dict[str, ToolGroup]] = {
    "avr-atmega328p": {
        "build": (("avr-gcc",), ("avr-objcopy",), ("avr-size",)),
        "program": (("avrdude",),),
    },
    "pic16f18855": {
        "build": (("xc8-cc", "xc8"),),
        "program": (("mplab_ipe",),),
    },
    "dspic33ck": {
        "build": (("xc16-gcc",),),
        "program": (("mplab_ipe",),),
    },
    "pic32mx": {
        "build": (("xc32-gcc",),),
        "program": (("mplab_ipe",),),
    },
    "samd21": {
        "build": (("arm-none-eabi-gcc",), ("arm-none-eabi-objcopy",), ("arm-none-eabi-size",)),
        "program": (("bossac", "openocd"),),
    },
    "stm32f103": {
        "build": (("arm-none-eabi-gcc",), ("arm-none-eabi-objcopy",), ("arm-none-eabi-size",)),
        "program": (("openocd", "stm32flash"),),
    },
    "esp32": {
        "build": (("idf.py", "xtensa-esp32-elf-gcc", "riscv32-esp-elf-gcc"),),
        "program": (("esptool", "esptool.py"),),
    },
    "rp2040": {
        "build": (("arm-none-eabi-gcc",), ("arm-none-eabi-objcopy",), ("arm-none-eabi-size",)),
        "program": (("picotool",),),
    },
}

# These are deliberately connection profiles, not detected hardware. A profile
# says which local tool could be used later and whether it needs a serial port.
# Detecting and writing to a board belong to the explicit programming workflow.
FIRMWARE_PROGRAMMERS: dict[str, tuple[dict[str, Any], ...]] = {
    "avr-atmega328p": (
        {"id": "avr-arduino", "label": "Arduino bootloader", "requiresPort": True, "writeSupported": True, "tools": (("avrdude",),)},
        {"id": "avr-usbasp", "label": "USBasp", "requiresPort": False, "writeSupported": True, "tools": (("avrdude",),)},
        {"id": "avr-isp", "label": "AVR ISP", "requiresPort": False, "writeSupported": False, "tools": (("avrdude",),)},
    ),
    "pic16f18855": (
        {
            "id": "microchip-mplab-ipe",
            "label": "PICkit, SNAP alebo ICD cez MPLAB IPE",
            "requiresPort": False,
            "writeSupported": False,
            "tools": (("mplab_ipe",),),
        },
    ),
    "dspic33ck": (
        {
            "id": "microchip-mplab-ipe",
            "label": "PICkit, SNAP alebo ICD cez MPLAB IPE",
            "requiresPort": False,
            "writeSupported": False,
            "tools": (("mplab_ipe",),),
        },
    ),
    "pic32mx": (
        {
            "id": "microchip-mplab-ipe",
            "label": "PICkit, SNAP alebo ICD cez MPLAB IPE",
            "requiresPort": False,
            "writeSupported": False,
            "tools": (("mplab_ipe",),),
        },
    ),
    "samd21": (
        {"id": "sam-bossac", "label": "SAM-BA bootloader", "requiresPort": True, "writeSupported": False, "tools": (("bossac",),)},
        {"id": "sam-openocd", "label": "CMSIS-DAP cez OpenOCD", "requiresPort": False, "writeSupported": False, "tools": (("openocd",),)},
    ),
    "stm32f103": (
        {"id": "stm32-uart", "label": "UART bootloader", "requiresPort": True, "writeSupported": True, "tools": (("stm32flash",),)},
        {"id": "stm32-openocd", "label": "ST-LINK alebo CMSIS-DAP", "requiresPort": False, "writeSupported": False, "tools": (("openocd",),)},
    ),
    "esp32": (
        {
            "id": "esp-uart",
            "label": "UART bootloader",
            "requiresPort": True,
            "writeSupported": False,
            "tools": (("esptool", "esptool.py"),),
        },
    ),
    "rp2040": (
        {"id": "rp2040-picotool", "label": "USB cez picotool", "requiresPort": False, "writeSupported": False, "tools": (("picotool",),)},
        {"id": "rp2040-uf2", "label": "USB úložisko UF2", "requiresPort": False, "writeSupported": False, "tools": ()},
    ),
}


def firmware_programmer_ids_for_target(target_id: str) -> set[str]:
    """Return the persisted programmer identifiers permitted for one target."""

    return {str(profile["id"]) for profile in FIRMWARE_PROGRAMMERS.get(target_id, ())}


class FirmwareToolchains:
    """Reports which prerequisites are present for every supported target."""

    def __init__(self, which: Callable[[str], str | None] = shutil.which) -> None:
        self._which = which

    def status(self) -> dict[str, dict[str, Any]]:
        return {target_id: self._target_status(target_id, definition) for target_id, definition in FIRMWARE_TOOLCHAINS.items()}

    def _target_status(self, target_id: str, definition: dict[str, ToolGroup]) -> dict[str, Any]:
        build_tools, missing_build = self._resolve(definition["build"])
        programmer_tools, missing_programmers = self._resolve(definition["program"])
        build_available = not missing_build
        programmer_available = not missing_programmers
        if build_available and programmer_available:
            message = "Pripravené na zostavenie; zápis do zariadenia vyžaduje samostatné potvrdenie."
        elif build_available:
            message = f"Zostavenie je pripravené. Chýba nástroj pre zápis: {', '.join(missing_programmers)}."
        elif programmer_available:
            message = f"Nástroj na zápis je dostupný, ale chýba toolchain pre zostavenie: {', '.join(missing_build)}."
        else:
            missing = ", ".join([*missing_build, *missing_programmers])
            message = f"Chýbajú nástroje: {missing}."
        return {
            "id": target_id,
            "buildAvailable": build_available,
            "programmerAvailable": programmer_available,
            "available": build_available and programmer_available,
            "buildTools": build_tools,
            "programmerTools": programmer_tools,
            "missingBuildTools": missing_build,
            "missingProgrammerTools": missing_programmers,
            "message": message,
        }

    def _resolve(self, groups: ToolGroup) -> tuple[list[str], list[str]]:
        found: list[str] = []
        missing: list[str] = []
        for alternatives in groups:
            tool = next((candidate for candidate in alternatives if self._which(candidate)), "")
            if tool:
                found.append(tool)
            else:
                missing.append(" alebo ".join(alternatives))
        return found, missing


class FirmwareDeviceInventory:
    """Read-only inventory of serial ports and supported connection profiles."""

    _SERIAL_PATTERNS = (
        "/dev/serial/by-id/*",
        "/dev/ttyACM*",
        "/dev/ttyUSB*",
        "/dev/cu.*",
    )

    def __init__(
        self,
        *,
        globber: Callable[[str], list[str]] = glob,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self._globber = globber
        self._which = which

    def status(self) -> dict[str, Any]:
        return {
            "ports": self._serial_ports(),
            "programmers": {
                target_id: self._programmers_for_target(target_id, profiles)
                for target_id, profiles in FIRMWARE_PROGRAMMERS.items()
            },
        }

    def _serial_ports(self) -> list[dict[str, str]]:
        paths = {path for pattern in self._SERIAL_PATTERNS for path in self._globber(pattern)}
        return [{"id": path, "label": path} for path in sorted(paths, key=str.casefold)[:64]]

    def _programmers_for_target(self, target_id: str, profiles: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for profile in profiles:
            tools, missing = self._resolve(profile["tools"])
            has_programming_step = bool(profile["tools"])
            available = has_programming_step and not missing
            write_supported = bool(profile.get("writeSupported"))
            if not write_supported:
                message = "Zápis cez tento profil sa pripojí v samostatnom kroku."
            elif not has_programming_step:
                message = "Zápis cez USB úložisko sa pripojí v samostatnom kroku."
            elif available:
                message = "Pripravené na nastavenie pripojenia."
            else:
                message = f"Chýba nástroj: {', '.join(missing)}."
            entries.append(
                {
                    "id": str(profile["id"]),
                    "label": str(profile["label"]),
                    "requiresPort": bool(profile["requiresPort"]),
                    "available": available,
                    "writeAvailable": available and write_supported,
                    "tools": tools,
                    "missingTools": missing,
                    "message": message,
                }
            )
        return entries

    def _resolve(self, groups: ToolGroup) -> tuple[list[str], list[str]]:
        found: list[str] = []
        missing: list[str] = []
        for alternatives in groups:
            tool = next((candidate for candidate in alternatives if self._which(candidate)), "")
            if tool:
                found.append(tool)
            else:
                missing.append(" alebo ".join(alternatives))
        return found, missing
