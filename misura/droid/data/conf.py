# -*- coding: utf-8 -*-
"""Data management and formats"""
from persistent import PersistentConf
from .. import parameters as params
from .. import utils
from misura.canon import option
from misura.canon import logger
import dirshelf
from cPickle import HIGHEST_PROTOCOL
hp = HIGHEST_PROTOCOL


class Conf(PersistentConf):

    """Share-able configuration class for misura objects."""

    def __init__(self, desc={}, conf_dir='',
                 buffer_length=params.buffer_length, empty=False):
        PersistentConf.__init__(self, conf_dir=conf_dir)
        option.Conf.__init__(self, desc=desc, empty=empty)
        self.buffer_length = buffer_length
        from misura import share
#       print 'initializing data.Conf',len(desc)
        self.desc = dirshelf.DirShelf(basedir=share.dbpath, desc=desc)
        self.kid_base = str(id(self))
        self.log = logger.SubLogger(self)
        self.db = share.database
        # History funcs
        self.h_get = self.desc.h_get
        self.h_time_at = self.desc.h_time_at
        self.h_get_time = self.desc.h_get_time
        self.h_get_history = self.desc.h_get_history
        self.h_clear = self.desc.h_clear

    def close(self):
        print 'Conf.close', self.desc
        self.desc.close()

    @property
    def dir(self):
        return self.desc.dir

    def fp(self, name):
        return self.desc.fp(name)

    def set_current(self, name, nval, t=-1):
        if name == 'log':
            level, message = nval
            message = message.decode('utf-8', errors='replace')
            if self.db:
                self.db.put_log(
                    message, o=self.get_current('fullpath', 'Unknown'), p=level)
            nval = [level, message]
        self.desc.set(name, nval, t=t, newmeta=False)
        return nval

    def get_current(self, name, *a):
        try:
            return self.desc.get(name, meta=False)
        except:
            if len(a) == 1:
                return a[0]
            raise

    def set(self, name, nval, t=-1):
        """Sets a key, triggering history recording if set on the attributes. 
        `t` forces a different time."""
        if t < 0 or t is None:
            t = utils.time()
        # This will automatically call set_current above
        nval = option.Conf.set(self, name, nval, t=t)
        return nval

    def describe(self, *excl):
        """Returns a dictionary of configuration options, each one rendered as a dictionary. 
        Runtime options are not included (attr `Runtime`).
        """
        desc = {}
        if len(excl) == 0:
            excl = ['Runtime', 'Binary', 'Object', 'Profile', 'Image']
        elif isinstance(excl, list) or isinstance(excl, tuple):
            excl = excl[0]
        excl = set(excl)
        for k, e in self.desc.iteritems():
            try:
                par = set(e['attr'] + [e['type']])
            except:
                print 'describe:', k, e
                raise
            entry = e.entry
            # Update to current values
            if self.desc[k]['current'] is None:
                print 'Found None value', k
                entry['current'] = 'None'
            # Replace with factory default if type/attr is not requested
            if len(par - excl) < len(par):
                entry['current'] = entry['factory_default']
            desc[k] = entry
        return desc

    def mb(self, name):
        """Returns modbus parameter, if set."""
        if self.desc[name].has_key('mb'):
            return int(self.desc[name]['mb'])
        return None

    def update(self, newdict, current=True):
        """Updates conf definition by merging dictionary `newdict`.
        Avoid keepnames."""
        opts = {}
        for k, v in newdict.iteritems():
            if k in self.keepnames:
                continue
            if isinstance(v, dict):
                v = option.Option(**v)
            opts[k] = v
        self.desc.update(opts)
        self.validate()

    def updateCurrent(self, currentDict, t=-1):
        """Updates current values to `currentDict`. 
        History options are recorded, optionally at time `t`.
        Returns the number of errors encountered."""
        if t < 0:
            t = utils.time()
        e = 0
        keys = self.desc.keys()
        for key, val in currentDict.iteritems():
            if (key not in keys) and (not self.empty):
                e += 1
                self.log.debug('Asked to update non-existent property:', key)
                continue
            if self.empty:
                if not self.has_key(key):
                    self.sete(key, {'factory_default': val})
            self.set(key, val, t)
        return e
    
