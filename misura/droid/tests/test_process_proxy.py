#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Simple remote object access via FileBuffer."""
import unittest
import os
from time import sleep, time
from traceback import print_exc, format_exc
from multiprocessing import Lock

from misura.droid.process_proxy import ProcessProxy, ProcessProxyManager, ProcessProxyInstantiator

from misura.droid import parameters as params

class DummyCallable(object):

    def __init__(self, a, b=1):
        self.a = a
        self.b = b

    def set(self, name, value):
        setattr(self, name, value)
        return 'set ', name, value

    def get(self, name):
        return getattr(self, name, 'UNDEFINED')
    
    def sleep(self,t):
        sleep(t)
        return True

class TestProcessProxy(unittest.TestCase):

    def test(self):
        pp = ProcessProxy(DummyCallable)
        pp._start(0, b=2)
        for i in xrange(100):
            pp.set('a', i)
            self.assertEqual(pp.get('a'), i)
        os.remove(pp._path + '/pid')
        sleep(1)
        pp._process.terminate()
        
    def test_fail_start(self):
        pp = ProcessProxy(DummyCallable)
        self.assertRaises(RuntimeError, pp._start)
        
    def test_max_restarts(self):
        pp = ProcessProxy(DummyCallable)
        pp._max_restarts = 2
        pp._start(1,2)
        
        os.remove(pp._pid_path)
        sleep(1)
        self.assertFalse(pp._is_alive())
        self.assertEqual(pp.get('a'),1)
        self.assertTrue(pp._is_alive())
        
        os.remove(pp._pid_path)
        sleep(1)
        self.assertFalse(pp._is_alive())
        self.assertEqual(pp.get('a'),1)
        self.assertTrue(pp._is_alive())
        
        os.remove(pp._pid_path)
        sleep(1)
        self.assertFalse(pp._is_alive())
        self.assertRaises(RuntimeError, lambda: pp.get('a'))
        self.assertFalse(pp._is_alive())        
        
    def test_unpicklable_noinit(self):
        pp = ProcessProxy(DummyCallable)
        pp._set_logging(os.path.join(params.rootdir, 'dev','shm','misura','pplog'))
        #pp._log.debug(Lock())
        pp._max_restarts = 1
        l = Lock()
        pp._start(1, l)
        a = lambda: pp.set('a', Lock())
        self.assertRaises(RuntimeError, a)
        os.remove(pp._pid_path)
        pp.get('a')
        pp._stop()
        
    def test_unpicklable_init(self):
        from misura.droid import share
        share.init()
        self.test_unpicklable_noinit()
        share.stop()   
             
    def test_manager(self):
        pm = ProcessProxyManager()
        pm.register('DummyCallable', DummyCallable)
        pp = pm.DummyCallable(1, b=3)
        self.assertTrue(pp._process.is_alive())
        self.assertEqual(pp.get('a'), 1)
        self.assertEqual(pp.get('b'), 3)
        pp._stop()
        
    def test_timestamp(self):
        pp = ProcessProxy(DummyCallable)
        pp._start(1)
        ts = pp._get_timestamp()
        pp.set('a', 2)
        ts1 = pp._get_timestamp()
        self.assertGreater(ts1, ts)
        pp._stop()
        
    def _test_recursion(self):
	return
        pp = ProcessProxy(DummyCallable)
        pp._timeout = 0.001
        pp._max_restarts = -1
        pp._start(1)
        for i in range(2000):
            print('CYCLE',i)
            try:
                pp._start(1)
            except:
                print_exc()


if __name__ == "__main__":
    unittest.main(verbosity=2)
