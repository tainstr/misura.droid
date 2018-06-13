#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#!/usr/bin/twistd -noy
"""Misura super server to start and manage other modules."""
# TODO: implement errors
import xmlrpclib
import os
import importlib
from traceback import format_exc, print_exc
from multiprocessing import Lock, Process, Value
from multiprocessing.managers import BaseProxy
from time import time, sleep
from commands import getstatusoutput
import thread

from twisted.internet import reactor
from twisted.internet import defer, task, threads
from twisted.web import server, http, xmlrpc

from .. import parameters as params
from .. import utils
from .. import share
from .. import device

from .base import BaseServer
import stream


def iterate_plugins(plug):
    group = []
    for plug in plug.splitlines():
        if len(plug) < 2:
            continue
        if plug == '#GROUP':
            ret = group[:]
            group = []
            yield ret
        if plug.startswith('#'):
            continue
        func = False
        if '.' in plug:
            plug = plug.split('.')
            func = plug.pop(-1)
            plug = '.'.join(plug)
        try:
            m = importlib.import_module(plug)
            if func:
                m = getattr(m, func)
            group.append(m)
        except:
            print format_exc()

    yield group


class MainServer(BaseServer):
    """Live MisuraServer object"""

    reinit_instrument = False

    def __str__(self):
        return 'MAINSERVER ' + repr(self)

    def __init__(self, instanceName='',
                 port=3880,
                 confdir=params.confdir,
                 datadir=params.datadir,
                 plug=False, manager=False):
        if manager is False:
            manager = share.manager
        print('MainServer with manager', repr(manager))
        BaseServer.__init__(self, manager, confdir, datadir)
        self.time_delta = 0
#        share.Log.setStatus(self.desc)
        self.glock = Lock()
        # Announce zeroconf service
        msg = 'SERIAL=%s; HSM=%i; ODHT=%i; ODLT=%i; FLEX=%i' % (self['eq_sn'],
                                                                self['eq_hsm'],
                                                                self[
                                                                    'eq_vertical'],
                                                                self[
                                                                    'eq_horizontal'],
                                                                self['eq_flex'])
        if params.announceZeroconf:
            self.zeroconf = utils.ZeroconfService(
                name='misura' + instanceName, port=str(port), text=msg)
            self.zeroconf.publish()

        # Redefine maximum serial scan
        max_serial = self['eq_serialPorts']
        if max_serial > 0:
            device.Serial.dev_pattern = '/dev/tty*[USB][0-{}]'.format(
                max_serial)
        else:
            device.Serial.dev_pattern = '/dev/ttyUSB*'
        params.max_serial_scan = max_serial
        # Load plugins
        initializing = Value('i', 0)
        if not plug:
            plug = self['eq_plugin']

        def init(func):
            func(self)
            initializing.value -= 1
        for group in iterate_plugins(plug):
            for func in group:
                if params.init_threads:
                    initializing.value += 1
                    thread.start_new_thread(init, (func, ))
                else:
                    func(self)
            while initializing.value > 0:
                print('WAITING THREADED INITIALIZATION',
                      initializing.value, group)
                sleep(1)
        # Start the auto-check looping function
        self.looping = task.LoopingCall(self.threaded_check)
        self.looping.start(5)
        # Refresh lists
        self.xmlrpc_list()
        # Update and reset last/runningInstrument chooser
        opts = []
        vals = []
        for ins in self.instruments:
            vals.append(ins['devpath'])
            opts.append(ins['name'])
        ri = self.gete('runningInstrument')
        ri['options'] = opts
        ri['values'] = vals
        ri['current'] = ''
        self.sete('runningInstrument', ri)
        ri = self.gete('lastInstrument')
        ri['options'] = opts
        ri['values'] = vals
        ri['current'] = ''
        self.sete('lastInstrument', ri)
        self.stream = stream.MisuraDirectory(self)
        if self['eq_sn'] == 'VirtualMisuraServer':
            self.enable_simulation_server()

    def enable_simulation_server(self):
        self.log.info('Enabling simulation server')
        from misura.tests import preconf as pc
        pc.full_server(self)
        pc._full_hsm(1, self)
        pc._absolute_flex(self)
        pc._full_horizontal(self)
        self.log.info('Enabled simulation server')
        return 'done'

    xmlrpc_enable_simulation_server = enable_simulation_server

    def set_endStatus(self, val):
        """Concatenate general endStatus messages form all devices"""
        if not val:
            return ''
        msg = self['endStatus']
        if msg:
            if val not in msg:
                return msg + '\n' + val
            else:
                return msg
        else:
            return val

    def threaded_check(self):
        """Perform the global check() into a separate thread."""
        # If glock is locked, it means a previous check is still running: skip.
        if not os.path.exists(share.dbpath):
            print '#*#*#*#*#*#*#*#*#*#\n' * 5
            print 'SHARED MEMORY PANIC\n'
            print '#*#*#*#*#*#*#*#*#*#\n' * 5
            getstatusoutput('pkill -9 -f MisuraServer.py')
        if not self.glock.acquire(False):
            self.log.debug('Skipping theaded check: locked')
            return False
        if self.shutting_down:
            self.log.debug('Skipping theaded check: shutting down')
            self.glock.release()
            return False
        if self['initTest']:
            self.log.debug('Skipping theaded check: initializing new test')
            self.glock.release()
            return False

        if self['restartOnNextCheck'] and self['restartOnFinishedTest']:
            self.restart(init_instrument=True)
            self.glock.release()
            return False
        else:
            self['restartOnNextCheck'] = False

        def fcheck():
            """Do the iterative check and release glock"""
            self.log.debug('Threaded check')
            try:
                self.check()
            except:
                self.log.error('Threaded check error', format_exc())
            finally:
                self.glock.release()
        threads.deferToThread(fcheck)
        return True

    def pause_check(self):
        """Pause threaded check"""
        if not reactor.running:
            return
        BaseServer.pause_check(self)
        t0 = time()
        while time() - t0 < 5:
            r = self.glock.acquire(False)
            if r:
                break
            print 'Waiting for looping call to stop'
            sleep(.1)

    def resume_check(self):
        """Resume threaded check"""
        try:
            self.glock.release()
        except:
            pass
        self.shutting_down = False

    def get_scanning(self):
        """Check if any subdevice is scanning for hardware to become ready"""
        self.set('scanning', False)
        for dev in self.devices:
            if not dev.has_key('waiting'):
                continue
            if dev['waiting']:
                self.set('scanning', True)
                break
        return False

    def describe(self, *a, **kw):
        self.get_scanning()
        return BaseServer.describe(self, *a, **kw)

    def search_log(self, fromt=False, tot=False, maxn=None, priority=0, owner=False):
        return share.database.get_log(fromt, priority, owner, tot=tot, maxn=maxn)
    xmlrpc_search_log = search_log

    def xmlrpc_send_log(self, msg, p=10):
        """Clients can send a message to the server"""
        # easter egg
        if msg.lower() == 'ground control to major tom':
            msg = 'Major Tom to Ground Control'
        msg = '(client) ' + msg
        self.log(msg, p=p)
        return True

    def set_timeDelta(self, val):
        self.time_delta = val
        return val

    def newSession(self):
        return 1
    xmlrpc_newSession = newSession

    def close(self):
        if self.desc is False:
            return False
        self.stream.close()
        self.shutting_down = True
        self.pause_check()
        self.glock.release()

        return BaseServer.close(self)

    def restart(self, after=1, init_instrument=False, writeLevel=5, userName='unknown'):
        if after < 1:
            after = 1
        self.shutdown(after=after, restart=True, init_instrument=init_instrument, 
                      writeLevel=writeLevel, userName=userName)
        return 'Restarting in %i seconds' % after
    xmlrpc_restart = restart

    shutting_down = False

    def shutdown(self, after=1, restart=False, init_instrument=False, writeLevel=5, userName='system'):
        if self.shutting_down:
            return 'Already shutting down.'
        if writeLevel < 5:
            self.log.critical('Unauthorized shutdown request')
            return 'NotAuthorized'
        self.stop_acquisition()
        if after < 1:
            after = 0.1
        self.restart = restart
        if init_instrument:
            self.reinit_instrument = self['lastInstrument']
            self.log.info(
                'Reinitializing instrument after restart:', self.reinit_instrument)
        else:
            self.reinit_instrument = False
        self['isRunning'] = False
        self['endStatus'] = 'Forced via shutdown.'
        msg = 'SHUTDOWN'
        if restart:
            msg = 'RESTART'
        self.log.critical(
            '%s in %.1f seconds requested by user "%s"' % (msg, after, userName))
        
        utils.apply_time_delta(self.time_delta)
        
        def stop():
            from twisted.internet import reactor
            #print 'Closing everything'
            #try:
            #    self.close()
            #except:
            #    print_exc()
            print 'Stopping share'
            try:
                share.stop()
                share.close_sparse_objects()
            except:
                print_exc()
            print 'Stopping reactor'
            reactor.stop()
        task.deferLater(reactor, after, stop)
        return 'Stopping scheduled in %.1f second.' % after
        
    xmlrpc_shutdown = shutdown

    def _syncRender(self, request, function, args, kwargs):
        """Standard rendering."""
        defer.maybeDeferred(function, *args, **kwargs).addErrback(
            self._ebRender
        ).addCallback(
            self._cbRender, request
        )

    def _asyncRender(self, request, function, args, kwargs):
        """Makes all rendering asynchronous."""
        d = threads.deferToThread(function, *args, **kwargs).addErrback(
            self._ebRender
        ).addCallback(
            self._cbRender, request
        )

    def _ebRender(self, failure):
        """Trap failures into Misura logging system"""
        try:
            what = failure.getTraceback()
        except:
            what = self.FAILURE
        self.log.debug('XMLRPC Failure:', what)
        # Try to delete the entire multiprocessing connection cache
        if "Broken pipe" in what:
            for address in BaseProxy._address_to_local.iterkeys():
                del BaseProxy._address_to_local[address][0].connection
        return xmlrpc.XMLRPC._ebRender(self, failure)

    def render_POST(self, request):
        """ Overridden 'render' method which takes care of
        specialized auth and procedure lookup. """
        self['lastClientAccessTime'] = utils.time()
        rlev, wlev = 5, 5
        user = 'nouser'
        session = request.getSession()
        request.content.seek(0, 0)
        if params.useAuth:
            user = request.getUser()
            rlev, wlev = self.users.levels(user)
        # Redirect streaming POST requests:
        if wlev >= 5 and self.stream.check_POST(request):
            s = self.stream.getChild(request.path, request)
            return s.render_POST(request)
        # xmlrpc never passes parametric arguments, so I can add auth-related
        # ones here
        kwopt = {'readLevel': rlev, 'writeLevel': wlev,
                 'userName': user, 'sessionID': session, 'request': request}
        args, functionPath = xmlrpclib.loads(request.content.read())
        try:
            function = self.lookupProcedure(functionPath)
        except xmlrpclib.Fault, f:
            self._cbRender(f, request)
            return server.NOT_DONE_YET
        else:
            r = device.fill_implicit_args(function, args, kwopt)
            if r is False:
                request.setResponseCode(http.BAD_REQUEST)
                return 'Bad function call!'
            function, args, kwargs = r
            request.setHeader("content-type", "text/xml")
            self._asyncRender(request, function, args, kwargs)
            return server.NOT_DONE_YET

    def render_GET(self, request):
        """Pass GET requests to the MisuraDirectory object"""
        self['lastClientAccessTime'] = utils.time()
        s = self.stream.getChild(request.path, request)
        return s.render_GET(request)

    def lookupProcedure(self, procedurePath):
        """Route special procedure requests to the storage.test FileServer object."""
        f = 'storage' + self.separator + 'test' + self.separator
#         print 'MainServer.lookupProcedure',procedurePath, 'filtering',f
        if not procedurePath.startswith(f):
            #             print procedurePath,'was not starting with',f
            return xmlrpc.XMLRPC.lookupProcedure(self, procedurePath)
#         print 'routing to storage.test: ',procedurePath[len(f):]
        return self.storage.test.lookupProcedure(procedurePath[len(f):])
