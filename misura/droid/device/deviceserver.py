#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Main Interfaces"""
from traceback import print_exc, format_exc
import os
from time import sleep
from copy import deepcopy

from device import Device,  get_registry

from misura.canon.csutil import unlockme

conf = [
    {"handle": 'waiting', "name": 'Waiting sub devices',
        "attr": ['ReadOnly'], "type": 'Integer'},
    {"handle": 'rescan', "name": 'Scan for new devices',
        "type": 'Button', "readLevel": 3},
    {"handle": 'order', "name": 'Initialization Order',
        "type": 'TextArea', "readLevel": 4},
    {"handle": 'devlist',   "name": 'List of served devices',
        "type": 'TextArea', "readLevel": 3},
    {"handle": 'blacklist', "name": 'Comma-separed list of blacklisted devices',
        "type": 'String', "readLevel": 4},
    {"handle": 'servedClasses', "name": 'List of served device classes',
        "type": 'String', "readLevel": 4},
    {"handle": 'initInstrument', "name": 'Initializing devices',
        "type": 'Progress', "attr": ['Runtime']},
]


class DeviceServer(Device):

    """Implements generally useful methods for device servers."""
    idx = -1
    ServedClasses = False
    """Class served by this device server and used by addNode"""
    conf_def = deepcopy(Device.conf_def)
    conf_def += conf
    naturalName = 'devserver'

    def __init__(self, parent=None, node=None):
        if node is None:
            node = self.class_name.lower()
        Device.__init__(self, parent=parent, node=node)
        if parent is not None:
            parent.deviceservers.append(self)
        self.xmlrpc_naturalNaming = self.naturalNaming

    def get_servedClasses(self):
        r = ', '.join([c.__name__ for c in self.ServedClasses])
        return r

    def naturalNaming(self):
        """Add a progressive idx0-idxN xmlrpc handle to all children peripherals"""
        self.log.debug('naturalNaming')
        for i, d in enumerate(self.devices):
            sub = d.fixedNaturalName
            if not sub:
                sub = 'idx%i' % i
            # If subhandler is missing, define it
            if self.getSubHandler(sub) == None:
                d = self.devices[i]
                d.idx = i
                self.putSubHandler(sub, d)
                setattr(self, sub, d)
                d.naturalName = sub
                d.log.info('naturalNaming:', str(d))
        return True

    @unlockme
    def addNode(self, node, served_class=False):
        """Build a child device for `node`. Scans over all ServedClasses until the first validates."""
        if not self.ServedClasses:
            self.log.error(
                "Impossible to addNode(%s). No ServedClasses defined!" % node)
            return False
        # Avoid duplicating a device
        if self.search_opt('devpath', node) is not False:
            self.log.info('Device already mapped:', node, self.class_name)
            return True
        # Recursive call with all served classes
        if not served_class:
            for cls in self.ServedClasses:
                # Must unlock for autocalls
                self.unlock()
                r = self.addNode(node, served_class=cls)
                if r:
                    return r
            return False
        elif not self['scan_'+served_class.__name__]:
            self.log.debug('ServedClass is disabled by configuration', served_class.__name__)
            return False
        # Do addNode
        self.log.debug('addNode', served_class,  node)
        # Locking should fail in autocalls
        self.lock(False)
        dev = served_class(parent=self, node=node)
        bl = self['blacklist'].replace(', ', ',').split(',')
        self.log.debug('Connecting', dev['fullpath'])
        r = False
        try:
            r = dev.connection(bl)
        except:
            self.log.debug(
                'Exception while connecting new device', format_exc())
        if dev['isConnected']:
            self.log.debug(
                'Recognized node', node, dev, dev['dev'], dev['devpath'])
            i = len(self.devices) - 1
            name = 'idx%i' % i
            dev.idx = i
            setattr(self, name, dev)
            dev.post_connection()
            return True
        else:
            self.log.debug('Discarted node', node, self)
            cd = dev.conf_dir
            dev.close()
            if os.path.exists(cd):
                if len(os.listdir(cd)) == 0:
                    print 'Removing dir', cd
                    os.rmdir(cd)
            return False

    def removeNode(self, node):
        dev = False
        dev = self.search_opt('devpath', node)
        if not dev:
            self.log.debug('No node found', node)
            return False
        # Closing will automatically remove the node from devices and from
        # subhandlers
        name = dev['name']
        fp = dev['fullpath']
        dev.close()
        del dev
        self.log.info('Dropped device:', name, fp)
        return True

    def get_rescan(self):
        p = self.parent()
        if p:
            p.pause_check()
        self.unlock()
        self['initializing'] = True
        registry = get_registry()
        # Trigger simulators reset
        if self.desc.has_key('simulators'):
            self['simulators'] = self['simulators']
        if not self.ServedClasses:
            self['initializing'] = False
            if p:
                p.resume_check()
            return False
        dspath = self['fullpath']
        # Free the registry from all devices assigned myself
        registry.free_all(dspath)
        # Call pre-scan hook on each served object
        for d in self.devices[:]:
            print 'Checking device', d
            ok = d.__class__ in self.ServedClasses
            ok *= d.check()
            if not ok:
                self.log.error(
                    'Device self-check failed! Removing', d['fullpath'])
                d.close()
                continue
            print 'keeping', d.__class__, self.ServedClasses
            # Reassign active devices
            registry.assign(d, dspath)
            d.pre_scan()
        new = []
        for cls in self.ServedClasses:
            print 'rescan class',cls
            # Intercept Enumerated devices and refresh their value
            eo = getattr(cls, 'enumerated_option', False)
            if eo:
                self[eo] = self[eo]
            cls.list_available_devices()
            print self.class_name + '::SCANNING::', cls, cls.available
            free = registry.check_available(cls.available)
            print self.class_name + '::SCANNING::', free
            # Continue scanning until there are no more availed or non-failed
            # nodes
            for path in free:
                print self.class_name + '::FREE::', free
                an = False
                print '>>Trying path', path
                # Try to reserve the device in the registry, as pending
                r = registry.reserve(path, dspath)
                # If the insertion fails, sleep and then continue (maybe is in
                # use)
                if not r:
                    sleep(.1)
                    # If the dev was permanently assigned,
                    # it will never be listed as free again
                    free = registry.check_available(cls.available)
                    continue
                try:
                    an = self.addNode(path, served_class=cls)
                except:
                    print_exc()
                    an = False
                if not an:
                    # If instantiation failed, free the registry
                    registry.free(path, dspath)
                else:
                    # Permanently assign
                    registry.assign(path, dspath)
                    new.append(path)
                free = registry.check_available(cls.available)
                print 'Rescan iteration'
        # Refreshing alternative naming
        self.naturalNaming()
        # Initializing found nodes
        self['initializing'] = False
#       self.init_instrument(partial=new)
        # Clear cached model
        self._rmodel = False
        getattr(p, 'resume_check', lambda:0)()
        return True

    def _get_rescan(self):
        self.unlock()
        self['initializing'] = True
        # Trigger simulators reset
        if self.desc.has_key('simulators'):
            self['simulators'] = self['simulators']
        if not self.ServedClasses:
            return False
        dspath = self['fullpath']
        # Call pre-scan hook on each served object
        for d in self.devices:
            registry.assign(d, self)
            d.pre_scan()
        self.allavail = []

        def avail(cls, assigned):
            """Calculates the available device list"""
            # All possible devices (also connected, failed, connecting...)
            preassigned = set([d['devpath'] for d in self.devices])
            print self.class_name + '::PREASSIGNED =>', preassigned
            print self.class_name + '::CONNECTED =>', cls.available
            lst0 = cls.available
            self.allavail += lst0
            lst = list(set(lst0) - preassigned)
            print self.class_name + '::PRELIST =>', lst, lst0
            # Check for devices which are not currently connecting to another
            # DeviceServer
            lst = registry.check_available(lst)
            print self.class_name + '::REGAVAIL =>', lst
            # Leave only devices which did not already fail or succeed
            lst = list(set(lst) - set(assigned))
            print self.class_name + '::AVAIL =>', lst
            return lst

        for cls in self.ServedClasses:
            print self.class_name + '::SCANNING::', cls, cls.list_available_devices()
            # Continue scanning until there are no more availed or non-failed
            # nodes
            failed = []
            succeed = []
            ndl = avail(cls, failed)
            while len(ndl) > 0:
                an = False
                path = ndl[0]
                print '>>Trying path', path
                # Try to insert the device in the registry as pending
                r = registry.assign(path, dspath)
                # If the insertion fails, sleep and then continue
                if not r:
                    sleep(.5)
                    ndl = avail(cls, failed)
                    continue
                try:
                    an = self.addNode(path, served_class=cls)
                    if an:
                        succeed.append(path)
                except:
                    print_exc()
                    an = False
                    registry.free(path, dspath)
                if not an:
                    failed.append(path)
                ndl = avail(cls, failed + succeed)
                print 'Rescan iteration', an, failed, succeed, ndl
        self.naturalNaming()
        # Removing non-existent nodes
        allavail = set(self.allavail)
        preassigned = set([d['devpath'] for d in self.devices])
        removing = list(preassigned - allavail)
        print self.class_name + '::REMOVING NODES =>', removing
        for rempath in removing:
            self.removeNode(rempath)

        # Initializing found nodes:
        self['initializing'] = False
        self.init_instrument(partial=succeed)
        self._rmodel = False
        return True

    def get_devlist(self, partial=False,  order=False):
        """Get an ordered device listing. Sub-devices can also be specified."""
        devlist = [d['devpath'] for d in self.devices]
        if partial is False:
            partial = devlist[:]
        if not order:
            order = self['order']
        prio = order.splitlines()
        print 'priority:', prio
        undef = list(set(partial) - set(prio))
        undef.sort(key=lambda p: partial.index(p))
        print 'undefined:', undef
        # Append existing devices which does not compare in the ordered list
        prio += undef
        print 'final priority:', prio
        return '\n'.join(prio)

    def get_initializing(self):
        """"A DeviceServer is considered initializing whenever:
        - the object is being created
        - an instrument configuration is being initialized"""
        return self.desc.get('initializing') or self['initInstrument']

    def init_instrument(self, name=False, partial=False, presets={}):
        """Load default or instrument configuration for all subdevices"""
        # avoid doubled calls
        if self['initializing']:
            return False
        # Load the preset associated with 'name', to get the proper init order
        self['initializing'] = True
        Device.init_instrument(self, name, sub=False)
        prio = self.get_devlist(partial).splitlines()
        done = []
        # Prepare progress indicator
        self.setattr('initInstrument', 'max', len(prio) + 1)
        self['initInstrument'] = 1
        # Add to global server progress
        if self.root:
            self.root.set('progress', self['fullpath'] + 'initInstrument')
        for path in prio:
            # END placeholder breaks the device sequence
            if path == '#END':
                break
            d = self.child(path)
            self['initInstrument'] += 1
            if d is None:
                self.log.error('Child not found!', path)
                continue
            preset = presets.get(path, name)
            self['preset'] = preset
            d.init_instrument(preset)
            done.append(path)
        self['initInstrument'] = 0
        self['initializing'] = False
        return done

    xmlrpc_init_instrument = init_instrument

    def close(self):
        """Recursively calls close() an all served devicess"""
        print 'DeviceServer will now close', self.devices
        for b in self.devices:
            print 'DeviceServer closing:', b, repr(b.close)
            b.close()
            print 'Done'
        Device.close(self)
