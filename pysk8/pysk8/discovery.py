import logging

import pysk8.util
from pysk8.util import pp_hex

class Descriptor(object):
    """
    Represents a BLE descriptor within a characteristic
    """

    def __init__(self, handle, uuid):
        self.handle = handle
        self.uuid = uuid

class Characteristic(object):
    """
    Represents a BLE characteristic within a service
    """

    def __init__(self, handle, value):
        self.handle = handle
        self.value = value
        self.props = value[0]
        self.char_handle = value[1:3]
        self.raw_uuid = value[3:]
        self.uuid = pp_hex(self.raw_uuid)
        logger.debug('Creating char %04X, %s, %s, %s' % (handle, self.pp_properties(), pp_hex(self.char_handle), self.uuid))
        self.descriptors = {}

    def add_descriptor(self, handle, uuid):
        self.descriptors[handle] = Descriptor(handle, uuid)

    def can_read(self):
        return (self.props & PROP_READ != 0)

    def can_write(self):
        return (self.props & PROP_WRITE != 0)

    def can_notify(self):
        return (self.props & PROP_NOTIFY != 0)

    # pretty print properties
    def pp_properties(self):
        p = []
        if self.props & PROP_BROADCAST:
            p.append('Broadcast')
        if self.props & PROP_READ:
            p.append('Read')
        if self.props & PROP_WRITE_NO_RESP:
            p.append('Write No Response')
        if self.props & PROP_WRITE:
            p.append('Write')
        if self.props & PROP_NOTIFY:
            p.append('Notify')

        return '|'.join(p)

    def get_descriptor_by_uuid(self, uuid):
        for d in list(self.descriptors.values()):
            if d.uuid == uuid:
                return d

        return None

class Service(object):
    """
    Represents a BLE service 
    """

    def __init__(self, start_handle, end_handle, uuid):
        self.start_handle = start_handle
        self.end_handle = end_handle
        self.uuid = pp_hex(uuid)
        self.raw_uuid = uuid
        self.chars = {}

    def add_characteristic(self, handle, value):
        self.chars[handle] = Characteristic(handle, value)

    def get_characteristic_by_uuid(self, uuid):
        for c in list(self.chars.values()):
            if c.uuid == uuid:
                return c

        return None

    def get_characteristic_by_handle(self, handle):
        return self.chars.get(handle, None)

