# -*- coding: utf-8 -*-
"""Circular buffer implementation"""
from copy import deepcopy
from .. import parameters as params
from misura.canon import csutil
import numpy


def isTime(v):
    try:
        f = float(v[0])
        return True
    except:
        return False


class CircularBuffer(object):

    """Circular buffer implementation for storing History options."""

    def __init__(self, length=params.buffer_length, lst=False):
        self.idx = -1
        # FIXME: trovare un paragone più elegante
        if type(lst) != type(False):
            self.list = lst
            self.idx = len(self.list)
            if len(lst) > 0:
                self.times = numpy.array([float(l[0]) for l in lst])
                self.idx = len(self.times)
        else:
            self.list = [[]] * length
            self.times = numpy.array([0.] * len(self.list))
        # deve essere di tipo lista, altrimenti la concatenazione ha problemi!
        self.list = list(self.list)
        self.empty = self.list[0]
        self.len = len(self.list)

    # L'oggetto deve rimanere picklable.
    def __repr__(self):
        return self.list.__repr__()

    def __str__(self):
        return self.list.__str__()

    def get(self, *a, **b):
        return self.__getitem__(*a, **b)

    def expand(self, n):
        self.list.append([] * n)
        self.len = len(self.list)

    def __len__(self):
        return len(self.list)

    def shift(self, i):
        """Translate relative index `i` by the current buffer position idx, returning absolute list index"""
        # se la richiesta è troppo antica, restituisco il più vecchio
        if abs(i) > self.len:
            return self.shift(0)
        i = (i + self.idx + 1) % self.len
        return i

    def deshift(self, a):
        """Translate absolute list index `a` into relative to the actual buffer position idx"""
        a = a - self.idx - 1
        return a

    def pos(self):
        return self.idx

    def length(self):
        return self.len

    def __getitem__(self, i):
        """Get slice `i` from the current buffer position"""
        if self.idx < 0:
            # Not initialized
            return []
        if getattr(i, 'indices', None) == None:
            i = self.shift(i)
            return self.list[i]
        a = self.idx			# newest
        b = self.shift(0)		# oldest

        # Return the entire vector
        if i.start == i.stop == None:
            print 'return all'
            return self.list[b:] + self.list[:b]

        if i.start != None:
            a = self.shift(i.start)

        if i.stop != None:
            b = self.shift(i.stop)

        if b <= a and i.start != i.stop:
            return self.list[a:] + self.list[:b]
        elif a == b:
            return []
        s = slice(a, b, i.step)
        return self.list[s]

    def __setitem__(self, i, v):
        i = self.shift(i)
        self.list[i] = v
        if isTime(v):
            self.times[i] = v[0]

    def remove(self, val):
        # FIXME: distrugge l'integrità del buffer!
        self.list.remove(val)

    def append(self, v):
        self.idx += 1
        self.idx = self.idx % self.len
        self.list[self.idx] = v
        if isTime(v):
            self.times[self.idx] = float(v[0])
    commit = append

    def get_time(self, t):
        """Search the row index nearest to the requested `t` time"""
        idx = csutil.find_nearest_brute(self.times, t)
        return self.deshift(idx)

    def clear(self):
        for i, foo in enumerate(self.list):
            self.list[i] = deepcopy(self.empty)
        self.len = len(self.list)
        self.times = numpy.array([0.] * self.len)
        self.idx = -1
