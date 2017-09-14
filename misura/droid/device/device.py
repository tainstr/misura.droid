#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Generic Device object"""
from copy import deepcopy
from traceback import format_exc
import multiprocessing
from collections import defaultdict

from misura.canon import milang, option
from misura.canon.csutil import unlockme, initializeme

from .. import utils
from .. import data, share  # needed for share loading in partial imports

from inputoutput import InputOutput
import device_conf
from exceptions import BaseException
from node import Node

# Possible relative import?
from misura.droid.device import get_registry


class AlreadyLocked(BaseException):
    pass


class Device(option.Aggregative, milang.Scriptable, Node):

    """General interface for devices. Role-aware and Multiprocessing-aware"""
    allow_none = True
    idx = -1
    """Index on parent device list"""
    fixedNaturalName = False
    """Define if this device has a fixed, pre-defined natural name and should not be named after idx0,1,2"""
    naturalName = 'dev'
    """Automatic naming"""
    available = {}
    """Available device registry {devpath:dev file}"""
    _udev = {}
    """query_udev cache"""
    conf_def = deepcopy(Node.conf_def + device_conf.conf)
    """Configuration definition"""
    process = False
    """Parallel acquisition process"""
    _daemon_acquisition_process = False
    """Acquisition child processes should be daemonic? (testing)"""
    Node.setProperties('zerotime', 'initializing', 'locked')

    def copy(self):
        # FIXME: Defined here just to allow hu_testing!
        return self

    @classmethod
    def served_by(cls, DeviceServerClass, original=False):
        """Performs registration operations when this class is served by a DeviceServer"""
        if original is not False:
            cls = original
        if cls in DeviceServerClass.ServedClasses:
            print 'Attept to register an already registered class', cls
            return False
        # Add class enabling option to the conf
        DeviceServerClass.conf_def.append({"handle": 'scan_' + cls.__name__,
                                           "name": 'Scan for ' + cls.__name__, "current": True,
                                           "type": 'Boolean', "writeLevel": 5, "readLevel": 4,
                                           # Causes a set_func call when a
                                           # preset is loaded
                                           'attr': ['Hardware']
                                           })
        DeviceServerClass.ServedClasses.append(cls)
        return True

    def __init__(self, parent=None, node='', conf_def=False):
        """Role-aware"""
        # Assure that each instance gets its own, unique, configuration
        # definition
        self.roledev = {}
        """Role->Dev mapping dictionary"""
        if conf_def is not False:
            self.conf_def = conf_def
        self.conf_def = deepcopy(self.conf_def)
        milang.Scriptable.__init__(self)
        Node.__init__(self, parent=parent, node=node)
        if self['name'] == 'device':
            self['name'] = self['devpath']
        self._lock = multiprocessing.Lock()
        self.desc.setKeep_names(['locked'])

    def xmlrpc___nonzero__(self):
        return True
    
    def xmlrpc_collect_aggregate(self, *a, **k):
        return self.collect_aggregate(*a, **k)
    
    def xmlrpc_update_aggregates(self, *a, **k):
        return self.update_aggregates(*a, **k)

    @classmethod
    def list_available_devices(cls):
        return cls.available

    def pre_scan(self):
        """Placeholder called on each instance of this class,
        before rescanning for new available devices.
        Useful for closing operations."""
        return True

    @classmethod
    def set_available_devices(cls, avail):
        """If  `avail` is a dictionary, directly set as available class attribute.
        If is a list, compile {devpath:dev} dictionary by replicating items in list
        and validating devpath"""
        if isinstance(avail, list):
            avail = {utils.validate_filename(v): v for v in avail}
        cls.available = avail

    @classmethod
    def from_devpath(cls, devpath):
        """Try to translate `devpath` into a physical device identifier (like a /dev/ file or specific driver enumerator).
        Returns `dev`==`devpath` if not found.
        The inverse of from_dev."""
        return cls.available.get(devpath, devpath)

    @classmethod
    def from_dev(cls, dev):
        """Try to translate a device system identifier `dev` into a device unique path devpath.
        Returns `dev` if not found.
        The inverse of from_devpath.
        """
        devpath = dev
        for dp, d in cls.available.iteritems():
            if d == dev:
                devpath = dp
        return utils.validate_filename(devpath)

    @classmethod
    def query_udev(cls, node=None):
        """Calculate and return the unique devpath
        for a possible instance of this class.
        Returns also other path-dependant properties in a dictionary."""
        if node in [None, '', False]:
            devpath = cls.naturalName
            dev = devpath
        else:
            dev = cls.from_devpath(node)
            devpath = cls.from_dev(dev)
            if devpath == dev:  # nothing found
                devpath = node
        return {'devpath': devpath, 'dev': dev}

    @property
    def root_isRunning(self):
        """Shortcut for accessing the isRunning option on object root."""
        if not self.root_obj:
            return False
        if not self.root_obj.has_key('isRunning'):
            return False
        return self.root_obj['isRunning']

    def sleep(self, t=0.1):
        utils.sleep(t)

    def connect(self):
        """Dummy method for client-server mixed testing."""
        pass

    def connection(self, blacklist=[]):
        """Connect (initialize) device for operation."""
        dp = self['devpath']
        av = self.__class__.available
        if av.has_key(dp) and av[dp] == self['dev']:
            self['isConnected'] = True
            return True
        else:
            print 'devpath not found in available', dp, av, av.has_key(dp), self['dev']
            self['isConnected'] = False
            return False

    def post_connection(self):
        """Executed immediately after a successful device initialization and connection."""
        self.query_udev(self['devpath'])
        # Update available presets
        self.desc.listPresets()
        # Try loading default configuration, if present
        self.set_preset('default')

    def map_role_dev(self, handle, new=None):
        """Processes a role-dev association for option `handle`.
        Returns:
        False on failure - old value should be restored.
        None on unset - new value is empty role
        obj,preset,io - new object role was defined with preset and io
        """
        prop = self.desc.gete(handle)
        slot = prop['type']
        # Discard non-role objects
        if not slot.startswith('Role'):
            return False
        # Empty entry
        empty_entry = (False, False, False)
        oldentry = self.roledev.get(handle, empty_entry)
        self.roledev[handle] = empty_entry
        isIO = slot.endswith('IO')
        if self.root_isRunning and not isIO:
            self.log.critical(
                'Tentative to change role-dev mapping while running. Option:', handle)
            return False
        if isIO:
            cur = prop.get('options', ['None'] * 3)
            iokid = cur[2]
        else:
            cur = prop['current']
            iokid = False
        if new is not None:
            cur = new
        path = cur[0]
        preset = cur[1]
        io = False
        self.log.debug('map_role_dev', handle, cur, isIO)
        # Identify invalid, incomplete, empty configurations
        if path in ['None', None]:
            self.log.error('Un-set Role configuration for:', handle, cur)
            cur[0] = 'None'  # avoid None
            cur[1] = 'default'
            if isIO:
                cur[2] = 'None'
            if isIO:
                self.desc.setattr(handle, 'options', cur)
                self.desc.set(handle, prop['factory_default'])
            else:
                self.desc.set(handle, cur)
            return None
        if path == '.':
            obj = self
        else:
            # Search for configured dev path
            hp = self.root_obj.searchPath(path)
            if not hp:
                self.log.debug('Devpath not found:', handle, path, hp, cur)
                return False
            # Translate the hierarchy path into the real object
            obj = self.root_obj.toPath(hp)
            self.log.debug('map_role_dev toPath', hp, cur)
        if obj is None:
            self.log.debug('Object not found in hierarchy', handle, hp, obj)
            return False
        # Get the IO handler if needed
        if isIO:
            # Intercept IO redirects to another role!
            if not obj.has_key(iokid):
                self.log.debug('IO Not found', handle, repr(hp), cur)
                return False
            iotype = obj.gete(iokid)['type']
            if iotype.startswith('Role'):
                r = obj.map_role_dev(iokid)
                self.roledev[handle] = r
                return r
            io = obj.io(iokid)
            if not io:
                self.log.debug('IO Not found', handle, repr(hp), cur)
                return False
        # Init a new sample, but only if it was updated
        isSample = handle.startswith('smp') and prop['parent'] == 'nSamples'
        if isSample and (oldentry[0] is not obj):
            self.log.debug('mapRoleDev: re-initializing sample', handle)
            self.init_sample(obj, handle)
        # Remember the association
        self.roledev[handle] = (obj, preset, io)
        # Proxy the object
        if io == False:
            self.putSubHandler(handle, obj)
        return obj, preset, io

    def dev2role(self, fullpath):
        """Search a role for device fullpath"""
        for role, obj in self.roledev.iteritems():
            obj = obj[0]
            if not obj:
                continue
            if obj['fullpath'] == fullpath:
                return role
        return False

    def xmlrpc_roledev(self, handle):
        """Debug print of assigned roledevs"""
        obj = self.roledev.get(handle, [False, False, False])
        if obj[0] is False:
            return 'NO OBJECT ' + handle
        return obj[0]['fullpath'], obj[1:]

    def wiring(self, definitions=False):
        """Render a dot file representing all RoleIO relations of this object and all its children."""
        """
        digraph structs {
            node [shape=record];
            "name0 fullpath0"[label="<out1> first out|<out2> second out|<out3> third out"];
            "name1 fullpath1"[label="<role1> first role|<role2> second role|<role3> third role"];
            "name0 fullpath0":out1 -> "name1 fullpath1":role2;
        }
        """
        body = ''
        main_call = definitions is False
        if main_call:
            definitions = defaultdict(list)
        title = '{}\\n{}'.format(self['name'], self['fullpath'])
        for (handle, (obj, preset, io)) in self.roledev.iteritems():
            definitions[title].append(handle)
            if obj is False:
                continue
            title_dev = '{}\\n{}'.format(obj['name'], obj['fullpath'])
            if io is False:
                connection = '"{}":{} -> "{}";\n'.format(title, handle, title_dev)
            else:
                connection = '"{}":{} -> "{}":{};\n'.format(
                    title, handle, title_dev, io.handle)
                definitions[title_dev].append(io.handle)
            body += connection
        # Recursive call
        for obj in self.devices:
            obj_body, definitions = obj.wiring(definitions)
            body += obj_body

        if not main_call:
            return body, definitions

        if body == '':
            return ''
        # Add definitions fields
        header = ''
        for title, sockets in definitions.iteritems():
            label = '<{}> {}|' * len(sockets)
            sockets2 = []
            for s in sockets: sockets2+=[s,s]
            label = label.format(*sockets2)[:-1]
            header += '"{}" [label="{} |{}"];\n'.format(title,title,label)
        return 'digraph {{\n rankdir=LR;\n node [shape=record];\n{}\n{}\n}}'.format(header, body)

    xmlrpc_wiring = wiring

    def init_sample(self, obj, handle):
        pass

    def check(self):
        # Skip if initializing.
        if self['initializing']:
            self.log.debug('Cannot check() while initializing')
            return False
        # Join any finished child procs
        multiprocessing.active_children()
        # Refresh running status
        self['running']
        self.check_children()
        return True
    xmlrpc_check = check

    def check_children(self):
        """Propagate check() to all subdevices."""
        done = [self]
        for name, obj in self.subHandlers.items():
            if obj in done:
                continue
            # Non-Device children
            if not hasattr(obj, '__getitem__'):
                continue
            if getattr(obj, 'desc', False) is False:
                self.log.error(
                    'Child object does not have a description:', name, obj)
                del self.subHandlers[name]
                continue
            ck = getattr(obj, 'check', False)
            if not ck:
                continue
            r = 0
            try:
                r = ck()
            except:
                self.log.error('check error', format_exc())
            if not r:
                r = -1
            # Increase/decrease error count
            anerr = obj['anerr'] - r
            # Avoid below-zero runaway
            if anerr >= 0:
                obj['anerr'] = anerr
            done.append(obj)
            
    def do_self_test(self):
        """Returns a list of (status, message) validation items"""
        return True, []
    
    def get_selfTest(self):
        """Returns local validation items"""
        return [self.desc.get('selfTest')[0]]+self.do_self_test()[1]
            
    def do_iter_test(self, done=False):
        """Collects validation items from across all subdevices"""
        p = self['fullpath']
        done = done or [p]
        status = []
        for item in self.do_self_test()[1]:
            status.append(item+[p])
        ok = True
        for name, obj in self.subHandlers.items():
            if name=='desc':
                continue
            if not getattr(obj, 'do_iter_test', False):
                self.log.error('Child object cannot be validated', name, obj)
                continue
            p = obj['fullpath']
            if p in done:
                continue
            ok1, status1 = obj.do_iter_test(done)
            for item in status1:
                status.append(item+[p])
            ok *= ok1
            done.append(p)
        return ok, status
    
    xmlrpc_do_iter_test = do_iter_test
            
    def get_validate(self):
        """Pre-test status validation and error reporting"""
        cur = self.desc.get('validate')[0]
        return [cur]+self.do_iter_test()[1]
    
    def lock(self, blocking=True, exc=False):
        """Blocks current operations on device.
        `blocking`=False immediately returns the lock status (default: True, wait until free).
        `exc`=True throws an exception if device is locked (default: False, ignore)."""
        a = self._lock.acquire(blocking)
        if not blocking:
            if not a and exc:
                self.log.debug('Already locked')
                raise AlreadyLocked()
        if not a:
            print 'Impossible to acquire lock', a
        return a

    def get_locked(self):
        # Returns True if locked
        r = self._lock.acquire(False)
        # If it was not locked, release it immediately
        if r:
            self._lock.release()
        return not r

    def set_locked(self, v):
        if v:
            self._lock.acquire(1)
        else:
            self.unlock()
        return v

    def unlock(self):
        """Unblock device for concurrent operations."""
        try:
            self._lock.release()
        except:
            pass
        return True
    
    @initializeme(repeatable=True)
    def applyDesc(self, desc=False):
        """Apply current settings"""
        if desc is not False:
            self.desc.update(desc)
        else:
            desc = self.desc.describe([])
        # Trigger get/set function for options involving Hardware
        kn = self.desc.getKeep_names()
        # Sort by priority
        items = desc.values()
        items.sort(option.prop_sorter)
        if self['isConnected']:
            for ent in items:
                key = ent['handle']
                if key in kn:
                    continue
                if ent['type'] in ['ReadOnly', 'Button', 'Hidden', 'Progress']:
                    continue
                ro = set(['ReadOnly', 'Runtime']) - set(ent['attr'])
                if len(ro) < 2:
                    continue
                if self.controls.has_key(key):
                    self.log.info(
                        'Loading option control', key, ent['current'])
                    self.controls[key].set(ent['current'])
                elif 'Hardware' in ent['attr']:
                    self.log.info('Loading option', key, ent['current'])
                    self.set(key, ent['current'])
                elif ent['type'].startswith('Role'):
                    self.log.info('Loading role', key, ent['current'])
                    self.map_role_dev(key)
        return desc

    def io(self, handle):
        """Return an InputOutput object for option `handle`."""
        for opt in self.desc.describe().itervalues():
            if opt['handle'] == handle:
                return InputOutput(opt, self)
        return None

    def init_instrument(self, name=False, sub=True):
        """Initialize device for instrument `name` use"""
        preset = self.validate_preset_name(name)
        self.set_preset(preset)
        # Initialize sub-devices
        if sub:
            for dev in self.devices:
                dev.init_instrument(name)
        self.log.info(
            'Initialized instrument:', name, self['name'], self['devpath'])
        return True

    xmlrpc_init_instrument = init_instrument

    def init_acquisition(self, instrument, *args):
        """Here each device should prepare itself for acquisition, and create a reference to the acquisition instrument.
        It should also return tableName, tableTitle"""
        self.reset_acquisition()
        return True

    def prepare_control_loop(self, *a, **kwa):
        """Preparation for the run_acquisition control loop. Runs in the same subprocess.
        Returns True if the device control is allowed to start, False if there was an initialization problem and
        run_acquisition should abort.
        Separed for testing purposes"""
        self['anerr'] = 0
        return True

    def set_monitor(self, k):
        """Append kid `k` to `monitor` option if missing.
        If `k` is a sequence, fully replace the option."""
        if isinstance(k, list) or isinstance(k, tuple):
            return k
        m = self['monitor']
        if k not in m:
            m.append(k)
        return m

    def oldest_refresh_time(self, monitored):
        """Find the option with oldest refresh time in `monitored` list of options"""
        t = utils.time()
        delta = 0
        delta_opt = False
        for k in monitored:
            obj, opt = self.read_kid(k)
            if not obj:
                self.log.debug('Monitored option not found', k)
                continue
            oldest = obj.h_time_at(opt, -1)
            d = t-oldest
            if d > delta:
                delta = d
                delta_opt = k
        return delta_opt, delta

    def control_loop(self):
        """Called each acquisition/control iteration, in a separate process.
        Reads each option referenced in `monitor` option.
        Reads all custom controls with in_acquisition_process flag set.
        """
        n = 0
        t = utils.time()
        # Manage special controls
        for handle, ctrl in self.controls.iteritems():
            if not ctrl.in_acquisition_process:
                continue
            n += 1
            v = ctrl._get()
            if v is None:
                self.log.debug(
                    'Error reading `{}` in acquisition process'.format(handle))
                continue
            # Set new value in-memory
            self.desc.set(handle, v)
        # Manage monitored options
        m = self['monitor']
        if not n and len(m) == 0:
            self.log.error(
                'No control and no monitored options were defined for acquisition. Exiting.')
            return False
        m0 = m[:]
        for k in m0:
            obj, opt = self.read_kid(k)
            if not obj:
                self.log.debug('Monitored option does not exist:', k)
                m.remove(k)
                continue
            try:
                v = obj[opt]
                e = self['anerr']
                if e > 0:
                    self['anerr'] = e - 1
            except:
                self['anerr'] += 1
                self.log.error('Error getting monitored option {} in parallel process.'.format(
                    opt), format_exc())
        # Purge non-existent options from monitor list
        if len(m) != len(m0):
            self.desc.set('monitor', m)
        self.limit_freq(t)
        return True

    def limit_freq(self, t):
        """Wait if cycle is faster than device frequency"""
        t1 = utils.time()
        t = (1. / self['maxfreq']) - (t1 - t)
        t = min(t, 10)  # Minimum freq is 0.1!
        if t > 0:
            utils.sleep(0.99 * t)

    def process_alive(self):
        pid = self['pid']
        multiprocessing.active_children()
        return utils.check_pid(pid)


    def xmlrpc_process_alive(self):
        return self.process_alive()

    def set_running(self, nval, zt=-1):
        """Start/stop the acquisition process"""
        if nval and self['initializing']:
            self.log.error(
                'Cannot start parallel acquisition while still initializing')
            nval = 0
        nval = int(nval)
        current = self.desc.get('running')
        if current == nval:
            self.log.debug('Running state already set:', current)
            return current
        nval0 = nval
        if nval == 2:
            nval = 0
        # immediately communicate the new status
        self.desc.set('running', nval)
        self.log.debug('running set to', nval)
        if nval0 == 2:
            return nval
        if nval == 0:
            # Wait until the process stops
            if self.process_alive():
                # Called while closing...
                if self['initializing']:
                    self.log.debug('Trying to stop process while initializing')
                    return 0
                pid = self['pid']
                self.log.debug('A parallel process was defined.', pid)
                self.desc.set('running', 0)
                r = utils.join_pid(pid, 12, self['fullpath'])
                self.desc.set('running', 0)
                if not r:
                    self.log.critical('Terminating acquisition process!', pid, 
                                      self.desc.get('running'), self['running'])
                    utils.kill_pid(pid)
                self.unlock()
                self.process = False
                self['pid'] = 0
        else:
            if self.process_alive():
                self.log.error(
                    'Asked to start but already running as pid', self['pid'])
                return 1
            # Start a new subprocess
            if zt < 0:
                zt = self.root_obj['zerotime']
            self.log.info('Starting acquisition process')
            self.reset_acquisition()
            self.desc.set('running', 1)
            self.process = multiprocessing.Process(target=self.run_acquisition, args=(
                zt,), name=self['fullpath'] + 'run_acquisition')
            self.process.daemon = self._daemon_acquisition_process
            self.process.start()
            self['pid'] = self.process.ident
            self.log.info(
                'Started acquisition process with pid', self.process.ident)
            nval = 1
        multiprocessing.active_children()
        return nval

    def get_running(self):
        """Retrieve the parallel acquisition process status.
        It is a combination of the in-memory valued AND the real process status."""
        p = self.process_alive()
        r = self.desc.get('running')
        if not p:
            # no process
            return 0  # stopped
        if r != 1:
            # flag unset, process alive
            return 2  # stopping
        # flag==alive
        return 1  # running

    def soft_get(self, key):
        """Avoid triggering actions on opt requests while the device is already running.
        Get a key from memory if running, from self if not running."""
        if self['running'] != 0:
            return self.desc.get(key)
        else:
            return self.get(key)

    xmlrpc_soft_get = soft_get

    def run_acquisition(self, zerotime, *args):
        """Continously call control_loop.
        """
        self.isDevice = True
        if self.desc.has_key('zerotime'):
            self['zerotime'] = zerotime
        self.set('analysis', True)
        self.desc.set('running', 1)
        self.log.debug('run_acquisition set running to', self.desc.get('running') )
        if not self.prepare_control_loop(utils.time()):
            self.log.error(
                "Control loop initialization problem. Aborting device control.")
            self.end_acquisition()
            return
        while True:
            try:
                if not self.control_loop():
                    self.log.debug('Control loop returned False')
                    break
            except:
                self.log.error('control_loop exception', format_exc)
                break
            if self.desc.get('running') != 1:
                self.log.debug('Exited from running state')
                break
            anerr = self['anerr']
            maxErr = self['maxErr']
            if not anerr < maxErr:
                self.log.debug('Exceeded maximum error count', anerr, maxErr)
                break
            continue
        self.end_acquisition()

    def end_acquisition(self):
        """Executed when acquisition loop ends"""
        self.set('analysis', False)
        self.desc.set('running', 0)
        self.log.debug('Acquisition loop ended.')

    @unlockme
    def reset_acquisition(self):
        """Clears out the history buffer and resets all History values to factory defaults.
        Run at acquisition initialization and right before starting the acquisition subprocess.
        Always run in the main server process."""
        self.log.debug('Resetting options for new acquisition.')
        self['anerr'] = 0
        # Ensure reset of Meta options
        for k, opt in self.desc.describe().iteritems():
            if opt['type'] != 'Meta':
                continue
            self.desc.set(k, {'temp': 'None', 'time': 'None', 'value': 'None'})
        # Clear history buffer
        self.desc.h_clear()

    def close(self):
        if self.desc is False:
            return False
        print 'Device.close', self
        self['initializing'] = True
        self.set_running(0)
        try:
            dp = self.desc.get('devpath')
            dev = self.desc.get('dev')
            get_registry().purge(dev)
            cls = self.__class__
            print 'deleting available', dp, dev
            if cls.available.has_key(dp):
                del self.__class__.available[dp]
        except:
            pass
        return Node.close(self)

    def xmlrpc_close(self, writeLevel=4):
        return self.close()

    def __del__(self):
        if hasattr(self, 'desc'):
            self.close()
