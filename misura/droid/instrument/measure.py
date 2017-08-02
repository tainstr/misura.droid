# -*- coding: utf-8 -*-
"""
General Measure class
"""
from copy import deepcopy

from misura.canon.csutil import utime, validate_filename
from misura.droid import device


conf = [
    {"handle": 'operator', "name": "Operator",
     "current": 'unknown', "type": 'String'},
    {"handle": 'flavour', "name": 'Type',
        "current": 'Standard', "type": 'Chooser',
        "options": ['Standard', 'Calibration'], "writeLevel":2, "readLevel": 4,
     },
    {"handle": 'date', "name": 'Started at (h:m:s, dd/mm/yyyy)',
        "current": 0,
        "attr": ['ReadOnly'], "type": 'Date',
     },
    {"handle": 'id', "name": 'Test ID name',
        "current": '', "type": 'ReadOnly',
     },
    {"handle": 'uid', "name": 'Test UID',
        "current": '', "type": 'ReadOnly', "readLevel": 2, "parent": 'id',
        "attr": ['Runtime'],
     },
    {"handle": 'measureFile', "name": 'Measure File Path',
        "current": '', "readLevel": 2, "parent": 'id',
        "attr": ['Hidden'], "type": 'ReadOnly',
     },
    {"handle": 'nSamples',  "name": 'Number of samples',
        "current": 1,  "writeLevel": 2,
        "type": 'Chooser', "options": [1, 2, 3, 4, 5, 6, 7, 8]
     },
    {"handle": 'kilnBeforeStart',
     "name": 'Kiln position before acquisition', "type": 'Chooser',
        "current": 1,
        "options": ['Closed', 'Opened'], "writeLevel":2,
        "values":[1, 0]},
    {"handle": 'kilnAfterEnd',
        "name": 'Kiln position after acquisition', "type": 'Chooser',
        "options": ['Closed', 'Opened', 'Unchanged'], "writeLevel":2,
        "current":-1,
        "values":[1, 0, -1]},
    {"handle": 'elapsed', "name": 'Elapsed time', "attr": ['ReadOnly'],
        "current": 0, "type": 'Float', "unit": 'second',
     },
    # {"handle": 'etaTC', "name": 'Estimated time to finish thermal cycle',
    #   "current": 0, "type": 'Float',  "unit": 'second',
    #   },
    # {"handle": 'etaAQ',   "name": 'Estimated time to finish acquisition',
    #   "current": 0, "type": 'Float', "unit": 'second',
    #   },


    # end (End of test)
    {"handle": 'end', "name": 'End of the test',
        "type": 'Meta',
     },
    {"handle": 'scrEnd', "name": 'End of test',
        "current": 'mi.Point(idx=-1)', "parent": 'end',
        "flags": {'period': -1}, "type": 'Script', "readLevel": 3, "writeLevel": 3,
     },

    {"handle": 'endStatus', "name": "End status", "attr": ['ReadOnly'],
        "current": '', "writeLevel": 5, "type": 'TextArea'},

    #------

    # maxT (Maximum Temperature)
    {"handle": 'maxT', "name": 'Maximum Temperature', "type": 'Meta'},
    {"handle": 'scrMaxT', "name": 'Maximum Temperature',
     "current": """
i,t,T=mi.Max('T')
mi.t(t)
mi.T(T)
""", "parent": 'maxT',
        "flags": {'period': -1}, "type": 'Script', "readLevel": 3, "writeLevel": 3,
     },

    # maxHeatingRate (Maximum Heating Rate)
    {"handle": 'maxHeatingRate',
        "name": 'Maximum Heating Rate', "type": 'Meta'},
    {"handle": 'scrMaxHeatingRate', "name": 'Maximum Heating Rate',
        "current": """
T1=kiln.TimeDerivative('T')
if len(T1)<10: mi.Exit()
rate=max(T1)
w=mi.Where(T1==rate)
if w<0: mi.Exit()
mi.Point(idx=w+1)
mi.Value(rate*60)

""", "parent": 'maxHeatingRate', "readLevel": 3, "writeLevel": 3,
        "flags": {'period': -1}, "type": 'Script',
     },

    # coolingDuration (Total cooling duration)
    {"handle": 'coolingDuration',
        "name": 'Total cooling duration', "type": 'Meta'},
    {"handle": 'scrCoolingDuration', "name": 'Total cooling duration',
     "current": """
ret = mi.GetCoolingTimeAndIndex()
if not ret:
    mi.Exit()
cooling_time =ret[0]
t, T = mi.AtTime('T', cooling_time)
end_t, end_T = mi.AtIndex('T', -1)
mi.T(T - end_T)
mi.t(end_t - t)
""", "parent": 'coolingDuration', "readLevel": 3, "writeLevel": 3,
        "flags": {'period': -1}, "type": 'Script',
     },

    # maxCoolingRate (Maximum Cooling Rate)
    {"handle": 'maxCoolingRate',
        "name": 'Maximum Cooling Rate', "type": 'Meta'},
    {"handle": 'scrMaxCoolingRate', "name": 'Maximum Cooling Rate',
     "current": """
ret = mi.GetCoolingTimeAndIndex()
if not ret:
    mi.Exit()
cooling_time, cooling_index = ret
T1=mi.TimeDerivative('/kiln/T', cooling_time)
if len(T1)<10: mi.Exit()
rate=min(T1)
w = mi.Where(T1 == rate) - 1
if w<0: mi.Exit()
mi.Value(rate/60)
mi.Point(idx=w)
""", "parent": 'maxCoolingRate', "readLevel": 3, "writeLevel": 3,
        "flags": {'period': -1}, "type": 'Script',
     },

    # TERMINATION Conditions
    # errors (Stop on consecutive image analysis errors)
    #
    {"handle": 'errors', "name": 'Stop on consecutive image analysis errors',
        "max": 500, "current": 100, "step": 1, "min": 1,
        "flags": {'enabled': True}, "type": 'Integer', "readLevel": 3,
     },
    # duration (Maximum test duration (min))
    #
    {"handle": 'duration', "name": 'Maximum test duration', "max": 60*24*30,
        "current": -1, "type": 'Float', 'unit': 'minute', 'priority': 0
     },
    # cooling (Stop after cooling)
    #
    {"handle": 'onKilnStopped', "name": 'Stop after thermal cycle', 'priority': 0,
     "current": """if kiln.Opt('analysis'): mi.Exit()
belowTemp=script.Opt('coolingBelowTemp') # degrees
afterMinutes=script.Opt('coolingAfterTime')
stop=False
if belowTemp == 0 and afterMinutes <= 0:
    stop = True
if kiln.Opt('T')<belowTemp and belowTemp!=0:
    stop=True
if measure.Opt('elapsed')-kiln.Opt('coolingStart')>afterMinutes*60 and afterMinutes>0:
    stop=True

if stop:
    mi.Log('Stop acquisition after cooling')
    ins.stop_acquisition()""",
        "flags": {'enabled': True, 'period': 0}, "type": 'Script',
     },
    # coolingBelowTemp (Wait T smaller than)
    {"handle": 'coolingBelowTemp', "name": 'Wait T smaller than',
        "parent": 'onKilnStopped', "unit": "celsius",
        "current": 0, "type": 'Float',
     },
    # coolingAfterTime (Wait minutes)
    {"handle": 'coolingAfterTime', "name": 'Wait minutes',
        "parent": 'onKilnStopped', "unit": "minute",
        "current": 0, "type": 'Float',
     },

    {"handle": 'thermalCycle',
     "name": 'Thermal cycle',
        "current": 'None',
        "type": 'RoleIO',
        "options": ['/kiln/', 'default', 'thermalCycle'],
     },
    {"handle": 'curve', "name": 'Heating curve',
        "options": ['/kiln/', 'default', 'thermalCycle'], "type": 'RoleIO', 
        'attr':['Hidden']},
]


class Measure(device.Device):

    """Public interface to a measurement recipe"""
    conf_def = deepcopy(device.Device.conf_def + conf)

    def set_name(self, tn):
        """Option `name` must be a valid file name."""
        tn = validate_filename(tn)
        return tn

    def get_elapsed(self):
        """Returns elapsed time since the beginning of a test"""
        instrobj = self.parent()
        zt = instrobj['zerotime']
        # Zero, if zerotime is not initialized
        if zt <= 0.:
            return 0.
        r = float(utime() - zt)
        return r

    def get_coolingAfterTime(self):
        return self.get_if_on_kiln_stopped_enabled('coolingAfterTime')

    def get_coolingBelowTemp(self):
        return self.get_if_on_kiln_stopped_enabled('coolingBelowTemp')

    def get_if_on_kiln_stopped_enabled(self, option_name):
        if not self.gete('onKilnStopped')['flags']['enabled']:
            return 0.

        return self.desc.get(option_name)

    def set_preset(self, preset, *a, **k):
        """Force loading of the thermal cycle"""
        ret = device.Device.set_preset(self, preset, *a, **k)
        if preset == 'factory_default':
            return ret
        cycle = self.get_from_preset('thermalCycle', preset)
        if cycle:
            self['thermalCycle'] = cycle
        curve = self.get_from_preset('curve', preset)
        if curve:
            self['curve'] = curve
        return ret
