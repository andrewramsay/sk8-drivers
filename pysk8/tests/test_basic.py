import os
import time
import unittest
from configparser import ConfigParser

from .context import pysk8
from pysk8.core import Dongle, SK8
from pysk8.constants import *

class BasicTests(unittest.TestCase):

    def setUp(self):
        parser = ConfigParser()
        parser.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'))
        self.config = parser['main']
        self.recv_data = []

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
        
    def imu_callback(self, acc, gyro, mag, index, seq, timestamp, data):
        self.recv_data.append((acc, gyro, mag, index, seq, timestamp))

    def test_imu_streaming(self):
        with Dongle() as d:
            self.assertEqual(True, d.init(self.config['dongle_port']), 'Dongle init failed')
            (result, devicelist) = d.scan_and_connect([self.config['device_name']])
            self.assertEqual(result, True, 'Connection failed, result False')
            device = devicelist[0]
            self.assertEqual(self.config['device_name'], device.get_device_name(), 'Device name mismatch: {} vs expected {}'.format(device.get_device_name(), self.config['device_name']))

            device.set_imu_callback(self.imu_callback)
            result = device.enable_imu_streaming([0], SENSOR_ALL)
            self.assertEqual(result, True, 'Failed to enable IMU streaming')
            time.sleep(1.0)
            result = device.disable_imu_streaming()
            self.assertEqual(result, True, 'Failed to disable IMU streaming')

            # with internal IMU only, should get acc+gyro data but no mag data
            self.assertGreater(len(self.recv_data), 0, 'Failed to receive any data from the IMU!')

            expected = -1
            for d in self.recv_data:
                (acc, gyro, mag, index, seq, timestamp) = d
                self.assertNotEquals(max(acc), 0, 'Acc sample max value is zero: {}'.format(acc))
                self.assertNotEquals(max(gyro), 0, 'Gyro sample max value is zero: {}'.format(gyro))
                self.assertEqual(index, 0, 'Unexpected index value: {}'.format(index))
                if expected == -1:
                    expected = (seq + 1) % 256
                else:
                    self.assertEqual(expected, seq, 'Dropped packet(s) detected: expected {}, found {}'.format(expected, seq))
                    expected = (expected + 1) % 256







if __name__ == "__main__":
    unittest.main()
