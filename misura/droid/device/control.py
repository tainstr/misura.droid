#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Generic option Control object"""
import numpy as np

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

"""
# Example Calibrator option structure:

    {"handle": 'T',
     "name": 'Sample Temperature',
        "type": 'Float', 'unit': 'celsius',
        "attr": ['History', 'ReadOnly'],
     },
    {"handle": 'rawT',
     "name": 'Raw Temperature',
        "parent": 'T',
        "type": 'Float', 'unit': 'celsius',
        "attr": ['History', 'ReadOnly'],
     },

    {"handle": 'calibrationT',    "name": 'Sample Calibration',
     "current": [[('Measured', 'Float'),
                  ('Theoretical', 'Float'),
                  ],
                 [20,20]
                 ],
        "unit": ['celsius', 'celsius'],
        "type": 'Table',
        "writeLevel": 4,
     },
"""

class Calibrator(Control):
    """Generic calibration control.
    The host Device must define also rawOption (Float) 
    and calibrationOption (2 col Floats table, Measured, Theoretical)""" 
    
    _calibration_func = False
    @property
    def calibration_func(self):
        """Cache a polynomial calibration function"""
        # Return if already defined
        if self._calibration_func:
            return self._calibration_func
        # Disabled
        if self._calibration_func is None:
            return False
        cal = self.parent['calibration'+self.handle][1:]
        
        if self.parent.has_key('calibrationDeg'+self.handle):
            deg = self.parent['calibrationDeg'+self.handle]
        else:
            deg = min(3, len(cal)-2)
        
        # Disable if not enough points
        if len(cal)-2<deg or deg<=0:
            self._calibration_func = None
            return False
        # Create new function
        m,t = [],[]
        map(lambda v: (m.append(v[0]), t.append(v[1])), cal)
        self.parent.log.debug('Reacreating calibration_func', self.handle, deg, m, t)
        factors = np.polyfit(m, t, deg = deg)
        self._calibration_func = np.poly1d(factors)
        return self._calibration_func
    
    _inverse_func = False
    @property
    def inverse_func(self):
        """Cache the inverse of the calibration function"""
        # Return if already defined
        if self._inverse_func:
            return self._inverse_func
        # Disabled
        if self._inverse_func is None:
            return False
        cal = self.parent['calibration'+self.handle][1:]
        
        if self.parent.has_key('calibrationDeg'+self.handle):
            deg = self.parent['calibrationDeg'+self.handle]
        else:
            deg = min(3, len(cal)-2)
        
        # Disable if not enough points
        if len(cal)-2<deg or deg<=0:
            self._inverse_func = None
            return False
        # Create new function
        m,t = [],[]
        map(lambda v: (m.append(v[0]), t.append(v[1])), cal)
        self.parent.log.debug('Reacreating inverse_func', self.handle, deg, m, t)
        factors = np.polyfit(t, m, deg = deg)
        self._inverse_func = np.poly1d(factors)
        return self._inverse_func
    
    def calibrated(self, nval):
        """Return theoretical value from measured value `nval`"""
        if not self.calibration_func:
            return nval
        # Store in rawT dataset
        self.parent['raw'+self.handle] = nval
        return self._calibration_func(nval)
    
    def inverse(self, val): 
        """Return the required measured value in order 
        to obtain a calibrated value `val`"""
        if not self.inverse_func:
            return val
        return self._inverse_func(val)       


        
    