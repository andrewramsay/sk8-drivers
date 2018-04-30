"""Core classes for the pysk8 package.

This module contains the core classes for interacting with SK8 Bluetooth Low
Energy sensor packs. Currently supported is limited to Windows/OSX/Linux desktop
platforms, and requires a Silicon Labs BLED112 USB dongle. A link to a webpage 
with more information about this dongle can be found 
`here <https://www.silabs.com/products/wireless/bluetooth/bluetooth-low-energy-modules/bled112-bluetooth-smart-dongle>`_.

"""

import logging
import struct 
import time 
import os
from configparser import ConfigParser
import threading
from queue import Queue

import serial
import serial.tools.list_ports

from bgapi.api import BlueGigaAPI
from bgapi.module import BlueGigaCallbacks
from bgapi.cmd_def import gap_discoverable_mode, gap_connectable_mode, RESULT_CODE

from pysk8.util import pp_hex, fmt_addr, fmt_addr_raw
from pysk8.constants import *
from pysk8.imu import IMUData
from pysk8.extana import ExtAnaData
from pysk8.discovery import Service

# bgapi is pretty verbose and usually won't need to see most of what it produces
bglogger = logging.getLogger('bgapi')
bglogger.setLevel(logging.WARN)

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARN)

class ScanResult(object):
    """An individual result from a BLE scan process for a particular device

    Attributes:
        addr (str): Device hardware address in xx:xx:xx:xx:xx:xx format.
        raw_addr (bytearray): Device hardware address as raw bytes.
        name (str): Device name (if available) as ASCII text.
        rssi (float): Latest RSSI from the scan result for the device, if any.
    """

    def __init__(self, addr, raw_addr, name=None, rssi=0):
        """Initialise a new ScanResult.

        Args:
            addr (str): Device hardware address in xx:xx:xx:xx:xx:xx format.
            raw_addr (bytearray): Device hardware address as raw bytes.
            name (str): Device name (if available) as ASCII text.
            rssi (float): Latest RSSI from the scan result for the device, if any.
        """
        self.addr = addr
        self.raw_addr = raw_addr
        self.name = name
        self.rssi = rssi
        self.age = time.time()

    def update(self, name, rssi):
        """Update the device name and/or RSSI.

        During an ongoing scan, multiple records from the same device can be 
        received during the scan. Each time that happens this method is 
        called to update the :attr:`name` and/or :attr:`rssi` attributes.
        """
        self.name = name
        self.rssi = rssi
        self.age = time.time()

    def age(self):
        """Returns the "age" of the ScanResult.
        
        This method simply returns the time (in seconds) since this ScanResult
        was created or updated.
        """
        return time.time() - self.age

    def __eq__(self, v):
        """
        Equality test matches parameter against either device address or name
        """
        return v == self.addr or v == self.name

    def __repr__(self):
        return 'addr={},name={},rssi={},age={}'.format(self.addr, self.name, self.rssi, self.age)

class ScanResults(object):
    """Collection of results from a BLE device scan.

    Provides methods to manage and query a set of results from an ongoing or
    completed BLE scan.
    """

    def __init__(self):
        self._devices = {}

    def clear(self):
        """Clear all device information."""
        self._devices = {}

    def update(self, addr, raw_addr, name=None, rssi=None):
        """Updates the collection of results with a newly received scan response.

        Args:
            addr (str): Device hardware address in xx:xx:xx:xx:xx:xx format.
            raw_addr (bytearray): Device hardware address as raw bytes.
            name (str): Device name (if available) as ASCII text. May be None.
            rssi (float): Latest RSSI from the scan result for the device. May be 0.

        Returns:
            True if an existing device was updated, False if a new entry was created.
        """
        if addr in self._devices:
            # logger.debug('UPDATE scan result: {} / {}'.format(addr, name))
            self._devices[addr].update(name, rssi)
            return False
        else:
            self._devices[addr] = ScanResult(addr, raw_addr, name, rssi)
            logger.debug('Scan result: {} / {}'.format(addr, name))
            return True

    def get(self):
        """Returns the raw dict containing the scan result data.

        Returns:
            A standard Python dictionary. Keys are device addresses in 
            xx:xx:xx:xx:xx:xx format, values are :class:`ScanResult` objects.
        """
        return self._devices

    def get_device(self, addr_or_name):
        """Retrieve a device with a given address or name from the results.
        
        Args:
            addr_or_name (str): a string containing either a BLE address in xx:xx:xx:xx:xx:xx
                format, or a plain device name. The supplied value is checked as an address
                first and if that fails to produce a result, it is matched against each
                named device in the collection. 

        Returns:
            The first matching :class:`ScanResult` instance, or None. 
        """
        if addr_or_name in self._devices:
            return self._devices[addr_or_name]

        for v in self._devices.values():
            if v == addr_or_name:
                return v

        return None

    def found(self, ids):
        """ Utility method to check if a set of devices are contained in the result set.
        
        Args:
            ids (list): a list of device addresses in xx:xx:xx:xx:xx:xx format.

        Returns:
            True if all supplied devices exist in the result set, False otherwise.
        """
        for id in ids:
            if id not in self:
                return False

        return True

    def __contains__(self, addr_or_name):
        """ Test if the device identified by <addr_or_name> appears in the result set

        Args:
            addr_or_name (str): a string containing either a BLE address in xx:xx:xx:xx:xx:xx
                format, or a plain device name. The supplied value is checked as an address
                first and if that fails to produce a result, it is matched against each
                named device in the collection. 

        Returns:
            True if the parameter matched any device, False otherwise.
        """
        if addr_or_name in self._devices:
            return True

        for v in self._devices.values():
            if v == addr_or_name:
                return True

        return False

    def __len__(self):
        return len(self._devices)

class SK8(object):
    """Represents a single, currently connected SK8 device.

    **NOTE**: normally you should *not* create instances of this class manually. 
    Instead, use the methods of the :class:`Dongle` object to create connections 
    and retrieve the corresponding :class:`SK8` objects. 

    Args:
        dongle: reference to the host :class:`Dongle` instance.
        conn_handle (int): BLED112 connection handle.
        devinfo: ScanResult for this device, containing address information.
        calibration (bool): indicates if calibration data should be loaded (if available)
    """

    def __init__(self, dongle, conn_handle, devinfo, calibration=True):
        self.dongle = dongle
        self.addr = devinfo.addr
        self.raw_addr = devinfo.raw_addr
        self.name = devinfo.name
        self.firmware_version = 'unknown'
        self.conn_handle = conn_handle
        self.imus = [IMUData(x) for x in range(MAX_IMUS)]
        self.extana_data = ExtAnaData()
        self.enabled_imus = []
        self.streaming = False
        self.packets = 0
        self.services = {}
        self.imu_callback = None
        self.imu_callback_data = None
        self.extana_callback = None
        self.extana_callback_data = None
        self.led_state = None
        self.hardware = -1
        self.uuid_chars = {}
        self.uuid_cccds = {}
        if calibration:
            logger.debug('Attempting to load calibration for addr={}'.format(self.addr))
            self.load_calibration()

    def __eq__(self, v):
        """Devices considered equal if address or name match"""
        return self.addr == v or self.name == v

    def set_calibration(self, enabled, imus):
        """Set calibration state for attached IMUs.

        Args:
            enabled (bool): True to apply calibration to IMU data (if available). 
            False to output uncalibrated data.
            imus (list): indicates which IMUs the calibration state should be set on. 
            Empty list or [0, 1, 2, 3, 4] will apply to all IMUs, [0, 1] only to 
            first 2 IMUs, etc. 
        """
        if len(imus) == 0:
            imus = list(range(MAX_IMUS))

        for i in imus:
            if i < 0 or i >= MAX_IMUS:
                logger.warn('Invalid IMU index {} in set_calibration'.format(i))
                continue
            self.imus[i]._use_calibration = enabled

    def get_calibration(self):
        """Get calibration state for attached IMUs.

        Returns:
            list. A 5-element list of bools indicating if calibrated output is 
            currently enabled or disabled on the IMU with the corresponding index.
            Note that if calibration is enabled but no calibration file has been
            loaded, uncalibrated data will still be output!
        """
        return [x._use_calibration for x in self.imus]

    def load_calibration(self, calibration_file=None):
        """Load calibration data for IMU(s) connected to this SK8.

        This method attempts to load a set of calibration data from a .ini file 
        produced by the sk8_calibration_gui application (TODO link!).

        By default, it will look for a file name "sk8calib.ini" in the current working
        directory. This can be overridden using the `calibration_file` parameter.

        Args:
            calibration_file (str): Path to a user-specified calibration file (ini format).

        Returns:
            True if any calibration data was loaded, False if none was. Note that True will be
            returned even if for example only 1 IMU had any calibration data available.
        """
        logger.debug('Loading calibration for {}'.format(self.addr))
        calibration_data = ConfigParser()
        path = calibration_file or os.path.join(os.getcwd(), 'sk8calib.ini')
        logger.debug('Attempting to load calibration from {}'.format(path))
        calibration_data.read(path)
        success = False
        for i in range(MAX_IMUS):
            s = '{}_IMU{}'.format(self.name, i)
            if s in calibration_data.sections():
                logger.debug('Calibration data for device {} was detected, extracting...'.format(s))
                success = success or self.imus[i]._load_calibration(calibration_data[s])

        return success

    def disconnect(self):
        """Disconnect the dongle from this SK8.

        Simply closes the active BLE connection to the device represented by the current instance.

        Returns:
            bool. True if connection was closed, False if not (e.g. if already closed).
        """
        result = False
        logger.debug('SK8.disconnect({})'.format(self.conn_handle))
        if self.conn_handle >= 0:
            logger.debug('Calling dongle disconnect')
            result = self.dongle._disconnect(self.conn_handle)
            self.conn_handle = -1
            self.packets = 0

        return result

    def set_extana_callback(self, callback, data=None):
        """Register a callback for incoming data packets from the SK8-ExtAna board.

        This method allows you to pass in a callable which will be called on 
        receipt of each packet sent from the SK8-ExtAna board. Set to `None` to
        disable it again.

        Args:
            callback: a callable with the following signature:
                        (ana1, ana2, temp, seq, timestamp, data)
                      where:
                        ana1, ana2 = current values of the two analogue inputs
                        temp = temperature sensor reading
                        seq = packet sequence number (int, 0-255)
                        timestamp = value of time.time() when packet received
                        data = value of `data` parameter passed to this method
            data: an optional arbitrary object that will be passed as a 
                parameter to the callback
        """
        self.extana_callback = callback
        self.extana_callback_data = data

    def enable_extana_streaming(self, include_imu=False, enabled_sensors=SENSOR_ALL):
        """Configures and enables sensor data streaming from the SK8-ExtAna device.

        By default this will cause the SK8 to only stream data from the analog 
        sensors on the SK8-ExtAna, but if `include_imu` is set to True, it will 
        also send data from the internal IMU in the SK8. 

        NOTE: only one streaming mode can be active at any time, so e.g. if you 
        want to stream IMU data normally, you must disable SK8-ExtAna streaming first. 

        Args:
            include_imu (bool): If False, only SK8-ExtAna packets will be streamed.
                If True, the device will also stream data from the SK8's internal IMU. 
            enabled_sensors (int): If `include_imu` is True, this can be used to 
                select which IMU sensors will be active. 

        Returns:
            bool. True if successful, False if an error occurred.
        """
        if not self.dongle._enable_extana_streaming(self, include_imu, enabled_sensors):
            logger.warn('Failed to enable SK8-ExtAna streaming!')
            return False

        # have to add IMU #0 to enabled_imus if include_imu is True
        if include_imu:
            self.enabled_imus = [0]

        return True

    def disable_extana_streaming(self):
        """Disable SK8-ExtAna streaming for this device.

        Returns:
            True on success, False if an error occurred.
        """
        self.enabled_imus = []
        return self.dongle._disable_extana_streaming(self)

    def get_extana_led(self, cached=True):
        """Returns the current (R, G, B) colour of the SK8-ExtAna LED.

        Args:
            cached (bool): if True, returns the locally cached state of the LED (based
                on the last call to :meth:`set_extana_led`). Otherwise query the device
                for the current state.

        Returns:
            a 3-tuple (r, g, b) (all unsigned integers) in the range 0-255, or `None` on error.
        """
        if cached:
            return self.led_state

        extana_led = self.get_characteristic_handle_from_uuid(UUID_EXTANA_LED)
        if extana_led is None:
            logger.warn('Failed to find handle for ExtAna LED')
            return None

        rgb = self.dongle._read_attribute(self.conn_handle, extana_led, israw=True)
        if rgb is None:
            return rgb

        return list(map(lambda x: int(x * (LED_MAX / INT_LED_MAX)), struct.unpack('<HHH', rgb)))
        
    def set_extana_led(self, r, g, b, check_state=True):
        """Update the colour of the RGB LED on the SK8-ExtAna board.

        Args:
            r (int): red channel, 0-255
            g (int): green channel, 0-255
            b (int): blue channel, 0-255
            check_state (bool): if True (default) and the locally cached LED state matches
                the given (r, g, b) triplet, pysk8 will NOT send any LED update command to
                the SK8. If you want to force the command to be sent even if the local state
                matches the new colour, set this to False. 

        Returns:
            True on success, False if an error occurred.
        """

        r, g, b = map(int, [r, g, b])

        if min([r, g, b]) < LED_MIN or max([r, g, b]) > LED_MAX:
            logger.warn('RGB channel values must be {}-{}'.format(LED_MIN, LED_MAX))
            return False

        if check_state and (r, g, b) == self.led_state:
            return True

        # internally range is 0-3000
        ir, ig, ib = map(lambda x: int(x * (INT_LED_MAX / LED_MAX)), [r, g, b])
        val = struct.pack('<HHH', ir, ig, ib)

        extana_led = self.get_characteristic_handle_from_uuid(UUID_EXTANA_LED)
        if extana_led is None:
            logger.warn('Failed to find handle for ExtAna LED')
            return None
            
        if not self.dongle._write_attribute(self.conn_handle, extana_led, val):
            return False

        # update cached LED state if successful
        self.led_state = (r, g, b)
        return True

    def set_imu_callback(self, callback, data=None):
        """Register a callback for incoming IMU data packets.
        
        This method allows you to pass in a callbable which will be called on
        receipt of each IMU data packet sent by this SK8 device. Set to `None`
        to disable it again.

        Args:
            callback: a callable with the following signature:
                        (acc, gyro, mag, imu_index, seq, timestamp, data)
                      where:
                        acc, gyro, mag = sensor data ([x,y,z] in each case)
                        imu_index = originating IMU number (int, 0-4)
                        seq = packet sequence number (int, 0-255)
                        timestamp = value of time.time() when packet received
                        data = value of `data` parameter passed to this method
            data: an optional arbitrary object that will be passed as a 
                parameter to the callback
        """
        self.imu_callback = callback
        self.imu_callback_data = data

    def enable_imu_streaming(self, enabled_imus, enabled_sensors=SENSOR_ALL):
        """Configures and enables IMU sensor data streaming.

        NOTE: only one streaming mode can be active at any time, so e.g. if you 
        want to stream IMU data, you must disable SK8-ExtAna streaming first.

        Args:
            enabled_imus (list): a list of distinct ints in the range `0`-`4`
                inclusive identifying the IMU. `0` is the SK8 itself, and 
                `1`-`4` are the subsidiary IMUs on the USB chain, starting
                from the end closest to the SK8. 
            enabled_sensors (int): to save battery, you can choose to enable some 
                or all of the sensors on each enabled IMU. By default, the
                accelerometer, magnetometer, and gyroscope are all enabled. Pass
                a bitwise OR of one or more of :const:`SENSOR_ACC`, 
                :const:`SENSOR_MAG`, and :const:`SENSOR_GYRO` to gain finer
                control over the active sensors.

        Returns:
            bool. True if successful, False if an error occurred.
        """
        imus_enabled = 0
        for imu in enabled_imus:
            imus_enabled |= (1 << imu)

        if enabled_sensors == 0:
            logger.warn('Not enabling IMUs, no sensors enabled!')
            return False

        if not self.dongle._enable_imu_streaming(self, imus_enabled, enabled_sensors):
            logger.warn('Failed to enable IMU streaming (imus_enabled={}, enabled_sensors={}'.format(imus_enabled, enabled_sensors))
            return False

        self.enabled_imus = enabled_imus
        return True

    def get_enabled_imus(self):
        """Returns the set of currently enabled IMUs.

        This method returns a copy of the list of enabled IMUs as most recently
        passed to the :meth:`enable_imu_streaming` method. 

        Returns:
            The list will contain ints from 0-4, up to a maximum of 5 entries, and may be empty if no IMUs are enabled. 
        """
        return self.enabled_imus

    def disable_imu_streaming(self):
        """Disable IMU streaming for this device.

        Returns:
            True on success, False if an error occurred.
        """
        self.enabled_imus = []
        # reset IMU data state
        for imu in self.imus:
            imu.reset()
        return self.dongle._disable_imu_streaming(self)

    def get_battery_level(self):
        """Reads the battery level descriptor on the device.

        Returns:
            int. If successful this will be a positive value representing the current 
            battery level as a percentage. On error, -1 is returned. 
        """

        battery_level = self.get_characteristic_handle_from_uuid(UUID_BATTERY_LEVEL)
        if battery_level is None:
            logger.warn('Failed to find handle for battery level')
            return None

        level = self.dongle._read_attribute(self.conn_handle, battery_level)
        if level is None:
            return -1
        return ord(level)

    def get_device_name(self, cached=True):
        """Returns the SK8 device BLE name.

        Args:
            cached (bool): if True, returns the locally cached copy of the name. If this is
                set to False, or the name is not cached, it will read from the device instead.

        Returns:
            str. The current device name. May be `None` if an error occurs.
        """
        if cached and self.name is not None:
            return self.name

        device_name = self.get_characteristic_handle_from_uuid(UUID_DEVICE_NAME)
        if device_name is None:
            logger.warn('Failed to find handle for device name')
            return None

        self.name = self.dongle._read_attribute(self.conn_handle, device_name)
        return self.name

    def set_device_name(self, new_name):
        """Sets a new BLE device name for this SK8.

        Args:
            new_name (str): the new device name as an ASCII string.

        Returns:
            True if the name was updated successfully, False otherwise.
        """

        device_name = self.get_characteristic_handle_from_uuid(UUID_DEVICE_NAME)
        if device_name is None:
            logger.warn('Failed to find handle for device name')
            return None
        
        if self.dongle._write_attribute(self.conn_handle, device_name, new_name.encode('ascii')):
            self.name = new_name
            return True

        return False

    def get_received_packets(self):
        """Returns number of received data packets.

        Returns:
            int. Number of sensor data packets received either since the connection
            was established, or since :meth:`reset_received_packets` was called.
        """
        return self.packets

    def reset_received_packets(self):
        """Reset counter tracking received data packets to zero"""
        self.packets = 0

    def get_firmware_version(self, cached=True):
        """Returns the SK8 device firmware version.

        Args:
            cached (bool): if True, returns the locally cached copy of the firmware version.
                If this is set to False, or the version is not cached, it will read from
                the device instead. 

        Returns:
            str. The current firmware version string. May be `None` if an error occurs.
        """
        if cached and self.firmware_version != 'unknown':
            return self.firmware_version

        firmware_version = self.get_characteristic_handle_from_uuid(UUID_FIRMWARE_REVISION)
        if firmware_version is None:
            logger.warn('Failed to find handle for device name')
            return None

        self.firmware_version = self.dongle._read_attribute(self.conn_handle, firmware_version)
        return self.firmware_version

    def get_imu(self, imu_number):
        """Returns a :class:`pysk8.imu.IMUData` object representing one of the attached IMUs.

        Args:
            imu_number (int): a value from 0-4 inclusive identifying the IMU. `0` is the
                SK8 itself, and `1`-`4` are the subsidiary IMUs on the USB chain, starting
                from the end closest to the SK8. 

        Returns:
            :class:`pysk8.imu.IMUData` object, or `None` if an invalid index is supplied.
        """
        if imu_number < 0 or imu_number >= MAX_IMUS:
            return None
        return self.imus[imu_number]

    def get_extana(self):
        """Returns a :class:`pysk8.extana.ExtAnaData` object representing an attach SK8-ExtAna board.

        Returns:
            :class:`pysk8.extana.ExtAnaData` object.
        """
        return self.extana_data

    def _update_sensors(self, acc, gyro, mag, imu, seq, timestamp):
        self.imus[imu]._update(acc, gyro, mag, seq, timestamp)
        # call the registered IMU callback if any
        if self.imu_callback is not None:
            self.dongle._cbthread_q.put((self.imu_callback, (acc, gyro, mag, imu, seq, timestamp, self.imu_callback_data)))

    def _update_extana(self, ch1, ch2, temp, seq, timestamp):
        self.extana_data._update(ch1, ch2, temp, seq, timestamp)
        # call the registered ExtAna callback if any
        if self.extana_callback is not None:
            self.dongle._cbthread_q.put((self.extana_callback, (ch1, ch2, temp, seq, timestamp, self.extana_callback_data)))

    def _check_hardware(self):
        hardware_state = self.get_characteristic_handle_from_uuid(UUID_HARDWARE_STATE)
        hardware_state_tmp = self.get_characteristic_handle_from_uuid(UUID_HARDWARE_STATE_TMP)
        if hardware_state is None and hardware_state_tmp is None:
            logger.warn('Failed to find handle for hardware state')
            return -1

        if hardware_state is not None:
            self.hardware = ord(self.dongle._read_attribute(self.conn_handle, hardware_state))
        else:
            self.hardware = ord(self.dongle._read_attribute(self.conn_handle, hardware_state_tmp))
        return self.hardware

    def has_extana(self, cached=True):
        """Can be used to check if an SK8-ExtAna device is currently connected.
            NOTE: do not attempt to call while data streaming is active!

        Args:
            cached (bool): if True, use the cached value of the connected hardware
                state rather than querying the device. Set to False to force a query.

        Returns:
            bool. True if the SK8 currently has an SK8-ExtAna device attached, False otherwise.
        """
        if cached and self.hardware != -1:
            return True if (self.hardware & EXT_HW_EXTANA) else False

        result = self._check_hardware()
        return True if (result & EXT_HW_EXTANA) else False

    def has_imus(self, cached=True):
        """Can be used to check if an external IMU chain is currently connected.
            NOTE: do not attempt to call while data streaming is active!

        Args:
            cached (bool): if True, use the cached value of the connected hardware
                state rather than querying the device. Set to False to force a query.

        Returns:
            bool. True if the SK8 currently has an IMU chain attached, False otherwise.
        """
        if cached and self.hardware != -1:
            return True if (self.hardware & EXT_HW_IMUS) else False

        result = self._check_hardware()
        return True if (result & EXT_HW_IMUS != 0) else False

    def pp_services(self):
        """Display (somewhat) pretty-printed dump of service, charactertistic 
            and descriptor information for this device. 
            
        Returns:
            Nothing.
        """
        for s in self.services.values():
            s.pp()

    def _discover_services(self):
        """Starts a service discovery operation on the SK8, to build up 
        information on the services, characteristics and descriptors defined in
        its GATT database.
        
        Returns:
            list. A list of :class:`Service` objects.

        """
        return self.dongle._discover_services(self)

    def get_characteristic_handle_from_uuid(self, uuid):
        """Given a characteristic UUID, return its handle.
    
        Args:
            uuid (str): a string containing the hex-encoded UUID

        Returns:
            None if an error occurs, otherwise an integer handle. 
        """
        ch = self.get_characteristic_from_uuid(uuid)
        return None if ch is None else ch.char_handle

    def get_characteristic_from_uuid(self, uuid):
        """Given a characteristic UUID, return a :class:`Characteristic` object
        containing information about that characteristic

        Args:
            uuid (str): a string containing the hex-encoded UUID

        Returns:
            None if an error occurs, otherwise a :class:`Characteristic` object
        """

        if uuid in self.uuid_chars:
            logger.debug('Returning cached info for char: {}'.format(uuid))
            return self.uuid_chars[uuid]

        for service in self.services.values():
            char = service.get_characteristic_by_uuid(uuid)
            if char is not None:
                self.uuid_chars[uuid] = char
                logger.debug('Found char for UUID: {}'.format(uuid))
                return char

        logger.warn('Failed to find char for UUID: {}'.format(uuid))
        return None

    def get_ccc_handle_from_uuid(self, uuid):
        """Utility function to retrieve the client characteristic configuration
        descriptor handle for a given characteristic.
        
        Args:
            uuid (str): a string containing the hex-encoded UUID
            
        Returns:
            None if an error occurs, otherwise an integer handle.
        """

        if uuid in self.uuid_cccds:
            return self.uuid_cccds[uuid].handle
        
        char = self.get_characteristic_from_uuid(uuid)
        if char is None:
            return None

        ccc = char.get_descriptor_by_uuid(UUID_GATT_CCC)
        if ccc is not None:
            self.uuid_cccds[uuid] = ccc
        return None if ccc is None else ccc.handle

    def _add_characteristic(self, atthandle, value):
        for s in self.services.values():
            if s.start_handle <= atthandle and s.end_handle >= atthandle:
                logger.debug('add char 0x{:02X} to service {}'.format(atthandle, s.uuid))
                return s.add_characteristic(atthandle, value)

    def _add_service(self, start_handle, end_handle, uuid):
        self.services[pp_hex(uuid)] = Service(start_handle, end_handle, uuid)
        return self.services[pp_hex(uuid)]

    def get_service(self, uuid):
        """Lookup information about a given GATT service.

        Args:
            uuid (str): a string containing the hex-encoded service UUID

        Returns:
            None if an error occurs, otherwise a :class:`Service` object.
        """
        if uuid in self.services:
            return self.services[uuid]

        if pp_hex(uuid) in self.services:
            return self.services[pp_hex(uuid)]

        return None

    def get_service_for_handle(self, handle):
        """Given a characteristic handle, return the :class:`Service` object that
        the handle belongs to. 

        Args:
            handle (int): the characteristic handle

        Returns:
            None if no service matches the given handle, otherwise a :class:`Service` object.
        """
        for s in self.services.values():
            if s.start_handle <= handle and s.end_handle >= handle:
                return s

        return None

class Dongle(BlueGigaCallbacks):
    """Represents a physical BLED112 dongle.
    
    Provides various methods to scan for and connect to one or more SK8 devices
    """

    BAUDRATE                = 250600    #: serial port baud rate for the BLED112
    PORT_RETRIES            = 3         #: number of attempts to make at opening the serial port
    DEF_SCAN_INTERVAL       = 0x4b      #: default BLE scan interval, units of 625us
    DEF_SCAN_WINDOW         = 0x4b      #: default BLE scan window, units of 625us

    _STATE_IDLE              = 0 
    _STATE_RESET             = 1
    _STATE_CONFIGURE_SCAN    = 2
    _STATE_SCANNING          = 3
    _STATE_CONNECTING        = 4
    _STATE_CONNECTED         = 5
    _STATE_DISCOVER_SERVICES = 6
    _STATE_DISCOVER_CHARS    = 7
    _STATE_DISCOVER_DESCS    = 8
    _STATE_DISCONNECTING     = 9
    _STATE_DISCONNECTED      = 10
    _STATE_BEGIN_STREAMING   = 11
    _STATE_STREAMING         = 12
    _STATE_CONFIGURE_IMUS    = 13
    _STATE_READ_GATT         = 14
    _STATE_WRITE_GATT        = 15
    _STATE_GAP_END           = 16
    _STATE_DONGLE_COMMAND    = 17
    _STATE_CONFIGURE_ANA     = 18

    def __init__(self):
        """Create a :class:`Dongle` instance (without connecting to the physical device)"""
        self.scan_responses = ScanResults()
        self.state = Dongle._STATE_RESET
        self.supported_connections = -1
        self._disconnect_handler = None
        self.ignore_nameless = True
        self.api = None
        self._clear()

    def init(self, address, hard_reset=False):
        """Open the serial connection to a dongle at the supplied address.

        Args:
            address (str): the serial port address of the BLED112 dongle, e.g. 'COM5'
            hard_reset (bool): not currently used

        Returns:
            True if a connection with the dongle was established, False otherwise.
        """
        self.address = address

        if hard_reset:
            # TODO (needs more work to be usable)
            # if not Dongle._hard_reset(address):
            #     return False
            # time.sleep(2.0)
            pass

        # TODO timeout not working if opened on valid, non Bluegiga port
        for i in range(Dongle.PORT_RETRIES):
            try:
                logger.debug('Setting up BGAPI, attempt {}/{}'.format(i + 1, Dongle.PORT_RETRIES))
                self.api = BlueGigaAPI(port=self.address, callbacks=self, baud=Dongle.BAUDRATE, timeout=DEF_TIMEOUT)
                self.api.start_daemon()
                break
            except serial.serialutil.SerialException as e:
                logger.debug('Failed to init BlueGigaAPI: {}, attempt {}/{}'.format(e, i + 1, Dongle.PORT_RETRIES))
                time.sleep(0.1)

        if self.api is None:
            return False

        time.sleep(0.5) # TODO
        self.get_supported_connections()
        logger.info('Dongle supports {} connections'.format(self.supported_connections))
        self.conn_state = {x: self._STATE_IDLE for x in range(self.supported_connections)}
        self.reset()

        self._cbthread = threading.Thread(target=self._cbthreadfunc)
        self._cbthread.setDaemon(True)
        self._cbthread_q = Queue()
        self._cbthread.start()
        return True

    def _cbthreadfunc(self):
        while self._cbthread_q is not None:
            cbfunc, cbparams = self._cbthread_q.get()
            cbfunc(*cbparams)

    @staticmethod
    def find_dongle_port():
        """Convenience method which attempts to find the port where a BLED112 dongle is connected.

        This relies on the `pyserial.tools.list_ports.grep method 
        <https://pyserial.readthedocs.io/en/latest/tools.html#serial.tools.list_ports.grep>`_, 
        and simply searches for a port containing the string "Bluegiga" in its description. 
        (This probably only works on Windows at the moment (TODO)).

        Returns:
            A string containing the detected port address, or `None` if no matching port was found.
        """
        logger.debug('Attempting to find Bluegiga dongle...')
        # TODO this will probably only work on Windows at the moment
        ports = list(serial.tools.list_ports.grep('Bluegiga'))
        if len(ports) == 0:
            logger.debug('No Bluegiga-named serial ports discovered')
            return None

        # just return the first port even if multiple dongles
        logger.debug('Found "Bluegiga" serial port at {}'.format(ports[0].device))
        return ports[0].device

    def reset(self):
        """Attempts to reset the dongle to a known state.

        When called, this method will reset the internal state of the object, and
        disconnect any active connections. 
        """
        logger.debug('resetting dongle state')

        self._clear()

        if self.api is not None:
            self._set_state(Dongle._STATE_RESET)
            self.api.ble_cmd_gap_set_mode(gap_discoverable_mode['gap_non_discoverable'], gap_connectable_mode['gap_non_connectable'])
            self._wait_for_state(self._STATE_RESET)

            for i in range(self.supported_connections):
                self._set_conn_state(i, self._STATE_DISCONNECTING)
                self.api.ble_cmd_connection_disconnect(i)	
                self._wait_for_conn_state(i, self._STATE_DISCONNECTING)

        logger.debug('reset completed')

    def close(self):
        """Closes the connection to the dongle.
        
        Calls :meth:`reset` and then closes the serial port connection to the dongle."""
        logger.debug('closing dongle, {} active connections'.format(len(self.conn_handles)))
        self.reset()
        if self.api is not None:
            self.api.stop_daemon()
            self.api = None

    def _discover_services(self, sk8):
        """ TODO """

        ts = time.time()

        # start by discovering primary service UUIDs
        # params to ble_cmd_attclient_read_by_group_type are:
        #   conn_handle, start handle, end handle, UUID identifier to match (little endian)
        self._set_conn_state(sk8.conn_handle, self._STATE_DISCOVER_SERVICES)
        self.api.ble_cmd_attclient_read_by_group_type(sk8.conn_handle, 0x0001, 0xFFFF, RAW_UUID_GATT_PRIMARY_SERVICE)
        self._wait_for_conn_state(sk8.conn_handle, self._STATE_DISCOVER_SERVICES)
        logger.debug('Service discovery took: {:.3f}s'.format(time.time() - ts))

        logger.debug('Found {} primary services'.format(sk8.services))

        # now discover characteristics and descriptors within each service
        tc = time.time()
        for service in sk8.services.values():
            self._set_conn_state(sk8.conn_handle, self._STATE_DISCOVER_CHARS)
            self.api.ble_cmd_attclient_read_by_type(sk8.conn_handle, service.start_handle, service.end_handle, RAW_UUID_GATT_CHAR_DECL)
            self._wait_for_conn_state(sk8.conn_handle, self._STATE_DISCOVER_CHARS)

            self._set_conn_state(sk8.conn_handle, self._STATE_DISCOVER_DESCS)
            self.api.ble_cmd_attclient_find_information(sk8.conn_handle, service.start_handle, service.end_handle)
            self._wait_for_conn_state(sk8.conn_handle, self._STATE_DISCOVER_DESCS)

        logger.debug('Characteristic discovery took: {:.3f}s'.format(time.time() - tc))

        return True


    def get_connection_interval(self):
        """Returns the current BLE connection interval in ms"""
        return self._conn_interval

    def get_supervision_timeout(self):
        """Returns the current BLE supervision timeout in ms"""
        return self._supervision_timeout

    def get_slave_latency(self):
        """Returns the current BLE slave latency in connection intervals"""
        return self._slave_latency

    def scan_and_connect(self, devnames, timeout=DEF_TIMEOUT, calibration=True):
        """Scan for and then connect to a set of one or more SK8s.

        This method is intended to be a simple way to combine the steps of 
        running a BLE scan, checking the results and connecting to one or more
        devices. When called, a scan is started for a period equal to `timeout`,
        and a list of devices is collected. If at any point during the scan all of
        the supplied devices are detected, the scan will be ended immediately. 
        
        After the scan has completed, the method will only proceed to creating
        connections if the scan results contain all the specified devices. 

        Args:
            devnames (list): a list of device names (1 or more)
            timeout (float): a time period in seconds to run the scanning process 
                (will be terminated early if all devices in `devnames` are discovered)

        Returns:
            Returns the same results as :meth:`connect`.
        """
        responses = self.scan_devices(devnames, timeout)

        for dev in devnames:
            if dev not in responses:
                logger.error('Failed to find device {} during scan'.format(dev))
                return (False, [])

        return self.connect([responses.get_device(dev) for dev in devnames], calibration)

    # scan parameters are scan interval, scan window and active scanning
    # scan interval is the amount of time the dongle will spend on a  
    #   a single advertising channel frequency (spec defines 3 of them)
    #   (units of 625us)
    # scan window is the amount of time the dongle will actually listen
    #   for packets on the current frequency, again in units of 625us. must
    #   be =< scan interval
    # active scanning = 1 (active), 0 (passive). active scanning means that
    #   the dongle will respond to advertisement packets by sending a reply
    #   requesting a scan response packet (in the case of the SK8 this will
    #   contain the device name so is useful to have)

    # asynchronous scanning
    def begin_scan(self, callback=None, interval=DEF_SCAN_INTERVAL, window=DEF_SCAN_WINDOW):
        """Begins a BLE scan and returns immediately.

        Using this method you can begin a BLE scan and leave the dongle in scanning
        mode in the background. It will remain in scanning mode until you call the
        :meth:`end_scan` method or the :meth:`reset` method. 

        Args:
            interval (int): BLE scan interval, in units of 625us
            window (int): BLE scan window, in units of 625us

        Returns:
            True on success, False otherwise.
        """

        # TODO validate params and current state
        logger.debug('configuring scan parameters') 
        self.api.ble_cmd_gap_set_scan_parameters(interval, window, 1)
        self._set_state(self._STATE_CONFIGURE_SCAN)
        self.api.ble_cmd_gap_discover(1) # any discoverable devices
        self._wait_for_state(self._STATE_CONFIGURE_SCAN)
        # TODO check state

        logger.debug('starting async scan for devices')
        self.scan_targets = None
        self.scan_callback = callback
        self._set_state(self._STATE_SCANNING)
        return True

    def is_scanning(self):
        return self.state == self._STATE_SCANNING

    def end_scan(self):
        """Ends an ongoing BLE scan started by :meth:`begin_scan`.

        Returns:
            a :class:`ScanResults` object containing the scan results.
        """
        # TODO check states before/after
        self._set_state(self._STATE_GAP_END)
        self.api.ble_cmd_gap_end_procedure()
        self._wait_for_state(self._STATE_GAP_END)

        logger.debug('scanning completed')
        return self.scan_responses

    # synchronous scan
    def scan_devices(self, devnames, timeout=DEF_TIMEOUT, interval=DEF_SCAN_INTERVAL, window=DEF_SCAN_WINDOW):
        """Run a BLE scan for a defined interval and return results.
        
        Alternative to :meth:`begin_scan/:meth:`end_scan`. 

        Args:
            timeout (float): time in seconds to run the scanning process for
            interval (int): BLE scan interval, in units of 625us
            window (int): BLE scan window, in units of 625us

        Returns:
            a :class:`ScanResults` object containing the scan results.
        """

        # TODO validate params and state
        logger.debug('configuring scan parameters') 
        self.api.ble_cmd_gap_set_scan_parameters(interval, window, 1)
        self._set_state(self._STATE_CONFIGURE_SCAN)
        self.api.ble_cmd_gap_discover(1) # any discoverable devices
        self._wait_for_state(self._STATE_CONFIGURE_SCAN)

        logger.debug('starting scan for devices {}'.format(devnames))
        self.scan_targets = devnames
        self._set_state(self._STATE_SCANNING)
        self._wait_for_state(self._STATE_SCANNING, timeout)

        self._set_state(self._STATE_GAP_END)
        self.api.ble_cmd_gap_end_procedure()
        self._wait_for_state(self._STATE_GAP_END)

        logger.debug('scanning completed')

        return self.scan_responses

    # connecting to a device
    # params are:
    #   address of device
    #   address type (0 for public)
    #   conn interval min (units of 1.25ms)
    #   conn interval max (units of 1.25ms)
    #   supervision timeout (units of 10ms)
    #   slave latency

    def connect(self, devicelist, calibration=True):
        """Establish a connection to one or more SK8 devices.

        Given a list of 1 or more :class:`ScanResult` objects, this method will attempt
        to create a connection to each SK8 in sequence. It will return when
        all connections have been attempted, although they may not all have succeeded. In
        addition, the dongle has a limit on simultaneous connections, which you can
        retrieve by calling :meth:`get_supported_connections`. If the number of 
        supplied device names exceeds this value then the method will abort 
        immediately. 

        Args:
            devicelist (list): a list of :class:`ScanResult` instances, one for each
                SK8 you wish to create a connection to. 
            calibration (bool): True if calibration data should be loaded post-connection,
                for each device (if available).

        Returns:
            tuple (`result`, `devices`), where `result` is a bool indicating if 
            connections were successfully made to all given devices. If True, 
            `devices` will contain a list of :class:`SK8` instances representing
            the connected SK8 devices. If False, `devices` will contain a smaller
            number of :class:`SK8` instances depending on the number of connections
            that succeeded (possibly 0). 
        """
        if not isinstance(devicelist, list):
            devicelist = [devicelist]

        logger.debug('Connecting to {} devices'.format(len(devicelist)))
        if len(devicelist) > self.supported_connections:
            logging.error('Dongle firmware supports max {} connections, {} device connections requested!'.format(self.supported_connections, len(devicelist)))
            return (False, [])

        # TODO check number of active connections and fail if exceeds max

        connected_devices = []
        all_connected = True
        for dev in devicelist:
            logger.info('Connecting to {} (name={})...'.format(dev.addr, dev.name))
            self._set_state(self._STATE_CONNECTING)
            self.api.ble_cmd_gap_connect_direct(dev.raw_addr, 0, 6, 14, 100, 5)
            self._wait_for_state(self._STATE_CONNECTING, 5)

            if self.state != self._STATE_CONNECTED:
                logger.warn('Connection failed!')
                # send end procedure to cancel connection attempt
                self._set_state(self._STATE_GAP_END)
                self.api.ble_cmd_gap_end_procedure()
                self._wait_for_state(self._STATE_GAP_END)
                all_connected = False
                continue

            conn_handle = self.conn_handles[-1]
            logger.info('Connection OK, handle is 0x{:02X}'.format(conn_handle))
            sk8 = SK8(self, conn_handle, dev, calibration)
            self._add_device(sk8)
            connected_devices.append(sk8)
            sk8._discover_services()

            time.sleep(0.1) # TODO
        return (all_connected, connected_devices)


    def connect_direct(self, device, calibration=True):
        """Establish a connection to a single SK8.

        Args:
            device: either a :class:`ScanResult` or a plain hardware address string
                in xx:xx:xx:xx:xx:xx format.
            calibration (bool): True to attempt to load calibration data for this
                device after connection, False otherwise. See :meth:`SK8.load_calibration`.

        Returns:
            tuple (`result`, `device`), where `result` is a bool indicating if a 
            connection was created successfully. If `result` is True, `device` will
            be set to a new :class:`SK8` instance. Otherwise it will be None.
        """

        # convert string address into a ScanResult if needed
        if not isinstance(device, ScanResult):
            if isinstance(device, str):
                device = ScanResult(device, fmt_addr_raw(device))
            elif isinstance(device, unicode):
                device = device.encode('ascii')
                device = ScanResult(device, fmt_addr_raw(device))
            else:
                logger.warn('Expected ScanResult, found type {} instead!'.format(type(device)))
                return (False, None)

        logger.debug('Connecting directly to device address'.format(device.addr))
        # TODO check number of active connections and fail if exceeds max
        self._set_state(self._STATE_CONNECTING)

        # TODO parameters here = ???
        self.api.ble_cmd_gap_connect_direct(device.raw_addr, 0, 6, 14, 100, 5)
        self._wait_for_state(self._STATE_CONNECTING, 5)

        if self.state != self._STATE_CONNECTED:
            logger.warn('Connection failed!')
            # send end procedure to cancel connection attempt
            self._set_state(self._STATE_GAP_END)
            self.api.ble_cmd_gap_end_procedure()
            self._wait_for_state(self._STATE_GAP_END)
            return (False, None)

        conn_handle = self.conn_handles[-1]
        logger.info('Connection OK, handle is 0x{:02X}'.format(conn_handle))
        sk8 = SK8(self, conn_handle, device, calibration)
        self._add_device(sk8)
        sk8._discover_services()

        return (True, sk8)

    def get_supported_connections(self):
        """Returns the number of supported simultaneous BLE connections.

        The BLED112 is capable of supporting up to 8 simultaneous BLE connections.
        However, the default firmware image has a limit of just 3 devices, which 
        is a lot easier to run up against. This method retrieves the current value
        of this setting. 

        Returns:
            int. The number of supported simultaneous connections, or -1 on error
        """
        if self.supported_connections != -1:
            return self.supported_connections
        
        if self.api is None:
            return -1

        self._set_state(self._STATE_DONGLE_COMMAND)
        self.api.ble_cmd_system_get_connections()
        self._wait_for_state(self._STATE_DONGLE_COMMAND)
        
        return self.supported_connections

    def get_device_addresses(self):
        """Obtain a list of hardware addresses (hex format) for all connected SK8s.
        
        Returns:
            list of str, each giving the hardware address of a currently connected
            SK8 device.
        """
        return list(self.devices.keys())

    def get_devices(self):
        """Obtain a list of :class:`SK8` objects for all connected SK8s.
        
        Returns:
            list of :class:`SK8` objects, each corresponding to a 
            currently connected SK8 device.
        """
        return list(self.devices.values())

    def set_disconnect_handler(self, h):
        """Allows an application to register a callback to receive disconnection events.

        An application can pass a callback here to be notified when a connected
        device is unexpectedly disconnected. The supplied callable should have 
        signature: (dongle(:class:`Dongle`), sk8(:class:`SK8`), `reason`, `msg`) where 
        `reason` will be a numeric code indicating the reason for the disconnection,
        and `msg` will be a string containing a human readable description. 
        """
        self._disconnect_handler = h

    def get_device(self, n):
        """Get :class:`SK8` instance for a specific connected device.

        Retrieves an :class:`SK8` object identified by its hardware address.

        Args:
            n (str): device address in xx:xx:xx:xx:xx:xx format

        Returns:
            The :class:`SK8` instance matching the supplied address, or None if
            no matching device exists. 
        """ 
        return self.devices.get(n, None)

    # internal funcs

    def _add_device(self, dev):
        self.devices[dev.addr] = dev
        self.conn_devices[dev.conn_handle] = dev

    @staticmethod
    def _hard_reset(address):
        logger.info('Attempting hard reset on dongle at {}'.format(address))
        p = None
        for i in range(Dongle.PORT_RETRIES):
            try:
                p = serial.Serial(port=address, baudrate=Dongle.BAUDRATE, timeout=DEF_TIMEOUT)
                logger.info('Opened serial port successfully')
                break
            except serial.serialutil.SerialException as e:
                logger.warn('Failed to open serial port, attempt {}/{}'.format(i+1, Dongle.PORT_RETRIES))
                time.sleep(0.1)

        if p is None:
            logger.error('Hard reset failed, unable to access serial port {}'.format(address))
            return False

        payload = struct.pack('<B', 0)
        reset_cmd = struct.pack('>HBB', len(payload), 0, 0) + payload
        p.write(reset_cmd)
        p.close()
        logger.info('System reset sequence completed')
        return True

    def _clear(self):
        self.conn_handles = []
        self.scan_targets = []
        self.scan_callback = None
        self.devices = {}
        self.attr_read = {}
        self.attr_write = {}
        self.conn_devices = {}
        self._conn_interval = -1
        self._supervision_timeout = -1
        self._slave_latency = -1
        self.packets = 0
        self.lastpackets = 0


    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """
        Called when object used with "with" keyword goes out of scope, just calls
        the close method.
        """
        self.close()
        # if exc_type is not None:
        #     logger.warn(exc_type)
        #     logger.warn(exc_value)
        #     logger.warn(exc_traceback)

    def _disconnect(self, handle):
        logger.debug('Disconnecting conn handle = {}'.format(handle))
        self._set_conn_state(handle, self._STATE_DISCONNECTING)
        self.api.ble_cmd_connection_disconnect(handle)
        self._wait_for_conn_state(handle, self._STATE_DISCONNECTING)
        if handle in self.conn_handles:
            logger.debug('Removing conn handle')
            self.conn_handles.remove(handle)
        return True

    def _wait_for_state(self, state, timeout=DEF_TIMEOUT):
        t = time.time()

        while self.state == state:
            if timeout is not None and time.time() - t >= timeout:
                break

            time.sleep(0.001)

        logger.debug('_wait_for_state: {:.2f}'.format(time.time() - t))

    def _wait_for_conn_state(self, connection, state, timeout=DEF_TIMEOUT):
        t = time.time()

        while self.conn_state[connection] == state:
            if timeout is not None and time.time() - t >= timeout:
                break

            time.sleep(0.001)

        logger.debug('_wait_for_conn_state: {:.2f}'.format(time.time() - t))

    def _read_attribute(self, conn_handle, att_handle, israw=False):
        self.attr_read = {}

        self._set_conn_state(conn_handle, self._STATE_READ_GATT)
        self.api.ble_cmd_attclient_read_by_handle(conn_handle, att_handle)
        self._wait_for_conn_state(conn_handle, self._STATE_READ_GATT, DEF_TIMEOUT)

        if conn_handle not in self.attr_read:
            logger.debug('Failed to read attribute {:04X} on {:02X}'.format(att_handle, conn_handle))
            return None

        data = self.attr_read[conn_handle].get(att_handle, None)
        if data is None:
            logger.warn('Reading attribute 0x{:04X} failed'.format(att_handle))
            return None

        if israw:
            return data

        return data.decode('ascii')

    def _write_attribute(self, conn_handle, att_handle, value):
        self.attr_write = {}

        self._set_conn_state(conn_handle, self._STATE_WRITE_GATT)
        self.api.ble_cmd_attclient_attribute_write(conn_handle, att_handle, value)
        self._wait_for_conn_state(conn_handle, self._STATE_WRITE_GATT, DEF_TIMEOUT)

        if conn_handle not in self.attr_write:
            logger.debug('Failed to write attribute {:04X} on {:02X}, val={}'.format(att_handle, conn_handle, value))
            return False

        if self.attr_write[conn_handle][att_handle] != 0:
            reason = RESULT_CODE[self.attr_write[conn_handle][att_handle]]
            logger.debug('Failed to write attribute {:04X} on {:02X}, reason={}'.format(att_handle, conn_handle, reason))
            return False

        return True

    def _set_state(self, s):
        self.state = s
        logger.debug('set_state({})'.format(s))

    def _set_conn_state(self, c, s):
        self.conn_state[c] = s

    def _enable_imu_streaming(self, dev, imu_state, sensor_state):

        imu_select = dev.get_characteristic_handle_from_uuid(UUID_IMU_SELECTION)
        sensor_select = dev.get_characteristic_handle_from_uuid(UUID_SENSOR_SELECTION)

        if imu_select is None or sensor_select is None:
            logger.warn('Failed to find handles for IMU configuration!')
            return False

        logger.debug('setting IMU state = {:02X} on device {}'.format(imu_state, dev.addr))
        self._write_attribute(dev.conn_handle, imu_select, struct.pack('B', imu_state))
        time.sleep(0.1)
        self._write_attribute(dev.conn_handle, sensor_select, struct.pack('B', sensor_state))
        logger.debug('Completed configuring IMUs on device {}'.format(dev.addr))

        self._set_conn_state(dev.conn_handle, self._STATE_BEGIN_STREAMING)
        self.api.ble_cmd_attclient_attribute_write(dev.conn_handle, dev.get_ccc_handle_from_uuid(UUID_IMU_CCC), b'\x01\x00')
        self._wait_for_conn_state(dev.conn_handle, self._STATE_BEGIN_STREAMING)

        if self.conn_state[dev.conn_handle] != self._STATE_STREAMING:
            logger.debug('Failed to activate streaming on device {}!'.format(dev.addr))
            return False

        logger.debug('IMU streaming activated OK on device {}'.format(dev.addr))
        dev.imus_enabled = imu_state
        return True

    def _enable_extana_streaming(self, dev, include_imu, enabled_sensors):
        # if we want to stream internal IMU data too, set that up first
        if include_imu:
            imu_select = dev.get_characteristic_handle_from_uuid(UUID_IMU_SELECTION)
            sensor_select = dev.get_characteristic_handle_from_uuid(UUID_SENSOR_SELECTION)

            if imu_select is None or sensor_select is None:
                logger.warn('Failed to find handles for IMU configuration!')
                return False

            # set up IMU state before activating streaming
            imu_state = 0x01
            logger.debug('setting IMU state = {:02X} on device {}'.format(imu_state, dev.addr))
            self._write_attribute(dev.conn_handle, imu_select, struct.pack('B', imu_state))
            time.sleep(0.1)
            self._write_attribute(dev.conn_handle, sensor_select, struct.pack('B', enabled_sensors))
            logger.debug('Completed configuring IMUs on device {}'.format(dev.addr))

        extana_imu_streaming = dev.get_characteristic_handle_from_uuid(UUID_EXTANA_IMU_STREAMING)
        extana_imu_streaming_tmp = dev.get_characteristic_handle_from_uuid(UUID_EXTANA_IMU_STREAMING_TMP)
        if extana_imu_streaming is None and extana_imu_streaming_tmp is None:
            logger.warn('Failed to find handles for ExtAna configuration')
            return False

        # write to the char that will actually enable the sending of IMU packets
        # while ExtAna streaming is active
        if extana_imu_streaming is not None:
            self._write_attribute(dev.conn_handle, extana_imu_streaming, struct.pack('B', 1 if include_imu else 0))
        else:
            self._write_attribute(dev.conn_handle, extana_imu_streaming_tmp, struct.pack('B', 1 if include_imu else 0))

        # enable ExtAna streaming
        self._set_conn_state(dev.conn_handle, self._STATE_BEGIN_STREAMING)
        self.api.ble_cmd_attclient_attribute_write(dev.conn_handle, dev.get_ccc_handle_from_uuid(UUID_EXTANA_CCC), b'\x01\x00')
        self._wait_for_conn_state(dev.conn_handle, self._STATE_BEGIN_STREAMING)

        if self.conn_state[dev.conn_handle] != self._STATE_STREAMING:
            logger.debug('Failed to activate streaming on device {}!'.format(dev.addr))
            return False

        logger.debug('SK8-ExtAna streaming activated OK on device {}'.format(dev.addr))
        return True

    def _disable_imu_streaming(self, dev):
        self._set_conn_state(dev.conn_handle, self._STATE_CONFIGURE_IMUS)
        self.api.ble_cmd_attclient_attribute_write(dev.conn_handle, dev.get_ccc_handle_from_uuid(UUID_IMU_CCC), b'\x00\x00')
        self._wait_for_conn_state(dev.conn_handle, self._STATE_CONFIGURE_IMUS)
        return True

    def _disable_extana_streaming(self, dev):
        self._set_conn_state(dev.conn_handle, self._STATE_CONFIGURE_ANA)
        self.api.ble_cmd_attclient_attribute_write(dev.conn_handle, dev.get_ccc_handle_from_uuid(UUID_EXTANA_CCC), b'\x00\x00')
        self._wait_for_conn_state(dev.conn_handle, self._STATE_CONFIGURE_ANA)
        return True

    # responses

    def ble_rsp_attclient_attribute_write(self, connection, result):
        super(Dongle, self).ble_rsp_attclient_attribute_write(connection, result)
        logger.debug('Result of attclient_attribute_write on conn 0x{:02X} = {}'.format(connection, RESULT_CODE[result]))

    # response to service discovery command
    def ble_rsp_attclient_read_by_group_type(self, connection, result):
        super(Dongle, self).ble_rsp_attclient_read_by_group_type(connection, result)
        logger.debug('Result of read_by_group_type on conn 0x{:02X} = {}'.format(connection, RESULT_CODE[result]))
        if result != 0:
            self._set_conn_state(connection, self._STATE_IDLE)

    def ble_rsp_gap_end_procedure(self, result):
        super(Dongle, self).ble_rsp_gap_end_procedure(result)
        logger.debug('Result of gap_end_procedure: {}'.format(RESULT_CODE[result]))
        self._set_state(self._STATE_IDLE)

    def ble_rsp_gap_set_mode(self, result):
        super(Dongle, self).ble_rsp_gap_set_mode(result)
        logger.debug('Result of gap_set_mode: {}'.format(RESULT_CODE[result]))
        self._set_state(self._STATE_IDLE)

    def ble_rsp_gap_discover(self, result):
        super(Dongle, self).ble_rsp_gap_discover(result)
        logger.debug('Result of gap_discover: {}'.format(RESULT_CODE[result]))
        self.scan_responses.clear()
        self._set_state(self._STATE_IDLE)

    def ble_rsp_connection_update(self, connection, result):
        super(Dongle, self).ble_rsp_connection_update(connection, result)
        logger.debug('>>> Connection update result: {}'.format(RESULT_CODE[result]))

    # conn_handle = uint8
    def ble_rsp_gap_connect_direct(self, result, connection_handle):
        super(Dongle, self).ble_rsp_gap_connect_direct(result, connection_handle)
        logger.debug('Result of gap_connect_direct: {} [0x{:02X}]'.format(RESULT_CODE[result], connection_handle))
        # if result == 0:
        #     self.conn_handles.append(connection_handle)
        #     self._set_state(self._STATE_CONNECTED)
        # else:
        #     self._set_state(self._STATE_IDLE)

    def ble_rsp_connection_disconnect(self, connection, result):
        super(Dongle, self).ble_rsp_connection_disconnect(connection, result)
        if result == 0:
            logger.debug('Disconnect on connection 0x{:02X} = {}'.format(connection, RESULT_CODE[result]))
        self._set_conn_state(connection, self._STATE_IDLE)

    def ble_rsp_attclient_read_by_type(self, connection, result):
        super(Dongle, self).ble_rsp_attclient_read_by_type(connection, result)
        logger.debug('Result of read by type: {} [0x{:02X}]'.format(connection, result))

    def ble_rsp_system_get_connections(self, maxconn):
        super(Dongle, self).ble_rsp_system_get_connections(maxconn)
        self.supported_connections = maxconn
        self._set_state(self._STATE_IDLE)

    # events

    def ble_evt_connection_disconnected(self, connection, reason):
        super(Dongle, self).ble_evt_connection_disconnected(connection, reason)
        if reason == 0:
            logger.debug('Connection disconnected locally')
        else:
            if reason == 0x216: # locally initiated, probably not error
                logger.debug('Connection disconnected (terminated by local host)')
            else:
                logger.warn('Connection disconnected: {} - {}'.format(reason, RESULT_CODE[reason]))
                if connection in self.conn_devices:
                    logger.debug('Calling disconnect on device with handle {}'.format(connection))
                    self.conn_devices[connection].disconnect()
                    # this is probably an error, so call the handler if the user has set one
                    if self._disconnect_handler is not None:
                        self._disconnect_handler(self, self.conn_devices[connection], reason, RESULT_CODE[reason])
                else:
                    logger.warn('Disconnected orphaned connection {}'.format(connection))

    def ble_evt_connection_status(self, connection, flags, address, address_type, conn_interval, timeout, latency, bonding):
        super(Dongle, self).ble_evt_connection_status(connection, flags, address, address_type, conn_interval, timeout, latency, bonding)

        logger.debug('Received evt_connection_status(conn={}, flags={})'.format(connection, flags))
        if conn_interval == 0 and timeout == 0 and latency == 0:
            logger.debug('Conn params are zero (probably old/leftover connection)')
            return
        self.conn_handles.append(connection)
        self._set_state(self._STATE_CONNECTED)

        # convert both of these values into milliseconds
        self._conn_interval = conn_interval * 1.25
        self._supervision_timeout = timeout * 10
        # latency is given in number of connection intervals
        self._slave_latency = latency
        logger.debug('>>> CONN PARAMS: interval={:.1f}ms, timeout={:.1f}ms, latency={:d}'.format(conn_interval * 1.25, timeout * 10, latency))

    
    def ble_evt_gap_scan_response(self, rssi, packet_type, sender, address_type, bond, data):
        super(Dongle, self).ble_evt_gap_scan_response(rssi, packet_type, sender, address_type, bond, data)

        addr = fmt_addr(sender)
        # packet type should be 4 for scan response including device names
        has_name = (packet_type == 0x04)
        name = None

        if has_name:
            # data structure:
            #   byte 1: length of the data
            #   byte 2: AD type = Complete local name = 0x09
            #   remainder of data is the name in ASCII format
            # (this may vary for other devices, but the SK8s should all match this)
            data = bytearray(list(data))
            if len(data) > 2 and data[0] == (len(data) - 1) and data[1] == 0x09:
                name = data[2:].decode('ascii')

        # TODO: can probably ignore any device that has no name, SK8s will usually have one set
        if self.ignore_nameless and (not has_name or name is None):
            return

        if self.scan_responses.update(addr, sender, name, rssi):
            # returns True if newly discovered device, not one seen already
            if self.scan_callback is not None:
                self.scan_callback(self.scan_responses.get_device(addr))

        if self.scan_targets is not None and len(self.scan_targets) > 0 and len(self.scan_responses) >= len(self.scan_targets):
            # check if we have responses from all target devices
            for dev in self.scan_targets:
                if dev not in self.scan_responses:
                    return

            # if so, end the scan now (otherwise it will continue until the 
            # timeout expires 
            logger.debug('Found all scan targets! {}'.format(self.scan_targets))
            self._set_state(self._STATE_IDLE)

    # events produced during service discovery
    def ble_evt_attclient_group_found(self, connection, start, end, uuid):
        super(Dongle, self).ble_evt_attclient_group_found(connection, start, end, uuid)
        logger.debug('>> Service found [{:04X}, {:04X}], UUID = {}'.format(start, end, pp_hex(bytearray(uuid))))
        if connection in self.conn_devices:
            dev = self.conn_devices[connection]
            dev._add_service(start, end, uuid)
        logger.debug('GROUP: 0x{:04X} 0x{:04X} {}'.format(start, end, pp_hex(uuid)))

    # events produced during descriptor discovery
    def ble_evt_attclient_find_information_found(self, connection, chrhandle, uuid):
        super(Dongle, self).ble_evt_attclient_find_information_found(connection, chrhandle, uuid)

        # lookup char matching the UUID and add descriptor info to it
        if connection in self.conn_devices:
            dev = self.conn_devices[connection]
            # check if this is a char declaration
            if uuid == RAW_UUID_GATT_CHAR_DECL or uuid == RAW_UUID_GATT_CCC:
                current_service = dev.get_service_for_handle(chrhandle)
                if chrhandle in current_service.chars:
                    current_char = current_service.chars[chrhandle]
                    logger.debug('Adding desc to char {:04X} / {}'.format(current_char.handle, pp_hex(current_char.value)))
                    current_char.add_descriptor(chrhandle, uuid, pp_hex(uuid))
                else:
                    if uuid != RAW_UUID_GATT_CCC:
                        logger.warn('unknown UUID {} not in char {:04X}'.format(pp_hex(uuid), chrhandle))

    # events produced during characteristic discovery and notifications
    def ble_evt_attclient_attribute_value(self, connection, atthandle, type, value):
        super(Dongle, self).ble_evt_attclient_attribute_value(connection, atthandle, type, value)

        # logger.debug('attr value: {} {} {} {}'.format(connection, atthandle, type, value))
        if type == ATTR_VALUE_TYPE_READ_BY_TYPE:
            if connection in self.conn_devices and self.conn_state[connection] == self._STATE_DISCOVER_CHARS:
                dev = self.conn_devices[connection]
                value = bytearray(value)
                char = dev._add_characteristic(atthandle, value)
                # should also add the descriptor this is linked to
                char.add_descriptor(char.char_handle, char.raw_uuid, char.uuid)
                # if this is a notify charactertistic, can add the CCCD here too
                if char.can_notify():
                    logger.debug('Found a notify char, adding CCCD with handle {:04X}'.format(atthandle+2))
                    char.add_descriptor(atthandle + 2, RAW_UUID_GATT_CCC, UUID_GATT_CCC)
                

        if type == ATTR_VALUE_TYPE_READ:
            # standard read attribute operation response
            if connection in self.conn_devices:
                self.attr_read[connection] = {}
                self.attr_read[connection][atthandle] = value
                self._set_conn_state(connection, self._STATE_IDLE)
                logger.debug('Read attribute: conn={:02X}, atthandle={:04X}, value={}'.format(connection, atthandle, value))

        if type == ATTR_VALUE_TYPE_NOTIFY:
            if connection in self.conn_devices:
                timestamp = time.time()
                device = self.conn_devices[connection]
                # for now determine packet type based on length
                if len(value) == IMU_DATA_STRUCT.size:
                    data = IMU_DATA_STRUCT.unpack(value)
                    device._update_sensors(data[:3], data[3:6], data[6:9], data[9], data[10], timestamp)
                elif len(value) == ANA_DATA_STRUCT.size:
                    data = ANA_DATA_STRUCT.unpack(value)
                    device._update_extana(data[0], data[1], data[2], data[3], timestamp)
                device.packets += 1
                self.packets += 1

    def ble_evt_attclient_procedure_completed(self, connection, result, chrhandle):
        super(Dongle, self).ble_evt_attclient_procedure_completed(connection, result, chrhandle)
        logger.debug('GATT procedure completed on conn 0x{:02X}, result 0x{:04X}, char handle 0x{:04X}'.format(connection, result, chrhandle))
        if self.conn_state[connection] == self._STATE_BEGIN_STREAMING and result == 0:
            self._set_conn_state(connection, self._STATE_STREAMING)
        else:
            if connection in self.conn_devices:
                self.attr_write[connection] = {}
                self.attr_write[connection][chrhandle] = result
                logger.debug('Write attribute: conn={:02X}, chrhandle={:04X}, result={:02X}'.format(connection, chrhandle, result))
            self._set_conn_state(connection, self._STATE_IDLE)

