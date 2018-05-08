import sys
import time

import pysk8
from pysk8.core import Dongle

def basic(port, device_name):
    with Dongle() as dongle: # this will disconnect any active connections when it goes out of scope

        if not dongle.init(port):
            sys.exit('Failed to initialise dongle on port {}'.format(port))

        # use the scan_and_connect convenience function to scan for a list of
        # one or more devices and then attempt to connect to them if they are
        # detected in the scan results
        (result, devices) = dongle.scan_and_connect([device_name])

        if not result:
            # scan failed to detect device(s), or connection to those device(s)
            # failed for some reason
            sys.exit('Failed to establish connections to all devices')

        print('Connections created to {} devices'.format(len(devices)))

        # Each entry in this list is an SK8 object representing the physical device
        sk8 = devices[0]

        # Get the name and firmware version
        print('Device 0, name={}, firmware={}'.format(sk8.get_device_name(), sk8.get_firmware_version()))
        print('Battery level: {}%'.format(sk8.get_battery_level()))

        # disconnect the device
        sk8.disconnect()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit('Usage: python basic.py <serial port> <device name>')

    basic(sys.argv[1], sys.argv[2])
