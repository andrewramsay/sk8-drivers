import sys

import pysk8
from pysk8.core import Dongle

def namechange(port, device_name):
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
        sk8 = dongle.get_devices()[0]

        print('Device name (cached) is: {}'.format(sk8.get_device_name(cached=True)))
        print('Device name (uncached) is: {}'.format(sk8.get_device_name(cached=False)))

        print('Changing device name to "TEST"...')
        if not sk8.set_device_name('TEST'):
            sys.exit('Failed to set device name')

        print('Reading back name (cached): {}'.format(sk8.get_device_name(cached=True)))
        print('Reading back name (uncached): {}'.format(sk8.get_device_name(cached=False)))

        print('Changing device name back to original...')
        if not sk8.set_device_name(device_name):
            sys.exit('Failed to set device name')

        print('Reading back name (cached): {}'.format(sk8.get_device_name(cached=True)))
        print('Reading back name (uncached): {}'.format(sk8.get_device_name(cached=False)))

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit('Usage: python basic.py <serial port> <device name>')

    namechange(sys.argv[1], sys.argv[2])
