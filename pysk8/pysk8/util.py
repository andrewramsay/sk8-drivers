
def fmt_addr(addr):
    """ Format a Bluetooth hardware address as a hex string.
    
    Args:
        addr (bytes): raw Bluetoot address in dongle format.

    Returns:
        str. Address in xx:xx:xx:xx:xx:xx format.
    """
    return ':'.join(reversed(['{:02x}'.format(v) for v in bytearray(addr)]))

def fmt_addr_raw(addr, reverse=True):
    """Given a string containing a xx:xx:xx:xx:xx:xx address, return as a byte sequence.

    Args:
        addr (str): Bluetooth address in xx:xx:xx:xx:xx:xx format.
        reverse (bool): True if the byte ordering should be reversed in the output.

    Returns:
        A bytearray containing the converted address.
    """
    addr = addr.replace(':', '')
    raw_addr = [int(addr[i:i+2], 16) for i in range(0, len(addr), 2)]
    if reverse:
        raw_addr.reverse()
    return bytearray(raw_addr)

def pp_hex(raw, reverse=True):
    """Return a pretty-printed (hex style) version of a binary string.

    Args:
        raw (bytes): any sequence of bytes
        reverse (bool): True if output should be in reverse order.

    Returns:
        Hex string corresponding to input byte sequence.
    """
    if not reverse:
        return ''.join(['{:02x}'.format(v) for v in raw])

    return ''.join(reversed(['{:02x}'.format(v) for v in raw]))

