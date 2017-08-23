# -*- coding: utf-8 -*-
"""
General Sample class
"""
from copy import deepcopy
from misura.droid import device


conf = [
    {"handle": 'T',     "name": "Temperature", "type": 'RoleIO', "unit": 'celsius',
        "options": ['/kiln/', 'default', 'Ts']},
    {"handle": 'initialDimension',  "name": 'Initial sample dimension', "unit": 'micron',
        "current": 0,   "min": 0, "type": 'Float'},
    {"handle": 'ii', "name": 'Sample index on device',  "min": 0, "attr": ['Hidden'],
     "max": 20,     "current": 1, "type": 'Integer'},
    {"handle": 'frame',     "name": 'Last frame',
        "attr": ['Runtime', 'History'], "type": 'Image'},
    {"handle": 'bayes',     "name": 'Last Bayes frame',
        "attr": ['Runtime'], "type": 'Image'},
    {"handle": 'profile',   "name": 'Last profile',
     "current": [(), [], []], "attr": ['Runtime', 'History', 'Hidden'], "type": 'Profile'},
    {"handle": 'filteredProfile',   "name": 'Last profile',
     "current": [(), [], []], "attr": ['Runtime', 'History', 'Hidden'], "type": 'Profile'},
    {"handle": 'recFrame',  "name": 'Record frames',
        "current": True, "type": 'Boolean'},
    {"handle": 'recProfile', "name": 'Record profiles',
        "current": True, "type": 'Boolean'},
]


class Sample(device.Device):

    """Public interface to a Sample description."""
    analyzer = False
    conf_def = deepcopy(device.Device.conf_def + conf)
    suffixes = []
    """List of sub-sample partial object names"""
    part_def = deepcopy(conf_def)
    """Definition for sub-sample partial objects"""
    samples = []
    """List of sub-samples"""

    def __init__(self, parent=None, node='sample', conf_def=False, suffixes=False):
        """For each sample-part suffix, a sub-sample is created being of the same class as self and part_def default configuration."""
        device.Device.__init__(
            self, parent=parent, node=node, conf_def=conf_def)
        if suffixes is not False:
            self.suffixes = suffixes
        self.samples = []
        for suffix in self.suffixes:
            # Create a sub-sample using the same class as "self",
            # so we get the correct analyzer
            part = self.__class__(parent=self,      # same class as itself
                                  node=suffix,
                                  conf_def=self.part_def,       # partial definition
                                  suffixes=[])              # no suffixes
            part['name'] = 'Part ' + suffix
            self.samples.append(part)
        print 'Sample parts', self.devices
        self['recFrame'] = False

    def set_roi(self, roi):
        # TODO: Full validation...?
        if roi[0] < 0:
            roi[0] = 0
        if roi[1] < 0:
            roi[1] = 0
        # Mirror any roi change to rrt
        self['rrt'] = roi
        return roi

    def get_History_attr(self, opt):
        """Return true if History attr is set for option `opt`."""
        a = self.desc.getattr(opt, 'attr')
        if 'History' in a:
            return True
        return False

    def set_History_attr(self, opt, val):
        """Set History attr on option `opt`."""
        a = self.desc.getattr(opt, 'attr')
        old = 'History' in a
        if old == val:
            return val
        if val:
            a.append('History')
        else:
            a.remove('History')
        self.desc.setattr(opt, 'attr', a)
        # Recursively set the option to all sub-samples
        for smp in self.samples:
            smp.desc.setattr(opt, 'attr', a)
        return val

    def get_recFrame(self):
        """The value of recFrame depends on the presence of History attribute on frame option."""
        return self.get_History_attr('frame')

    def set_recFrame(self, val):
        """By setting recFrame, History attribute on frame option is accordingly added or removed."""
        return self.set_History_attr('frame', val)

    def get_recProfile(self):
        """The value of recProfile depends on the presence of History attribute on profile option."""
        return self.get_History_attr('profile')

    def set_recProfile(self, val):
        """By setting recProfile, History attribute on profile/filteredProfile options is accordingly added or removed."""
        r = self.set_History_attr('profile', val)
        r = self.set_History_attr('filteredProfile', val)
        return r
