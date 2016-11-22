#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest
import os
from misura.droid.data import refupdater, dirshelf
from misura.canon.option import Option
from misura.canon.indexer import SharedFile
from time import time, sleep
print 'Importing', __name__


def setUpModule():
    print 'Starting', __name__

dspath = '/dev/shm/misura/test'


class TestRefUpdater(unittest.TestCase):

    def setUp(self):
        self.zerotime = time()
        self.k = dspath + '/refup/h/self'
        if os.path.exists(self.k):
            os.remove(self.k)
        self.sh = SharedFile('reftest.h5', mode='w')
        self.ru = refupdater.ReferenceUpdater(dspath, self.sh, self.zerotime)
        self.ds = dirshelf.DirShelf(dspath, 'refup', {'h': Option(
            handle='h', type='Integer', attr=['History'], kid='/h')})

    def tearDown(self):
        self.sh.close()
        self.ru.close()
        self.ds.close()

    def changeval(self, nval):
        print 'CHANGEVAL', nval
        t0 = time()
        sleep(0.00001)
        t1 = time()
        self.ds.set_current('h', nval, t1)
        t2 = time()
        self.assertTrue(self.ru.sync())
        rt = self.ru.cache[self.k].mtime
        print '{:f} < {:f} < {:f}'.format(t0, rt, t2)
        self.assertEqual(rt, t1)
        self.assertGreater(rt, t0)
        self.assertLess(rt, t2)

    def test_refupdater(self):
        # FIXME: The reference is created but the first point is missed
        self.ru.nthreads = 1
        self.ru.sync()
        print self.ru.cache
        self.assertTrue(self.ru.cache.has_key(self.k))
        rt = self.ru.cache[self.k].mtime
        self.assertAlmostEqual(rt, self.zerotime, delta=0.1)

        self.changeval(1)

        # Check double appending
        for i in range(10):
            print 'Changing values', i
            self.changeval(i + 2)
        sleep(5)
        for i in range(10):
            print 'Sync', i
            self.ru.sync()
        # Check summary
        for i in range(10):
            print 'Changing values', i
            self.changeval(i + 2)
            sleep(1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
