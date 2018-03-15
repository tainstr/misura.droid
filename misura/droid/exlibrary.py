#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Utilities for rich Ctypes wrapping of C/C++ libraries"""
import exceptions
from misura.canon import logger

class ApiError(exceptions.BaseException):
    errors = {4210: 'Read-Only operation',
              4211: 'Write-Only operation',
              4212: 'Invalid handle',
              4213: 'Parameter not found',
              4214: 'Accessor recursion exceeded',
              4215: 'Parameter modifier not found',
              4216: 'Library load failed',
              4217: 'Library not initialized'}
    """Error code : Description"""
    _num = 0

    def __init__(self, num=None, *a):
        if num is None:
            num = self._num
        self.num = num
        self.args = a
        self.name = self.errors.get(num, 'Unknown Error')
        self.msg = '{} ({}) '.format(self.name, num)
        self.msg += '\nCalling:  ' + ', '.join([str(b) for b in a])
        exceptions.BaseException.__init__(self, self.msg)

    @classmethod
    def iserr(cls, n):
        if n < 0 or cls.errors.has_key(n):
            return True
        return False


class ReadOnlyError(ApiError):
    _num = 4210


class WriteOnlyError(ApiError):
    _num = 4211


class InvalidHandle(ApiError):
    _num = 4212


class NoParameterError(ApiError):
    _num = 4213


class AccessorRecursionError(ApiError):
    _num = 4214


class NoModifierError(ApiError):
    _num = 4215


class LibraryLoadError(ApiError):
    _num = 4216


class LibraryNotInitializedError(ApiError):
    _num = 4217


class FunctionCall(object):

    """Error handling on top of ctypes function calls."""
    ignore = []
    """Error numbers alwasy ignored"""
    prefix = ''
    """Will be added to any library function call."""
    exceptionClass = ApiError

    def __init__(self, f, name='FunctionCall', log=False):
        self.ignore = self.__class__.ignore[:]
        self.f = f
        self.name = self.prefix + name
        if not log:
            log = logger.BaseLogger()
        self.log = log

    def __call__(self, *a):
        r = self.f(*a)
        if self.exceptionClass.iserr(r) and not (r in self.ignore):
            raise self.exceptionClass(r, self.name, *a)
        return r


class ExcRaiser(object):

    """Callable object raising an ApiError exception whenever called."""

    def __init__(self, num):
        self.num = num

    def __call__(self, *a):
        ApiError(self.num)


class ParamAccessor(object):

    """Easy access to device parameters."""
    # TODO: migrate these to set()
    _modifiers = ['min', 'max']
    _reserved = ['get', 'set', 'step']
    step = 1

    def __init__(self, context, name, modifier='', log=False):
        self._name = name
        self._ctx = context
        self._modifier = modifier
        if not log:
            log = logger.BaseLogger()
        self._log = log

    @property
    def _handle(self):
        """Shortcut for device handle."""
        return self._ctx.handle

    def get(self):
        """Read the current parameter value"""
        # To be reimplemented
        raise ApiError()

    def set(self, nval):
        """Change the current parameter value to nval"""
        # To be reimplemented
        raise ApiError()

    def __call__(self, nval=None):
        """If no argument is supplied, the same as get(). 
        If `nval` is supplied, the same as set(). """
        if nval is not None:
            return self.set(nval)
        return self.get()

    def __getattr__(self, name):
        """Allows to retrieve parameter _modifiers (max,min,inc, ...) 
        and current value as attributes."""
        # Filter accessor attributes
        if name.startswith('_'):
            return object.__getattribute__(self, name)
        elif name in self._reserved:
            return object.__getattribute__(self, name)
        elif name == 'value':
            return self.get()
        # No sub-modifier recursion
        elif self._name in self._modifiers:
            raise AccessorRecursionError()
        elif name in self._modifiers:
            # Return a new instance with the _modifier
            #           print 'Retrieving with _modifier', self._name, name
            r = None
            try:
                r = self.__class__(self._ctx, self._name, name).get()
            # Return None if the _modifier is not supported
            except ApiError as e:
                if e.num != -1:
                    raise e
            return r
        return object.__getattribute__(self, name)

    def __setattr__(self, name, nval):
        """Allows to set current value by assigning ´current´  attribute.
        eg: obj.current=nval"""
        # Filter accessor attributes
        if name.startswith('_'):
            return object.__setattr__(self, name, nval)
        elif name in self._reserved:
            return object.__setattr__(self, name, nval)
        elif name == 'value':
            return self.set(nval)
        # No sub-modifier recursion
        elif self._name in self._modifiers:
            raise AccessorRecursionError()
        # Intercept set requests on _modifiers
        elif name in self._modifiers:
            return self.__class__(self._ctx, self._name, name).set(nval)
        return object.__setattr__(self, name, nval)


class Api(object):

    """Library and device interface."""
    _handle = None
    _idx = -1
    _lib = None
    _init = True
    """Initialized?"""
    _functionCallClass = FunctionCall
    _paramAccessorClass = ParamAccessor
    
    def __init__(self, log=False):
        if not log:
            log = logger.BaseLogger()
        self._log = log
        self._current = {}

    def __del__(self):
        self.close()

    def close(self):
        # To be reimplemented
        return True

    @property
    def handle(self):
        """Raise an exception if no handle was defined by an open() call."""
        if self._handle is None:
            try:
                self.open()
            except:
                raise InvalidHandle()
        return self._handle

    def param(self, name, modifier=''):
        """Build a ParamAccessor for name and modifier."""
        # To be reimplemented
        return self._paramAccessorClass(self, name, modifier, log=self.log)

    def __getattr__(self, name):
        """Allow to access to exception-aware functions (FunctionCall)
        and smart parameters (ParamAccessor).
        Examples:
        > api.Init will call that function with exception handling
        > api.brightness will return a parameter accessor for that parameter name."""
        # Filter private attributes
        if name.startswith('_'):
            return object.__getattribute__(self, name)
        # intercept library function calls: whose names start with a capital
        # letter
        f = getattr(self._lib, self._functionCallClass.prefix + name, False)
        if f:
            if not self._init:
                raise LibraryNotInitializedError()
            return self._functionCallClass(f, name, log=self._log)
        # intercept parameter access requests
        try:
            if not self._init:
                raise LibraryNotInitializedError()
            p = self.param(name)

            return p
        except NoParameterError:
            pass
        # Nothing found: fallback to Api python class
        return object.__getattribute__(self, name)

    def __setattr__(self, name, nval):
        """Allow to directly set a parameter by assigning it as an object attribute.
        Example:
        > api.width=100"""
        if name.startswith('_'):
            return object.__setattr__(self, name, nval)
        try:
            p = self.param(name)
        except NoParameterError:
            return object.__setattr__(self, name, nval)
        if not self._init:
            raise LibraryNotInitializedError()
        return p.set(nval)
