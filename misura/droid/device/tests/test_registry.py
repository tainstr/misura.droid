#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest
import os
from copy import deepcopy

from misura.canon.option import ao
from misura.droid import device

print 'Importing', __name__


def setUpModule():
    print 'Starting', __name__


class DevicePathRegistry(unittest.TestCase):

    def setUp(self):
        self.ds = device.DeviceServer()
        self.dev1 = device.Device(self.ds, 'dev1')
        self.dev1['dev'] = '/dev/1'
        self.dev2 = device.Device(self.ds, 'dev2')
        self.dev2['dev'] = '/dev/2'
        self.reg = device.DevicePathRegistry()

    def test_assign_free(self):
        lst = set(['/dev/1', '/dev/2'])
        av = lambda: self.reg.check_available(lst)
        self.assertSetEqual(av(),  lst)
        r = self.reg.assign(self.dev1['dev'], self.ds['fullpath'])
        self.assertTrue(r)
        self.assertSetEqual(av(), set(['/dev/2']))
        # unassign from other server should fail
        self.assertFalse(self.reg.free(self.dev1, 'blabla'))
        # assign to other server should fail
        self.assertFalse(self.reg.assign(self.dev1, 'blabla'))
        # reserve to other server should fail
        self.assertFalse(self.reg.reserve(self.dev1, 'blabla'))
        # reserve dev2
        r = self.reg.reserve(self.dev2['dev'], self.ds['fullpath'])
        self.assertTrue(r)
        # reservation should also make the device unavailable
        self.assertEqual(av(),  set())
        # freeing
        self.assertTrue(self.reg.free(self.dev1, self.ds))
        self.assertSetEqual(av(),  set(['/dev/1']))
        self.assertTrue(self.reg.free(self.dev2, self.ds))
        self.assertSetEqual(av(),  lst)
        # Removal will return True
        self.assertTrue(self.reg.free(self.dev2, self.ds))

    def test_free_all(self):
        self.reg.assign(self.dev1['dev'], self.ds['fullpath'])
        self.reg.assign(self.dev2, self.ds)
        self.assertEqual(len(self.reg['reg']), 2)
        r = self.reg.free_all('blabla')
        self.assertEqual(r, 0)
        r = self.reg.free_all(self.ds)
        self.assertEqual(r, 2)


if __name__ == "__main__":
    unittest.main()
