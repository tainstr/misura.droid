# -*- coding: utf-8 -*-
"""Data management and formats"""
import os
import logging
import logging.handlers
import conf
from .. import parameters as params
from misura.canon import logger
from circularbuffer import CircularBuffer
from .. import utils
from dirshelf import DirShelf


class Database(object):
    out = False
    """Buffering object for data output"""

    def __init__(self, dbpath, log_format='%(levelname)s:%(asctime)s%(message)s', log_filename=False):
        # Clean the path before setting it
        self.dbpath = dbpath
#       self._lock=Lock()
        self._lock = False
        # TODO: make these shared!
        kid_list = [[0., '']] * params.buffer_length
        self.kid_buf = CircularBuffer(lst=kid_list)
        """Latest modified KIDs"""
        self.nkid = 0
        """Current kid index"""
        log_list = [[0, 0, '', '']] * params.buffer_length
        self.log_buf = CircularBuffer(lst=log_list)
        """Latest log lines"""
        self.nlog = 0
        """Current log index"""
        self.set_logger(log_format, log_filename=log_filename)

    def set_logger(self, log_format='%(levelname)s:%(asctime)s%(message)s', log_filename=False):
        self.log_format = log_format
        self.formatter = logging.Formatter(log_format)
        self.main_logger = logging.getLogger('misura')
        self.main_logger.setLevel(logging.DEBUG)
        if not len(self.main_logger.handlers):
            handler = logging.StreamHandler()
            handler.setFormatter(self.formatter)
            self.main_logger.addHandler(handler)
        else:
            print 'Already defined logging handlers', self.main_logger.handlers
        if not log_filename:
            return
        self.log_filename = log_filename
        self.addFileHandler(log_filename,
                            params.log_file_dimension,
                            params.log_backup_count)

    def __getstate__(self):
        d = self.__dict__.copy()
        for k in ['main_logger', 'formatter', 'log_filename', 'log_format']:
            if d.has_key(k):
                del d[k]
        return d

    def __setstate__(self, state):
        self.set_logger(state['log_format'], state['log_filename'])

    def addFileHandler(self, filename, max_dim=2 * 10**6, backups=10):
        """Adds logrotate logging"""
        print 'Database.addFileHandler', filename, self.log_format
        handler = logging.handlers.RotatingFileHandler(filename,
                                                       maxBytes=max_dim,
                                                       backupCount=backups)
        handler.setFormatter(self.formatter)
        self.main_logger.addHandler(handler)

    def close(self):
        pass

    # LOGGING FUNCTIONS

    def get_log(self, fromt=False, priority=0, owner=False, tot=False, maxn=None):
        """Search in the log buffer. Require priority equal
        or bigger than `priority` and emitted by `owner`.
        Maximum time `tot`, maximum number of entries `maxn`."""
        t, obuf = utils.get_history(self.log_buf, fromt)
        buf = []
        if type(obuf[0]) == type(1.):
            obuf = [obuf]
        if tot is False:
            tot = obuf[-1][0] + 1
        for b in obuf:
            if b[0] > fromt and b[0] < tot:
                buf.append(b)
        if not owner and priority == 0:
            return t, buf[:maxn]
        r = []
        # time, prio, owner, msg
        for l in buf:
            if len(l) < 3:
                break
            if priority > 0:
                if l[1] < priority:
                    continue
            if owner:
                if l[2] != owner:
                    continue
            if l is None:
                l = 'None'
            r.append(l)
        return t, r[:maxn]

    def put_log(self, *msg, **po):
        """General, short-memory logging"""
        t, st, p, o, msg, pmsg = logger.formatMsg(*msg, **po)
        self.log_buf.append([t, p, o, pmsg])
        self.main_logger.log(p, pmsg)
        self.nlog += 1
        return p, msg
