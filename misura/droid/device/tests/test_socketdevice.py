#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest
import os
from misura.droid import device

import threading
import socket

print 'Importing ', __name__
PORT = 8003
server = False


def setUpModule():
    print 'Starting ', __name__
    os.environ['http_proxy'] = ''


def start():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Avoid "already in use" error
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('127.0.0.1', PORT))
    srv.listen(1)

    def accept():
        print 'Dummy server waiting for connection...'
        srv.accept()
    server = threading.Thread(target=accept)
    server.start()
    return server


class Socket(unittest.TestCase):

    def setUp(self):
        self.d = device.Socket(node='127.0.0.1:%i' % PORT)

    def tearDown(self):
        self.d.close()

    def test_nodelay(self):
        d = self.d
        server = start()
        d.connection()
        server.join()
        # These works also out-of-connection
        delay = d.com.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
        self.assertEqual(delay, False)
        d['nodelay'] = True
        delay = d.com.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
        self.assertEqual(delay, True)

    def test_connect(self):
        d = self.d
        self.assertEqual(d['addr'], '127.0.0.1')
        self.assertEqual(d['port'], PORT)
        self.assertFalse(d['isConnected'])

        self.assertFalse(d.connection())
        self.assertFalse(d['isConnected'])

        server = start()
        d.connection()
        self.assertTrue(d['isConnected'])
        server.join()

        # Verify new connection to now closed socket
        d.com.close()
        self.assertFalse(d.connection())
        self.assertFalse(d['isConnected'])

# TODO: test enumeration (with generic DeviceServer)

if __name__ == "__main__":
    unittest.main(verbosity=2)
