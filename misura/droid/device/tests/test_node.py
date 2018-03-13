#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest
import os
from misura.canon.option import ao

from misura.droid import device
from misura.droid import parameters as params
from . import testdir

# Need to import data in order to register Conf obj

print('Importing', __name__)


def setUpModule():
    print('Starting', __name__)
    #ut.parallel(1)


def tearDownModule():
    pass
    #ut.parallel(0)


class Node(unittest.TestCase):

    def setUp(self):
        """Prepare a minimal tree"""
        params.confdir = testdir
        self.root = device.Node(node='root')
        print(self.root.desc.describe())
        self.sub = device.Node(parent=self.root, node='sub')
        name = ao({},'name', 'String')['name']
        self.sub.sete('name', name.copy())
        self.subA = device.Node(parent=self.root, node='subA')
        self.subA.sete('name', name.copy())
        self.sub2 = device.Node(parent=self.sub, node='sub2')
        self.sub2.sete('name', name.copy())

    def test_parent(self):
        self.assertIs(self.sub.parent(), self.root)
        self.assertIs(self.sub2.parent(), self.sub)

    def test_list(self):
        self.sub['name'] = 'subname'
        self.subA['name'] = 'subnameA'
        self.sub2['name'] = 'subname2'
        self.assertEqual(
            self.root.list(), [('subname', 'sub'), ('subnameA', 'subA')])
        self.assertEqual(self.sub.list(), [('subname2', 'sub2')])
        self.assertEqual(self.subA.list(), [])
        self.assertEqual(self.sub2.list(), [])

    def test_flatten(self):
        flat = [id(obj) for obj in self.root.flatten()]
        teor = [id(obj) for obj in [self.sub, self.sub2, self.subA]]
        self.assertEqual(flat, teor)

    def test_devpath(self):
        self.assertEqual(self.root['devpath'], 'root')
        self.assertEqual(self.sub['devpath'], 'sub')
        self.assertEqual(self.subA['devpath'], 'subA')
        self.assertEqual(self.sub2['devpath'], 'sub2')

    def test_get_fullpath(self):
        self.assertEqual(self.root['fullpath'], '/')
        self.assertEqual(self.sub['fullpath'], '/sub/')
        self.assertEqual(self.sub2['fullpath'], '/sub/sub2/')
        self.assertEqual(self.subA['fullpath'], '/subA/')
    
    def test_conf_dir(self):
        self.assertEqual(
            self.root.conf_dir, testdir)
        self.assertEqual(
            self.sub.conf_dir, testdir + 'sub/')
        self.assertEqual(
            self.sub2.conf_dir, testdir + 'sub/sub2/')
        self.assertEqual(
            self.subA.conf_dir, testdir + 'subA/')
        # TODO: Cleanup!
        os.removedirs(self.sub2.conf_dir)
        os.removedirs(self.subA.conf_dir)

    def test_toPath(self):
        self.assertEqual(self.root.toPath('none'), None)
        self.assertIs(self.sub.toPath('sub2'), self.sub2)
        self.assertIs(self.root.toPath('sub/sub2'), self.sub2)

    def test_searchPath(self):
        p = self.root
        self.assertFalse(p.searchPath('None'))
        self.assertEqual(p.searchPath('/sub/'), 'sub')
        self.assertEqual(p.searchPath('/subA/'), 'subA')
        self.assertEqual(p.searchPath('/sub/sub2/'), 'sub/sub2')
        self.assertFalse(p.searchPath('/dev/'))

    def test_tree(self):
        t, m = self.root.tree()
        print m
        self.assertEqual(len(t), 3)
        self.assertEqual(t.keys(), ['self', 'sub', 'subA'])
        self.assertEqual(t['sub'].keys(), ['self', 'sub2'])
        t, m = self.sub.tree()
        print m
        self.assertEqual(len(t), 2)
        self.assertEqual(t.keys(), ['self', 'sub2'])


if __name__ == "__main__":
    unittest.main(verbosity=2)
