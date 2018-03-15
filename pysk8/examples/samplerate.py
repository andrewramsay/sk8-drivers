import sys
import time

import pysk8
from pysk8.core import Dongle
from pysk8.constants import SENSOR_ALL

def samplerate(port, device_name):
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

        # Enable IMU data streaming from the SK8 only (no external IMUs)
        sk8.enable_imu_streaming([0], enabled_sensors=SENSOR_ALL)

        start_time, last_time = time.time(), time.time()
        while True:
            try:
                if time.time() - last_time > 1.0:
                    elapsed = time.time() - start_time
                    print('------------')
                    # display the rate at which data packets are being received (from each IMU)
                    print('Rate: {:.2f}Hz'.format((sk8.get_received_packets() / elapsed) / len(sk8.get_enabled_imus())))
                    last_time = time.time()

                imu = sk8.get_imu(0)
                print('acc={}, mag={}, gyro={}'.format(imu.acc, imu.mag, imu.gyro))
                time.sleep(0.05)
            except KeyboardInterrupt:
                print('Disconnecting...')
                break

        sk8.disable_imu_streaming()
        sk8.disconnect()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit('Usage: python samplerate.py <serial port> <device name>')

    samplerate(sys.argv[1], sys.argv[2])
