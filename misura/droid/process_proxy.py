#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Simple remote object access via network sockets."""
import os
from time import sleep, time
from traceback import print_exc, format_exc
from multiprocessing import Process, Value
import tempfile
from misura.canon import csutil

import errno
import socket
from cPickle import loads, dumps, HIGHEST_PROTOCOL

import threading
import utils

sep = '#$#$#$****&&%$#(*⁽&%#--#--#--#'

isWindows = os.name=='nt'
base_path = '/dev/shm/misura'
if isWindows:
    base_path='C:\dev\shm\misura'

class ProcessProxy(object):
    _protect = set([])
    _process = None
    _timeout = 5
    _pid_path = ''
    _deleted = False
    _unpickled = False
    # Beware max recursion depth!
    _max_restarts = 100
    _timestamp = -1

    def __init__(self, cls, base_path=base_path, 
                 exit_on_exception=False,
                 max_restarts=100):
        """Acts as a proxy to a remote instance of `cls`
        which will be created in a parallel process upon ProcessProxy.start().
        All calls to ProcessProxy methods not starting with '_' will be redirected to the remote object.
        """
        self._cls = cls
        self._base_path = base_path
        self._exit_on_exception = exit_on_exception
        if not os.path.exists(self._base_path):
            os.makedirs(self._base_path)
        self._path = tempfile.mkdtemp(
            dir=self._base_path, prefix=self._cls.__name__ + '_')
        self._pid_path = os.path.join(self._path, 'pid')
        self._input_path = os.path.join(self._path, 'input')
        self._args = tuple()
        self._kwargs = {}
        self._log_path = ''
        self._log_owner = 'ProcessProxy'
        self._protect.update(dir(self))
        self._sockets = {}
        from misura.droid import share
        self._log = share.FileBufferLogger()
        self._restarts = Value('i')
        self._restarts.value = 0
        self._max_restart = max_restarts

    def _do_set_logging(self, log_path, owner='ProcessProxy'):
        self._log_path = log_path
        self._log_owner = owner
        self._log.log_path = log_path
        self._log.owner = owner+'pp'+self._cls.__name__+'/'
        self._log.debug('Set ProcessProxy logging to', log_path, owner)

    def _set_logging(self, log_path,  owner='ProcessProxy'):
        self._log_path = log_path
        self._log_owner = owner
        self._do_set_logging(log_path, owner)
        # Send log settings to subprocess (__ escape)
        if self._is_alive():
            self._procedure_call('__do_set_logging', log_path, owner)
        return True
    
    def _do_get_timestamp(self):
        return self._timestamp
    
    def _get_timestamp(self):
        if self._is_alive():
            return self._procedure_call('__do_get_timestamp')
        else:
            return 0       


    def __getstate__(self):
        """Prepare for pickling: remove _process and _sockets attributes because they cannot be pickled"""
        result = self.__dict__.copy()
        # A Process instance cannot be pickled (get AuthenticationString error)
        result.pop('_process')
        # Sockets cannot be pickled.
        result.pop('_sockets')
        # Synchronized objects cannot be pickled
        result.pop('_log')
        result.pop('_restarts')
        return result

    def __setstate__(self, state):
        self.__dict__ = state
        self._sockets = {}
        self._process = None
        self._unpickled = True
        from misura.droid import share
        self._log = share.FileBufferLogger()
        self._restarts = Value('i')
        self._restarts.value = 0        

    def __del__(self):
        self._max_restarts = -1
        self._deleted = True

    def _cleanup(self):
        self._sockets = {}
        for name in os.listdir(self._path):
            name = os.path.join(self._path, name)
            os.remove(name)

    def _client_socket(self, name):
        path = os.path.join(self._path, name)
        if isWindows:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self._timeout)
            s.setblocking(1)
            port = int(open(path, 'r').read())
            s.connect(('localhost', port))
        else:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(path)
        return s

    def _server_socket(self, name, listen=1, timeout=5):
        if not name in self._sockets:
            path = os.path.join(self._path, name)
            if os.path.exists(path):
                os.remove(path)
            if isWindows:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setblocking(1)
                s.bind(('localhost', 0))
                port = s.getsockname()[1]
                # Save current effective port in the socket file path
                open(path, 'w').write(str(port))
            else:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.bind(path)
            s.settimeout(timeout)
            s.listen(listen)
            self._sockets[name] = s
        return self._sockets[name]

    def _write_object(self, name, obj):
        try:
            s = self._client_socket(name)
        except:
            print('Error connecting to client socket', format_exc())
            return False
        data = dumps(obj, HIGHEST_PROTOCOL) + sep
        s.sendall(data)
        s.close()
        return True

    def _read_socket(self, s, timeout=3):
        data = b''
        t0 = time()
        while time() - t0 < timeout:
            data += s.recv(1024)
            if not data.endswith(sep):
                continue
            obj = loads(data[:-len(sep)])
            return obj
        raise BaseException('_read_socket timeout')

    def _process_packet(self, packet):
        pid, method_name, args, kwargs = loads(packet)
        if method_name!='__do_get_timestamp':
            self._timestamp = time()
        try:
            if method_name.startswith('__'):
                method = getattr(self, method_name[1:])
                print 'Local call: ', method_name, method
            else:
                method = getattr(self._instance, method_name)
            result = method(*args, **kwargs)
            ret = True
        except BaseException as e:
            self._log.error('ProcessProxy._process_packet:', method_name, format_exc())
            result = e
            ret = False
        self._write_object(pid, result)
        return ret

    def _run(self, spr=False):
        """Execution cycle runs in a separate process"""
        if spr:
            spr()
        # Write process pid
        pid = str(os.getpid())
        if os.path.exists(self._input_path):
            os.remove(self._input_path)
        s = self._server_socket('input', 1000, timeout=self._timeout)
        # Create served instance
        self._log.debug('Class parameters', pid, self._pid_path, self._cls.__name__, 
                        self._args, self._kwargs)
        self._instance = self._cls(*self._args, **self._kwargs)
        data = b''
        go = True
        open(self._pid_path, 'w').write(pid)
        while go:
            if not os.path.exists(self._pid_path):
                self._log.debug( 'ProcessProxy terminated by deletion:', pid, self._pid_path)
                break
            try:
                conn, addr = s.accept()
            except:
                continue
            conn.settimeout(self._timeout)
            while go:
                try:
                    data += conn.recv(1024)
                except:
                    break
                if sep in data:
                    packets = data.split(sep)
                    data = packets.pop(-1)
                    for packet in packets:
                        # End process if error processing packet
                        if not self._process_packet(packet):
                            go = not self._exit_on_exception
                            self._log.debug('ProcessProxy setting GO', go, self._exit_on_exception)
                            break
                    if len(data) == 0:
                        break
            conn.close()
        s.close()
        self._log.debug('ProcessProxy exiting', pid, self._pid_path)
        self._cleanup()

    def _start(self, *args, **kwargs):
        # Remove old sockets and pid file
        self._cleanup()
        self._stop()
        #TODO: user the spawn context in Python3!
        #ctx = multiprocessing.get_context("spawn")
        #ctx.Process(...
        self._process = Process(target=self._run, args=(csutil.sharedProcessResources,))
        self._args = args
        self._kwargs = kwargs
        self._process.daemon = True
        self._process.start()
        sleep(0.1)
        t0=time()
        while (not os.path.exists(self._pid_path)) and (time()-t0 < self._timeout):
            sleep(0.1)
        if not os.path.exists(self._pid_path):
            self._log.debug('ProcessProxy unable to start!!!', self._cls.__name__, 
                            self._args, 
                            self._kwargs,
                            self._pid_path)
            raise RuntimeError('ProcessProxy cannot start!!! '+self._pid_path)
        self._set_logging(self._log_path, self._log_owner)
        self._log.debug('ProcessProxy started', self._pid_path)
        
        

    def _stop(self):
        self._log.debug("ProcessProxy._stop", self._pid_path)
        r = False
        if os.path.exists(self._pid_path):
            pid = self._get_pid()
            os.remove(self._pid_path)
            sleep(0.5)
            r = utils.kill_pid(pid)
        try:
            if self._process:
                self._process.terminate()
        except:
            print_exc()
        self._process = None
        print('ProcessProxy: DONE STOPPING', self._pid_path)
        return r

    def _is_alive(self):
        if not os.path.exists(self._pid_path):
            return False
        pid = int(open(self._pid_path, 'r').read())
        return utils.check_pid(pid)

    ############
    # Caller interface
    ###
    
    def _procedure_call(self, method, *args, **kwargs):
        """Send procedure call over input socket and return result received on output socket.
        Each caller process PID has its own output socket, while the input socket is unique.
        """
        if self._deleted:
            raise BaseException('Calling a deleted ProcessProxy')
        # Start the process if it died and this object is not unpickled
        if not self._is_alive() and not self._unpickled:
            if self._max_restarts>=0 and self._restarts.value >= self._max_restarts:
                self._log.critical('ProcessProxy died too many times. Giving up', self._max_restarts, self._pid_path)
                raise RuntimeError('ProcessProxy died too many times. Giving up.', self._max_restarts)
            if method!='put_log':
                self._log.debug('_procedure_call restarting underlying process', self._restarts.value, self._max_restarts)
            self._start(*self._args, **self._kwargs)
            self._restarts.value+=1
        # Combine PID and thread ID
        pid = str(os.getpid()) + ':' + str(threading.current_thread().ident)
        packet = (pid, method, args, kwargs)
        # Start listening on reply socket named as caller pid
        s = self._server_socket(pid, timeout=self._timeout)
        w = self._write_object('input', packet)
        if not w:
            raise RuntimeError('ProcessProxy cannot call remote process: '+method)
        try:
            conn, addr = s.accept()
        except IOError, e:
            if e.errno != errno.EINTR:
                s.close()
                if pid in self._sockets:
                    self._sockets.pop(pid)
                raise
            # Retry the operation
            self._log.debug('_procedure_call retry on EINTR', packet, format_exc())
            conn, addr = s.accept()
        conn.settimeout(self._timeout)
        result = self._read_socket(conn, timeout=self._timeout)
        conn.close()
        if isinstance(result, BaseException):
            raise result
        return result

    def _get_pid(self):
        return int(open(self._pid_path, 'r').read())

    def __getattr__(self, name):
        """Route all method calls to this object as remote procedure calls to the underlying process.
        Returns a callable simulating a standard object method"""
        if (name in self._protect) or (name.startswith('_') and not name.startswith('__')):
            return object.__getattribute__(self, name)
        if not name in dir(self._cls):
            raise AttributeError(
                'ProcessProxy class %r has no method named %s' % (self._cls, name))
        return lambda *a, **ka: self._procedure_call(name, *a, **ka)


class ProcessProxyInstantiator(object):

    def __init__(self, cls, base_path='/tmp/misura', 
                 exit_on_exception=False, 
                 max_restarts=ProcessProxy._max_restarts):
        self.cls = cls
        self.base_path = base_path
        self.instance = None
        self.exit_on_exception = exit_on_exception
        self.max_restarts = max_restarts

    def __call__(self, *args, **kwargs):
        self.instance = ProcessProxy(self.cls,
                                     base_path=self.base_path,
                                     exit_on_exception=self.exit_on_exception,
                                     max_restarts=self.max_restarts)
        self.instance._start(*args, **kwargs)
        return self.instance


class State(object):
    value = 0


class ProcessProxyManager(object):
    _registry = {}
    _base_path = '/tmp/misura'
    _deleted = False
    
    def __init__(self, *args, **kwargs):
        """Compatibility layer between ProcessProxy and multiprocessing managers"""
        self.instantiators = []
        self.__state = State()

    @property
    def _state(self):
        self.__state.value = 0
        if len(self.instantiators):
            if self.instantiators[0].instance:
                self.__state.value = 2 * \
                    self.instantiators[0].instance._is_alive()
        return self.__state

    def start(self):
        pass

    def connect(self):
        pass

    def get_ids(self):
        return ''

    def get_pid(self):
        """Get pid of the first ProcessProxy instance.
        Misura should create only one instance per manager"""
        if not self.instantiators:
            return -1
        print 'ProcessProxyManager._get_pid', len(self.instantiators)
        return self.instantiators[0].instance._get_pid()

    def __del__(self):
        if self._deleted:
            return
        self.shutdown()
        self._deleted = True
        
    def shutdown(self):
        for instantiator in self.instantiators:
            pp = instantiator.instance
            if pp is not None:
                print 'Stopping instantiator.instance', pp, pp._is_alive()
                if pp._is_alive():
                    pp._stop()

    @classmethod
    def register(cls, name, remote_cls):
        """Register `cls` as `name`."""
        assert name not in dir(cls)
        cls._registry[name] = remote_cls

    def __getattr__(self, name):
        """Returns a ProcessProxyInstantiator which can be called to obtain a started ProcessProxy"""
        cls = self._registry.get(name, False)
        if cls is not False:
            instantiator = ProcessProxyInstantiator(
                cls, base_path=self._base_path)
            self.instantiators.append(instantiator)
            return instantiator
        return object.__getattribute__(self, name)
