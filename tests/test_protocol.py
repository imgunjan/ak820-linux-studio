import unittest
from datetime import datetime
from ak820linux.protocol import (command_packet, time_data_packet, image_header,
                                 image_payload, _usb_identity, _usage_page, FRAME_BYTES)
from ak820linux.images import rgb565, text_card


class ProtocolTest(unittest.TestCase):
    def test_start_packet(self):
        p = command_packet(0x18)
        self.assertEqual(len(p), 64)
        self.assertEqual((p[0], p[1], p[8]), (4, 0x18, 1))

    def test_clock(self):
        p = time_data_packet(datetime(2026, 5, 16, 14, 30, 45))
        self.assertEqual(len(p), 64)
        self.assertEqual(p[:11].hex(), '00015a1a05100e1e2d0004')
        self.assertEqual(p[62:], bytes.fromhex('aa55'))

    def test_static_header(self):
        h = image_header()
        self.assertEqual(h[:4], bytes.fromhex('0100ffff'))
        self.assertEqual(len(h), 256)

    def test_image_padding(self):
        data = image_payload([bytes(FRAME_BYTES)])
        self.assertEqual(len(data), 9 * 4096)
        self.assertEqual(data[:2], b'\x01\x00')
        self.assertEqual(data[-1], 255)

    def test_gif(self):
        data = image_payload([bytes(FRAME_BYTES), bytes([1]) * FRAME_BYTES], [100, 200])
        self.assertEqual(data[:3], bytes([2, 50, 100]))
        self.assertEqual(len(data) % 4096, 0)

    def test_usb(self):
        self.assertEqual(_usb_identity('HID_ID=0003:00000C45:00008009'), (0x0c45, 0x8009))
        self.assertEqual(_usage_page(b'\x06\x13\xff\x09\x01\xa1\x01\xc0'), 0xFF13)
        self.assertEqual(_usage_page(b'\x06\x68\xff\x09\x01\xa1\x01\xc0'), 0xFF68)

    def test_image(self):
        rgb = rgb565(text_card('Hello Linux'))
        self.assertEqual(len(rgb), FRAME_BYTES)


if __name__ == '__main__':
    unittest.main()
