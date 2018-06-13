#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest
import numpy as np
import os

from twisted.web import xmlrpc

from misura.canon import csutil, indexer

from misura.droid import storage
from misura.droid import data
from misura.droid.data.tests import testdir
from misura.droid import process_proxy
from cPickle import dumps, loads
rd = np.random.random


print 'Importing ' + __name__


def setUpModule():
    print 'Starting ' + __name__

m4file = os.path.join(testdir, 'hsm_test.h5')


class FileServer(unittest.TestCase):

    def setUp(self):
        self.fs = storage.FileServer()

    def tearDown(self):
        self.fs.close()

    def test_getSubHandler(self):
        self.assertRaises(storage.TestFileNotFound, self.fs.getSubHandler, '/dev/null/file' )
        f = self.fs.getSubHandler(m4file)
        self.assertIsInstance(f, indexer.SharedFile)
        uid = f.get_uid()
        # Get by uid
        f1 = self.fs.getSubHandler(uid)
        self.assertEqual(f, f1)
        self.assertEqual(self.fs.paths[m4file], uid)
        self.assertEqual(self.fs.tests[uid], f)
        self.assertEqual(self.fs.uids[uid], m4file)

    def test_lookupProcedure(self):
        # Fail by opening non-existent file
        try:
            self.assertRaises(
                xmlrpc.NoSuchFunction, self.fs.lookupProcedure('/dev/null/file'))
        except:
            pass
        # Open existing file and call a method (.header())
        cb = self.fs.lookupProcedure(m4file + '/' + 'header')
        h = cb()
        self.assertIsInstance(h, list)
        self.assertGreaterEqual(len(h), 10)
        # File by uid
        uid = self.fs.paths[m4file]
        cb = self.fs.lookupProcedure(uid + '/' + 'header')
        h1 = cb()
        self.assertEqual(h, h1)


class Storage(unittest.TestCase):

    def setUp(self):
        self.store = storage.Storage(path=testdir)
        b = os.path.join(testdir, 'upload', '')
        if not os.path.exists(b):
            os.makedirs(b)
        for f in os.listdir(b):
            os.remove(os.path.join(b,f))

    def tearDown(self):
        self.store.close()
        
    def test_dump(self):
        loads(dumps(self.store))

    def test_new_path(self):
        fn, sid, uid = self.store.new_path('upload', 'blabla')
        self.assertEqual(fn, os.path.join(self.store.path + 'upload' , 'blabla.h5'))
        self.assertEqual(sid, 'blabla')
        fn1, sid1, uid1 = self.store.new_path('upload', 'blabla')
        self.assertEqual(sid1, 'blabla_2')
        self.assertEqual(fn1, os.path.join(self.store.path + 'upload', 'blabla_2.h5'))
        self.assertNotEqual(uid, uid1)

    def test_new(self):
        from misura.droid import share
        self.store.manager = share.SharingManager()
        f = self.store.new('upload', 'blabla')
        self.assertIsInstance(f, process_proxy.ProcessProxy)
        self.assertEquals(f._cls, data.outfile.OutputFile)
        self.assertEqual(f.get_path(), os.path.join(self.store.path + 'upload', 'blabla.h5'))
        f.close()
    
    @unittest.skip('')
    def test_4_upload(self):
        fp = os.path.join(testdir, 'hsm_test.h5')
        csutil.chunked_upload(self.store.upload, fp)

    def test_diskUsage(self):
        print self.store['diskUsage']


if __name__ == "__main__":
    unittest.main(verbosity=2)
