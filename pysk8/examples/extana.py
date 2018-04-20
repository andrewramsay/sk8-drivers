import sys 
import time

import pysk8
from pysk8.core import Dongle

RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
OFF = (0, 0, 0)
FSR_THRESHOLD = 250

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

        # Enable ExtAna streaming, optionally with internal IMU active too
        enable_imu = True
        if not sk8.enable_extana_streaming(enable_imu):
            sys.exit('Failed to enable streaming!')

        # can optionally get packets through a callback
        def eana_callback(ch1, ch2, temp, seq, timestamp, data):
            print(ch1, ch2, seq)

            # LED is green if both channels above threshold, red for channel 1
            # only, blue for channel 2 only, otherwise off
            if ch1 > FSR_THRESHOLD and ch2 > FSR_THRESHOLD:
                sk8.set_extana_led(*GREEN)
            elif ch1 > FSR_THRESHOLD:
                sk8.set_extana_led(*RED)
            elif ch2 > FSR_THRESHOLD:
                sk8.set_extana_led(*BLUE)
            else:
                sk8.set_extana_led(*OFF)
        sk8.set_extana_callback(eana_callback)

        while True:
            try:
                # retrieve latest set of analog data
                data = sk8.get_extana()
                # if IMU enabled above, this should return valid data too
                imu_data = sk8.get_imu(0)

                time.sleep(0.01)

            except KeyboardInterrupt:
                print('Disconnecting...')
                break

        sk8.disable_extana_streaming()
        sk8.disconnect()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit('Usage: python extana.py <serial port> <device name>')

    extana(sys.argv[1], sys.argv[2])
