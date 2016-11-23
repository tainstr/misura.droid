#!/usr/bin/python
# -*- coding: utf-8 -*-
"""A device/peripheral available through the LAN."""
from copy import deepcopy
import urllib2
from traceback import format_exc

from physicaldevice import Physical
from enumerated import Enumerated

class HTTP(Physical, Enumerated):

    """A device/peripheral available through the LAN."""
    conf_def = deepcopy(Physical.conf_def)
    conf_def += [{'handle': 'auth', 'name': 'Authentication Type', 'type': 'Chooser', 'current': 'None', 'options': ['None', 'Basic', 'SSL', 'misura']},
                 {'handle': 'login', 'name': 'Login Name',
                     'current': 'ipdas', 'type': 'String', "readLevel": 3},
                 {'handle': 'password', 'name': 'Password',
                     'current': 'cyber', 'type': 'String', "readLevel": 3},
                 {'handle': 'session', 'name': 'Session', 'type': 'String',
                     'attr': ['ReadOnly'], "readLevel":3},
                 {'isConnected': False}]
    available = {}
    _udev = {}
    enumerated_option = 'http'

    def login_Basic(self):
        """Handles the basic login authentication to the device"""
        return True

    def login(self):
        if self['auth'] == 'Basic':
            return self.login_Basic()
        # No auth defined
        return True

    def validate_connection(self):
        return True

    def connection(self, blacklist=[]):
        self['isConnected'] = False
        # First check if the host is alive
        try:
            print 'Opening url', self['dev']
            u = urllib2.urlopen(self['dev'], timeout=30)
            u.close()
        except:
            self.log.error(format_exc())
            return False
        # Then try to login
        if not self.login():
            self.log.error('Login failed:', self['dev'], self['login'])
            return False
        # Then, validate the content of the connection
        if not self.validate_connection():
            return False
        self['isConnected'] = True
        return True
