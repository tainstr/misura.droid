#!/usr/bin/python
# -*- coding: utf-8 -*-
"""A device/peripheral available through the LAN."""
import socket
from copy import deepcopy
from traceback import format_exc

from physicaldevice import Physical
from enumerated import Enumerated


conf = [
    {"handle": 'addr', 	"name": 'Remote address',
     "current": '192.168.0.34', 	"type": 'String', "readLevel": 3	},
    {"handle": 'port', 	"name": 'Port', 	"current": 502,
        "type": 'Integer', 	"readLevel": 3},
    {"handle": 'nodelay', 	"name": 'TCP_NODELAY',
        "current": False, "type": 'Boolean', "readLevel": 3},
    {'timeout': 1000}
]


class Socket(Physical, Enumerated):

    """Interfaccia generica per periferiche seriali"""
    conf_def = deepcopy(Physical.conf_def)
    conf_def += conf
    available = {}
    _udev = {}
    enumerated_option = 'socket'

    def __init__(self, parent=None, node='127.0.0.1:8000'):
        Physical.__init__(self, parent=parent, node=node)
        node = self['dev']
        self.com = False
        self.timeout = self.get('timeout') / 1000.
        self['isConnected'] = False
        if ':' in node:
            self['addr'], port = node.split(':')
            self['port'] = int(port)
        else:
            self['addr'] = node

    def set_timeout(self, val):
        if self.com:
            self.com.settimeout(val / 1000.)
        return val

    def set_nodelay(self, val=None):
        """Set TCP_NODELAY"""
        w = False
        if val is None:
            val = self.desc.get('nodelay')
            w = True
        if self.com:
            self.com.setsockopt(
                socket.IPPROTO_TCP, socket.TCP_NODELAY, int(val))
        if w:
            self.desc.set('nodelay', val)
        return val

    def get_nodelay(self):
        """Get TCP_NODELAY"""
        if self.com:
            val = self.com.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
        else:
            return self.desc.get('nodelay')
        return bool(val)

    def com_close(self):
        """Properly close the current socket"""
        if not self.com:
            return
        try:
            self.com.shutdown(socket.SHUT_RDWR)
        except:
            self.log.debug(format_exc())
        self.com.close()
        self.com = False

    def com_new(self):
        """Re-create the socket connection"""
        self.com_close()
        t = self['timeout'] / 1000.
        addr = (self['addr'], self['port'])
        self.log.debug('com_new', addr, t)
        self.com = socket.create_connection(addr,  t)
        self.log.debug('Reconnected socket', addr)
        self.set_nodelay()
        return self.com

    def connection(self, blacklist=[]):
        """Connect to a socket"""
        v = False
        try:
            self.com_new()
            v = self.validate_connection()
            if not v:
                self.com.close()
        except:
            self.com = False
            self.log.error("Socket connect error ", format_exc())
        self['isConnected'] = v
        return v

    def validate_connection(self):
        """Funzione di validazione della connessione. Da reimplementare ad hoc."""
        self.log.debug('validation...')
#		r=self.com.sendall('10'*1000) #, socket.MSG_DONTWAIT
        r = self.com.send('1')
        return r == 1

    # debug
    def raw(self, idx, msg):
        if not getattr(self, 'read', False):
            self.log.debug('UnImplemented read function')
            return 'UnImplemented'
        self.com.send(msg)
        return self.read()
    xmlrpc_raw = raw

    def close(self):
        self.com_close()
        return Physical.close(self)
