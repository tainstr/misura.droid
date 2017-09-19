#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Main Interfaces"""
from traceback import print_exc, format_exc
import os
from time import sleep
from copy import deepcopy

from device import Device,  get_registry

from misura.canon.csutil import unlockme, initializeme

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

    @initializeme()
    def get_rescan(self):
        p = self.parent()
        if p:
            p.pause_check()
        self.unlock()
        registry = get_registry()
        # Trigger simulators reset
        if self.desc.has_key('simulators'):
            self['simulators'] = self['simulators']
        if not self.ServedClasses:
            if p:
                p.resume_check()
            return False
        dspath = self['fullpath']
        # Free the registry from all devices assigned myself
        registry.free_all(dspath)
        # Call pre-scan hook on each served object
        for d in self.devices[:]:
            self.log.debug('Checking device', d)
            ok = d.__class__ in self.ServedClasses
            ok *= d.check()
            if not ok:
                self.log.error(
                    'Device self-check failed! Removing', d['fullpath'])
                d.close()
                continue
            self.log.debug('keeping', d.__class__, self.ServedClasses)
            # Reassign active devices
            registry.assign(d, dspath)
            d.pre_scan()
        new = []
        for cls in self.ServedClasses:
            self.log.debug('rescan class',cls)
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
                self.log.debug(self.class_name + '::FREE::', free)
                an = False
                self.log.debug('>>Trying path', path)
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
                self.log.debug('Rescan iteration')
        # Refreshing alternative naming
        self.naturalNaming()
        # Clear cached model
        self._rmodel = False
        getattr(p, 'resume_check', lambda:0)()
        return True
    
    def do_self_test(self):
        """Append an error if a configured enumerated device is missing"""
        status, msgs = super(DeviceServer, self).do_self_test()
        registry = get_registry()
        for cls in self.ServedClasses:
            eo = getattr(cls, 'enumerated_option', False)
            if not eo: 
                # Not an enumerated
                continue
            free = list(registry.check_available(cls.available))
            if not len(free):
                # All devices are correctly detected
                continue
            status = False
            self.log.warning('Configured devices could not be found:', cls.__name__, free)
            map(lambda p: msgs.append([0, '{} not found: {}'.format(cls.__name__, p)]), free)
        return status, msgs
    
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

    @initializeme()
    def init_instrument(self, name=False, partial=False, presets={}):
        """Load default or instrument configuration for all subdevices"""
        # Load the preset associated with 'name', to get the proper init order
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
        return done

    xmlrpc_init_instrument = init_instrument

    def close(self):
        """Recursively calls close() an all served devicess"""
        print('DeviceServer will now close', self.devices)
        for b in self.devices:
            print('DeviceServer closing:', b, repr(b.close))
            b.close()
            print('Done')
        Device.close(self)
