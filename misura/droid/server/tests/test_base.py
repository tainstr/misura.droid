#!/usr/bin/python
# -*- coding: utf-8 -*-

import unittest

from misura.droid import server
from misura.droid import parameters as params
from misura.droid import storage, share

print 'Importing ' + __name__
params.testing = True


def setUpModule():
    print 'Starting ' + __name__

class BaseServer(unittest.TestCase):

    def setUp(self):
        self.srv = server.BaseServer(share.DummyManager())

    def test_register(self):
        obj = storage.Storage(self.srv)
        print self.srv, obj
        self.assertTrue(hasattr(self.srv, 'storage'))
        self.assertIsInstance(self.srv.storage, storage.Storage)

    def test_mapdate(self):
        v0 = self.srv['name']
        idx, rep = self.srv.mapdate([('name', 0)])
        self.assertEqual(idx[0], 0)
        self.assertEqual(rep[0], v0)
        t0 = self.srv.time()
        idx, rep = self.srv.mapdate([('name', t0)])
        self.assertEqual(len(idx), 0)
        self.assertEqual(len(rep), 0)
        self.srv['name'] = 'newname'
        idx, rep = self.srv.mapdate([('name', t0)])
        self.assertEqual(idx[0], 0)
        t1 = self.srv.time()
        v1 = rep[0]
        self.assertGreater(t1, t0)
        self.assertEqual(v1, 'newname')
        # Change readLevel so it cannot be accessed
        self.srv.setattr('name', 'readLevel', 5)
        # Default level is 0, so I should not access
        idx, rep = self.srv.mapdate([('name', t0)])
        self.assertEqual(len(idx), 0)
        # If I specify an upper/equal readlevel, mapdate should return the
        # results.
        idx, rep = self.srv.mapdate([('name', t0)], readLevel=5)
        self.assertEqual(len(idx), 1)
        self.assertEqual(rep[0], v1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
