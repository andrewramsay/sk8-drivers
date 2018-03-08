import unittest

from .context import pysk8
from pysk8.util import fmt_addr, fmt_addr_raw, pp_hex

class UtilTests(unittest.TestCase):

    TEST_ADDR = '50:c2:00:a1:d1:20'
    TEST_RAW = b'\x20\xd1\xa1\x00\xc2\x50'
    TEST_HEX = b'\x10\x20\x33\x73\x99'
    TEST_HEX_IN = b'\x41\x42\x43\x44\x45\x46'
    TEST_HEX_OUT = '464544434241'

    def test_fmt_addr_raw(self):
        self.assertEqual(UtilTests.TEST_RAW, fmt_addr_raw(UtilTests.TEST_ADDR))

    def test_fmt_addr(self):
        self.assertEqual(UtilTests.TEST_ADDR, fmt_addr(UtilTests.TEST_RAW))

    def test_pp_hex(self):
        self.assertEqual(UtilTests.TEST_HEX_OUT, pp_hex(UtilTests.TEST_HEX_IN))

if __name__ == "__main__":
    unittest.main()
