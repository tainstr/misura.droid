# -*- coding: utf-8 -*-
"""Recursive Reference updater from DirShelf"""
import os
from time import sleep
from traceback import print_exc
import threading

import numpy as np

from misura.canon import reference
from misura.canon.csutil import lockme, sharedProcessResources
from filebuffer import FileBuffer, LOCK_SH

# TODO: Evaluate inotifyx for more efficient scan!

log_marker = '/log/self'
if os.name=='nt':
    log_marker = '\\log\\self'
    
class ReferenceUpdater(object):
    outfile = False
    zerotime = 0
    nthreads = 3 
    scanning = 0
    paths = None
    
    def __init__(self, base, outfile=False, zerotime=0):
        self.base = base
        self._lock = threading.Lock()
        sharedProcessResources.register(self.restore_lock, self._lock)
        self.pool = []
        self.callback_result = []
        if not self.nthreads:
            self.nthreads = 1
        # Direct initialization
        if outfile:
            self.reset(outfile, zerotime)
            
    def restore_lock(self, lk):
        self._lock=lk
        
    def __getstate__(self):
        r = self.__dict__.copy()
        r.pop('_lock')
        return r
    
    def __setstate__(self, s):
        self.__dict__ = s 
        self._lock = threading.Lock()

    def close(self):
        """Stop threaded operations and commit latest results"""
        self.running = False
        for t in self.pool:
            t.join(0.5)
        n = self.commit_results(self.callback_result)
        print('ReferenceUpdater.close: committed results', n)
        return True

    def __del__(self):
        self.close()

    @lockme()
    def reset(self, outfile, zerotime=0):
        """Prepare for a new acquisition"""
        self.zerotime = zerotime
        self.outfile = outfile
        self.callback_result = []
        self.pool = []
        self.running = False
        self.paths = {}  # dict of path:kid where new data may be found
        self.link = {}  # dict of kid:[RoleIO paths] for linked RoleIO paths
        self.cache = {}  # path: Reference
        self.linked = set([])
        self.exclude = set()
        # Initialize file buffers
        self.buffers = []
        for i in range(self.nthreads):
            fb = FileBuffer(private_cache=True)
            fb.cache_len = 0
            self.buffers.append(fb)
        self.main_buffer = FileBuffer(private_cache=True)
        self.main_buffer.cache_len = 0
        print('Refupdater.reset DONE')

    def recursive_link(self, data_source, ref):
        """Recursively create all defined links"""
        #FIXME: this is not safe if process died while creating a link and is re-created
        linked = self.link.get(data_source, [])
        for p in linked:
            if (p, ref.path) in self.linked:
                print('Already linked', p)
                continue
            print('Linking', p, ref.path)
            if not self.outfile.has_node(p):
                self.outfile.link(p, ref.path)
            self.linked.add((p, ref.path))
            link_name = '/summary' + p
            if ref.__class__.__name__ == 'Array' and not self.outfile.has_node(link_name):
                self.outfile.link(link_name, ref.summary.path)
            # Recursively create nested links
            self.recursive_link(p, ref)

    def get_cache(self, path, fbuffer):
        """If the path is not in cache, evaluate if eligible and add it."""
        if path in self.exclude:
            return False
        # Try to recover from cache
        ref = self.cache.get(path, False)
        if ref:
            return ref
        # Creating new reference
        opt = fbuffer.get_meta(path)
        Cls = reference.get_reference(opt)
        # Output folder is red from the option KID attribute
        ref = Cls(self.outfile, opt=opt)
        ref.mtime = self.zerotime
        # Save in cache
        self.cache[path] = ref
        self.recursive_link(opt['kid'], ref)
        self.outfile.flush()
        return ref

    def add_path(self, f, dirname, names):
        """Check if `path` should be added to self.path for monitoring.
        Only objects with 'History' attr are considered."""
        if not 'self' in names:
            return False
        path = os.path.join(dirname, 'self')
        # if History is not specified, exclude this path from further sync
        opt = self.main_buffer.get_meta(path)
        attr = opt.get('attr', [])
        if opt['type'] == 'RoleIO':
            lk = opt['options']
            if lk[0] in (None, 'None'):
                self.exclude.add(path)
                return False
            # Remember kid of linked RoleIO
            kid = lk[0] + lk[2]
            if not self.link.has_key(kid):
                self.link[kid] = []
            self.link[kid].append(opt['kid'])
            # TODO: Should record anyway if defines History attr
            # but referred one does not...?
            self.exclude.add(path)
            return False
        if 'History' not in attr:
            self.exclude.add(path)
            return False
        # Monitor the path
        self.paths[path] = opt['kid']

    @lockme()
    def sync(self, zerotime=-1, only_logs=False):
        """Sync all entries.
        Returns number of monitored paths and updated ones."""
        self.only_logs = only_logs
        if self.paths is None:
            print('ReferenceUpdater.sync: no paths defined.', self.paths)
            self.paths = {}
            return False, 0
        N = len(self.paths)

        # if no path is being monitored, scan the entire memory
        if N == 0:
            print('Walking')
            os.path.walk(self.base, self.add_path, 0)
            N = len(self.paths)
            print('Walked', N)
            print('Linked', self.link)
            if N == 0:
                print('No path found')
                return False, 0

        if zerotime >= 0:
            self.zerotime = zerotime

        # Call the scan function in 5 different threads
        self.batch_length = N / self.nthreads
        if self.nthreads==1:
            self.single_threaded_scan()
        else:
            self.multi_threaded_scan()
        sc = len(self.callback_result)
        sc = self.commit_results(self.callback_result)
        self.callback_result = []
        return N, sc
    

    def multi_threaded_scan(self):
        if len(self.pool):
            return False
        self.running = True
        for i in range(self.nthreads):
            print('Starting scan thread', i)
            t = threading.Thread(target=self.scan_loop, args=(i,))
            t.start()
            self.pool.append(t)
        return True
                
    def single_threaded_scan(self):
        self._lock.release()
        self.scan(0)
        self._lock.acquire()

    def commit_results(self, result=[]):
        """When a scan ends, write out the result"""
        c = 0
        for path, elems in result:
            if self.only_logs and not path.endswith(log_marker):
                continue
            if elems is False:
                # Just create an empty ref
                ref = self.get_cache(path, self.main_buffer)
                continue
            # Waiting for new points
            if len(elems) == 0:
                continue
            # Retrieve saved ref
            ref = self.cache.get(path, False)
            if ref is False:
                print('Failed finding reference!')
                continue
            self.commit(ref, elems)
            c += 1
        return c

    def commit(self, ref, elems):
        """Commits `elems` data to `ref` Reference object in thread-safe mode."""
        N = len(elems)
        if N == 0:
            return False
        e = False
        try:
            for e in elems:
                ref.append(np.array(e))
        except:
            print('ReferenceUpdater.commit', ref.folder, e)
            raise
        # Interpolation step
        try:
            ref.interpolate()
        except:
            print('ReferenceUpdater.commit/interpolate', ref.folder, elems)
            raise
        return N

    @lockme()
    def from_cache(self, key):
        return self.cache.get(key, False)

    @lockme()
    def set_cache(self, key, val):
        self.cache[key] = val

    @lockme()
    def append_callback(self, elems):
        self.callback_result += elems

    ###############
    # THREAD POOL OPERATIONS
    # TODO: move to a separate SharedMemoryMonitor object to test inotifyx
    # Grouping methods which are called in separate threads during sync.
    # None of these methods should interact with outfile
    ###############
    def collect(self, path, fbuffer):
        """Collects new data points from `path` using file buffer `fbuffer`.
        Returns a list of elements to be added, or False if the output Reference was not created."""
#       self._lock.acquire()
        if path in self.exclude:
            return False
        ref = self.from_cache(path)
#       self._lock.release()
        if ref is False:
            lastt = self.zerotime
        else:
            lastt = ref.mtime
        elems = []
        try:
            #           mt=os.stat(path).st_mtime # not reliable for mmapped files!
            # Lock the file with low-level fopen()
            fbuffer.fopen(path, LOCK_SH)
            mt = fbuffer.mtime  # real last mod
        except:
            print('ReferenceUpdater.collect: error ', path)
            print_exc()
            fbuffer.fclose()
            return False

        # Reference missing
        if ref is False:
            fbuffer.fclose()
            # Avoid creating reference without a recent change
            if mt < lastt:
                # Return empty list = do not create ref
                #               print 'collect: not modified',path,ref,mt,lastt
                return elems
            # Force ref creation
            # print 'Force ref creation', path
            return False

        if mt < lastt and mt >= 0:
            fbuffer.fclose()
#           print 'No newer modification {:f}<{:f}'.format(mt,lastt)
            return elems
        # Get nearest time
        i = fbuffer._get_time_idx(ref.mtime - self.zerotime)
        # No newer points
        if i < 0:
            fbuffer.fclose()
            return elems
        i += 1
        if i >= fbuffer.idx_entries:
            fbuffer.fclose()
            return elems
        # Get sequence from the real index up to the end of the buffer
        elems0 = fbuffer._sequence(i)  # these have real timestamps
        # Unlock the file with low-level fclose()
        fbuffer.fclose()
        for i, e in enumerate(elems0):
            if e is False:
                #               print 'Erroneous result',path,i
                continue
            if e[0] <= ref.mtime:  # OK, e[0] has real timestamps as ref.mtime
                # print 'Skipping point',path,i,e[0],ref.mtime
                continue
            out = None
            ntime = e[0]  # newer time
            # Scale zerotime
            e[0] -= self.zerotime
            try:
                out = ref.encode(e)
            except:
                print_exc()
            if out is None:
                print('Encoding error', path, e)
                continue
            elems.append(out)
            # Remember newer time
            ref.mtime = ntime

        # Be sure to update reference with new mtime
        self.set_cache(path, ref)
        return elems

    def scan(self, thread_index=0):
        """Scan the whole self.paths list of eligible paths and collects data to be committed"""
        # Use a dedicated FileBuffer
        buff = self.buffers[thread_index]
        c = []
        start = self.batch_length * thread_index
        end = len(self.paths)
        if thread_index < self.nthreads - 1:
            end = self.batch_length * (thread_index + 1)
        for p in range(start, end):
            # End of scan
            if p >= len(self.paths):
                break
            p = self.paths.keys()[p]
            # Skip non-log entries
            if self.only_logs and not p.endswith(log_marker):
                continue
            elems = self.collect(p, buff)
            if elems is False:
                c.append((p, False))
                continue
            if len(elems) == 0:
                continue
            c.append((p, elems))
        self.append_callback(c)
        return c
    
    def scan_loop(self, *a, **k):
        while self.running:
            self.scan(*a, **k)
            sleep(0.2)
        print('ReferenceUpdater.scan_loop: exiting', a, k)
        
