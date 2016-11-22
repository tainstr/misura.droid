#!/usr/bin/python
# -*- coding: utf-8 -*-

import unittest
import shutil
import os
import exceptions
import fcntl
from fcntl import flock, LOCK_SH, LOCK_EX, LOCK_NB
from time import time, sleep

from misura import utils_testing as ut

from misura.droid.data import filebuffer

from misura.droid import utils


dr = ut.params.tmpdir + 'testfb/'
p = dr + 'test'


class FileBuffer(unittest.TestCase):

    def setUp(self):
        self.fb = filebuffer.FileBuffer()
        self.fb.cache = {}

    def tearDown(self):
        self.fb.close()
        if os.path.exists(dr):
            shutil.rmtree(dr)

    def test_fopen_fclose(self):
        fb = self.fb
        if os.path.exists(p):
            os.remove(p)
# 		self.assertFalse(os.path.exists(p))
        mm, fd = fb.fopen(p, LOCK_EX)
        self.assertEqual(mm, fb.mm)
        self.assertEqual(fd, fb.fd)
        self.assertTrue(os.path.exists(p))
        self.assertEqual(mm[:2], '-1')
        self.assertTrue(fb.cache.has_key(p))
        self.assertEqual(fb.cache[p], fd)
        # Check thread safety
        self.assertFalse(fb._lock.acquire(False))
        fb.fclose()
        self.assertFalse(fb.mm)
        self.assertTrue(fb._lock.acquire(False))
        fb._lock.release()

    def check_invalid(self, valid=True):
        """Check if the latest entry has invalidated oldest entry."""
        # Oldest entry should not be invalidated,
        # as all values have the same dimension
        fb = self.fb
        fb.fopen(p)
        t, s, e = fb._get_idx(0)
        t1, s1, e1 = fb._get_idx(-1)
        info = fb.info
        fb.fclose()
        # If the oldest entry must be invalid
        if not valid:
            self.assertEqual(s, -1)
            return False
        # The oldest entry is still valid
        self.assertGreater(s, 0)
        # The latest entry comes after in time than the oldest
        self.assertGreater(t1, t)
        # But comes first in position, if it's not the first one!
        if info[0] < fb.idx_entries - 1:
            self.assertGreater(s, s1)
        else:
            self.assertGreater(s1, s)
        return True

    def test_write(self):
        fb = self.fb
        # Fill with 0 values
        for i in range(fb.idx_entries):
            fb.write(p, 0)
        info = fb.get_info(p)
        self.assertEqual(info[:2], (99, fb.idx_entries))
        fb.write(p, 0)
        info = fb.get_info(p)
        self.assertEqual(info[:2], (0, fb.idx_entries + 1))
        self.check_invalid(valid=True)
        # Repeat many times
        for i in range(fb.idx_entries * 2):
            fb.write(p, 0)
            self.check_invalid(valid=True)
        # Check if the writing of a bigger object invalidates subsequent
        # entries
        for i in range(fb.idx_entries - 2):  # avoid re-starting from zero!
            fb.write(p, 'LongPickledObject')
            self.check_invalid(valid=False)
        # But, after that, if the length does not increase or diminish,
        # no indices are invalidated anymore
        for i in range(fb.idx_entries * 2):
            fb.write(p, 0)
            self.check_invalid(valid=True)
        print 'done write'

    def test_sequence(self):
        fb = self.fb
        rg = range(fb.idx_entries)
        for i in rg:
            print 'writing', i
            t0 = time()
            if i == 25:
                t = t0
            fb.write(p, i, t0)
        print 'Sequencing0'
        seq = fb.sequence(p, 0)
        v = [e[1] for e in seq]
        self.assertEqual(v, rg)
        print 'Sequencing1'
        seq = fb.sequence(p, -10)
        v = [e[1] for e in seq]
        self.assertEqual(v, rg[-10:])
        print 'Searching time'
        # Search for time
        i0 = fb.get_time_idx(p, t)
        # Check with lower level
        fb.fopen(p)
        i = utils.find_nearest_val(fb, t, get=fb._time)
        fb.fclose()
        self.assertEqual(i, i0)
        self.assertEqual(i, 25)
        # Get sequence from time to the end
        seq = fb.sequence(p, i)
        self.assertEqual(seq[0][1], 25)
        self.assertEqual(len(seq), fb.idx_entries - 25)
        # Write 10 more than the length, then try again
        [fb.write(p, i + fb.idx_entries, time()) for i in range(10)]
        # time `t` entry should not have been overwritten
        # Search for time again
        i = fb.get_time_idx(p, t)
        # the point slides back by 10, as 10 new points were written
        self.assertEqual(i, 25 - 10)
        # Get sequence from time to the end
        seq = fb.sequence(p, i)
        self.assertEqual(seq[0][1], 25)  # the written data is still the same
        # the sequence is 10 points longer!
        self.assertEqual(len(seq), fb.idx_entries - 25 + 10)

        # Test extremities
        lseq0 = fb.sequence(p, -1)
        self.assertEqual(len(lseq0), 1)
        lastt = fb.get_idx(p, -1)[0]
        lastt2 = fb.get_idx(p, fb.idx_entries - 1)[0]
        self.assertEqual(lastt, lastt2)
        lasti = fb.get_time_idx(p, lastt)
        lastt3 = fb.get_idx(p, lasti)[0]
        self.assertEqual(lastt3, lastt)
        # The last point must be the same
        self.assertEqual(fb.idx(
            lasti), fb.idx(-1), msg="Last time does not return to last idx {}".format(lasti))
        self.assertEqual(lasti, fb.idx_entries - 1)
        # Check the items retrieved at those indexes are the same
        self.assertListEqual(fb.get_item(p, -1), fb.get_item(p, lasti))
        # Thus, the sequence from the lasti should be the same than from idx=-1
        lseq1 = fb.sequence(p, lasti)
        self.assertListEqual(lseq0, lseq1)

        # Out of boundaries get_time_idx
        self.assertEqual(fb.get_time_idx(p, 0), 0)
        self.assertEqual(fb.get_time_idx(p, t + 100), -1)

    def test_idx(self):
        """Index conversions"""
        fb = self.fb
        fb.fopen(p)
        self.assertEqual(fb.idx(0), fb.idx(fb.idx_entries))
        self.assertEqual(fb.idx(-1), fb.idx(fb.idx_entries - 1))
        fb.fclose()
        [fb.write(p, i) for i in range(10)]
        self.assertTupleEqual(fb.get_idx(p, -1), fb.get_idx(p, 9))
        # At some point, past the end
        [fb.write(p, i) for i in range(fb.idx_entries)]
        self.assertTupleEqual(
            fb.get_idx(p, -1), fb.get_idx(p, fb.idx_entries - 1))

    def test_get_time_idx(self):
        fb = self.fb
        self.assertEqual(fb.idx_entries, 100)
        for i in range(10):
            # Record fifth time
            t0 = time()
            if i == 5:
                t = t0
            fb.write(p, i, t0)
        # Search for fifth time index
        self.assertEqual(fb.get_time_idx(p, t), 5)
        # Out of boundaries values
        self.assertEqual(fb.get_time_idx(p, 0), 0)
        self.assertEqual(fb.get_time_idx(p, time()), -1)

    def test_clear(self):
        fb = self.fb
        meta = 'metainfo'
        print 'Writing'
        [fb.write(p, i, newmeta=meta) for i in range(10)]
        print 'Getting last item'
        last = fb.get_item(p, -1)
        print 'Clearing'
        fb.clear(p)
        print 'last1'
        last1 = fb.get_item(p, -1)
        self.assertEqual(last, last1)
        self.assertEqual(fb.get_info(p)[:2], (0, 1))
        print 'done clear'

    def test_nocron(self):
        """Not keeping cronology"""
        fb = self.fb
        fb.idx_entries = 1
        [fb.write(p, i) for i in range(10)]
        self.assertTupleEqual(fb.get_idx(p, -1), fb.get_idx(p, 9))
        self.assertTupleEqual(fb.get_idx(p, 0), fb.get_idx(p, 9))
        self.assertEqual(fb.high, 0)
        self.assertEqual(fb.count, 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
