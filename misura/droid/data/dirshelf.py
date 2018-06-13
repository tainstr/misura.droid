# -*- coding: utf-8 -*-
"""Shelve-like object implemented using filesystem-level FileBuffer circular buffer."""
import os
import shutil
from cPickle import HIGHEST_PROTOCOL
from copy import deepcopy
from filebuffer import FileBuffer
from .. import utils


def new_name(base):
    """Find a new progressive name for subdirectory of `base`"""
    lst = os.listdir(base)
    N = len(lst)
    while str(N) in lst:
        N += 1
    return str(N)

sep = '\\' if os.name=='nt' else '/'

class DirShelf(FileBuffer):

    """Permanent object storage with good concurrency.
    Each key is saved/red to/from a file in a directory (possibly in the shared memory space /dev/shm.
    Keys must be valid file names. Values are automatically pickled/unpickled. """
    dir = False

    def __init__(self, basedir, viewdir=False, desc=False, protocol=HIGHEST_PROTOCOL, private_cache=False, **k):
        """`basedir`: RAM directory for sharing object pickles and current values"""
        super(DirShelf, self).__init__(private_cache=private_cache)
        self.idx_entries = 100
        if not basedir.endswith(sep):
            basedir += sep
        self.basedir = basedir
        if not os.path.exists(self.basedir):
            print 'DirShelf: creating basedir', self.basedir
            os.makedirs(self.basedir)
        if viewdir:
            if not viewdir.endswith(sep):
                viewdir += sep
        else:
            viewdir = new_name(self.basedir) + sep
        self.viewdir = viewdir
        self.dir = os.path.join(self.basedir, self.viewdir)
        self.protocol = protocol
        if desc:
            self.update(desc)

    def close(self):
        FileBuffer.close(self, self.dir, hard=True)
        if not os.path.exists(self.dir):
            return True
        shutil.rmtree(self.dir, ignore_errors=True)
        # Recreate the directory to avoid future name conflicts
        if not os.path.exists(self.dir):
            os.mkdir(self.dir)
        return True

    # FIXME: this should be removed.
    # Probably it's a bit overzealous and can create problems (E.g.: in unit tests...)
    # It can happen that this is called when most of objects are already
    # destroyed (os.path)
    def __del__(self):
        self.close()

    def fp(self, key):
        """Object path"""
        if key == '':
            return os.path.join(self.dir, 'self')
        return os.path.join(self.dir, str(key), 'self')

    def set(self, key, val, t=-1, newmeta=True):
        if newmeta:
            val = deepcopy(val)
            cur = val.pop('current')
            if val['handle'] != key:
                print('Handle mismatch: {} {} {}'.format(key, val['handle'], self.dir))
                val['handle'] = key
            newmeta = val
        else:
            cur = val
        self.write(self.fp(key), cur, t=t, newmeta=newmeta)
        
    __setitem__ = set

    def set_current(self, key, val, t=-1):
        self.set(key, val, t, newmeta=False)

    def get(self, key, *a, **k):
        meta = k.get('meta', True)
        r = self.read(self.fp(key), meta=meta)
        return r

    def __getitem__(self, key):
        return self.get(key, meta=True)

    def has_key(self, key):
        r = os.path.exists(self.fp(key))
        return r
    
    def __contains__(self, key):
        return self.has_key(key)

    def __delitem__(self, key):
        path = self.dir + key
        super(DirShelf,self).close(path)
        shutil.rmtree(path)

    def update(self, desc):
        for k, v in desc.iteritems():
            self.set(k, v, newmeta=True)

    def keys(self, key=''):
        if not os.path.exists(self.dir):
            return []
        k = os.listdir(self.dir + key)
        if 'self' in k:
            k.remove('self')
        return k

    def items(self, key=''):
        return [(k, self.get(k)) for k in self.keys(key)]
    # Not real iterators, to save I/O

    def iteritems(self, key=''):
        it = self.items(key)
        for k, v in it:
            assert v is not False
            yield k, v

    def iterkeys(self, key=''):
        ks = self.keys(key)
        for k in ks:
            yield k

    def itervalues(self, key=''):
        it = self.items(key)
        for k, v in it:
            yield v
            
    def values(self, key=''):
        return [it[1] for it in self.items(key)]
            
    def copy(self, key=''):
        """Returns a dictionary containing all items, mimicking dict.copy"""
        res = {}
        for k, v in self.items(key):
            res[k] = v
        return res

    def h_get(self, key, startIdx=0, endIdx=-1):
        """Returns key sequence from startIdx to endIdx"""
        if startIdx == endIdx:
            return self.get_item(self.fp(key), startIdx, meta=False)
        r = self.sequence(self.fp(key), startIdx, endIdx)
        return r

    def h_time_at(self, key, idx=-1):
        """Returns the time of the last recorded point"""
        return self.time(self.fp(key), idx)

    def h_get_time(self, key, t):
        """Searches the nearest point to time `t` and returns its index for option `name`."""
        r = self.get_time_idx(self.fp(key), t)
        return r

    def h_get_history(self, key, t0=-2, t1=0):
        """Returns history vector for option `name` between time `t0` and time `t1`"""
        # Translate time to the past
        t = utils.time()
        if t1 <= 0:
            t1 += t
        if t0 <= 0:
            t0 += t
        # Get the index corresponding to oldest point
        idx0 = self.h_get_time(key, t0)
        # Get the index corresponding to newest point
        idx1 = self.h_get_time(key, t1)
#       print 'h_get_history',t0,t1,idx0,idx1,self.time(self.fp(key),idx0),self.time(self.fp(key),idx1),self.fp(key)
#       assert idx1>=idx0, 'invalid history {}!>={} for {}'.format(idx1, idx0, self.fp(key))
        v = self.h_get(key, idx0, idx1)
        # Nothing found
        if len(v) == 0:
            return False
        return v

    def h_clear(self, key=''):
        """Clears the history registry."""
        self.clear(self.fp(key))
