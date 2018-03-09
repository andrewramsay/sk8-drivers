
class IMUData(object):
    """Instances of this class provide access to sensor data from individual IMUs.

    Attributes:
        acc (list): latest accelerometer readings, [x, y, z]
        mag (list): latest magnetometer readings, [x, y, z]
        acc (list): latest gyroscope readings, [x, y, z]
        seq (int): sequence number from most recent packet (0-255 range)
    """

    def __init__(self, calibration=True, calibration_data=None):
        self.acc = [0, 0, 0]
        self.mag = [0, 0, 0]
        self.gyro = [0, 0, 0]
        self.seq = 0
        self._use_calibration = False
        self.has_acc_calib, self.has_mag_calib, self.has_gyro_calib = False, False, False
        self._load_calibration(calibration_data)

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
        
        self.seq = seq
        self.timestamp = timestamp

    def __repr__(self):
        return 'acc={}, mag={}, gyro={}, seq={}'.format(self.acc, self.mag, self.gyro, self.seq)

