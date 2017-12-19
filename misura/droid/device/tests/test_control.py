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
    
cal = [[20,120],[100,200],[300,400],[400,500]]

class TestCalibrator(unittest.TestCase):
    
    def setUp(self):
        self.d = device.Device()
        self.d.sete('T', {"type": 'Float', "attr": ['History', 'ReadOnly']})
        self.d.sete('rawT',{"type": 'Float', 'unit': 'celsius'})
        self.d.sete('calibrationT', {"current": [[('Measured', 'Float'), ('Theoretical', 'Float')],
                 [20,20]
                 ],"type": 'Table'})
        device.Calibrator(self.d, 'T')
        
    def test_create(self):
        self.assertIn('T', self.d.controls)
        c = self.d.controls['T']
        self.assertTrue(c._calibration_func is False)
        self.assertTrue(c._inverse_func is False)
        self.assertEqual(c.calibrated(10), 10)
        self.assertTrue(c._calibration_func is None)
        self.assertEqual(c.inverse(10), 10)
        self.assertTrue(c._inverse_func is None)
        
    def test_calibrated(self):
        c = self.d.controls['T']
        self.d['calibrationT']=[self.d['calibrationT'][0]]+cal
        n = c.calibrated(100)
        self.assertFalse(not c.calibration_func)
        self.assertAlmostEqual(n, 200)
        self.assertAlmostEqual(c.calibrated(150), 250)
        
    def test_inverse(self):
        c = self.d.controls['T']
        self.d['calibrationT']=[self.d['calibrationT'][0]]+cal
        self.assertAlmostEqual(c.inverse(100), 0)
        self.assertAlmostEqual(c.inverse(150), 50)     
        
        
    
if __name__ == "__main__":
    unittest.main()