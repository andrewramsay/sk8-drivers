import sys, time

import pysk8
from pysk8.core import Dongle

# called each time a new BLE device is discovered. the parameter is a
# ScanResult object containing information about the device.
def scan_callback(result):
    print('Found device:')
    # .addr contains address formatted as a string, .raw_addr contains binary data
    print('\tAddress: {}'.format(dev.addr))
    # BLE device name 
    print('\tName: {}'.format(dev.name))
    # RSSI from BLED112 API
    print('\tRSSI: {}dBm'.format(dev.rssi))
    # "age" of the result object, i.e. how long since it was created
    print('\tAge: {}s'.format(dev.age()))


def scanner(port):
    with Dongle() as dongle:

        if not dongle.init(port):
            sys.exit('Failed to init dongle on port {}'.format(port))

        # begin a scan for BLE devices. this will run in the background
        # until end_scan() is called. The parameter is an optional callable
        # that will be called when a new device is discovered. You can use this
        # to stop the scan
        dongle.begin_scan(scan_callback)

        # wait until Ctrl-C is pressed to stop the scan
        print('Press Ctrl-C to stop scan')
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass

        # end the scan and retrieve a ScanResults object containing
        # all the discovered BLE devices (not that this list does NOT
        # only contain SK8 devices!)
        results = dongle.end_scan()
        print('Found {} results'.format(len(results)))

if __name__ == "__main__":
    scanner(sys.argv[1])

