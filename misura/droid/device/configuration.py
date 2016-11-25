# -*- coding: utf-8 -*-
"""Data management and formats"""
import types
from cPickle import dumps
import inspect
import functools
from twisted.web import xmlrpc


from misura.canon import logger
from misura.canon import csutil
from misura.canon.csutil import sanitize,  xmlrpcSanitize, func_args
from ..utils import listDirExt
from .. import parameters as params

####
# EXCEPTIONS


class ReadNotAuthorized(xmlrpc.Fault):

    def __init__(self, msg='ReadNotAuthorized'):
        xmlrpc.Fault.__init__(self, 3880, msg)


class WriteNotAuthorized(xmlrpc.Fault):

    def __init__(self, msg='WriteNotAuthorized'):
        xmlrpc.Fault.__init__(self, 3881, msg)


class NoProperty(xmlrpc.Fault):

    def __init__(self, msg='NoProperty'):
        xmlrpc.Fault.__init__(self, 3890, msg)


class FunctionRoutingError(xmlrpc.Fault):

    def __init__(self, msg='FunctionRoutingError'):
        xmlrpc.Fault.__init__(self, 3891, msg)

####
# UTILITIES


def fill_implicit_args(function, args, kwopt):
    """Fill connection-related optional function arguments `kwopt`,
    if target function `function` requires them as parameters and if they are not already listed as `args`.
    Returns False on validation failure.
    Returns function, args, and filled kwargs dict on success.
    kwopt keywords: readLevel,writeLevel,userName,sessionID,request."""
    # authLevel,userName parameters are set only if the calling function
    # accepts them
    pop = 0
    kwargs = {}  # filled arguments
    vn = func_args(function)
    # Internal call, nothing to do here
    if len(kwopt) == 0 or len(vn) == 0:
        return function, args, kwargs
    # Asks for the granted readLevel
    if kwopt.has_key('readLevel') and ('readLevel' in vn or 'krl' in vn or 'krwl' in vn):
        pop += 1
        kwargs['readLevel'] = kwopt['readLevel']
    # Asks for the granted writeLevel
    if kwopt.has_key('writeLevel') and ('writeLevel' in vn or 'kwl' in vn or 'krwl' in vn):
        pop += 1
        kwargs['writeLevel'] = kwopt['writeLevel']
    # Asks for the logged username
    if kwopt.has_key('userName') and ('userName' in vn or 'kun' in vn):
        pop += 1
        kwargs['userName'] = kwopt['userName']
    # Asks for the session
    if kwopt.has_key('sessionID') and ('sessionID' in vn or 'ksid' in vn):
        pop += 1
        kwargs['sessionID'] = kwopt['sessionID']
    # Asks for the full request
    if kwopt.has_key('request') and ('request' in vn):
        kwargs['request'] = kwopt['request']
    # Asks all optional arguments as dict
    if 'kwopt' in vn:
        kwargs['kwopt'] = kwopt
    # Check for maximum number of arguments accepted by function
    maxlen = len(vn) - pop - 1
    if len(args) > maxlen and pop > 0 and maxlen > 0:
        print 'fill_implicit_args', maxlen, args, pop
        return False
    return function, args, kwargs


class SubDict(dict):

    """Subordinated dictionary for Dict-type properties. It allows syntax like:
    parent['pkey']['subkey']=foo, where parent is a ConfigurationInterface object."""

    def __init__(self, ini_dict, parent, parent_key):
        dict.__init__(self, ini_dict)
        self.parent = parent
        self.parent_key = parent_key

    def __setitem__(self, key, val):
        """This will cause each change in the subdict to reflect on the parent dict"""
        dict.__setitem__(self, key, val)
        self.parent.set(self.parent_key, self.copy())


class ConfigurationInterface(xmlrpc.XMLRPC, object):

    """Public interface to Conf objects (XMLRPC and get/set mechanics)"""
    conf_class = 'Conf'
    """Conf class towards which this class acts as a ConfigurationInterface."""
    main_confdir = params.confdir
    """Base server configuration directory"""
    conf_def = [{"handle": 'mro', "name": 'Class hierarchy', "type": 'List', "attr": ['ReadOnly','Hidden']},
                {"handle": 'log', "name": 'Log',
                    "type": 'Log', "attr": ['History']},
                ]
    """Default configuration list"""

    server = None
    allow_none = True
    _Method__name = 'undefined'

    def __init__(self, desc):
        """Create an interface for configuration object `desc`. """

        xmlrpc.XMLRPC.__init__(self, allowNone=True)
        object.__init__(self)
        self.separator = '/'
        self.devices = []
        self.controls = {}
        self.desc = desc
        self.log = logger.SubLogger(self)

        ######
        # data.Conf method routing (self.desc)
        self.keys = self.desc.keys
        self.get_preset = self.desc.get_preset
        self.sete = self.desc.sete
        self.getattr = self.desc.getattr
        self.setattr = self.desc.setattr
        self.getkid = self.desc.getkid
        self.gettype = self.desc.gettype
        self.has_key = self.desc.has_key
        self.listPresets = self.desc.listPresets
        self.updateCurrent = self.desc.updateCurrent
        self.update = self.desc.update
        self.fp = self.desc.fp
        self.iolist = self.desc.iolist
        self.get_from_preset = self.desc.get_from_preset
        self.compare_presets = self.desc.compare_presets

        ######
        # Direct publication
        # TODO: SECURITY CHECKS! readLevel,writeLevel, etc...
        self.xmlrpc_has_key = self.desc.has_key
        self.xmlrpc_keys = self.desc.keys
        self.xmlrpc_getattr = self.getattr
        self.xmlrpc_setattr = self.setattr
        self.xmlrpc_getkid = sanitize(self.desc.getkid)
        self.xmlrpc_applyDesc = self.applyDesc
        self.xmlrpc_listPresets = self.desc.listPresets
        self.save = self.desc.save
        self.xmlrpc_save = self.desc.save
        self.remove = self.desc.remove
        self.xmlrpc_remove = self.desc.remove  # config. file
        self.rename = self.desc.rename
        self.xmlrpc_rename = self.desc.rename
        self.delete = self.desc.delete
        self.xmlrpc_delete = self.desc.delete  # key
        self.xmlrpc_h_get = sanitize(self.desc.h_get)
        self.xmlrpc_h_get_time = sanitize(self.desc.h_get_time)
        self.xmlrpc_getAttributes = sanitize(self.desc.getAttributes)
        self.xmlrpc_iolist = self.iolist
        self.xmlrpc_get_from_preset = self.get_from_preset
        self.xmlrpc_compare_presets = self.compare_presets
        # History methods
        self.h_get = self.desc.h_get
        self.h_get_history = self.desc.h_get_history
        self.h_get_time = self.desc.h_get_time
        self.h_clear = self.desc.h_clear
        self.h_time_at = self.desc.h_time_at
        self.xmlrpc_h_time_at = self.h_time_at

        ######
        # Mediated publication
        self.xmlrpc___getitem__ = sanitize(self.xmlrpc_get)
        self.xmlrpc___setitem__ = sanitize(self.xmlrpc_set)
        self.xmlrpc_setFlags = sanitize(self.setFlags)
        self.xmlrpc_getFlags = sanitize(self.getFlags)
        self.xmlrpc___contains__ = self.desc.has_key
        self.xmlrpc___hash__ = self.__hash__
        self.xmlrpc___eq__ = self.__eq__
        self.xmlrpc___repr__ = self.desc.__repr__
        self.xmlrpc___str__ = self.__str__

    # Must explicitly define these functions.
    # Cannot assign them to self during __init__
    def __getitem__(self, *args, **kwargs):
        return self.get(*args, **kwargs)

    def __setitem__(self, *args, **kwargs):
        return self.set(*args, **kwargs)

    def __contains__(self, *args, **kwargs):
        return self.desc.has_key(*args, **kwargs)

    def getcontrols(self):
        """Returns currently defined controls"""
        return self.controls.keys()
    xmlrpc_getcontrols = getcontrols

    def close(self):
        if self.desc is False:
            return False
        print 'ConfigurationInterface.close', type(self), id(self)
        self.desc.close()
        self.desc = False
        return True

    @property
    def class_name(self):
        return self.__class__.__name__

    def classname(self):
        return self.class_name
    xmlrpc_classname = classname

    def mro(self):
        mro = inspect.getmro(self.__class__)
        r = []
        for cl in mro:
            r.append(cl.__name__)
        return r[:-3]

    xmlrpc_mro = mro

    def describe(self, *a, **kw):
        self['mro'] = self.mro()
        return self.desc.describe(*a, **kw)

    def get_mro(self):
        return self.mro()

    def iteritems(self): pass

    def iterkeys(self): pass

    def __iter__(self): pass

    def __hash__(self):
        """L'hash viene calcolato sulla base dell'oggetto self.log onde evitare ricorsioni infinite."""
        return hash(self.log)

    def __eq__(self, other):
        if not getattr(other, '_Method__name', False):
            return False
        if self._Method__name != other._Method__name:
            return False
        return True

    def __str__(self):
        if self.desc is False:
            return 'Closed {}: {}, {}, {}'.format(self.__class__.__name__, repr(self), type(self), id(self))
        r = self.__class__.__name__ + ' for ' + self.desc.__str__()
        r += '\nconf_dir: %s \nconf_obj: %s' % (self.conf_dir, self.conf_obj)
        return r

    def xmlrpc_describe(self, readLevel=0):
        """Sanitize description dictionary and filter depending on user's readLevel."""
        r = self.desc.describe()
        for key, val in r.items():
            if val['readLevel'] > readLevel:
                del r[key]
                continue
            val['current'] = xmlrpcSanitize(
                val['current'], attr=val['attr'], otype=val['type'])
#           if 'Binary' in val['attr'] or val['type']=='Profile':
#               val['current']=xmlrpc.Binary(dumps(val['current']))
            r[key] = val
        l = [v.keys() for v in r.values()]
        print set([type(item) for sublist in l for item in sublist])
        return r

    _rmodel = False

    def rmodel(self):
        """Dictionary model recursively listing all subdevices' paths.
        {'self':name,
         'sub1':{'self':name,
                 'sub1sub1':{'self':name,...},
         'sub2':{'self':name}
          ...}
        """
        if self._rmodel is not False:
            return self._rmodel
        out = {'self': self['name']}
        for name, path in self.list():
            d = self.getSubHandler(path)
            if d is self:
                print 'Skipping myself', name
                continue
            if d is None:
                print 'skipping NONE', name, path
                continue
            out[path] = d.rmodel()
        return out
    xmlrpc_rmodel = rmodel

    @classmethod
    def _pget(cls, key, self):
        """Helper function for getting a class-defined property"""
        #print 'PGET', type(self), key # this works!
        return self.get(key)

    @classmethod
    def _pset(cls, key, self, val):
        """Helper function for setting a class-defined property"""
        # FIXME: pset does not work!
        #print 'PSET', type(self), key, val
        return self.set(key, val)

    @classmethod
    def setProperties(cls, *keys):
        """Contructs class properties corresponding to Conf options."""
        for key in keys:
            if hasattr(cls, key):
                v = getattr(cls, key)
                print 'Property {} is overwriting previous attribute {}'.format(key, repr(v))
                del v
            pget = functools.partial(cls._pget, key)
            pset = functools.partial(cls._pset, key)
            p = property(pget, pset)
            setattr(cls, key, p)

    def set_preset(self, *args, **kwargs):
        """Calls applyDesc after setting the preset"""
        r = self.desc.set_preset(*args, **kwargs)
        if r:
            self.applyDesc()
        return r


    def applyDesc(self,  *a,  **k):
        """To be reimplemented."""
        return True

    def validate_preset_name(self, name):
        return select_preset_for_name(name, self.listPresets())

    def getattr(self, name, attr):
        return self.desc.gete(name)[attr]

    def setAttributes(self, name, attrlist, writeLevel=5):
        return self.desc.setAttributes(name, attrlist)
    xmlrpc_setAttributes = setAttributes

    def getFlags(self, opt):
        """Returns option flags for `opt`"""
        if self.controls.has_key(opt):
            out = {}
            pre = self.desc.getFlags(opt)
            for key, val in pre.iteritems():
                r = self.controls[opt].getFlag(key)
                print 'control getflag', key, r
                if r:
                    out[key] = val
                else:
                    out[key] = pre[key]
            self.desc.setFlags(opt, out)
        return self.desc.getFlags(opt)

    def file_list(self, opt, ext=''):
        """Update a FileList options attribute"""
        odir = self.desc.getConf_dir() + opt + '/'
        r = listDirExt(odir, ext, create=True)
        self.setattr(opt, 'options', r)
        return r

    def get(self, name, *opt):
        """Get routing.
        First searches for a get_`name` method to call,
        then for a special control, finally directly retrieve the value from memory"""
        # Check get_name existance
        if not self.desc.has_key(name):
            if len(opt) > 0:
                return opt[0]
            self.log.warning('No property: ', name)
            raise NoProperty('NoProperty: ' + name)
        # Call getter functions
        func = getattr(self, 'get_' + name, False)
        val = None
        if func:
            val = func()
            self.desc.set(name, val)
        # Call special controls
        elif self.controls.has_key(name):
            val = self.controls[name].get()
#           print 'Getting control',name,val
            self.desc.set(name, val)
        # Get a SubDict
        if isinstance(val, dict):
            return SubDict(val, self, name)
        # If intercepted by special any function, return here
        # They should take care about managing special types (Dict, FileList,
        # RoleIO)
        if val is not None:
            return val
        prop = self.desc.gete(name)
        val = prop['current']
        typ = prop.get('type', '')
        # Manage Dict-type options
        if isinstance(prop, bool) or isinstance(prop, str):
            self.log.error(
                'Wrong type for handle', name, type(prop), repr(prop))
        if typ == 'Meta':
            val = SubDict(val, self, name)
        # Update file listings on get()
        elif typ == 'FileList':
            self.file_list(name)
        # Resolve RoleIO
        elif typ == 'RoleIO':
            obj = self.roledev.get(name, False)
            # Try to remap
            if not obj:
                obj = self.map_role_dev(name)
            if obj:
                obj, pre, io = obj
                if io and obj:
                    val = obj[io.handle]
                    self.desc.set(name, val)
            else:
                val = self.desc.get(name)
        return val

    def gete(self, opt, *a, **k):
        r = self.desc.gete(opt, *a, **k)
        # Refresh file listing
        if r.get('type', '') == 'FileList':
            self.file_list(opt)
            r = self.desc.gete(opt, *a, **k)
        return r

    @property
    def root_obj(self):
        """Dummy root obj"""
        return self

    def xmlrpc_get(self, name, readLevel=0):
        """Client frontend for the `get()` method.
        Security check with `readLevel`.
        Only read values from memory if no acquisition isRunning.
        Pickle or otherwise xmlrpc-sanitize values for network transmission"""
        r = self.desc.getattr(name, 'readLevel')
        if readLevel < r:
            self.log.critical('Not authorized get', name)
            raise ReadNotAuthorized(
                'Option: %s Required: %i Level: %i' % (name, r, readLevel))
        p = self.desc.gete(name)
        if 'Hot' in p['attr']:
            if self.root_obj.get('isRunning'):
                r = self.desc.get(name)
            else:
                r = self.get(name)
        else:
            r = self.get(name)
        if p['type'] in ['Binary', 'Profile', 'Image']:
            return xmlrpc.Binary(dumps(r))
        if p['type'] == 'Meta':
            return r.copy()
        return csutil.xmlrpcSanitize(r)

    def multiget(self, opts, readLevel=0):
        """Performs get operation on a list of options, returning a {opt:val} mapping"""
        r = {}
        for opt in opts:
            r[opt] = self.xmlrpc_get(opt, readLevel=readLevel)
        return r
    xmlrpc_multiget = sanitize(multiget)

    @sanitize
    def xmlrpc_geth(self, name, readLevel=0):
        dn = self.desc.gete(name)
        rl = dn['readLevel']
        if rl > readLevel:
            self.log.critical('Not authorized geth', name)
            raise ReadNotAuthorized(
                'Option: %s, Required: %i, Level: %i' % (name, rl, readLevel))
        attr = dn.get('attr', [])
        if 'History' in attr and getattr(self.desc, 'history', False):
            return self.desc.h_get_history(name)
        return 'No history for property: ' + name

    @sanitize
    def xmlrpc_set(self, name, val, kwopt={'writeLevel': 5}):
        writeLevel = kwopt['writeLevel']
        w = self.desc.getattr(name, 'writeLevel')
        if writeLevel < w:
            self.log.critical('Not authorized set', name)
            raise WriteNotAuthorized(
                'Option: %s, Required: %i, Level: %i' % (name, w, writeLevel))
        return self.set(name, val, kwopt=kwopt)

    def setFlags(self, opt, flags):
        """Set flags for option `opt`"""
        if self.controls.has_key(opt):
            out = {}
            pre = self.desc.getFlags(opt)
            for key, val in flags.iteritems():
                r = self.controls[opt].setFlag(key, val)
                if r:
                    out[key] = val
                else:
                    out[key] = pre[key]
            flags = out
        return self.desc.setFlags(opt, flags)

    def map_role_dev(self, new=None):
        return True

    # FIXME: SET SHOULD RETURN NVAL, not (name,nval)!!!
    # Change client-side where needed
    def set(self, name,  val, t=-1, kwopt={}):
        """Set routing.
        First searches for a set_`name` method to call.
        Then searches for a control `name`.
        Finally directly set the value on memory (self.desc).
        Returns the actual value set."""
        if not self.desc:
            print 'No desc interface object', self, self.desc
            return None
        if self.desc.getEmpty() and not self.desc.has_key(name):
            self.desc.set(name, val, t)
            return name, val
        dn = self.desc.gete(name)
        oval = self.desc.get(name)
        typ = dn['type']
        # Dict-like management
        if typ == 'Meta':
            # Obtain a pure-dict object which must be picklable
            val = val.copy()
        # Role management
        elif typ == 'Role':
            if isinstance(val, str):
                val = val.split(',')
                if len(val) == 1:
                    val.append('default')
            if not (isinstance(val, list) or isinstance(val, tuple)):
                # Convert object to role list: [fullpath,preset]
                val = [val['fullpath'], val['preset']]
        # Resolve RoleIO
        # FIXME: security breach: could write to a protected opt as access
        # levels are not checked here
        elif typ == 'RoleIO':
            obj = self.roledev.get(name, False)
            # Try to remap
            if not obj:
                obj = self.map_role_dev(name)
            if obj:
                obj, pre, io = obj
                if io:
                    obj[io.handle] = val
        ### HOOKS ###
        # Setter hook
        # Search for a setter function and call it
        func = getattr(self, 'set_' + name, False)
        if func and type(func) != types.MethodType:
            func = False
        # Controls hook
        # Search if a control object has been defined in the self.controls
        # dict.
        if (not func) and self.controls.has_key(name):
            func = self.controls[name].set
        # If a valid function was found, fill implicit arguments if present
        if func:
            r = fill_implicit_args(func, (val,), kwopt)
            if not r:
                raise FunctionRoutingError()
            # Pass also filled kwargs to func
            val = func(val, **r[-1])
        ############
        if val == None:
            self.log.debug('Failed setting', name)
            return name, oval
        # SET IN MEMORY
        self.desc.set(name, val, t)
        # At the end, intercept Role mapping requests
        if typ == 'Role':
            r = self.map_role_dev(name, val)
            # Restoring old value
            if r is False:
                self.desc.set(name, oval)
        return name, val

    @sanitize
    def xmlrpc_gete(self, name, readLevel=0):
        r = self.desc.gete(name).entry.copy()
        if readLevel < r['readLevel']:
            self.log.critical('Not authorized gete', name)
            raise ReadNotAuthorized(
                'Option: %s Required: %i Level: %i' % (name, r['readLevel'], readLevel))
        r['current'] = self.xmlrpc_get(name, readLevel=readLevel)
        return r

    def xmlrpc_sete(self, name, opt, writeLevel=0):
        if writeLevel < 4:
            self.log.critical('Not authorized sete', name)
            raise WriteNotAuthorized(
                'Option: %s Required: %i Level: %i' % (name, 4, writeLevel))
        return self.sete(name, opt)

    def setConf_dir(self, cd):
        """Set the folder where the configuration should be saved."""
        self.desc.setConf_dir(cd)

    def getConf_dir(self):
        """Return the folder where the configuration should be saved."""
        return self.desc.getConf_dir()
    conf_dir = property(getConf_dir, setConf_dir)

    def setConf_obj(self, obj):
        """Set the output full path for current configuration."""
        self.desc.setConf_obj(obj)

    def getConf_obj(self):
        """Return the output full path for current configuration."""
        return self.desc.getConf_obj()
    conf_obj = property(getConf_obj, setConf_obj)

    @sanitize
    def echo(self, s='none', readLevel=0, writeLevel=0, userName=''):
        """Login demo function."""
        l = ['guest', 'analyst', 'user', 'tech', 'maint', 'admin']
        r = 'Welcome {}. \nYour role is: read={},{} / write={},{}.\nHere is your echo: {}'.format(
            userName, readLevel, l[readLevel], writeLevel, l[writeLevel], s)
        return r
    xmlrpc_echo = echo

    def check_read(self, opt, readLevel=0):
        """Check if option `opt` can be red by current user"""
        return self.getattr(opt, 'readLevel') <= readLevel
    xmlrpc_check_read = check_read

    def check_write(self, opt, writeLevel=0):
        """Check if option `opt` can be written by current user"""
        return self.getattr(opt, 'writeLevel') <= writeLevel
    xmlrpc_check_write = check_write


def select_preset_for_name(name, available_presets):
    presets = filter(lambda preset: preset in available_presets,
                     presets_from_name(name))
    selected_preset = (presets or ['default'])[0]

    if selected_preset not in available_presets:
        selected_preset = 'factory_default'

    return selected_preset

def presets_from_name(name):
    if not name:
        return []
    underscore_indexes = [i for i, ch in enumerate(name) if ch == '_']
    presets = [name]

    for underscore_index in underscore_indexes:
        presets.append(name[underscore_index+1:])

    return presets
