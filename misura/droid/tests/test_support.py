#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest
import numpy as np
import os
from commands import getoutput as go

from misura.droid import support
from misura.droid.version import __version__

rd = np.random.random


print 'Importing ' + __name__


def setUpModule():
    print 'Starting ' + __name__

def tearDownModule():
    pass


class Support(unittest.TestCase):

    def setUp(self):
        self.s = support.Support()

    def test_get_lib_info(self):
        out0 = support.get_lib_info()
        out1 = self.s['libs']
        print out1
        self.assertEqual(out0, out1)

    def test_get_version(self):
        self.assertEqual(self.s['version'], __version__)

    def test_get_env(self):
        env = self.s['env']
        self.assertIn('misura', env)

    def test_do_backup(self):
        p0 = '/tmp/misuratest/'
        p = p0 + 'source/'
        f = p + 'file'
        p1 = p0 + 'odir/'
        # Clean
        go('rm -rf {}'.format(p0))

        os.makedirs(p)

        open(f, 'w').write('test1')

        of, r = self.s.do_backup(p, p1)
        # Check output
        self.assertTrue(r)
        self.assertIn('./file', r)

        # Check if tar exists
        ls = os.listdir(p1)
        self.assertEqual(len(ls), 1)
        ls1 = ls[0]
        self.assertTrue(ls1.endswith('.tar.bz2'))

        # Change file and try a new backup
        open(f, 'w').write('test2')
        self.s.do_backup(p, p1)
        # Check output
        self.assertTrue(r)
        self.assertIn('./file', r)

        # Check if second tar exists
        ls = os.listdir(p1)
        self.assertEqual(len(ls), 2)
        # Choose the newer one
        ls2 = ls[0]
        if ls2 == ls1:
            ls2 = ls[1]
        self.assertTrue(ls2.endswith('.tar.bz2'))

        # Change again
        open(f, 'w').write('test3')
        # Go in the correct position
        os.chdir('/')
        # Now restore first version
        st, r = self.s.do_restore(p1 + ls1, p)
        print 'Restore 1\n', r
        # Check output
        self.assertTrue(st)
        self.assertIn('./file', r)

        # Check restored file contents
        r = open(f, 'r').read()
        self.assertEqual(r, 'test1')

        # Now restore second version
        st, r = self.s.do_restore(p1 + ls2, p)
        print 'Restore 2\n', r
        # Check output
        self.assertTrue(st)
        self.assertIn('./file', r)

        # Check restored file contents
        r = open(f, 'r').read()
        self.assertEqual(r, 'test2')
        # Clean
        go('rm -rf {}'.format(p0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
