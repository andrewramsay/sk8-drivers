import sys

import pysk8
from pysk8.core import Dongle

def set_name(port, device_name_old, device_name_new):
    with Dongle() as dongle: # this will disconnect any active connections when it goes out of scope

        if not dongle.init(port):
            sys.exit('Failed to initialise dongle on port {}'.format(port))

        # use the scan_and_connect convenience function to scan for a list of
        # one or more devices and then attempt to connect to them if they are
        # detected in the scan results
        (result, devices) = dongle.scan_and_connect([device_name_old])

        if not result:
            # scan failed to detect device(s), or connection to those device(s)
            # failed for some reason
            sys.exit('Failed to establish connections to all devices')

        print('Connections created to {} devices'.format(len(devices)))

        # Each entry in this list is an SK8 object representing the physical device
        sk8 = dongle.get_devices()[0]

        print('Changing device name to "{}"...'.format(device_name_new))
        if not sk8.set_device_name(device_name_new):
            sys.exit('Failed to set device name')

        print('Reading back name (cached): {}'.format(sk8.get_device_name(cached=True)))
        print('Reading back name (uncached): {}'.format(sk8.get_device_name(cached=False)))

if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit('Usage: python namechange.py <serial port> <device name> <new device name>')

    set_name(sys.argv[1], sys.argv[2], sys.argv[3])
