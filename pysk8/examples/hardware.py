
import sys 
import time
import logging

import pysk8
from pysk8.core import Dongle

def hardware(port, device_name):
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

        while True:
            try:
                print('Has IMUs: {} | Has ExtAna: {}'.format(sk8.has_imus(False), sk8.has_extana(True)))
                time.sleep(1.0)
            except KeyboardInterrupt:
                print('Disconnecting...')
                break

        sk8.disconnect()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit('Usage: python hardware.py <serial port> <device name>')

    hardware(sys.argv[1], sys.argv[2])
