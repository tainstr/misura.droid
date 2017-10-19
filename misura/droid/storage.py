# -*- coding: utf-8 -*-
"""Serving hdf5 files"""
import hashlib
import os
from copy import deepcopy
from time import time
from commands import getstatusoutput
from traceback import format_exc
from twisted.web import xmlrpc

from . import utils
from . import parameters as params
from misura.canon import csutil, indexer
from . import device
from __builtin__ import False

csutil.binfunc = xmlrpc.Binary


class TestFileReserved(xmlrpc.Fault):

    def __init__(self, msg=''):
        xmlrpc.Fault.__init__(self, 3900, self.__class__.__name__ + ': ' + msg)


class TestFileNotFound(xmlrpc.Fault):

    def __init__(self, msg=''):
        xmlrpc.Fault.__init__(self, 3901, self.__class__.__name__ + ': ' + msg)


class FileServer(xmlrpc.XMLRPC, indexer.FileManager):
    # TODO: Evaluate if would it be useful to transform FileServer into a configurable Device object.
    # Dummy functions required for client compatibility
    xmlrpc_has_key = lambda *foo: False
    xmlrpc_list = lambda *foo: []
    xmlrpc_io = lambda *foo: []
    xmlrpc_searchPath = lambda *foo: False
    timeout = 600

    @property
    def live(self):
        """Client UT compatibility"""
        r = self.getSubHandler('live')
        r.parent = lambda *a: self
        r.root = self.store.parent()
        r.addr = '://testing'
        r.user = 'test'
        r.password = 'test'
        r.copy = lambda *a: r
        r.child = lambda *a: None
        r._Method__name = 'storage/live'
        return r

    live_file = False

    def __init__(self, store=False):
        xmlrpc.XMLRPC.__init__(self, allowNone=True)
        self.separator = '/'
        indexer.FileManager.__init__(self, store=store)
        self.xmlrpc_open_uid = self.open_uid
        self.reserved = set()  # reserved uid registry
        
    def do_self_test(self):
        """Compatibility with Device"""
        return True,[]
    
    def do_iter_test(self):
        """Compatibility with Device"""
        return True,[]

    def check(self):
        """Closes timed-out files to save RAM"""
        t = time()
        for uid, test in self.tests.items():
            ts = test._get_timestamp()
            if t - ts > self.timeout:
                self.log.debug(
                    'SharedFile timeout:', t - ts, self.uids[uid], uid)
                self.close_uid(uid)
        return True

    def close_uid(self, uid):
        """Override FileManager.close_uid to shutdown the ProcessProxy also"""
        f = self.uid(uid)
        r = indexer.FileManager.close_uid(self, uid)
        if f is not False:
            f._stop()
        return r

    def getSubHandler(self, prefix):
        """Override getSubHandler in order to open SharedFile instances as needed."""
        if prefix == 'live' and self.live_prefix:
            prefix = self.live_prefix
        if not prefix:
            return False
        n = self.subHandlers.get(prefix, False)
        if n is not False:
            return n
        # Get corresponding uid or assume uid
        uid = self.paths.get(prefix, prefix)
        # Check if reserved
        if uid in self.reserved:
            raise TestFileReserved('{}, at {}'.format(uid, prefix))
        f = self.open(prefix)
        if not f:
            raise TestFileNotFound('{}, at {}'.format(uid, prefix))
            return False
        return f
    child = getSubHandler
    toPath = getSubHandler

    @property
    def live_prefix(self):
        return self.store['live']

    def get_live(self):
        """Returns the current live UID/path"""
        return self.store['live']
    xmlrpc_get_live = get_live

    def reserve(self, uid):
        """Lock `uid` as reserved for download.
        Returns True if successful.
        False if the file is still in use (eg: it's the live output file)."""
        # Still live uid - cannot reserve
        if uid == self.live_prefix:
            print 'Cannot reserve live UID', uid
            return False
        if uid in self.reserved:
            print 'Already reserved UID', uid
            return False
        self.close_uid(uid)
        # Add to reserved set so it cannot be opened again
        self.reserved.add(uid)
        return False
    xmlrpc_reserve = reserve

    def is_reserved(self, uid):
        return uid in self.reserved
    xmlrpc_is_reserved = is_reserved

    def free(self, uid):
        """Free `uid` from download lock."""
        if uid == self.live_prefix:
            print 'Cannot free live UID'
            return False
        self.close_uid(uid)
        if uid in self.reserved:
            self.reserved.remove(uid)
        return True
    xmlrpc_free = free

    def lookupProcedure(self, procedurePath):
        """Override XMLRPC lookupProcedure in order to call getSubHandler
        also if the procedurePath was not registered"""
        pp = procedurePath.split(self.separator)
        # If just one item, it is a function of FileServer itself
        if len(pp) == 1:
            f = getattr(self, 'xmlrpc_' + pp[0], False)
            if f is False:
                raise xmlrpc.NoSuchFunction(self.NOT_FOUND,
                                            "FileServer procedure %s not found" % procedurePath)
            return f
        # Function name is always the last item
        f = pp.pop(-1)
        # Filename requires rejoining the remaining part of pp
        prefix = '/'.join(pp)
        # Retrieve the served file
        sub = self.getSubHandler(prefix)
        if sub is False:
            raise xmlrpc.NoSuchFunction(self.NOT_FOUND,
                                        "SharedFile %s not found for procedure %s" % (prefix, procedurePath))
        # Retrieve the function - try first with xmlrpc_ prefix
        cb = getattr(sub, 'xmlrpc_' + f, False)
        # try as-is
        if cb is False:
            cb = getattr(sub, f, False)
        if cb is False:
            raise xmlrpc.NoSuchFunction(self.NOT_FOUND,
                                        "SharedFile method %s not found on handler %s for procedure %s" % (f, prefix, procedurePath))
        # Return the function
        return cb


class Storage(device.Device, indexer.Indexer):

    """Serving test files from on-board disk storage"""
    test = False
    naturalName = 'storage'
    conf_def = deepcopy(device.Device.conf_def)
    conf_def += [{"handle": 'appendCommand', "name": "Exec on test finish", "type": 'String'},
                 {"handle": 'keepDisk', "name": "Ensure free space", "current":
                     2000, "min": 500, "unit": "megabytes", "type": 'Integer', },
                 {"handle": 'diskUsage', "name": "Current disk usage", "current": 0, "min": 0,
                     "max": 1, "unit": "megabytes", "attr": ['ReadOnly'], "type":'Progress', },
                 {"handle": 'testPid', "name": "Process managing opened tests",
                  "current": -1, "attr": ['ReadOnly'], "readLevel":5, "type":'Integer'},
                 {"handle": 'live', "name": "Current output file uid",
                  "type": 'String', },
                 ]

    def __init__(self, parent=None, node='storage', path=False):
        device.Device.__init__(self, parent=parent, node=node)
        self['name'] = 'Storage'
        self['comment'] = 'Storage'
        self['devpath'] = 'storage'
        if path:
            self.path = path
        elif self.root is None:
            self.path = params.datadir
        else:
            self.path = self.root.main_datadir

        indexer.Indexer.__init__(self,
                                 dbPath=self.path + 'misura.sqlite',
                                 paths=[self.path],
                                 log=self.log)
        self.test = FileServer(self)
        self.test.file_class = self.manager.SharedFile
        self.test.log = self.log
        self.putSubHandler('test', self.test)
        # Publish public Indexer functions as xmlrpc:
        for f in indexer.Indexer.public:
            g = getattr(self, f)
            setattr(self, 'xmlrpc_' + f, g)

    def appendFile(self, *a, **k):
        r = False
        try:
            r = indexer.Indexer.appendFile(self, *a, **k)
        except:
            self.log.error(format_exc())
        cmd = self['appendCommand']
        if cmd != '':
            self.log.info('Executing post append command')
            s, out = getstatusoutput(cmd)
            self.log.info('Post append returns {}:\n{}'.format(s, out))
        return r

    def get_testPid(self):
        """Returns the manager PID"""
        if hasattr(self.manager, '_process'):
            pid = self.manager._process.ident
            return pid
        return -1

    def get_diskUsage(self):
        free, total, used = utils.disk_free(self.path)
        d = self.gete('diskUsage')
        d['max'] = int(total)
        self.sete('diskUsage', d)
        self.log.info('DISKUSAGE', self.path, free, total, used)
        return int(used)

    def _remove_oldest_names(self):
        """Warning: chmod can change ctime and so lead to wrong deletions"""
        free_space_in_MB = utils.disk_free(self.path, unit=2.**20)[0]
        space_to_keep_in_MB = self['keepDisk']
        files_sorted_by_oldest_first = map(
            lambda elem: elem[0], utils.iter_cron_sort(self.path))
        files_sorted_by_oldest_first = utils.only_hdf_files(
            utils.filter_calibration_filenames(files_sorted_by_oldest_first))

        while (free_space_in_MB < space_to_keep_in_MB and len(files_sorted_by_oldest_first) > 1):
            file_to_delete = files_sorted_by_oldest_first.pop(0)
            os.remove(file_to_delete)
            free_space_in_MB = utils.disk_free(self.path, unit=2.**20)[0]
            self.log.info(
                'Auto cleanup: removed ', file_to_delete, '. Free space: ', free_space_in_MB)
            
        if free_space_in_MB < space_to_keep_in_MB:
            self.log.critical(
                'Failed to increase tests storage. Please contact support! \nFree storage: {:.2f}MB'.format(free_space_in_MB))
            # Stop test if cannot free more disk space and it goes below a half
            if self.root_isRunning:
                status, msgs = self.do_self_test() 
                if not status:
                    self.root_obj['endStatus'] = msgs[-1][1]
                    self.root_obj['isRunning'] = False
            return False
        return True
    
    def do_self_test(self):
        status, msgs = super(Storage, self).do_self_test()
        free_space_in_MB = utils.disk_free(self.path, unit=2.**20)[0]
        if free_space_in_MB < self['keepDisk']/2:
            msgs.append([0, 'Disk space is only {:.0f}MB'.format(free_space_in_MB)])
            status = False
        return status, msgs

    def check(self):
        """Deletes old files when disk space is running out"""
        free_space_in_MB = utils.disk_free(self.path, unit=2.**20)[0]
        space_to_keep_in_MB = self['keepDisk']
        if free_space_in_MB > space_to_keep_in_MB:
            self.test.check()
            return True

        entries = self.query({}, 1, 'zerotime', 'ASC', 50, 0)
        r = True
        while (free_space_in_MB < space_to_keep_in_MB and len(entries) > 0):
            entry = entries.pop(0)
            r = self.remove_uid(entry[2])
            if not r:
                os.remove(entry[0])
            free_space_in_MB = utils.disk_free(self.path, unit=2.**20)[0]
            self.log.info(
                'Auto cleanup: removed ', entry[0], '. Free space: ', free_space_in_MB)

        if free_space_in_MB < space_to_keep_in_MB:
            self.log.critical('Removing files by name...')
            r = self._remove_oldest_names()
        self.test.check()
        return r

    def close(self):
        if self.desc is False:
            return False
        print 'Storage.close', type(self), id(self)
        indexer.Indexer.close_db(self)
        print 'Storage.close', type(self.test), id(self.test)
        if self.test:
            self.test.close()
        print 'Storage.close device'
        return device.Device.close(self)

    def new_path(self,
                 instrument,
                 shortname='test',
                 sub=False,
                 forcepath=False,
                 title=''):
        """Returns a new file path, calculated from an `instrument` name, a `shortname` identifier of the test,
        an optional `sub` directory, or a different forced path passed to `forcepath`"""
        shortname = utils.validate_filename(shortname)
        if forcepath is not False:
            dirpath = forcepath
        else:
            # nome unico per il file a partire dal numero di file nella
            # cartella
            dirpath = self.path + instrument + '/'
            if sub:
                dirpath += sub + '/'
        if not dirpath.endswith('/'):
            dirpath += '/'
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)
        n = len(os.listdir(dirpath))  # numero di file
        sn = 'unittest'
        if self.root is not None:
            sn = self.root.get('eq_sn')  # serial number
        uid = hashlib.md5('%s_%.2f_%i' % (sn, time(), n)).hexdigest()
        sid = shortname
        fn = dirpath + sid + params.ext  # 1.h5, 2.h5, etc...
        n = 1
        while os.path.exists(fn):
            n += 1
            uid = hashlib.md5('%s_%.2f_%i' % (sn, time(), n)).hexdigest()
            sid = shortname + '_' + str(n)
            fn = dirpath + sid + params.ext
        # Touch the file
        open(fn, 'w').close()
        return fn, sid, uid

    def new(self, instrument, shortname='test', sub=False,  forcepath=False, title='', shm_path=None, zerotime=None):
        """Returns a new, opened SharedFile instance"""
        fn, sid, uid = self.new_path(instrument, shortname=shortname,
                                     sub=sub, forcepath=forcepath, title=title)
        self.log.debug('Storage.new', fn, sid, uid)
        # Create the shared file via process proxy
        out = self.manager.OutputFile(fn,
                                      uid=uid,
                                      mode='a',
                                      title=title,
                                      shm_path=shm_path,
                                      zerotime=zerotime)
        out._max_restarts = 5
        out._timeout = 60
        out._set_logging(self.fp('log'),  self['fullpath'])
        out._log.debug('Created new OutputFile')
        self.log.debug(
            'Created new OutputFile', self.manager, type(self.manager), out, type(out))
        # Register in FileServer
        self.test.uids[uid] = fn
        self.test.paths[fn] = uid
        self.test.tests[uid] = out
        # Return the interface
        self.log.debug('Storage.new DONE')
        return out
