#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest

from misura.droid import server
from misura.droid import share

print 'Importing ' + __name__


def setUpModule():
    print 'Starting ' + __name__

class MainServer(unittest.TestCase):

    def setUp(self):
        self.srv = server.MainServer(manager=share.DummyManager())

    def test_plugins(self):
        # Load default plugins
        self.assertTrue(hasattr(self.srv, 'users'))
        self.assertTrue(hasattr(self.srv, 'storage'))
        self.assertTrue(hasattr(self.srv, 'support'))
        self.assertEqual(len(self.srv.deviceservers), 5)
        self.assertEqual(len(self.srv.instruments), 6)
        


if __name__ == "__main__":
    unittest.main(verbosity=2)
