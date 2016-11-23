#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest
import os
import SimpleHTTPServer
import SocketServer
import threading

from misura.droid import device

print 'Importing ', __name__

PORT = 8006


def setUpModule():
    global httpd, server, PORT
    print 'Starting ', __name__
    Handler = SimpleHTTPServer.SimpleHTTPRequestHandler
    httpd = SocketServer.TCPServer(("", 0), Handler)
    ADDRESS, PORT = httpd.server_address
    print 'Preparing server', ADDRESS, PORT
    # A separate server object for handling one request at a time
    server = threading.Thread(target=httpd.handle_request)
    os.environ['http_proxy'] = ''


class HTTP(unittest.TestCase):

    def setUp(self):
        self.d = device.HTTP(node='http://127.0.0.1:{}'.format(PORT))

    def test_connect(self):
        global server
        os.environ['http_proxy'] = ''
        self.assertFalse(self.d['isConnected'])
        server.start()
        self.d.connection()
        print 'JOINING'
        server.join()
        self.assertTrue(self.d['isConnected'])


if __name__ == "__main__":
    unittest.main()
