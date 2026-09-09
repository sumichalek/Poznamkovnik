from __future__ import annotations

import unittest

from backend.firmware import FirmwareDeviceInventory, FirmwareToolchains


class FirmwareToolchainsTestCase(unittest.TestCase):
    def test_target_status_distinguishes_build_from_programming_tools(self) -> None:
        installed = {"avr-gcc", "avr-objcopy", "avr-size", "avrdude", "stm32flash", "mplab_ipe"}
        toolchains = FirmwareToolchains(lambda name: f"/tools/{name}" if name in installed else None)
        status = toolchains.status()

        avr = status["avr-atmega328p"]
        self.assertTrue(avr["buildAvailable"])
        self.assertTrue(avr["programmerAvailable"])
        self.assertTrue(avr["available"])

        stm32 = status["stm32f103"]
        self.assertFalse(stm32["buildAvailable"])
        self.assertTrue(stm32["programmerAvailable"])
        self.assertIn("chýba toolchain", stm32["message"])

        pic = status["pic16f18855"]
        self.assertFalse(pic["buildAvailable"])
        self.assertTrue(pic["programmerAvailable"])

    def test_device_inventory_lists_ports_and_connection_profiles_without_touching_them(self) -> None:
        installed = {"avrdude", "stm32flash"}
        inventory = FirmwareDeviceInventory(
            globber=lambda pattern: {
                "/dev/serial/by-id/*": ["/dev/serial/by-id/usb-board"],
                "/dev/ttyACM*": ["/dev/ttyACM0"],
                "/dev/ttyUSB*": ["/dev/ttyUSB0", "/dev/ttyUSB0"],
            }.get(pattern, []),
            which=lambda name: f"/tools/{name}" if name in installed else None,
        )

        status = inventory.status()

        self.assertEqual(
            status["ports"],
            [
                {"id": "/dev/serial/by-id/usb-board", "label": "/dev/serial/by-id/usb-board"},
                {"id": "/dev/ttyACM0", "label": "/dev/ttyACM0"},
                {"id": "/dev/ttyUSB0", "label": "/dev/ttyUSB0"},
            ],
        )
        avr = {profile["id"]: profile for profile in status["programmers"]["avr-atmega328p"]}
        self.assertTrue(avr["avr-arduino"]["available"])
        self.assertTrue(avr["avr-arduino"]["requiresPort"])
        stm32 = {profile["id"]: profile for profile in status["programmers"]["stm32f103"]}
        self.assertTrue(stm32["stm32-uart"]["available"])
        self.assertFalse(stm32["stm32-openocd"]["available"])
