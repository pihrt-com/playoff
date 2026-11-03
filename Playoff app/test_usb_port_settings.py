import unittest

import playoff


class USBPortSettingsTests(unittest.TestCase):
    def test_disabled_choice_is_persisted_as_empty_port(self):
        self.assertEqual(
            playoff.normalize_usb_port_choice(playoff.USB_PORT_DISABLED_LABEL),
            "",
        )
        self.assertEqual(playoff.usb_port_choice(""), playoff.USB_PORT_DISABLED_LABEL)

    def test_one_display_without_gate_has_no_conflict(self):
        self.assertIsNone(playoff.find_usb_port_conflict("", "COM3", ""))

    def test_duplicate_gate_and_display_port_is_rejected(self):
        self.assertEqual(
            playoff.find_usb_port_conflict("COM3", "COM3", ""),
            ("COM3", "Měřící brána", "LED displej ID-1"),
        )

    def test_duplicate_display_ports_are_rejected_case_insensitively(self):
        self.assertEqual(
            playoff.find_usb_port_conflict("", "com3", "COM3"),
            ("COM3", "LED displej ID-1", "LED displej ID-2"),
        )

    def test_configured_identical_panels_are_listed_as_generic_displays(self):
        details = [
            {"device": "COM5", "description": "USB-SERIAL CH340"},
            {"device": "COM6", "description": "USB-SERIAL CH340"},
        ]

        detected = playoff.classify_usb_devices(details, "", "COM5", "COM6")

        self.assertEqual(detected["detected_displays"], ["COM5", "COM6"])
        self.assertEqual(detected["detected_gates"], [])
        self.assertEqual(detected["unassigned"], [])

    def test_mega_is_detected_but_unknown_ch340_is_not_guessed(self):
        details = [
            {"device": "COM3", "description": "Arduino Mega 2560"},
            {"device": "COM5", "description": "USB-SERIAL CH340"},
        ]

        detected = playoff.classify_usb_devices(details)

        self.assertEqual(detected["detected_gates"], ["COM3"])
        self.assertEqual(detected["detected_displays"], [])
        self.assertEqual(
            [item["device"] for item in detected["unassigned"]],
            ["COM5"],
        )

    def test_nano_descriptor_is_detected_as_generic_display(self):
        details = [{"device": "COM7", "description": "Arduino Nano"}]

        detected = playoff.classify_usb_devices(details)

        self.assertEqual(detected["detected_displays"], ["COM7"])


if __name__ == "__main__":
    unittest.main()
