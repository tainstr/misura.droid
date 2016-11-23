#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Generic option Control object"""


class Control(object):

    """Generic control object managing get/set and flags on behalf of an Option."""
    in_acquisition_process = False
    """Reading this value must always happen in a separate acquisition process."""

    def __init__(self, parent, handle, read_only=False):
        self.parent = parent
        self.handle = handle
        self.read_only = read_only
        # Create a reference in parent controls
        parent.controls[handle] = self

    def _get(self):
        """Actually read the value in an autostarted Control."""
        return False

    def get(self):
        """Manage the autostart of the Control in a separate process."""
        # Manage autostart
        if self.in_acquisition_process:
            r = self.parent['running']
            # Start acquisition if not running
            if not r:
                self.parent['running'] = 1
            # Return in-memory value
            return self.parent.desc.get(self.handle)
        # Else, actually read the value and return
        return self._get()

    def set(self, val):
        """Set current value and return operation status."""
        return False

    def getFlag(self, flag):
        return False

    def setFlag(self, flag, val):
        return False
