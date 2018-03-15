# -*- coding: utf-8 -*-
"""Filesystem-level CircularBuffer implementation"""
import os
import mmap
import collections
import numpy as np
from cStringIO import StringIO
import functools
from traceback import print_exc
from cPickle import dump, dumps, loads, HIGHEST_PROTOCOL
import exceptions
import multiprocessing
from time import time, sleep
from misura.canon import csutil

from misura.droid import utils
from __builtin__ import False

isWindows = os.name == 'nt'

LOCK_FR = 0
LOCK_UN = 1

LOCK_SH = 2
LOCK_EX = 3

LOCK_NBSH = 4
LOCK_NBEX = 6

flags = os.O_RDWR 
if not isWindows:
    flags |= os.O_SYNC

class SharedMemoryLock(object):
    """In-memory registry for file locking statuses.
    Makes file-locking fast and fully cross-platform."""
    timeout = 5
    
    def __init__(self, N=10000):
        self.cache = {}
        self.free = set(range(N))
        # 0=free address, 1=unlocked, 2=locked
        self.locks = [multiprocessing.Value('i') for i in self.free]
    
    def _read(self, path):
        try:
            idx = int(open(path+'.lk', 'rb').read())
        except:
            print_exc()
            return -1
        self.cache[path] = idx
        if idx in self.free:
            self.free.remove(idx) 
        return idx 
    
    def _idx(self, path):      
        idx = self.cache.get(path, -1)
        if idx<0:
            idx = self._read(idx)
        return idx        
    
    def unlock(self, path):
        """Set `path` to unlocked"""
        idx = self._idx(path)
        self.locks[idx].value = LOCK_UN
        return True
        
    def lock(self, path, value=LOCK_EX, timeout=-1):
        """Lock `path` with locking `value`.
        Returns False on failure."""
        if value==LOCK_UN:
            return self.unlock(path)
        if value==LOCK_FR:
            return self.clear(path)
        
        idx = self._read(path)
        lk = self.locks[idx]
        if lk.value==LOCK_FR:
            if value==LOCK_EX:
                lk.value = value
                return True
            print('Cannot lock unassigned address', idx, path)
            raise exceptions.MemoryError('FileBuffer lock address is unassigned {} {} {}'.format(idx, 
                                                                                                 path, 
                                                                                                 value))
            return False
        
        # If unlocked, apply right away
        if lk.value == LOCK_UN:
            self.locks[idx].value = value
            return True
        
        if timeout<0:
            timeout=self.timeout
        
        # Check if operation is non-blocking
        nonblock = value>3
        if nonblock:
            value /= 2
            
        # Can overlock with shared
        if lk.value==value==LOCK_SH:
            return True
        
        # Wait for exclusive lock to go away
        # Or a shared lock if we are trying to get an exclusive lock
        t0 = -1
        while (not nonblock) and (lk.value==LOCK_EX or (value==LOCK_EX and lk.value==LOCK_SH)):
            if t0<0:
                t0=time()
            elif time()-t0>timeout:
                break
            sleep(0.001)
        if t0>0:
            print('SharedMemoryLock.lock WAITED', time()-t0, path, value)
        # Cannot lock anyway with exclusive
        if lk.value==LOCK_EX:
            print('FileBuffer was exclusively locked', idx, path, value)
            raise exceptions.MemoryError('FileBuffer was exclusivly locked {} {} {}'.format(idx, path, value))
        # Apply lock
        self.locks[idx].value = value
        return True
    
    def refresh(self):
        """Refresh free addresses set"""
        self.free = set()
        for i, lock in enumerate(self.locks):
            if lock.value==LOCK_FR:
                self.free.add(i)
        assert len(self.free)>0, 'OUT OF FREE LOCK ADDRESSES!'
        
    
    def new(self, path):
        """Init a new lock on `path`"""
        idx = -1
        while len(self.free):
            idx0 = self.free.pop()
            # Should stop immediately unless parallel process reserved
            # some other addresses
            if self.locks[idx].value==LOCK_FR:
                idx=idx0
                break
        if idx<0:
            self.refresh()
            # Repeat
            return self.new(path)
        self.cache[path] = idx
        self.locks[idx].value=LOCK_UN
        fo = open(path+'.lk','wb')
        fo.write(str(idx))
        fo.close()
        
    def clear(self, path):
        """Free the path's locking address."""
        idx = self._read(path)
        self.locks[idx].value = 0
        if path in self.cache:
            self.cache.pop(path)
        if os.path.exists(path+'.lk'):
            os.remove(path+'.lk')
        
        
        
locker = SharedMemoryLock()
    


def exclusive(func, lock=LOCK_EX):
    """Decorator for FileBuffer fopen/fclose management"""
    @functools.wraps(func)
    def exclusive_wrapper(self, path, *a, **k):
        self.fopen(path, lock)
        try:
            r = func(self, *a, **k)
        except:
            print('Calling func', func.__name__, path, a, k)
            print_exc()
            raise
        finally:
            # Always close the file!
            self.fclose()
        return r
    return exclusive_wrapper

def shared(func):
    """fopen with shared locking"""
    return exclusive(func, lock=LOCK_SH)

def clean_cache(obj):
    """Shrink cache to its maximum length by closing oldest files."""
    i = 0
    for i in range(0, len(obj.cache) - obj.cache_len):
        # remove and close the first inserted item
        oldp, oldfd = obj.cache.popitem(False)
        os.close(oldfd)
    return i


class FileBuffer(object):

    """Persistent indexed queue-like array for IPC"""
    protocol = HIGHEST_PROTOCOL
    separator = '\n#$#$#$#\n'
    sep_len = len(separator)
    idx_fmt = '{:<20f}\t{:<11}\t{:<11}\n'  # time, start byte, end byte
    info_fmt = '{:<3}\t{:<22}\t{:<17f}\n'  # latest idx, total, last mod. time
    meta_len = 5120  # 5k of reserved metadata space (scripts!!!)
    idx_len = len(idx_fmt.format(0., 0, 0))
    assert idx_len == len(info_fmt.format(0, 0, 0))
    idx_entries = 100
    """Maximum number of entries to keep in history. Set this *before* any use of FileBuffer."""
    invalid = '#'
    empty_entry = invalid + ' ' * (idx_len - 2) + '\n'
    max_size = 2 * 10**6
    cache = collections.OrderedDict()  # {path: (mmap,(fileno, lock_fileno))}
    # maximum number of opened file descriptors, per PROCESS (class attribute!)
    cache_len = 500
    start_meta_position = idx_len * (idx_entries + 1)
    """Metadata block start byte"""
    start_position = start_meta_position + meta_len
    """Queue start byte"""
    _lock = multiprocessing.Lock()
    """Inter-process locking. Avoids concurrent threads/processes using the same buffer object"""
    info = -1, 0, -1
    """Uninitialized info tuple (high/current index, total count, modification time)"""
    path = False
    fd = -1
    mm = False
    
    def __init__(self, private_cache=False):
        """private_cache: use global FileBuffer.cache and _lock class attributes if False, 
        otherwise instantiated a new private cache and lock"""
        if private_cache:
            self._lock = multiprocessing.Lock()
            self.cache = {}

    def init(self, path):
        """Initialize a storage file"""
        d = os.path.dirname(path)
        if not os.path.exists(d):
            os.makedirs(d)
        fo = open(path, 'wb')
        # Write info line, init at -1
        # so it will restart next append
        fo.write(self.info_fmt.format(-1, 0, -1.0))
        fo.write(self.empty_entry * self.idx_entries)
        fo.write(' ' * self.meta_len)
        fo.close()
        locker.new(path)
            
    def remap(self, fd, path, lock):
        if fd < 0:
            return False
        # Lock must precede mmap
        try:
            locker.lock(path, lock)
        except:
            raise
        
        try:
            # Must re-map each time
            self.mm = mmap.mmap(fd, length=0)
        except:
            locker.unlock(path)
            return False
        
        self.fd = fd
        self.info = self._get_info()
        self.mm.seek(0)
        self.path = path
        return True

    def fopen(self, path, lock=LOCK_EX):
        """Open a file in path, handling the locking"""
        self._lock.acquire()
        
        fd = self.cache.get(path, -1)
        if self.remap(fd, path, lock):
            return self.mm, self.fd
        
        # Initialize the indexed file, if exclusive lock was required
        # (writing)
        ex = os.path.exists(path) and os.path.exists(path+'.lk')
        if not ex:
            if lock in [LOCK_EX, LOCK_NBEX]:
                self.init(path)
            else:
                self._lock.release()
                raise exceptions.KeyError(
                    'Non-existent FileBuffer for reading: ' + path)
            
        # Lock must precede mmap
        try:
            locker.lock(path, lock)
        except:
            self._lock.release()
            raise
        
        self.path = path
        # Open the file descriptor
        self.fd = os.open(path, flags)
        # Create the memory map
        self.mm = mmap.mmap(self.fd, length=0)

        # Manage caching
        if self.cache_len > 0:
            clean_cache(self)
            self.cache[path] = self.fd

        self.info = self._get_info()
        return self.mm, self.fd
    
    @classmethod
    def empty_global_cache(cls):
        """Close all opened files."""
        return clean_cache(cls)

    def close(self, basepath=''):
        for p in self.cache.keys():
            if not p.startswith(basepath):
                continue
            fd = self.cache.pop(p)
            locker.unlock(p)
            os.close(fd)
        try:
            self._lock.release()
        except:
            pass
        return True

    def __del__(self):
        self.close()

    def fclose(self):
        if self.mm:
            self.mm.flush()  # needed to actually sync
            self.mm = False
        if self.path:
            locker.unlock(self.path)
            self.path = False
        if self.cache_len <= 0 and self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
            
        try:
            self._lock.release()
        except:
            pass
    @property
    def high(self):
        return self.info[0]

    @property
    def count(self):
        return self.info[1]

    @property
    def mtime(self):
        return self.info[2]

    def _get_info(self):
        """Get the index info line"""
        s = self.mm[:self.idx_len]
        high, count, mtime = s.split('\t')
        return int(high), int(count), float(mtime)

    @shared
    def get_info(self):
        return self._get_info()

    def set_info(self, *vals):
        """Set the index info line"""
        self.mm[:self.idx_len] = self.info_fmt.format(*vals)
        self.info = vals

    def __len__(self):
        high, count, mtime = self.info
        return self.idx_entries if high + 1 < count else count

    def idx(self, idx):
        """Normalize idx with respect to high position. 
        Normalized idx is always 0<idx<idx_entries-1.
        By adding 1, it represents the index line."""
        high, count, mtime = self.info
        # Not initialized
        if high < 0:
            return -1
        N = len(self)
        wrap = count > N
        # Negative index: wrap around buffer length
        if idx < 0 and abs(idx) > N:
            return -1
        if idx < 0:
            idx += high + 1 if wrap else count
            return idx
        if wrap:
            idx += high + 1
            # Wrap around length
            idx %= self.idx_entries
        return idx

    def _get_idx(self, idx0):
        """Return index values at `idx`"""
        idx = self.idx(idx0)
        if idx < 0:
            print('Invalid index request', self.path, self.info, idx0, idx)
            return -1, -1, -1
        # Always exclude the info line
        start = (idx + 1) * self.idx_len
        if self.mm[start] == self.invalid:  # invalid entry detected
            #           print('Invalid index entry',self.path, idx0,idx)
            return -1, -1, -1
        end = start + self.idx_len
        s = self.mm[start:end]
        # Decode the index line
        t, s, e = s.split('\t')
        return float(t), int(s), int(e)

    @shared
    def get_idx(self, idx):
        r = self._get_idx(idx)
        if r[1] < 0:
            print('Invalid index')
        return r

    @shared
    def full_idx(self):
        """Parse the full index into a numpy array"""
        high, count, mtime = self.info
        e = self.start_meta_position
        if count <= high + 1:
            e = count * self.idx_len
        fidx = self.mm[self.idx_len:e]
        # Invalid values are set to False in the output array
        r = np.loadtxt(
            StringIO(fidx), dtype=None, delimiter='\t', comments=self.invalid)
        if count <= high + 1:
            return r
        # Newest values
        r1 = r[:high]
        # Oldest values
        r0 = r[high:]
        return np.concatenate((r0, r1))

    def _time(self, idx):
        return self._get_idx(idx)[0]

    @shared
    def time(self, idx):
        return self._time(idx)

    def _get_time_idx(self, t):
        # If requested time is bigger than last entry, return -1 index
        if t > self.info[2]:
            #           print('Bigger time', self.info)
            return -1
        # bisect search using self._time handler
        i = csutil.find_nearest_val(self, t, get=self._time)
        return i

    @shared
    def get_time_idx(self, t):
        """Find nearest index corresponding to time `t`"""
        return self._get_time_idx(t)

    def require_idx(self, idx0):
        """Return the first valid index starting from idx"""
        h, c, mt = self.info
        N = self.idx_entries if c > h + 1 else c
        idx = idx0
        nt, ns, ne = -1, -1, -1
        while idx < N:
            nt, ns, ne = self._get_idx(idx)
            print('require idx,', idx0, idx, nt, ns, ne)
            if ns > 0:
                # Valid entry found
                break
            idx += 1
            # No valid entry after required idx
            if idx >= N:
                break
        return idx, nt, ns, ne

    def set_idx(self, idx, t, start_byte, end_byte):
        """Set index info at `idx`"""
        idx = self.idx(idx)
        assert idx >= 0
        idx_start = (idx + 1) * (self.idx_len)
        # Intercept invalidation requests
        if start_byte < 0:
            self.mm[idx_start] = self.invalid
            return False
        idx_end = idx_start + self.idx_len
        # Invalidate old entries written after the current one, if they were
        # overwritten
        high, count, mtime = self.info
        if high + 1 < count:
            after = self.idx_entries - idx
            nidx = 0  # start from oldest
            # up to the remaining to the end of the stack
            while nidx < after - 1:
                nt, ns, ne = self._get_idx(nidx)
                # Already invalid
                if ns < 0:
                    # Detect first run
                    if high + 1 == count:
                        break
                    # Continue until next valid entry or end
                    nidx += 1
                    continue
                # if the current entry ends after the next, invalidate the next
                if end_byte >= ns:
                    # print('invalidating',self.path,idx,nidx,end_byte,ns)
                    self.set_idx(nidx, -1, -1, -1)
                else:
                    break
                nidx += 1
        # Eventually write the index
        self.mm[idx_start:idx_end] = '{:<20f}\t{:<11}\t{:<11}\n'.format(
            t, start_byte, end_byte)
        return True

    def _set_meta(self, meta):
        self.mm.seek(self.start_meta_position)
        dump(meta, self.mm, self.protocol)
        self.mm.seek(0)

    @exclusive
    def set_meta(self, meta):
        return self._set_meta(meta)

    @exclusive
    def write(self, val, t=-1, newmeta=False):
        """Append value to path."""
        high, count, mtime = self.info
        # Start rewriting from 0
        if high >= self.idx_entries - 1 or high < 0:
            start_byte0 = self.start_position
            high = 0
        # End byte of the last entry as reference
        else:
            t0, s, start_byte0 = self._get_idx(-1)
            assert s > 0, 'FileProxy.write: corrupted entry during'
            high += 1
        count += 1
        # If time was not defined, get its value
        if t < 0:
            t = utils.time()
        # Write the info
        self.set_info(high, count, t)
        start_byte = start_byte0 + self.sep_len
        g = dumps(val, self.protocol)
        lg = len(g)
        end_byte = start_byte + lg
        sz = len(self.mm)
        res = end_byte - sz + 1
        if res > 0:
            self.mm.resize(sz + res)
            self.mm.seek(0, os.SEEK_SET)
#           print('Resizing',start_byte,sz,end_byte,res,len(fo),len(g))
        self.mm[start_byte0:end_byte] = self.separator + g
        self.set_idx(-1, t, start_byte, end_byte)
        if newmeta:
            self._set_meta(newmeta)
        return True

    def clear(self, path):
        """Clear buffer `path` and re-init with latest values"""
        if not os.path.exists(path):
            return False
        # NEED MANUAL LOCKING MANAGEMENT
        self.fopen(path)
        # Collect latest metadata and value
        meta = self._get_meta()
        t, val = self._get_item(-1)
        self.fclose()
        # Remove from cache and FS
        if self.cache_len > 0:
            fd = self.cache.pop(path)
            locker.unlock(path)
            os.close(fd)
        os.remove(path)
        # This will re-init a blank file with the latest values.
        self.write(path, val, t, newmeta=meta)
        return True

    def _get_item(self, idx):
        """Return sequence element at `idx`"""
        t, s, e = self._get_idx(idx)
        if s < 0:
            #           print('_get_item',t,s,e)
            return False
        dat = self.mm[s:e]
        try:
            obj = loads(dat)
        except:
            print('_get_item', self.path, t, s, e, dat)
            print_exc()
            raise
        return [t, obj]

    def _get_meta(self):
        try:
            meta = loads(
                self.mm[self.start_meta_position:self.start_meta_position + self.meta_len])
        except:
            print('_get_meta')
            print_exc()
            raise
        return meta

    @shared
    def get_meta(self):
        return self._get_meta()

    @shared
    def get_item(self, idx, meta=False):
        """Get item from `path` at index `idx`"""
        r = self._get_item(idx)
        if r is False:
            print('Error get_item')
        elif meta:
            m = self._get_meta()
            m['current'] = r[1]
            r[1] = m
        return r

    def read(self, path, meta=True):
        """Get latest item"""
        r = self.get_item(path, -1, meta)
        if r is False:
            print('Error reading', path)
            return False
        return r[1]

    def _sequence(self, startIdx=0, endIdx=None):
        """Reads a sequence of objects appended to `path` from `startIdx` to `endIdx`"""
        s = startIdx
        N = len(self)
        if s < 0:
            s += N
        e = endIdx
        if e is None:
            e = N
        if e < 0:
            e += N
#       print('SEQUENCING',s,e)
        if s == e:
            return [self._get_item(s)]
        out = []
        for i in range(s, e):
            try:
                out.append(self._get_item(i))
            except:
                print('trying to unpickle', self.path, i)
                print_exc()
#       print('Returning sequence',startIdx,endIdx,s,e,len(out),self.info)
        return out

    @shared
    def sequence(self, *a, **k):
        return self._sequence(*a, **k)
