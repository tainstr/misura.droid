#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest
import numpy as np
import tables

#from misura import utils_testing as ut

from misura.droid.data import sign
from misura.canon import indexer
from . import testdir
rd = np.random.random


print 'Importing ' + __name__


def setUpModule():
    print 'Starting ' + __name__

m4file = testdir + 'hsm_test.h5'
certs = testdir + '../../../tests/data/'


class OutputFile(unittest.TestCase):

    def test_3_signAndVerify(self):
        f = tables.open_file(m4file, mode='r+')
        s = sign(f, cacert=certs + 'cacert.pem', privkey=certs + 'privkey.pem')
        self.assertTrue(s, msg='Signature Failed')
        v = indexer.verify(f)
        self.assertTrue(v, msg='Verification Failed')
        f.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
