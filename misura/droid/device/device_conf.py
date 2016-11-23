# -*- coding: utf-8 -*-

conf = [

    # preset (Comment)
    {"handle": 'preset', "name": 'Configuration preset',
        "current": 'factory_default', "type": 'Preset', "readLevel": 2, "writeLevel": 2, "priority": -1},

    # name (Name)
    {"handle": 'name', "name": 'Name',
        "current": 'device', "type": 'String', "writeLevel": 2, "priority": -1},

    # comment (Comment)
    {"handle": 'comment', "name": 'Comment', "type": 'String', "priority": 0},

    # initializing (Is Initializing)
    {"handle": 'initializing',  "name": 'Is Initializing',
        "current": False, "type": 'Boolean', "attr": ['Hidden']},

    # isConnected (Is Connected)
    {"handle": 'isConnected',   "name": 'Is Connected',
        "current": True, "type": 'Boolean', "attr": ['Hidden']},

    # idx (Index in parent device list)
    {"handle": 'idx',   "name": 'Index in parent device list',
        "current": -1, "type": 'Integer', "attr": ['Hidden']},

    # locked (Lock depth)
    {"handle": 'locked',    "name": 'Lock depth',
        "current": False, "type": 'Boolean', "attr": ['Hidden']},

    # running (Running acquisition)
    {"handle": 'running',   "name": 'Running acquisition', "attr": ['Runtime'],
        "current": 0, "type": 'Chooser', "values": [0, 1, 2], "options":['Stopped', 'Running', 'Stopping']},
    # idx (Index in parent device list)
    {"handle": 'pid',   "name": 'Subprocess ident',
        "current": 0, "type": 'Integer', "attr": ['Hidden', 'Runtime']},

    # anerr(Consecutive Analysis Errors)
    {"handle": 'anerr', "name": 'Consecutive Errors',
        "current": 0, "min": 0, "type": 'Integer', "attr": ['History', 'ReadOnly', 'Runtime'], "readLevel":1, "priority": 0},
    {"handle": 'maxErr',
        "name": 'Maximum number of errors before aborting acquisition.',
        "current": 50,
        "type": 'Integer', "readLevel": 4, "writeLevel": 4, "priority": 0},
    #------

    # err (Measurement Error index)
    #
    {"handle": 'err', "name": 'Measurement error', "min": 0,
        "type": 'Float', "attr": ['ReadOnly', 'History', 'Runtime'], "readLevel": 2},

    # status
    {"handle": 'status', "name": 'Status', "current": True,
        "type": 'Boolean', "readLevel": 3, "attr":['ReadOnly']},

    # zerotime (Acquisition starting time)
    #
    {"handle": 'zerotime',  "name": 'Acquisition starting time',
        "type": 'Float', "attr": ['Hidden']},

    # analysis (Is in use by analysis process)
    {"handle": 'analysis',  "name": 'Is in use by analysis process',
        "current": False, "type": 'Boolean',
     "attr": ['Hidden', 'Runtime', 'History'],
     "readLevel": 2, "writeLevel": 3},

    {"handle": 'monitor',   "name": 'Acquisition loop inputs',
     "current": [], "type": 'List', "attr": ['Hidden', 'Runtime']},

    {"handle": 'maxfreq',   "name": 'Max acquisition frequency', "current": 20,
        "min": 0.01, "max": 1000, "type": 'Float', "unit": 'hertz', "readLevel": 4},


]
