import struct

from pysk8.util import pp_hex
from pysk8.constants import *

class Descriptor(object):
    """
    Represents a BLE descriptor within a characteristic
    """

    def __init__(self, handle, raw_uuid, uuid):
        self.handle = handle
        self.uuid = uuid
        self.raw_uuid = raw_uuid

    def pp(self, baseindent=2):
        indent = '\t' * baseindent
        print('{}+ Descriptor uuid={}, handle=0x{:04X}'.format(indent, self.uuid, self.handle))

    def __repr__(self):
        return '[Descriptor] handle=0x{:04X}, uuid={}'.format(self.handle, self.uuid)

class Characteristic(object):
    """
    Represents a BLE characteristic within a service
    """

    def __init__(self, handle, value):
        self.handle = handle
        self.value = value
        self.props = value[0]
        self.char_handle = struct.unpack('<H', value[1:3])[0]
        self.raw_uuid = value[3:]
        self.uuid = pp_hex(self.raw_uuid)
        # logger.debug('Creating char %04X, %s, %s, %s' % (handle, self.pp_properties(), pp_hex(self.char_handle), self.uuid))
        self.descriptors = {}

    def add_descriptor(self, handle, raw_uuid, uuid):
        self.descriptors[handle] = Descriptor(handle, raw_uuid, uuid)

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

    def pp(self, baseindent=1):
        indent = '\t' * baseindent
        print('{}Char uuid={}'.format(indent, self.uuid))
        print('{}\tProperties: {}'.format(indent, self.pp_properties()))
        print('{}\tHandle: 0x{:04X}'.format(indent, self.handle))
        print('{}\tChar handle: 0x{:04X}'.format(indent, self.char_handle))
        print('{}\tNum descs: {}'.format(indent, len(self.descriptors)))
        for d in self.descriptors.values():
            d.pp()

    def __repr__(self):
        s = '[Characteristic] handle={:04X}, uuid={}, descriptors='.format(self.handle, self.uuid) 
        for d in self.descriptors.values():
            s += '\n\t{}'.format(d)
        return s

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
        return self.chars[handle]

    def get_characteristic_by_uuid(self, uuid):
        for c in list(self.chars.values()):
            if c.uuid == uuid:
                return c

        return None

    def get_characteristic_by_handle(self, handle):
        return self.chars.get(handle, None)
    
    def pp(self):
        print('Service uuid={}'.format(self.uuid))
        print('\tStart handle: 0x{:04X}'.format(self.start_handle))
        print('\tEnd handle: 0x{:04X}'.format(self.end_handle))
        print('\tNum chars: {}'.format(len(self.chars)))
        for c in self.chars.values():
            c.pp()


