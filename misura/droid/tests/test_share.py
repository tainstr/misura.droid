#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import os
import unittest
import pickle
import multiprocessing
import exceptions
from misura.droid import share
from misura.droid import data
from misura.droid import utils


#from misura.data import FileBuffer



@unittest.skip('')
class ShareModule(unittest.TestCase):

    def test_register(self):
        self.assertTrue(share.registered.has_key('SharedFile'))
        self.assertTrue(share.registered.has_key('Database'))


def parallel_dumps(obj):
    """Dummy func which returns a pickled object"""
    return pickle.dumps(obj)


def parallel_func(obj):
    """Calling parallel_dumps in a separate process"""
    p = multiprocessing.Process(target=parallel_dumps, args=(obj,))
    p.daemon = True
    p.start()
    p.join()


def pool_func(*objs):
    """Calling parallel_dumps in a pool of worker processes"""
    print 'Starting pool of workers'
    p = multiprocessing.Pool(2)
    print 'Calling parallel_dumps'
    res = []
    if len(objs) == 0:
        objs = [share.manager.Conf() for i in range(5)]
    for i, obj in enumerate(objs):
        r = p.apply_async(parallel_dumps, (obj,))
        print 'getting results', i
        r = r.get()
        res.append(r)
    print 'closing'
    p.close()
    print 'joining'
    p.join()
    print 'done pool_func'


@unittest.skip('')
class Pickling(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mgr = share.dummy()

    @classmethod
    def tearDownClass(cls):
        cls.mgr.shutdown()

    def stop(self):
        print 'stopping'
        self.mgr.shutdown()
        print'stopped'

    def start(self):
        self.mgr = share.SharingManager()
        self.mgr.start()

    def test_noshare(self):
        from misura import device
        pickle.dumps(data.Conf())
        pickle.dumps(data.CircularBuffer())
        obj = self.mgr.Conf()
        pickle.dumps(obj)
        obj = self.mgr.CircularBuffer()
        pickle.dumps(obj)
        obj = device.Device()
        pickle.dumps(obj.desc)

    def test_share(self):
        self.start()
        self.test_noshare()
        self.stop()

#	@unittest.skip('')
    def test_parallel_noshare(self):
        obj = self.mgr.Conf()
        parallel_func(obj)

#	@unittest.skip('')
    def test_parallel_share(self):
        self.start()
        self.test_parallel_noshare()
        self.stop()

    def test_pool_noshare(self):
        pool_func()

#	@unittest.skip('')
    def test_pool_share(self):
        print 'test_pool_share'
        self.start()
        self.test_pool_noshare()
        self.stop()



@unittest.skip('')
class InitStop(unittest.TestCase):

    def test_initstop(self):
        share.init()
        share.stop()
        share.init()
        share.stop()



@unittest.skip('')
class Parallel(unittest.TestCase):

    @classmethod
    def tearDownClass(cls):
        ut.parallel(0)

    def test_onoff(self):
        from misura.device import Node
        n0 = Node()
        self.assertEqual(n0['devpath'], 'node')
#		raw_input()
        ut.parallel(1)
        n1 = Node()
        print n1.desc.desc.cache
#		raw_input()
        self.assertEqual(n1['devpath'], 'node')
        m = share.cache.get()
        obj = m.Lock()
        obj.acquire()
        obj.release()
#         print 'DEBUGINFO', m._debug_info()
#         print 'IDS', m.get_ids()
        ut.parallel(0)
        n2 = Node()
        print n2.desc.desc.cache
#		raw_input()
        self.assertEqual(n2['devpath'], 'node')
        self.assertEqual(
            m._state.value, multiprocessing.managers.State.SHUTDOWN)
        self.assertRaises(exceptions.EOFError, obj.acquire)
#		del obj
        ut.parallel(1)
        n3 = Node()
        self.assertEqual(n3['devpath'], 'node')
        ut.parallel(0)


class ProcessCache(unittest.TestCase):

    def test(self):
        p = share.ProcessCache()
        p.start()
        m = p.get()
        obj = m.SharedFile()
        self.assertFalse(obj.get_uid())
        p.destroy(m)
        print 'AAAAAAAAAAAA',obj.get_uid(), obj._get_pid()
        m = p.get()
        obj = m.SharedFile()
        pid = obj._get_pid()
        self.assertGreater(pid, 0)
        self.assertNotEqual(pid, os.getpid())
        self.assertTrue(utils.check_pid(pid))
        self.assertEqual(os.kill(pid, 9), None)
        utils.join_pid(pid, 10)
        self.assertFalse(utils.check_pid(pid))


if __name__ == "__main__":
    unittest.main(verbosity=2)
