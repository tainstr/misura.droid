#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest

from misura.droid import server
from misura.droid import share

print 'Importing ' + __name__


def setUpModule():
    print 'Starting ' + __name__

plug="""
misura.droid.users.Users
misura.droid.storage.Storage
misura.droid.support.Support
"""
class MainServer(unittest.TestCase):

    def setUp(self):
        self.srv = server.MainServer(plug=plug, manager=share.DummyManager())

    def test_plugins(self):
        # Load default plugins
        self.assertTrue(hasattr(self.srv, 'users'))
        self.assertTrue(hasattr(self.srv, 'storage'))
        self.assertTrue(hasattr(self.srv, 'support'))
        self.assertEqual(len(self.srv.deviceservers), 0)
        self.assertEqual(len(self.srv.instruments), 0)
        


if __name__ == "__main__":
    unittest.main(verbosity=2)
