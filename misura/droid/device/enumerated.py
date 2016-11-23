# -*- coding: utf-8 -*-
#!/usr/bin/python
"""Base class for devices which are a-priori enumerated in the DeviceServer."""

from . import device

#FIXME: this should not need to inherit device.Device
class Enumerated(device.Device):
    enumerated_option = 'simulators'
    """The option name which will be added to the DeviceServer in order to configure the available devices."""
    @classmethod
    def served_by(cls, dsc,  original=False):
        """Additionally to the Device.served_by classmethods, adds the enumerating option to the DeviceServer and a setter method set_<enumerated_option> for editing the available devices."""
        if original is not False:
            cls = original
        else:
            original = cls
        device.Device.served_by(dsc, original)
        # Add enumerator option to the conf
        dsc.conf_def.append({"handle": cls.enumerated_option,
                             "name": 'List of available ' + cls.__name__, "current": '',
                             "type": 'String',
                             # Causes a set_func call when a preset is loaded
                             'attr': ['Hardware']
                             })
        # Create the enumerator setter

        def setfunc(self, lst):
            """Setter method for triggering a modification of Enumerated.available on enumerated_option modification."""
            v = []
            if len(lst) > 0:
                # Legal separators: <,><;><\n>
                sep = ',' if ',' in lst else ';' if ';' in lst else '\n'
                v = lst.split(sep)
            cls.set_available_devices(v)
            return lst
        setattr(dsc, 'set_' + cls.enumerated_option, setfunc)
