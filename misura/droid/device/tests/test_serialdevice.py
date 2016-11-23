#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest

from misura.droid import device


print 'Importing', __name__


def setUpModule():
    print 'Starting', __name__


class Serial(unittest.TestCase):
    #	def setUp(self):
    #		self.d=device.Serial()

    def test__init__(self):
        print device.Serial.list_available_devices()
        d = device.Serial(node='/dev/ttyS0')
        self.assertTrue(d['dev'], '/dev/ttyS0')

if __name__ == "__main__":
    unittest.main(verbosity=2)
