#!/usr/bin/python
# -*- coding: utf-8 -*-
import unittest
import os
from nose.tools import assert_equals
from pickle import dumps
from misura.droid import data
from misura.droid.device import configuration


class ConfigurationInterface(unittest.TestCase):

    def setUp(self):
        self.cf = data.Conf()
        self.ci = configuration.ConfigurationInterface(self.cf)
        
    def test_dump(self):
        dumps(self.ci)
    
    @unittest.skip('FIX ME!!!')
    def test_validate_preset_name(self):
        self.ci.setConf_dir('/tmp')
        self.ci.save('default')
        self.ci.save('test')

        self.assertEqual(self.ci.validate_preset_name('test'), 'test')
        self.assertEqual(self.ci.validate_preset_name('default'), 'default')
        # Fallback to default
        self.assertEqual(self.ci.validate_preset_name('pippo'), 'default')
        # Remove default
        self.ci.remove('default')
        self.assertEqual(self.ci.validate_preset_name('test'), 'test')
        # Fallback to factory_default
        self.assertEqual(self.ci.validate_preset_name('pippo'), 'factory_default')
        # Remove test
        self.ci.remove('test')
        # Always fallback to factory_default
        self.assertEqual(self.ci.validate_preset_name('test'), 'factory_default')
        self.assertEqual(self.ci.validate_preset_name('pippo'), 'factory_default')


class PresetSelection(unittest.TestCase):
    def test_defaults_when_nothing_available(self):
        assert_equals(
            'factory_default',
            configuration.select_preset_for_name('any preset name', ())
        )

        assert_equals(
            'default',
            configuration.select_preset_for_name('any preset name', ('default',))
        )

    def test_search_presets_based_on_name(self):
        available_presets = ('a preset', 'preset1', 'preset2', 'preset3')
        preset_name = 'preset1_preset2_preset3'
        assert_equals(
            'preset3',
            configuration.select_preset_for_name(preset_name, available_presets)
        )

        available_presets = (
            'a preset',
            'preset1',
            'preset1_preset2',
            'preset2_preset3'
        )
        preset_name = 'preset2_preset3'
        assert_equals(
            'preset2_preset3',
            configuration.select_preset_for_name(preset_name, available_presets)
        )

        available_presets = (
            'a preset',
            'preset1',
            'preset1_preset2_preset3',
            'preset3'
        )
        preset_name = 'enything_preset1_preset2_preset3'
        assert_equals(
            'preset1_preset2_preset3',
            configuration.select_preset_for_name(preset_name, available_presets)
        )


    def test_presets_from_name(self):
        assert_equals(
            ['preset1'],
            configuration.presets_from_name('preset1')
        )

        assert_equals(
            ['preset1_preset2', 'preset2'],
            configuration.presets_from_name('preset1_preset2')
        )

        assert_equals(
            ['preset1_preset2_preset3', 'preset2_preset3', 'preset3'],
            configuration.presets_from_name('preset1_preset2_preset3')
        )

if __name__ == "__main__":
    unittest.main()
