#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest
from misura.droid import device

print 'Importing', __name__


def setUpModule():
    print 'Starting', __name__


class FakeMeasurer(device.Node, device.Measurer):

    """Fake class, inheriting both Measurer and Node"""
    pass


class TestMeasurer(unittest.TestCase):

    def setUp(self):
        self.m = FakeMeasurer()
        self.m.sete('nSamples', {'type': 'Integer'})
        self.m.sete('initializing', {'type': 'Boolean'})
        self.m.sete('running', {'type': 'Boolean'})
        
    def verify(self, n):
        # Check that defined samples has their handles
        for i in range(n):
            h = 'smp%i' % i
            self.assertTrue(self.m.has_key(h))
            self.assertTrue(self.m.roledev.has_key(h))
            self.assertEqual(self.m.roledev[h], (False, False))

        self.assertFalse(self.m.has_key('smp%i' % n))
        self.assertFalse(self.m.roledev.has_key('smp%i' % n))
        self.assertFalse(self.m.has_key('smp%i' % (n + 1)))
        self.assertFalse(self.m.roledev.has_key('smp%i' % (n + 1)))
        sl = [s for s in self.m.iter_samples()]
        self.assertEqual(sl, [False] * n)

    def test_nsamples(self):
        # After init, no sample is defined
        self.verify(0)
        self.m['nSamples'] = 4
        self.verify(4)
        self.m['nSamples'] = 8
        self.verify(8)
        self.m['nSamples'] = 5
        self.verify(5)


if __name__ == "__main__":
    unittest.main()
