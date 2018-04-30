import sys, time, os, logging

from datetime import datetime
from configparser import ConfigParser

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QMainWindow, QApplication, QDialog

from sk8_calibration_gui_ui import Ui_MainWindow
from sk8_acc_dialog_ui import Ui_AccDialog
from sk8_gyro_dialog_ui import Ui_GyroDialog
from sk8_mag_dialog_ui import Ui_MagDialog

from pysk8.core import Dongle

class ScanDeviceItem(QtGui.QStandardItem):
    """Overrides QStandardItem to show device name+address in scanned devices list"""

    def __init__(self, device):
        QtGui.QStandardItem.__init__(self, 'name={}, address={}'.format(device.name, device.addr))
        self.device = device

class SK8GyroDialog(QDialog, Ui_GyroDialog):
    """Implements a simple dialog to carry out gyro calibration"""

    INTERVAL = 50
    GYRO_BIAS_TIME = 5

    def __init__(self, imu, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.imu = imu
        # set up and start a timer to record gyro samples
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(self.INTERVAL)
        self.timer.timeout.connect(self.update)
        self.started_at = time.time()
        self.samples = []
        self.timer.start()

    def accept(self):
        QDialog.accept(self)
        self.timer.stop()

    def reject(self):
        QDialog.reject(self)
        self.timer.stop()

    def update(self):
        # on every timer tick, record a gyro sample and exit if required time has elapsed
        elapsed = int(100 * ((time.time() - self.started_at) / self.GYRO_BIAS_TIME))
        self.progressBar.setValue(elapsed)
        self.samples.append(self.imu.gyro)

        if time.time() - self.started_at > self.GYRO_BIAS_TIME:
            self.accept()
            QtWidgets.QMessageBox.information(self, 'Gyro calibration', 'Calibration finished')

class SK8AccDialog(QDialog, Ui_AccDialog):
    """Implements a simple dialog to carry out accelerometer calibration"""

    INTERVAL = 20
    RECORD_TIME = 1.00

    def __init__(self, imu, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.imu = imu
        self.state = 0
        self.recording = False
        self.recording_started = time.time()

        # setup button handlers
        self.buttons = [self.btnPosX, self.btnNegX, self.btnPosY, self.btnNegY, self.btnPosZ, self.btnNegZ]
        for i, b in enumerate(self.buttons):
            b.clicked.connect(self.record)
        self.btnCancel.clicked.connect(self.reject)
        self.btnOK.clicked.connect(self.accept)
        self.buttons[0].setFocus(True)

        # want to record samples individually for +/- x, y, z
        self.samples = [[] for x in range(6)]

        # start a timer to collect accelerometer samples
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(self.INTERVAL)
        self.timer.timeout.connect(self.update)
        self.timer.start()

    def accept(self):
        QDialog.accept(self)
        self.timer.stop()

    def reject(self):
        QDialog.reject(self)
        self.timer.stop()

    def record(self):
        if self.state < len(self.buttons):
            self.recording = True
            self.buttons[self.state].setEnabled(False)
            self.recording_started = time.time()

    def update(self):
        # on timer tick, update UI...
        self.dataAccX.setText('X: {}'.format(str(self.imu.acc[0])))
        self.dataAccY.setText('Y: {}'.format(str(self.imu.acc[1])))
        self.dataAccZ.setText('Z: {}'.format(str(self.imu.acc[2])))

        if self.recording:
            # record current sample in appropriate list
            self.samples[self.state].append(self.imu.acc)
            elapsed = (time.time() - self.recording_started) / self.RECORD_TIME
            self.progSamples.setValue(int(100 * elapsed))
            if elapsed >= 1.0:
                # if required time has elapsed, move to next state or finish
                self.buttons[self.state].setEnabled(False)
                self.recording = False
                self.state += 1
                self.progSamples.setValue(0)
                if self.state < 6:
                    self.buttons[self.state].setEnabled(True)
                    self.buttons[self.state].setFocus(True)
                else:
                    self.btnOK.setEnabled(True)
                    self.btnOK.setFocus(True)

class SK8MagDialog(QDialog, Ui_MagDialog):
    """"Implements a simple dialog to carry out magnetometer calibration"""

    INTERVAL = 20

    def __init__(self, imu, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.imu = imu
        self.state = 0
        
        # setup button handlers
        self.buttons = [self.btnPosX, self.btnNegX, self.btnPosY, self.btnNegY, self.btnPosZ, self.btnNegZ]
        for i, b in enumerate(self.buttons):
            b.clicked.connect(self.record)
        self.btnCancel.clicked.connect(self.reject)
        self.btnOK.clicked.connect(self.accept)
        self.buttons[0].setFocus(True)
        self.samples = []

        # start a timer to collect magnetometer samples
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(self.INTERVAL)
        self.timer.timeout.connect(self.update)
        self.timer.start()

    def accept(self):
        QDialog.accept(self)
        self.timer.stop()

    def reject(self):
        QDialog.reject(self)
        self.timer.stop()

    def record(self):
        if self.state < len(self.buttons):
            self.samples.append(self.imu.mag)
            self.buttons[self.state].setEnabled(False)
            self.state += 1
            if self.state < len(self.buttons):
                self.buttons[self.state].setEnabled(True)
                self.buttons[self.state].setFocus(True)
            else:
                self.btnOK.setEnabled(True)
                self.btnOK.setFocus(True)

    def update(self):
        self.dataMagX.setText('X: {}'.format(str(self.imu.mag[0])))
        self.dataMagY.setText('Y: {}'.format(str(self.imu.mag[1])))
        self.dataMagZ.setText('Z: {}'.format(str(self.imu.mag[2])))

class SK8Calibration(QMainWindow, Ui_MainWindow):

    # scanning states
    SCAN_STATE_IDLE        = 0
    SCAN_STATE_ACTIVE      = 1
    SCAN_STATE_STOP        = 2

    # calibration modes
    CAL_ACC                = 0
    CAL_GYRO               = 1
    CAL_MAG                = 2
    CAL_NONE               = 3

    # default filename for storing calibration data
    DEFAULT_CALIB_FILENAME = 'sk8calib.ini'

    # strings identifying the various calibration parameters
    ACCX_OFFSET            = 'accx_offset'
    ACCY_OFFSET            = 'accy_offset'
    ACCZ_OFFSET            = 'accz_offset'
    ACCX_SCALE             = 'accx_scale'
    ACCY_SCALE             = 'accy_scale'
    ACCZ_SCALE             = 'accz_scale'
    ACC_TIMESTAMP          = 'acc_timestamp'

    GYROX_OFFSET           = 'gyrox_offset'
    GYROY_OFFSET           = 'gyroy_offset'
    GYROZ_OFFSET           = 'gyroz_offset'
    GYRO_TIMESTAMP         = 'gyro_timestamp'

    MAGX_OFFSET            = 'magx_offset'
    MAGY_OFFSET            = 'magy_offset'
    MAGZ_OFFSET            = 'magz_offset'
    MAGX_SCALE             = 'magx_scale'
    MAGY_SCALE             = 'magy_scale'
    MAGZ_SCALE             = 'magz_scale'
    MAG_TIMESTAMP          = 'mag_timestamp'

    def __init__(self, dongle_port):
        QMainWindow.__init__(self)
        self.setupUi(self)

        # setup the dongle
        self.dongle = Dongle()
        self.dongle.init(dongle_port)

        # disable maximize button
        flags = self.windowFlags()
        flags ^= QtCore.Qt.WindowMaximizeButtonHint
        self.setWindowFlags(flags | QtCore.Qt.CustomizeWindowHint)

        # hook up various Qt GUI slots etc
        self.devicelist_model = QtGui.QStandardItemModel(self.lstDevices)
        self.lstDevices.setModel(self.devicelist_model)
        self.lblPort.setText('Dongle serial port: {}'.format(dongle_port))
        self.btnRefresh.clicked.connect(self.refresh_devices)
        self.btnCancelScan.clicked.connect(self.cancel_scan)
        self.lstDevices.clicked.connect(self.device_selected)
        self.btnConnect.clicked.connect(self.connect_device)
        self.btnConnect.setEnabled(False)
        self.btnAcc.clicked.connect(self.accel_calibration)
        self.btnGyro.clicked.connect(self.gyro_calibration)
        self.btnMag.clicked.connect(self.mag_calibration)
        self.btnExit.clicked.connect(self.exit)
        self.spinIMU.valueChanged.connect(self.imu_changed)
        self.spinIMU.setEnabled(False)

        self.gyro_dialog = None
        self.acc_dialog = None
        self.mag_dialog = None
        self.sk8 = None
        self.current_imuid = None
        self.calibration_state = self.CAL_NONE
        self.scan_state = self.SCAN_STATE_IDLE

        # start a 30ms timer to update displayed sensor data
        self.data_timer = QtCore.QTimer(self)
        self.data_timer.setInterval(30)
        self.data_timer.timeout.connect(self.update_data)
        
        # start a 3s timer to update battery level 
        self.battery_timer = QtCore.QTimer(self)
        self.battery_timer.setInterval(3000)
        self.battery_timer.timeout.connect(self.update_battery)
        
        # attempt to parse any existing calibration file
        self.calibration_data = ConfigParser()
        self.calibration_data.read(os.path.join(os.path.dirname(__file__), self.DEFAULT_CALIB_FILENAME))

        # begin a scan on startup
        self.refresh_devices()

    def get_current_data(self):
        """Return the calibration data for the current IMU, if any."""
        if self.current_imuid in self.calibration_data:
            return self.calibration_data[self.current_imuid]

        return {}

    def update_battery(self):
        """Updates the battery level in the UI for the connected SK8, if any"""
        if self.sk8 is None:
            return
        battery = self.sk8.get_battery_level()
        self.lblBattery.setText('Battery: {}%'.format(battery))

    def imu_changed(self, val):
        """Handle clicks on the IMU index spinner."""
        self.current_imuid = '{}_IMU{}'.format(self.sk8.get_device_name(), val)
        self.update_data_display(self.get_current_data())
            
    def accel_calibration(self):
        """Perform accelerometer calibration for current IMU."""
        self.calibration_state = self.CAL_ACC
        self.acc_dialog = SK8AccDialog(self.sk8.get_imu(self.spinIMU.value()), self)
        if self.acc_dialog.exec_() == QDialog.Rejected:
            return
        
        self.calculate_acc_calibration(self.acc_dialog.samples)

    def gyro_calibration(self):
        """Perform gyroscope calibration for current IMU."""
        QtWidgets.QMessageBox.information(self, 'Gyro calibration', 'Ensure the selected IMU is in a stable, unmoving position, then click OK. Don\'t move the the IMU for a few seconds')
        self.calibration_state = self.CAL_GYRO
        self.gyro_dialog = SK8GyroDialog(self.sk8.get_imu(self.spinIMU.value()), self)
        if self.gyro_dialog.exec_() == QDialog.Rejected:
            return
        
        self.calculate_gyro_calibration(self.gyro_dialog.samples)
    
    def mag_calibration(self):
        """Perform magnetometer calibration for current IMU."""
        self.calibration_state = self.CAL_MAG
        self.mag_dialog = SK8MagDialog(self.sk8.get_imu(self.spinIMU.value()), self)
        if self.mag_dialog.exec_() == QDialog.Rejected:
            return

        self.calculate_mag_calibration(self.mag_dialog.samples)

    def update_data(self):
        """Updates the displayed data in the GUI for the current IMU, applying
        current calibration if it is available. """
        if self.sk8 is not None:
            imu = self.spinIMU.value()
            data = self.sk8.get_imu(imu)
            if self.current_imuid in self.calibration_data:
                calib_data = self.calibration_data[self.current_imuid]
            else:
                calib_data = {}
                self.calibration_data[self.current_imuid] = calib_data

            if calib_data is not None and self.ACC_TIMESTAMP in calib_data:
                self.dataAccX.setText(str(int((data.acc[0] * float(calib_data[self.ACCX_SCALE])) - float(calib_data[self.ACCX_OFFSET]))))
                self.dataAccY.setText(str(int((data.acc[1] * float(calib_data[self.ACCY_SCALE])) - float(calib_data[self.ACCY_OFFSET]))))
                self.dataAccZ.setText(str(int((data.acc[2] * float(calib_data[self.ACCZ_SCALE])) - float(calib_data[self.ACCZ_OFFSET]))))
            else:
                self.dataAccX.setText(str(data.acc[0]))
                self.dataAccY.setText(str(data.acc[1]))
                self.dataAccZ.setText(str(data.acc[2]))

            if calib_data is not None and self.GYRO_TIMESTAMP in calib_data:
                self.dataGyroX.setText(str(data.gyro[0] - int(calib_data[self.GYROX_OFFSET])))
                self.dataGyroY.setText(str(data.gyro[1] - int(calib_data[self.GYROY_OFFSET])))
                self.dataGyroZ.setText(str(data.gyro[2] - int(calib_data[self.GYROZ_OFFSET])))
            else:
                self.dataGyroX.setText(str(data.gyro[0]))
                self.dataGyroY.setText(str(data.gyro[1]))
                self.dataGyroZ.setText(str(data.gyro[2]))

            if calib_data is not None and self.MAG_TIMESTAMP in calib_data:
                self.dataAccX.setText(str(int((data.mag[0] * float(calib_data[self.MAGX_SCALE])) - float(calib_data[self.MAGX_OFFSET]))))
                self.dataAccY.setText(str(int((data.mag[1] * float(calib_data[self.MAGY_SCALE])) - float(calib_data[self.MAGY_OFFSET]))))
                self.dataAccZ.setText(str(int((data.mag[2] * float(calib_data[self.MAGZ_SCALE])) - float(calib_data[self.MAGZ_OFFSET]))))
            else:
                self.dataMagX.setText(str(data.mag[0]))
                self.dataMagY.setText(str(data.mag[1]))
                self.dataMagZ.setText(str(data.mag[2]))

    def calculate_gyro_calibration(self, gyro_samples):
        """Performs a basic gyroscope bias calculation. 

        Takes a list of (x, y, z) samples and averages over each axis to calculate
        the bias values, and stores them in the calibration data structure for the 
        currently connected SK8"""

        totals = [0, 0, 0]
        for gs in gyro_samples:
            totals[0] += gs[0]
            totals[1] += gs[1]
            totals[2] += gs[2]

        for i in range(3):
            totals[i] = int(float(totals[i]) / len(gyro_samples))

        print('Saving gyro offsets for {}'.format(self.current_imuid))
        self.calibration_data[self.current_imuid][self.GYROX_OFFSET] = str(totals[0])
        self.calibration_data[self.current_imuid][self.GYROY_OFFSET] = str(totals[1])
        self.calibration_data[self.current_imuid][self.GYROZ_OFFSET] = str(totals[2])
        self.calibration_data[self.current_imuid][self.GYRO_TIMESTAMP] = datetime.now().isoformat()
        self.write_calibration_data()
        self.update_data_display(self.calibration_data[self.current_imuid])
        self.calibration_state = self.CAL_NONE

    def calculate_acc_calibration(self, acc_samples):
        """Performs accelerometer calibration. Assumes acc_samples contains samples
        in order [+x, -x, +y, -y, +z, -z]. Calculates per-axis scale/offset values"""

        # assumes 2g range
        data = self.calibration_data[self.current_imuid]
        accx_pos = sum([x[0] for x in acc_samples[0]]) / float(len(acc_samples[0]))
        accx_neg = sum([x[0] for x in acc_samples[1]]) / float(len(acc_samples[1]))
        accy_pos = sum([y[1] for y in acc_samples[2]]) / float(len(acc_samples[2]))
        accy_neg = sum([y[1] for y in acc_samples[3]]) / float(len(acc_samples[3]))
        accz_pos = sum([z[2] for z in acc_samples[4]]) / float(len(acc_samples[4]))
        accz_neg = sum([z[2] for z in acc_samples[5]]) / float(len(acc_samples[5]))
        data[self.ACCX_SCALE] = str(2000.0 / (accx_pos - accx_neg))
        data[self.ACCY_SCALE] = str(2000.0 / (accy_pos - accy_neg))
        data[self.ACCZ_SCALE] = str(2000.0 / (accz_pos - accz_neg))

        data[self.ACCX_OFFSET] = str(int((accx_pos + accx_neg) / 2.0))
        data[self.ACCY_OFFSET] = str(int((accy_pos + accy_neg) / 2.0))
        data[self.ACCZ_OFFSET] = str(int((accz_pos + accz_neg) / 2.0))

        data[self.ACC_TIMESTAMP] = datetime.now().isoformat()

        self.write_calibration_data()
        self.update_data_display(self.calibration_data[self.current_imuid])
        self.calibration_state = self.CAL_NONE

    def calculate_mag_calibration(self, mag_samples):
        """Performs magnetometer calibration. Assumes mag_samples contains samples
        in order [+x, -x, +y, -y, +z, -z]. Calculates per-axis scale/offset values"""

        max_vals = [mag_samples[0][0], mag_samples[2][1], mag_samples[3][2]]
        min_vals = [mag_samples[1][0], mag_samples[3][1], mag_samples[5][2]]

        magbiases = [int((max_vals[i] + min_vals[i]) / 2.0) for i in range(3)]
        magscalings = [(max_vals[i] - min_vals[i]) / 2.0 for i in range(3)]
        avg_rads = sum(magscalings) / 3.0
        magscalings = [avg_rads / magscalings[i] for i in range(3)]

        data = self.calibration_data[self.current_imuid]

        data[self.MAGX_OFFSET] = str(int(magbiases[0]))
        data[self.MAGY_OFFSET] = str(int(magbiases[1]))
        data[self.MAGZ_OFFSET] = str(int(magbiases[2]))
        
        data[self.MAGX_SCALE] = str(magscalings[0])
        data[self.MAGY_SCALE] = str(magscalings[1])
        data[self.MAGZ_SCALE] = str(magscalings[2])

        data[self.MAG_TIMESTAMP] = datetime.now().isoformat()

        self.write_calibration_data()
        self.update_data_display(self.calibration_data[self.current_imuid])
        self.calibration_state = self.CAL_NONE

    def exit(self):
        # if a device is connected, disconnect it
        if self.sk8 is not None:
            self.sk8.disconnect()

        # if currently scanning, stop the scan
        if self.scan_state == self.SCAN_STATE_ACTIVE:
            self.dongle.end_scan()
        self.dongle.close()

        print('Writing calibration data')
        self.write_calibration_data()
        QtCore.QCoreApplication.exit()

    def write_calibration_data(self):
        with open(os.path.join(os.path.dirname(__file__), self.DEFAULT_CALIB_FILENAME), 'w') as f:
            self.calibration_data.write(f)

    def scan_result_found(self, result):
        """Callback triggered when a BLE device is found by the scanning process"""
        self.devicelist_model.appendRow(ScanDeviceItem(result))

    def cancel_scan(self):
        if self.scan_state == self.SCAN_STATE_ACTIVE:
            self.scan_state = self.SCAN_STATE_IDLE
            print('Scanning stopped')
            self.dongle.end_scan()
            self.scan_state = self.SCAN_STATE_IDLE
            self.btnRefresh.setEnabled(True)
            self.btnCancelScan.setEnabled(False)

    def refresh_devices(self):
        if self.scan_state == self.SCAN_STATE_IDLE:
            self.devicelist_model.clear()
            self.scan_state = self.SCAN_STATE_ACTIVE
            self.dongle.begin_scan(self.scan_result_found)
            self.btnRefresh.setEnabled(False)
            self.btnCancelScan.setEnabled(True)

    def device_selected(self, index):
        """Handler for selecting a device from the list in the UI"""
        device = self.devicelist_model.itemFromIndex(index)
        print(device.device.addr)
        self.btnConnect.setEnabled(True)

    def update_data_display(self, data):
        """Triggered when the selected device/IMU is changed. Updates the background
        colours of the text widgets in the UI to indicate which sensors have calibration
        data available (green) and which do not (red)"""
        acc_cal = self.ACC_TIMESTAMP in data
        mag_cal = self.MAG_TIMESTAMP in data
        gyro_cal = self.GYRO_TIMESTAMP in data

        uncal = 'QLineEdit {background-color: #cc3333;};'
        cal = 'QLineEdit {background-color: #33cc33;};'

        if acc_cal:
            self.dataAccX.setStyleSheet(cal)
            self.dataAccY.setStyleSheet(cal)
            self.dataAccZ.setStyleSheet(cal)
        else:
            self.dataAccX.setStyleSheet(uncal)
            self.dataAccY.setStyleSheet(uncal)
            self.dataAccZ.setStyleSheet(uncal)

        if gyro_cal:
            self.dataGyroX.setStyleSheet(cal)
            self.dataGyroY.setStyleSheet(cal)
            self.dataGyroZ.setStyleSheet(cal)
        else:
            self.dataGyroX.setStyleSheet(uncal)
            self.dataGyroY.setStyleSheet(uncal)
            self.dataGyroZ.setStyleSheet(uncal)

        if mag_cal:
            self.dataMagX.setStyleSheet(cal)
            self.dataMagY.setStyleSheet(cal)
            self.dataMagZ.setStyleSheet(cal)
        else:
            self.dataMagX.setStyleSheet(uncal)
            self.dataMagY.setStyleSheet(uncal)
            self.dataMagZ.setStyleSheet(uncal)

    def connect_device(self):
        if self.sk8 is not None:
            # disconnect
            self.data_timer.stop()
            self.battery_timer.stop()
            self.sk8.disconnect()
            self.sk8 = None
            print('Disconnected')
            self.btnConnect.setText('Connect device')
            self.statusbar.showMessage('Disconnected')
            self.btnRefresh.setEnabled(True)
            self.spinIMU.setEnabled(False)
            self.btnAcc.setEnabled(False)
            self.btnGyro.setEnabled(False)
            self.btnMag.setEnabled(False)
            return

        # stop any scan still in progress
        self.cancel_scan()

        # retrieve the selected device object and try to connect
        selected = self.lstDevices.selectedIndexes()
        if len(selected) == 0:
            print('No device selected')
            return

        dev = self.devicelist_model.itemFromIndex(selected[0])
        if not self.dongle.connect([dev.device]):
            print('Failed to connect to device')
            return

        # configure the UI state for the new device
        self.sk8 = self.dongle.get_device(dev.device.addr)
        self.btnConnect.setText('Disconnect {}'.format(dev.device.name))
        self.statusbar.showMessage('Connected to {}'.format(dev.device.name))
        self.sk8.enable_imu_streaming([0, 1, 2, 3, 4])
        self.data_timer.start()
        self.update_battery()
        self.battery_timer.start()
        self.btnRefresh.setEnabled(False)
        self.spinIMU.setEnabled(True)
        self.btnAcc.setEnabled(True)
        self.btnGyro.setEnabled(True)
        self.btnMag.setEnabled(True)

        # load existing calibration, if any
        devname = self.sk8.get_device_name()
        imu = self.spinIMU.value()
        self.current_imuid = '{}_IMU{}'.format(devname, imu)
        if self.current_imuid in self.calibration_data:
            print('Found existing calibration data for {}'.format(self.current_imuid))
        else:
            print('No calibration data for {}'.format(devname))
            for i in range(5):
                data = {}
                self.calibration_data[self.current_imuid] = data

        self.update_data_display(self.calibration_data[self.current_imuid])

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit('Usage: python sk8_calibration_gui.py <serial port>')

    app = QApplication(sys.argv)
    window = SK8Calibration(sys.argv[1])
    window.show()
    sys.exit(app.exec_())
