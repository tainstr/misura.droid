#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Device which represents a real hardware peripheral"""
import os
import glob
from copy import deepcopy

from device import Device
from ..utils import query_udev

class Physical(Device):

    """A real external device/peripheral connected to the PC."""
    conf_def = deepcopy(Device.conf_def)
    conf_def += [{"handle": 'readerror',	"name": 'Last read error', "type": 'String', "readLevel": 3},
                 {"handle": 'writeerror', "name": 'Last write error',
                     "type": 'String', "readLevel": 3},
                 {"handle": 'comErr', "name": 'Consecutive communication errors',
                  "attr": ['ReadOnly'], "readLevel": 3, "type": 'Integer', "readLevel":3},
                 {"handle": 'latency', 	"name": 'Latency', "type": 'Integer',
                  "max": 1000, 	"current": 10, 	"step": 1, 	"min": 0, "readLevel": 3, 'unit': 'millisecond'},
                 {"handle": 'retry', 	"name": 'Retry chances', 	"max": 10, "current": 3, "step": 1,
                  "min": 0, "type": 'Integer', "readLevel": 3},
                 {"handle": 'timeout', "name": 'Communication timeout', "type": 'Integer', "unit": 'millisecond',
                  "max": 2000, 	"current": 75, 	"step": 1, 	"min": 10, "readLevel": 3},
                 ]
    available = {}
    _udev = {}
    Device.setProperties('retry', 'isConnected')

    def __init__(self, parent=None, node='?p'):
        # Retrieve the  dev identifier corresponding to node devpath.
        dev = self.__class__.from_devpath(node)
        devpath = self.__class__.from_dev(dev)
        if devpath == dev:
            devpath = node
        Device.__init__(self, parent=parent, node=devpath)
        self['initializing'] = False
        self.fd = None
        self.file = dev
        self['dev'] = dev
        self['isConnected'] = False
        print 'PhysicalDevice init with', dev, devpath

    @classmethod
    def _decode_node(cls, devpath=0):
        print 'DECNO: start', devpath
        if isinstance(devpath, int):
            print 'DECNO: node not defined,  returning ', devpath
            return '{}{}'.format(cls.node_prefix, devpath), devpath
        dev = cls.from_devpath(devpath)
        # Starting with node_prefix? Decompose to find integer
        if dev.startswith(cls.node_prefix):
            n = dev[len(cls.node_prefix):]
            print 'DECNO: unprefixing ', dev, n
            # not a serial number: convert to int
            # we consider unreasonable int driver idx above 99...
            if len(n) < 3:
                n = int(n)
                print 'DECNO: integer ', dev, n

        # Search for available devpath corresponding to ndev,
        # and retrieve it as node
        dp1 = cls.from_dev(dev)
        # fallback to previous devpath
        if dp1 == dev:
            dp1 = devpath
        print 'DECNO: from_dev', devpath, dev, dp1, cls.available
        return dp1, n

    @property
    def latency(self):
        return self['latency'] / 1000.

    @latency.setter
    def latency(self, nval):
        self['latency'] = nval * 1000.

    def sleep(self, t=-1, f=1):
        """Sleep `t` seconds, divided by a factor of `f`"""
        if t < 0:
            t = self.latency
        t /= float(f)
        Device.sleep(self, t)

    @property
    def timeout(self):
        return self['timeout'] / 1000.

    @timeout.setter
    def timeout(self, nval):
        self['timeout'] = nval * 1000.

    def get_dev(self):
        self['dev'] = self.file
        return self.file
    
    def check(self):
        if not super(Physical, self).check():
            return False
        delta_opt, delta = self.oldest_refresh_time(self['monitor'])
        if delta > self.timeout:
            self.log.critical('Stale monitor process found, ', delta_opt, delta)
            self['running'] = False
            self['running'] = True
            return False
        return True

    def close(self):
        print 'Physical.close', repr(self)
        Device.close(self)
        


class UDevice(Physical):

    """A real device which is managed by udev system. 
    It is represented by a device node in /dev/..."""
    dev_pattern = False
    """Device file-node pattern, eg /dev/video*"""

    @classmethod
    def list_available_devices(cls):
        """Builds available dictionary by iterating all devices matching dev_pattern."""
        if not cls.dev_pattern:
            return cls.available
        r = {}
        for dev in glob.glob(cls.dev_pattern):
            u = cls.query_udev(dev)
            r[u['devpath']] = dev
        cls.available = r
        print 'Physical LISTAD', r
        return r

    @classmethod
    def query_udev(cls, node):
        # Try to convert a devpath
        if not os.path.exists(node):
            node = cls.from_devpath(node)
        dp, tree = query_udev(node)
        if not tree:
            print 'Physical.query_udev FAIL', node
            return {'devpath': node, 'dev': node}
        print 'tree', tree
        print 'default path', dp
        a = 0
        if len(tree) > 0:
            a = tree[-1].get('ATTRS', 0)
        p, v = 0, 0
        if a:
            p = a.get('idProduct', 0)
            v = a.get('idVendor', 0)
        r = {'devpath': dp, 'usbProduct': p, 'usbVendor': p, 'dev': node}
        return r
