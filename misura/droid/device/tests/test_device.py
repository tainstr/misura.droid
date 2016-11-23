#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest
import os
from copy import deepcopy

from misura.canon.option import ao
from misura.droid import device

from misura.droid.data.tests import testdir

print 'Importing', __name__


def setUpModule():
    print 'Starting', __name__


class Device(unittest.TestCase):

    def setUp(self):
        self.nodp = device.Device()
        self.dp = device.Device()

    @unittest.skip('')
    def test_model(self):
        device.Device(self.dp, 'pippo')
        print self.dp.devices
        mod = self.dp.model()
        print mod
        self.assertDictEqual(
            {'pippo': {'self': 'device'}, 'self': 'device'}, mod)

    def test_nodp(self):
        dev = self.nodp
        self.assertTrue(dev.desc.has_key('dev'))
        self.assertEqual(dev['devpath'], 'dev')
        self.assertEqual(dev['dev'], 'dev')

    def test_dp(self):
        dev = self.dp
        dev.desc.setConf_dir(testdir)
        dev.desc.load('Conf')
        self.assertEqual(dev['name'], 'Simulator')

    def test_list_available_devices(self):
        self.assertEqual(device.Device.list_available_devices(), {})
        device.Device.available = {'test': 'test'}
        self.assertEqual(
            device.Device.list_available_devices(), {'test': 'test'})

    def test_init_instrument(self):
        self.dp.save('default')
        self.dp['devpath'] = 'blabla'
        self.dp['name'] = 'pippo'
        self.assertEqual(self.dp.desc['name'], 'pippo')
        self.dp.init_instrument()
        self.assertEqual(self.dp['name'], 'dev')
        self.assertEqual(self.dp['devpath'], 'blabla')
        os.remove(self.dp.getConf_dir() + '/default.csv')
        # TODO: test with different instrument names etc...

    def test_applyDesc(self):
        class SubDevice(device.Device):
            hardvar = 0
            softvar = 0

            def set_hard(self, val):
                self.hardvar = val
                return val

            def set_soft(self, val):
                self.softvar = val
                return val
        dev = SubDevice(node='null')
        self.assertTrue(dev.desc.has_key('name'))
        print 'KEYS', dev.desc.keys()
        d = dev.describe()
        self.assertTrue(d.has_key('name'))
        # Keep current config
        oldd = deepcopy(d)
        # Modify a copy of current config
        d['dev']['current'] = 'dev0'
        d['devpath']['current'] = '/dev/0/1/'
        d['name']['current'] = 'pippo'
        del d['zerotime']
        # Apply modified config to dev
        dev.applyDesc(d)
        # Should maintain dev and devpath
        for k in ('dev', 'devpath'):
            self.assertEqual(dev[k], oldd[k]['current'])
        # Should update any other property
        for k in ('name',):
            self.assertEqual(dev[k], d[k]['current'])
        # Should not delete missing keys
        self.assertTrue(dev.desc.has_key('zerotime'))

        # Test Hardware triggers
        dev.hardvar = 0
        h = ao({}, 'hard', type='Integer', attr=['Hardware'])
        h = ao(h, 'soft', type='Integer')
        dev.update(h)

        self.assertEqual(dev['hard'], dev.hardvar)
        self.assertEqual(dev['soft'], dev.softvar)
        dev['hard'] = 3
        dev['soft'] = 3
        self.assertEqual(dev['hard'], dev.hardvar)
        self.assertEqual(dev['soft'], dev.softvar)

        h['hard']['current'] = 5
        h['soft']['current'] = 5
        dev.applyDesc(h)
        # Both current values should be updated
        self.assertEqual(dev['hard'], 5)
        self.assertEqual(dev['soft'], 5)
        # The set_hard should be triggered:
        self.assertEqual(dev['hard'], dev.hardvar)
        # The set_soft should NOT be triggered:
        self.assertEqual(dev.softvar, 3)

    def test_io(self):
        dev = self.nodp
        io = dev.io('zerotime')
        self.assertNotEqual(io, None)
        self.assertEqual(io.get(), dev['zerotime'])
        io.set(10)
        self.assertEqual(io.get(), dev['zerotime'])
        dev['zerotime'] = 20
        self.assertEqual(io.get(), dev['zerotime'])

    def test_RoleIO(self):
        dev = self.nodp
        # Create a linked option
        dev.desc.sete('rio',
                      {'options': ['/', '', 'zerotime'], 'type': 'RoleIO'})
        # A get() should return linked value
        self.assertEqual(dev['rio'], dev['zerotime'])
        # Which also becomes the current in-memory value
        self.assertEqual(dev.desc.get('rio'), dev['zerotime'])
        # If zerotime changes, rio changes
        dev['zerotime'] += 1
        # until get() request arrives, the in-memory value does not change
        self.assertEqual(dev.desc.get('rio'), dev['zerotime'] - 1)
        # A get() request updates the in-memory value
        self.assertEqual(dev['rio'], dev['zerotime'])
        dev['zerotime'] += 1
        # Define an option linked to rio (a chain of links)
        dev.desc.sete('rio2',
                      {'options': ['/', '', 'rio'], 'type': 'RoleIO'})
        # Calling the head of a chain of links will return the end of the
        # referred
        self.assertEqual(dev['rio2'], dev['zerotime'])
        # Calling get on a link will NOT update all downstream links until the referred
        # Because map_role_dev points straight to the referred
        self.assertEqual(dev.desc.get('rio'), dev['zerotime'] - 1)

        # Setting a RoleIO should reflect write to referred
        old = dev['zerotime']
        dev['rio'] += 1
        self.assertEqual(dev['zerotime'], old + 1)
        
    def test_wiring(self):
        device.Device(self.nodp, 'dev1')
        self.nodp.desc.sete('role',
                      {'current': ['/dev1/', 'default'], 'type': 'Role'})
        self.nodp.map_role_dev('role')
        self.assertIn('digraph', self.nodp.wiring())

    def test_lock(self):
        # Non-blocking
        self.nodp.lock()
        a = self.nodp.lock(blocking=False)
        self.assertFalse(a)
        self.nodp.unlock()
        # new lock
        a = self.nodp.lock()
        self.assertTrue(a)
        self.nodp.unlock()
        # Blocking
        a = self.nodp.lock()
        self.assertTrue(a)
        self.nodp.unlock()

    def test_list(self):
        self.assertEqual(self.dp.devices, [])
        device.Device(self.dp, 'dev1')
        self.dp.dev1['name'] = 'device'
        v = self.dp.list()
        self.assertEqual(v, [('device', 'dev1')])

    def test_get_running(self):
        self.assertFalse(self.dp['running'])
        # No process anyway!
        self.dp.desc.set('running', 1)
        self.assertFalse(self.dp['running'])
        # Fake running
        self.dp['pid'] = os.getpid()
        self.dp.desc.set('running', 1)
        self.assertEqual(self.dp['running'], 1)
        # Fake stopping
        self.dp.desc.set('running', 0)
        self.assertEqual(self.dp['running'], 2)
        self.dp['pid'] = 0
        self.assertEqual(self.dp['running'], 0)

if __name__ == "__main__":
    unittest.main()
