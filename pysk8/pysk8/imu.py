import time

class IMUData(object):
    """Instances of this class provide access to sensor data from individual IMUs.

    Attributes:
        acc (list): latest accelerometer readings, [x, y, z]
        mag (list): latest magnetometer readings, [x, y, z]
        acc (list): latest gyroscope readings, [x, y, z]
        seq (int): sequence number from most recent packet (0-255 range)
        timestamp (float): value of `time.time()` when packet received
    """

    PACKET_PERIOD = 3

    def __init__(self, index, calibration_data=None):
        self.calibration_data = calibration_data
        self.index = index
        self.reset()

    def reset(self):
        self.acc = [0, 0, 0]
        self.mag = [0, 0, 0]
        self.gyro = [0, 0, 0]
        self.seq = 0
        self._use_calibration = False
        self.has_acc_calib, self.has_mag_calib, self.has_gyro_calib = False, False, False
        self._load_calibration(self.calibration_data)
        self.packet_metadata = []
        self.packet_start = time.time()
        self.packets_lost = 0

    def get_sample_rate(self):
        if time.time() - self.packet_start < IMUData.PACKET_PERIOD:
            return -1
        return len(self.packet_metadata) / IMUData.PACKET_PERIOD

    def get_packets_lost(self):
        sample_rate = self.get_sample_rate()
        if sample_rate == -1:
            return -1

        return sum([x[1] for x in self.packet_metadata])

    def get_total_packets_lost(self):
        return self.pakcets_lost 

    def _load_calibration(self, calibration_data):
        axes = ['x', 'y', 'z']
        if calibration_data is None:
            return False

        if 'accx_offset' in calibration_data:
            self.acc_scale = list(map(float, [calibration_data['acc{}_scale'.format(x)] for x in axes]))
            self.acc_offsets = list(map(int, [calibration_data['acc{}_offset'.format(x)] for x in axes]))
            self.has_acc_calib = True
        else:
            self.acc_scale = None
            self.acc_offsets = None
            
        if 'gyrox_offset' in calibration_data:
            self.gyro_offsets = list(map(int, [calibration_data['gyro{}_offset'.format(x)] for x in axes]))
            self.has_gyro_calib = True
        else:
            self.gyro_offsets = None

        if 'magx_offset' in calibration_data:
            self.mag_scale = list(map(float, [calibration_data['mag{}_scale'.format(x)] for x in axes]))
            self.mag_offsets = list(map(int, [calibration_data['mag{}_offset'.format(x)] for x in axes]))
            self.has_mag_calib = True
        else:
            self.mag_offsets = None
            self.mag_scale = None

        self._use_calibration = True
        return True

    def _get_cal(self, raw, offset, scale=None):
        if offset is not None and scale is None:
            return [raw[x] - offset[x] for x in range(len(raw))]
        elif offset is None:
            return raw
        return [(raw[x] * scale[x]) - offset[x] for x in range(len(raw))]

    def _update(self, acc, gyro, mag, seq, timestamp):
        if not self._use_calibration:
            self.acc = acc
            self.gyro = gyro
            self.mag = mag
        else:
            self.acc = list(map(int, self._get_cal(acc, self.acc_offsets, self.acc_scale)))
            self.gyro = self._get_cal(gyro, self.gyro_offsets, None)
            self.mag = list(map(int, self._get_cal(mag, self.mag_offsets, self.mag_scale)))
        
        dropped = 0
        if self.seq != -1:
            expected = (self.seq + 1) % 256
            if expected != seq:
                dropped = (expected - seq) % 256
                self.packets_lost += dropped
        self.seq = seq
        self.timestamp = timestamp
        self.packet_metadata.insert(0, (timestamp, dropped))
        now = time.time()
        while now - self.packet_metadata[-1][0] > IMUData.PACKET_PERIOD:
            self.packet_metadata.pop()

    def __repr__(self):
        return '[{}] acc={}, mag={}, gyro={}, seq={}'.format(self.index, self.acc, self.mag, self.gyro, self.seq)

