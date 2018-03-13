# -*- coding: utf-8 -*-
"""/opt/misura/misura/conf/Server.Device"""
import os
isWindows = os.name=='nt'

plugins="""
misura.droid.users.Users
misura.droid.storage.Storage
misura.droid.support.Support
#GROUP
misura.beholder.Beholder
misura.morla.Morla
misura.smaug.Smaug
#GROUP
misura.kiln.Kiln
misura.microscope.Hsm
misura.dilatometer.VerticalDilatometer
misura.dilatometer.HorizontalDilatometer
misura.flex.Flex
"""

if isWindows:
    plugins="""
misura.droid.users.Users
misura.droid.storage.Storage
misura.droid.support.Support
#GROUP
misura.morla.Morla
misura.smaug.Smaug
#GROUP
misura.kiln.Kiln
"""


conf = [
    # Main (Status)
    {"handle": 'Main', "name": 'Status',
     "current": '', "type": 'Section',
     },
    {"handle": 'lastClientAccessTime', "name": 'Last access time of client',
        "current": 0, "type": 'Hidden', "attr": ['Runtime'],
    },
    {"handle": 'autoShutdownInterval', "name": 'Shutdown after inactivity',
        "current": 3600, "type": 'Chooser', 
        "options":['Never', '5 min', '1 hour', '4 hours', '12 hours', '1 day', '3 days'], 
        "values": [ 0,       300,    3600,        4*3600,    12*3600, 24*3600, 3*24*3600],
    },

    # scanning (Scanning for devices)
    {"handle": 'scanning', "name": 'Scanning for devices',
        "current": False, "type": 'Boolean', "attr": ['ReadOnly', 'Runtime']	},
    # isRunning (Running test)
    {"handle": 'isRunning', "name": 'Running test',
        "current": False, "type": 'Boolean', "attr": ['ReadOnly', 'Runtime']},
    # runningInstrument (Running Instrument)
    {"handle": 'runningInstrument', "name": 'Running Instrument',  "current": '',
        "attr": ['ReadOnly', 'Runtime'], "type": 'Chooser',
     },
    {"handle": 'lastInstrument', "name": 'Last initialized instrument', "current": '',
        "attr": ['ReadOnly', 'Runtime'], "type": 'Chooser',
     },
    {"handle": 'restartOnNextCheck', "name": 'Restart server at next periodic check', "current": False,
        "attr": ['ReadOnly', 'Runtime'], "type": 'Boolean',
     },
    {"handle": 'restartOnFinishedTest', "name": 'Restart server at each finished test',
        "current": False, "type": 'Boolean',
     },
    {"handle": 'delayStart', "name": 'Enable delayed start',  "writeLevel": 1,
        "type": 'Boolean', "current": False, "attr": ['Runtime']},
    {"handle": 'delay', "name": 'Delayed start date',
        "writeLevel": 1, "type": 'Time', "attr": ['Runtime']},
    {"handle": 'timeDelta', "name": 'Hardware clock time delta (UTC)','unit': 'second',
        "attr": ['Runtime'], "type": 'Float'},
    # error (Errors)
    {"handle": 'error', "name": 'Errors',
     "attr": ['ReadOnly'], "type": 'String'},
    # zeroTime (Acquisition start time)
    {"handle": 'zerotime', "name": 'Acquisition start time',
        "attr": ['ReadOnly'], "type": 'Float'},
    # TODO: endtime
    # {"handle": 'endtime',"name": 'Acquisition end time',
    # 	"attr": ['ReadOnly'], "readLevel": 5,"type": 'Float'},
    # initTest (Initializing New Test)
    {"handle": 'initTest',
        "name": 'Initializing New Test',
        "current": 0,
        "type": 'Progress',
        "attr": ['Runtime'],
     },
    {"handle": 'closingTest',
        "name": 'Closing the current test',
        "current": 0,
        "type": 'Progress',
        "attr": ['Runtime'],
     },
    {"handle": 'progress',
        "attr": ['ReadOnly', 'Runtime'],
        "name": 'Operation in progress',
        "type": 'List',
     },
    {"handle": 'endStatus', "name": 'End status',
        "current": '', "writeLevel": 5, "type": 'TextArea'},
    # instruments (List of available instruments)
    {"handle": 'instruments',
        "attr": ['ReadOnly', 'Runtime'],
        "name": 'List of available instruments',
        "current": [], "attr":['Hidden'], "type": 'List',
     },
    # deviceservers (List of available device servers)
    {"handle": 'deviceservers',
        "attr": ['ReadOnly', 'Hidden', 'Runtime'],
        "name": 'List of available device servers',
        "current": [], "type": 'List',
     },

    # eq (Equipment Identification)
    {"handle": 'eq', "name": 'Equipment Identification', "type": 'Section'},
    # eq_sn (Serial Number)
    {"handle": 'eq_sn', "name": 'Serial Number',
        "current": '12345', "writeLevel": 5, "type": 'String'},
    {"handle": 'eq_mac', "name": 'External MAC address',
        "current": '', "writeLevel": 6, "type": 'String'},
    # Plugin list
    {"handle": 'eq_plugin', "name": 'Load Plugins', 'writeLevel': 5,
     "current": plugins, "type": 'TextArea'},
    # eq_kiln (Enable KILN)
    {"handle": 'eq_kiln', "name": 'Enable KILN', 'writeLevel': 5,
        "current": True, "type": 'Hidden',
     },
    # eq_hsm (Enable HSM Heating Microscope)
    {"handle": 'eq_hsm', "name": 'Enable Heating Microscope',
     "current": 1, "type": 'Boolean', 'writeLevel': 5,},
    # eq_post (Enable Post-Analysis)
    #{"handle": 'eq_post', "name": 'Enable Post-Analysis',
    #	"current": 1, "type": 'Boolean'},
    {"handle": 'eq_vertical', "name": 'Enable Vertical Optical Dilatometer',
     "current": 1, "type": 'Boolean', 'writeLevel': 5,},
    {"handle": 'eq_horizontal', "name": 'Enable Horizontal Optical Dilatometer',
     "current": True, "type": 'Boolean', 'writeLevel': 5,},
    {"handle": 'eq_flex', "name": 'Enable Optical Fleximeter',
        "current": 1, "type": 'Boolean', 'writeLevel': 5,},
    {"handle": 'eq_dta', "name": 'DTA',
        "current": 1, "type": 'Boolean', 'writeLevel': 5,},
    {"handle": 'eq_motion', "name": 'Has motion control',
     "current": True,  "type": 'Boolean', 'writeLevel': 5,},
    {"handle": 'eq_serialPorts', "name": 'Max COM serial ports to be scanned',
     "current": 2, "max": 10, "step": 1, "min": 0, "type": 'Integer', 'writeLevel': 5,},
    
    # cs (Customer Information)
    {"handle": 'cs', "name": 'Customer Information', "type": 'Section'},
    # cs_org (Organization)
    {"handle": 'cs_org', "name": 'Organization',
     "current": 'TA Instruments / Waters LLC', "type": 'String'},
    # cs_dept (Department)
    {"handle": 'cs_dept', "name": 'Department',
        "current": 'Research and Development', "type": 'String'},
    # cs_lab (Laboratory)
    {"handle": 'cs_lab', "name": 'Laboratory',
        "current": 'Computational Development', "type": 'String'},
    # cs_addr (Complete Address)
    {"handle": 'cs_addr', "name": 'Complete Address',
        "current": 'viale Virgilio 58/L, 41100 Modena (MO), Italy', "type": 'String'},
    # cs_cname (Contact Name)
    {"handle": 'cs_cname', "name": 'Contact Name',
        "current": 'Daniele Paganelli', "type": 'String'},
    # cs_qual (Contact Qualification)
    {"handle": 'cs_qual', "name": 'Contact Qualification',
        "current": 'Researcher', "type": 'String'},
    # email (eMail List)
    {"handle": 'email',	"name": 'eMail List',
        "current": 'd.paganelli@expertsystemsolutions.it', "type": 'String'},
    # cs_phone (Phone Number)
    {"handle": 'cs_phone', "name": 'Phone Number',
        "current": '+39 059 8860024', "type": 'String'},


]
