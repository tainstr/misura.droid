#!/usr/bin/python
# -*- coding: utf-8 -*-

import unittest
import shutil
import os
import exceptions
from time import time, sleep

from misura import utils_testing as ut
from misura import share
from misura.droid.data import dirshelf
from misura.droid import utils


dr = ut.params.tmpdir + 'testfb/'
p = dr + 'test'
props = {'a': {'handle': 'a', 'type': 'Object', 'current': [1, 2]}}


class DirShelf(unittest.TestCase):

    def setUp(self):
        self.d = dirshelf.DirShelf(share.dbpath, 'dirshelf')

    def tearDown(self):
        self.d.close()

    def test_update(self):
        d = self.d
        d.update(props)
        p1 = d['a']
        self.assertEqual(p1, props['a'])

    def test_nocron(self):
        d = self.d
        d.idx_entries = 1
        d.set('a', 1, newmeta=False)
        t = time()
        d.set('a', 2, newmeta=False)

        self.assertEqual(d.info[:2], (0, 2))
        self.assertAlmostEqual(d.info[2], t, delta=0.001)
        d.set('a', 3, newmeta=False)
        self.assertEqual(d.get('a', meta=False), 3)
        for i in range(10):
            t = time()
            d.set('a', i, newmeta=False)
            self.assertEqual(d.get('a', meta=False), i)
            self.assertEqual(d.info[:2], (0, i + 4))
            self.assertAlmostEqual(d.info[2], t, delta=0.001)

if __name__ == "__main__":
    unittest.main(verbosity=2)
