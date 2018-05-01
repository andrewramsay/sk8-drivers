import sys
import time

import pysk8
from pysk8.core import Dongle
from pysk8.constants import SENSOR_ALL, SENSOR_ACC, SENSOR_MAG, SENSOR_GYRO

from msvcrt import getch, kbhit

import logging

pysk8.core.logger.setLevel(logging.DEBUG)

def samplerate(port, device_names):
    with Dongle() as dongle: # this will disconnect any active connections when it goes out of scope

        if not dongle.init(port):
            sys.exit('Failed to initialise dongle on port {}'.format(port))

        # use the scan_and_connect convenience function to scan for a list of
        # one or more devices and then attempt to connect to them if they are
        # detected in the scan results
        (result, devices) = dongle.scan_and_connect(device_names, 5.0)

        if not result:
            # scan failed to detect device(s), or connection to those device(s)
            # failed for some reason
            sys.exit('Failed to establish connections to all devices')

        print('Connections created to {} devices'.format(len(devices)))

        # Enable IMU data streaming from the SK8 only (no external IMUs)
        for sk8 in devices:
            sk8.enable_imu_streaming([0, 1, 2, 3, 4], enabled_sensors=SENSOR_ACC|SENSOR_GYRO)
        # start_time = time.time()
        last_time = time.time()
        show_data = False

        logfile = open('log.txt', 'w')

        def imu_callback(acc, gyro, mag, index, seq, timestamp, data):
            if show_data:
                print('{}: [{}] acc={}, mag={}, gyro={}, seq={}'.format(data, index, acc, mag, gyro, seq))
            logfile.write('{},{},{},{},{}\n'.format(data, index, seq, timestamp, acc))

        for sk8 in devices:
            sk8.set_imu_callback(imu_callback, sk8.name)

        while True:
            try:
                if time.time() - last_time > 1.0:

                    # display the rate at which data packets are being received (from each IMU)
                    for sk8 in devices:
                        rates = []
                        drops = []
                        for i in sk8.get_enabled_imus():
                            imu = sk8.get_imu(i)
                            rates.append(imu.get_sample_rate())
                            drops.append(imu.get_packets_lost())

                        if -1 not in rates:
                            print('------------')
                            fmt_f = '{:.1f}|' * len(rates)
                            fmt_d = '{:02d}|' * len(rates)
                            print('Rates: ' + fmt_f.format(*rates))
                            print('Drops: ' + fmt_d.format(*drops))
                            print(devices[0].get_polling_override())
                        else:
                            print('Waiting...')

                    last_time = time.time()

                time.sleep(0.01)

                if kbhit():
                    ch = getch()
                    if ch == b's':
                        show_data = not show_data
                    if ch == b'1':
                        print(devices[0].set_polling_override(50))
                    if ch == b'0':
                        print(devices[0].set_polling_override(10))

            except KeyboardInterrupt:
                print('Disconnecting...')
                break

        for sk8 in devices:
            sk8.disable_imu_streaming()
            sk8.disconnect()
        logfile.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit('Usage: python samplerate.py <serial port> <device name>')

    samplerate(sys.argv[1], sys.argv[2:])
