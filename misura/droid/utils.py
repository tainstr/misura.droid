#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Utilities and constants common to all misura server-side modules."""
import types
import os
import functools
from time import time, sleep
from glob import glob
from commands import getstatusoutput
import multiprocessing

from numpy import array
import numpy as np

from twisted.web import xmlrpc
from twisted.internet import defer, threads

from . import parameters as params
from misura.canon import csutil
from misura.canon.csutil import *

csutil.binfunc = xmlrpc.Binary


def defer(func):
    """deferToThread decorator"""
    # FIXME
    @functools.wraps(func)
    def defer_wrapper(self, *args, **kwargs):
        # Skip deferring if unittesting
        if params.ut:
            return func(self, *args, **kwargs)
        d = threads.deferToThread(func, self, *args, **kwargs)
        return d
    return defer_wrapper

############
# MULTIPROCESSING
#


def check_pid(pid):
    """ Check For the existence of a unix pid. """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def join_pid(pid, timeout=10, label=''):
    """Wait until process `pid` finishes."""
    if pid <= 0:
        return True
    t0 = time()
    while time() - t0 <= timeout:
        multiprocessing.active_children()
        if not check_pid(pid):
            return True
        sleep(.5)
        print label, 'Still waiting for subprocess', pid
    return False


def kill_pid(pid):
    """Terminate process `pid`"""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 9)
    except OSError:
        return False
    else:
        return True
# à


def listDirExt(dir, ext=params.conf_ext, create=False):
    """Elenca tutti i file con estensione `ext` contenuti nella cartella `dir`"""
    if create:
        if not os.path.exists(dir):
            os.makedirs(dir)
            return []
    l = os.listdir(dir)
    n = len(ext)
    r = []
    for e in l:
        if n > 0:
            if e[-n:] != ext:
                continue
            r.append(e[:-n])
        else:
            r.append(e)
    return sorted(r, cmp=lambda x,y: cmp(x.lower(), y.lower()))


def latestFile(path):
    ls = os.listdir(path)
    ls = [path + f for f in ls]
    if not len(ls):
        return None
    latest_file = max(ls, key=os.path.getmtime)
    return latest_file


def newestFileModified(lst):
    mod = [os.stat(f).st_mtime for f in lst]
    i = mod.index(np.max(mod))
    return lst[i]


def oldestFileModified(lst):
    mod = [os.stat(f).st_mtime for f in lst]
    i = mod.index(np.min(mod))
    return lst[i]


def crc(s):
    """Calculate CRC16 MSB+LSB 4 bytes to append each message in a ModBus transaction"""
    crc = 0xffff
    for b in s:
        crc = crc ^ (ord(b))
        for j in range(8):
            if crc % 2:
                crc = ((crc >> 1) ^ 0xA001)
            else:
                crc = crc >> 1
    lsb, msb = divmod(crc,  256)
    return chr(msb) + chr(lsb)

from commands import getstatusoutput as gopt


def go(cmd):
    """Failsafe bash execution"""
    err, out = gopt(cmd)
    if err != 0:
        print 'Error %i executing %s:' % (err, cmd)
        print out
    return err, out


# http://code.activestate.com/recipes/219300/
# Convert positive integer to bit string
int2bitstring = lambda n: n > 0 and int2bitstring(n >> 1) + str(n & 1) or ''


def get_history(buf, start_time=False):
    t = buf[-1]
    if t == []:
        return time(), []
    if len(t) > 1:
        t = t[0]
    else:
        t = 0
    # Se start_time non è specificato, restituisce le ultime 10 righe
    if not start_time:
        fromn = -10
    # Altrimenti ricerco nel log la posizione di start_time
    else:
        fromn = buf.get_time(start_time)
    return t, buf[fromn:]

def apply_time_delta(delta):
    """Change hardware clock by `delta` seconds"""
    if delta < 1:
        return False
    print 'APPLY TIME DELTA',delta
    ago = ''
    if delta<0:
        ago = 'ago'
        delta = abs(delta)
    cmd = "date -s '{} seconds {}'".format(delta, ago)
    r=go(cmd)
    # Sync to hardware clock for next reboot
    r1 = go("sudo hwclock --systohc")
    print 'apply_time_delta',cmd,r,r1

avahi = False
dbus = False
try:
    import avahi
    import dbus
except:
    pass


class ZeroconfService:

    """A simple class to publish a network service with zeroconf using avahi.
    Credits: http://stackp.online.fr/?p=35
    """

    def __init__(self, name, port, stype="_https._tcp",
                 domain="", host="", text=""):
        self.name = name
        self.stype = stype
        self.domain = domain
        self.host = host
        self.port = port
        self.text = text

    def publish(self):
        bus = dbus.SystemBus()
        server = dbus.Interface(
            bus.get_object(
                avahi.DBUS_NAME,
                avahi.DBUS_PATH_SERVER),
            avahi.DBUS_INTERFACE_SERVER)

        g = dbus.Interface(
            bus.get_object(avahi.DBUS_NAME,
                           server.EntryGroupNew()),
            avahi.DBUS_INTERFACE_ENTRY_GROUP)

        g.AddService(avahi.IF_UNSPEC, avahi.PROTO_UNSPEC, dbus.UInt32(0),
                     self.name, self.stype, self.domain, self.host,
                     dbus.UInt16(self.port), self.text)

        g.Commit()
        self.group = g

    def unpublish(self):
        self.group.Reset()


def testZCS():
    service = ZeroconfService(name="TestService", port=3000)
    service.publish()
    raw_input("Press any key to unpublish the service ")
    service.unpublish()


class void(object):
    pass


###
# UDEV UTILITIES
# To uniquely identify a device based on its hw connection
###

def query_udev_tree(node):
    """Parses udevinfo about device `node`. Returns a dictionary of values."""
    s, out = go("udevadm info -a -p $(udevadm info -q path -n %s)" % node)
    if s != 0:
        return False
    tree = []
    begin = False
    for line in out.splitlines():
        if 'looking at device ' in line or 'looking at parent device ' in line:
            if begin:
                tree.append(prop)
            prop = {'ATTRS': {}}
            begin = True
            ip = line.find("'") + 1
            op = line.find("'", ip)
            path = line[ip:op]
            prop['path'] = path
            continue
        elif not begin or '==' not in line:
            continue
        line = line.replace(' ', '')
        key, val = line.split('==')[:2]
        val = val[1:-1]
        if 'ATTRS{' in key:
            key = key[6:-1]
            prop['ATTRS'][key] = val
            continue
        prop[key] = val
#   print "query_udev_tree", tree
    return tree


def queryFtdiSerial(node):
    tree = query_udev_tree(node)
    if not tree:
        return False, tree
    for dev in tree:
        # skip non-parent devices
        if not dev.has_key('ATTRS'):
            continue
        attrs = dev['ATTRS']
        if not attrs.has_key('serial'):
            continue
        if not attrs.has_key('idProduct') and not attrs.has_key('idVendor'):
            continue
        # Returns a serial only if dev is FTDI family
        if attrs['idProduct'] not in ['6001', 'b3a8'] or attrs['idVendor'] != '0403':
            continue
        if attrs.has_key('serial'):
            return attrs['serial'], tree
    return False, tree

import string


def validate_obj_name(name, valid=string.letters + string.digits, replace='_'):
    """Replace all non valid Python object characters with `replace` string"""
    new = ''
    for s in name:
        if s not in valid:
            new += replace
        else:
            new += s
    return new


def query_udev(node):
    # Intercept pure serial nodes
    if node.startswith('/dev/ttyS'):
        return node.split('/')[-1], [{}]
    serial, tree = queryFtdiSerial(node)
    if serial:
        return 's' + serial, tree
    if not tree:
        return False, False
    vbus = []
    for dev in tree:
        bus = ''
        dri = dev.get('DRIVERS')
        if not dri or dri != 'usb':
            continue
        kn = dev.get('KERNELS')
        if kn:
            bus += kn + ':'
        attrs = dev['ATTRS']
        # Check if vid:pid are forbidden
        pid = attrs.get('idProduct', '____')
        vid = attrs.get('idVendor', '____')
        if '%s:%s' % (vid, pid) in params.forbiddenID:
            return False, False
        for a in ['idProduct', 'idVendor', 'serial']:
            if attrs.get(a, False):
                bus += attrs.get(a) + 'I'
        vbus.append(bus[:-1])
    dp = '_'.join(vbus)
    dp = validate_obj_name(dp)
    return dp, tree


def count_usb_devices(supported):
    """Count number of devices in sysfs with matching idVendor and idProduct.
    ` supported`={idVend0:[idProd0,idProd1,...],
                            idVend1:[idProd10,idProd11,...], ... }"""
    n = 0
    r = []
    lst = glob('/sys/bus/usb/devices/*')
    for d in lst:
        fv = d + '/idVendor'
        if not os.path.exists(fv):
            continue
        vid = open(fv, 'r').read()[:-1].upper()
        if not supported.has_key(vid):
            continue
        fp = d + '/idProduct'
        if not os.path.exists(fp):
            continue
        pid = open(fp, 'r').read()[:-1].upper()
        if pid not in supported[vid]:
            continue
        r.append('{}/{}:{}'.format(d, vid, pid))
        n += 1
    print 'devices', n, r
    return n


def beep():
    getstatusoutput('beep')


def uname(flags):
    s, o = getstatusoutput('uname ' + flags)
    return o


def validateRow(row):
    """Valida una lista di righe per l'aggiunta ad una tabella"""
    lt = [types.ListType, type(array([]))]
    if not type(row) in lt:
        return False
    if len(row) < 1:
        return False
    if type(row[0]) not in lt:
        row = [row]
    for el in row:
        if type(el) not in lt:
            row.remove(el)
        if len(el) < 1:
            row.remove(el)
    return row


def smooth(x, window_len=5, window='hanning'):
    if x.ndim != 1:
        raise ValueError, "smooth only accepts 1 dimension arrays."
    if x.size < window_len:
        raise ValueError, "Input vector must be bigger than window size."
    if window_len < 3:
        return x
    if not window in ['flat', 'hanning', 'hamming', 'bartlett', 'blackman']:
        raise ValueError, "Window is on of 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'"
    s = np.r_[2 * x[0] - x[window_len - 1::-1],
                 x, 2 * x[-1] - x[-1:-window_len:-1]]
    # print(len(s))
    if window == 'flat':  # moving average
        w = np.ones(window_len, 'd')
    else:
        w = eval('numpy.' + window + '(window_len)')
    y = np.convolve(w / w.sum(), s, mode='same')
    return y[window_len:-window_len + 1]
