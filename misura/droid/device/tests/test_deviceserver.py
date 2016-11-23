#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest
from misura.canon.option import ao
from misura.droid import device

from misura.server import BaseServer

print 'Importing', __name__


def setUpModule():
    print 'Starting', __name__


class DummyServedDevice(device.Device):
    pass


class DeviceServer(unittest.TestCase):

    def setUp(self):
        self.root = BaseServer()
        self.ds = device.DeviceServer(self.root, 'srv')
        self.dev1 = device.Device(self.ds, 'dev1')
        self.dev1['dev'] = '/dev/1'
        self.dev2 = device.Device(self.ds, 'dev2')
        self.dev2['dev'] = '/dev/2'

        self.reg = device.DevicePathRegistry()

    def test_search_opt(self):
        self.assertTrue(self.ds.search_opt('dev', '/dev/1'))
        self.assertTrue(self.ds.search_opt('devpath', 'dev1'))
        self.assertFalse(self.ds.search_opt('dev', '/dev/3'))
        self.assertFalse(self.ds.search_opt('devpath', 'dev3'))
        self.assertTrue(self.ds.search_opt('dev', '/dev/2'))
        self.assertTrue(self.ds.search_opt('devpath', 'dev2'))

    def test_removeNode(self):
        self.ds.naturalNaming()
        self.assertEqual(len(self.ds.devices), 2)
        self.assertTrue(self.ds.removeNode('dev1'))
        self.assertFalse(self.ds.search_opt('dev', '/dev/1'))
        self.assertFalse(self.ds.search_opt('devpath', 'dev1'))
        self.assertNotIn(['/dev/1'], [d['dev'] for d in self.ds.devices])
        self.assertNotIn('dev1', self.ds.subHandlers.keys())
        self.assertEqual(len(self.ds.devices), 1)
        self.assertTrue(self.ds.search_opt('dev', '/dev/2'))
        self.assertTrue(self.ds.search_opt('devpath', 'dev2'))
        self.assertIn(self.dev2, self.ds.devices)

    def test_flatten(self):
        self.assertEqual(self.ds.flatten(), self.ds.devices)

    def test_devlist(self):
        lst = [d['devpath'] for d in self.ds.devices]
        self.assertEqual(self.ds['devlist'].splitlines(), lst)

    def test_init_instrument(self):
        ds = self.ds
        ds.save('default')

        def check(lst):
            ini = ds.init_instrument()
            self.assertEqual(lst, ini)
        # No order defined=devlist order
        lst = ds['devlist'].splitlines()
#       check(lst)
        # No save: order overwritten on reinit
        # FIXME: WHAT DOES IT MEAN!????
        ds['name'] = 'pippo'
        self.assertEqual(ds.desc['name'], 'pippo')
        ds['order'] = 'dev2\ndev1'
        self.assertEqual(ds.desc['order'], 'dev2\ndev1')
        self.assertEqual(
            ds.desc.getKeep_names(), ['fullpath', 'locked', 'dev', 'devpath'])
        ds.init_instrument()
        self.assertEqual(ds.desc['name'], 'srv')
        self.assertEqual(ds.desc['order'], '')
        self.assertEqual(ds['name'], 'srv')
        self.assertEqual(ds['order'], '')
        check(lst)

        # Saved order
        ds['order'] = 'dev2\ndev1'
        ds.desc.save('default')
        check(['dev2', 'dev1'])
        ds['order'] = 'dev1\ndev2'
        ds.desc.save('default')
        check(['dev1', 'dev2'])

        # Check undefined paths appended at the end
        ds['order'] = 'dev1'
        ds.desc.save('default')
        check(['dev1', 'dev2'])

        ds['order'] = 'dev2'
        ds.desc.save('default')
        check(['dev2', 'dev1'])

        ds.desc.remove('default')

    def test_get_rescan(self):
        # Notify dev1, dev2 are really served
        self.ds.ServedClasses = [device.Device]
        device.Device.set_available_devices(['dev1', 'dev2'])
        self.ds.get_rescan()
        self.assertEqual(len(self.ds.devices), 2)
        
        self.ds.sete('scan_DummyServedDevice', ao({},'scan_DummyServedDevice', 'Boolean', current=True)['scan_DummyServedDevice'])
        self.ds.ServedClasses = [DummyServedDevice]
        DummyServedDevice.set_available_devices(['dummy'])
#       # This get_rescan purge dev1, dev2 as they are not officially served
        self.ds.get_rescan()
        self.assertEqual(len(self.ds.devices), 1)
        self.assertEqual(self.ds.devices[0]['fullpath'], '/srv/dummy/')


if __name__ == "__main__":
    unittest.main()
