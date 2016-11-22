#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Parallel processes"""
import shutil
import os

from time import sleep
import multiprocessing
from multiprocessing.managers import SyncManager
from multiprocessing import Lock

from misura.canon import indexer, logger
import data
import parameters as params
import process_proxy
# # Activate multiprocessing logging
# import logging
#mplog = multiprocessing.get_logger()
# mplog.setLevel(multiprocessing.util.DEBUG)
# mplog.addHandler(logging.StreamHandler())

# MPI tests
comm = False
rank = 0
size = 0
try:
    from mpi4py import MPI
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
except:
    pass


class MisuraForkAwareThreadLock(object):

    """"Overrides multiprocessing.util.ForkAwareThreadLock
    in order to use a multiprocessing.Lock instead of a threading.Lock."""
    # http://stackoverflow.com/questions/3649458/broken-pipe-when-using-python-multiprocessing-managers-basemanager-syncmanager

    def __init__(self):
        self._reset()
        multiprocessing.util.register_after_fork(
            self, MisuraForkAwareThreadLock._reset)

    def _reset(self):
        self._lock = multiprocessing.Lock()
        self.acquire = self._lock.acquire
        self.release = self._lock.release

# Monkey patch BaseProxy in order to use the correct locking
multiprocessing.managers.BaseProxy._mutex = MisuraForkAwareThreadLock()

class FileBufferLogger(logger.BaseLogger):
    def __init__(self, log_path = False,  owner = False):
        self.buffer = data.FileBuffer() # Output filebuffer
        self.log_path = log_path
        self.owner = owner
        
    def log(self, *msg, **po):
        """Post log message to shared logging and append to log_path buffer"""
        if self.owner:
            po['o'] = self.owner
            # Ensure message is a string, to avoid passing unpicklable to database ProcessProxy
        msg = logger.concatenate_message_objects(*msg)
        p, msg = database.put_log(*msg, **po)
        if self.log_path:
            msg = u' '.join(tuple(msg))
            msg = msg.decode('utf-8', errors='replace')
            self.buffer.write(self.log_path,  [p, msg])
        return p,msg  


class SharingServer(multiprocessing.managers.Server):
    public = multiprocessing.managers.Server.public[:]
    public += ['get_ids', 'get_pid']

    def get_ids(self, c):
        self.mutex.acquire()
        try:
            r = ''
            for idref,  nref in self.id_to_refcount.iteritems():
                r += '{}::{}\n'.format(idref, nref)
            print 'get_ids: returning  ', r
            return r
        finally:
            self.mutex.release()

    def get_pid(self, c):
        self.mutex.acquire()
        try:
            return os.getpid()
        finally:
            self.mutex.release()


registered = {'SharedFile': indexer.SharedFile,
              'OutputFile': data.OutputFile}

class SharingManager(process_proxy.ProcessProxyManager):
    def __init__(self, *a, **k):
        global registered
        process_proxy.ProcessProxyManager.__init__(self, *a, **k)
        self._base_path = dbpath
        for name, cls in registered.iteritems():
            if self._registry.has_key(name):
                print 'SharingManager: already registered', name, cls, id(self)
                continue
            print 'SharingManager: register', name, cls, id(self)
            self.register(name, cls)


class DummyManager(object):

    def __init__(self, *a, **kw):
        for name, cls in registered.iteritems():
            self.register(name, cls)

    def __getattr__(self, key):
        global registered
        print 'DummyManager: getting', key
        if registered.has_key(key):
            return registered[key]
        else:
            return object.__getattribute__(key)

    def get_ids(self, *a):
        return ''

    def register(self, name, cls):
        global registered
        registered[name] = cls
        return True

    def start(self):
        print 'Dummy manager started'
        return True

    def shutdown(self):
        print 'Dummy manager shutting down'
        return True


class ProcessCache(object):

    def __init__(self, n=params.managers_cache):
        self.n = n
        self.free = [DummyManager() for i in range(n)]
        self.used = []
        self.started = 0
        print 'ProcessCache init', repr(self.free)

    def start(self):
        print 'Starting ProcessCache', self.n
        if self.started:
            self.stop()
        self.free = []
        self.used = []
        for i in range(self.n):
            m = SharingManager()
            print 'ProcessCache: Starting SharingManager', i
            m.start()
            print 'ProcessCache: done, appending.'
            self.free.append(m)
        self.started = 1
        print repr(self.free)

    def get(self):
        if len(self.free) == 0:
            print 'Starting a brand new manager...'
            if self.started:
                m = SharingManager()
            else:
                m = DummyManager()
            m.start()
        else:
            print 'Retrieving an already started manager...'
            m = self.free.pop(0)
        print 'MANAGERS: used: {}, free: {}, found: {}'.format(len(self.used), len(self.free), repr(m))
        self.used.append(m)
        return m

    def release(self, m):
        """Release manager and keep if for future reuse."""
        print 'Releasing manager...'
        if m in self.used:
            self.used.remove(m)
        else:
            print 'Released manager was not in use!', m
        self.free.append(m)
        return True

    def destroy(self, m):
        """Definitely shutdown a manager process."""
        print 'Destroying manager...'
        if m in self.free + self.used:
            self.used.remove(m)
        m.shutdown()

    def stop(self):
        for m in self.free + self.used:
            m.shutdown()
        # Restore dummy managers
        self.free = [DummyManager() for i in range(self.n)]
        self.used = []
        self.started = 0


# MPI test stuff
# TODO: remove dbpath and exclusively use params.rundir
dbpath = False


def set_dbpath():
    global dbpath
    dbpath = 0
    if rank == 0:
        dbpath = params.rundir
    if size > 1:
        comm.bcast(dbpath, root=0)
        print 'BROADCASTING DATABASE PATHS', rank, dbpath
    print 'share.dbpath', dbpath

set_dbpath()


# HACK
class ClassThatDeletesSharedMemoryWhenGarbageCollected():
    keepme = (dbpath + '.')[:-1]

    def __del__(self):
        if os.path.exists(self.keepme):
            import shutil
            shutil.rmtree(self.keepme)

dont_garbage_collect_me_manually = ClassThatDeletesSharedMemoryWhenGarbageCollected()


def init(connect=False, authkey='misura', port=0, log_filename=params.log_filename):
    """Initialize global variables. Must be called only by main module."""
    global manager, database
    set_dbpath()
    print 'empty FileBuffer cache', len(data.FileBuffer.cache)
    data.FileBuffer.empty_global_cache()
    # Clean the database dir
    if os.path.exists(dbpath):
        print 'Clearing shared memory shelf', dbpath
        shutil.rmtree(dbpath)
    # Clear the device registry
    try:
        from misura.device import delete_registry
        delete_registry()
    except:
        pass
    print 'starting sharing, was:', manager
    if isinstance(manager, SharingManager):
        if manager._state.value == 1:
            print 'Keeping old manager'
        else:
            manager = False
    else:
        manager = False
    if manager is False:
        print 'starting sharing manager'
        manager = SharingManager(address=('', port), authkey=authkey)
        if connect:
            print 'Connecting to SharingManager', port
            manager.connect()
        else:
            print 'Starting new SharingManager', manager
            manager.start()

    print 'starting process cache'
    cache.start()
    print 're-opening database', dbpath, params.log_filename
    database = manager.Database(dbpath, log_filename=log_filename)
    print 'share.init() DONE'
    return manager

import weakref
import gc
from traceback import print_exc


def stop(last=False):
    """Stop the manager, database, cache and replace with non-shared objects."""
    global manager, database
    print 'empty FileBuffer cache', len(data.FileBuffer.cache)
    data.FileBuffer.empty_global_cache()
    print 'stopping sharing', manager
    cache.stop()
    print 'cache stopped'
    if isinstance(manager, SharingManager):
        if manager._state.value == 0:
            print 'MAIN MANAGER WAS NOT STARTED', manager
        while manager._state.value == 1:
            print 'MAIN MANAGER: STOPPING', manager
            manager.shutdown()
            sleep(0.1)
        del manager
        # Re-create manager as DummyManager
        manager = DummyManager()
        sleep(0.1)
        
    database = manager.Database(dbpath)

    if os.path.exists(dbpath):
        print 'Removing shared memory shelf', dbpath
        shutil.rmtree(dbpath)

    # Clear the multiprocessing afterfork registry in order not to block
    # between unittesting restarts
    if params.utest and not last:
        multiprocessing.util._afterfork_registry = weakref.WeakValueDictionary()

    print 'share.stop() DONE'


def close_sparse_objects():
    # Close all Misura-related objects
    so = 0
    for o in gc.get_objects():
        # Exclude classes
        if hasattr(o, '__name__'):
            continue
        # Exclude non-misura
        if not getattr(o, '__module__', '').startswith('misura'):
            continue
        # Exclude lacking a ´close´ attribute
        if not hasattr(o, 'close'):
            continue
        # Exclude lacking a callable ´close´
        if not hasattr(o.close, '__call__'):
            continue
        print 'Closing sparse object', type(o), id(o)
        so += 1
        try:
            o.close()
            del o
        except:
            print_exc()
    print 'SPARSE OBJECTS', so


def register(name, cls):
    global manager, registered
    manager.register(name, cls)
    registered[name] = cls

# Serverless, shareless compatibility (for unittesting):


def dummy():
    global manager
    manager = DummyManager()
    return manager

# Serverless definitions
cache = ProcessCache()
manager = DummyManager()
register('SharedFile', indexer.SharedFile)
register('Database', data.Database)
database = data.Database(dbpath)

main_confdir = params.confdir

print 'SHARE IMPORTED'
