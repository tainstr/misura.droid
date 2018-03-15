#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest
import tables
from tables.nodes import filenode
from pickle import loads

from misura.canon.option import ao
from misura.canon import csutil
from misura.droid import share
from misura.droid import device, server, storage

from misura.droid import instrument
from misura.droid.instrument.tests import testdir
testdir += '/data/'

def setUpModule():
    print 'Starting ' + __name__


def tearDownModule():
    pass


def set_options(obj):
    obj.sete('val', {'type': 'Float', 'attr': ['History']})
    obj.sete('str', {'type': 'String', 'attr': ['History']})
    obj.sete('bin', {'type': 'Binary', 'attr': ['History']})
    obj.sete('prf', {'type': 'Profile', 'attr': ['History']})
    obj.sete('img', {'type': 'Image', 'attr': ['History']})

hdfpath = testdir + 'intrument.instrument.h5'

cf0 = testdir + 'AnalyzerHsm.AnalyzerShape.Analyzer.Device.csv'


class InstrumentSetup(unittest.TestCase):

    def setUp(self):
        self.root = server.BaseServer(share.SharingManager())
        storage.Storage(parent=self.root)  
        self.obj = instrument.Instrument(self.root, 'instrument')
        self.obj.outFile = False
        # Create a device server with some sub-devices
        self.dsrv = device.DeviceServer(self.root, 'dsrv')
        self.root.deviceservers = [self.dsrv]
        self.dev1 = device.Device(self.dsrv, 'dev1')
        self.dev2 = device.Device(self.dsrv, 'dev2')
        self.assertEqual(len(self.dsrv.devices), 2)

        set_options(self.dev1)
        set_options(self.dev2)
        set_options(self.obj)
#		self.obj.devices=[self.dev1,self.dev2]
        self.obj.measure['measureFile'] = hdfpath
        d = {}
        ao(d, 'dev1role', 'Role', ['/dsrv/dev1/', 'default'])
        ao(d, 'dev2role', 'Role', ['/dsrv/dev2/', 'default'])

        self.obj.desc.update(d)
        self.d = d
        
        self.obj.init_instrument()

    def tearDown(self):  # self.obj.devices=[self.dev1,self.dev2]
        print('#### TEAR DOWN ####\n' * 5)
        if self.obj.outFile is not False:
            self.obj.outFile.close()
        self.root.close()
        print('Done')




class Instrument(InstrumentSetup):
    #	@unittest.skip('')

    def test_sub(self):
        self.assertTrue(hasattr(self.obj, 'measure'))
        self.assertTrue(hasattr(self.obj, 'sample0'))
        print('ONLY SUBDEVICE', self.obj.devices[0]['devpath'])
        self.assertEqual(len(self.obj.devices), 2)
        self.assertEqual(self.obj.sample0.devices, [])

#	@unittest.skip('')
    def test_samples(self):
        """Check correlation between nSamples defined in measure and nSamples defined in instrument"""
        for n in range(1, 4) + range(3, 1, -1):
            self.obj.measure['nSamples'] = n
            self.assertEqual(len(self.obj.samples), n)
            self.assertEqual(self.obj.measure['nSamples'], n)
            self.assertEqual(self.obj['nSamples'], n)


#	@unittest.skip('')
    def test_mapRoleDev(self):
        self.obj.mapRoleDev()
        print('MAPPED DEVICES', self.obj.mapped_devices)
        self.assertEqual(len(self.obj.mapped_devices), 3)  # smp+2 dev, no kiln
        self.assertFalse(self.obj.kiln)
        t, m = self.root.tree()
        self.assertSetEqual(
            set(t.keys()), set(['instrument', 'self', 'dsrv', 'storage']))
        self.assertSetEqual(set(t['instrument'].keys()),
                            set(['self', 'measure', 'sample0']))

#	@unittest.skip('')
    def test_init_instrument(self):
        self.dev1['name'] = 'defaultdev'
        self.dev1.desc.save('default')
        self.dev1['name'] = 'modev'
        self.dev2['name'] = 'defaultdev2'
        self.dev2['devpath'] = 'dev2mod'
        # init_instrument should cause the loading of saved 'default' setting
        self.obj.init_instrument()
        self.assertEqual(self.dev1['name'], 'defaultdev')
        self.assertEqual(self.dev1['devpath'], 'dev1')
        self.assertEqual(self.dev2['name'], 'defaultdev2')
        # Devpath should never be overwritten by a conf load
        self.assertEqual(self.dev2['devpath'], 'dev2mod')

    @unittest.skip('')
    def test_init_storage(self):
        self.obj.mapRoleDev()
        self.obj.init_storage()
        of = self.obj.outFile
        # Check root nodes
        self.assertEqual(of.list_nodes('/', 'Group'),
                         ['dsrv', 'instrument'])
        self.assertEqual(of.list_nodes('/dsrv', 'Group'),
                         ['dev1', 'dev2'])
        # Check dev1 nodes
        devnodes = ['anerr', 'bin', 'img', 'prf', 'str', 'val']
        self.assertEqual(of.list_nodes('/dsrv/dev1'),
                         devnodes)
        self.assertEqual(of.list_nodes('/dsrv/dev2'),
                         devnodes)

import numpy as np
rd = np.random.random
from time import sleep, time
import multiprocessing


#@unittest.skip('')
class SimpleAcquisition(InstrumentSetup):

    """Simple acquisition test. Verify reference memorization during parallel processing."""

    @classmethod
    def setUpClass(cls):
        cls.N = 100
        cls.slp = .1
        cls.pos = range(cls.N)
        cls.T = [n + 20 for n in cls.pos]

    @classmethod
    def tearDownClass(cls):
        pass

    def parallel_process(self, wait=3, spr=False):
        """Change options over time in a parallel process, 
        to simulate device acquisition cycle"""
        if spr: spr()
        sleep(wait)
        for i, pos in enumerate(self.pos):
            T = self.T[i]
            self.obj.sample0['anerr'] = pos
            self.dev1['val'] = T
            self.obj.log.debug('Parallel_process test', i, pos)
            print self.obj.sample0['anerr'], self.dev1['val']
            sleep(self.slp)
        # TODO: change also other reference types, logging, etc

    def test_acquisitionProcess(self):
        """Test if acquisition process works"""
        self.obj.start_acquisition()
        print('acquisition started')
        p = multiprocessing.Process(target=self.parallel_process, 
                                    kwargs={'spr':csutil.sharedProcessResources})
        p.daemon = self.obj._daemon_acquisition_process
        sleep(3)
        p.start()
        sleep(2)
        self.assertFalse(self.obj.root['initTest'])
        self.assertTrue(self.obj.root['isRunning'])

        p.join()
        sleep(3)
        self.obj.stop_acquisition(writeLevel=5)
        hdf = tables.open_file(self.obj.measure.get('measureFile'), mode='r')
        elp = hdf.root.conf.attrs.elapsed
        self.assertGreater(elp, 10)
        node = filenode.open_node(hdf.root.conf, 'r')
        node.seek(0)
        tree = node.read()
        node.close()
        d = loads(tree)
        self.assertEqual(
            elp, d['instrument']['measure']['self']['elapsed']['current'])
        print('ELAPSED', elp)
        T = self.T
        pos = self.pos
        sT = hdf.root.dsrv.dev1.val.cols.v
        spos = hdf.root.instrument.sample0.anerr.cols.v
        # Few more points at the beginning!
        self.assertEqual(len(sT), self.N)
        self.assertEqual(len(spos), self.N)
        eT = sT[:] - np.array(T)
        eT = eT.sum()
        epos = spos[:] - np.array(pos)
        epos = epos.sum()
        msg = 'Saved data do not correspond to predetermined values. Total err=%.2f'
        self.assertEqual(eT, 0, msg=msg % eT)
        self.assertEqual(epos, 0, msg=msg % epos)
        hdf.close()


if __name__ == "__main__":
    unittest.main()
