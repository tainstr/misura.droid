#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Generic Device object"""
from misura.canon.csutil import sanitize
from twisted.web import xmlrpc


class InputOutput(xmlrpc.XMLRPC):

    """Interface to a single option representing an input/output terminal"""

    def __init__(self, propDict, dev):
        xmlrpc.XMLRPC.__init__(self, allowNone=True)
        self.separator = '/'
        self.dev = dev
        '''Device owning the I/O option we are interfacing to'''
        self.prop = propDict
        '''Descriptive dictionary for the option'''
        self.kid = propDict['kid']
        '''Key IDentifier'''
        self.handle = propDict['handle']
        '''Option Handle'''
        self.input = True
        '''Is an input option? (Readable)'''
        self.output = True
        '''Is an output option? (Write-able)'''
        
    def get(self):
        return self.dev.get(self.handle)
    
    def soft_get(self):
        return self.dev.soft_get(self.handle)
    
    def set(self, val):
        return self.dev.set(self.handle, val)
    
    def xmlrpc_set(self, *a, **k):
        return self.set(*a, **k)

    def __str__(self):
        s = "InputOutput for %s by %s" % (self.handle, self.dev['name'])
        return s

    @sanitize
    def xmlrpc_get(self):
        """During acquisition, only return the in-memory value, if this is a readable option. 
        Avoids a real reading from hardware."""
        # TODO: check for readLevel!
        if self.dev.root['isRunning'] and self.input:
            return self.dev.desc.get(self.handle)
        return self.get()
