import os
import unittest
from configparser import ConfigParser

from .context import pysk8
from pysk8.core import Dongle, SK8

class BasicTests(unittest.TestCase):

    def setUp(self):
        parser = ConfigParser()
        parser.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'))
        self.config = parser['main']

    def test_find_port(self):
        port = Dongle.find_dongle_port()
        self.assertIsNotNone(port, 'find_dongle_port is None')
        self.assertEqual(port, self.config['dongle_port'], 'discovered port {} != defined port {}'.format(port, self.config['dongle_port']))

    # def test_dongle_init_with_reset(self):
    #     with Dongle() as d:
    #         self.assertEqual(True, d.init(self.config['dongle_port'], hard_reset=True), "Dongle init failed")
    #         self.assertGreater(d.get_supported_connections(), 0, 'Supported connections should be at least 1, found {}'.format(d.get_supported_connections()))

    def test_dongle_init(self):
        with Dongle() as d:
            self.assertEqual(True, d.init(self.config['dongle_port'], hard_reset=False), "Dongle init failed")
            self.assertGreater(d.get_supported_connections(), 0, 'Supported connections should be at least 1, found {}'.format(d.get_supported_connections()))

    def test_basic_connect_disconnect(self):
        with Dongle() as d:
            self.assertEqual(True, d.init(self.config['dongle_port']), "Dongle init failed")
            (result, device) = d.connect_direct(self.config['device_addr'])
            self.assertEqual(result, True, 'Connection failed, result False')
            self.assertIsInstance(device, SK8, 'Returned object is not SK8 instance')
            self.assertIsNotNone(device, 'Returned SK8 instance is None')

    def test_get_set_device_name(self):
        with Dongle() as d:
            self.assertEqual(True, d.init(self.config['dongle_port']), 'Dongle init failed')
            (result, device) = d.connect_direct(self.config['device_addr'])
            self.assertEqual(result, True, 'Connection failed, result False')
            self.assertIsInstance(device, SK8, 'Returned object is not SK8 instance')
            self.assertIsNotNone(device, 'Returned SK8 instance is None')
            self.assertEqual(self.config['device_name'], device.get_device_name(), 'Device name mismatch: {} vs expected {}'.format(device.get_device_name(), self.config['device_name']))

            temp_name = 'temp_name'
            self.assertEqual(True, device.set_device_name(temp_name), 'Failed to set device name')
            self.assertEqual(temp_name, device.get_device_name(), 'Device name mismatch: {} vs expected {}'.format(device.get_device_name(), temp_name))
            
            self.assertEqual(True, device.set_device_name(self.config['device_name']), 'Failed to set device name')
            self.assertEqual(self.config['device_name'], device.get_device_name(), 'Device name mismatch: {} vs expected {}'.format(device.get_device_name(), self.config['device_name']))


if __name__ == "__main__":
    unittest.main()
