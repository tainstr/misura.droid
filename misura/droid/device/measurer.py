#!/usr/bin/python
# -*- coding: utf-8 -*-
"""A device hosting one or more samples and operating on them (typically, for measurement)."""
from misura.canon.csutil import initializeme

class Measurer(object):

    """A device hosting one or more samples and operating on them (typically, for measurement).
    Lightweight class for defining additional methods."""
    conf_def = [{"handle": 'nSamples', "name": 'Number of samples', "max": 8, "current": 0, "step": 1, "min": 0, "type": 'Integer',
                 "attr": ['Runtime'], "writeLevel":2},
                {"handle": 'smp0', "name": 'Sample 0 path',
                    "type": 'Role', 'parent': 'nSamples', "writeLevel": 3},
                ]

    @initializeme(repeatable=True)
    def set_nSamples(self, n):
        """Set the number of samples to search in the image. Creates a Role option for each sample."""
        if self.root is not None and self.root['isRunning']:
            self.log.error(
                'Cannot change number of samples while running acquisition.')
            return None
        if n > 16:
            n = 16
        self['running'] = 0
        for i in range(n):
            h = 'smp%i' % i
            # Don't overwrite already existing options
            if (self.desc.has_key(h)):
                continue
            print 'Creating sample', h
            opt = {'name': 'Output Sample %i' % i, 'current': [
                'None', 'default'], 'type': 'Role', 'parent': 'nSamples'}
            self.desc.sete(h, opt)
            self.roledev[h] = (False, False)
        # Remove unnecessary samples
        for i in range(n, 16):
            h = 'smp%i' % i
            if self.desc.has_key(h):
                self.log.debug('Removing sample option', h)
                self.desc.delete(h)
                if self.roledev.has_key(h):
                    self.log.debug('Removing sample role', h)
                    del self.roledev[h]
            else:
                break
#       # Re-init all samples
        self.desc.set('nSamples', n)  # n will be used in init_sample!
        self.init_samples()
        return n

    def iter_samples(self, dsample=False):
        """Generator function returning the configured samples"""
        nSamples = 1
        if dsample is False:
            nSamples = self['nSamples']
        i = 0
        while i < nSamples:
            if dsample is not False:
                yield dsample
                break
            h = 'smp%i' % (i)
            # Retrieve sample object from roledev dictionary mapping
            smp = self.roledev.get(h, (False, False, False))[0]
            #  If no sample was defined, return the error
            if smp is False:
                self.log.debug('No sample defined!', i)
#               break
            yield smp
            i += 1

    def iter_samples_get(self, opt):
        """Iterate over samples collecting their option `opt` in a list."""
        r = []
        for smp in self.iter_samples():
            if smp is False:
                continue
            r.append(smp.get(opt))
        return r

    def init_sample(self, sample, handle):
        return True

    def init_samples(self):
        self.log.debug('init_samples')
        n = 0
        for i, smp in enumerate(self.iter_samples()):
            if not smp:
                continue
            h = 'smp%i' % i
            n += self.init_sample(smp, h)
        return n
