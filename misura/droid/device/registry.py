# -*- coding: utf-8 -*-
"""Device registry"""
from multiprocessing import Lock
from ..data import DirShelf
from misura.canon.csutil import lockme
from .. import share


conf_def = {
    # devpath:devsrvpath mappings
    'reg': {'handle': 'reg', 'current': {}, 'type': 'Object'},  # Assigned
    'tmp': {'handle': 'tmp', 'current': {}, 'type': 'Object'},  # Reserved
}


def _cvt(path, devsrv):
    """If passed arguments are Devices, retrieve their appropriate `dev` and `fullpath` options."""
    if not isinstance(path, str):
        path = path['dev']
    if not isinstance(devsrv, str):
        devsrv = devsrv['fullpath']
    return path, devsrv


class DevicePathRegistry(object):

    """Registry object for device paths. Assures that a device will not be opened at the same time by two DeviceServer"""
    _lock = Lock()

    def __init__(self):
        self.shelf = DirShelf(share.dbpath, 'reg')
        # Do not record chronology (must be set *before* calling update())
        self.shelf.idx_entries = 1
        # Set current description
        self.shelf.update(conf_def)

    def __getitem__(self, key):
        return self.shelf.get(key, meta=False)

    def __setitem__(self, key, val):
        self.shelf.set(key, val, newmeta=False)

    def _unreg(self, path, devsrv, key='reg'):
        """Remove `path` from the list of already assigned paths to registry `key`.
        Returns False only if path is present but cannot be removed because of devsrv mismatch."""
        path, devsrv = _cvt(path, devsrv)
        r = self[key]
        if not r.has_key(path):
            return True
        if not r[path] == devsrv:
            return False
        del r[path]
        self[key] = r
        return True

    def _free(self, *a):
        """Remove `path` from all registries.
        Returns False if removal fails on any registry."""
        r = self._unreg(*a, key='reg')
        r = r and self._unreg(*a, key='tmp')
        return r

    @lockme()
    def free(self, *a):
        """Locked version of _free()."""
        return self._free(*a)

    def _free_all(self, devsrv, key='reg'):
        """Remove all paths pertaining to a devsrv, from registry `key`."""
        d, dspath = _cvt('', devsrv)
        r = self[key]
        n0 = len(r)
        for p, dsp in r.items():
            if dsp != dspath:
                continue
            del r[p]
        self[key] = r
        return n0 - len(r)

    @lockme()
    def free_all(self, *a):
        """Locked version of _free_all(), from all registries."""
        r = self._free_all(*a, key='reg')
        r += self._free_all(*a, key='tmp')
        return r

    @lockme()
    def purge(self, path):
        """Remove device `path` from all registries. Called on Device.close()."""
        path, s = _cvt(path, '')
        r = self['reg']
        t = self['tmp']
        if r.has_key(path):
            del r[path]
            self['reg'] = r
        if t.has_key(path):
            del t[path]
            self['tmp'] = t

    @lockme()
    def assign(self, path, devsrv, key='reg'):
        """Assign device `path` to `devsrv` path on registry `key`.
        Returns true on success, False if already assigned to another DeviceServer"""
        path, devsrv = _cvt(path, devsrv)
        # Try to free the registries
        if not self._free(path, devsrv):
            print 'DevicePathRegistry.assign: error, already in use.'
            return False
        r = self[key]
        r[path] = devsrv
        self[key] = r
        return True

    def reserve(self, path, devsrv):
        """Assign `path` and ` devsrv` to temporary registry 'tmp'."""
        return self.assign(path, devsrv, key='tmp')

    @lockme()
    def check_available(self, lst=set()):
        """Return unassigned paths in `lst`, removing `failed` paths"""
        assigned = set(self['reg'].keys())
        reserved = set(self['tmp'].keys())
        return set(lst) - assigned - reserved

registry = None


def get_registry():
    global registry
    if registry is None:
        registry = DevicePathRegistry()
    return registry


def delete_registry():
    global registry
    if registry is not None:
        registry.shelf.close()
    registry = None
