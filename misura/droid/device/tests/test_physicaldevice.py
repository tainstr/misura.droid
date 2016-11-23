#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest
from misura.droid import device


print 'Importing', __name__


def setUpModule():
    print 'Starting', __name__


class Physical(unittest.TestCase):

    def setUp(self):
        self.d = device.Physical()

    def test_retry(self):
        self.assertEqual(self.d.retry, self.d['retry'])
        self.d['retry'] += 1
        self.assertEqual(self.d.retry, self.d['retry'])
        print 'set prop'
        self.d.retry = 20
        print 'done'
        self.assertEqual(self.d.retry, self.d['retry'])
        self.d['retry'] = 8
        self.assertEqual(8, self.d.retry)


class UDevice(unittest.TestCase):

    def setUp(self):
        self.d = device.UDevice()

    def test_list_available_devices(self):
        class SubPhysical(device.UDevice):
            dev_pattern = '/dev/tty*'
        v = SubPhysical.list_available_devices()
        self.assertIn('/dev/tty0', v.values())
        self.assertGreater(len(v), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
