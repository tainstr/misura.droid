#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest
import numpy as np
import tempfile
import shutil
import struct
import random
import os

#from misura import utils_testing
from misura.droid import data
from misura.canon import option

from . import testdir
rd = np.random.random

c1 = testdir + 'Conf.csv'
c2 = testdir + 'Conf2.csv'
print 'Importing', __name__


def setUpModule():
    print 'Starting', __name__


class DummyLogDb(object):
    args = None
    kwargs = {}

    def put_log(self, *a, **k):
        self.args = a
        self.kwargs = k


class Conf(unittest.TestCase):

    """Tests Conf features: persistence and history."""

    def setUp(self):
        self.cf = data.Conf()
        self.cf.update(option.ao({}, 'fullpath', type='ReadOnly'))
        self.cf.update(option.ao({}, 'opt', current=0))
        self.cf.update(option.ao({}, 'log', type='Log'))
        self.cfd = tempfile.mkdtemp()
        self.cf.setConf_dir(self.cfd)
        shutil.copy(c1, self.cfd)
        shutil.copy(c2, self.cfd)

    def tearDown(self):
        shutil.rmtree(self.cfd)

    def test_merge_desc(self):
        self.cf.save('default')
        k0 = set(self.cf.desc.keys())
        olde = self.cf['opt']
        self.cf['opt'] = 1200
        ###
        # Merging itself
        self.cf.load('default')
        k1 = set(self.cf.desc.keys())
        newe = self.cf['opt']
        # Maintain same set of keys
        self.assertEqual(k0, k1)
        # Merging should overwrite
        self.assertEqual(newe, olde)

    def test_priority(self):
        self.cf.load(path=c1)
        self.assertTrue(self.cf.has_key('opt'))
        e = self.cf.gete('opt')
        self.assertEqual(
            e['priority'], 0, msg="Wrong priority. real=%i, teor=%i" % (e['priority'], 12))
        self.cf.validate()
        e = self.cf.gete('opt')
        self.assertEqual(
            e['priority'], 0, msg="Wrong priority after validation. real=%i, teor=%i" % (e['priority'], 12))
        d = self.cf.read_preset('Conf2')
        self.cf.merge_desc(d)
        e = self.cf.gete('opt')
        self.assertEqual(
            e['priority'], 0, msg="Wrong priority after merge. real=%i, teor=%i" % (e['priority'], 12))

    def test_readName(self):
        cf = self.cf
        desc = cf.read_preset('Conf')
        self.assertEqual(desc['name']['current'], 'Simulator')

    def test_describe(self):
        self.cf.update(option.ao({}, 'bin', type='Binary'))
        self.cf.update(option.ao({}, 'num', type='Float'))
        self.cf['num'] = np.int32(0)
        self.cf['bin'] = 'binary'
        d = self.cf.describe()
        print 'test_describe', type(d['num']['current']), repr(d['bin']['factory_default'])
        self.assertIsInstance(d['num']['current'], np.int32)
        self.assertEqual(d['bin']['current'], '')

    def test_update(self):
        cf = self.cf
        self.assertEqual(cf['opt'], 0)
        cf.update(option.ao({}, 'opt1', current=1))
        self.assertEqual(cf['opt'], 0)
        self.assertEqual(cf['opt1'], 1)
        cf.update(option.ao(cf.desc, 'opt2', current=2))
        self.assertEqual(cf['opt'], 0)
        self.assertEqual(cf['opt1'], 1)
        self.assertEqual(cf['opt2'], 2)
        cf.update(option.ao({}, 'opt', current=10))
        self.assertEqual(cf['opt'], 10)

    def test_updateCurrent(self):
        self.assertEqual(self.cf['opt'], 0)
        self.cf.updateCurrent({'opt': 1})
        self.assertEqual(self.cf['opt'], 1)

    def test_presets(self):
        cf = self.cf
        cf.update(option.ao({}, 'opt1', current=0))
        # Get preset should return 'factory_default' if not found
        self.assertEqual(cf.get_preset(), 'factory_default')
        cf.update(
            option.ao({}, 'preset', type='Preset', options=[], current='factory_default'))
        desc0 = cf.describe()
        self.assertEqual(cf['preset'], 'factory_default')
        cf.setConf_dir(self.cfd)
        cf.save('test0')
        self.assertEqual(cf['preset'], 'test0')
        self.assertEqual(cf.listPresets(), cf.gete('preset')['options'])
        self.assertEqual(
            cf.listPresets(), ['factory_default', 'Conf', 'Conf2', 'test0'])
        cf['opt'] = 1
        cf.save('test1')
        self.assertEqual(
            set(cf.listPresets()), set(['factory_default', 'Conf', 'Conf2', 'test0', 'test1']))
        cf.set_preset('test0')
        self.assertEqual(cf['opt'], 0)
        cf.set_preset('test1')
        self.assertEqual(cf['opt'], 1)
        # Default loading
        cf['opt'] = 2
        print cf.save('default')
        self.assertEqual(
            set(cf.listPresets()), set(['factory_default', 'Conf', 'Conf2', 'default', 'test0', 'test1']))
        # Create a totally new object
        cf1 = data.Conf(desc=desc0)
        # Set the same confdir: the default.csv file should be red.
        cf1.setConf_dir(self.cfd)
        print cf1.conf_dir, cf1.keys()
        self.assertEqual(cf['opt'], cf1['opt'])

    def test_rename(self):
        cf = self.cf
        cf['opt'] = 0
        cf.save('old_name')
        cf['opt'] = 1
        self.assertTrue(os.path.exists(os.path.join(self.cfd, 'old_name.csv')))
        r = cf.rename('new_name', 'fake_name')
        self.assertTrue(r.startswith('No source'), r)
        
        r = cf.rename('new_name', 'old_name')
        self.assertTrue(r.startswith('Configuration renamed'), r)
        
        cf.set_preset('new_name')
        self.assertEqual(cf['opt'], 0)
        cf['opt'] = 1
        cf.save('old_name')
        r = cf.rename('new_name', 'old_name')
        self.assertTrue(r.startswith('Cannot overwrite'), r)
        
        cf.set_preset('new_name')
        self.assertEqual(cf['opt'], 0)
        r = cf.rename('new_name', 'old_name', True)
        self.assertTrue(r.startswith('Configuration renamed'), r)
        
        cf.set_preset('new_name')
        self.assertEqual(cf['opt'], 1)
        

    def test_keepnames(self):
        cf = self.cf
        cf.update(option.ao({}, 'opt1', current=0))
        cf.update(
            option.ao({}, 'preset', type='Preset', options=[], current='factory_default'))
        cf.setConf_dir(self.cfd)
        # Protect the `opt` name
        cf.setKeep_names(['opt'])
        self.assertEqual(cf.keepnames, ['opt'])
        cf['opt'] = 0
        cf['opt1'] = 5
        cf.save('test')
        self.assertEqual(cf.desc['opt1']['current'], cf.get_current('opt1'))
        cf['opt'] = 1
        cf['opt1'] = 1
        # Current value should be updated
        self.assertEqual(cf.get_current('opt1'), 1)
        self.assertEqual(cf.get_current('opt'), 1)
        # Load previous config
        self.assertEqual(cf.keepnames, ['opt'])
        cf.load('test')
        self.assertEqual(cf.keepnames, ['opt'])
        self.assertEqual(cf.keepnames, cf.getKeep_names())
        # 'opt1' name should be overwritten by the load operation
        self.assertEqual(cf['opt1'], 5)
        # 'opt' name should NOT be overwritten during load, because it is protected
        self.assertEqual(cf['opt'], 1)

    def test_log(self):
        cf = self.cf
        cf.update(option.ao({}, 'log', type='Log'))
        cf.db = DummyLogDb()

        def check_log(set_log, expect_log):
            cf['log'] = set_log
            self.assertEqual(cf['log'], expect_log)
            self.assertEqual(cf.db.args[0], expect_log[1])
            self.assertEqual(cf.db.kwargs.get('p', None), expect_log[0])
            self.assertEqual(cf.db.kwargs.get('o', None), '')

        check_log([10, 'test'], [10, 'test'])
        check_log([20, '<\xeb\xa7\xc1'], [20, u'<\ufffd\ufffd'])

        for i in xrange(100):
            msg = struct.pack("=I", random.randint(0, 4294967295))
            level = random.randint(0, 5) * 10
            cf['log'] = [level, msg]
            out_level, out_msg = cf['log']
            self.assertEqual(out_level, level)
            # Should not raise any exception
            self.assertIsInstance(out_msg, unicode)
            # Should not raise any exception
            out_msg.encode('utf-8', 'strict')

        cf['log']


if __name__ == "__main__":
    unittest.main(verbosity=2)
