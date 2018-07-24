#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#!/usr/bin/twistd -noy
"""Misura super server to start and manage other modules."""
# TODO: implement errors
from copy import deepcopy
from traceback import print_exc
from collections import defaultdict
from commands import getoutput as go

from misura.canon import csutil

from .. import parameters as params
from .. import device
from .. import share

import server_conf



class BaseServer(device.Device):

    """Basic server object functions. Useful for testing purposes"""
    allowNone = True
    naturalName = 'server'
    restart = False
    scanningPorts = 0
    _Method__name = 'MAINSERVER'
    name = 'server'
    conf_def = deepcopy(device.Device.conf_def)
    conf_def += server_conf.conf


    def __str__(self):
        return 'BASESERVER ' + repr(self)

    def __init__(self, manager=share.manager, confdir=params.confdir,  datadir=params.datadir):
        self.manager = manager
        self._server = self
        self._root = self
        device.Device.__init__(self, parent=None, node='MAINSERVER')
        self.separator = '/'

        self.storage, self.beholder, self.balance, self.smaug, self.morla = [
            False] * 5
        self.hsm, self.horizontal, self.vertical, self.flex, self.post, self.drop, self.kiln = [
            False] * 7
        self.instruments = []
        self.deviceservers = []
        self.main_confdir = confdir
        self.main_datadir = datadir

    def pause_check(self):
        self.shutting_down = True

    def get_instruments(self):
        """Returns the list of available Instrument names"""
        lst = [(obj['comment'] or obj['name'], obj.naturalName) for obj in self.instruments]
        self.desc.set('instruments', lst)
        return lst

    def get_deviceservers(self):
        """Returns the list of available DeviceServer names"""
        lst = [obj['name'] for obj in self.deviceservers]
        self.desc.set('deviceservers', lst)
        return lst

    @property
    def runningInstrument(self):
        ins = self['runningInstrument']
        if ins in ['', 'None', None, False]:
            return False
        obj = self.child(ins)
        if obj is None:
            return False
        return obj

    @property
    def lastInstrument(self):
        """Configured instrument, ready for test start"""
        ins = self['lastInstrument']
        if ins in ['', 'None', None, False]:
            return False
        obj = self.child(ins)
        if obj is None:
            return False
        return obj

    def get_initTest(self):
        """Retrieve initialization status from active instrument"""
        obj = self.runningInstrument
        if obj is False:
            return False
        return obj['initTest']

    def get_closingTest(self):
        """Retrieve closing status from active instrument"""
        obj = self.runningInstrument
        if obj is False:
            return False
        return obj['closingTest']

    def get_progress(self):
        """Remove finished Progress before returning the list of active tasks."""
        p = list(set(self.desc.get('progress')))
        # Clean finished progresses
        for e0 in p[:]:
            e = e0.split('/')
            # Option name
            opt = e.pop(-1)
            # Retrive the pointed object
            obj = self.child(e)
            if not obj:
                self.log.error('Operation object no longer exists!', e0)
                p.remove(e0)
            # Operation ended
            if not obj[opt]:
                self.log.debug('Operation ended', e0)
                p.remove(e0)
        # List contains still running options
        return p

    def set_progress(self, kid):
        """Append kid to the list instead of substituting"""
        p = self.desc.get('progress')
        p.append(kid)
        return p

    def check(self):
        """Check for delayed start"""
        ins = self.lastInstrument  # there must be a defined running instrument
        test_in_progress = ins and (ins['running'] + ins['initTest'] + ins['closingTest'] + ins['initializing'])

        delay = self['delay']
        delayT = self['delayT']
        T = self.kiln['T']
        last_client_access_time = self['lastClientAccessTime']
        auto_shutdown_interval = self['autoShutdownInterval']

        client_inactive = (self.time() - last_client_access_time > auto_shutdown_interval) \
                        and auto_shutdown_interval >= 300 \
                        and last_client_access_time > 0 \
                        and not test_in_progress \
                        and not self['delayStart'] \
                        and not self.time_delta

        if client_inactive:
            self.log.debug('Client inactive: halting server.')
            self.support.get_halt()

        if not ins:
            self['delayStart'] = False
        elif self['delayStart'] and delay > 0:
            d = delay - self.time()
            if -120 < d < 0 or (T<delayT and delayT>0):
                if test_in_progress == 0:
                    self.log.info('Delayed start:', self['lastInstrument'], self['delay'], self['delayT'])
                    ins.start_acquisition(userName=ins.measure['operator'])
                    self['delay'] = 0
                    self['delayT'] = -1
                    self['delayStart'] = False
                    return True
                else:
                    self.log.warning('Delayed start cannot be applied: {}, {}, {}, {}'.format(
                        ins['running'],  ins['initTest'],  ins['closingTest'],  ins['initializing']))
            elif d > 0:
                self.log.debug('Waiting for delayed start of {}. Remaining {}min. Target T: {}, current: {}'
                               .format(self['lastInstrument'], int(d / 60), delayT, T))
            else:
                self.log.error('Delayed start timed out.', d)
                self['delay'] = 0
                self['delayStart'] = False

        return device.Device.check(self)

    def set_delayStart(self, val, userName='unknown'):
        """Forbit if no instrument is configured or set operator name."""
        if not val:
            return False
        ins = self.lastInstrument
        if not ins:
            self.log.error(
                'Cannot set delayed start if no instrument is configured.')
            return False
        if ins is False:
            self.log.error('Unknown instrument for delayed start: {}'.format(repr(ins)))
            return False
        if self['isRunning'] + ins['running'] + ins['initTest'] + ins['closingTest'] + ins['initializing'] != 0:
            self.log.error(
                'Cannot set delayed start. Instrument is already running/closing.')
            return False
        if self['delay'] < self.time() + 10:
            self.log.error(
                'Delayed start require `delay` option to be set in the future.')
            return False
        self.log.debug('set_delayStart', val, userName)
        ins.measure['operator'] = userName
        return True

    def stop_acquisition(self, save=True, writeLevel=1):
        ins = self['runningInstrument']
        obj = getattr(self, ins, False)
        if obj is False:
            if ins != '':
                self.log.error(
                    'Cannot stop acquisition for running instrument:', ins)
            return False
        if not obj['analysis']:
            self.log.warning('Acquisition is not running for instrument', ins)
            return False
        return obj.stop_acquisition(save=True, writeLevel=1)
    xmlrpc_stop_acquisition = stop_acquisition

    def time(self):
        """Returns the server's time"""
        return csutil.time()
    xmlrpc_time = time

    def mapdate(self, kid_times, readLevel=0):
        """Receives a list of KID names and times to check for updates.
        Replies with two lists. The first (idx) is the list of updated positional indexes referring to
        the relative position of the option in kid_times.
        The second (rep) contains new current values.
        Is time is positive, the value is red from memory (.desc.get()).
        If negative, reading is forced through a standard get() call."""
        idx = []
        rep = []

        for i, (k,  t0) in enumerate(kid_times):
            obj, n = self.read_kid(k)
            if not obj:
                continue
            rl = obj.getattr(n, 'readLevel')
            if rl > readLevel:
                self.log.error(
                    'Permission denied for option:', n, rl, readLevel)
                continue
            # Detect forced updates
            if t0 < 0:
                rep.append(obj.get(n))
                idx.append(i)
                continue
            nt = obj.h_time_at(n)
            if nt > t0:
                # Retrieve the memory value,
                # in order not to trigger on-get updates
                rep.append(obj.desc.get(n))
                idx.append(i)
        return [idx, rep]
    xmlrpc_mapdate = csutil.sanitize(mapdate)

    def shutdown(self, *a, **k):
        try:
            self.close()
            share.stop()
        except:
            print_exc()
        from twisted.internet import reactor
        reactor.stop()

    def get_eq_mac(self):
        all_mac = go("ifconfig | grep 'HW' | awk '{ print $5}'")
        return all_mac
