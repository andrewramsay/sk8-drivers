import sys
import time
import logging

import pysk8
from pysk8.core import Dongle

def extana(port, device_name):
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

        # Enable ExtAna streaming
        if not sk8.enable_extana_streaming(True):
            sys.exit('Failed to enable streaming!')

        start_time, last_time = time.time(), time.time()
        c = 0
        while True:
            try:
                if time.time() - last_time > 1.0:
                    elapsed = time.time() - start_time
                    print('------------')
                    # display the rate at which data packets are being received
                    print('Rate: {:.2f}Hz'.format((sk8.get_received_packets() / elapsed)))
                    last_time = time.time()

                data = sk8.get_extana()
                print(data)
                print(sk8.get_imu(0))
                time.sleep(0.5) 

                if c == 0:
                    print('RED')
                    sk8.set_extana_led(255, 0, 0)
                    print(sk8.get_extana_led())
                elif c == 1:
                    print('GREEN')
                    sk8.set_extana_led(0, 255, 0)
                    print(sk8.get_extana_led())
                elif c == 2:
                    print('BLUE')
                    sk8.set_extana_led(0, 0, 255)
                    print(sk8.get_extana_led())
                elif c == 3:
                    sk8.set_extana_led(255, 0, 255)
                    print(sk8.get_extana_led())
                elif c == 4:
                    sk8.set_extana_led(0, 255, 255)
                    print(sk8.get_extana_led())
                elif c == 5:
                    sk8.set_extana_led(255, 255, 0)
                    print(sk8.get_extana_led())
                c = (c + 1) % 6
            except KeyboardInterrupt:
                print('Disconnecting...')
                break

        sk8.disable_extana_streaming()
        sk8.disconnect()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit('Usage: python extana.py <serial port> <device name>')

    extana(sys.argv[1], sys.argv[2])
