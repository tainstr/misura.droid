#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Test per Misura Language."""
import unittest
from misura.canon import csutil as utils
from misura.canon.tests import FakeStorageFile, DummyInstrument, checkCompile
from misura.droid import instrument


def setUpModule():
    print 'Starting', __name__

class Measure(unittest.TestCase):

    def setUp(self):
        self.stor = FakeStorageFile()
        self.ins = DummyInstrument('/ins')
        self.ins.root = DummyInstrument('/')
        self.ins.root['isRunning'] = False
        self.ins._parent = self.ins.root
        self.ins['analysis'] = True
        instruments = {}
        for ins in ['', 'hsm', 'flex']:
            itrm = instrument.measure.Measure(node='measure', parent=self.ins)
            #itrm._parent = self.ins
            itrm.outFile = self.stor
            itrm.env.hdf = self.stor
            instruments[ins] = itrm
        self.instruments = instruments
        
        self.ins.outFile = self.stor
        
        
    @classmethod
    def setUpClass(cls):
        super(Measure, cls).setUpClass()
        utils.time_scaled.value = 1
        
    @classmethod
    def tearDownClass(cls):
        super(Measure, cls).tearDownClass()
        utils.time_scaled.value = 0
        
    def test_elapsed(self):
        measure = self.instruments['']
        utils.sh_time_step.value = 10
        self.assertEqual(utils.time(), 10)
        self.ins['zerotime'] = 0
        self.assertEqual(measure['elapsed'], 0)
        self.ins['zerotime'] = 1
        self.assertEqual(measure['elapsed'], 9)
        

    def test_compiling(self):
        for ins, itrm in self.instruments.iteritems():
            itrm.env.tab = FakeStorageFile()
            itrm.compile_scripts(self.stor)
            checkCompile(self, itrm, itrm)

    def test_cooling(self):
        self.test_compiling()
        self.ins.kiln = DummyInstrument()
        
        itrm = self.instruments['']
        print itrm['onKilnStopped']
        itrm.setFlags('onKilnStopped', {'enabled': True})

        itrm['coolingBelowTemp'] = -1
        itrm['coolingAfterTime'] = 10
        tab = itrm.env.hdf

        t0 = tab.t[-1]
        T0 = tab.T[-1]
        self.ins.kiln['cooling'] = True
        self.ins.kiln['coolingStart'] = t0
        self.ins['zerotime'] = tab.t[0] + 1 
        self.ins.kiln['T'] = T0
        print 'ALL SCRIPTS', itrm.all_scripts, itrm.end_scripts
        exe = itrm.all_scripts['onKilnStopped']

        # Time elapsing conditions
        self.ins.root['isRunning'] = True
        self.ins.measure = itrm
        exe.eval(itrm, self.ins)
        self.assertTrue(self.ins.root['isRunning'])
        utils.sh_time_step.value = int(t0 + 10 * 60 + 20)
        self.assertEqual(itrm['elapsed'],t0 + 10 * 60 + 19)
        exe.eval(itrm, self.ins)
        self.assertFalse(self.ins.root['isRunning'])
        
        # Temperature threshold conditions
        utils.sh_time_step.value = int(t0)
        self.ins.root['isRunning'] = True
        self.ins['elapsed'] = t0
        self.ins.kiln['T'] = 1000
        itrm['coolingBelowTemp'] = 900
        exe.eval(itrm, self.ins)
        self.assertTrue(self.ins.root['isRunning'])
        self.ins.kiln['T'] = 899
        exe.eval(itrm, self.ins)
        self.assertFalse(self.ins.root['isRunning'])


if __name__ == "__main__":
    unittest.main()
