#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Main Interfaces"""
from time import sleep
from copy import deepcopy
from twisted.web import xmlrpc
from traceback import format_exc
import serial

from misura.canon.csutil import retry, lockme, time

from ..utils import crc
from physicaldevice import UDevice

from .. import parameters as params


conf = [
    {"handle": 'baudrate', "name": 'Communication Baudrate',
     "current": 19200, "type": 'Integer', "readLevel": 3},
    {"handle": 'bytesize', "name": 'Byte size',
     "current": 8, "type": 'Integer', "readLevel": 3},
    {"handle": 'parity', "name": 'Parity',
     "current": 'N', "type": 'String', "readLevel": 3},
    {"handle": 'stopbits', "name": 'Stop bits',
     "current": 1, "type": 'Integer', "readLevel": 3},
    {"handle": 'rtscts', "name": 'RtsCts', "readLevel": 3,
        "current": 0, "type": 'Boolean', },
    {"handle": 'xonxoff', "name": 'xOnxOff', "readLevel": 3,
     "current": 0, "type": 'Boolean', },
    {"handle": 'autoBaudrate', "name": 'Automatically find correct baudrate',
     "current": True, "type": 'Boolean', "readLevel": 3},
]


class ReplyTooShort(xmlrpc.Fault):

    def __init__(self, msg='ReplyTooShort'):
        xmlrpc.Fault.__init__(self, 3883, msg)


class SerialError(xmlrpc.Fault, serial.SerialException):

    def __init__(self, msg='ReplyTooShort', code=3884):
        serial.SerialException.__init__(self, msg)
        xmlrpc.Fault.__init__(self, code, msg)


class SerialTimeout(SerialError):

    def __init__(self, msg='SerialTimeout', code=3885):
        SerialError.__init__(self, msg, code)


class SerialPortNotOpen(SerialError):

    def __init__(self, msg='SerialPortNotOpen', code=3886):
        SerialError.__init__(self, msg, code)


class FailedCRC(SerialError):
    pass


class Serial(UDevice):

    """Generic interface for serial devices."""
    conf_def = deepcopy(UDevice.conf_def)
    conf_def += conf
#   dev_pattern='/dev/ttyUSB*'
    dev_pattern = '/dev/tty*[USB][0-{}]'.format(params.max_serial_scan)
    baudrates = []
    """List of baudrates available for auto scan"""
    available = {}
    _udev = {}
    minimum_reply_len = 1
    """Standard minimum length for reply messages"""
    cyclic_redundancy_check = 0
    """Perform crc on messages - set to last digits to use"""
    endstring = ''
    """String marking end of reply message"""
    UDevice.setProperties(
        'bytesize', 'parity', 'stopbits', 'xonxoff', 'rtscts')
    readerror = None

    def __init__(self, parent=None, node='?s', bytesize=serial.EIGHTBITS,
                 parity=serial.PARITY_NONE,
                 stopbits=1,
                 xonxoff=0,  # Software handshake
                 rtscts=0):  # Hardware handshake
        UDevice.__init__(self, parent=parent, node=node)
        # Redefine here for updated max
        self.com = False
        self.baudrates = []
        self['isConnected'] = False

    def connection(self, blacklist=[]):
        """Connect to serial port and validate response"""
        v = False
        self['isConnected'] = v
        b = self['baudrate']
        # Ricerca abilitata
        print 'AutoSearch:', self['autoBaudrate'], self.baudrates
        if self['autoBaudrate'] and len(self.baudrates) > 0:
            if b not in self.baudrates:
                b = self.baudrates + [b]
            else:
                b = self.baudrates[:]
            self.log.info('Scanning Baudrates', b)
            v = self.findBaudrate(b)
        else:
            print 'connect_baudrate'
            v = self.connect_baudrate(b)
        print b, self['autoBaudrate'], self.baudrates
        # imposto l'opzione e attivo eventuali set_isConnected
        self['isConnected'] = v
        # Se sono connesso, carico le impostazioni di default, etc...
        return v

    xmlrpc_connection = connection

    def connect_baudrate(self, baudrate=False):
        """Connects serial port with a baudrate."""
        if not baudrate:
            baudrate = self['baudrate']
        print 'Serial.connect_baudrate', baudrate
        if self.com is not False:
            if self.com.isOpen():
                self.com.close()
                sleep(.1)
        self.desc.set('baudrate', baudrate)
        
        try:
            self.com = serial.Serial(port=self['dev'],   baudrate=baudrate,
                                 bytesize=self['bytesize'],  
                                 parity=self['parity'],  stopbits=self['stopbits'],
                                 timeout=self.timeout, xonxoff=self['xonxoff'], rtscts=self['rtscts'])
        except:
            self.log.error('Error opening serial port:', self['dev'], format_exc())
            return False
                    
        if not self.com.isOpen():
            self.log.debug('Unable to open serial port')
            return False
        # Validate this connection
        if self.validate_connection():
            return True
        # Discard
        return False

    def findBaudrate(self, baudrates):
        """Iterate amongst available baudrates until a connection is successful."""
        for br in baudrates:
            self.log.debug('Try baudrate:', br)
            if self.connect_baudrate(baudrate=br):
                return True
        self.com.close()
        return False

    def validate_connection(self):
        """Connection validation function. To be re-implemented ad hoc."""
        self.log.debug('Skipping validation...')
        return True

    def get_baudrate(self):
        if not self.com:
            return self.desc.get('baudrate')
        return self.com.baudrate

    @lockme()
    def raw(self, msg):
        """Debug. Directly write to serial port and try to read reply"""
        if not getattr(self, 'read', False):
            self.log.debug('UnImplemented read function')
            return 'UnImplemented'
        self.writeerror = None
        self.readerror = None
        self.com.write(msg)
        self.sleep()
        return self.read()
    xmlrpc_raw = raw

    @UDevice.timeout.setter
    def timeout(self, nval):
        """Propagate timeout to serial port."""
        self.timeout = nval * 1000.
        if self.com:
            self.com.timeout = self.timeout

    def set_timeout(self, val):
        val = int(val)
        self.timeout = val
        self.log.debug('timeout set to', val, 'ms')
        return val

    def _flush(self):
        self.com.flushInput()
        self.sleep()
        self.com.flushOutput()
        self.sleep()
        self.com.flush()
        self.sleep()

    @lockme()
    def flush(self):
        self._flush()
    xmlrpc_flush = flush

    def write(self, msg):
        """Write msg to the serial port"""
        self.writeerror = None
        if not self.com.isOpen():
            self.log.error('Port was not open. Reopening...')
            self.com.open()
        try:
            n = self.com.write(msg)
        except serial.SerialException:
            self.connect_baudrate()
            self.writeerror = (30, 'Cannot open serial port for write')
            raise
        # Written the whole message
        if n == len(msg):
            return True
        i = 0
        while self.com.outWaiting() > 0 and i < 5:
            i += 1
            self.sleep()
        if self.com.outWaiting():
            self._flush()
            self.writeerror = (30, 'Output buffer not empty after write')
            raise SerialTimeout(self.writeerror[1])
        return True

    def read(self, minlen=-1, timeout=-1, endstring=False):
        """Read from the serial port, at least minlen characters, until timeout seconds passed."""
        if not self.com.isOpen():
            self.com.open()
            self._flush()
            self.readerror = (30, 'Cannot open serial port for read')
            raise SerialPortNotOpen()
        r = 0
        red = ''
        self.readerror = None
        # Get default minlength
        if minlen < 0:
            minlen = self.minimum_reply_len
        # Get default timeout
        if timeout < 0:
            timeout = self.timeout
        # Get default endstring
        if not endstring:
            endstring = self.endstring
        ncrc = self.cyclic_redundancy_check
        okcrc = False
        t = time()
        while True:
            w = self.com.inWaiting()
            if w == 0:
                if time() - t > timeout:
                    self.readerror = (30, 'Serial.read: timeout, minlen={}, red={}'.format(minlen, len(red)))
                    self.log.debug(self.readerror[1])
                    break
                r += 1
                if len(red) >= minlen and r > 3:
                    break
                #self.log.debug('Serial.read sleeping...', len(red),  repr(red),  minlen, self.latency)
                self.sleep()
                continue
            r = 0
            red += self.com.read(w)
            if len(red) >= minlen and len(red) > ncrc + 1:
                # If crc is enabled and passes, interrupt reading
                if ncrc:
                    if red[-ncrc:] == crc(red[:-ncrc]):
                        okcrc = True
                        break
                if endstring and endstring in red:
                    i = red.index(endstring, -1)
                    red = red[:i + len(endstring)]
                    break
        # CRC required but failed!
        if ncrc and not okcrc:
            self.readerror = (31, 'CRC Redundancy Check failed')
            self._flush()
            raise FailedCRC('CRC Redundancy Check failed')
        if len(red) < minlen and red != endstring:
            self.readerror = (30, 'Too short to be a reply', red)
            self._flush()
            raise ReplyTooShort('Too short to be a reply: ' + repr(red))
        if not red.endswith(endstring):
            self.readerror = (30, 'Message is not correctly terminated', red)
            self._flush()
            msg = 'Message is not correctly terminated by {}: {}'.format(
                endstring, red)
            raise ReplyTooShort(msg)
        return red

    def _writeread(self, msg=False, minlen=-1, timeout=-1):
        """Write `msg` and read the reply."""
        if msg:
            self.write(msg)
        self.sleep()
        return self.read(minlen=minlen, timeout=timeout)

    @lockme()
    @retry()
    def writeread(self, msg=False, minlen=-1, timeout=-1):
        """Locked write `msg` and read the reply."""
        return self._writeread(msg=msg, minlen=minlen, timeout=timeout)

    def close(self):
        if self.com:
            self.com.close()
        return UDevice.close(self)
