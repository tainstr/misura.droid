#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Test for Sample object"""
import unittest
from misura.droid import instrument

print 'Importing ' + __name__


def setUpModule():
    print 'Starting ' + __name__


def tearDownModule():
    pass


class DummySample(instrument.Sample):
    suffixes = ['a', 'b', 'c']


class Sample(unittest.TestCase):

    def test_init(self):
        s = instrument.Sample()
        self.assertTrue(s.has_key('anerr'))

    def test_sampleparts(self):
        d = DummySample()
        self.assertEqual(len(d.devices), 3)
        self.assertEqual(d.list(),
                         [('Part a', 'a'), ('Part b', 'b'), ('Part c', 'c')])


if __name__ == "__main__":
    unittest.main()
