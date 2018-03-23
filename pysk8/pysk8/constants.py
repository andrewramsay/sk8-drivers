"""pysk8 constants.

Attributes:
    DATA_STRUCT: structure for unpacking SK8 IMU data packets
    MAX_IMUS: maximum number of IMUs attached to any SK8
    DEF_TIMEOUT: default timeout (seconds) for various operations
"""

import struct

IMU_DATA_STRUCT                          = struct.Struct('<hhhhhhhhhBB')
ANA_DATA_STRUCT                          = struct.Struct('<HHHB')
MAX_IMUS                                 = 5
DEF_TIMEOUT                              = 3

LED_MAX                                  = 3000

SENSOR_ACC                               = 0x01
SENSOR_GYRO                              = 0x02
SENSOR_MAG                               = 0x04
SENSOR_ALL                               = SENSOR_ACC | SENSOR_GYRO | SENSOR_MAG

# TODO
# these handles may change when the firmware is modified significantly
# for now, accessing things by handle avoids the need to do service/char discovery
HANDLE_CCC_IMU                           = 0x000F 
HANDLE_CCC_ANA                           = 0x0012
HANDLE_IMU_SELECTION                     = 0x0014
HANDLE_SENSOR_SELECTION                  = 0x0016
HANDLE_SOFT_RESET                        = 0x0018
HANDLE_EXTANA_LED                        = 0x001A 
HANDLE_PACKET_TIMING                     = 0x001C

HANDLE_DEVICE_NAME                       = 0x0007
HANDLE_BATTERY_LEVEL                     = 0x001D
HANDLE_FIRMWARE_VERSION                  = 0x002D

# UUID_SK8_SERVICE                         = 'b9e32260107411e6a7d50002a5d5c51b'
# UUID_IMU_CHAR                            = 'b9e32261107411e6a7d50002a5d5c51b'

UUID_GATT_PRIMARY_SERVICE                = '\x00\x28'
UUID_GATT_CHAR_DECL                      = '\x03\x28'
UUID_GATT_CCC                            = '\x02\x29'

# characteristic properties
PROP_BROADCAST                           = 0x01
PROP_READ                                = 0x02
PROP_WRITE_NO_RESP                       = 0x04
PROP_WRITE                               = 0x08
PROP_NOTIFY                              = 0x10
PROP_INDICATE                            = 0x20
PROP_AUTH_WRITE                          = 0x40
PROP_EXT_PROPS                           = 0x80

# attribute value types
ATTR_VALUE_TYPE_READ                     = 0x00
ATTR_VALUE_TYPE_NOTIFY                   = 0x01
ATTR_VALUE_TYPE_INDICATE                 = 0x02
ATTR_VALUE_TYPE_READ_BY_TYPE             = 0x03
ATTR_VALUE_TYPE_READ_BLOB                = 0x04
ATTR_VALUE_TYPE_INDICATE_RSP_REQ         = 0x05
